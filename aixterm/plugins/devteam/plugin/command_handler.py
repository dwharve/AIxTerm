import asyncio

"""
Command handler module for the DevTeam plugin.

This module provides command handling functionality for the DevTeam plugin.
"""

import logging
from typing import Any, Dict

from ..modules.types import TaskPriority, TaskStatus, TaskType
from ..modules.workflow_engine import WorkflowStep

logger = logging.getLogger(__name__)


class DevTeamCommandHandler:
    """Handler for DevTeam plugin commands."""

    def __init__(self, plugin):
        """
        Initialize the command handler.

        Args:
            plugin: The DevTeam plugin instance
        """
        self._plugin = plugin
        self._task_manager = plugin._task_manager
        self._workflow_engine = plugin._workflow_engine
        self._event_bus = plugin._event_bus
        self._agent_registry = plugin._agent_registry
        self._adaptive_learning = plugin._adaptive_learning
        self._workflow_templates = plugin._workflow_templates

    def handle_task_create(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the devteam:task:create command.

        Creates a new task and optionally starts a workflow for it.

        Args:
            request: The request data containing parameters.

        Returns:
            Response containing task details.
        """
        parameters = request.get("parameters", {})
        try:
            # Extract task parameters
            title = parameters.get("title")
            description = parameters.get("description", "")
            task_type_str = parameters.get("type", "feature").lower()
            priority_str = parameters.get("priority", "medium").upper()

            # Validate required parameters
            if not title:
                return {"success": False, "error": "Missing required parameter: title"}

            # Convert task type string to enum
            try:
                task_type = TaskType[task_type_str.upper()]
            except (KeyError, AttributeError):
                valid_types = [t.name.lower() for t in TaskType]
                return {
                    "success": False,
                    "error": f"Invalid task type: {task_type_str}. Valid types: {', '.join(valid_types)}",
                }

            # Convert priority string to enum
            try:
                priority = TaskPriority[priority_str]
            except (KeyError, AttributeError):
                valid_priorities = [p.name.lower() for p in TaskPriority]
                return {
                    "success": False,
                    "error": f"Invalid priority: {priority_str}. Valid priorities: {', '.join(valid_priorities)}",
                }

            # Create task
            task = self._task_manager.create_task(
                title=title,
                description=description,
                task_type=task_type,
                priority=priority,
            )

            # Check if we should start a workflow
            start_workflow = parameters.get("start_workflow", True)
            if start_workflow:
                # Get workflow template based on task type
                template_name = task_type.value
                if template_name not in self._workflow_templates:
                    template_name = "feature"  # Default to feature workflow

                template = self._workflow_templates[template_name]

                # Create workflow for the task
                workflow = self._workflow_engine.create_workflow(
                    template, context={"task_id": task.id}
                )

                # Start workflow
                asyncio.create_task(self._workflow_engine.start_workflow(workflow.id))

                # Return response with task and workflow details
                return {
                    "success": True,
                    "task": {
                        "id": task.id,
                        "title": task.title,
                        "description": task.description,
                        "type": task.task_type.value,
                        "priority": task.priority.name,
                        "status": task.status.value,
                        "created_at": task.created_at.isoformat(),
                    },
                    "workflow": {
                        "id": workflow.id,
                        "status": workflow.status.value,
                        "step_count": len(workflow.steps),
                    },
                }
            else:
                # Return response with just the task details
                return {
                    "success": True,
                    "task": {
                        "id": task.id,
                        "title": task.title,
                        "description": task.description,
                        "type": task.task_type.value,
                        "priority": task.priority.name,
                        "status": task.status.value,
                        "created_at": task.created_at.isoformat(),
                    },
                }
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return {"success": False, "error": f"Failed to create task: {str(e)}"}

    def handle_task_list(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the devteam:task:list command.

        Lists all tasks or tasks matching filters.

        Args:
            request: The request data containing parameters.

        Returns:
            Response containing task list.
        """
        parameters = request.get("parameters", {})
        try:
            # Extract filter parameters
            status_filter = parameters.get("status")
            type_filter = parameters.get("type")

            # Get tasks from manager
            tasks = self._task_manager.get_tasks(
                status=TaskStatus[status_filter.upper()] if status_filter else None,
                task_type=TaskType[type_filter.upper()] if type_filter else None,
            )

            # Format tasks for response
            task_list = []
            for task in tasks:
                task_list.append(
                    {
                        "id": task.id,
                        "title": task.title,
                        "type": task.task_type.value,
                        "priority": task.priority.name,
                        "status": task.status.value,
                        "created_at": task.created_at.isoformat(),
                    }
                )

            # Sort by created_at, most recent first
            task_list.sort(key=lambda t: t["created_at"], reverse=True)

            return {"success": True, "tasks": task_list}
        except Exception as e:
            logger.error(f"Error listing tasks: {e}")
            return {"success": False, "error": f"Failed to list tasks: {str(e)}"}

    def handle_task_get(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the devteam:task:get command.

        Gets details of a specific task.

        Args:
            request: The request data containing parameters.

        Returns:
            Response containing task details.
        """
        parameters = request.get("parameters", {})
        try:
            # Extract task ID
            task_id = parameters.get("id")

            # Validate required parameters
            if not task_id:
                return {"success": False, "error": "Missing required parameter: id"}

            # Get task from manager
            task = self._task_manager.get_task(task_id)

            if not task:
                return {"success": False, "error": f"Task not found: {task_id}"}

            # Get associated workflow if any
            workflow = None
            for wf in self._workflow_engine.get_workflows():
                if wf.context.get("task_id") == task_id:
                    workflow = wf
                    break

            # Format task details
            task_details = {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "type": task.task_type.value,
                "priority": task.priority.name,
                "status": task.status.value,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                "completed_at": (
                    task.completed_at.isoformat() if task.completed_at else None
                ),
                "metadata": task.metadata,
            }

            # Add workflow details if available
            if workflow:
                task_details["workflow"] = {
                    "id": workflow.id,
                    "status": workflow.status.value,
                    "current_steps": [
                        {
                            "id": step_id,
                            "name": workflow.steps[step_id].name,
                            "status": workflow.steps[step_id].status.value,
                        }
                        for step_id in workflow.current_step_ids
                    ],
                }

            return {"success": True, "task": task_details}
        except Exception as e:
            logger.error(f"Error getting task: {e}")
            return {"success": False, "error": f"Failed to get task details: {str(e)}"}

    def handle_task_cancel(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the devteam:task:cancel command.

        Cancels a task and its associated workflow.

        Args:
            request: The request data containing parameters.

        Returns:
            Response indicating success or failure.
        """
        parameters = request.get("parameters", {})
        try:
            # Extract task ID
            task_id = parameters.get("id")

            # Validate required parameters
            if not task_id:
                return {"success": False, "error": "Missing required parameter: id"}

            # Get task from manager
            task = self._task_manager.get_task(task_id)

            if not task:
                return {"success": False, "error": f"Task not found: {task_id}"}

            # Cancel task
            self._task_manager.cancel_task(task_id)

            # Cancel associated workflow if any
            workflow_cancelled = False
            for wf in self._workflow_engine.get_workflows():
                if wf.context.get("task_id") == task_id:
                    self._workflow_engine.cancel_workflow(wf.id)
                    workflow_cancelled = True
                    break

            return {
                "success": True,
                "message": f"Task {task_id} cancelled"
                + (" and workflow cancelled" if workflow_cancelled else ""),
            }
        except Exception as e:
            logger.error(f"Error cancelling task: {e}")
            return {"success": False, "error": f"Failed to cancel task: {str(e)}"}

    def handle_workflow_status(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the devteam:workflow:status command.

        Gets the status of a workflow.

        Args:
            request: The request data containing parameters.

        Returns:
            Response containing workflow details.
        """
        parameters = request.get("parameters", {})
        try:
            # Extract workflow ID
            workflow_id = parameters.get("id")

            # Validate required parameters
            if not workflow_id:
                return {"success": False, "error": "Missing required parameter: id"}

            # Get workflow
            workflow = self._workflow_engine.get_workflow(workflow_id)

            if not workflow:
                return {"success": False, "error": f"Workflow not found: {workflow_id}"}

            # Get step details
            steps = []
            for step_id, step in workflow.steps.items():
                steps.append(
                    {
                        "id": step_id,
                        "name": step.name,
                        "status": step.status.value,
                        "is_current": step_id in workflow.current_step_ids,
                        "started_at": (
                            step.started_at.isoformat() if step.started_at else None
                        ),
                        "completed_at": (
                            step.completed_at.isoformat() if step.completed_at else None
                        ),
                    }
                )

            # Sort steps by ID (which should be sequential)
            steps.sort(key=lambda s: s["id"])

            # Get associated task if any
            task_id = workflow.context.get("task_id")
            task = None
            if task_id:
                task = self._task_manager.get_task(task_id)

            # Workflow details
            workflow_details = {
                "id": workflow.id,
                "status": workflow.status.value,
                "created_at": workflow.created_at.isoformat(),
                "updated_at": (
                    workflow.updated_at.isoformat() if workflow.updated_at else None
                ),
                "completed_at": (
                    workflow.completed_at.isoformat() if workflow.completed_at else None
                ),
                "current_step_ids": list(workflow.current_step_ids),
                "steps": steps,
            }

            # Add task details if available
            if task:
                workflow_details["task"] = {
                    "id": task.id,
                    "title": task.title,
                    "status": task.status.value,
                }

            return {"success": True, "workflow": workflow_details}
        except Exception as e:
            logger.error(f"Error getting workflow status: {e}")
            return {
                "success": False,
                "error": f"Failed to get workflow status: {str(e)}",
            }

    def handle_workflow_cancel(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the devteam:workflow:cancel command.

        Cancels a workflow.

        Args:
            request: The request data containing parameters.

        Returns:
            Response indicating success or failure.
        """
        parameters = request.get("parameters", {})
        try:
            # Extract workflow ID
            workflow_id = parameters.get("id")

            # Validate required parameters
            if not workflow_id:
                return {"success": False, "error": "Missing required parameter: id"}

            # Get workflow
            workflow = self._workflow_engine.get_workflow(workflow_id)

            if not workflow:
                return {"success": False, "error": f"Workflow not found: {workflow_id}"}

            # Cancel workflow
            self._workflow_engine.cancel_workflow(workflow_id)

            # Update associated task status if any
            task_id = workflow.context.get("task_id")
            if task_id:
                task = self._task_manager.get_task(task_id)
                if task and task.status not in [
                    TaskStatus.COMPLETED,
                    TaskStatus.FAILED,
                    TaskStatus.CANCELLED,
                ]:
                    self._task_manager.cancel_task(task_id)

            return {"success": True, "message": f"Workflow {workflow_id} cancelled"}
        except Exception as e:
            logger.error(f"Error cancelling workflow: {e}")
            return {"success": False, "error": f"Failed to cancel workflow: {str(e)}"}

    def handle_agent_list(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the devteam:agent:list command.

        Lists all agents in the registry.

        Args:
            request: The request data containing parameters.

        Returns:
            Response containing agent list.
        """
        try:
            # Get agents from registry
            agents = self._agent_registry.get_agents()

            # Format agents for response
            agent_list = []
            for agent_id, agent in agents.items():
                agent_list.append(
                    {
                        "id": agent_id,
                        "name": agent.name,
                        "role": agent.role,
                        "description": agent.description,
                    }
                )

            return {"success": True, "agents": agent_list}
        except Exception as e:
            logger.error(f"Error listing agents: {e}")
            return {"success": False, "error": f"Failed to list agents: {str(e)}"}

    def handle_prompt_metrics(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the devteam:prompt:metrics command.

        Gets prompt metrics from the adaptive learning system.

        Args:
            request: The request data containing parameters.

        Returns:
            Response containing prompt metrics.
        """
        parameters = request.get("parameters", {})
        try:
            # Extract arguments
            agent_type = parameters.get("agent_type")
            days = int(parameters.get("days", 7))

            # Validate required parameters
            if not agent_type:
                # Get metrics for all agent types
                metrics = {}
                for agent_type in ["project_manager", "developer", "qa_tester"]:
                    agent_metrics = self._adaptive_learning.get_prompt_metrics(
                        agent_type, days
                    )
                    if agent_metrics:
                        metrics[agent_type] = agent_metrics
            else:
                # Get metrics for specific agent type
                metrics = {
                    agent_type: self._adaptive_learning.get_prompt_metrics(
                        agent_type, days
                    )
                }

            return {"success": True, "metrics": metrics}
        except Exception as e:
            logger.error(f"Failed to get prompt metrics: {e}")
            return {
                "success": False,
                "error": f"Failed to get prompt metrics: {str(e)}",
            }

    def handle_prompt_experiment(self, request: Dict[str, Any]) -> Dict[str, Any]:
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
            logger.error(f"Failed to start prompt experiment: {e}")
            error_msg = (
                f"Invalid parameter: {str(e)}"
                if isinstance(e, ValueError)
                else f"Failed to start prompt experiment: {str(e)}"
            )
            return {"success": False, "error": error_msg}

    async def execute_workflow_step(
        self, step: WorkflowStep, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a workflow step using the appropriate agent.

        Args:
            step: The workflow step to execute
            context: The workflow context

        Returns:
            Step execution result
        """
        try:
            # Extract task ID from context if available
            task_id = context.get("task_id")
            task = None
            if task_id:
                task = self._task_manager.get_task(task_id)

            # Get step agent type
            agent_type = getattr(step, "agent_type", "developer")

            # Get agent from registry
            agent = self._agent_registry.get_agent(agent_type)
            if not agent:
                raise ValueError(f"Agent not found for type: {agent_type}")

            # Execute step using agent
            result = await agent.execute_step(step, context, task)
            if isinstance(result, dict):
                return result
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error executing workflow step: {e}")
            return {
                "success": False,
                "error": f"Failed to execute workflow step: {str(e)}",
            }
