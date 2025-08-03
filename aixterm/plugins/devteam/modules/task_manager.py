"""
Task management system for the DevTeam plugin.

This module provides task creation, tracking, and management.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from .config import ConfigManager
from .events import Event, EventBus, EventType, TaskEvent
from .types import TaskId, TaskPriority, TaskStatus, TaskType

logger = logging.getLogger(__name__)


class Task:
    """Represents a DevTeam task."""

    def __init__(
        self,
        title: str,
        description: str,
        task_type: TaskType = TaskType.FEATURE,
        priority: TaskPriority = TaskPriority.MEDIUM,
        task_id: Optional[TaskId] = None,
        parent_id: Optional[TaskId] = None,
        metadata: Optional[Dict[str, Any]] = None,
        assignee: Optional[str] = None,
    ):
        """
        Initialize a task.

        Args:
            title: Task title
            description: Task description
            task_type: Type of task (default: DEVELOPMENT)
            priority: Task priority (default: MEDIUM)
            task_id: Unique task ID (auto-generated if not provided)
            parent_id: Parent task ID if this is a subtask
            metadata: Additional task metadata
            assignee: Name of the assigned agent (if any)
        """
        self.task_id = task_id or str(uuid.uuid4())
        self.title = title
        self.description = description
        self.task_type = task_type
        self.priority = priority
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.parent_id = parent_id
        self.metadata = metadata or {}
        self.assignee = assignee
        self.subtasks: Set[TaskId] = set()
        self.artifacts: Dict[str, Any] = {}
        self.dependencies: Set[TaskId] = set()
        self.blockers: Set[TaskId] = set()
        self.notes: List[Dict[str, str]] = []

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert task to a dictionary.

        Returns:
            Dictionary representation of the task.
        """
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
            "assignee": self.assignee,
            "subtasks": list(self.subtasks),
            "artifacts": self.artifacts,
            "dependencies": list(self.dependencies),
            "blockers": list(self.blockers),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, task_dict: Dict[str, Any]) -> "Task":
        """
        Create a task from a dictionary.

        Args:
            task_dict: Dictionary containing task data

        Returns:
            Task object.
        """
        task = cls(
            title=task_dict["title"],
            description=task_dict["description"],
            task_type=TaskType(task_dict["task_type"]),
            priority=TaskPriority(task_dict["priority"]),
            task_id=task_dict["task_id"],
            parent_id=task_dict.get("parent_id"),
            metadata=task_dict.get("metadata", {}),
            assignee=task_dict.get("assignee"),
        )

        task.status = TaskStatus(task_dict["status"])
        task.created_at = task_dict["created_at"]
        task.updated_at = task_dict["updated_at"]
        task.started_at = task_dict.get("started_at")
        task.completed_at = task_dict.get("completed_at")
        task.subtasks = set(task_dict.get("subtasks", []))
        task.artifacts = task_dict.get("artifacts", {})
        task.dependencies = set(task_dict.get("dependencies", []))
        task.blockers = set(task_dict.get("blockers", []))
        task.notes = task_dict.get("notes", [])

        return task

    def update_status(self, status: TaskStatus) -> None:
        """
        Update the task status and timestamps.

        Args:
            status: New status for the task
        """
        now = datetime.now().isoformat()
        self.updated_at = now

        if status == TaskStatus.IN_PROGRESS and not self.started_at:
            self.started_at = now
        elif (
            status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
            and not self.completed_at
        ):
            self.completed_at = now

        self.status = status

    def add_subtask(self, subtask_id: TaskId) -> None:
        """
        Add a subtask to this task.

        Args:
            subtask_id: ID of the subtask
        """
        self.subtasks.add(subtask_id)
        self.updated_at = datetime.now().isoformat()

    def add_dependency(self, dependency_id: TaskId) -> None:
        """
        Add a dependency to this task.

        Args:
            dependency_id: ID of the dependency
        """
        self.dependencies.add(dependency_id)
        self.updated_at = datetime.now().isoformat()

    def add_blocker(self, blocker_id: TaskId) -> None:
        """
        Add a blocker to this task.

        Args:
            blocker_id: ID of the blocking task
        """
        self.blockers.add(blocker_id)
        self.updated_at = datetime.now().isoformat()

    def remove_blocker(self, blocker_id: TaskId) -> bool:
        """
        Remove a blocker from this task.

        Args:
            blocker_id: ID of the blocking task

        Returns:
            True if the blocker was removed, False otherwise
        """
        if blocker_id in self.blockers:
            self.blockers.remove(blocker_id)
            self.updated_at = datetime.now().isoformat()
            return True
        return False

    def assign(self, assignee: str) -> None:
        """
        Assign the task to an agent.

        Args:
            assignee: Name of the agent
        """
        self.assignee = assignee
        self.updated_at = datetime.now().isoformat()

    def add_note(self, note: str, author: str = "system") -> None:
        """
        Add a note to the task.

        Args:
            note: Note content
            author: Author of the note (default: "system")
        """
        self.notes.append(
            {"content": note, "author": author, "timestamp": datetime.now().isoformat()}
        )
        self.updated_at = datetime.now().isoformat()

    def add_artifact(self, artifact_name: str, artifact_data: Any) -> None:
        """
        Add an artifact to the task.

        Args:
            artifact_name: Name of the artifact
            artifact_data: Artifact data
        """
        self.artifacts[artifact_name] = artifact_data
        self.updated_at = datetime.now().isoformat()


class TaskManager:
    """Manager for DevTeam tasks."""

    def __init__(self, config_manager: ConfigManager, event_bus: EventBus):
        """
        Initialize the task manager.

        Args:
            config_manager: Configuration manager
            event_bus: Event bus for publishing events
        """
        self.config = config_manager
        self.event_bus = event_bus
        self.tasks: Dict[TaskId, Task] = {}

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

        # If this is a subtask, update the parent
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
            Task object if found, None otherwise.
        """
        return self.tasks.get(task_id)

    def update_task_status(
        self, task_id: TaskId, status: TaskStatus, note: Optional[str] = None
    ) -> Optional[Task]:
        """
        Update the status of a task.

        Args:
            task_id: ID of the task to update
            status: New status for the task
            note: Optional note to add to the task

        Returns:
            Updated task if found, None otherwise.
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        old_status = task.status
        task.update_status(status)

        if note:
            task.add_note(note)

        # Determine the event type based on the status
        event_type = EventType.TASK_UPDATED
        if status == TaskStatus.IN_PROGRESS and old_status != TaskStatus.IN_PROGRESS:
            event_type = EventType.TASK_STARTED
        elif status == TaskStatus.COMPLETED:
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
            Updated task if found, None otherwise.
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        old_assignee = task.assignee
        task.assign(assignee)

        # Publish task assigned event
        self._publish_task_event(
            event_type=EventType.AGENT_TASK_ASSIGNED,
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
        Add a dependency to a task.

        Args:
            task_id: ID of the task to update
            dependency_id: ID of the dependency

        Returns:
            True if successful, False otherwise.
        """
        task = self.tasks.get(task_id)
        dependency = self.tasks.get(dependency_id)

        if not task or not dependency:
            return False

        task.add_dependency(dependency_id)

        # Publish task updated event
        self._publish_task_event(
            event_type=EventType.TASK_UPDATED,
            task_id=task_id,
            data={"task": task.to_dict(), "dependency_added": dependency_id},
        )

        return True

    def add_task_blocker(self, task_id: TaskId, blocker_id: TaskId) -> bool:
        """
        Add a blocker to a task.

        Args:
            task_id: ID of the task to update
            blocker_id: ID of the blocking task

        Returns:
            True if successful, False otherwise.
        """
        task = self.tasks.get(task_id)
        blocker = self.tasks.get(blocker_id)

        if not task or not blocker:
            return False

        task.add_blocker(blocker_id)

        # Publish task updated event
        self._publish_task_event(
            event_type=EventType.TASK_UPDATED,
            task_id=task_id,
            data={"task": task.to_dict(), "blocker_added": blocker_id},
        )

        return True

    def remove_task_blocker(self, task_id: TaskId, blocker_id: TaskId) -> bool:
        """
        Remove a blocker from a task.

        Args:
            task_id: ID of the task to update
            blocker_id: ID of the blocking task

        Returns:
            True if successful, False otherwise.
        """
        task = self.tasks.get(task_id)

        if not task:
            return False

        if task.remove_blocker(blocker_id):
            # Publish task updated event
            self._publish_task_event(
                event_type=EventType.TASK_UPDATED,
                task_id=task_id,
                data={"task": task.to_dict(), "blocker_removed": blocker_id},
            )
            return True

        return False

    def add_task_note(
        self, task_id: TaskId, note: str, author: str = "system"
    ) -> Optional[Task]:
        """
        Add a note to a task.

        Args:
            task_id: ID of the task to update
            note: Note content
            author: Author of the note

        Returns:
            Updated task if found, None otherwise.
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        task.add_note(note, author)

        # Publish task updated event
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
            task_id: ID of the task to update
            artifact_name: Name of the artifact
            artifact_data: Artifact data

        Returns:
            Updated task if found, None otherwise.
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        task.add_artifact(artifact_name, artifact_data)

        # Publish task updated event
        self._publish_task_event(
            event_type=EventType.TASK_UPDATED,
            task_id=task_id,
            data={"task": task.to_dict(), "artifact_added": artifact_name},
        )

        return task

    def get_all_tasks(self) -> Dict[TaskId, Task]:
        """
        Get all tasks.

        Returns:
            Dictionary of all tasks.
        """
        return self.tasks

    def get_tasks_by_status(self, status: TaskStatus) -> Dict[TaskId, Task]:
        """
        Get tasks by status.

        Args:
            status: Status to filter by

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
            task_type: Type to filter by

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
        Get tasks by assignee.

        Args:
            assignee: Assignee to filter by

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
        Get subtasks of a task.

        Args:
            parent_id: ID of the parent task

        Returns:
            Dictionary of subtasks for the specified parent.
        """
        return {
            task_id: task
            for task_id, task in self.tasks.items()
            if task.parent_id == parent_id
        }

    def delete_task(self, task_id: TaskId) -> bool:
        """
        Delete a task.

        Args:
            task_id: ID of the task to delete

        Returns:
            True if the task was deleted, False otherwise.
        """
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task_data = task.to_dict()

        # Remove subtask references from parent
        if task.parent_id and task.parent_id in self.tasks:
            parent = self.tasks[task.parent_id]
            if task_id in parent.subtasks:
                parent.subtasks.remove(task_id)

        # Delete the task
        del self.tasks[task_id]

        # Publish task deleted event (using TASK_CANCELLED event type)
        self._publish_task_event(
            event_type=EventType.TASK_CANCELLED,
            task_id=task_id,
            data={"task": task_data},
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
