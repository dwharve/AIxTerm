"""
Task management orchestration and control logic.
"""

import logging
from typing import Any, Dict, Optional

from .models import Task
from ..config import ConfigManager
from ..events import EventBus, EventType, TaskEvent
from ..types import TaskId, TaskPriority, TaskStatus, TaskType

logger = logging.getLogger(__name__)


class TaskManager:
    """Manager for DevTeam tasks."""

    def __init__(self, config_manager: ConfigManager, event_bus: EventBus):
        """
        Initialize the task manager.

        Args:
            config_manager: Configuration manager
            event_bus: Event bus for publishing events
        """
        self.config_manager = config_manager
        self.event_bus = event_bus
        self.tasks: Dict[TaskId, Task] = {}
        self._shutdown_event = None  # Added for test compatibility

    def create_task(
        self,
        title: str,
        description: str,
        task_type: TaskType = TaskType.FEATURE,
        priority: TaskPriority = TaskPriority.MEDIUM,
        parent_id: Optional[TaskId] = None,
        metadata: Optional[Dict[str, Any]] = None,
        assignee: Optional[str] = None,
    ) -> Task:
        """
        Create a new task.

        Args:
            title: Task title
            description: Task description
            task_type: Type of task (default: DEVELOPMENT)
            priority: Task priority (default: MEDIUM)
            parent_id: Parent task ID if this is a subtask
            metadata: Additional task metadata
            assignee: Name of the assigned agent (if any)

        Returns:
            The created task.
        """
        task = Task(
            title=title,
            description=description,
            task_type=task_type,
            priority=priority,
            parent_id=parent_id,
            metadata=metadata,
            assignee=assignee,
        )

        self.tasks[task.task_id] = task

        # Add to parent task if specified
        if parent_id and parent_id in self.tasks:
            self.tasks[parent_id].add_subtask(task.task_id)

        # Publish task created event
        self._publish_task_event(
            event_type=EventType.TASK_CREATED,
            task_id=task.task_id,
            data={"task": task.to_dict()},
        )

        return task

    def get_task(self, task_id: TaskId) -> Optional[Task]:
        """
        Get a task by ID.

        Args:
            task_id: ID of the task to get

        Returns:
            The task or None if not found.
        """
        return self.tasks.get(task_id)

    def update_task_status(
        self, task_id: TaskId, status: TaskStatus, note: Optional[str] = None
    ) -> Optional[Task]:
        """
        Update a task's status.

        Args:
            task_id: ID of the task to update
            status: New status
            note: Optional note to add

        Returns:
            The updated task or None if not found.
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        old_status = task.status
        task.update_status(status)

        if note:
            task.add_note(note, "system")

        # Determine event type
        event_type = EventType.TASK_UPDATED
        if status == TaskStatus.COMPLETED:
            event_type = EventType.TASK_COMPLETED
        elif status == TaskStatus.FAILED:
            event_type = EventType.TASK_FAILED
        elif status == TaskStatus.CANCELLED:
            event_type = EventType.TASK_CANCELLED

        # Publish task status event
        self._publish_task_event(
            event_type=event_type,
            task_id=task_id,
            data={
                "task": task.to_dict(),
                "old_status": old_status.value,
                "new_status": status.value,
            },
        )

        return task

    def assign_task(self, task_id: TaskId, assignee: str) -> Optional[Task]:
        """
        Assign a task to an agent.

        Args:
            task_id: ID of the task to assign
            assignee: Name of the agent

        Returns:
            The updated task or None if not found.
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        old_assignee = task.assignee
        task.assign(assignee)

        # Publish task assigned event
        self._publish_task_event(
            event_type=EventType.TASK_ASSIGNED,
            task_id=task_id,
            data={
                "task": task.to_dict(),
                "old_assignee": old_assignee,
                "new_assignee": assignee,
            },
        )

        return task

    def add_task_dependency(self, task_id: TaskId, dependency_id: TaskId) -> bool:
        """
        Add a dependency between tasks.

        Args:
            task_id: ID of the task that depends on another
            dependency_id: ID of the task that is depended upon

        Returns:
            True if the dependency was added successfully, False otherwise.
        """
        task = self.tasks.get(task_id)
        dependency_task = self.tasks.get(dependency_id)

        if not task or not dependency_task:
            return False

        task.add_dependency(dependency_id)

        # Publish task dependency added event
        self._publish_task_event(
            event_type=EventType.TASK_UPDATED,
            task_id=task_id,
            data={
                "task": task.to_dict(),
                "dependency_added": dependency_id,
            },
        )

        return True

    def add_task_blocker(self, task_id: TaskId, blocker_id: TaskId) -> bool:
        """
        Add a blocker to a task.

        Args:
            task_id: ID of the task being blocked
            blocker_id: ID of the task causing the block

        Returns:
            True if the blocker was added successfully, False otherwise.
        """
        task = self.tasks.get(task_id)
        blocker_task = self.tasks.get(blocker_id)

        if not task or not blocker_task:
            return False

        task.add_blocker(blocker_id)

        # Publish task blocker added event
        self._publish_task_event(
            event_type=EventType.TASK_UPDATED,
            task_id=task_id,
            data={
                "task": task.to_dict(),
                "blocker_added": blocker_id,
            },
        )

        return True

    def remove_task_blocker(self, task_id: TaskId, blocker_id: TaskId) -> bool:
        """
        Remove a blocker from a task.

        Args:
            task_id: ID of the task
            blocker_id: ID of the blocker to remove

        Returns:
            True if the blocker was removed, False otherwise.
        """
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.remove_blocker(blocker_id):
            # Publish task blocker removed event
            self._publish_task_event(
                event_type=EventType.TASK_UPDATED,
                task_id=task_id,
                data={
                    "task": task.to_dict(),
                    "blocker_removed": blocker_id,
                },
            )
            return True

        return False

    def add_task_note(
        self, task_id: TaskId, note: str, author: str = "system"
    ) -> Optional[Task]:
        """
        Add a note to a task.

        Args:
            task_id: ID of the task
            note: Note content
            author: Author of the note (default: "system")

        Returns:
            The updated task or None if not found.
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        task.add_note(note, author)

        # Publish task note added event
        self._publish_task_event(
            event_type=EventType.TASK_UPDATED,
            task_id=task_id,
            data={
                "task": task.to_dict(),
                "note_added": {"content": note, "author": author},
            },
        )

        return task

    def add_task_artifact(
        self, task_id: TaskId, artifact_name: str, artifact_data: Any
    ) -> Optional[Task]:
        """
        Add an artifact to a task.

        Args:
            task_id: ID of the task
            artifact_name: Name of the artifact
            artifact_data: Artifact data

        Returns:
            The updated task or None if not found.
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        task.add_artifact(artifact_name, artifact_data)

        # Publish task artifact added event
        self._publish_task_event(
            event_type=EventType.TASK_UPDATED,
            task_id=task_id,
            data={
                "task": task.to_dict(),
                "artifact_added": {"name": artifact_name, "data": artifact_data},
            },
        )

        return task

    def get_all_tasks(self) -> Dict[TaskId, Task]:
        """
        Get all tasks.

        Returns:
            Dictionary of all tasks.
        """
        return self.tasks.copy()

    def get_tasks_by_status(self, status: TaskStatus) -> Dict[TaskId, Task]:
        """
        Get tasks by status.

        Args:
            status: Task status to filter by

        Returns:
            Dictionary of tasks with the specified status.
        """
        return {
            task_id: task
            for task_id, task in self.tasks.items()
            if task.status == status
        }

    def get_tasks_by_type(self, task_type: TaskType) -> Dict[TaskId, Task]:
        """
        Get tasks by type.

        Args:
            task_type: Task type to filter by

        Returns:
            Dictionary of tasks with the specified type.
        """
        return {
            task_id: task
            for task_id, task in self.tasks.items()
            if task.task_type == task_type
        }

    def get_tasks_by_assignee(self, assignee: str) -> Dict[TaskId, Task]:
        """
        Get tasks assigned to a specific agent.

        Args:
            assignee: Name of the assigned agent

        Returns:
            Dictionary of tasks assigned to the specified agent.
        """
        return {
            task_id: task
            for task_id, task in self.tasks.items()
            if task.assignee == assignee
        }

    def get_subtasks(self, parent_id: TaskId) -> Dict[TaskId, Task]:
        """
        Get subtasks of a parent task.

        Args:
            parent_id: ID of the parent task

        Returns:
            Dictionary of subtasks.
        """
        parent_task = self.tasks.get(parent_id)
        if not parent_task:
            return {}

        return {
            task_id: task
            for task_id, task in self.tasks.items()
            if task_id in parent_task.subtasks
        }

    def delete_task(self, task_id: TaskId) -> bool:
        """
        Delete a task.

        Args:
            task_id: ID of the task to delete

        Returns:
            True if the task was deleted, False if not found.
        """
        task = self.tasks.get(task_id)
        if not task:
            return False

        # Remove from parent task if it's a subtask
        if task.parent_id and task.parent_id in self.tasks:
            parent_task = self.tasks[task.parent_id]
            parent_task.subtasks.discard(task_id)

        # Remove the task
        del self.tasks[task_id]

        # Publish task deleted event
        self._publish_task_event(
            event_type=EventType.TASK_DELETED,
            task_id=task_id,
            data={"task": task.to_dict()},
        )

        return True

    def _publish_task_event(
        self, event_type: EventType, task_id: TaskId, data: Dict[str, Any]
    ) -> None:
        """
        Publish a task event.

        Args:
            event_type: Type of event
            task_id: ID of the task
            data: Event data
        """
        event = TaskEvent(event_type=event_type, task_id=task_id, data=data)
        self.event_bus.publish(event)