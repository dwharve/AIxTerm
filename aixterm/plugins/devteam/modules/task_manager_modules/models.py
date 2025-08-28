"""
Task data model for the DevTeam plugin.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from ..types import TaskId, TaskPriority, TaskStatus, TaskType


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
            status: New status
        """
        old_status = self.status
        self.status = status
        self.updated_at = datetime.now().isoformat()

        # Update timestamps based on status
        if status == TaskStatus.IN_PROGRESS and old_status == TaskStatus.PENDING:
            self.started_at = self.updated_at
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            self.completed_at = self.updated_at

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
        Add a task dependency.

        Args:
            dependency_id: ID of the task this task depends on
        """
        self.dependencies.add(dependency_id)
        self.updated_at = datetime.now().isoformat()

    def add_blocker(self, blocker_id: TaskId) -> None:
        """
        Add a blocker task.

        Args:
            blocker_id: ID of the task blocking this one
        """
        self.blockers.add(blocker_id)
        self.updated_at = datetime.now().isoformat()

    def remove_blocker(self, blocker_id: TaskId) -> bool:
        """
        Remove a blocker task.

        Args:
            blocker_id: ID of the blocker task to remove

        Returns:
            True if the blocker was removed, False if it wasn't present
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
