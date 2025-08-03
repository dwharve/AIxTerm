"""Utility functions and helpers for AIxTerm."""

import logging
import os
import sys
from pathlib import Path
from typing import Optional


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically __name__)
        level: Logging level override

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        # Create handler
        handler = logging.StreamHandler(sys.stderr)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(handler)

    # Set level - check environment variable as fallback
    if level:
        logger.setLevel(getattr(logging, level.upper(), logging.WARNING))
    elif not logger.level or logger.level == logging.NOTSET:
        # Only set default if no level is already set
        log_level = os.environ.get("AIXTERM_LOG_LEVEL", "WARNING")
        logger.setLevel(getattr(logging, log_level.upper(), logging.WARNING))

    return logger


def get_current_shell() -> str:
    """Detect the current shell from environment variables.

    Returns:
        Shell name (bash, zsh, fish) or 'bash' as fallback
    """
    # Try SHELL environment variable first
    shell_path = os.environ.get("SHELL", "")
    if shell_path:
        shell_name = Path(shell_path).name
        if shell_name in ["bash", "zsh", "fish"]:
            return shell_name

    # Try 0 argument (current process name)
    try:
        import psutil

        current_process = psutil.Process()
        parent = current_process.parent()
        if parent:
            parent_name = parent.name()
            if parent_name in ["bash", "zsh", "fish"]:
                return parent_name
    except (ImportError, Exception):
        pass

    # Fallback to bash
    return "bash"


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted file size string
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i: int = 0
    size_float = float(size_bytes)
    while size_float >= 1024 and i < len(size_names) - 1:
        size_float /= 1024
        i += 1

    return f"{size_float:.1f} {size_names[i]}"
