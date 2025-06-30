"""LLM client for communicating with language models."""

import json
from typing import Any, Dict, List, Optional

import requests
import tiktoken

from .utils import get_logger


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
        messages = self._validate_and_fix_role_alternation(messages)

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
                return self._handle_streaming_response(response)
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

    def _handle_streaming_response(self, response: requests.Response) -> str:
        """Handle streaming response from LLM.

        Args:
            response: Streaming response object

        Returns:
            Complete response text
        """
        full_response = ""
        # print("\n--- AI Response ---")

        try:
            for line in response.iter_lines():
                if line:
                    line_str = line.decode("utf-8").strip()

                    # Skip empty lines and completion marker
                    if not line_str or line_str == "data: [DONE]":
                        continue

                    if line_str.startswith("data: "):
                        line_str = line_str[6:]  # Remove "data: " prefix

                    try:
                        data = json.loads(line_str)

                        # Handle tool calls
                        choice = data.get("choices", [{}])[0]
                        delta = choice.get("delta", {})

                        if "tool_calls" in delta:
                            # Handle tool calls in streaming mode
                            tool_calls = delta["tool_calls"]
                            for tool_call in tool_calls:
                                self._handle_tool_call(tool_call)

                        content = delta.get("content", "")
                        if content:
                            print(content, end="", flush=True)
                            full_response += content

                    except json.JSONDecodeError:
                        # Some lines might not be JSON
                        continue

        except Exception as e:
            self.logger.error(f"Error processing streaming response: {e}")

        print()  # New line after streaming
        return full_response

    def _handle_tool_call(self, tool_call: Dict[str, Any]) -> None:
        """Handle tool call from LLM.

        Args:
            tool_call: Tool call information
        """
        # For now, just log tool calls
        # In a full implementation, this would execute the tool
        function_name = tool_call.get("function", {}).get("name", "unknown")
        self.logger.info(f"LLM requested tool call: {function_name}")
        print(f"[Tool Call: {function_name}]")

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
            from .context import TerminalContext

            context_manager = TerminalContext(self.config)

            # Use proper token counting for space calculation
            model = self.config.get("model", "gpt-3.5-turbo")
            system_tokens = self._count_tokens(system_prompt, model)
            query_context_tokens = self._count_tokens(
                f"{query}\n\nContext:\n{context}\n----", model
            )

            # Calculate available space for history (reserve some space for tools)
            available_context = self.config.get_available_context_size()
            tools_tokens = self._count_tokens_for_tools(tools, model) if tools else 0
            used_tokens = system_tokens + query_context_tokens + tools_tokens

            # Reserve at least 200 tokens for conversation buffer, use conservative
            # limit for history
            available_for_history = max(
                0, min(500, (available_context - used_tokens - 200))
            )

            conversation_history = context_manager.get_conversation_history(
                available_for_history
            )
            self.logger.debug(
                f"Loaded {len(conversation_history)} history messages, "
                f"targeting {available_for_history} tokens"
            )

            # Ensure conversation history has proper role alternation
            conversation_history = self._fix_conversation_history_roles(
                conversation_history
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
            managed_payload = self._manage_context_with_tools(
                conversation_messages, tools
            )
            if not managed_payload:
                self.logger.error("Could not fit conversation within context limits")
                break

            conversation_messages = managed_payload["messages"]
            current_tools = managed_payload.get("tools")

            # Make request to LLM with managed context
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
                if stream:
                    print(content, end="", flush=True)

            if tool_calls:
                self.logger.debug(
                    f"Processing {len(tool_calls)} tool calls in iteration {iteration}"
                )
                # Add assistant message with tool calls to conversation
                conversation_messages.append(
                    {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls,
                    }
                )

                # Execute each tool call
                for tool_call in tool_calls:
                    tool_call_id = tool_call.get("id", f"call_{iteration}")
                    function = tool_call.get("function", {})
                    function_name = function.get("name", "")

                    self.logger.info(f"Executing tool: {function_name}")
                    print(f"[Tool Call: {function_name}]")

                    # Execute the tool
                    try:
                        result = self._execute_tool_call(
                            function_name,
                            function.get("arguments", "{}"),
                            tools,
                        )

                        # Debug: log the raw tool result to understand its format
                        self.logger.debug(
                            f"Raw tool result for {function_name}: {type(result)} = "
                            f"{str(result)[:300]}..."
                        )

                        # Smart context management for tool results
                        # Calculate remaining context budget after conversation
                        # so far using proper token counting
                        conversation_tokens = self._count_tokens_for_messages(
                            conversation_messages,
                            self.config.get("model", "gpt-3.5-turbo"),
                        )
                        remaining_context = max_context_size - conversation_tokens

                        # Reserve space for continued conversation (at least 200 tokens)
                        available_for_result = max(200, remaining_context // 2)
                        # Use token-aware truncation instead of character estimation
                        max_result_tokens = available_for_result

                        # Helper function to truncate content to token limit
                        def truncate_to_tokens(text: str, max_tokens: int) -> str:
                            """Truncate text to fit within token limit."""
                            current_tokens = self._count_tokens(
                                text, self.config.get("model", "gpt-3.5-turbo")
                            )
                            if current_tokens <= max_tokens:
                                return text

                            # Simple approach: cut to estimated length and verify
                            estimated_chars = max_tokens * 3  # Conservative estimate
                            if estimated_chars < len(text):
                                truncated = (
                                    text[:estimated_chars]
                                    + f"... [Result truncated to fit "
                                    f"{max_tokens} token limit]"
                                )
                                if (
                                    self._count_tokens(
                                        truncated,
                                        self.config.get("model", "gpt-3.5-turbo"),
                                    )
                                    <= max_tokens
                                ):
                                    return truncated
                                # If still too long, cut more aggressively
                                truncated = (
                                    text[: estimated_chars // 2] + "... [Truncated]"
                                )
                                return truncated
                            return text

                        # Extract and format tool result for LLM consumption
                        result_content = ""

                        if isinstance(result, dict):
                            # Handle MCP response format
                            if "content" in result:
                                content_obj = result.get("content")
                                if (
                                    isinstance(content_obj, list)
                                    and len(content_obj) > 0
                                ):
                                    # MCP format: {"content": [{"type": "text",
                                    # "text": "..."}]}
                                    first_content = content_obj[0]
                                    if (
                                        isinstance(first_content, dict)
                                        and "text" in first_content
                                    ):
                                        result_content = first_content["text"]
                                    else:
                                        result_content = str(first_content)
                                elif isinstance(content_obj, str):
                                    # Simple string content
                                    result_content = content_obj
                                else:
                                    result_content = str(content_obj)
                            elif "result" in result:
                                # Alternative result format
                                result_content = str(result["result"])
                            else:
                                # Fallback: stringify the entire dict but make it
                                # readable
                                if len(str(result)) > 500:
                                    # For large results, try to extract key information
                                    important_keys = [
                                        "output",
                                        "stdout",
                                        "result",
                                        "data",
                                        "response",
                                    ]
                                    for key in important_keys:
                                        if key in result:
                                            result_content = str(result[key])
                                            break
                                if not result_content:
                                    result_content = json.dumps(result, indent=2)
                        else:
                            # Non-dict result
                            result_content = str(result)

                        # Apply token-based truncation
                        result_content = truncate_to_tokens(
                            result_content, max_result_tokens
                        )

                        self.logger.debug(
                            f"Processed tool result for {function_name}: "
                            f"{result_content[:200]}..."
                        )

                        # Add tool result to conversation
                        conversation_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": result_content,
                            }
                        )

                        self.logger.debug(
                            f"Tool {function_name} result: {result_content[:200]}..."
                        )

                    except Exception as e:
                        self.logger.error(f"Tool execution failed: {e}")
                        # Add error result to conversation
                        conversation_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": f"Error: {str(e)}",
                            }
                        )

                # Continue conversation with tool results
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

        if stream:
            print()  # New line after streaming

        # If we have partial response but no final response, return what we have
        if not final_response and iteration > 1:
            final_response = "Tool execution completed successfully."

        return final_response

    def _execute_tool_call(
        self,
        function_name: str,
        arguments_str: str,
        tools: List[Dict[str, Any]],
    ) -> Any:
        """Execute a tool call via the MCP client.

        Args:
            function_name: Name of the function to call
            arguments_str: JSON string of function arguments
            tools: List of available tools

        Returns:
            Tool execution result
        """
        # Find the tool and its server
        tool_info = None
        for tool in tools:
            if tool.get("function", {}).get("name") == function_name:
                tool_info = tool
                break

        if not tool_info:
            raise Exception(f"Tool {function_name} not found")

        server_name = tool_info.get("server")
        if not server_name:
            raise Exception(f"No server specified for tool {function_name}")

        # Parse arguments
        try:
            arguments = json.loads(arguments_str) if arguments_str else {}
            self.logger.debug(
                f"Calling tool {function_name} with arguments: {arguments}"
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid tool arguments: {e}")

        # Execute via MCP client
        return self.mcp_client.call_tool(function_name, server_name, arguments)

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
        messages = self._validate_and_fix_role_alternation(messages)

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

        # Final token count verification for debugging
        model = self.config.get("model", "gpt-3.5-turbo")
        final_tokens = self._count_tokens_for_payload(payload, model)
        self.logger.debug(f"Final payload tokens: {final_tokens}")

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
                    estimated_tokens = self._count_tokens(payload_str, model)
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

    def _validate_and_fix_role_alternation(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Validate and fix message role alternation for API compatibility.

        OpenAI API requires proper message flow:
        - [system] (optional)
        - user, assistant (with optional tool_calls), tool (responses to tool_calls),
          assistant, ...
        - Tool messages must immediately follow assistant messages with tool_calls

        Args:
            messages: List of message dictionaries

        Returns:
            Fixed list of messages with proper role alternation
        """
        if not messages:
            return messages

        # Check for tool calls - if there are tool calls, preserve all messages
        has_tool_calls = any(
            msg.get("tool_calls") or msg.get("role") == "tool" for msg in messages
        )

        if has_tool_calls:
            # For tool-based conversations, trust the structure and just validate
            # basic requirements
            fixed_messages = []

            # Handle system message separately
            if messages and messages[0].get("role") == "system":
                fixed_messages.append(messages[0])
                remaining_messages = messages[1:]
            else:
                remaining_messages = messages

            # Process messages while preserving tool calls and tool responses
            i = 0
            while i < len(remaining_messages):
                message = remaining_messages[i]
                role = message.get("role", "")

                if role in ["user", "assistant", "tool"]:
                    # All these roles are valid in OpenAI API
                    fixed_messages.append(message)

                    # If this is an assistant message with tool calls,
                    # make sure any following tool messages are preserved
                    if role == "assistant" and message.get("tool_calls"):
                        # Look ahead for tool response messages
                        j = i + 1
                        while (
                            j < len(remaining_messages)
                            and remaining_messages[j].get("role") == "tool"
                        ):
                            fixed_messages.append(remaining_messages[j])
                            j += 1
                        i = j - 1  # Skip the tool messages we just added

                i += 1

            return fixed_messages

        # For simple conversations without tool calls, ensure proper alternation
        # but preserve the structure if it's already reasonable
        fixed_messages = []

        # Handle system message separately
        if messages and messages[0].get("role") == "system":
            fixed_messages.append(messages[0])
            remaining_messages = messages[1:]
        else:
            remaining_messages = messages

        if not remaining_messages:
            return fixed_messages

        # Check if the sequence is already properly alternating
        non_system_roles = [msg.get("role") for msg in remaining_messages]
        is_properly_alternating = True

        for i, role in enumerate(non_system_roles):
            if role not in ["user", "assistant"]:
                continue
            expected = "user" if i % 2 == 0 else "assistant"
            if role != expected:
                is_properly_alternating = False
                break

        if is_properly_alternating:
            # Already properly alternating, keep as-is
            fixed_messages.extend(remaining_messages)
        else:
            # Apply strict alternation fix, but preserve the last message if it's
            # a user message (which is likely the current query)
            last_message = remaining_messages[-1] if remaining_messages else None

            if last_message and last_message.get("role") == "user":
                # Process all but the last message with strict alternation
                history_to_fix = remaining_messages[:-1]
                current_query = last_message

                # Fix the history part
                fixed_history = self._fix_conversation_history_roles(history_to_fix)
                fixed_messages.extend(fixed_history)

                # Always add the current user query at the end
                fixed_messages.append(current_query)
            else:
                # No special last user message to preserve, apply full fix
                fixed_history = self._fix_conversation_history_roles(remaining_messages)
                fixed_messages.extend(fixed_history)

        # Final validation: ensure we have a reasonable conversation flow
        roles = [msg.get("role") for msg in fixed_messages]
        self.logger.debug(f"Role validation result: {roles}")

        return fixed_messages

    def _fix_conversation_history_roles(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fix conversation history to ensure proper role alternation.

        This ensures that conversation history follows the pattern:
        user, assistant, user, assistant, ...
        and filters out incomplete pairs.

        Args:
            messages: List of conversation history messages

        Returns:
            Fixed list of messages with proper role alternation
        """
        if not messages:
            return messages

        fixed_messages = []

        # Group messages into user-assistant pairs
        i = 0
        while i < len(messages):
            message = messages[i]
            role = message.get("role", "")

            if role == "user":
                # Look for the following assistant message
                user_msg = message
                assistant_msg = None

                # Check if there's an assistant response
                if i + 1 < len(messages) and messages[i + 1].get("role") == "assistant":
                    assistant_msg = messages[i + 1]
                    i += 2  # Skip both messages
                else:
                    # Skip incomplete user message without assistant response
                    i += 1
                    continue

                # Add the complete pair
                fixed_messages.append(user_msg)
                fixed_messages.append(assistant_msg)

            elif role == "assistant":
                # Skip assistant messages that don't follow user messages
                # (these are incomplete pairs)
                i += 1
                continue
            else:
                # Skip other roles (system, tool, etc.)
                i += 1
                continue

        self.logger.debug(
            f"Fixed conversation history: {len(messages)} -> "
            f"{len(fixed_messages)} messages"
        )
        roles = [msg.get("role") for msg in fixed_messages]
        self.logger.debug(f"Fixed conversation history roles: {roles}")

        return fixed_messages

    def _manage_context_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Comprehensive context management for messages and tools.

        This method ensures the entire request (messages + tools) fits within
        the model's context window, following both OpenAI API and MCP specifications.
        Tools are provided only via the API 'tools' field, not in system prompts.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tool definitions

        Returns:
            Managed payload dict with 'messages' and optionally 'tools', or None
            if impossible to fit
        """
        model = self.config.get("model", "gpt-3.5-turbo")
        max_context = (
            self.config.get_total_context_size()
            - self.config.get_response_buffer_size()
        )

        # Start with current messages and tools
        current_messages = messages.copy()
        current_tools = tools.copy() if tools else None

        # Calculate total tokens needed
        def calculate_total_tokens() -> int:
            msg_tokens = self._count_tokens_for_messages(current_messages, model)
            tool_tokens = (
                self._count_tokens_for_tools(current_tools, model)
                if current_tools
                else 0
            )
            return msg_tokens + tool_tokens

        total_tokens = calculate_total_tokens()
        self.logger.debug(
            f"Initial request size: {total_tokens} tokens (max: {max_context})"
        )

        # If we fit, return as-is
        if total_tokens <= max_context:
            return {"messages": current_messages, "tools": current_tools}

        self.logger.warning(
            f"Request too large ({total_tokens} tokens), applying context management"
        )

        # Step 1: Try reducing tools first (keep most essential tools)
        if current_tools and len(current_tools) > 10:
            # Prioritize tools by name patterns (keep essential system/file tools)
            essential_tools = []
            other_tools = []

            for tool in current_tools:
                tool_name = tool.get("function", {}).get("name", "").lower()
                if any(
                    keyword in tool_name
                    for keyword in [
                        "file",
                        "read",
                        "write",
                        "list",
                        "directory",
                        "system",
                        "execute",
                        "command",
                    ]
                ):
                    essential_tools.append(tool)
                else:
                    other_tools.append(tool)

            # Start with essential tools only
            current_tools = essential_tools[:10]  # Limit to 10 essential tools
            total_tokens = calculate_total_tokens()

            if total_tokens <= max_context:
                self.logger.info(
                    f"Reduced tools from {len(tools) if tools else 0} to "
                    f"{len(current_tools) if current_tools else 0} essential tools"
                )
                return {"messages": current_messages, "tools": current_tools}

        # Step 2: If still too large, reduce tools more aggressively
        if current_tools and total_tokens > max_context:
            # Try with just 5 most essential tools
            if len(current_tools) > 5:
                current_tools = current_tools[:5]
                total_tokens = calculate_total_tokens()

                if total_tokens <= max_context:
                    self.logger.info("Reduced to top 5 essential tools")
                    return {
                        "messages": current_messages,
                        "tools": current_tools,
                    }

        # Step 3: If still too large, try without tools entirely
        if total_tokens > max_context:
            current_tools = None
            total_tokens = calculate_total_tokens()

            if total_tokens <= max_context:
                self.logger.warning("Removed all tools to fit context limit")
                return {"messages": current_messages, "tools": None}

        # Step 4: Trim messages using existing logic
        if total_tokens > max_context:
            self.logger.info("Trimming messages to fit context")
            # Calculate available space for messages (accounting for tools if any)
            tool_tokens = (
                self._count_tokens_for_tools(current_tools, model)
                if current_tools
                else 0
            )
            available_for_messages = max_context - tool_tokens

            trimmed_messages = self._trim_messages_to_fit(
                current_messages, available_for_messages, model
            )

            # Recalculate with trimmed messages
            current_messages = trimmed_messages
            total_tokens = calculate_total_tokens()

            if total_tokens <= max_context:
                final_msg_tokens = self._count_tokens_for_messages(
                    current_messages, model
                )
                final_tool_tokens = (
                    self._count_tokens_for_tools(current_tools, model)
                    if current_tools
                    else 0
                )
                self.logger.info(
                    f"Final context: {final_msg_tokens} message tokens + "
                    f"{final_tool_tokens} tool tokens = {total_tokens} total"
                )
                return {"messages": current_messages, "tools": current_tools}

        # Step 5: Last resort - minimal payload
        if total_tokens > max_context:
            self.logger.error("Cannot fit request even with aggressive trimming")
            # Try with just system message and latest user message, no tools
            minimal_messages = []
            if current_messages and current_messages[0].get("role") == "system":
                minimal_messages.append(current_messages[0])

            # Add the most recent user message
            for msg in reversed(current_messages):
                if msg.get("role") == "user":
                    minimal_messages.append(msg)
                    break

            minimal_tokens = self._count_tokens_for_messages(minimal_messages, model)
            if minimal_tokens <= max_context:
                self.logger.warning(
                    "Using minimal payload: system + last user message only"
                )
                return {"messages": minimal_messages, "tools": None}

        # If we can't fit even the minimal payload, something is very wrong
        self.logger.error("Cannot fit even minimal request within context limits")
        return None

    def _trim_messages_to_fit(
        self, messages: List[Dict[str, Any]], max_tokens: int, model: str
    ) -> List[Dict[str, Any]]:
        """Trim messages to fit within a token limit.

        Args:
            messages: List of message dictionaries
            max_tokens: Maximum allowed tokens for messages
            model: Model name for tokenizer

        Returns:
            Trimmed messages that fit within token limits
        """
        if not messages:
            return messages

        # Calculate total tokens in current conversation using proper token counting
        total_tokens = self._count_tokens_for_messages(messages, model)

        # If we're within limits, return as-is
        if total_tokens <= max_tokens:
            return messages

        self.logger.warning(
            f"Messages too large ({total_tokens} tokens), trimming to {max_tokens}"
        )

        # Need to trim - keep system message and recent important messages
        trimmed_messages = []
        remaining_budget = max_tokens

        # Always keep system message (first message)
        if messages and messages[0].get("role") == "system":
            system_msg = messages[0]
            system_tokens = self._count_tokens_for_messages([system_msg], model)
            if system_tokens <= remaining_budget:
                trimmed_messages.append(system_msg)
                remaining_budget -= system_tokens
            remaining_messages = messages[1:]
        else:
            remaining_messages = messages

        # Prioritize recent messages, especially user messages and tool results
        # Work backwards from most recent messages
        for message in reversed(remaining_messages):
            message_tokens = self._count_tokens_for_messages([message], model)
            role = message.get("role", "")

            # Always try to keep recent user messages and tool results
            if role in ["user", "tool"] or message_tokens <= remaining_budget:
                if message_tokens <= remaining_budget:
                    trimmed_messages.insert(
                        (-1 if len(trimmed_messages) > 1 else len(trimmed_messages)),
                        message,
                    )
                    remaining_budget -= message_tokens
                else:
                    # Try to fit a truncated version for important messages
                    if (
                        role in ["user", "tool"] and remaining_budget > 100
                    ):  # Need reasonable space
                        content = str(message.get("content", ""))
                        # Truncate to fit remaining budget (rough estimation)
                        max_chars = remaining_budget * 3  # Conservative estimate
                        if len(content) > max_chars:
                            truncated_content = (
                                content[:max_chars]
                                + "... [truncated for context limit]"
                            )
                            truncated_message = message.copy()
                            truncated_message["content"] = truncated_content
                            truncated_tokens = self._count_tokens_for_messages(
                                [truncated_message], model
                            )
                            if truncated_tokens <= remaining_budget:
                                trimmed_messages.insert(
                                    (
                                        -1
                                        if len(trimmed_messages) > 1
                                        else len(trimmed_messages)
                                    ),
                                    truncated_message,
                                )
                                remaining_budget -= truncated_tokens
                    break

        final_tokens = self._count_tokens_for_messages(trimmed_messages, model)
        self.logger.info(
            f"Messages trimmed from {total_tokens} to {final_tokens} tokens"
        )
        return trimmed_messages

    def _count_tokens(self, text: str, model: str = "gpt-3.5-turbo") -> int:
        """Count tokens in text using tiktoken.

        Args:
            text: Text to count tokens for
            model: Model name for tokenizer (defaults to gpt-3.5-turbo)

        Returns:
            Number of tokens
        """
        try:
            # Get encoding for the model
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except KeyError:
            # Fallback to cl100k_base encoding if model not found
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception as e:
            # Fallback to character estimation if tiktoken fails
            self.logger.warning(
                f"Token counting failed, using character estimation: {e}"
            )
            return len(text) // 3  # Conservative fallback

    def _count_tokens_for_messages(
        self, messages: List[Dict[str, Any]], model: str = "gpt-3.5-turbo"
    ) -> int:
        """Count tokens for a list of messages including OpenAI format overhead.

        Args:
            messages: List of message dictionaries
            model: Model name for tokenizer

        Returns:
            Total token count including message formatting overhead
        """
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fallback to simple estimation
            total_chars = sum(
                len(str(msg.get("content", ""))) + len(str(msg.get("role", "")))
                for msg in messages
            )
            return total_chars // 3

        total_tokens = 0

        for message in messages:
            # Each message has overhead tokens for role and message structure
            total_tokens += 4  # Base overhead per message

            for key, value in message.items():
                if isinstance(value, str):
                    total_tokens += len(encoding.encode(value))
                elif isinstance(value, list):
                    # Handle tool_calls or other list content
                    total_tokens += len(encoding.encode(str(value)))

        # Add overhead for conversation structure
        total_tokens += 2  # Conversation-level overhead

        return total_tokens

    def _count_tokens_for_payload(
        self, payload: Dict[str, Any], model: str = "gpt-3.5-turbo"
    ) -> int:
        """Count tokens for a complete API payload including all fields.

        Args:
            payload: Complete API payload dictionary
            model: Model name for tokenizer

        Returns:
            Total token count for the payload
        """
        try:
            # Convert entire payload to JSON and count tokens
            payload_json = json.dumps(payload)
            return self._count_tokens(payload_json, model)
        except Exception as e:
            self.logger.warning(f"Payload token counting failed: {e}")
            # Fallback: sum individual components
            total = 0

            # Count messages
            if "messages" in payload:
                total += self._count_tokens_for_messages(payload["messages"], model)

            # Count tools
            if "tools" in payload:
                total += self._count_tokens_for_tools(payload["tools"], model)

            # Add overhead for other fields (model, stream, etc.)
            total += 50  # Conservative overhead estimate

            return total

    def _count_tokens_for_tools(
        self, tools: List[Dict[str, Any]], model: str = "gpt-3.5-turbo"
    ) -> int:
        """Count tokens for tools definition including JSON overhead.

        Args:
            tools: List of tool definitions
            model: Model name for tokenizer

        Returns:
            Total token count for tools
        """
        if not tools:
            return 0

        try:
            tools_json = json.dumps(tools)
            return self._count_tokens(tools_json, model)
        except Exception as e:
            self.logger.warning(f"Tools token counting failed: {e}")
            # Fallback estimation
            return len(str(tools)) // 3


class LLMError(Exception):
    """Exception raised for LLM-related errors."""

    pass
