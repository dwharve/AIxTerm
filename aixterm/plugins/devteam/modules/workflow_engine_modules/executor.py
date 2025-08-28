"""
Workflow execution engine and orchestration logic.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Set

from .models import Workflow, WorkflowStep
from ..config import ConfigManager
from ..events import EventBus, EventType, WorkflowEvent
from ..task_manager import TaskManager
from ..types import WorkflowId, WorkflowStatus

logger = logging.getLogger(__name__)


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
        self.config_manager = config_manager
        self.event_bus = event_bus
        self.task_manager = task_manager
        self.workflows: Dict[WorkflowId, Workflow] = {}
        self.running_workflows: Set[WorkflowId] = set()
        self._workflow_tasks: Dict[WorkflowId, asyncio.Task] = {}  # Internal task tracking
        self._shutdown_event = asyncio.Event()

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
            The workflow or None if not found.
        """
        return self.workflows.get(workflow_id)

    def start_workflow(
        self, workflow_id: WorkflowId, initial_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Workflow]:
        """
        Start a workflow execution.

        Args:
            workflow_id: ID of the workflow to start
            initial_context: Initial context for the workflow

        Returns:
            The started workflow or None if not found.
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            logger.error(f"Workflow {workflow_id} not found")
            return None

        if workflow.status != WorkflowStatus.PENDING:
            logger.error(f"Workflow {workflow_id} is not pending")
            return None

        # Update workflow status and context
        workflow.status = WorkflowStatus.IN_PROGRESS
        workflow.started_at = datetime.now().isoformat()
        workflow.updated_at = workflow.started_at
        workflow.context = initial_context or {}
        workflow.context["workflow_id"] = workflow_id
        workflow.context["_workflow_engine"] = self  # Add engine reference

        # Publish workflow started event
        self._publish_workflow_event(
            event_type=EventType.WORKFLOW_STARTED,
            workflow_id=workflow_id,
            data={"workflow": workflow.to_dict()},
        )

        # Start the workflow execution
        task = asyncio.create_task(self._execute_workflow(workflow))
        self._workflow_tasks[workflow_id] = task
        self.running_workflows.add(workflow_id)

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
                self.running_workflows.discard(workflow.workflow_id)
            if workflow.workflow_id in self._workflow_tasks:
                del self._workflow_tasks[workflow.workflow_id]

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
        return await step.execute(context, workflow)

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
        if workflow_id in self._workflow_tasks:
            self._workflow_tasks[workflow_id].cancel()
            del self._workflow_tasks[workflow_id]
        
        self.running_workflows.discard(workflow_id)

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