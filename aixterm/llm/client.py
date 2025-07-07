"""LLM client for communicating with language models."""

import json
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

from ..context import TokenManager, ToolOptimizer
from ..utils import get_logger
from .exceptions import LLMError
from .message_validator import MessageValidator
from .tools import ToolHandler


class LLMClient:
    """Client for communicating with OpenAI-compatible LLM APIs."""

    def __init__(
        self,
        config_manager: Any,
        mcp_client: Any,
        progress_callback_factory: Optional[Callable] = None,
        display_manager: Any = None,
    ):
        """Initialize LLM client.

        Args:
            config_manager: Configuration manager instance
            mcp_client: MCP client instance for tool calls
            progress_callback_factory: Optional factory for creating progress callbacks
            display_manager: Display manager for progress and output
        """
        self.config = config_manager
        self.mcp_client = mcp_client
        self.progress_callback_factory = progress_callback_factory
        self.display_manager = display_manager
        self.logger = get_logger(__name__)

        # Initialize OpenAI client
        api_key = self.config.get("api_key")
        base_url = self.config.get("api_url", "http://localhost/v1")

        # Convert full endpoint URL to base URL for OpenAI client
        # OpenAI client expects base URL to end with /v1, not the full endpoint
        if base_url.endswith("/chat/completions"):
            base_url = base_url.replace("/chat/completions", "")

        self.openai_client = OpenAI(
            api_key=api_key or "dummy-key",  # Some local APIs don't require real keys
            base_url=base_url,
        )

        # Initialize helper components
        self.token_manager = TokenManager(config_manager, self.logger)
        self.tool_optimizer = ToolOptimizer(
            config_manager, self.logger, self.token_manager
        )
        self.message_validator = MessageValidator(config_manager, self.logger)
        self.tool_handler = ToolHandler(config_manager, mcp_client, self.logger)
        # Pass display manager to tool handler for clearing displays
        self.tool_handler.set_progress_display_manager(display_manager)

        # Initialize response timing tracking
        self._response_start_time: Optional[float] = None

    def _clear_progress_displays(self, context: str = "", force: bool = False) -> bool:
        """Centralized method to clear all progress displays and terminal line.

        Args:
            context: Context description for debug logging
            force: Force clearing even if not needed

        Returns:
            True if displays were actually cleared, False otherwise
        """
        if not self.display_manager:
            return False

        try:
            self.display_manager.clear_all_progress()
            return True
        except Exception as e:
            self.logger.debug(f"Error clearing displays {context}: {e}")
            return False

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        stream: bool = True,
        tools: Optional[List[Dict[str, Any]]] = None,
        silent: bool = False,
    ) -> str:
        """Send chat completion request to LLM.

        Args:
            messages: List of message dictionaries
            stream: Whether to stream the response
            tools: Optional list of tools for the LLM
            silent: If True, collect response without printing during streaming

        Returns:
            Complete response text
        """
        # If tools are provided and MCP client is available, use conversation flow
        if tools and self.mcp_client:
            return self._chat_completion_with_tools(messages, tools, stream, silent)
        else:
            return self._basic_chat_completion(messages, stream, tools, silent)

    def _basic_chat_completion(
        self,
        messages: List[Dict[str, str]],
        stream: bool = True,
        tools: Optional[List[Dict[str, Any]]] = None,
        silent: bool = False,
    ) -> str:
        """Basic chat completion without tool execution.

        Args:
            messages: List of message dictionaries
            stream: Whether to stream the response
            tools: Optional list of tools for the LLM
            silent: If True, collect response without printing during streaming

        Returns:
            Complete response text
        """
        # Validate and fix message role alternation for API compatibility
        messages = self.message_validator.validate_and_fix_role_alternation(messages)

        # Log the final message sequence for debugging
        role_sequence = [msg.get("role", "unknown") for msg in messages]
        self.logger.debug(f"Basic completion message role sequence: {role_sequence}")

        # Prepare request parameters
        request_params = {
            "model": self.config.get("model", "local-model"),
            "messages": messages,
            "stream": stream,
        }

        # Add tools if provided
        if tools:
            request_params["tools"] = tools
            # Some models expect tool_choice to be set
            request_params["tool_choice"] = "auto"

        # Show API request progress with spinner for non-streaming requests
        api_progress = None
        if not stream and self.display_manager and not silent:
            try:
                api_progress = self.display_manager.create_progress(
                    token="api_request",
                    title="Waiting for AI response",
                    total=None,  # Indeterminate progress (spinner)
                    show_immediately=True,
                )
            except Exception as e:
                self.logger.debug(f"Could not create API progress indicator: {e}")

        try:
            if stream:
                # Handle streaming response
                response_stream = self.openai_client.chat.completions.create(
                    **request_params
                )
                return self._handle_streaming_response(response_stream, silent)
            else:
                # Handle non-streaming response
                response = self.openai_client.chat.completions.create(**request_params)

                # Complete API progress for non-streaming requests
                if api_progress:
                    try:
                        api_progress.complete("Response received")
                    except Exception as e:
                        self.logger.debug(f"Error completing API progress: {e}")

                content: str = response.choices[0].message.content or ""
                # Filter thinking content from non-streaming responses too
                return self._filter_thinking_content(content)

        except Exception as e:
            # Complete API progress on error
            if api_progress:
                try:
                    api_progress.complete("Request failed")
                except Exception as progress_error:
                    self.logger.debug(
                        f"Error completing API progress on failure: {progress_error}"
                    )

            self.logger.error(f"LLM request failed: {e}")
            raise LLMError(f"Error communicating with LLM: {e}")

    def _handle_streaming_response(
        self, response_stream: Any, silent: bool = False
    ) -> str:
        """Handle streaming response from OpenAI client.

        Args:
            response_stream: Stream from OpenAI client
            silent: If True, collect response without printing during streaming

        Returns:
            Complete response text
        """
        content_parts = []
        content_buffer = ""

        # Thinking detection state - maintain state across chunks
        thinking_active = False
        thinking_progress = None

        # Clear progress displays before streaming starts
        if not silent:
            self._clear_progress_displays("for streaming")

        try:
            for chunk in response_stream:
                if (
                    chunk.choices
                    and chunk.choices[0].delta
                    and chunk.choices[0].delta.content
                ):
                    content = chunk.choices[0].delta.content
                    content_parts.append(content)
                    content_buffer += content

                    if not silent:
                        # Process the accumulated buffer for thinking tags with state
                        output_text, remaining_buffer, thinking_active = (
                            self._process_thinking_content_stateful(
                                content_buffer, thinking_active
                            )
                        )

                        # Update progress indicator state
                        if (
                            thinking_active
                            and thinking_progress is None
                            and self.display_manager
                        ):
                            try:
                                thinking_progress = (
                                    self.display_manager.create_progress(
                                        token="thinking",
                                        title="AI is thinking...",
                                        total=None,  # Indeterminate progress
                                        show_immediately=True,
                                    )
                                )
                            except Exception as e:
                                self.logger.debug(
                                    f"Could not create thinking progress: {e}"
                                )
                        elif not thinking_active and thinking_progress:
                            try:
                                thinking_progress.complete("")
                                thinking_progress = None
                            except Exception as e:
                                self.logger.debug(
                                    f"Error completing thinking progress: {e}"
                                )

                        # Output any new content using display manager
                        if output_text:
                            if (
                                hasattr(self, "display_manager")
                                and self.display_manager
                            ):
                                self.display_manager.stream_content(output_text)
                            # No fallback needed - display manager always present

                        # Update buffer
                        content_buffer = remaining_buffer

            # Clean up thinking progress if still active
            if thinking_progress:
                try:
                    thinking_progress.complete("")
                except Exception as e:
                    self.logger.debug(
                        f"Error completing thinking progress on cleanup: {e}"
                    )

            # Handle any remaining content in buffer
            if content_buffer and not silent:
                # Filter any remaining thinking content and use display manager
                filtered_remaining = self._filter_thinking_content(content_buffer)
                if filtered_remaining:
                    if hasattr(self, "display_manager") and self.display_manager:
                        self.display_manager.stream_content(filtered_remaining)
                    # No fallback needed - display manager should always be present

            # Add newline after streaming completes
            if not silent and content_parts:
                if hasattr(self, "display_manager") and self.display_manager:
                    self.display_manager.end_streaming()
                # No fallback needed - display manager should always be present

        except Exception as e:
            # Clean up thinking progress on error
            if thinking_progress:
                try:
                    thinking_progress.complete("Thinking interrupted")
                except Exception as progress_error:
                    self.logger.debug(
                        f"Error completing thinking progress on error: {progress_error}"
                    )

            self.logger.error(f"Error during streaming: {e}")
            raise LLMError(f"Streaming error: {e}")

        # Filter out thinking content from final response
        final_response = "".join(content_parts)
        return self._filter_thinking_content(final_response)

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
        # and saves tokens. However, we can enhance with categories and tags.
        system_prompt = self._enhance_system_prompt_with_tool_info(
            base_system_prompt, tools
        )

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
        silent: bool = False,
    ) -> str:
        """Handle chat completion with tool execution capability.

        Args:
            messages: List of message dictionaries
            tools: List of available tools
            stream: Whether to stream the response
            silent: If True, collect response without printing during streaming

        Returns:
            Complete response text including tool results
        """
        conversation_messages = messages.copy()
        max_iterations = self.config.get(
            "tool_management.max_tool_iterations", 5
        )  # Get from config with fallback
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
                response_text, tool_calls = self._handle_streaming_with_tools(
                    conversation_messages, current_tools, silent
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
                    # Note: Don't clear displays - thinking cleared already
                    self.tool_handler.process_tool_calls(
                        tool_calls,
                        conversation_messages,
                        tools,
                        iteration,
                        max_context_size,
                        self.progress_callback_factory,
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
                    # Note: Don't clear displays - thinking cleared already
                    self.tool_handler.process_tool_calls(
                        tool_calls,
                        conversation_messages,
                        tools,
                        iteration,
                        max_context_size,
                        self.progress_callback_factory,
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

        # Prepare request parameters
        request_params = {
            "model": self.config.get("model", "local-model"),
            "stream": stream,
            "messages": messages,
        }

        # Add tools to payload according to OpenAI API and MCP specifications
        if tools:
            request_params["tools"] = tools
            request_params["tool_choice"] = "auto"
            # Debug: Log the tools being sent to the model
            self.logger.debug(
                f"Sending {len(tools)} tools to model "
                f"{self.config.get('model', 'local-model')}"
            )
            for i, tool in enumerate(tools[:3]):  # Log first 3 tools
                self.logger.debug(f"Tool {i}: {json.dumps(tool, indent=2)}")

        # Final token count verification for debugging
        model = self.config.get("model", "gpt-3.5-turbo")
        # Create a mock payload for token counting
        # (since OpenAI client handles the actual payload)
        mock_payload = {
            "model": request_params["model"],
            "stream": request_params["stream"],
            "messages": request_params["messages"],
        }
        if tools:
            mock_payload["tools"] = tools
            mock_payload["tool_choice"] = "auto"

        final_tokens = self.token_manager.count_tokens_for_payload(mock_payload, model)
        self.logger.debug(f"Final payload tokens: {final_tokens}")

        # Debug: Log the complete request structure (without full content for brevity)
        debug_request = {
            "model": request_params["model"],
            "stream": request_params["stream"],
            "messages": f"{len(request_params['messages'])} messages",
            "tools": (
                f"{len(request_params.get('tools', []))} tools" if tools else "no tools"
            ),
            "tool_choice": request_params.get("tool_choice", "not set"),
        }
        self.logger.debug(
            "Complete request structure: " f"{json.dumps(debug_request, indent=2)}"
        )

        try:
            response = self.openai_client.chat.completions.create(**request_params)

            self.logger.debug("LLM response received successfully")

            if stream:
                # For streaming, we'd need different handling
                # For now, return None to indicate streaming not supported in
                # this context
                return None
            else:
                # Convert OpenAI response to dict format for compatibility
                content = response.choices[0].message.content
                filtered_content = (
                    self._filter_thinking_content(content) if content else content
                )

                response_data = {
                    "choices": [
                        {
                            "message": {
                                "content": filtered_content,
                                "role": response.choices[0].message.role,
                                "tool_calls": (
                                    [
                                        {
                                            "id": tc.id,
                                            "type": tc.type,
                                            "function": {
                                                "name": tc.function.name,
                                                "arguments": tc.function.arguments,
                                            },
                                        }
                                        for tc in response.choices[0].message.tool_calls
                                    ]
                                    if response.choices[0].message.tool_calls
                                    else None
                                ),
                            }
                        }
                    ]
                }
                self.logger.debug(
                    f"LLM response data: {json.dumps(response_data, indent=2)[:500]}..."
                )
                return response_data

        except Exception as e:
            self.logger.error(f"LLM request failed: {e}")
            return None

    def _enhance_system_prompt_with_tool_info(
        self, base_prompt: str, tools: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Enhance system prompt with dynamically generated tool categories and tags.

        Args:
            base_prompt: Base system prompt
            tools: Available tools to analyze

        Returns:
            Enhanced system prompt with tool information
        """
        if not tools:
            return base_prompt

        try:
            # Extract categories and tags from available tools
            categories = set()
            tags = set()

            for tool in tools:
                function = tool.get("function", {})

                # Try to extract category from tool metadata if available
                if "category" in function:
                    categories.add(function["category"])

                # Try to extract tags from tool metadata if available
                if "tags" in function:
                    tool_tags = function["tags"]
                    if isinstance(tool_tags, list):
                        tags.update(tool_tags)
                    elif isinstance(tool_tags, str):
                        tags.add(tool_tags)

                # Infer categories and tags from tool names and descriptions
                name = function.get("name", "").lower()
                description = function.get("description", "").lower()

                # Infer categories from names
                if any(
                    keyword in name
                    for keyword in ["execute", "command", "run", "shell"]
                ):
                    categories.add("system")
                elif any(
                    keyword in name
                    for keyword in ["file", "read", "write", "find", "search"]
                ):
                    categories.add("filesystem")
                elif any(
                    keyword in name for keyword in ["web", "http", "search", "download"]
                ):
                    categories.add("network")
                elif any(
                    keyword in name for keyword in ["git", "build", "test", "deploy"]
                ):
                    categories.add("development")
                elif any(keyword in name for keyword in ["tool", "describe", "list"]):
                    categories.add("introspection")

                # Infer tags from names and descriptions
                common_tags = [
                    "file",
                    "command",
                    "search",
                    "web",
                    "git",
                    "build",
                    "test",
                    "read",
                    "write",
                    "execute",
                    "download",
                    "upload",
                    "process",
                    "analyze",
                    "convert",
                    "format",
                    "backup",
                    "security",
                ]

                for tag in common_tags:
                    if tag in name or tag in description:
                        tags.add(tag)

            # Format the enhanced prompt
            if categories or tags:
                tool_info = "\n\nAvailable tool capabilities:"

                if categories:
                    sorted_categories = sorted(categories)
                    tool_info += f"\nCategories: {', '.join(sorted_categories)}"

                if tags:
                    # Limit tags to most relevant ones to avoid bloating prompt
                    sorted_tags = sorted(tags)[:15]  # Limit to 15 most common tags
                    tool_info += f"\nCommon operations: {', '.join(sorted_tags)}"

                tool_info += (
                    "\n\nUse search_tools to find specific tools for tasks, "
                    "or describe_tool for detailed information about any tool."
                )

                return base_prompt + tool_info

        except Exception as e:
            self.logger.debug(f"Error enhancing system prompt with tool info: {e}")

        return base_prompt

    def _handle_streaming_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        silent: bool = False,
    ) -> tuple[str, Optional[List[Dict[str, Any]]]]:
        """Handle streaming response with tool calls using OpenAI client.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tools
            silent: If True, collect response without printing during streaming

        Returns:
            Tuple of (response_text, tool_calls)
        """
        # Validate and fix message role alternation for API compatibility
        messages = self.message_validator.validate_and_fix_role_alternation(messages)

        # Prepare request parameters
        request_params = {
            "model": self.config.get("model", "local-model"),
            "messages": messages,
            "stream": True,
        }

        # Add tools if provided
        if tools:
            request_params["tools"] = tools
            request_params["tool_choice"] = "auto"

        # Record start time for adaptive timing
        self._record_response_start()

        # Show API request progress with smart timing-based progress
        api_progress = None  # Clear progress displays before streaming starts
        if self.display_manager and not silent:
            try:
                # Get timing configuration for smart progress
                timing_config = self.config.get("tool_management.response_timing", {})
                avg_time = timing_config.get("average_response_time", 10.0)

                # Use the average time as the total for the progress bar
                # This gives users a sense of expected completion time
                api_progress = self.display_manager.create_progress(
                    token="api_request",
                    title="Waiting for AI response",
                    total=int(
                        avg_time * 10
                    ),  # Convert to deciseconds for smoother progress
                    show_immediately=True,
                )

                # Start a background task to update progress based on time
                self._start_smart_progress_update(api_progress, timing_config)

            except Exception as e:
                self.logger.debug(f"Error setting up progress displays: {e}")

        content_parts = []
        tool_calls = []
        current_tool_calls: Dict[int, Dict[str, Any]] = (
            {}
        )  # Track multiple tool calls by index
        content_buffer = ""

        # Thinking detection state - maintain state across chunks
        thinking_active = False
        thinking_progress = None
        first_content = True

        try:
            response_stream = self.openai_client.chat.completions.create(
                **request_params
            )

            for chunk in response_stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Handle content
                if delta.content:
                    content_parts.append(delta.content)
                    content_buffer += delta.content

                    if not silent:
                        # Complete API progress when content starts arriving
                        if first_content and api_progress:
                            try:
                                api_progress.complete("")
                                # Record response completion for adaptive timing
                                self._record_response_complete()

                                # Clear displays for clean streaming output
                                self._clear_progress_displays(
                                    "for clean streaming output"
                                )
                            except Exception as e:
                                self.logger.debug(f"Error completing API progress: {e}")
                            first_content = False

                        # Process the accumulated buffer for thinking tags with state
                        output_text, remaining_buffer, thinking_active = (
                            self._process_thinking_content_stateful(
                                content_buffer, thinking_active
                            )
                        )

                        # Update progress indicator state
                        if (
                            thinking_active
                            and thinking_progress is None
                            and self.display_manager
                        ):
                            try:
                                thinking_progress = (
                                    self.display_manager.create_progress(
                                        token="thinking",
                                        title="AI is thinking...",
                                        total=None,  # Indeterminate progress
                                        show_immediately=True,
                                    )
                                )
                            except Exception as e:
                                self.logger.debug(
                                    f"Could not create thinking progress: {e}"
                                )
                        elif not thinking_active and thinking_progress:
                            try:
                                thinking_progress.complete("")
                                thinking_progress = None
                            except Exception as e:
                                self.logger.debug(
                                    f"Error completing thinking progress: {e}"
                                )

                        # Output any new content using display manager
                        if output_text:
                            if (
                                hasattr(self, "display_manager")
                                and self.display_manager
                            ):
                                self.display_manager.stream_content(output_text)
                            # No fallback needed - display manager always present

                        # Update buffer
                        content_buffer = remaining_buffer

                # Handle tool calls
                if delta.tool_calls:
                    for tool_call_delta in delta.tool_calls:
                        # Get the index for this tool call
                        index = (
                            tool_call_delta.index
                            if tool_call_delta.index is not None
                            else 0
                        )

                        # Initialize tool call if it doesn't exist
                        if index not in current_tool_calls:
                            current_tool_calls[index] = {
                                "id": tool_call_delta.id or "",
                                "type": tool_call_delta.type or "function",
                                "function": {
                                    "name": "",
                                    "arguments": "",
                                },
                            }

                        # Update the tool call with new data
                        tool_call = current_tool_calls[index]

                        # Update ID if provided
                        if tool_call_delta.id:
                            tool_call["id"] = tool_call_delta.id

                        # Update type if provided
                        if tool_call_delta.type:
                            tool_call["type"] = tool_call_delta.type

                        # Update function data if provided
                        if tool_call_delta.function:
                            if tool_call_delta.function.name:
                                tool_call["function"][
                                    "name"
                                ] += tool_call_delta.function.name
                            if tool_call_delta.function.arguments:
                                tool_call["function"][
                                    "arguments"
                                ] += tool_call_delta.function.arguments

            # Save all completed tool calls
            for index, tool_call in current_tool_calls.items():
                tool_calls.append(tool_call)

            # Clean up any remaining progress indicators
            if api_progress:
                try:
                    api_progress.complete("Request completed")
                except Exception as e:
                    self.logger.debug(f"Error completing API progress on cleanup: {e}")

            if thinking_progress:
                try:
                    # Don't show completion message for thinking progress
                    # since tool output will replace it
                    thinking_progress.complete("")
                except Exception as e:
                    self.logger.debug(
                        f"Error completing thinking progress on cleanup: {e}"
                    )

            # Record response completion if not already recorded
            if self._response_start_time is not None:
                self._record_response_complete()

            # Handle any remaining content in buffer
            if content_buffer and not silent:
                # Filter any remaining thinking content and use display manager
                filtered_remaining = self._filter_thinking_content(content_buffer)
                if filtered_remaining:
                    if hasattr(self, "display_manager") and self.display_manager:
                        self.display_manager.stream_content(filtered_remaining)
                    # No fallback needed - display manager should always be present

            # Add newline after streaming completes, but only if no tool calls follow
            if not silent and content_parts and not tool_calls:
                if hasattr(self, "display_manager") and self.display_manager:
                    self.display_manager.end_streaming()
                # No fallback needed - display manager should always be present

        except Exception as e:
            # Clean up progress indicators on error
            if api_progress:
                try:
                    api_progress.complete("Request failed")
                except Exception as progress_error:
                    self.logger.debug(
                        f"Error completing API progress on error: {progress_error}"
                    )

            if thinking_progress:
                try:
                    thinking_progress.complete("Thinking interrupted")
                except Exception as progress_error:
                    self.logger.debug(
                        f"Error completing thinking progress on error: {progress_error}"
                    )

            self.logger.error(f"Error during streaming with tools: {e}")
            raise LLMError(f"Streaming error: {e}")

        # Filter thinking content from the final response
        response_text = "".join(content_parts)
        filtered_response = self._filter_thinking_content(response_text)
        return filtered_response, tool_calls if tool_calls else None

    def _process_thinking_content(
        self, content_buffer: str, printed_content: str, thinking_progress: Any
    ) -> tuple[str, str, bool]:
        """Process content buffer for thinking tags and return output text.

        Args:
            content_buffer: Accumulated content buffer
            printed_content: Content already printed
            thinking_progress: Current thinking progress indicator

        Returns:
            Tuple of (output_text, remaining_buffer, thinking_active)
        """
        output_text = ""
        remaining_buffer = content_buffer
        thinking_active = False

        # Simple state machine approach
        while True:
            thinking_start = remaining_buffer.find("<thinking>")
            thinking_end = remaining_buffer.find("</thinking>")

            if thinking_start == -1 and thinking_end == -1:
                # No thinking tags
                # Be careful about partial tags at the end
                if remaining_buffer.endswith("<thin") or remaining_buffer.endswith(
                    "</think"
                ):
                    # Keep partial tag in buffer
                    if len(remaining_buffer) > 10:
                        output_text += remaining_buffer[:-10]
                        remaining_buffer = remaining_buffer[-10:]
                    break
                else:
                    output_text += remaining_buffer
                    remaining_buffer = ""
                    break

            elif thinking_start != -1 and (
                thinking_end == -1 or thinking_end < thinking_start
            ):
                # We have <thinking> but no matching </thinking>
                output_text += remaining_buffer[:thinking_start]
                remaining_buffer = ""
                thinking_active = True
                break

            elif thinking_end != -1 and thinking_start == -1:
                # We have </thinking> but no <thinking> (continuing from previous chunk)
                # Skip everything up to and including </thinking>
                remaining_buffer = remaining_buffer[thinking_end + len("</thinking>") :]
                thinking_active = False
                # Continue processing remaining buffer

            elif (
                thinking_start != -1
                and thinking_end != -1
                and thinking_end > thinking_start
            ):
                # We have a complete thinking block
                output_text += remaining_buffer[:thinking_start]
                remaining_buffer = remaining_buffer[thinking_end + len("</thinking>") :]
                thinking_active = False
                # Continue processing remaining buffer

            else:
                # Shouldn't happen, but break to avoid infinite loop
                break

        return output_text, remaining_buffer, thinking_active

    def _process_thinking_content_stateful(
        self, content_buffer: str, in_thinking_mode: bool
    ) -> tuple[str, str, bool]:
        """Process content buffer for thinking tags with state tracking.

        This method is designed to handle character-by-character streaming properly.
        It never outputs thinking content and handles partial tags correctly.

        Args:
            content_buffer: Accumulated content buffer
            in_thinking_mode: Whether we are currently inside a thinking block

        Returns:
            Tuple of (output_text, remaining_buffer, new_thinking_state)
        """
        output_text = ""
        remaining_buffer = content_buffer

        while True:
            if in_thinking_mode:
                # We're in thinking mode, look for the end tag
                thinking_end = remaining_buffer.find("</thinking>")
                if thinking_end != -1:
                    # Found end of thinking - keep content after tag for processing
                    remaining_buffer = remaining_buffer[
                        thinking_end + len("</thinking>") :
                    ]
                    in_thinking_mode = False
                    # Continue processing remaining buffer for more content
                    continue
                else:
                    # Still in thinking mode, keep accumulating but don't output
                    # Keep buffer to detect </thinking> when complete
                    break
            else:
                # Not in thinking mode, look for start tag
                thinking_start = remaining_buffer.find("<thinking>")
                if thinking_start != -1:
                    # Found start of thinking - output content before the tag only
                    output_text += remaining_buffer[:thinking_start]
                    # Switch to thinking mode and consume from start tag onwards
                    remaining_buffer = remaining_buffer[
                        thinking_start + len("<thinking>") :
                    ]
                    in_thinking_mode = True
                    # Continue processing to handle any remaining content
                    continue
                else:
                    # No complete thinking start tag found
                    # Check for potential partial start tags at the end
                    # Be conservative - hold any potential start of thinking tag
                    partial_matches = []
                    thinking_tag = "<thinking>"

                    # Check for all possible partial matches at the end
                    for i in range(1, len(thinking_tag)):
                        partial_tag = thinking_tag[:i]
                        if remaining_buffer.endswith(partial_tag):
                            partial_matches.append((i, partial_tag))

                    if partial_matches:
                        # Found a partial match - keep the longest one in buffer
                        longest_match = max(partial_matches, key=lambda x: x[0])
                        partial_len = longest_match[0]

                        # Output everything except the partial tag
                        if len(remaining_buffer) > partial_len:
                            output_text += remaining_buffer[:-partial_len]
                            remaining_buffer = remaining_buffer[-partial_len:]
                        # If buffer only contains the partial tag, keep it all
                    else:
                        # No partial start tags, safe to output everything
                        output_text += remaining_buffer
                        remaining_buffer = ""

                    break

        return output_text, remaining_buffer, in_thinking_mode

    def _filter_thinking_content(self, content: str) -> str:
        """Filter out thinking content from the response.

        Args:
            content: The raw content that may contain thinking tags

        Returns:
            Content with thinking sections removed
        """
        # Remove thinking content using regex to handle multiline thinking blocks
        # This regex will match <thinking>...</thinking> including newlines
        filtered = re.sub(r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL)

        # Clean up any extra whitespace that might be left
        filtered = re.sub(
            r"\n\s*\n\s*\n", "\n\n", filtered
        )  # Reduce multiple blank lines
        filtered = filtered.strip()

        return filtered

    # Delegation methods for backward compatibility with tests
    def _validate_and_fix_role_alternation(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Delegate to message validator for backward compatibility."""
        return self.message_validator.validate_and_fix_role_alternation(messages)

    def _start_smart_progress_update(
        self, progress: Any, timing_config: Dict[str, Any]
    ) -> None:
        """Start a background timer to update progress based on expected timing.

        Args:
            progress: Progress indicator to update
            timing_config: Timing configuration with intervals and limits
        """

        def update_progress() -> None:
            """Update progress in the background until completion or timeout."""
            try:
                update_interval = timing_config.get("progress_update_interval", 0.1)
                max_time = timing_config.get("max_progress_time", 30.0)
                avg_time = timing_config.get("average_response_time", 10.0)

                # Convert to deciseconds to match the total from create_progress
                total_steps = int(avg_time * 10)
                steps_per_update = max(1, int(update_interval * 10))
                max_updates = int(max_time / update_interval)

                current_step = 0
                updates = 0

                while current_step < total_steps and updates < max_updates:
                    time.sleep(update_interval)
                    current_step += steps_per_update
                    updates += 1

                    # Check if progress is still active (not completed or cancelled)
                    if hasattr(progress, "_completed") and progress._completed:
                        break

                    try:
                        # Update progress with current step, capped at total
                        progress.update(min(current_step, total_steps))
                    except Exception as e:
                        self.logger.debug(f"Error updating progress: {e}")
                        break

            except Exception as e:
                self.logger.debug(f"Error in smart progress update thread: {e}")

        # Start the update thread
        try:
            thread = threading.Thread(target=update_progress, daemon=True)
            thread.start()
        except Exception as e:
            self.logger.debug(f"Could not start progress update thread: {e}")

    def _record_response_start(self) -> None:
        """Record the start time of an API response for timing tracking."""
        self._response_start_time = time.time()

    def _record_response_complete(self) -> None:
        """Record the completion time and update adaptive timing."""
        if (
            hasattr(self, "_response_start_time")
            and self._response_start_time is not None
        ):
            response_time = time.time() - self._response_start_time

            # Update the adaptive timing in config
            try:
                self.config.update_response_timing(response_time)
            except Exception as e:
                self.logger.debug(f"Error updating response timing: {e}")

            self._response_start_time = None
