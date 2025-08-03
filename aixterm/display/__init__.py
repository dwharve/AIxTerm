"""Unified display system for AIxTerm.

This module provides a single object-oriented solution for all display operations
including progress bars, streaming content, status messages, and terminal control.
"""

from .content import ContentStreamer
from .manager import DisplayManager
from .progress import _MockProgress, _ProgressDisplay
from .status import StatusDisplay
from .terminal import TerminalController
from .types import DisplayType, MessageType


# Create factory function for backward compatibility
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


__all__ = [
    "DisplayType",
    "MessageType",
    "DisplayManager",
    "ContentStreamer",
    "StatusDisplay",
    "TerminalController",
    "create_display_manager",
]
