"""Utility functions and helpers for AIxTerm."""

import logging
import os
import sys
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
