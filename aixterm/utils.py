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

        # Set level
        log_level = level or os.environ.get("aixterm_LOG_LEVEL", "WARNING")
        if log_level:
            logger.setLevel(getattr(logging, log_level.upper(), logging.WARNING))

    return logger


def is_windows() -> bool:
    """Check if running on Windows.

    Returns:
        True if on Windows, False otherwise
    """
    return os.name == "nt"


def get_home_dir() -> Path:
    """Get user home directory.

    Returns:
        Path to user home directory
    """
    return Path.home()


def safe_filename(filename: str) -> str:
    """Create a safe filename by removing/replacing problematic characters.

    Args:
        filename: Original filename

    Returns:
        Safe filename
    """
    # Replace problematic characters
    safe_chars = []
    for char in filename:
        if char.isalnum() or char in ".-_":
            safe_chars.append(char)
        else:
            safe_chars.append("_")

    return "".join(safe_chars)


def ensure_directory(path: Path) -> None:
    """Ensure directory exists, create if necessary.

    Args:
        path: Directory path to ensure exists
    """
    path.mkdir(parents=True, exist_ok=True)


def get_file_size(path: Path) -> int:
    """Get file size in bytes.

    Args:
        path: Path to file

    Returns:
        File size in bytes, 0 if file doesn't exist
    """
    try:
        return path.stat().st_size
    except (OSError, FileNotFoundError):
        return 0


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate string to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


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
