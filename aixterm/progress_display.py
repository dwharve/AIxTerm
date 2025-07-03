"""Progress display utilities using tqdm for robust terminal progress bars."""

import threading
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
    """Manages progress display using tqdm for robust terminal handling."""

    def __init__(
        self, display_type: ProgressDisplayType = ProgressDisplayType.PROGRESS_BAR
    ):
        """Initialize progress display.

        Args:
            display_type: Type of progress display to use
        """
        self.display_type = display_type
        self.logger = get_logger(__name__)
        self._active_displays: Dict[Union[str, int], "TqdmProgress"] = {}
        self._lock = threading.RLock()
        self._position_counter = 0  # For positioning multiple progress bars

    def create_progress(
        self,
        progress_token: Union[str, int],
        title: str = "Processing",
        total: Optional[int] = None,
        show_immediately: bool = True,
    ) -> "TqdmProgress":
        """Create a new progress display.

        Args:
            progress_token: Unique identifier for this progress
            title: Title/description to display
            total: Total expected progress (if known)
            show_immediately: Whether to show progress immediately

        Returns:
            TqdmProgress instance for updates
        """
        with self._lock:
            # Assign position for concurrent displays
            position = self._position_counter
            self._position_counter += 1

            progress = TqdmProgress(
                token=progress_token,
                title=title,
                total=total,
                display_type=self.display_type,
                position=position,
                parent=self,
            )

            self._active_displays[progress_token] = progress

            if show_immediately:
                progress.show()

            return progress

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
        with self._lock:
            if progress_token in self._active_displays:
                self._active_displays[progress_token].update(progress, message, total)

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
                self._active_displays[progress_token].complete(final_message)
                del self._active_displays[progress_token]

    def cleanup_all(self) -> None:
        """Clean up all active progress displays."""
        with self._lock:
            for progress in list(self._active_displays.values()):
                progress.complete("Cancelled")
            self._active_displays.clear()
            self._position_counter = 0


class TqdmProgress:
    """An active progress display using tqdm."""

    def __init__(
        self,
        token: Union[str, int],
        title: str,
        total: Optional[int],
        display_type: ProgressDisplayType,
        position: int,
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
        self.token = token
        self.title = title
        self.total = total
        self.display_type = display_type
        self.position = position
        self.parent = parent

        self.current_progress = 0
        self.message = ""
        self.is_visible = False
        self.is_completed = False

        # tqdm instance
        self._tqdm: Optional[tqdm] = None

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

        # Update total if provided
        if total is not None and total != self.total:
            self.total = total
            if self._tqdm:
                self._tqdm.total = total
                self._tqdm.refresh()

        # Update message
        if message is not None:
            self.message = message

        # Update progress
        if self._tqdm is not None:
            try:
                # Calculate the increment
                increment = progress - self.current_progress
                if increment > 0:
                    self._tqdm.update(increment)

                # Update description with message
                if self.message:
                    self._tqdm.set_description(f"{self.title} - {self.message}")
                else:
                    self._tqdm.set_description(self.title)
            except Exception as e:
                # Handle any tqdm errors gracefully
                self.logger.debug(f"Error updating tqdm progress: {e}")

        self.current_progress = progress

    def complete(self, final_message: Optional[str] = None) -> None:
        """Complete the progress display.

        Args:
            final_message: Optional final message
        """
        if self.is_completed:
            return

        self.is_completed = True

        if final_message:
            self.message = final_message

        if self._tqdm is not None:
            try:
                # Complete the progress bar
                if self.total:
                    remaining = self.total - self.current_progress
                    if remaining > 0:
                        self._tqdm.update(remaining)

                # Set final description
                if final_message:
                    self._tqdm.set_description(f"{self.title} - {final_message}")

                # Close the tqdm instance
                self._tqdm.close()
            except Exception as e:
                # Handle any tqdm errors gracefully
                self.logger.debug(f"Error closing tqdm progress: {e}")
            finally:
                self._tqdm = None

    def _create_tqdm(self) -> None:
        """Create the tqdm instance based on display type."""
        try:
            # Configure tqdm parameters based on display type
            tqdm_kwargs = {
                "desc": self.title,
                "position": self.position,
                "leave": True,  # Keep progress bar after completion
                "unit": "items",
            }

            # Handle total - use False for indeterminate progress to avoid tqdm
            # bool issues
            if self.total is not None:
                tqdm_kwargs["total"] = self.total
            else:
                # Use False instead of None for indeterminate progress
                tqdm_kwargs["total"] = False

            if self.display_type == ProgressDisplayType.SIMPLE:
                tqdm_kwargs.update(
                    {
                        "bar_format": "{desc}: {n}/{total} ({percentage:3.0f}%) "
                        "{postfix}",
                        "ncols": 80,
                    }
                )
            elif self.display_type == ProgressDisplayType.PROGRESS_BAR:
                tqdm_kwargs.update(
                    {
                        "bar_format": "{desc}: {percentage:3.0f}%|{bar}| {n}/{total} "
                        "[{elapsed}<{remaining}] {postfix}",
                        "ncols": 100,
                    }
                )
            elif self.display_type == ProgressDisplayType.SPINNER:
                # Use a progress bar but with custom format that looks like a spinner
                tqdm_kwargs.update(
                    {
                        "bar_format": "{desc}: {n} items [{elapsed}] {postfix}",
                        "ncols": 80,
                    }
                )
            elif self.display_type == ProgressDisplayType.DETAILED:
                tqdm_kwargs.update(
                    {
                        "bar_format": "{desc}: {percentage:3.0f}%|{bar}| {n}/{total} "
                        "[{elapsed}<{remaining}, {rate_fmt}] {postfix}",
                        "ncols": 120,
                        "unit_scale": True,
                    }
                )

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
