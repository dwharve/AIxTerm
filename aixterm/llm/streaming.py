"""Streaming response handling for LLM requests."""

import json
from typing import Any, Dict, List, Optional, Tuple

import requests


class StreamingHandler:
    """Handles streaming responses from LLM APIs."""

    def __init__(
        self, config_manager: Any, logger: Any, progress_display_manager: Any = None
    ):
        """Initialize streaming handler.

        Args:
            config_manager: Configuration manager instance
            logger: Logger instance
            progress_display_manager: Progress display manager for clearing displays
        """
        self.config = config_manager
        self.logger = logger
        self.progress_display_manager = progress_display_manager
        self._streaming_started = False
        self._response_start_time: Optional[float] = None

    def _clear_progress_displays_for_streaming(self, api_progress: Any = None) -> None:
        """Clear all active progress displays before streaming starts.

        Args:
            api_progress: API progress indicator to complete (if provided)
        """
        if self.progress_display_manager and not self._streaming_started:
            try:
                # Complete API progress if provided
                if api_progress:
                    try:
                        api_progress.complete("Response received")
                    except Exception as e:
                        self.logger.debug(f"Error completing API progress: {e}")

                # Clear all active progress displays using the new method
                self.progress_display_manager.clear_all_displays()

                # Clear the entire line and move to beginning for clean output
                import sys

                sys.stderr.write("\r\033[2K")  # Clear entire line
                sys.stderr.flush()

            except Exception as e:
                self.logger.debug(f"Error clearing progress displays: {e}")

            self._streaming_started = True

    def handle_streaming_response(
        self, response: requests.Response, silent: bool = False
    ) -> str:
        """Handle streaming response from LLM.

        Args:
            response: Streaming response object
            silent: If True, collect response without printing (for progress bar
                coordination)

        Returns:
            Full response text
        """
        full_response = ""
        first_content = True

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
                                function_name = tool_call.get("function", {}).get(
                                    "name", "unknown"
                                )
                                if not silent:
                                    print(f"[Tool Call: {function_name}]")
                                self.handle_tool_call(tool_call)

                        content = delta.get("content", "")
                        if content:
                            # Clear progress displays before first content
                            if first_content and not silent:
                                self._clear_progress_displays_for_streaming()
                                first_content = False

                            if not silent:
                                print(content, end="", flush=True)
                            full_response += content

                    except json.JSONDecodeError:
                        # Some lines might not be JSON
                        continue

        except Exception as e:
            self.logger.error(f"Error processing streaming response: {e}")

        if not silent and full_response:
            print()  # New line after streaming
        return full_response

    def handle_tool_call(self, tool_call: Dict[str, Any]) -> None:
        """Handle tool call from LLM.

        Args:
            tool_call: Tool call information
        """
        # For now, just log tool calls
        # In a full implementation, this would execute the tool
        function_name = tool_call.get("function", {}).get("name", "unknown")
        self.logger.info(f"LLM requested tool call: {function_name}")
        print(f"\n⚡ Executing tool: {function_name}")  # Enhanced display

    def handle_streaming_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        silent: bool = False,
    ) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
        """Handle streaming response that may include tool calls.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tools
            silent: If True, collect response without printing (for progress bar
                coordination)

        Returns:
            Tuple of (response_text, tool_calls)
        """
        # Reset streaming state for this request
        self._streaming_started = False

        # Record start time for adaptive timing
        self._record_response_start()

        # Make streaming request
        headers = {
            "Content-Type": "application/json",
        }

        api_key = self.config.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": self.config.get("model", "local-model"),
            "stream": True,
            "messages": messages,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        # Show API request progress with smart timing-based progress
        api_progress = None
        if self.progress_display_manager and not silent:
            try:
                # Get timing configuration
                timing_config = self.config.get("tool_management.response_timing", {})
                avg_time = timing_config.get("average_response_time", 10.0)

                # Use the average time as the total for the progress bar
                # This gives users a sense of expected completion time
                api_progress = self.progress_display_manager.create_progress(
                    progress_token="api_request",
                    title="Waiting for AI response",
                    total=int(
                        avg_time * 10
                    ),  # Convert to deciseconds for smoother progress
                    show_immediately=True,
                )

                # Start a background task to update progress based on time
                self._start_smart_progress_update(api_progress, timing_config)

            except Exception as e:
                self.logger.debug(f"Could not create API progress indicator: {e}")

        try:
            response = requests.post(
                self.config.get("api_url", "http://localhost/v1/chat/completions"),
                headers=headers,
                json=payload,
                stream=True,
                timeout=30,
            )
            response.raise_for_status()

            # Don't complete API progress here - let the streaming content clear it
            # when the first actual content arrives
            return self.parse_streaming_response_with_tools(
                response, silent, api_progress
            )

        except requests.exceptions.RequestException as e:
            # Complete API progress on error
            if api_progress:
                try:
                    api_progress.complete("Request failed")
                except Exception as progress_error:
                    self.logger.debug(
                        f"Error completing API progress on failure: {progress_error}"
                    )

            self.logger.error(f"Streaming LLM request failed: {e}")
            return "", None

    def parse_streaming_response_with_tools(
        self,
        response: requests.Response,
        silent: bool = False,
        api_progress: Any = None,
    ) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
        """Parse streaming response and extract content and tool calls.

        Args:
            response: Streaming response object
            silent: If True, collect response without printing (for progress bar
                coordination)
            api_progress: API progress indicator to complete when content arrives

        Returns:
            Tuple of (response_text, tool_calls)
        """
        full_response = ""
        tool_calls: List[Dict[str, Any]] = []
        current_tool_calls: Dict[int, Dict[str, Any]] = {}
        first_content = True

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
                        choice = data.get("choices", [{}])[0]
                        delta = choice.get("delta", {})

                        # Handle content
                        content = delta.get("content", "")
                        if content:
                            # Clear progress displays and complete API progress
                            if first_content and not silent:
                                # Complete API progress when content starts arriving
                                if api_progress:
                                    try:
                                        api_progress.complete("AI responding")
                                    except Exception as e:
                                        self.logger.debug(
                                            f"Error completing API progress: {e}"
                                        )

                                # Record response completion for adaptive timing
                                self._record_response_complete()

                                self._clear_progress_displays_for_streaming()
                                first_content = False

                            if not silent:
                                print(content, end="", flush=True)
                            full_response += content

                        # Handle tool calls
                        if "tool_calls" in delta:
                            delta_tool_calls = delta["tool_calls"]
                            for delta_tool_call in delta_tool_calls:
                                index = delta_tool_call.get("index", 0)

                                if index not in current_tool_calls:
                                    current_tool_calls[index] = {
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    }

                                tool_call = current_tool_calls[index]

                                # Update tool call ID
                                if "id" in delta_tool_call:
                                    tool_call["id"] = delta_tool_call["id"]

                                # Update function details
                                if "function" in delta_tool_call:
                                    func = delta_tool_call["function"]
                                    if "name" in func:
                                        tool_call["function"]["name"] += func["name"]
                                    if "arguments" in func:
                                        tool_call["function"]["arguments"] += func[
                                            "arguments"
                                        ]

                    except json.JSONDecodeError:
                        # Some lines might not be JSON
                        continue

        except Exception as e:
            self.logger.error(f"Error parsing streaming response: {e}")

        # Convert tool calls dict to list
        if current_tool_calls:
            tool_calls = list(current_tool_calls.values())
            # Filter out incomplete tool calls
            tool_calls = [
                tc
                for tc in tool_calls
                if tc.get("id") and tc.get("function", {}).get("name")
            ]

        # Only add newline if we actually streamed content and not silent
        if full_response and not silent:
            print()  # New line after streaming

        # Record response completion if not already recorded
        if self._response_start_time is not None:
            self._record_response_complete()

        return full_response, tool_calls if tool_calls else None

    def _start_smart_progress_update(
        self, progress: Any, timing_config: Dict[str, Any]
    ) -> None:
        """Start a background timer to update progress based on expected timing.

        Args:
            progress: Progress indicator to update
            timing_config: Timing configuration with intervals and limits
        """
        import threading
        import time

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
        import time

        self._response_start_time = time.time()

    def _record_response_complete(self) -> None:
        """Record the completion time and update adaptive timing."""
        if self._response_start_time is not None:
            import time

            response_time = time.time() - self._response_start_time

            # Update the adaptive timing in config
            try:
                self.config.update_response_timing(response_time)
            except Exception as e:
                self.logger.debug(f"Error updating response timing: {e}")

            self._response_start_time = None
