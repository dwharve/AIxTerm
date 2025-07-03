"""LLM client for communicating with language models."""

import json
from typing import Any, Dict, List, Optional

import requests

from ..context import TokenManager, ToolOptimizer
from ..utils import get_logger
from .exceptions import LLMError
from .message_validator import MessageValidator
from .streaming import StreamingHandler
from .tools import ToolHandler


class LLMClient:
    """Client for communicating with OpenAI-compatible LLM APIs."""

    def __init__(self, config_manager: Any, mcp_client: Any = None) -> None:
        """Initialize LLM client.

        Args:
            config_manager: AIxTermConfig instance
            mcp_client: MCP client instance for tool execution
        """
        self.config = config_manager
        self.mcp_client = mcp_client
        self.logger = get_logger(__name__)

        # Initialize helper components
        self.token_manager = TokenManager(config_manager, self.logger)
        self.tool_optimizer = ToolOptimizer(
            config_manager, self.logger, self.token_manager
        )
        self.message_validator = MessageValidator(config_manager, self.logger)
        self.streaming_handler = StreamingHandler(config_manager, self.logger)
        self.tool_handler = ToolHandler(config_manager, mcp_client, self.logger)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        stream: bool = True,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Send chat completion request to LLM.

        Args:
            messages: List of message dictionaries
            stream: Whether to stream the response
            tools: Optional list of tools for the LLM

        Returns:
            Complete response text
        """
        # If tools are provided and MCP client is available, use conversation flow
        if tools and self.mcp_client:
            return self._chat_completion_with_tools(messages, tools, stream)
        else:
            return self._basic_chat_completion(messages, stream, tools)

    def _basic_chat_completion(
        self,
        messages: List[Dict[str, str]],
        stream: bool = True,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Basic chat completion without tool execution.

        Args:
            messages: List of message dictionaries
            stream: Whether to stream the response
            tools: Optional list of tools for the LLM

        Returns:
            Complete response text
        """
        # Validate and fix message role alternation for API compatibility
        messages = self.message_validator.validate_and_fix_role_alternation(messages)

        # Log the final message sequence for debugging
        role_sequence = [msg.get("role", "unknown") for msg in messages]
        self.logger.debug(f"Basic completion message role sequence: {role_sequence}")

        headers = {
            "Content-Type": "application/json",
        }

        api_key = self.config.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": self.config.get("model", "local-model"),
            "stream": stream,
            "messages": messages,
        }

        # Add tools if provided
        if tools:
            payload["tools"] = tools
            # Some models expect tool_choice to be set
            payload["tool_choice"] = "auto"

        try:
            response = requests.post(
                self.config.get("api_url", "http://localhost/v1/chat/completions"),
                headers=headers,
                json=payload,
                stream=stream,
                timeout=30,
            )
            response.raise_for_status()

            if stream:
                return self.streaming_handler.handle_streaming_response(response)
            else:
                data = response.json()
                content: str = data["choices"][0]["message"]["content"]
                return content

        except requests.exceptions.RequestException as e:
            self.logger.error(f"LLM request failed: {e}")
            raise LLMError(f"Error communicating with LLM: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in LLM request: {e}")
            raise LLMError(f"Unexpected error: {e}")

    def ask_with_context(
        self,
        query: str,
        context: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        use_planning: bool = False,
    ) -> str:
        """Ask LLM with terminal context and conversation history.

        Args:
            query: User query
            context: Terminal context
            tools: Optional tools for the LLM
            use_planning: Whether to use planning-focused prompt

        Returns:
            LLM response
        """
        if use_planning:
            base_system_prompt = self.config.get(
                "planning_system_prompt",
                "You are a strategic planning AI assistant. When given a task "
                "or problem, break it down into clear, actionable steps. Create "
                "detailed plans that consider dependencies, potential issues, and "
                "alternative approaches. Use tool calls to execute commands and "
                "perform actions. Always think through the complete workflow "
                "before starting and explain your reasoning.",
            )
        else:
            base_system_prompt = self.config.get(
                "system_prompt", "You are a terminal AI assistant."
            )

        # System prompt should NOT include tool descriptions - tools are provided
        # via API field. This follows OpenAI API and MCP specifications properly
        # and saves tokens
        system_prompt = base_system_prompt

        # Build initial messages
        messages = [{"role": "system", "content": system_prompt}]

        # Get conversation history using proper token counting
        try:
            # Import here to avoid circular imports
            from ..context import TerminalContext

            context_manager_terminal = TerminalContext(self.config)

            # Use proper token counting for space calculation
            model = self.config.get("model", "gpt-3.5-turbo")
            system_tokens = self.token_manager.estimate_tokens(system_prompt)
            query_context_tokens = self.token_manager.estimate_tokens(
                f"{query}\n\nContext:\n{context}\n----"
            )

            # Calculate available space for history (reserve some space for tools)
            available_context = self.config.get_available_context_size()
            tools_tokens = (
                self.token_manager.count_tokens_for_tools(tools, model) if tools else 0
            )
            used_tokens = system_tokens + query_context_tokens + tools_tokens

            # Reserve at least 200 tokens for conversation buffer, use conservative
            # limit for history
            available_for_history = max(
                0, min(500, (available_context - used_tokens - 200))
            )

            conversation_history = context_manager_terminal.get_conversation_history(
                available_for_history
            )
            self.logger.debug(
                f"Loaded {len(conversation_history)} history messages, "
                f"targeting {available_for_history} tokens"
            )

            # Ensure conversation history has proper role alternation
            conversation_history = (
                self.message_validator.fix_conversation_history_roles(
                    conversation_history
                )
            )
            messages.extend(conversation_history)

        except Exception as e:
            self.logger.warning(f"Could not get conversation history: {e}")

        # Add current query with context
        messages.append(
            {
                "role": "user",
                "content": f"{query}\n\nContext:\n{context}\n----",
            }
        )

        return self.chat_completion(messages, stream=True, tools=tools)

    def _chat_completion_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        stream: bool = True,
    ) -> str:
        """Handle chat completion with tool execution capability.

        Args:
            messages: List of message dictionaries
            tools: List of available tools
            stream: Whether to stream the response

        Returns:
            Complete response text including tool results
        """
        conversation_messages = messages.copy()
        max_iterations = 5  # Prevent infinite loops
        iteration = 0
        final_response = ""

        # Get context size limits from config
        max_context_size = self.config.get_available_context_size()

        while iteration < max_iterations:
            iteration += 1
            self.logger.debug(f"Chat iteration {iteration}/{max_iterations}")

            # Use centralized context management for both messages and tools
            # This ensures protocol compliance and proper token management
            managed_payload = self.tool_optimizer.manage_context_with_tools(
                conversation_messages, tools
            )
            if not managed_payload:
                self.logger.error("Could not fit conversation within context limits")
                break

            conversation_messages = managed_payload["messages"]
            current_tools = managed_payload.get("tools")

            # Make request to LLM with managed context
            if stream:
                # Handle streaming response with tools
                response_text, tool_calls = (
                    self.streaming_handler.handle_streaming_with_tools(
                        conversation_messages, current_tools
                    )
                )

                if response_text:
                    final_response += response_text

                # Process tool calls if any
                if tool_calls:
                    self.logger.debug(
                        f"Processing {len(tool_calls)} tool calls in iteration "
                        f"{iteration}"
                    )
                    # Add assistant message with tool calls to conversation
                    conversation_messages.append(
                        {
                            "role": "assistant",
                            "content": response_text,
                            "tool_calls": tool_calls,
                        }
                    )

                    # Process tool calls (same logic as non-streaming)
                    self.tool_handler.process_tool_calls(
                        tool_calls,
                        conversation_messages,
                        tools,
                        iteration,
                        max_context_size,
                    )
                    continue
                else:
                    # No tool calls, we're done
                    break
            else:
                response_data = self._make_llm_request(
                    conversation_messages, current_tools, stream=False
                )

                if not response_data:
                    self.logger.warning(
                        f"No response data from LLM in iteration {iteration}"
                    )
                    break

                choices = response_data.get("choices", [])
                if not choices:
                    self.logger.warning(
                        f"No choices in response data in iteration {iteration}"
                    )
                    break

                choice = choices[0]
                message = choice.get("message", {})

                # Check if LLM wants to use tools
                tool_calls = message.get("tool_calls")
                content = message.get("content", "")

                self.logger.debug(
                    f"Iteration {iteration}: content={bool(content)}, "
                    f"tool_calls={bool(tool_calls)}"
                )

                if content:
                    final_response += content

                if tool_calls:
                    self.logger.debug(
                        f"Processing {len(tool_calls)} tool calls in iteration "
                        f"{iteration}"
                    )
                    # Add assistant message with tool calls to conversation
                    conversation_messages.append(
                        {
                            "role": "assistant",
                            "content": content,
                            "tool_calls": tool_calls,
                        }
                    )

                    # Process tool calls
                    self.tool_handler.process_tool_calls(
                        tool_calls,
                        conversation_messages,
                        tools,
                        iteration,
                        max_context_size,
                    )
                    continue
                else:
                    # No more tool calls, we're done
                    self.logger.debug(
                        f"No tool calls in iteration {iteration}, ending conversation"
                    )
                    break

        if iteration >= max_iterations:
            self.logger.warning(
                f"Reached maximum iterations ({max_iterations}), stopping conversation"
            )

        # If we have partial response but no final response, return what we have
        if not final_response and iteration > 1:
            final_response = "Tool execution completed successfully."

        return final_response

    def _make_llm_request(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Make a request to the LLM API.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tools
            stream: Whether to stream response

        Returns:
            Response data or None if failed
        """
        # Context management should have been handled by the caller
        # This method focuses solely on API communication

        # Validate and fix message role alternation for API compatibility
        messages = self.message_validator.validate_and_fix_role_alternation(messages)

        # Log the final message sequence for debugging
        role_sequence = [msg.get("role", "unknown") for msg in messages]
        self.logger.debug(f"Message role sequence: {role_sequence}")

        headers = {
            "Content-Type": "application/json",
        }

        api_key = self.config.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": self.config.get("model", "local-model"),
            "stream": stream,
            "messages": messages,
        }

        # Add tools to payload according to OpenAI API and MCP specifications
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
            # Debug: Log the tools being sent to the model
            self.logger.debug(
                f"Sending {len(tools)} tools to model "
                f"{self.config.get('model', 'local-model')}"
            )
            for i, tool in enumerate(tools[:3]):  # Log first 3 tools
                self.logger.debug(f"Tool {i}: {json.dumps(tool, indent=2)}")

        # Final token count verification for debugging
        model = self.config.get("model", "gpt-3.5-turbo")
        final_tokens = self.token_manager.count_tokens_for_payload(payload, model)
        self.logger.debug(f"Final payload tokens: {final_tokens}")

        # Debug: Log the complete payload structure (without full content for brevity)
        debug_payload = {
            "model": payload["model"],
            "stream": payload["stream"],
            "messages": f"{len(payload['messages'])} messages",
            "tools": f"{len(payload.get('tools', []))} tools" if tools else "no tools",
            "tool_choice": payload.get("tool_choice", "not set"),
        }
        self.logger.debug(
            f"Complete payload structure: " f"{json.dumps(debug_payload, indent=2)}"
        )

        try:
            response = requests.post(
                self.config.get("api_url", "http://localhost/v1/chat/completions"),
                headers=headers,
                json=payload,
                stream=stream,
                timeout=30,
            )
            response.raise_for_status()

            self.logger.debug(f"LLM response status: {response.status_code}")

            if stream:
                # For streaming, we'd need different handling
                # For now, return None to indicate streaming not supported in
                # this context
                return None
            else:
                response_data: Dict[str, Any] = response.json()
                self.logger.debug(
                    f"LLM response data: {json.dumps(response_data, indent=2)[:500]}..."
                )
                return response_data

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                self.logger.error(f"LLM request rejected (400 error): {e}")
                # Log payload size for debugging
                try:
                    payload_str = json.dumps(payload)
                    payload_size = len(payload_str)
                    estimated_tokens = self.token_manager.estimate_tokens(payload_str)
                    self.logger.error(
                        f"Failed payload size: {payload_size} chars, "
                        f"{estimated_tokens} tokens"
                    )
                except Exception:
                    pass
            elif e.response.status_code == 500:
                # Server error - could be due to role alternation or other API issues
                self.logger.error(f"Server error (500): {e}")
                try:
                    # Try to get error details from response
                    error_details = e.response.text
                    if "roles must alternate" in error_details.lower():
                        self.logger.error(
                            "Server rejected request due to role alternation issues"
                        )
                        # Log the message sequence for debugging
                        role_sequence = [msg.get("role", "unknown") for msg in messages]
                        self.logger.error(f"Message role sequence was: {role_sequence}")
                    self.logger.debug(f"Server error details: {error_details[:500]}")
                except Exception:
                    pass

            self.logger.error(f"LLM request failed: {e}")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"LLM request failed: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error in LLM request: {e}")
            return None

    # Delegation methods for backward compatibility with tests
    def _validate_and_fix_role_alternation(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Delegate to message validator for backward compatibility."""
        return self.message_validator.validate_and_fix_role_alternation(messages)

    def _count_tokens(self, text: str, model: str = "gpt-3.5-turbo") -> int:
        """Delegate to token manager for backward compatibility."""
        return self.token_manager.estimate_tokens(text)

    def _count_tokens_for_messages(
        self, messages: List[Dict[str, Any]], model: str = "gpt-3.5-turbo"
    ) -> int:
        """Delegate to token manager for backward compatibility."""
        return self.token_manager.count_tokens_for_messages(messages, model)

    def _count_tokens_for_tools(
        self, tools: List[Dict[str, Any]], model: str = "gpt-3.5-turbo"
    ) -> int:
        """Delegate to token manager for backward compatibility."""
        return self.token_manager.count_tokens_for_tools(tools, model)

    def _handle_streaming_response(self, response: Any) -> str:
        """Delegate to streaming handler for backward compatibility."""
        return self.streaming_handler.handle_streaming_response(response)

    def _handle_tool_call(self, tool_call: Dict[str, Any]) -> None:
        """Delegate to streaming handler for backward compatibility."""
        return self.streaming_handler.handle_tool_call(tool_call)
