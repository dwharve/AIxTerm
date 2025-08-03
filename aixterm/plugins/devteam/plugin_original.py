"""
DevTeam Plugin for AIxTerm

This plugin implements a software development team orchestration system based on the
Pythonium DevTeam manager.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

from aixterm.plugins.base import Plugin

from .agents import create_default_registry
from .events import Event, EventBus, EventType, TaskEvent
from .prompts import create_default_optimizer
from .workflow import WorkflowTemplate, create_feature_workflow_template

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of development tasks."""

    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    ANALYSIS = "analysis"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    SECURITY = "security"
    PERFORMANCE = "performance"


class TaskPriority(Enum):
    """Task priority levels."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class TaskStatus(Enum):
    """Task execution status."""

    SUBMITTED = "submitted"
    QUEUED = "queued"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    UNDER_REVIEW = "under_review"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DevTeamPlugin(Plugin):
    """
    DevTeam Plugin for AIxTerm.

    This plugin implements a software development team orchestration system,
    allowing for task submission, agent coordination, and workflow management.
    """

    @property
    def id(self) -> str:
        """Get the plugin ID."""
        return "devteam"

    @property
    def name(self) -> str:
        """Get the plugin name."""
        return "DevTeam"

    @property
    def version(self) -> str:
        """Get the plugin version."""
        return "0.1.0"

    @property
    def description(self) -> str:
        """Get the plugin description."""
        return "AI-powered software development team orchestration"

    @property
    def dependencies(self) -> List[str]:
        """Get the plugin dependencies."""
        # No dependencies for now, but we'll add more as needed
        return []

    def initialize(self) -> bool:
        """Initialize the plugin."""
        self.logger.info("Initializing DevTeam plugin...")

        # Task management
        self._active_tasks = {}
        self._task_queue = []
        self._task_status = {}

        # Set up event bus
        self._event_bus = EventBus()

        # Set up prompt optimizer
        self._prompt_optimizer = create_default_optimizer()

        # Set up adaptive learning system
        from .adaptive import create_adaptive_learning_system

        self._adaptive_learning = create_adaptive_learning_system(
            self._prompt_optimizer
        )

        # Set up agent registry
        self._agent_registry = create_default_registry(self)

        # Set up workflow templates
        self._workflow_templates = {"feature": create_feature_workflow_template()}
        self._active_workflows = {}
        self._task_progress = {}

        # Agent management
        self._agent_registry = create_default_registry(self)
        self._agent_capacity = {}

        # Workflow engine (to be implemented)
        self._workflow_engine = None
        self._active_workflows = {}

        # Configuration (default values)
        self._plugin_config = {
            "max_concurrent_tasks": 5,
            "default_timeout_hours": 24,
            "agent_timeout_minutes": 30,
            "agents": {
                "project_manager": {"enabled": True, "max_tasks": 10},
                "architect": {"enabled": True, "max_tasks": 3},
                "developer": {"enabled": True, "instances": 2, "max_tasks": 5},
                "reviewer": {"enabled": True, "max_tasks": 8},
                "qa": {"enabled": True, "max_tasks": 5},
                "documentation": {"enabled": True, "max_tasks": 3},
            },
            "workflow": {
                "require_architecture_review": True,
                "require_code_review": True,
                "require_testing": True,
                "require_documentation": True,
                "parallel_development": True,
            },
        }

        # Override defaults with user configuration
        if self.config:
            self._plugin_config.update(self.config)

        # Background tasks
        self._background_tasks = set()
        self._shutdown_event = asyncio.Event()

        # Register commands
        self._register_commands()

        # Start background tasks
        self._start_background_tasks()

        # Initialize adaptive learning system
        try:
            if asyncio.get_running_loop():
                # Only create task if we're in an actual running event loop
                asyncio.create_task(self._initialize_adaptive_learning())
        except RuntimeError:
            # If no event loop is running (e.g. in tests), just log it
            self.logger.debug(
                "No running event loop for adaptive learning initialization"
            )
            # For tests, we'll initialize without the async part
            self._init_adaptive_learning_sync()

        self.logger.info("DevTeam plugin initialized successfully")
        return True

    def _init_adaptive_learning_sync(self) -> None:
        """
        Initialize the adaptive learning system synchronously.
        This is used in test environments where asyncio might not be available.
        """
        try:
            self.logger.debug("Initializing adaptive learning synchronously")
            # For testing, we don't need to initialize storage
            # Set metrics_loaded flag to prevent async initialization from running later
            if hasattr(self._adaptive_learning, "_metrics_loaded"):
                self._adaptive_learning._metrics_loaded = True
        except Exception as e:
            self.logger.error(
                f"Failed to initialize adaptive learning system synchronously: {e}"
            )

    async def _initialize_adaptive_learning(self) -> None:
        """Initialize the adaptive learning system."""
        try:
            import os
            from pathlib import Path

            # Create data directory if it doesn't exist
            # Use a subdirectory in the user's home directory
            data_dir = Path.home() / ".aixterm" / "plugins" / "devteam"
            os.makedirs(data_dir, exist_ok=True)

            # Initialize adaptive learning system
            metrics_path = data_dir / "prompt_metrics.json"
            await self._adaptive_learning.initialize(str(metrics_path))

            self.logger.info("Adaptive learning system initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize adaptive learning system: {e}")

    def shutdown(self) -> bool:
        """Shutdown the plugin."""
        self.logger.info("Shutting down DevTeam plugin...")

        # Signal background tasks to stop
        self._shutdown_event.set()

        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()

        # Shutdown all agents
        self._agent_registry.shutdown_agents()

        self.logger.info("DevTeam plugin shutdown successfully")
        return True

    def get_commands(self) -> Dict[str, Any]:
        """Get the plugin commands."""
        return {
            "devteam:submit": self._handle_submit,
            "devteam:list": self._handle_list,
            "devteam:status": self._handle_status,
            "devteam:cancel": self._handle_cancel,
            "devteam:workflow:start": self._handle_workflow_start,
            "devteam:workflow:status": self._handle_workflow_status,
            "devteam:workflow:list": self._handle_workflow_list,
            "devteam:prompt:metrics": self._handle_prompt_metrics,
            "devteam:prompt:experiment": self._handle_prompt_experiment,
        }

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle plugin requests.

        Args:
            request: The request data containing command and parameters.

        Returns:
            The command response.
        """
        command = request.get("command")
        parameters = request.get("parameters", {})

        self.logger.debug(f"Handling command: {command}")

        if command == "devteam:submit":
            return self._handle_submit(request)
        elif command == "devteam:list":
            return self._handle_list(request)
        elif command == "devteam:status":
            return self._handle_status(request)
        elif command == "devteam:cancel":
            return self._handle_cancel(request)
        elif command == "devteam:workflow:start":
            return self._handle_workflow_start(request)
        elif command == "devteam:workflow:status":
            return self._handle_workflow_status(request)
        elif command == "devteam:workflow:list":
            return self._handle_workflow_list(request)
        elif command == "devteam:prompt:metrics":
            return self._handle_prompt_metrics(request)
        elif command == "devteam:prompt:experiment":
            return self._handle_prompt_experiment(request)
        else:
            return {
                "success": False,
                "error": f"Unknown command: {command}",
            }

    def _register_commands(self) -> None:
        """Register plugin commands."""
        # Commands are registered automatically from get_commands()
        pass

    def _start_background_tasks(self) -> None:
        """Start background tasks."""
        # Create a task processor
        loop = asyncio.get_event_loop()
        task_processor = loop.create_task(self._process_tasks())
        self._background_tasks.add(task_processor)

        # Create a workflow processor
        workflow_processor = loop.create_task(self._process_workflows())
        self._background_tasks.add(workflow_processor)

        # Create a metrics saver for adaptive learning
        metrics_saver = loop.create_task(self._periodic_save_metrics())
        self._background_tasks.add(metrics_saver)

        # Remove tasks from set when done
        task_processor.add_done_callback(self._background_tasks.remove)
        workflow_processor.add_done_callback(self._background_tasks.remove)
        metrics_saver.add_done_callback(self._background_tasks.remove)

    async def _periodic_save_metrics(self) -> None:
        """Periodically save metrics from the adaptive learning system."""
        self.logger.debug("Metrics saver started")

        try:
            # Save metrics every hour
            save_interval = 3600  # seconds

            while not self._shutdown_event.is_set():
                # Wait for the interval or until shutdown
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=save_interval
                    )
                except asyncio.TimeoutError:
                    pass

                # If we're shutting down, break the loop
                if self._shutdown_event.is_set():
                    break

                # Save metrics
                try:
                    import os
                    from pathlib import Path

                    # Ensure directory exists
                    data_dir = Path.home() / ".aixterm" / "plugins" / "devteam"
                    os.makedirs(data_dir, exist_ok=True)

                    # Save metrics
                    metrics_path = data_dir / "prompt_metrics.json"
                    await self._adaptive_learning.save_metrics(str(metrics_path))

                    self.logger.debug("Saved adaptive learning metrics")
                except Exception as e:
                    self.logger.error(f"Failed to save adaptive learning metrics: {e}")
        except Exception as e:
            self.logger.error(f"Error in periodic metrics saving: {e}")

    async def _process_tasks(self) -> None:
        """Process tasks in the background."""
        self.logger.debug("Task processor started")

        try:
            while not self._shutdown_event.is_set():
                # Check if there are tasks to process
                if self._task_queue:
                    # Get the next task
                    task_id = self._task_queue[0]

                    # Process the task
                    self.logger.debug(f"Processing task: {task_id}")

                    # Update status
                    self._task_status[task_id] = TaskStatus.IN_PROGRESS

                    # Publish task started event
                    await self._event_bus.publish(
                        TaskEvent(
                            event_type=EventType.TASK_STARTED,
                            source="devteam",
                            task_id=task_id,
                            data={"task": self._active_tasks[task_id]},
                        )
                    )

                    # Get task details
                    task = self._active_tasks[task_id]
                    task_type = task.get("type", TaskType.FEATURE.value)

                    # Handle task based on type
                    if task_type == TaskType.FEATURE.value:
                        # Start a feature workflow for feature tasks
                        await self._start_feature_workflow(task_id, task)
                    else:
                        # For other task types, process directly
                        result = await self._process_task(task)

                        # Update task with result
                        self._active_tasks[task_id]["result"] = result

                        # Update task status
                        if result.get("success", False):
                            self._task_status[task_id] = TaskStatus.COMPLETED

                            # Publish task completed event
                            await self._event_bus.publish(
                                TaskEvent(
                                    event_type=EventType.TASK_COMPLETED,
                                    source="devteam",
                                    task_id=task_id,
                                    data={"task": self._active_tasks[task_id]},
                                )
                            )
                        else:
                            self._task_status[task_id] = TaskStatus.FAILED

                            # Publish task failed event
                            await self._event_bus.publish(
                                TaskEvent(
                                    event_type=EventType.TASK_FAILED,
                                    source="devteam",
                                    task_id=task_id,
                                    data={
                                        "task": self._active_tasks[task_id],
                                        "error": result.get("error", "Unknown error"),
                                    },
                                )
                            )

                    # Remove from queue
                    self._task_queue.pop(0)
                else:
                    # Wait for new tasks
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.logger.debug("Task processor cancelled")
        except Exception as e:
            self.logger.error(f"Error in task processor: {e}")

    async def _process_workflows(self) -> None:
        """Process workflows in the background."""
        self.logger.debug("Workflow processor started")

        try:
            while not self._shutdown_event.is_set():
                # Check if there are active workflows
                if self._active_workflows:
                    # Process each workflow
                    for workflow_id, workflow in list(self._active_workflows.items()):
                        # Skip if workflow is not running
                        if workflow.status.value != "running":
                            continue

                        # Check for steps to execute
                        for step_id in workflow.current_step_ids:
                            step = workflow.steps[step_id]

                            # Skip if step is already in progress
                            if step.status.value == "in_progress":
                                continue

                            # Execute the step
                            self.logger.debug(
                                f"Executing workflow step: {workflow_id}/{step_id}"
                            )

                            # Execute step in a separate task to avoid blocking
                            loop = asyncio.get_event_loop()
                            task = loop.create_task(
                                workflow.execute_step(
                                    step_id, self._execute_workflow_step
                                )
                            )

                            # Add callback to update workflow status when step completes
                            task.add_done_callback(lambda _: workflow.update_status())

                        # Update workflow status
                        workflow.update_status()

                        # Remove completed workflows
                        if workflow.status.value in [
                            "completed",
                            "failed",
                            "cancelled",
                        ]:
                            self.logger.info(
                                f"Workflow {workflow_id} finished with status: {workflow.status.value}"
                            )

                            # Update any associated tasks
                            task_id = workflow.context.get("task_id")
                            if task_id:
                                if workflow.status.value == "completed":
                                    self._task_status[task_id] = TaskStatus.COMPLETED

                                    # Publish task completed event
                                    await self._event_bus.publish(
                                        TaskEvent(
                                            event_type=EventType.TASK_COMPLETED,
                                            source="workflow_engine",
                                            task_id=task_id,
                                            data={"workflow_id": workflow_id},
                                        )
                                    )
                                elif workflow.status.value == "failed":
                                    self._task_status[task_id] = TaskStatus.FAILED

                                    # Publish task failed event
                                    await self._event_bus.publish(
                                        TaskEvent(
                                            event_type=EventType.TASK_FAILED,
                                            source="workflow_engine",
                                            task_id=task_id,
                                            data={"workflow_id": workflow_id},
                                        )
                                    )
                                elif workflow.status.value == "cancelled":
                                    self._task_status[task_id] = TaskStatus.CANCELLED

                                    # Publish task cancelled event
                                    await self._event_bus.publish(
                                        TaskEvent(
                                            event_type=EventType.TASK_CANCELLED,
                                            source="workflow_engine",
                                            task_id=task_id,
                                            data={"workflow_id": workflow_id},
                                        )
                                    )

                # Sleep before next iteration
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.logger.debug("Workflow processor cancelled")
        except Exception as e:
            self.logger.error(f"Error in workflow processor: {e}")

    async def _execute_workflow_step(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a workflow step's task.

        Args:
            task: The task to execute.

        Returns:
            The execution result.
        """
        agent_type = task.get("agent_type")
        if not agent_type:
            return {"success": False, "error": "No agent_type specified for task"}

        # Get the appropriate agent
        agent = self._agent_registry.get_agent(agent_type)
        if not agent:
            # Try to create the agent if it doesn't exist
            agent = self._agent_registry.create_agent(agent_type)

        if not agent:
            return {"success": False, "error": f"Agent not found: {agent_type}"}

        # Process the task with the agent
        self.logger.debug(f"Executing task with agent {agent_type}: {task.get('id')}")
        try:
            result = await agent.process_task(task)
            return result
        except Exception as e:
            self.logger.error(f"Error executing task with agent {agent_type}: {e}")
            return {"success": False, "error": f"Agent error: {str(e)}"}

    async def _process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a task directly (not through workflow).

        Args:
            task: The task to process.

        Returns:
            The processing result.
        """
        # Placeholder for now, will be implemented with agent dispatching
        task_type = task.get("type", TaskType.FEATURE.value)

        # Determine which agent type to use based on task type
        agent_type = "project_manager"  # Default
        if task_type == TaskType.ANALYSIS.value:
            agent_type = "code_analyst"
        elif task_type == TaskType.TESTING.value:
            agent_type = "qa_tester"

        # Add agent_type to task
        task_with_agent = {**task, "agent_type": agent_type}

        # Execute with the appropriate agent
        return await self._execute_workflow_step(task_with_agent)

    async def _start_feature_workflow(self, task_id: str, task: Dict[str, Any]) -> None:
        """
        Start a feature implementation workflow for a task.

        Args:
            task_id: The task ID.
            task: The task data.
        """
        workflow_template = self._workflow_templates.get("feature")
        if not workflow_template:
            self.logger.error(f"Feature workflow template not found")
            self._task_status[task_id] = TaskStatus.FAILED
            return

        # Create workflow parameters
        params = {
            "feature_name": task["title"],
            "feature_requirements": task["description"],
        }

        # Create workflow context
        context = {
            "task_id": task_id,
            "task": task,
        }

        # Create workflow
        workflow_id = f"workflow_{uuid.uuid4()}"
        workflow = workflow_template.create_workflow(
            workflow_id=workflow_id,
            name_suffix=f"for {task['title']}",
            params=params,
            context=context,
            event_bus=self._event_bus,
        )

        # Add to active workflows
        self._active_workflows[workflow_id] = workflow

        # Link task to workflow
        self._active_tasks[task_id]["workflow_id"] = workflow_id

        # Start the workflow
        self.logger.info(f"Starting workflow {workflow_id} for task {task_id}")
        await workflow.start()

    def _handle_submit(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle task submission.

        Args:
            request: The request data containing parameters.

        Returns:
            The command response.
        """
        parameters = request.get("parameters", {})
        try:
            # Create task ID
            task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Create task
            task = {
                "id": task_id,
                "title": parameters["title"],
                "description": parameters["description"],
                "type": parameters.get("type", TaskType.FEATURE.value),
                "priority": parameters.get(
                    "priority", TaskPriority.MEDIUM.name.lower()
                ),
                "submitted_at": datetime.now().isoformat(),
            }

            # Add to active tasks
            self._active_tasks[task_id] = task

            # Add to task queue
            self._task_queue.append(task_id)

            # Set initial status
            self._task_status[task_id] = TaskStatus.SUBMITTED

            return {
                "success": True,
                "task_id": task_id,
                "message": f"Task submitted successfully: {task_id}",
            }
        except KeyError as e:
            return {
                "success": False,
                "error": f"Missing required parameter: {str(e)}",
            }
        except Exception as e:
            self.logger.error(f"Error submitting task: {e}")
            return {
                "success": False,
                "error": f"Error submitting task: {str(e)}",
            }

    def _handle_list(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle task listing.

        Args:
            request: The request data containing parameters.

        Returns:
            The command response.
        """
        parameters = request.get("parameters", {})
        try:
            # Check if status filter is provided
            status_filter = parameters.get("status")

            tasks = []
            for task_id, task in self._active_tasks.items():
                # Get current status
                status = self._task_status.get(task_id, TaskStatus.SUBMITTED)

                # Apply status filter if provided
                if status_filter and status.value != status_filter:
                    continue

                # Add task to results
                tasks.append(
                    {
                        "id": task_id,
                        "title": task["title"],
                        "type": task["type"],
                        "priority": task["priority"],
                        "status": status.value,
                        "submitted_at": task["submitted_at"],
                    }
                )

            return {
                "success": True,
                "tasks": tasks,
            }
        except Exception as e:
            self.logger.error(f"Error listing tasks: {e}")
            return {
                "success": False,
                "error": f"Error listing tasks: {str(e)}",
            }

    def _handle_status(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle task status retrieval.

        Args:
            request: The request data containing parameters.

        Returns:
            The command response.
        """
        parameters = request.get("parameters", {})
        try:
            task_id = parameters["task_id"]

            # Check if task exists
            if task_id not in self._active_tasks:
                return {
                    "success": False,
                    "error": f"Task not found: {task_id}",
                }

            # Get task and status
            task = self._active_tasks[task_id]
            status = self._task_status.get(task_id, TaskStatus.SUBMITTED)
            progress = self._task_progress.get(task_id, {})

            return {
                "success": True,
                "task": {
                    "id": task_id,
                    "title": task["title"],
                    "description": task["description"],
                    "type": task["type"],
                    "priority": task["priority"],
                    "status": status.value,
                    "progress": progress,
                    "submitted_at": task["submitted_at"],
                },
            }
        except KeyError as e:
            return {
                "success": False,
                "error": f"Missing required parameter: {str(e)}",
            }
        except Exception as e:
            self.logger.error(f"Error getting task status: {e}")
            return {
                "success": False,
                "error": f"Error getting task status: {str(e)}",
            }

    def _handle_cancel(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle task cancellation.

        Args:
            request: The request data containing parameters.

        Returns:
            The command response.
        """
        parameters = request.get("parameters", {})
        try:
            task_id = parameters["task_id"]

            # Check if task exists
            if task_id not in self._active_tasks:
                return {
                    "success": False,
                    "error": f"Task not found: {task_id}",
                }

            # Set status to cancelled
            self._task_status[task_id] = TaskStatus.CANCELLED

            # Remove from queue if present
            if task_id in self._task_queue:
                self._task_queue.remove(task_id)

            # Cancel associated workflow if exists
            task = self._active_tasks[task_id]
            workflow_id = task.get("workflow_id")
            if workflow_id and workflow_id in self._active_workflows:
                workflow = self._active_workflows[workflow_id]
                workflow.status = (
                    "cancelled"  # This will be picked up by the workflow processor
                )

            return {
                "success": True,
                "message": f"Task cancelled: {task_id}",
            }
        except KeyError as e:
            return {
                "success": False,
                "error": f"Missing required parameter: {str(e)}",
            }
        except Exception as e:
            self.logger.error(f"Error cancelling task: {e}")
            return {
                "success": False,
                "error": f"Error cancelling task: {str(e)}",
            }

    def _handle_workflow_start(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle workflow start request.

        Args:
            request: The request data containing parameters.

        Returns:
            The command response.
        """
        parameters = request.get("parameters", {})
        try:
            template_id = parameters["template_id"]
            workflow_name = parameters.get(
                "name", f"Workflow {datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            params = parameters.get("params", {})

            # Check if template exists
            if template_id not in self._workflow_templates:
                return {
                    "success": False,
                    "error": f"Workflow template not found: {template_id}",
                }

            # Get workflow template
            template = self._workflow_templates[template_id]

            # Create workflow
            workflow_id = f"workflow_{uuid.uuid4()}"
            workflow = template.create_workflow(
                workflow_id=workflow_id,
                name_suffix=workflow_name,
                params=params,
                event_bus=self._event_bus,
            )

            # Add to active workflows
            self._active_workflows[workflow_id] = workflow

            # Start the workflow
            asyncio.create_task(workflow.start())

            return {
                "success": True,
                "workflow_id": workflow_id,
                "message": f"Workflow started: {workflow_id}",
            }
        except KeyError as e:
            return {
                "success": False,
                "error": f"Missing required parameter: {str(e)}",
            }
        except Exception as e:
            self.logger.error(f"Error starting workflow: {e}")
            return {
                "success": False,
                "error": f"Error starting workflow: {str(e)}",
            }

    def _handle_workflow_status(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle workflow status request.

        Args:
            request: The request data containing parameters.

        Returns:
            The command response.
        """
        parameters = request.get("parameters", {})
        try:
            workflow_id = parameters["workflow_id"]

            # Check if workflow exists
            if workflow_id not in self._active_workflows:
                return {
                    "success": False,
                    "error": f"Workflow not found: {workflow_id}",
                }

            # Get workflow
            workflow = self._active_workflows[workflow_id]

            # Get workflow status
            workflow_dict = workflow.to_dict()

            return {
                "success": True,
                "workflow": workflow_dict,
            }
        except KeyError as e:
            return {
                "success": False,
                "error": f"Missing required parameter: {str(e)}",
            }
        except Exception as e:
            self.logger.error(f"Error getting workflow status: {e}")
            return {
                "success": False,
                "error": f"Error getting workflow status: {str(e)}",
            }

    def _handle_workflow_list(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle workflow listing request.

        Args:
            request: The request data containing parameters.

        Returns:
            The command response.
        """
        parameters = request.get("parameters", {})
        try:
            # Check if status filter is provided
            status_filter = parameters.get("status")

            workflows = []
            for workflow_id, workflow in self._active_workflows.items():
                # Apply status filter if provided
                if status_filter and workflow.status.value != status_filter:
                    continue

                # Add workflow summary to results
                workflows.append(
                    {
                        "id": workflow_id,
                        "name": workflow.name,
                        "status": workflow.status.value,
                        "steps_total": len(workflow.steps),
                        "steps_completed": len(workflow.completed_step_ids),
                        "steps_failed": len(workflow.failed_step_ids),
                        "start_time": workflow.start_time,
                    }
                )

            return {"success": True, "workflows": workflows}
        except Exception as e:
            self.logger.error(f"Error listing workflows: {e}")
            return {"success": False, "error": f"Error listing workflows: {str(e)}"}

    def _handle_prompt_metrics(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the devteam:prompt:metrics command.

        Returns metrics and performance data from the adaptive learning system.

        Args:
            request: The request data containing parameters.

        Returns:
            Response with metrics data.
        """
        try:
            # Create a task to run the async method
            loop = asyncio.get_event_loop()
            metrics = loop.run_until_complete(
                self._adaptive_learning.get_metrics_report()
            )

            return {"success": True, "metrics": metrics}
        except Exception as e:
            self.logger.error(f"Failed to get prompt metrics: {e}")
            return {
                "success": False,
                "error": f"Failed to get prompt metrics: {str(e)}",
            }

    def _handle_prompt_experiment(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the devteam:prompt:experiment command.

        Starts an experiment with prompt variations for an agent type.

        Args:
            request: The request data containing parameters.

        Returns:
            Response indicating experiment status.
        """
        parameters = request.get("parameters", {})
        try:
            # Extract arguments
            agent_type = parameters.get("agent_type")
            variation_count = int(parameters.get("variations", 2))

            if not agent_type:
                return {
                    "success": False,
                    "error": "Missing required parameter: agent_type",
                }

            # Check if the agent type is valid
            valid_agent_types = [
                "project_manager",
                "code_analyst",
                "developer",
                "qa_tester",
            ]
            if agent_type not in valid_agent_types:
                return {
                    "success": False,
                    "error": f"Invalid agent_type: {agent_type}. Valid types: {', '.join(valid_agent_types)}",
                }

            # Start experiment (run async method in a task)
            loop = asyncio.get_event_loop()
            loop.run_until_complete(
                self._adaptive_learning.start_experiment(agent_type, variation_count)
            )

            return {
                "success": True,
                "message": f"Started prompt experiment for {agent_type} with {variation_count} variations",
            }
        except Exception as e:
            self.logger.error(f"Failed to start prompt experiment: {e}")
            error_msg = (
                f"Invalid parameter: {str(e)}"
                if isinstance(e, ValueError)
                else f"Failed to start prompt experiment: {str(e)}"
            )
            return {"success": False, "error": error_msg}
