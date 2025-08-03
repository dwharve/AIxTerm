"""Progress display implementations."""

import sys
import threading
import time
from typing import Any, Optional, Union

from tqdm import tqdm

from ..utils import get_logger
from .types import DisplayType


class _ProgressDisplay:
    """Individual progress display implementation."""

    def __init__(
        self,
        token: Union[str, int],
        title: str,
        total: Optional[int],
        display_type: DisplayType,
        position: int,
        manager: Any,  # Avoid circular imports by using Any
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
                # Provide an empty iterable as the first argument to tqdm
                # Ignore type errors since tqdm's type hints are complex and difficult to match exactly
                self._tqdm = tqdm(iter([]), **tqdm_kwargs)  # type: ignore

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
