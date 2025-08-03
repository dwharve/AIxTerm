"""
Workflow engine for the DevTeam plugin.

This module provides workflow creation, execution, and management.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Union

from .config import ConfigManager
from .events import Event, EventBus, EventType, WorkflowEvent
from .task_manager import Task, TaskManager
from .types import EventId, TaskId, TaskStatus, WorkflowId

logger = logging.getLogger(__name__)


class WorkflowStepStatus(Enum):
    """Status of a workflow step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStatus(Enum):
    """Status of a workflow."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


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
        step_type = WorkflowStepType(step_dict["step_type"])

        step = cls(
            step_id=step_dict["step_id"],
            step_type=step_type,
            name=step_dict["name"],
            description=step_dict["description"],
            next_steps=step_dict.get("next_steps", []),
            metadata=step_dict.get("metadata", {}),
        )

        step.status = WorkflowStepStatus(step_dict["status"])
        step.started_at = step_dict.get("started_at")
        step.completed_at = step_dict.get("completed_at")
        step.result = step_dict.get("result")
        step.error = step_dict.get("error")

        return step

    async def execute(
        self, context: Dict[str, Any], workflow_engine: "WorkflowEngine"
    ) -> Dict[str, Any]:
        """
        Execute the step.

        Args:
            context: Workflow context
            workflow_engine: Workflow engine instance

        Returns:
            Updated context after execution.
        """
        self.status = WorkflowStepStatus.IN_PROGRESS
        self.started_at = datetime.now().isoformat()

        try:
            # Implementation in subclasses
            context = await self._execute(context, workflow_engine)
            self.status = WorkflowStepStatus.COMPLETED
            self.result = context.get("result")
        except Exception as e:
            self.status = WorkflowStepStatus.FAILED
            self.error = str(e)
            logger.error(f"Step {self.step_id} failed: {e}")
            raise
        finally:
            self.completed_at = datetime.now().isoformat()

        return context

    async def _execute(
        self, context: Dict[str, Any], workflow_engine: "WorkflowEngine"
    ) -> Dict[str, Any]:
        """
        Internal execute method to be implemented by subclasses.

        Args:
            context: Workflow context
            workflow_engine: Workflow engine instance

        Returns:
            Updated context after execution.
        """
        raise NotImplementedError("Subclasses must implement _execute method")


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
        self, context: Dict[str, Any], workflow_engine: "WorkflowEngine"
    ) -> Dict[str, Any]:
        """
        Execute the task step.

        Args:
            context: Workflow context
            workflow_engine: Workflow engine instance

        Returns:
            Updated context after execution.
        """
        # Create the task
        from .types import TaskPriority, TaskType

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
        task_completed = asyncio.Future()

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
        self, context: Dict[str, Any], workflow_engine: "WorkflowEngine"
    ) -> Dict[str, Any]:
        """
        Execute the condition step.

        Args:
            context: Workflow context
            workflow_engine: Workflow engine instance

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
        # Parse steps
        steps_dict = workflow_dict.get("steps", {})
        steps = {}

        for step_id, step_data in steps_dict.items():
            step_type = WorkflowStepType(step_data["step_type"])

            if step_type == WorkflowStepType.TASK:
                steps[step_id] = TaskStep.from_dict(step_data)
            elif step_type == WorkflowStepType.CONDITION:
                steps[step_id] = ConditionStep.from_dict(step_data)
            else:
                # Default to base class for other step types
                steps[step_id] = WorkflowStep.from_dict(step_data)

        # Create the workflow
        workflow = cls(
            name=workflow_dict["name"],
            description=workflow_dict["description"],
            steps=steps,
            workflow_id=workflow_dict["workflow_id"],
            metadata=workflow_dict.get("metadata", {}),
            start_step_id=workflow_dict.get("start_step_id"),
        )

        # Set additional attributes
        workflow.status = WorkflowStatus(workflow_dict["status"])
        workflow.created_at = workflow_dict["created_at"]
        workflow.updated_at = workflow_dict["updated_at"]
        workflow.started_at = workflow_dict.get("started_at")
        workflow.completed_at = workflow_dict.get("completed_at")
        workflow.current_steps = set(workflow_dict.get("current_steps", []))
        workflow.completed_steps = set(workflow_dict.get("completed_steps", []))
        workflow.context = workflow_dict.get("context", {})

        return workflow


class WorkflowEngine:
    """Engine for managing and executing workflows."""

    def __init__(
        self,
        config_manager: ConfigManager,
        event_bus: EventBus,
        task_manager: TaskManager,
    ):
        """
        Initialize the workflow engine.

        Args:
            config_manager: Configuration manager
            event_bus: Event bus for publishing events
            task_manager: Task manager
        """
        self.config = config_manager
        self.event_bus = event_bus
        self.task_manager = task_manager
        self.workflows: Dict[WorkflowId, Workflow] = {}
        self.running_workflows: Dict[WorkflowId, asyncio.Task] = {}

    def create_workflow(
        self,
        name: str,
        description: str,
        steps: Dict[str, WorkflowStep],
        metadata: Optional[Dict[str, Any]] = None,
        start_step_id: Optional[str] = None,
    ) -> Workflow:
        """
        Create a new workflow.

        Args:
            name: Workflow name
            description: Workflow description
            steps: Dictionary of workflow steps
            metadata: Additional workflow metadata
            start_step_id: ID of the first step (default: first step in steps)

        Returns:
            The created workflow.
        """
        workflow = Workflow(
            name=name,
            description=description,
            steps=steps,
            metadata=metadata,
            start_step_id=start_step_id,
        )

        self.workflows[workflow.workflow_id] = workflow

        # Publish workflow created event
        self._publish_workflow_event(
            event_type=EventType.WORKFLOW_CREATED,
            workflow_id=workflow.workflow_id,
            data={"workflow": workflow.to_dict()},
        )

        return workflow

    def get_workflow(self, workflow_id: WorkflowId) -> Optional[Workflow]:
        """
        Get a workflow by ID.

        Args:
            workflow_id: ID of the workflow to get

        Returns:
            Workflow object if found, None otherwise.
        """
        return self.workflows.get(workflow_id)

    def start_workflow(
        self, workflow_id: WorkflowId, initial_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Workflow]:
        """
        Start a workflow.

        Args:
            workflow_id: ID of the workflow to start
            initial_context: Initial context for the workflow

        Returns:
            Started workflow if found, None otherwise.
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return None

        if workflow.status != WorkflowStatus.PENDING:
            return None

        # Update workflow status
        workflow.status = WorkflowStatus.IN_PROGRESS
        workflow.started_at = datetime.now().isoformat()
        workflow.updated_at = workflow.started_at

        # Set initial context
        if initial_context:
            workflow.context.update(initial_context)

        # Add workflow ID to context
        workflow.context["workflow_id"] = workflow_id

        # Start the workflow execution
        task = asyncio.create_task(self._execute_workflow(workflow))
        self.running_workflows[workflow_id] = task

        # Publish workflow started event
        self._publish_workflow_event(
            event_type=EventType.WORKFLOW_STARTED,
            workflow_id=workflow_id,
            data={"workflow": workflow.to_dict()},
        )

        return workflow

    async def _execute_workflow(self, workflow: Workflow) -> None:
        """
        Execute a workflow.

        Args:
            workflow: Workflow to execute
        """
        try:
            # Get the start step
            if (
                not workflow.start_step_id
                or workflow.start_step_id not in workflow.steps
            ):
                workflow.status = WorkflowStatus.FAILED
                logger.error(
                    f"Workflow {workflow.workflow_id} has no valid start step: "
                    f"{workflow.start_step_id}"
                )
                return

            current_steps = [workflow.start_step_id]
            workflow.current_steps = set(current_steps)

            # Execute steps until all paths are complete
            while current_steps and workflow.status == WorkflowStatus.IN_PROGRESS:
                next_steps = []

                # Execute all current steps in parallel
                step_tasks = []
                for step_id in current_steps:
                    step = workflow.steps.get(step_id)
                    if not step:
                        logger.error(
                            f"Step {step_id} not found in workflow {workflow.workflow_id}"
                        )
                        continue

                    # Publish step started event
                    self._publish_workflow_event(
                        event_type=EventType.WORKFLOW_STEP_STARTED,
                        workflow_id=workflow.workflow_id,
                        data={"step_id": step_id, "step": step.to_dict()},
                    )

                    # Create task for step execution
                    step_context = workflow.context.copy()
                    step_context["step_id"] = step_id
                    step_task = asyncio.create_task(
                        self._execute_step(step, step_context, workflow)
                    )
                    step_tasks.append((step_id, step_task))

                # Wait for all steps to complete
                for step_id, step_task in step_tasks:
                    try:
                        step_context = await step_task

                        # Update workflow context with step results
                        workflow.context.update(step_context)

                        # Add next steps
                        step = workflow.steps.get(step_id)
                        if step:
                            # Publish step completed event
                            self._publish_workflow_event(
                                event_type=EventType.WORKFLOW_STEP_COMPLETED,
                                workflow_id=workflow.workflow_id,
                                data={"step_id": step_id, "step": step.to_dict()},
                            )

                            # Add next steps
                            next_steps.extend(step.next_steps)

                            # Mark step as completed
                            workflow.completed_steps.add(step_id)
                    except Exception as e:
                        logger.error(f"Error executing step {step_id}: {e}")
                        workflow.status = WorkflowStatus.FAILED
                        break

                # Update current steps
                current_steps = [
                    step_id
                    for step_id in next_steps
                    if step_id not in workflow.completed_steps
                ]
                workflow.current_steps = set(current_steps)

                # Update workflow status
                workflow.updated_at = datetime.now().isoformat()

                # Check if all steps are completed or if there are no more steps to execute
                if not current_steps and workflow.status == WorkflowStatus.IN_PROGRESS:
                    workflow.status = WorkflowStatus.COMPLETED

            # Final workflow status update
            workflow.completed_at = datetime.now().isoformat()
            workflow.updated_at = workflow.completed_at

            # Publish workflow completed/failed event
            event_type = (
                EventType.WORKFLOW_COMPLETED
                if workflow.status == WorkflowStatus.COMPLETED
                else EventType.WORKFLOW_FAILED
            )
            self._publish_workflow_event(
                event_type=event_type,
                workflow_id=workflow.workflow_id,
                data={"workflow": workflow.to_dict()},
            )
        except Exception as e:
            logger.error(f"Error executing workflow {workflow.workflow_id}: {e}")
            workflow.status = WorkflowStatus.FAILED
            workflow.updated_at = datetime.now().isoformat()
            workflow.completed_at = workflow.updated_at

            # Publish workflow failed event
            self._publish_workflow_event(
                event_type=EventType.WORKFLOW_FAILED,
                workflow_id=workflow.workflow_id,
                data={"workflow": workflow.to_dict(), "error": str(e)},
            )
        finally:
            # Remove from running workflows
            if workflow.workflow_id in self.running_workflows:
                del self.running_workflows[workflow.workflow_id]

    async def _execute_step(
        self, step: WorkflowStep, context: Dict[str, Any], workflow: Workflow
    ) -> Dict[str, Any]:
        """
        Execute a workflow step.

        Args:
            step: Step to execute
            context: Step context
            workflow: Workflow being executed

        Returns:
            Updated context after step execution.
        """
        return await step.execute(context, self)

    def cancel_workflow(self, workflow_id: WorkflowId) -> bool:
        """
        Cancel a running workflow.

        Args:
            workflow_id: ID of the workflow to cancel

        Returns:
            True if the workflow was cancelled, False otherwise.
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return False

        if workflow.status != WorkflowStatus.IN_PROGRESS:
            return False

        # Cancel the workflow task
        if workflow_id in self.running_workflows:
            self.running_workflows[workflow_id].cancel()
            del self.running_workflows[workflow_id]

        # Update workflow status
        workflow.status = WorkflowStatus.CANCELLED
        workflow.updated_at = datetime.now().isoformat()
        workflow.completed_at = workflow.updated_at

        # Publish workflow cancelled event
        self._publish_workflow_event(
            event_type=EventType.WORKFLOW_CANCELLED,
            workflow_id=workflow_id,
            data={"workflow": workflow.to_dict()},
        )

        return True

    def _publish_workflow_event(
        self, event_type: EventType, workflow_id: WorkflowId, data: Dict[str, Any]
    ) -> None:
        """
        Publish a workflow event.

        Args:
            event_type: Type of event
            workflow_id: ID of the workflow
            data: Event data
        """
        event = WorkflowEvent(event_type=event_type, workflow_id=workflow_id, data=data)
        self.event_bus.publish(event)
