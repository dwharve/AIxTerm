"""TTY utilities for log file handling."""

import os
import sys
from pathlib import Path
from typing import List, Optional


def get_current_tty() -> Optional[str]:
    """Get the current TTY name for log file matching.

    Returns:
        TTY name string or None if not available
    """
    try:
        # Try multiple methods to get TTY
        tty_path = None

        # Method 1: From stdin
        if hasattr(os, "ttyname") and hasattr(sys.stdin, "fileno"):
            try:
                tty_path = os.ttyname(sys.stdin.fileno())
            except (OSError, AttributeError):
                pass

        # Method 2: From stdout if stdin failed
        if not tty_path and hasattr(os, "ttyname") and hasattr(sys.stdout, "fileno"):
            try:
                tty_path = os.ttyname(sys.stdout.fileno())
            except (OSError, AttributeError):
                pass

        # Method 3: From stderr if others failed
        if not tty_path and hasattr(os, "ttyname") and hasattr(sys.stderr, "fileno"):
            try:
                tty_path = os.ttyname(sys.stderr.fileno())
            except (OSError, AttributeError):
                pass

        # Method 4: Use 'tty' command as fallback
        if not tty_path:
            try:
                import subprocess as sp

                result = sp.run(["tty"], capture_output=True, text=True, timeout=1)
                if result.returncode == 0:
                    tty_path = result.stdout.strip()
            except (
                sp.SubprocessError,
                FileNotFoundError,
                ImportError,
            ):
                pass

        # If we got a path, extract the TTY name
        if tty_path and tty_path != "not a tty":
            tty_name = Path(tty_path).name
            return tty_name
        return None
    except Exception:
        return None


def get_active_ttys() -> List[str]:
    """Get list of currently active TTY sessions.

    Returns:
        List of active TTY names
    """
    active_ttys = []
    try:
        import subprocess

        # Use 'who' command to get active TTYs
        result = subprocess.run(["who"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        tty_name = parts[1]
                        # Normalize TTY name (remove /dev/ prefix, replace / with -)
                        normalized_tty = tty_name.replace("/dev/", "").replace("/", "-")
                        active_ttys.append(normalized_tty)
    except Exception:
        pass

    return active_ttys


def extract_tty_from_log_path(log_path: Path) -> Optional[str]:
    """Extract TTY name from log file path.

    Args:
        log_path: Path to log file

    Returns:
        TTY name or None if not a TTY-based log
    """
    filename = log_path.name
    if filename.startswith(".aixterm_log."):
        tty_name = filename[13:]  # Remove ".aixterm_log." prefix
        return tty_name
    return None
