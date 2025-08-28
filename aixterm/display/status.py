"""Status message functionality for the display system."""

from typing import Any

from ..utils import get_logger
from .types import MessageType


class StatusDisplay:
    """Handles status and error messages in the terminal."""

    def __init__(self, parent_manager: Any):  # Use Any to avoid circular imports
        """Initialize status display.

        Args:
            parent_manager: The DisplayManager instance that owns this display
        """
        self.logger = get_logger(__name__)
        self._parent = parent_manager

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
        # Only clear progress if there are active displays and clearing is requested
        if clear_progress and self._parent._active_progress:
            self._parent.clear_all_progress()

        # Format message based on type
        if msg_type == MessageType.ERROR:
            formatted = f"Error: {message}"
        elif msg_type == MessageType.WARNING:
            formatted = f"Warning: {message}"
        elif msg_type == MessageType.SUCCESS:
            formatted = message
        elif msg_type == MessageType.TOOL_CALL:
            formatted = message  # No prefix for tool calls
        else:  # INFO
            formatted = message

        print(formatted)

    def show_info(self, message: str, clear_progress: bool = True) -> None:
        """Show an information message."""
        self.show_message(message, MessageType.INFO, clear_progress)

    def show_error(self, message: str, clear_progress: bool = True) -> None:
        """Show an error message."""
        self.show_message(message, MessageType.ERROR, clear_progress)

    def show_warning(self, message: str, clear_progress: bool = True) -> None:
        """Show a warning message."""
        self.show_message(message, MessageType.WARNING, clear_progress)

    def show_success(self, message: str, clear_progress: bool = True) -> None:
        """Show a success message."""
        self.show_message(message, MessageType.SUCCESS, clear_progress)

    def show_tool_call(self, tool_name: str, clear_progress: bool = True) -> None:
        """Show a tool call message."""
        self.show_message(tool_name, MessageType.TOOL_CALL, clear_progress)

    def show_elapsed_time(self, seconds: float) -> None:
        """Display elapsed time of an operation.

        Args:
            seconds: Time in seconds
        """
        # Suppressed by default to keep CLI output clean.
        # If desired in the future, re-enable via config/env flag.
        try:
            import os
            if os.environ.get("AIXTERM_SHOW_TIMING", "").lower() in ("1", "true", "yes"):  # optional opt-in
                # Format time nicely
                if seconds < 0.1:
                    time_str = f"{seconds * 1000:.0f}ms"
                elif seconds < 1:
                    time_str = f"{seconds * 1000:.1f}ms"
                elif seconds < 60:
                    time_str = f"{seconds:.2f}s"
                else:
                    minutes = int(seconds / 60)
                    remaining_seconds = seconds % 60
                    time_str = f"{minutes}m {remaining_seconds:.1f}s"

                formatted = f"[Completed in {time_str}]"
                print(formatted)
        except Exception:
            # Fail closed (silent) on any unexpected error
            pass
