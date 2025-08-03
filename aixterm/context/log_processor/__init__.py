"""Log processing and conversation history management.

This module provides a fully modular implementation of the log processor,
with specialized components for different aspects of log processing.

The main components are:
- processor.py: Main LogProcessor class
- parsing.py: Log content parsing functions
- tokenization.py: Text truncation and token management
- tty_utils.py: TTY detection and validation
- summary.py: Intelligent summarization
"""

from pathlib import Path

from .parsing import extract_commands_from_log, extract_conversation_from_log
from .processor import LogProcessor
from .summary import build_tiered_summary
from .tokenization import read_and_truncate_log, truncate_text_to_tokens
from .tty_utils import extract_tty_from_log_path, get_active_ttys, get_current_tty

__all__ = [
    "LogProcessor",
    "extract_commands_from_log",
    "extract_conversation_from_log",
    "read_and_truncate_log",
    "truncate_text_to_tokens",
    "get_current_tty",
    "get_active_ttys",
    "extract_tty_from_log_path",
    "build_tiered_summary",
]

# Re-export Path for tests that patch it
Path = Path
