"""
Specialized workflow step implementations.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .models import WorkflowStep, WorkflowStepType
from ..events import Event, EventType
from ..types import TaskId, TaskPriority, TaskStatus, TaskType, WorkflowStepStatus

if TYPE_CHECKING:
    from .models import Workflow

logger = logging.getLogger(__name__)


class TaskStep(WorkflowStep):
    """Workflow step that creates and executes a task."""

    def __init__(
        self,
        step_id: str,
        name: str,
        description: str,
        task_title: str,
        task_description: str,
        task_type: str,
        task_priority: str,
        assignee: Optional[str] = None,
        wait_for_completion: bool = True,
        next_steps: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a task step.

        Args:
            step_id: Unique ID of the step
            name: Name of the step
            description: Description of the step
            task_title: Title of the task to create
            task_description: Description of the task to create
            task_type: Type of the task to create
            task_priority: Priority of the task to create
            assignee: Name of the agent to assign the task to
            wait_for_completion: Whether to wait for the task to complete
            next_steps: IDs of the next steps after this one
            metadata: Additional step metadata
        """
        super().__init__(
            step_id=step_id,
            step_type=WorkflowStepType.TASK,
            name=name,
            description=description,
            next_steps=next_steps,
            metadata=metadata,
        )
        self.task_title = task_title
        self.task_description = task_description
        self.task_type = task_type
        self.task_priority = task_priority
        self.assignee = assignee
        self.wait_for_completion = wait_for_completion
        self.task_id: Optional[TaskId] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the step to a dictionary.

        Returns:
            Dictionary representation of the step.
        """
        step_dict = super().to_dict()
        step_dict.update(
            {
                "task_title": self.task_title,
                "task_description": self.task_description,
                "task_type": self.task_type,
                "task_priority": self.task_priority,
                "assignee": self.assignee,
                "wait_for_completion": self.wait_for_completion,
                "task_id": self.task_id,
            }
        )
        return step_dict

    @classmethod
    def from_dict(cls, step_dict: Dict[str, Any]) -> "TaskStep":
        """
        Create a step from a dictionary.

        Args:
            step_dict: Dictionary containing step data

        Returns:
            TaskStep object.
        """
        step = cls(
            step_id=step_dict["step_id"],
            name=step_dict["name"],
            description=step_dict["description"],
            task_title=step_dict["task_title"],
            task_description=step_dict["task_description"],
            task_type=step_dict["task_type"],
            task_priority=step_dict["task_priority"],
            assignee=step_dict.get("assignee"),
            wait_for_completion=step_dict.get("wait_for_completion", True),
            next_steps=step_dict.get("next_steps", []),
            metadata=step_dict.get("metadata", {}),
        )

        step.status = WorkflowStepStatus(step_dict["status"])
        step.started_at = step_dict.get("started_at")
        step.completed_at = step_dict.get("completed_at")
        step.result = step_dict.get("result")
        step.error = step_dict.get("error")
        step.task_id = step_dict.get("task_id")

        return step

    async def _execute(
        self, context: Dict[str, Any], workflow: "Workflow"
    ) -> Dict[str, Any]:
        """
        Execute the task step.

        Args:
            context: Workflow context
            workflow: The workflow being executed

        Returns:
            Updated context after execution.
        """
        # Access workflow engine through context (set by executor)
        workflow_engine = context.get("_workflow_engine")
        if not workflow_engine:
            raise ValueError("WorkflowEngine not available in context")

        # Create the task
        task_manager = workflow_engine.task_manager
        task = task_manager.create_task(
            title=self._resolve_template(self.task_title, context),
            description=self._resolve_template(self.task_description, context),
            task_type=TaskType(self.task_type),
            priority=TaskPriority(self.task_priority),
            assignee=self.assignee,
            metadata={
                "workflow_id": context.get("workflow_id"),
                "step_id": self.step_id,
            },
        )

        self.task_id = task.task_id
        context["task_id"] = task.task_id

        if not self.wait_for_completion:
            # Don't wait for the task to complete
            context["result"] = {"task_id": task.task_id, "status": task.status.value}
            return context

        # Wait for the task to complete
        task_completed: asyncio.Future[TaskStatus] = asyncio.Future()

        def handle_task_event(event: Event) -> None:
            if event.event_type in [EventType.TASK_COMPLETED, EventType.TASK_FAILED]:
                event_data = event.data
                if event_data.get("task_id") == task.task_id:
                    task_status = TaskStatus(event_data.get("task", {}).get("status"))
                    task_completed.set_result(task_status)

        # Subscribe to task events
        workflow_engine.event_bus.subscribe(EventType.TASK_COMPLETED, handle_task_event)
        workflow_engine.event_bus.subscribe(EventType.TASK_FAILED, handle_task_event)

        try:
            # Wait for the task to complete or fail
            task_status = await task_completed

            # Update the result
            updated_task = task_manager.get_task(task.task_id)
            if updated_task:
                context["result"] = {
                    "task_id": updated_task.task_id,
                    "status": updated_task.status.value,
                    "artifacts": updated_task.artifacts,
                }

            # If the task failed, mark the step as failed
            if task_status == TaskStatus.FAILED:
                self.status = WorkflowStepStatus.FAILED
                self.error = "Task failed"
        finally:
            # Unsubscribe from task events
            workflow_engine.event_bus.unsubscribe(
                EventType.TASK_COMPLETED, handle_task_event
            )
            workflow_engine.event_bus.unsubscribe(
                EventType.TASK_FAILED, handle_task_event
            )

        return context

    def _resolve_template(self, template: str, context: Dict[str, Any]) -> str:
        """
        Resolve a template string using the context.

        Args:
            template: Template string with placeholders
            context: Workflow context

        Returns:
            Resolved string.
        """
        # Simple template resolution using string formatting
        try:
            return template.format(**context)
        except KeyError:
            # Return the original template if the context doesn't have the required keys
            return template


class ConditionStep(WorkflowStep):
    """Workflow step that evaluates a condition and determines flow."""

    def __init__(
        self,
        step_id: str,
        name: str,
        description: str,
        condition: str,
        true_step: str,
        false_step: str,
        next_steps: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a condition step.

        Args:
            step_id: Unique ID of the step
            name: Name of the step
            description: Description of the step
            condition: Condition to evaluate
            true_step: Step ID to execute if condition is true
            false_step: Step ID to execute if condition is false
            next_steps: IDs of the next steps after this one
            metadata: Additional step metadata
        """
        super().__init__(
            step_id=step_id,
            step_type=WorkflowStepType.CONDITION,
            name=name,
            description=description,
            next_steps=next_steps,
            metadata=metadata,
        )
        self.condition = condition
        self.true_step = true_step
        self.false_step = false_step

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the step to a dictionary.

        Returns:
            Dictionary representation of the step.
        """
        step_dict = super().to_dict()
        step_dict.update(
            {
                "condition": self.condition,
                "true_step": self.true_step,
                "false_step": self.false_step,
            }
        )
        return step_dict

    @classmethod
    def from_dict(cls, step_dict: Dict[str, Any]) -> "ConditionStep":
        """
        Create a step from a dictionary.

        Args:
            step_dict: Dictionary containing step data

        Returns:
            ConditionStep object.
        """
        step = cls(
            step_id=step_dict["step_id"],
            name=step_dict["name"],
            description=step_dict["description"],
            condition=step_dict["condition"],
            true_step=step_dict["true_step"],
            false_step=step_dict["false_step"],
            next_steps=step_dict.get("next_steps", []),
            metadata=step_dict.get("metadata", {}),
        )

        step.status = WorkflowStepStatus(step_dict["status"])
        step.started_at = step_dict.get("started_at")
        step.completed_at = step_dict.get("completed_at")
        step.result = step_dict.get("result")
        step.error = step_dict.get("error")

        return step

    async def _execute(
        self, context: Dict[str, Any], workflow: "Workflow"
    ) -> Dict[str, Any]:
        """
        Execute the condition step.

        Args:
            context: Workflow context
            workflow: The workflow being executed

        Returns:
            Updated context after execution.
        """
        # Evaluate the condition
        condition_result = self._evaluate_condition(self.condition, context)

        # Set the result
        context["result"] = {"condition": self.condition, "result": condition_result}
        self.result = condition_result

        # Modify the next steps based on the condition result
        if condition_result:
            self.next_steps = [self.true_step]
        else:
            self.next_steps = [self.false_step]

        return context

    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        Evaluate a condition string using the context.

        Args:
            condition: Condition string
            context: Workflow context

        Returns:
            Boolean result of the condition.
        """
        # Simple condition evaluation using eval (careful with security!)
        try:
            # Create a safe subset of the context for evaluation
            safe_context = {}
            for key, value in context.items():
                if isinstance(
                    value, (bool, int, float, str, list, dict, set, type(None))
                ):
                    safe_context[key] = value

            # Evaluate the condition
            return bool(eval(condition, {"__builtins__": {}}, safe_context))
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {e}")
            return False
