"""Terminal control functionality for the display system."""

import sys
import time
from typing import Any

from ..utils import get_logger


class TerminalController:
    """Handles terminal control operations."""

    def __init__(self, parent_manager: Any):  # Use Any to avoid circular imports
        """Initialize terminal controller.

        Args:
            parent_manager: The DisplayManager instance that owns this controller
        """
        self.logger = get_logger(__name__)
        self._parent = parent_manager
        self._last_clear_time = 0.0

    def clear_terminal_line(self) -> None:
        """Clear the current terminal line."""
        current_time = time.time()
        if current_time - self._last_clear_time > 0.1:  # Rate limit
            sys.stderr.write("\r\033[2K")  # Clear entire line
            sys.stderr.flush()
            self._last_clear_time = current_time
