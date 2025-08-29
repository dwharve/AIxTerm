"""Unified display system for AIxTerm."""

import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Union

from ..utils import get_logger
from .progress import _MockProgress, _ProgressDisplay
from .types import DisplayType, MessageType


class DisplayManager:
    """Unified display manager for all AIxTerm output operations.

    This class consolidates all display functionality including:
    - Progress bars and spinners
    - Streaming content output
    - Status and error messages
    - Terminal control and clearing
    - Content filtering (e.g., thinking tags)
    """

    def __init__(self, default_display_type: DisplayType = DisplayType.PROGRESS_BAR):
        """Initialize the display manager.

        Args:
            default_display_type: Default type for progress displays
        """
        from .content import ContentStreamer
        from .status import StatusDisplay
        from .terminal import TerminalController

        self.default_display_type = default_display_type
        self.logger = get_logger(__name__)

        # Progress management
        self._active_progress: Dict[Union[str, int], "_ProgressDisplay"] = {}
        self._progress_lock = threading.Lock()
        self._shutdown = False
        self._position_counter = 0

        # Component modules
        self.content = ContentStreamer(self)
        self.status = StatusDisplay(self)
        self.terminal = TerminalController(self)

        # Background thread executor for safe updates
        self._update_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="display-update"
        )

        # Terminal control
        self._last_clear_time = 0.0

    # ===== PROGRESS DISPLAY METHODS =====

    def create_progress(
        self,
        token: Union[str, int, None] = None,
        title: str = "Processing",
        total: Optional[int] = None,
        display_type: Optional[DisplayType] = None,
        show_immediately: bool = True,
        clear_others: bool = True,
    ) -> "_ProgressDisplay":
        """Create a new progress display for user feedback.

        Args:
            token: Unique identifier for this progress (defaults to "default" if None)
            title: Display title for the progress indicator
            total: Total number of steps (for percentage display)
            display_type: Type of display to use (spinner, progress bar, etc.)
            show_immediately: Whether to show the progress immediately
            clear_others: Whether to clear other progress displays

        Returns:
            Progress display object for updates and control
        """
        # Handle case where title is provided as first arg and token is missing
        if token is None:
            token = "default"
        with self._progress_lock:
            if self._shutdown:
                return _MockProgress()

            if token in self._active_progress:
                return self._active_progress[token]

            # Clear other displays if requested
            if show_immediately and clear_others and self._active_progress:
                self._clear_all_progress_internal()

            # Create new progress display
            display_type = display_type or self.default_display_type
            position = self._position_counter
            self._position_counter += 1

            progress = _ProgressDisplay(
                token=token,
                title=title,
                total=total,
                display_type=display_type,
                position=position,
                manager=self,
            )

            self._active_progress[token] = progress

            if show_immediately:
                progress.show()

            return progress

    def update_progress(
        self,
        token: Union[str, int],
        progress: int,
        message: Optional[str] = None,
        total: Optional[int] = None,
    ) -> None:
        """Update an existing progress display.

        Args:
            token: Progress identifier
            progress: Current progress value
            message: Optional status message
            total: Update total if provided
        """
        if self._shutdown:
            return

        with self._progress_lock:
            if token in self._active_progress:
                display = self._active_progress[token]
                # Use thread pool to prevent blocking
                self._update_executor.submit(
                    self._safe_progress_update, display, progress, message, total
                )

    def complete_progress(
        self, token: Union[str, int], final_message: Optional[str] = None
    ) -> None:
        """Complete and remove a progress display.

        Args:
            token: Progress identifier
            final_message: Optional final message
        """
        with self._progress_lock:
            if token in self._active_progress:
                display = self._active_progress[token]
                try:
                    display.complete(final_message)
                except Exception as e:
                    self.logger.debug(f"Error completing progress {token}: {e}")
                finally:
                    del self._active_progress[token]

    def clear_all_progress(self) -> None:
        """Clear all active progress displays."""
        with self._progress_lock:
            self._clear_all_progress_internal()

    def _clear_all_progress_internal(self) -> None:
        """Internal method to clear all progress displays."""
        active_tokens = list(self._active_progress.keys())
        for token in active_tokens:
            try:
                display = self._active_progress[token]
                display.complete("")  # Empty message triggers clean clearing
            except Exception as e:
                self.logger.debug(f"Error clearing progress {token}: {e}")
            finally:
                if token in self._active_progress:
                    del self._active_progress[token]

        # Ensure terminal is completely clean after clearing all progress
        if active_tokens:
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()

    def _safe_progress_update(
        self,
        display: "_ProgressDisplay",
        progress: int,
        message: Optional[str],
        total: Optional[int],
    ) -> None:
        """Safely update progress in background thread."""
        try:
            display.update(progress, message, total)
        except Exception as e:
            self.logger.debug(f"Error in progress update: {e}")

    # ===== STATUS DISPLAY METHODS =====

    # ===== CONTENT STREAMING METHODS =====

    def start_streaming(self, clear_progress: bool = True) -> None:
        """Start streaming content output.

        Args:
            clear_progress: Whether to clear progress displays first
        """
        self.content.start_streaming(clear_progress)

    def stream_content(self, content: str, filter_thinking: bool = True) -> str:
        """Stream content to output, handling thinking tags if needed.

        Args:
            content: Content to stream
            filter_thinking: Whether to filter thinking content

        Returns:
            Content that was actually output (thinking content filtered)
        """
        return self.content.stream_content(content, filter_thinking)

    def end_streaming(self, add_newline: bool = True) -> None:
        """End streaming content output.

        Args:
            add_newline: Whether to add a final newline
        """
        self.content.end_streaming(add_newline)

    def filter_thinking_content(self, content: str) -> str:
        """Filter out thinking content from text (for non-streaming use).

        Args:
            content: Content that may contain thinking tags

        Returns:
            Content with thinking sections removed
        """
        return self.content.filter_thinking_content(content)

    # ===== STATUS MESSAGE METHODS =====

    def show_message(
        self,
        message: str,
        msg_type: MessageType = MessageType.INFO,
        clear_progress: bool = True,
    ) -> None:
        """Show a status message.

        Args:
            message: Message to display
            msg_type: Type of message
            clear_progress: Whether to clear progress first
        """
        self.status.show_message(message, msg_type, clear_progress)

    def show_info(self, message: str, clear_progress: bool = True) -> None:
        """Show an information message."""
        self.status.show_info(message, clear_progress)

    def show_error(self, message: str, clear_progress: bool = True) -> None:
        """Show an error message."""
        self.status.show_error(message, clear_progress)

    def show_warning(self, message: str, clear_progress: bool = True) -> None:
        """Show a warning message."""
        self.status.show_warning(message, clear_progress)

    def show_success(self, message: str, clear_progress: bool = True) -> None:
        """Show a success message."""
        self.status.show_success(message, clear_progress)

    def show_tool_call(self, tool_name: str, clear_progress: bool = True) -> None:
        """Show a tool call message."""
        self.status.show_tool_call(tool_name, clear_progress)

    # ===== TERMINAL CONTROL METHODS =====

    def clear_terminal_line(self) -> None:
        """Clear the current terminal line."""
        self.terminal.clear_terminal_line()

    # ===== LIFECYCLE METHODS =====

    def shutdown(self) -> None:
        """Shutdown the display manager and cleanup resources."""
        with self._progress_lock:
            self._shutdown = True

            # Complete all active progress
            for progress in list(self._active_progress.values()):
                try:
                    progress.complete("Cancelled")
                except Exception as e:
                    self.logger.debug(f"Error during shutdown: {e}")

            self._active_progress.clear()
            self._position_counter = 0

            # Shutdown executor gracefully
            try:
                self._update_executor.shutdown(wait=True, cancel_futures=True)
            except Exception as e:
                self.logger.debug(f"Error shutting down executor: {e}")

    def show_response(self, response: Union[Dict, str]) -> None:
        """Display a response from the LLM.

        Args:
            response: Response from LLM (can be dict or string)
        """
        try:
            # Handle string responses
            if isinstance(response, str):
                self.content.show_response(response)
                return

            # Handle dict responses
            if isinstance(response, dict):
                # Show thinking content if available
                if "thinking" in response and response["thinking"]:
                    self.content.show_thinking(response["thinking"])

                # Show main response content
                if "content" in response:
                    self.content.show_response(response["content"])

                # Show elapsed time if available
                if "elapsed_time" in response:
                    elapsed = float(response["elapsed_time"])
                    self.status.show_elapsed_time(elapsed)

                # Log completion
                elapsed_time = response.get("elapsed_time", "N/A")
                self.logger.debug(f"Response displayed (time: {elapsed_time}s)")

        except Exception as e:
            self.logger.error(f"Error displaying response: {e}")
            print(f"Error displaying response: {e}", file=sys.stderr)


def create_display_manager(display_type: str = "bar") -> DisplayManager:
    """Create a display manager instance.

    Args:
        display_type: Default display type ("simple", "bar", "spinner", "detailed")

    Returns:
        DisplayManager instance
    """
    try:
        display_enum = DisplayType(display_type)
    except ValueError:
        display_enum = DisplayType.PROGRESS_BAR

    return DisplayManager(display_enum)
