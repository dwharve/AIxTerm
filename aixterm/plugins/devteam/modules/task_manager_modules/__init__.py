"""
Task management package for the DevTeam plugin.

This package provides task creation, tracking, and management split into
cohesive modules for better maintainability.
"""

# Export the main public API to preserve compatibility
from .models import Task
from .manager import TaskManager

__all__ = [
    "Task",
    "TaskManager",
]