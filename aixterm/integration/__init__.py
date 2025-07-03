"""Shell integration modules for terminal logging and context capture."""

from .base import BaseIntegration
from .bash import Bash
from .fish import Fish
from .zsh import Zsh

__all__ = [
    "BaseIntegration",
    "Bash",
    "Fish",
    "Zsh",
]
