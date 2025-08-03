"""
DevTeam Plugin Workflow Module

This module provides workflow functionality for the DevTeam plugin.
Workflows define how tasks are processed by different agents in sequence.
"""

import asyncio
import logging
import uuid
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

from aixterm.plugins.devteam.events import EventBus, EventType, WorkflowEvent

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

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStep:
    """
    A step in a workflow.

    Each step represents a task to be performed by an agent.
    """

    def __init__(
        self,
        step_id: str,
        name: str,
        description: str,
        agent_type: str,
        task_template: Dict[str, Any],
        depends_on: Optional[List[str]] = None,
    ):
        """
        Initialize a workflow step.

        Args:
            step_id: The unique ID for this step.
            name: The human-readable name for this step.
            description: A description of this step.
            agent_type: The type of agent that will handle this step.
            task_template: Template for the task to be created for this step.
            depends_on: IDs of steps that must be completed before this one.
        """
        self.step_id = step_id
        self.name = name
        self.description = description
        self.agent_type = agent_type
        self.task_template = task_template
        self.depends_on = depends_on or []

        self.status = WorkflowStepStatus.PENDING
        self.task_id: Optional[str] = None
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert this step to a dictionary.

        Returns:
            Dictionary representation of this step.
        """
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "agent_type": self.agent_type,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "task_id": self.task_id,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


class Workflow:
    """
    A workflow for processing tasks through multiple agents.

    Workflows define a sequence of steps, each handled by a different agent.
    Steps can have dependencies on other steps.
    """

    def __init__(
        self,
        workflow_id: str,
        name: str,
        description: str,
        steps: List[WorkflowStep],
        context: Optional[Dict[str, Any]] = None,
        event_bus: Optional[EventBus] = None,
    ):
        """
        Initialize a workflow.

        Args:
            workflow_id: The unique ID for this workflow.
            name: The human-readable name for this workflow.
            description: A description of this workflow.
            steps: The steps in this workflow.
            context: Shared context for the workflow.
            event_bus: Event bus for publishing events.
        """
        self.workflow_id = workflow_id
        self.name = name
        self.description = description
        self.steps = {step.step_id: step for step in steps}
        self.context = context or {}
        self.event_bus = event_bus

        self.status = WorkflowStatus.CREATED
        self.current_step_ids: List[str] = []
        self.completed_step_ids: List[str] = []
        self.failed_step_ids: List[str] = []
        self.skipped_step_ids: List[str] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    async def start(self) -> bool:
        """
        Start the workflow.

        Returns:
            True if the workflow was started successfully.
        """
        if (
            self.status != WorkflowStatus.CREATED
            and self.status != WorkflowStatus.PAUSED
        ):
            logger.error(
                f"Cannot start workflow {self.workflow_id} with status {self.status}"
            )
            return False

        # Set status to running
        self.status = WorkflowStatus.RUNNING
        self.start_time = asyncio.get_event_loop().time()

        # Publish event
        if self.event_bus:
            await self.event_bus.publish(
                WorkflowEvent(
                    event_type=EventType.WORKFLOW_CREATED,
                    source="workflow_engine",
                    workflow_id=self.workflow_id,
                    data={"name": self.name},
                )
            )

        # Find initial steps (no dependencies)
        self.current_step_ids = [
            step_id for step_id, step in self.steps.items() if not step.depends_on
        ]

        if not self.current_step_ids:
            logger.error(f"Workflow {self.workflow_id} has no initial steps")
            self.status = WorkflowStatus.FAILED
            return False

        logger.info(f"Started workflow {self.workflow_id} with {len(self.steps)} steps")
        return True

    async def execute_step(
        self,
        step_id: str,
        execute_task_fn: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    ) -> bool:
        """
        Execute a step in the workflow.

        Args:
            step_id: The ID of the step to execute.
            execute_task_fn: Function to execute a task.

        Returns:
            True if the step was executed successfully.
        """
        if step_id not in self.steps:
            logger.error(f"Step {step_id} not found in workflow {self.workflow_id}")
            return False

        step = self.steps[step_id]

        # Check if all dependencies are completed
        for dep_id in step.depends_on:
            if dep_id not in self.completed_step_ids:
                logger.error(
                    f"Cannot execute step {step_id}: dependency {dep_id} not completed"
                )
                return False

        # Update step status
        step.status = WorkflowStepStatus.IN_PROGRESS
        step.start_time = asyncio.get_event_loop().time()

        # Create task from template
        task = self._create_task_from_template(step)

        try:
            # Execute the task
            result = await execute_task_fn(task)

            # Update step with result
            step.task_id = task.get("id")
            step.result = result
            step.end_time = asyncio.get_event_loop().time()

            if result.get("success", False):
                step.status = WorkflowStepStatus.COMPLETED
                self.completed_step_ids.append(step_id)
                self.current_step_ids.remove(step_id)

                # Update workflow context with step result
                self._update_context_with_result(step_id, result)

                logger.info(f"Step {step_id} completed successfully")
            else:
                step.status = WorkflowStepStatus.FAILED
                step.error = result.get("error", "Unknown error")
                self.failed_step_ids.append(step_id)
                self.current_step_ids.remove(step_id)

                logger.error(f"Step {step_id} failed: {step.error}")

            # Find next steps
            self._update_next_steps()

            return step.status == WorkflowStepStatus.COMPLETED

        except Exception as e:
            logger.exception(f"Error executing step {step_id}")

            step.status = WorkflowStepStatus.FAILED
            step.error = str(e)
            step.end_time = asyncio.get_event_loop().time()

            self.failed_step_ids.append(step_id)
            if step_id in self.current_step_ids:
                self.current_step_ids.remove(step_id)

            return False

    def _create_task_from_template(self, step: WorkflowStep) -> Dict[str, Any]:
        """
        Create a task from a step's task template.

        Args:
            step: The workflow step.

        Returns:
            The task dictionary.
        """
        # Start with the template
        task = step.task_template.copy()

        # Add standard fields
        task["id"] = f"task_{uuid.uuid4()}"
        task["workflow_id"] = self.workflow_id
        task["workflow_step_id"] = step.step_id
        task["workflow_context"] = self.context.copy()

        return task

    def _update_context_with_result(self, step_id: str, result: Dict[str, Any]) -> None:
        """
        Update the workflow context with a step's result.

        Args:
            step_id: The ID of the completed step.
            result: The step's result.
        """
        if "result" in result:
            self.context[f"step_{step_id}_result"] = result["result"]

    def _update_next_steps(self) -> None:
        """Update the list of next steps that are ready to execute."""
        # Check all pending steps
        for step_id, step in self.steps.items():
            if step.status != WorkflowStepStatus.PENDING:
                continue

            # Check if all dependencies are completed
            deps_completed = True
            for dep_id in step.depends_on:
                if dep_id not in self.completed_step_ids:
                    deps_completed = False
                    break

            # If dependencies are completed, add to current steps
            if deps_completed and step_id not in self.current_step_ids:
                self.current_step_ids.append(step_id)

    def update_status(self) -> None:
        """Update the workflow status based on step statuses."""
        if self.status != WorkflowStatus.RUNNING:
            return

        # Check if all steps are done (completed, failed, or skipped)
        all_steps_done = all(
            step.status != WorkflowStepStatus.PENDING
            and step.status != WorkflowStepStatus.IN_PROGRESS
            for step in self.steps.values()
        )

        if all_steps_done:
            if not self.failed_step_ids:
                self.status = WorkflowStatus.COMPLETED
                logger.info(f"Workflow {self.workflow_id} completed successfully")
            else:
                self.status = WorkflowStatus.FAILED
                logger.error(
                    f"Workflow {self.workflow_id} failed with {len(self.failed_step_ids)} "
                    f"failed steps out of {len(self.steps)}"
                )

            self.end_time = asyncio.get_event_loop().time()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert this workflow to a dictionary.

        Returns:
            Dictionary representation of this workflow.
        """
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "steps": {step_id: step.to_dict() for step_id, step in self.steps.items()},
            "current_steps": self.current_step_ids,
            "completed_steps": self.completed_step_ids,
            "failed_steps": self.failed_step_ids,
            "skipped_steps": self.skipped_step_ids,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


class WorkflowTemplate:
    """
    A template for creating workflows.

    Workflow templates define the structure of a workflow, including its
    steps and their dependencies. Templates can be instantiated with different
    parameters to create concrete workflows.
    """

    def __init__(
        self,
        template_id: str,
        name: str,
        description: str,
        step_templates: List[Dict[str, Any]],
    ):
        """
        Initialize a workflow template.

        Args:
            template_id: The unique ID for this template.
            name: The human-readable name for this template.
            description: A description of this template.
            step_templates: Templates for the steps in this workflow.
        """
        self.template_id = template_id
        self.name = name
        self.description = description
        self.step_templates = step_templates

    def create_workflow(
        self,
        workflow_id: Optional[str] = None,
        name_suffix: str = "",
        params: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        event_bus: Optional[EventBus] = None,
    ) -> Workflow:
        """
        Create a workflow from this template.

        Args:
            workflow_id: The unique ID for the new workflow.
            name_suffix: Suffix to add to the workflow name.
            params: Parameters to customize the workflow.
            context: Initial context for the workflow.
            event_bus: Event bus for the workflow.

        Returns:
            The created workflow.
        """
        workflow_id = workflow_id or f"workflow_{uuid.uuid4()}"
        name = f"{self.name}{' ' + name_suffix if name_suffix else ''}"
        params = params or {}
        context = context or {}

        # Create steps from templates
        steps = []
        for step_template in self.step_templates:
            # Apply parameters to step template
            step_data = self._apply_params(step_template, params)

            # Create the step
            step = WorkflowStep(
                step_id=step_data["step_id"],
                name=step_data["name"],
                description=step_data["description"],
                agent_type=step_data["agent_type"],
                task_template=step_data["task_template"],
                depends_on=step_data.get("depends_on", []),
            )
            steps.append(step)

        # Create and return the workflow
        workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            description=self.description,
            steps=steps,
            context=context,
            event_bus=event_bus,
        )

        return workflow

    def _apply_params(
        self, template: Dict[str, Any], params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply parameters to a template.

        Args:
            template: The template to apply parameters to.
            params: The parameters to apply.

        Returns:
            The template with parameters applied.
        """
        # Make a deep copy of the template
        import json

        result = json.loads(json.dumps(template))

        # Replace {param_name} placeholders in strings with parameter values
        def replace_params(obj: Any) -> Any:
            if isinstance(obj, str):
                for param_name, param_value in params.items():
                    placeholder = f"{{{param_name}}}"
                    if placeholder in obj:
                        obj = obj.replace(placeholder, str(param_value))
                return obj
            elif isinstance(obj, dict):
                return {k: replace_params(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_params(item) for item in obj]
            else:
                return obj

        return replace_params(result)


def create_feature_workflow_template() -> WorkflowTemplate:
    """
    Create a workflow template for implementing a feature.

    Returns:
        The feature implementation workflow template.
    """
    return WorkflowTemplate(
        template_id="feature_implementation",
        name="Feature Implementation Workflow",
        description="Workflow for implementing a new feature",
        step_templates=[
            {
                "step_id": "planning",
                "name": "Feature Planning",
                "description": "Plan the feature implementation",
                "agent_type": "project_manager",
                "task_template": {
                    "type": "plan",
                    "description": "Plan the implementation of {feature_name}",
                    "requirements": "{feature_requirements}",
                },
            },
            {
                "step_id": "code_analysis",
                "name": "Code Analysis",
                "description": "Analyze the codebase to understand where to implement the feature",
                "agent_type": "code_analyst",
                "depends_on": ["planning"],
                "task_template": {
                    "type": "analyze",
                    "code_context": {
                        "description": "Analyze where to implement {feature_name}",
                        "files": {},  # Would be filled with actual files in a real workflow
                    },
                    "analysis_request": "Identify the best place to implement {feature_name}",
                },
            },
            {
                "step_id": "implementation",
                "name": "Feature Implementation",
                "description": "Implement the feature",
                "agent_type": "developer",
                "depends_on": ["planning", "code_analysis"],
                "task_template": {
                    "type": "implement",
                    "description": "Implement {feature_name}",
                    "requirements": "{feature_requirements}",
                    "code_context": {},  # Would be filled based on code_analysis result
                },
            },
            {
                "step_id": "testing",
                "name": "Feature Testing",
                "description": "Test the implemented feature",
                "agent_type": "qa_tester",
                "depends_on": ["implementation"],
                "task_template": {
                    "type": "design_tests",
                    "description": "Design tests for {feature_name}",
                    "requirements": "{feature_requirements}",
                    "code": "",  # Would be filled based on implementation result
                },
            },
        ],
    )
