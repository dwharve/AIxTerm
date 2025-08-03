"""Terminal context and log file management module."""

from .log_processor.parsing import (
    extract_commands_from_log,
    extract_conversation_from_log,
)
from .log_processor.processor import LogProcessor
from .log_processor.summary import build_tiered_summary
from .log_processor.tokenization import read_and_truncate_log, truncate_text_to_tokens
from .log_processor.tty_utils import get_active_ttys, get_current_tty
from .terminal_context import TerminalContext
from .token_manager import TokenManager
from .tool_optimizer import ToolOptimizer

__all__ = [
    "TerminalContext",
    "TokenManager",
    "ToolOptimizer",
    "LogProcessor",
    "extract_commands_from_log",
    "extract_conversation_from_log",
    "build_tiered_summary",
    "truncate_text_to_tokens",
    "read_and_truncate_log",
    "get_current_tty",
    "get_active_ttys",
]
