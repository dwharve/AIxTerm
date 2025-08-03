"""Shell integration modules for terminal logging and context capture."""

from typing import Dict, Optional, Type

from .base import BaseIntegration
from .bash import Bash
from .fish import Fish
from .zsh import Zsh

__all__ = [
    "BaseIntegration",
    "Bash",
    "Fish",
    "Zsh",
    "get_shell_integration_manager",
]

# Shell integration mapping
_SHELL_INTEGRATIONS: Dict[str, Type[BaseIntegration]] = {
    "bash": Bash,
    "fish": Fish,
    "zsh": Zsh,
}


def get_shell_integration_manager(shell_name: str) -> Optional[BaseIntegration]:
    """Get shell integration manager for the given shell name.

    Args:
        shell_name: Name of the shell

    Returns:
        Shell integration manager or None if not supported
    """
    # Handle common shell executable patterns
    shell_name = shell_name.lower()
    if "/" in shell_name or "\\" in shell_name:
        # Extract basename from path
        import os

        shell_name = os.path.basename(shell_name)

    # Remove file extension if present
    if "." in shell_name:
        shell_name = shell_name.split(".")[0]

    # Try to match shell
    integration_class = _SHELL_INTEGRATIONS.get(shell_name)
    if integration_class:
        # Shell integration classes don't accept logger parameter
        return integration_class()
