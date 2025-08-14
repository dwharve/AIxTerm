"""Streaming response handling for LLM client."""

import time
from typing import Any, Dict, List, Optional, Tuple

from ..exceptions import LLMError
from .progress import ProgressManager
from .thinking import ThinkingProcessor


class StreamingHandler:
    """Handles streaming responses from LLM API."""

    def __init__(
        self,
        logger: Any,
        config_manager: Any,
        thinking_processor: ThinkingProcessor,
        progress_manager: ProgressManager,
        openai_client: Any,
        display_manager: Optional[Any] = None,
    ):
        """Initialize streaming handler.

        Args:
            logger: Logger instance
            config_manager: Configuration manager
            thinking_processor: Thinking content processor
            progress_manager: Progress tracking manager
            display_manager: Optional display manager for UI updates
        """
        self.logger = logger
        self.config = config_manager
        self.thinking_processor = thinking_processor
        self.progress_manager = progress_manager
        self.openai_client = openai_client
        self.display_manager = display_manager

    def handle_streaming_response(
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
        if not silent and self.display_manager:
            self.progress_manager.clear_all_progress()

        try:
            for chunk in response_stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                if delta.content:
                    content_parts.append(delta.content)
                    content_buffer += delta.content

                    if not silent:
                        # Process the accumulated buffer for thinking tags with state
                        output_text, remaining_buffer, thinking_active = (
                            self.thinking_processor.process_thinking_content_stateful(
                                content_buffer, thinking_active
                            )
                        )

                        # Update progress indicator state
                        if (
                            thinking_active
                            and thinking_progress is None
                            and self.display_manager
                        ):
                            thinking_progress = (
                                self.progress_manager.create_thinking_progress()
                            )
                        elif not thinking_active and thinking_progress:
                            self.progress_manager.complete_progress(
                                thinking_progress, ""
                            )
                            thinking_progress = None

                        # Output any new content using display manager
                        if output_text:
                            if self.display_manager:
                                self.display_manager.stream_content(output_text)

                        # Update buffer
                        content_buffer = remaining_buffer

            # Clean up thinking progress if still active
            if thinking_progress:
                self.progress_manager.complete_progress(thinking_progress, "")

            # Handle any remaining content in buffer
            if content_buffer and not silent:
                filtered_buffer = self.thinking_processor.filter_thinking_content(
                    content_buffer
                )
                if filtered_buffer and self.display_manager:
                    self.display_manager.stream_content(filtered_buffer)

            # Add newline after streaming completes
            if not silent and content_parts and self.display_manager:
                self.display_manager.end_streaming()

        except Exception as e:
            # Clean up thinking progress on error
            if thinking_progress:
                self.progress_manager.complete_progress(
                    thinking_progress, "Thinking interrupted"
                )

            self.logger.error(f"Error during streaming: {e}")
            raise LLMError(f"Streaming error: {e}")

        # Filter out thinking content from final response
        final_response = "".join(content_parts)
        return self.thinking_processor.filter_thinking_content(final_response)

    def handle_streaming_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        silent: bool = False,
    ) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
        """Handle streaming response with tool calls using OpenAI client.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tools
            silent: If True, collect response without printing during streaming

        Returns:
            Tuple of (response_text, tool_calls)
        """
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
        start_time = time.time()

        # Show API request progress with smart timing-based progress
        api_progress = self.progress_manager.create_api_progress(silent)

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
                                self.progress_manager.complete_progress(
                                    api_progress, ""
                                )
                                api_progress = None
                            except Exception as e:
                                self.logger.debug(f"Error completing API progress: {e}")
                            first_content = False

                        # Process the accumulated buffer for thinking tags with state
                        output_text, remaining_buffer, thinking_active = (
                            self.thinking_processor.process_thinking_content_stateful(
                                content_buffer, thinking_active
                            )
                        )

                        # Update progress indicator state
                        if (
                            thinking_active
                            and thinking_progress is None
                            and self.display_manager
                        ):
                            thinking_progress = (
                                self.progress_manager.create_thinking_progress()
                            )
                        elif not thinking_active and thinking_progress:
                            self.progress_manager.complete_progress(
                                thinking_progress, ""
                            )
                            thinking_progress = None

                        # Output any new content using display manager
                        if output_text and self.display_manager:
                            self.display_manager.stream_content(output_text)

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
                self.progress_manager.complete_progress(
                    api_progress, "Request completed"
                )

            if thinking_progress:
                self.progress_manager.complete_progress(thinking_progress, "")

            # Calculate response time for logging
            response_time = time.time() - start_time
            self.logger.debug(f"Response time: {response_time:.2f}s")

            # Update adaptive timing in config if available
            try:
                self.config.update_response_timing(response_time)
            except Exception as e:
                self.logger.debug(f"Error updating response timing: {e}")

            # Handle any remaining content in buffer
            if content_buffer and not silent:
                # Filter any remaining thinking content and use display manager
                filtered_remaining = self.thinking_processor.filter_thinking_content(
                    content_buffer
                )
                if filtered_remaining and self.display_manager:
                    self.display_manager.stream_content(filtered_remaining)

            # Add newline after streaming completes, but only if no tool calls follow
            if not silent and content_parts and not tool_calls and self.display_manager:
                self.display_manager.end_streaming()

        except Exception as e:
            # Clean up progress indicators on error
            if api_progress:
                self.progress_manager.complete_progress(api_progress, "Request failed")

            if thinking_progress:
                self.progress_manager.complete_progress(
                    thinking_progress, "Thinking interrupted"
                )

            self.logger.error(f"Error during streaming with tools: {e}")
            raise LLMError(f"Streaming error: {e}")

        # Filter thinking content from the final response
        response_text = "".join(content_parts)
        filtered_response = self.thinking_processor.filter_thinking_content(
            response_text
        )
        return filtered_response, tool_calls if tool_calls else None
