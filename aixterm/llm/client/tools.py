"""Tool-based chat completion handling for LLM client."""

from typing import Any, Dict, List, Optional, Tuple

from ..exceptions import LLMError


class ToolCompletionHandler:
    """Handles LLM chat completion with tool execution."""

    def __init__(
        self,
        logger: Any,
        config_manager: Any,
        tool_optimizer: Any,
        tool_handler: Any,
        request_handler: Any,
        streaming_handler: Any,
    ):
        """Initialize tool completion handler.

        Args:
            logger: Logger instance
            config_manager: Configuration manager
            tool_optimizer: Tool context optimization manager
            tool_handler: Tool execution handler
            request_handler: LLM request handler
            streaming_handler: Streaming response handler
        """
        self.logger = logger
        self.config = config_manager
        self.tool_optimizer = tool_optimizer
        self.tool_handler = tool_handler
        self.request_handler = request_handler
        self.streaming_handler = streaming_handler

    def chat_completion_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        stream: bool = True,
        silent: bool = False,
        message_validator: Any = None,
    ) -> str:
        """Handle chat completion with tool execution capability.

        Args:
            messages: List of message dictionaries
            tools: List of available tools
            stream: Whether to stream the response
            silent: If True, collect response without printing during streaming
            message_validator: Message validator for role alternation fixes

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
                response_text, tool_calls = (
                    self.streaming_handler.handle_streaming_with_tools(
                        conversation_messages, current_tools, silent
                    )
                )

                if response_text:
                    final_response = response_text

                # Process tool calls if any
                if tool_calls:
                    self.logger.debug(
                        f"Processing {len(tool_calls)} tool calls from stream"
                    )
                    # Add assistant message with tool calls to conversation
                    conversation_messages.append(
                        {
                            "role": "assistant",
                            "content": response_text,
                            "tool_calls": tool_calls,
                        }
                    )

                    # Process tool calls and continue the conversation
                    self.tool_handler.process_tool_calls(
                        tool_calls,
                        conversation_messages,
                        tools,
                        iteration,
                        max_context_size,
                        clear_displays=False,  # Don't clear - already cleared by streaming
                    )
                    continue
                else:
                    # No tool calls, conversation is complete
                    self.logger.debug(
                        f"No tool calls in iteration {iteration}, ending conversation"
                    )
                    break
            else:
                response_data = self.request_handler.make_llm_request(
                    conversation_messages,
                    current_tools,
                    stream=False,
                    message_validator=message_validator,
                )

                if not response_data:
                    self.logger.error("Empty response from LLM")
                    break

                choices = response_data.get("choices", [])
                if not choices:
                    self.logger.error("No choices in LLM response")
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
