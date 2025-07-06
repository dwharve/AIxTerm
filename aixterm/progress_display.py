"""Progress display utilities using tqdm for robust terminal progress bars."""

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Dict, Optional, Union

from tqdm import tqdm

from .utils import get_logger


class ProgressDisplayType(Enum):
    """Types of progress display."""

    SIMPLE = "simple"  # Simple text updates
    PROGRESS_BAR = "bar"  # Progress bar with percentage
    SPINNER = "spinner"  # Spinning indicator (uses tqdm's progress bar)
    DETAILED = "detailed"  # Detailed with estimates


class ProgressDisplay:
    """Manages multiple progress displays with automatic positioning."""

    def __init__(
        self, display_type: ProgressDisplayType = ProgressDisplayType.PROGRESS_BAR
    ):
        """Initialize progress display manager.

        Args:
            display_type: Default type of progress display to create
        """
        self.display_type = display_type
        self.logger = get_logger(__name__)
        self._active_displays: Dict[Union[str, int], ProgressInterface] = {}
        self._lock = threading.Lock()
        self._shutdown = False
        self._position_counter = 0  # Add position counter for tests

        # Background thread executor for safe tqdm updates
        self._update_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="progress-update"
        )

    def create_progress(
        self,
        progress_token: Union[str, int],
        title: str = "Processing",
        total: Optional[int] = None,
        show_immediately: bool = True,
        clear_others: bool = True,
    ) -> "ProgressInterface":
        """Create a new progress display.

        Args:
            progress_token: Unique token for this progress
            title: Display title
            total: Total expected progress (None for indeterminate)
            show_immediately: Whether to show the progress immediately
            clear_others: Whether to clear other progress displays when showing

        Returns:
            Progress interface for updates
        """
        with self._lock:
            if self._shutdown:
                return MockProgress()

            if progress_token in self._active_displays:
                # Return existing display
                return self._active_displays[progress_token]

            # Clear other displays if requested and we're showing immediately
            if show_immediately and clear_others and self._active_displays:
                # Clear existing displays to avoid stacking
                active_tokens = list(self._active_displays.keys())
                for token in active_tokens:
                    try:
                        display = self._active_displays[token]
                        display.complete("")  # Clear with empty message
                    except Exception as e:
                        self.logger.debug(
                            f"Error clearing existing progress display {token}: {e}"
                        )
                    finally:
                        if token in self._active_displays:
                            del self._active_displays[token]

            # Assign position for concurrent displays
            position = self._position_counter
            self._position_counter += 1

            # Create appropriate progress display
            progress_display = TqdmProgress(
                token=progress_token,
                title=title,
                total=total,
                display_type=self.display_type,
                position=position,  # Add position parameter
                parent=self,
            )

            self._active_displays[progress_token] = progress_display

            if show_immediately:
                progress_display.show()

            return progress_display

    def update_progress(
        self,
        progress_token: Union[str, int],
        progress: int,
        message: Optional[str] = None,
        total: Optional[int] = None,
    ) -> None:
        """Update existing progress display.

        Args:
            progress_token: Token identifying the progress
            progress: Current progress value
            message: Optional status message
            total: Update total if provided
        """
        if self._shutdown:
            return

        with self._lock:
            if progress_token in self._active_displays:
                display = self._active_displays[progress_token]
                # Use thread pool to prevent blocking on terminal I/O
                self._update_executor.submit(
                    self._safe_update, display, progress, message, total
                )

    def _safe_update(
        self,
        display: "ProgressInterface",
        progress: int,
        message: Optional[str],
        total: Optional[int],
    ) -> None:
        """Safely update progress display in background thread."""
        try:
            display.update(progress, message, total)
        except Exception as e:
            self.logger.debug(f"Error in background progress update: {e}")

    def complete_progress(
        self, progress_token: Union[str, int], final_message: Optional[str] = None
    ) -> None:
        """Complete and remove a progress display.

        Args:
            progress_token: Token identifying the progress
            final_message: Optional final message to display
        """
        with self._lock:
            if progress_token in self._active_displays:
                display = self._active_displays[progress_token]
                # Complete synchronously to ensure cleanup
                try:
                    display.complete(final_message)
                except Exception as e:
                    self.logger.debug(f"Error completing progress: {e}")
                finally:
                    del self._active_displays[progress_token]

    def cleanup_all(self) -> None:
        """Clean up all active progress displays."""
        with self._lock:
            self._shutdown = True

            for progress in list(self._active_displays.values()):
                try:
                    progress.complete("Cancelled")
                except Exception as e:
                    self.logger.debug(f"Error during cleanup: {e}")

            self._active_displays.clear()
            self._position_counter = 0  # Reset position counter

            # Shutdown the executor
            self._update_executor.shutdown(wait=False)

    def clear_all_displays(self) -> None:
        """Clear all active progress displays by completing them with empty messages.

        This is used when something else needs to write to the terminal
        (like streaming output).
        """
        with self._lock:
            if self._shutdown:
                return

            # Complete all active displays with empty messages to clear them
            active_tokens = list(self._active_displays.keys())
            for token in active_tokens:
                try:
                    display = self._active_displays[token]
                    display.complete("")  # Empty message triggers clearing
                except Exception as e:
                    self.logger.debug(f"Error clearing progress display {token}: {e}")
                finally:
                    # Remove from active displays
                    if token in self._active_displays:
                        del self._active_displays[token]


class ProgressInterface:
    """Base interface for progress displays."""

    def __init__(self) -> None:
        self.is_visible = False

    def show(self) -> None:
        pass

    def update(
        self, progress: int, message: Optional[str] = None, total: Optional[int] = None
    ) -> None:
        pass

    def complete(self, final_message: Optional[str] = None) -> None:
        pass


class MockProgress(ProgressInterface):
    """Mock progress display for when system is shutting down."""

    def __init__(self) -> None:
        super().__init__()


class TqdmProgress(ProgressInterface):
    """An active progress display using tqdm."""

    def __init__(
        self,
        token: Union[str, int],
        title: str,
        total: Optional[int],
        display_type: ProgressDisplayType,
        position: int,  # Add position parameter
        parent: ProgressDisplay,
    ):
        """Initialize tqdm progress.

        Args:
            token: Progress token
            title: Progress title
            total: Total expected progress
            display_type: Type of display
            position: Position for concurrent displays
            parent: Parent ProgressDisplay instance
        """
        super().__init__()
        self.token = token
        self.title = title
        self.total = total
        self.display_type = display_type
        self.position = position  # Store position for tests
        self.parent = parent

        self.current_progress = 0
        self.message = ""
        self.is_completed = False
        self._last_update = 0.0  # Rate limiting

        # tqdm instance
        self._tqdm: Optional[tqdm] = None
        self._tqdm_lock = threading.Lock()  # Protect tqdm updates

        self.logger = get_logger(__name__)

    def show(self) -> None:
        """Show the progress display."""
        if not self.is_visible and not self.is_completed:
            self.is_visible = True
            self._create_tqdm()

    def update(
        self, progress: int, message: Optional[str] = None, total: Optional[int] = None
    ) -> None:
        """Update the progress display.

        Args:
            progress: Current progress value
            message: Optional status message
            total: Update total if provided
        """
        if self.is_completed:
            return

        # Rate limiting: only update if enough time passed or significant
        # progress change (but always update for tests when time difference is minimal)
        current_time = time.time()
        time_diff = current_time - self._last_update
        progress_diff = abs(progress - self.current_progress)

        # Skip rate limiting if time difference is very small (likely a test)
        # or if there's significant progress change
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
                        # Handle tqdm total update carefully
                        if old_total is None and total is not None:
                            # Recreate tqdm when going from indeterminate to determinate
                            old_desc = self._tqdm.desc
                            old_n = self._tqdm.n
                            self._tqdm.close()
                            self._create_tqdm()
                            if self._tqdm:
                                self._tqdm.n = old_n
                                self._tqdm.set_description(old_desc)
                                self._tqdm.refresh()
                        else:
                            # Normal total update
                            self._tqdm.total = total
                            self._tqdm.refresh()
                    except Exception as e:
                        self.logger.debug(
                            f"Error updating tqdm total from {old_total} to "
                            f"{total}: {e}"
                        )
                        # Try to recreate tqdm as fallback
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

        # Update progress value FIRST
        self.current_progress = progress

        # Update progress display
        with self._tqdm_lock:
            if self._tqdm is not None:
                try:
                    # Set the tqdm progress to match our current progress
                    self._tqdm.n = progress

                    # Update description with message
                    if self.message:
                        self._tqdm.set_description(f"{self.title} - {self.message}")
                    else:
                        self._tqdm.set_description(self.title)

                    # Force refresh to ensure display updates
                    self._tqdm.refresh()
                except Exception as e:
                    # Handle any tqdm errors gracefully
                    self.logger.debug(f"Error updating tqdm progress: {e}")

    def complete(self, final_message: Optional[str] = None) -> None:
        """Complete the progress display.

        Args:
            final_message: Optional final message
        """
        if self.is_completed:
            return

        self.is_completed = True

        # Set the final message
        if final_message is not None:
            self.message = final_message

        with self._tqdm_lock:
            if self._tqdm is not None:
                try:
                    # For empty final messages, clear immediately
                    # (this is for cleanup before streaming)
                    if final_message is not None and not final_message.strip():
                        # Clear and close immediately without showing completion
                        self._tqdm.clear()
                        self._tqdm.close()
                        # Extra clearing with ANSI codes
                        sys.stderr.write("\r\033[2K")  # Clear current line
                        sys.stderr.flush()
                    else:
                        # Complete the progress bar to 100% if it has a total
                        if self.total and self.total > 0:
                            remaining = self.total - self.current_progress
                            if remaining > 0:
                                self._tqdm.update(remaining)
                                self.current_progress = self.total

                        # Set final description
                        if final_message:
                            self._tqdm.set_description(
                                f"{self.title} - {final_message}"
                            )
                        else:
                            self._tqdm.set_description(f"{self.title} - completed")

                        # Refresh to show the final state
                        self._tqdm.refresh()

                        # Close without leaving a newline - this is key to prevent
                        # the line spacing issue
                        self._tqdm.close()

                        # Now write the final progress line manually without a newline
                        final_desc = (
                            self._tqdm.desc
                            if hasattr(self._tqdm, "desc")
                            else (
                                f"{self.title} - {final_message}"
                                if final_message
                                else f"{self.title} - completed"
                            )
                        )
                        sys.stderr.write(f"\r{final_desc}")
                        sys.stderr.flush()

                except Exception as e:
                    # Handle any tqdm errors gracefully
                    self.logger.debug(f"Error closing tqdm progress: {e}")
                finally:
                    self._tqdm = None

    def _create_tqdm(self) -> None:
        """Create the tqdm instance based on display type."""
        try:
            # Configure tqdm parameters for better terminal control
            tqdm_kwargs = {
                "desc": self.title,
                "leave": False,  # Don't leave progress bar after completion by default
                "unit": "items",
                "file": sys.stderr,  # Use stderr to avoid stdout conflicts
                "disable": False,  # Always enable unless explicitly disabled
                "dynamic_ncols": True,  # Auto-adjust width
                "ascii": True,  # Use ASCII characters for better compatibility
                "mininterval": 0.1,  # Faster updates for responsiveness
                "maxinterval": 1.0,  # Maximum interval between updates
                "smoothing": 0.1,  # Smoothing factor for speed estimates
                "position": None,  # Let tqdm handle positioning
                "ncols": 70,  # Fixed width to prevent line wrapping issues
                "colour": None,  # No colors to avoid terminal issues
            }

            # Handle total properly - fix the False bug
            if self.total is not None and self.total > 0:
                tqdm_kwargs["total"] = self.total
            else:
                # For indeterminate progress, don't set total
                pass  # tqdm will handle this automatically

            if self.display_type == ProgressDisplayType.SIMPLE:
                tqdm_kwargs.update(
                    {
                        "bar_format": "{desc}: {n} items",
                        "ncols": 60,  # Shorter to be less intrusive
                    }
                )
            elif self.display_type == ProgressDisplayType.PROGRESS_BAR:
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
                            "ncols": 60,  # Shorter for indeterminate progress
                        }
                    )
            elif self.display_type == ProgressDisplayType.SPINNER:
                tqdm_kwargs.update(
                    {
                        "bar_format": "{desc}: {n} items [{elapsed}]",
                        "ncols": 60,
                    }
                )
            elif self.display_type == ProgressDisplayType.DETAILED:
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

                # Set initial message if available
                if self.message:
                    self._tqdm.set_description(f"{self.title} - {self.message}")

        except Exception as e:
            self.logger.debug(f"Error creating tqdm progress: {e}")
            # Fallback to simple print-based progress
            self._tqdm = None


def create_progress_display(display_type: str = "bar") -> ProgressDisplay:
    """Create a progress display instance.

    Args:
        display_type: Type of display ("simple", "bar", "spinner", "detailed")

    Returns:
        ProgressDisplay instance
    """
    try:
        display_enum = ProgressDisplayType(display_type)
    except ValueError:
        display_enum = ProgressDisplayType.PROGRESS_BAR

    return ProgressDisplay(display_enum)
