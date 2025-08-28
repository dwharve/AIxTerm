"""
Data models for workflows and workflow steps.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from ..types import WorkflowId, WorkflowStatus, WorkflowStepStatus


class WorkflowStepType(Enum):
    """Types of workflow steps."""

    TASK = "task"  # Creates and executes a task
    CONDITION = "condition"  # Evaluates a condition to determine flow
    FORK = "fork"  # Splits workflow into parallel branches
    JOIN = "join"  # Joins parallel branches
    SUBPROCESS = "subprocess"  # Executes another workflow as a subprocess
    TRIGGER = "trigger"  # Triggers an event
    WAIT = "wait"  # Waits for a condition or event
    SCRIPT = "script"  # Runs a custom script or function


class WorkflowStep:
    """Base class for workflow steps."""

    def __init__(
        self,
        step_id: str,
        step_type: WorkflowStepType,
        name: str,
        description: str,
        next_steps: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a workflow step.

        Args:
            step_id: Unique ID of the step
            step_type: Type of the step
            name: Name of the step
            description: Description of the step
            next_steps: IDs of the next steps after this one
            metadata: Additional step metadata
        """
        self.step_id = step_id
        self.step_type = step_type
        self.name = name
        self.description = description
        self.next_steps = next_steps or []
        self.metadata = metadata or {}
        self.status = WorkflowStepStatus.PENDING
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.result: Optional[Any] = None
        self.error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the step to a dictionary.

        Returns:
            Dictionary representation of the step.
        """
        return {
            "step_id": self.step_id,
            "step_type": self.step_type.value,
            "name": self.name,
            "description": self.description,
            "next_steps": self.next_steps,
            "metadata": self.metadata,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, step_dict: Dict[str, Any]) -> "WorkflowStep":
        """
        Create a step from a dictionary.

        Args:
            step_dict: Dictionary containing step data

        Returns:
            WorkflowStep object.
        """
        step = cls(
            step_id=step_dict["step_id"],
            step_type=WorkflowStepType(step_dict["step_type"]),
            name=step_dict["name"],
            description=step_dict["description"],
            next_steps=step_dict.get("next_steps", []),
            metadata=step_dict.get("metadata", {}),
        )

        step.status = WorkflowStepStatus(step_dict.get("status", "pending"))
        step.started_at = step_dict.get("started_at")
        step.completed_at = step_dict.get("completed_at")
        step.result = step_dict.get("result")
        step.error = step_dict.get("error")

        return step

    async def execute(
        self, context: Dict[str, Any], workflow: "Workflow"
    ) -> Dict[str, Any]:
        """
        Execute the workflow step.

        Args:
            context: Execution context
            workflow: The workflow being executed

        Returns:
            Updated context after execution.
        """
        self.status = WorkflowStepStatus.IN_PROGRESS
        self.started_at = datetime.now().isoformat()

        try:
            context = await self._execute(context, workflow)
            self.status = WorkflowStepStatus.COMPLETED
            self.completed_at = datetime.now().isoformat()
        except Exception as e:
            self.status = WorkflowStepStatus.FAILED
            self.error = str(e)
            self.completed_at = datetime.now().isoformat()
            raise

        return context

    async def _execute(
        self, context: Dict[str, Any], workflow: "Workflow"
    ) -> Dict[str, Any]:
        """
        Internal execution method to be overridden by subclasses.

        Args:
            context: Execution context
            workflow: The workflow being executed

        Returns:
            Updated context after execution.
        """
        # Base implementation does nothing
        return context


class Workflow:
    """Represents a workflow in the DevTeam plugin."""

    def __init__(
        self,
        name: str,
        description: str,
        steps: Dict[str, WorkflowStep],
        workflow_id: Optional[WorkflowId] = None,
        metadata: Optional[Dict[str, Any]] = None,
        start_step_id: Optional[str] = None,
    ):
        """
        Initialize a workflow.

        Args:
            name: Workflow name
            description: Workflow description
            steps: Dictionary of workflow steps
            workflow_id: Unique workflow ID (auto-generated if not provided)
            metadata: Additional workflow metadata
            start_step_id: ID of the first step (default: first step in steps)
        """
        self.workflow_id = workflow_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.steps = steps
        self.metadata = metadata or {}
        self.status = WorkflowStatus.PENDING
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.current_steps: Set[str] = set()
        self.completed_steps: Set[str] = set()
        self.context: Dict[str, Any] = {}

        # Set the start step ID
        self.start_step_id: Optional[str]
        if start_step_id:
            self.start_step_id = start_step_id
        elif steps:
            self.start_step_id = next(iter(steps.keys()))
        else:
            self.start_step_id = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the workflow to a dictionary.

        Returns:
            Dictionary representation of the workflow.
        """
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "steps": {step_id: step.to_dict() for step_id, step in self.steps.items()},
            "metadata": self.metadata,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "current_steps": list(self.current_steps),
            "completed_steps": list(self.completed_steps),
            "start_step_id": self.start_step_id,
        }

    @classmethod
    def from_dict(cls, workflow_dict: Dict[str, Any]) -> "Workflow":
        """
        Create a workflow from a dictionary.

        Args:
            workflow_dict: Dictionary containing workflow data

        Returns:
            Workflow object.
        """
        # Parse steps - we'll need to import this after step_types.py is created
        steps_dict = workflow_dict.get("steps", {})
        steps: Dict[str, WorkflowStep] = {}

        for step_id, step_data in steps_dict.items():
            step_type = WorkflowStepType(step_data["step_type"])

            if step_type == WorkflowStepType.TASK:
                # Import here to avoid circular imports
                from .step_types import TaskStep
                steps[step_id] = TaskStep.from_dict(step_data)
            elif step_type == WorkflowStepType.CONDITION:
                # Import here to avoid circular imports
                from .step_types import ConditionStep
                steps[step_id] = ConditionStep.from_dict(step_data)
            else:
                # Generic workflow step
                steps[step_id] = WorkflowStep.from_dict(step_data)

        workflow = cls(
            workflow_id=workflow_dict["workflow_id"],
            name=workflow_dict["name"],
            description=workflow_dict["description"],
            steps=steps,
            metadata=workflow_dict.get("metadata", {}),
            start_step_id=workflow_dict.get("start_step_id"),
        )

        workflow.status = WorkflowStatus(workflow_dict.get("status", "pending"))
        workflow.created_at = workflow_dict.get("created_at", datetime.now().isoformat())
        workflow.updated_at = workflow_dict.get("updated_at", workflow.created_at)
        workflow.started_at = workflow_dict.get("started_at")
        workflow.completed_at = workflow_dict.get("completed_at")
        workflow.current_steps = set(workflow_dict.get("current_steps", []))
        workflow.completed_steps = set(workflow_dict.get("completed_steps", []))

        return workflow