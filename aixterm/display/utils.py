"""Terminal utilities for the display module."""

import sys


def clear_terminal():
    """Clear the entire terminal."""
    # This uses ANSI escape codes to clear the screen
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def move_cursor(row: int, col: int):
    """Move cursor to a specific position in terminal."""
    # ANSI escape code for cursor positioning
    sys.stdout.write(f"\033[{row};{col}H")
    sys.stdout.flush()


def get_terminal_size() -> tuple:
    """Get terminal size."""
    try:
        import shutil

        return shutil.get_terminal_size()
    except (AttributeError, ImportError):
        # Fallback for environments where shutil.get_terminal_size is not available
        return (80, 24)  # default size
