"""
Workflow engine package for the DevTeam plugin.

This package provides workflow creation, execution, and management split into
cohesive modules for better maintainability.
"""

# Export the main public API to preserve compatibility
from .models import Workflow, WorkflowStep, WorkflowStepType
from .executor import WorkflowEngine
from .step_types import TaskStep, ConditionStep

__all__ = [
    "Workflow",
    "WorkflowStep", 
    "WorkflowStepType",
    "WorkflowEngine",
    "TaskStep",
    "ConditionStep",
]
