"""Unified display system for AIxTerm.

This module provides a single object-oriented solution for all display operations
including progress bars, streaming content, status messages, and terminal control.
"""

import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Dict, Optional, Union

from tqdm import tqdm

from .utils import get_logger


class DisplayType(Enum):
    """Types of display output."""

    SIMPLE = "simple"  # Simple text updates
    PROGRESS_BAR = "bar"  # Progress bar with percentage
    SPINNER = "spinner"  # Spinning indicator
    DETAILED = "detailed"  # Detailed with estimates


class MessageType(Enum):
    """Types of status messages."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"
    TOOL_CALL = "tool_call"


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
        self.default_display_type = default_display_type
        self.logger = get_logger(__name__)

        # Progress management
        self._active_progress: Dict[Union[str, int], "_ProgressDisplay"] = {}
        self._progress_lock = threading.Lock()
        self._shutdown = False
        self._position_counter = 0

        # Content streaming state
        self._streaming_active = False
        self._thinking_active = False
        self._thinking_progress: Optional["_ProgressDisplay"] = None

        # Background thread executor for safe updates
        self._update_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="display-update"
        )

        # Terminal control
        self._last_clear_time = 0.0

    # ===== PROGRESS DISPLAY METHODS =====

    def create_progress(
        self,
        token: Union[str, int],
        title: str = "Processing",
        total: Optional[int] = None,
        display_type: Optional[DisplayType] = None,
        show_immediately: bool = True,
        clear_others: bool = True,
    ) -> "_ProgressDisplay":
        """Create a new progress display.

        Args:
            token: Unique identifier for this progress
            title: Display title
            total: Total expected progress (None for indeterminate)
            display_type: Type of display (defaults to instance default)
            show_immediately: Whether to show immediately
            clear_others: Whether to clear other progress displays first

        Returns:
            Progress display interface
        """
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

    # ===== CONTENT STREAMING METHODS =====

    def start_streaming(self, clear_progress: bool = True) -> None:
        """Start streaming content output.

        Args:
            clear_progress: Whether to clear progress displays first
        """
        if clear_progress:
            self.clear_all_progress()
            self._clear_terminal_line()
        self._streaming_active = True

    def stream_content(self, content: str, filter_thinking: bool = True) -> str:
        """Stream content to output, handling thinking tags if needed.

        Args:
            content: Content to stream
            filter_thinking: Whether to filter thinking content

        Returns:
            Content that was actually output (thinking content filtered)
        """
        if not content:
            return ""

        if filter_thinking:
            return self._process_thinking_content(content)
        else:
            print(content, end="", flush=True)
            return content

    def end_streaming(self, add_newline: bool = True) -> None:
        """End streaming content output.

        Args:
            add_newline: Whether to add a final newline
        """
        if self._streaming_active and add_newline:
            print()  # Add newline after streaming
        self._streaming_active = False

        # Clean up thinking progress if active
        if self._thinking_progress:
            try:
                self._thinking_progress.complete("Thinking complete")
            except Exception as e:
                self.logger.debug(f"Error completing thinking progress: {e}")
            finally:
                self._thinking_progress = None
        self._thinking_active = False

    def _process_thinking_content(self, content: str) -> str:
        """Process content for thinking tags and handle display appropriately.

        Args:
            content: Raw content that may contain thinking tags

        Returns:
            Content that was actually output (thinking filtered)
        """
        output_text = ""
        remaining_content = content

        while remaining_content:
            if not self._thinking_active:
                # Look for thinking start
                thinking_start = remaining_content.find("<thinking>")
                if thinking_start == -1:
                    # No thinking content, output everything
                    output_text += remaining_content
                    print(remaining_content, end="", flush=True)
                    break
                else:
                    # Output content before thinking
                    before_thinking = remaining_content[:thinking_start]
                    if before_thinking:
                        output_text += before_thinking
                        print(before_thinking, end="", flush=True)

                    # Start thinking mode
                    self._thinking_active = True
                    self._start_thinking_progress()
                    remaining_content = remaining_content[
                        thinking_start + 10 :
                    ]  # Skip "<thinking>"
            else:
                # In thinking mode, look for end
                thinking_end = remaining_content.find("</thinking>")
                if thinking_end == -1:
                    # No end tag yet, consume all remaining content silently
                    break
                else:
                    # End thinking mode
                    self._thinking_active = False
                    self._end_thinking_progress()
                    remaining_content = remaining_content[
                        thinking_end + 11 :
                    ]  # Skip "</thinking>"

        return output_text

    def filter_thinking_content(self, content: str) -> str:
        """Filter out thinking content from text (for non-streaming use).

        Args:
            content: Content that may contain thinking tags

        Returns:
            Content with thinking sections removed
        """
        # Remove thinking content using regex
        filtered = re.sub(r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL)

        # Clean up extra whitespace
        filtered = re.sub(r"\n\s*\n\s*\n", "\n\n", filtered)
        return filtered.strip()

    def _start_thinking_progress(self) -> None:
        """Start thinking progress indicator."""
        if not self._thinking_progress:
            try:
                self._thinking_progress = self.create_progress(
                    token="thinking",
                    title="AI is thinking",
                    total=None,
                    display_type=DisplayType.SPINNER,
                    show_immediately=True,
                    clear_others=False,
                )
            except Exception as e:
                self.logger.debug(f"Error starting thinking progress: {e}")

    def _end_thinking_progress(self) -> None:
        """End thinking progress indicator."""
        if self._thinking_progress:
            try:
                self.complete_progress("thinking", "")
            except Exception as e:
                self.logger.debug(f"Error ending thinking progress: {e}")
            finally:
                self._thinking_progress = None

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
        # Only clear progress if there are active displays and clearing is requested
        if clear_progress and self._active_progress:
            self.clear_all_progress()

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

    # ===== TERMINAL CONTROL METHODS =====

    def clear_terminal_line(self) -> None:
        """Clear the current terminal line."""
        self._clear_terminal_line()

    def _clear_terminal_line(self) -> None:
        """Internal method to clear terminal line with rate limiting."""
        current_time = time.time()
        if current_time - self._last_clear_time > 0.1:  # Rate limit
            sys.stderr.write("\r\033[2K")  # Clear entire line
            sys.stderr.flush()
            self._last_clear_time = current_time

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


class _ProgressDisplay:
    """Individual progress display implementation."""

    def __init__(
        self,
        token: Union[str, int],
        title: str,
        total: Optional[int],
        display_type: DisplayType,
        position: int,
        manager: DisplayManager,
    ):
        """Initialize progress display.

        Args:
            token: Progress token
            title: Progress title
            total: Total expected progress
            display_type: Type of display
            position: Position for concurrent displays
            manager: Parent display manager
        """
        self.token = token
        self.title = title
        self.total = total
        self.display_type = display_type
        self.position = position
        self.manager = manager

        self.current_progress = 0
        self.message = ""
        self.is_visible = False
        self.is_completed = False
        self._last_update = 0.0

        # tqdm instance
        self._tqdm: Optional[tqdm] = None
        self._tqdm_lock = threading.Lock()

        self.logger = get_logger(__name__)

    def show(self) -> None:
        """Show the progress display."""
        if not self.is_visible and not self.is_completed:
            self.is_visible = True
            self._create_tqdm()

    def update(
        self, progress: int, message: Optional[str] = None, total: Optional[int] = None
    ) -> None:
        """Update the progress display."""
        if self.is_completed:
            return

        # Rate limiting
        current_time = time.time()
        time_diff = current_time - self._last_update
        progress_diff = abs(progress - self.current_progress)

        if time_diff >= 0.1 and time_diff > 0.001 and progress_diff < 5:
            return
        self._last_update = current_time

        # Update total if provided
        if total is not None and total != self.total:
            old_total = self.total
            self.total = total
            with self._tqdm_lock:
                if self._tqdm:
                    try:
                        if old_total is None and total is not None:
                            # Recreate for indeterminate to determinate
                            old_desc = self._tqdm.desc
                            old_n = self._tqdm.n
                            self._tqdm.close()
                            self._create_tqdm()
                            if self._tqdm:
                                self._tqdm.n = old_n
                                self._tqdm.set_description(old_desc)
                                self._tqdm.refresh()
                        else:
                            self._tqdm.total = total
                            self._tqdm.refresh()
                    except Exception as e:
                        self.logger.debug(f"Error updating tqdm total: {e}")
                        # Fallback: recreate tqdm
                        try:
                            old_desc = self._tqdm.desc if self._tqdm else self.title
                            old_n = self._tqdm.n if self._tqdm else 0
                            if self._tqdm:
                                self._tqdm.close()
                            self._create_tqdm()
                            if self._tqdm:
                                self._tqdm.n = old_n
                                self._tqdm.set_description(old_desc)
                                self._tqdm.refresh()
                        except Exception as e2:
                            self.logger.debug(f"Failed to recreate tqdm: {e2}")

        # Update message
        if message is not None:
            self.message = message

        # Update progress value
        self.current_progress = progress

        # Update tqdm display
        with self._tqdm_lock:
            if self._tqdm is not None:
                try:
                    self._tqdm.n = progress

                    if self.message:
                        self._tqdm.set_description(f"{self.title} - {self.message}")
                    else:
                        self._tqdm.set_description(self.title)

                    self._tqdm.refresh()
                except Exception as e:
                    self.logger.debug(f"Error updating tqdm: {e}")

    def complete(self, final_message: Optional[str] = None) -> None:
        """Complete the progress display."""
        if self.is_completed:
            return

        self.is_completed = True

        if final_message is not None:
            self.message = final_message

        with self._tqdm_lock:
            if self._tqdm is not None:
                try:
                    # Always clear progress bars cleanly without leaving any output
                    self._tqdm.clear()
                    self._tqdm.close()
                    
                    # Clear any remaining line artifacts
                    sys.stderr.write("\r\033[K")
                    sys.stderr.flush()

                except Exception as e:
                    self.logger.debug(f"Error completing tqdm: {e}")
                finally:
                    self._tqdm = None

    def _create_tqdm(self) -> None:
        """Create the tqdm instance based on display type."""
        try:
            tqdm_kwargs = {
                "desc": self.title,
                "leave": False,
                "unit": "items",
                "file": sys.stderr,
                "disable": False,
                "dynamic_ncols": True,
                "ascii": False,
                "mininterval": 0.1,
                "maxinterval": 1.0,
                "smoothing": 0.1,
                "position": None,
                "ncols": 70,
                "colour": None,
            }

            # Handle total
            if self.total is not None and self.total > 0:
                tqdm_kwargs["total"] = self.total

            # Configure based on display type
            if self.display_type == DisplayType.SIMPLE:
                tqdm_kwargs.update(
                    {
                        "bar_format": "{desc}: {n} items",
                        "ncols": 60,
                    }
                )
            elif self.display_type == DisplayType.PROGRESS_BAR:
                if self.total:
                    tqdm_kwargs.update(
                        {
                            "bar_format": "{desc}: {percentage:3.0f}%|{bar}| "
                            "{n}/{total} [{elapsed}<{remaining}]",
                            "ncols": 80,
                        }
                    )
                else:
                    tqdm_kwargs.update(
                        {
                            "bar_format": "{desc} [{elapsed}]",
                            "ncols": 60,
                        }
                    )
            elif self.display_type == DisplayType.SPINNER:
                tqdm_kwargs.update(
                    {
                        "bar_format": "{desc}: {n} items [{elapsed}]",
                        "ncols": 60,
                    }
                )
            elif self.display_type == DisplayType.DETAILED:
                if self.total:
                    tqdm_kwargs.update(
                        {
                            "bar_format": "{desc}: {percentage:3.0f}%|{bar}| "
                            "{n}/{total} [{elapsed}<{remaining}, {rate_fmt}]",
                            "ncols": 100,
                            "unit_scale": True,
                        }
                    )
                else:
                    tqdm_kwargs.update(
                        {
                            "bar_format": "{desc}: {n} items [{elapsed}, {rate_fmt}]",
                            "ncols": 80,
                            "unit_scale": True,
                        }
                    )

            with self._tqdm_lock:
                self._tqdm = tqdm(**tqdm_kwargs)

                if self.message:
                    self._tqdm.set_description(f"{self.title} - {self.message}")

        except Exception as e:
            self.logger.debug(f"Error creating tqdm: {e}")
            self._tqdm = None


class _MockProgress(_ProgressDisplay):
    """Mock progress display for when system is shutting down."""

    def __init__(self) -> None:
        self.is_visible = False
        self.is_completed = False

    def show(self) -> None:
        pass

    def update(
        self, progress: int, message: Optional[str] = None, total: Optional[int] = None
    ) -> None:
        pass

    def complete(self, final_message: Optional[str] = None) -> None:
        pass


# ===== FACTORY FUNCTIONS =====


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
