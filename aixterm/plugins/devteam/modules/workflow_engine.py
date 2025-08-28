"""
Workflow engine for the DevTeam plugin - Facade for backward compatibility.

This module has been modularized for better maintainability.
The implementation is now split into cohesive modules under the workflow_engine/ package.
"""

# Re-export everything from the modular implementation to preserve API compatibility
from .workflow_engine_modules import (
    Workflow,
    WorkflowEngine,
    WorkflowStep,
    WorkflowStepType,
    TaskStep,
    ConditionStep,
)

# Also re-export the enums from types that tests expect
from .types import WorkflowStatus, WorkflowStepStatus

# For absolute backward compatibility, expose all the classes at the module level
__all__ = [
    "Workflow",
    "WorkflowEngine", 
    "WorkflowStep",
    "WorkflowStepType", 
    "WorkflowStatus",
    "WorkflowStepStatus",
    "TaskStep",
    "ConditionStep",
]
