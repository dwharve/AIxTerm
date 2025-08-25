"""Runtime path utilities for AIxTerm.

This module centralizes logic for determining the project root and the
runtime directory structure used by the unified socket-based service.

Layout (relative to discovered project root):

  .aixterm/
    config        JSON configuration file
    server.sock   Unix domain socket for client<->service IPC
    start.lock    Transient lock file used during auto-start to avoid races

Runtime directory policy (updated):
    The runtime directory is now fixed at the user's home directory:
            ~/.aixterm
    This reverts a prior project-local experiment to comply with the rule that
    the `.aixterm` directory should reside in the user's home. Project root
    discovery helpers are retained only if future features need contextual
    information, but they are no longer used for runtime artifact placement.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

PROJECT_MARKERS = {".git", "pyproject.toml"}  # retained for potential future use
RUNTIME_DIR_NAME = ".aixterm"  # now always in user HOME
CONFIG_FILENAME = "config"
SOCKET_FILENAME = "server.sock"
START_LOCK_FILENAME = "start.lock"


def _has_marker(path: Path) -> bool:
    """Return True if the directory contains any project marker."""
    for marker in PROJECT_MARKERS:
        if (path / marker).exists():
            return True
    return False


def get_project_root(start: Optional[Path] = None) -> Path:
    """Discover the project root.

    Args:
        start: Optional starting path (defaults to cwd)

    Returns:
        Path to discovered project root or starting directory fallback.
    """
    current = (start or Path.cwd()).resolve()
    if current.is_file():  # If invoked with a file path
        current = current.parent

    last = None
    while current != last:
        if _has_marker(current):
            return current
        last = current
        current = current.parent
    # Fallback to original start/cwd
    return (start or Path.cwd()).resolve()


def get_runtime_dir(start: Optional[Path] = None) -> Path:
    """Return the runtime directory path (not created).

    Ignoring 'start' for runtime placement; directory is always at $HOME/.aixterm
    per updated requirements.
    """
    return Path.home() / RUNTIME_DIR_NAME


def get_config_file(start: Optional[Path] = None) -> Path:
    """Return path to the config file (not created)."""
    return get_runtime_dir() / CONFIG_FILENAME


def get_socket_path(start: Optional[Path] = None) -> Path:
    """Return the Unix socket path inside runtime dir."""
    return get_runtime_dir() / SOCKET_FILENAME


def get_start_lock_path(start: Optional[Path] = None) -> Path:
    """Return the transient start lock file path."""
    return get_runtime_dir() / START_LOCK_FILENAME


def ensure_runtime_layout(start: Optional[Path] = None) -> Path:
    """Ensure the runtime directory exists with secure permissions (HOME).

    The 'start' parameter is ignored for current semantics.

    Returns:
        Path to runtime directory.
    """
    runtime_dir = get_runtime_dir()
    try:
        runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Tighten permissions if directory already existed with broader perms
        try:
            os.chmod(runtime_dir, 0o700)
        except OSError:
            pass  # Non-fatal
    except OSError:
        # Let caller handle directory creation failures later
        pass
    return runtime_dir


__all__ = [
    "get_project_root",
    "get_runtime_dir",
    "get_config_file",
    "get_socket_path",
    "get_start_lock_path",
    "ensure_runtime_layout",
]
