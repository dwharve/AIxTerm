"""
Task management system for the DevTeam plugin - Facade for backward compatibility.

This module has been modularized for better maintainability.
The implementation is now split into cohesive modules under the task_manager_modules/ package.
"""

# Re-export everything from the modular implementation to preserve API compatibility
from .task_manager_modules import (
    Task,
    TaskManager,
)

# For absolute backward compatibility, expose all the classes at the module level
__all__ = [
    "Task",
    "TaskManager",
]