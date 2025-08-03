"""Display types and enumerations."""

from enum import Enum


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
