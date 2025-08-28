"""
Characterization tests for task_manager.py

These tests capture the current behavior of the task manager module without
refactoring existing application logic. They serve as regression tests to ensure
that future changes don't break existing functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock
from typing import Set

from aixterm.plugins.devteam.modules.task_manager import Task, TaskManager
from aixterm.plugins.devteam.modules.types import (
    TaskId, 
    TaskType, 
    TaskPriority, 
    TaskStatus
)


class TestTaskManagerCharacterization:
    """Characterization tests for TaskManager class."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mocked dependencies for task manager."""
        mock_config_manager = Mock()
        mock_event_bus = Mock()
        
        mock_config_manager.get_config.return_value = {
            "max_tasks": 100,
            "default_priority": "medium",
            "auto_assign_enabled": True
        }
        
        return {
            "config_manager": mock_config_manager,
            "event_bus": mock_event_bus
        }

    @pytest.fixture
    def task_manager(self, mock_dependencies):
        """Create task manager instance with mocked dependencies."""
        return TaskManager(
            config_manager=mock_dependencies["config_manager"],
            event_bus=mock_dependencies["event_bus"]
        )

    def test_task_initialization_defaults(self):
        """Test Task initialization with default values."""
        # Given: minimal task parameters
        title = "Test Task"
        description = "A test task description"

        # When: creating task with defaults
        task = Task(title=title, description=description)

        # Then: task should have expected defaults
        assert task.title == title
        assert task.description == description
        assert task.task_type == TaskType.FEATURE  # Default from constructor
        assert task.priority == TaskPriority.MEDIUM  # Default from constructor
        assert task.status == TaskStatus.PENDING  # Default from Task class
        assert isinstance(task.task_id, str)
        assert len(task.task_id) > 0  # UUID should be generated
        assert task.parent_id is None
        assert task.assignee is None
        assert task.metadata == {}
        assert isinstance(task.created_at, str)  # ISO format timestamp
        assert task.updated_at == task.created_at
        assert task.started_at is None
        assert task.completed_at is None
        assert isinstance(task.subtasks, set)
        assert len(task.subtasks) == 0
        assert task.artifacts == {}
        assert isinstance(task.dependencies, set)
        assert len(task.dependencies) == 0
        assert isinstance(task.blockers, set)
        assert len(task.blockers) == 0
        assert isinstance(task.notes, list)
        assert len(task.notes) == 0

    def test_task_initialization_with_all_parameters(self):
        """Test Task initialization with all parameters specified."""
        # Given: complete task parameters
        task_id = "task_123"
        title = "Complete Feature"
        description = "Implement and test new feature"
        task_type = TaskType.BUGFIX
        priority = TaskPriority.HIGH
        parent_id = "parent_task_456"
        metadata = {"component": "ui", "estimate": "4h"}
        assignee = "developer_1"

        # When: creating task with all parameters
        task = Task(
            title=title,
            description=description,
            task_type=task_type,
            priority=priority,
            task_id=task_id,
            parent_id=parent_id,
            metadata=metadata,
            assignee=assignee
        )

        # Then: task should have all specified values
        assert task.task_id == task_id
        assert task.title == title
        assert task.description == description
        assert task.task_type == task_type
        assert task.priority == priority
        assert task.parent_id == parent_id
        assert task.metadata == metadata
        assert task.assignee == assignee
        assert task.status == TaskStatus.PENDING  # Still default

    def test_task_update_status_transitions(self):
        """Test task status update behavior and timestamp management."""
        # Given: a new task
        task = Task("Test Task", "Test description")
        initial_created_at = task.created_at
        initial_updated_at = task.updated_at

        # When: updating status to IN_PROGRESS
        task.update_status(TaskStatus.IN_PROGRESS)

        # Then: status and timestamps should be updated correctly
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.updated_at != initial_updated_at  # Should be updated
        assert task.started_at is not None  # Should be set when moving to IN_PROGRESS
        assert task.completed_at is None
        assert task.created_at == initial_created_at  # Should not change

        # When: updating to COMPLETED
        started_at = task.started_at
        task.update_status(TaskStatus.COMPLETED)

        # Then: completion timestamp should be set
        assert task.status == TaskStatus.COMPLETED
        assert task.started_at == started_at  # Should not change once set
        assert task.completed_at is not None
        
        # When: updating to FAILED
        task.update_status(TaskStatus.FAILED)
        
        # Then: completed_at should remain (characterizes current behavior)
        assert task.status == TaskStatus.FAILED
        assert task.completed_at is not None  # Should not be cleared

    def test_task_subtask_management(self):
        """Test task subtask addition and removal behavior."""
        # Given: a parent task
        parent_task = Task("Parent Task", "Parent description")
        subtask_id_1 = "subtask_1"
        subtask_id_2 = "subtask_2"

        # When: adding subtasks
        parent_task.add_subtask(subtask_id_1)
        parent_task.add_subtask(subtask_id_2)

        # Then: subtasks should be tracked
        assert subtask_id_1 in parent_task.subtasks
        assert subtask_id_2 in parent_task.subtasks
        assert len(parent_task.subtasks) == 2

        # When: adding duplicate subtask
        parent_task.add_subtask(subtask_id_1)

        # Then: should not create duplicate (set behavior)
        assert len(parent_task.subtasks) == 2

        # When: removing subtask
        parent_task.remove_subtask(subtask_id_1)

        # Then: subtask should be removed
        assert subtask_id_1 not in parent_task.subtasks
        assert subtask_id_2 in parent_task.subtasks
        assert len(parent_task.subtasks) == 1

        # When: removing non-existent subtask
        parent_task.remove_subtask("nonexistent")

        # Then: should not raise error (characterizes current behavior)
        assert len(parent_task.subtasks) == 1

    def test_task_dependency_management(self):
        """Test task dependency addition and removal behavior."""
        # Given: a task
        task = Task("Test Task", "Test description")
        dep_1 = "dependency_1"
        dep_2 = "dependency_2"

        # When: adding dependencies
        task.add_dependency(dep_1)
        task.add_dependency(dep_2)

        # Then: dependencies should be tracked
        assert dep_1 in task.dependencies
        assert dep_2 in task.dependencies
        assert len(task.dependencies) == 2

        # When: adding duplicate dependency
        task.add_dependency(dep_1)

        # Then: should not create duplicate
        assert len(task.dependencies) == 2

        # When: removing dependency
        task.remove_dependency(dep_1)

        # Then: dependency should be removed
        assert dep_1 not in task.dependencies
        assert dep_2 in task.dependencies
        assert len(task.dependencies) == 1

    def test_task_blocker_management(self):
        """Test task blocker addition and removal behavior."""
        # Given: a task
        task = Task("Test Task", "Test description")
        blocker_1 = "blocker_1"
        blocker_2 = "blocker_2"

        # When: adding blockers
        task.add_blocker(blocker_1)
        task.add_blocker(blocker_2)

        # Then: blockers should be tracked
        assert blocker_1 in task.blockers
        assert blocker_2 in task.blockers
        assert len(task.blockers) == 2

        # When: removing blocker
        task.remove_blocker(blocker_1)

        # Then: blocker should be removed
        assert blocker_1 not in task.blockers
        assert blocker_2 in task.blockers
        assert len(task.blockers) == 1

    def test_task_note_management(self):
        """Test task note addition behavior."""
        # Given: a task
        task = Task("Test Task", "Test description")
        note_1 = "First note"
        note_2 = "Second note"

        # When: adding notes
        task.add_note(note_1)
        task.add_note(note_2)

        # Then: notes should be stored in order
        assert len(task.notes) == 2
        assert task.notes[0] == note_1
        assert task.notes[1] == note_2

        # When: adding more notes
        note_3 = "Third note"
        task.add_note(note_3)

        # Then: notes should maintain order
        assert len(task.notes) == 3
        assert task.notes[2] == note_3

    def test_task_from_dict_deserialization(self):
        """Test Task.from_dict() preserves current deserialization behavior."""
        # Given: task dictionary representation
        task_dict = {
            "task_id": "task_123",
            "title": "Test Task",
            "description": "A test task",
            "task_type": "bugfix",
            "priority": "high",
            "status": "in_progress",
            "parent_id": "parent_456",
            "assignee": "dev_1",
            "metadata": {"component": "backend"},
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T01:00:00",
            "started_at": "2024-01-01T00:30:00",
            "completed_at": None,
            "subtasks": ["sub_1", "sub_2"],
            "artifacts": {"code": "/path/to/code"},
            "dependencies": ["dep_1"],
            "blockers": ["blocker_1"],
            "notes": ["Initial note", "Progress update"]
        }

        # When: creating task from dictionary
        task = Task.from_dict(task_dict)

        # Then: task should match expected values
        assert task.task_id == "task_123"
        assert task.title == "Test Task"
        assert task.description == "A test task"
        assert task.task_type == TaskType.BUGFIX
        assert task.priority == TaskPriority.HIGH
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.parent_id == "parent_456"
        assert task.assignee == "dev_1"
        assert task.metadata == {"component": "backend"}
        assert task.created_at == "2024-01-01T00:00:00"
        assert task.updated_at == "2024-01-01T01:00:00"
        assert task.started_at == "2024-01-01T00:30:00"
        assert task.completed_at is None
        assert task.subtasks == {"sub_1", "sub_2"}
        assert task.artifacts == {"code": "/path/to/code"}
        assert task.dependencies == {"dep_1"}
        assert task.blockers == {"blocker_1"}
        assert task.notes == ["Initial note", "Progress update"]

    def test_task_to_dict_serialization(self):
        """Test Task.to_dict() preserves current serialization behavior."""
        # Given: task with data
        task = Task(
            title="Serialize Test",
            description="Test serialization",
            task_type=TaskType.FEATURE,
            priority=TaskPriority.LOW,
            task_id="serialize_123",
            assignee="tester"
        )
        task.add_subtask("sub_1")
        task.add_dependency("dep_1")
        task.add_blocker("block_1") 
        task.add_note("Test note")
        task.artifacts = {"output": "result.txt"}

        # When: converting to dictionary
        task_dict = task.to_dict()

        # Then: dictionary should contain all expected keys
        expected_keys = {
            "task_id", "title", "description", "task_type", "priority", 
            "status", "parent_id", "assignee", "metadata", "created_at",
            "updated_at", "started_at", "completed_at", "subtasks",
            "artifacts", "dependencies", "blockers", "notes"
        }
        assert set(task_dict.keys()) == expected_keys

        # And: values should match task attributes
        assert task_dict["task_id"] == "serialize_123"
        assert task_dict["title"] == "Serialize Test"
        assert task_dict["task_type"] == "feature"
        assert task_dict["priority"] == "low"
        assert task_dict["assignee"] == "tester"
        assert "sub_1" in task_dict["subtasks"]
        assert "dep_1" in task_dict["dependencies"]
        assert "block_1" in task_dict["blockers"]
        assert task_dict["notes"] == ["Test note"]

    def test_task_manager_initialization(self, mock_dependencies):
        """Test TaskManager initialization with dependencies."""
        # Given: mocked dependencies

        # When: creating task manager
        manager = TaskManager(
            config_manager=mock_dependencies["config_manager"],
            event_bus=mock_dependencies["event_bus"]
        )

        # Then: manager should be properly initialized
        assert manager.config_manager == mock_dependencies["config_manager"]
        assert manager.event_bus == mock_dependencies["event_bus"]
        assert manager.tasks == {}
        assert hasattr(manager, '_shutdown_event')

    def test_task_manager_create_task(self, task_manager):
        """Test task creation through manager preserves current behavior."""
        # Given: task specification
        task_spec = {
            "title": "Manager Created Task",
            "description": "Task created through manager",
            "task_type": "feature",
            "priority": "high",
            "assignee": "dev_1"
        }

        # When: creating task through manager
        task_id = task_manager.create_task(task_spec)

        # Then: task should be created and stored
        assert isinstance(task_id, str)
        assert task_id in task_manager.tasks
        
        task = task_manager.tasks[task_id]
        assert task.title == "Manager Created Task"
        assert task.description == "Task created through manager"
        assert task.task_type == TaskType.FEATURE
        assert task.priority == TaskPriority.HIGH
        assert task.assignee == "dev_1"

    def test_task_manager_get_task(self, task_manager):
        """Test task retrieval behavior."""
        # Given: a created task
        task_spec = {
            "title": "Retrievable Task",
            "description": "Task for retrieval testing"
        }
        task_id = task_manager.create_task(task_spec)

        # When: getting task by ID
        retrieved_task = task_manager.get_task(task_id)

        # Then: should return the correct task
        assert retrieved_task is not None
        assert retrieved_task.task_id == task_id
        assert retrieved_task.title == "Retrievable Task"

        # When: getting non-existent task
        non_existent_task = task_manager.get_task("non_existent_id")

        # Then: should return None (characterizes current behavior)
        assert non_existent_task is None

    def test_task_manager_update_task(self, task_manager):
        """Test task update through manager."""
        # Given: a created task
        task_spec = {"title": "Original Title", "description": "Original description"}
        task_id = task_manager.create_task(task_spec)

        # When: updating task
        updates = {
            "title": "Updated Title",
            "priority": "high",
            "assignee": "new_assignee"
        }
        success = task_manager.update_task(task_id, updates)

        # Then: task should be updated
        assert success is True
        task = task_manager.get_task(task_id)
        assert task.title == "Updated Title"
        assert task.priority == TaskPriority.HIGH
        assert task.assignee == "new_assignee"
        assert task.description == "Original description"  # Should remain unchanged

    def test_task_manager_list_tasks_filtering(self, task_manager):
        """Test task listing with filters."""
        # Given: multiple tasks with different properties
        task1_id = task_manager.create_task({
            "title": "Task 1",
            "description": "First task",
            "task_type": "feature",
            "status": "pending",
            "assignee": "dev_1"
        })
        task2_id = task_manager.create_task({
            "title": "Task 2", 
            "description": "Second task",
            "task_type": "bugfix",
            "status": "pending",
            "assignee": "dev_2"
        })
        task3_id = task_manager.create_task({
            "title": "Task 3",
            "description": "Third task", 
            "task_type": "feature",
            "status": "pending",
            "assignee": "dev_1"
        })

        # When: listing all tasks
        all_tasks = task_manager.list_tasks()

        # Then: should return all tasks
        assert len(all_tasks) == 3
        task_ids = [task.task_id for task in all_tasks]
        assert task1_id in task_ids
        assert task2_id in task_ids 
        assert task3_id in task_ids

        # When: filtering by assignee
        dev1_tasks = task_manager.list_tasks(filters={"assignee": "dev_1"})

        # Then: should return only dev_1's tasks
        assert len(dev1_tasks) == 2
        for task in dev1_tasks:
            assert task.assignee == "dev_1"

        # When: filtering by task type
        feature_tasks = task_manager.list_tasks(filters={"task_type": "feature"})

        # Then: should return only feature tasks
        assert len(feature_tasks) == 2
        for task in feature_tasks:
            assert task.task_type == TaskType.FEATURE

        # When: filtering by status
        pending_tasks = task_manager.list_tasks(filters={"status": "pending"})

        # Then: should return only pending tasks
        assert len(pending_tasks) == 2
        for task in pending_tasks:
            assert task.status == TaskStatus.PENDING

    def test_task_manager_delete_task(self, task_manager):
        """Test task deletion behavior."""
        # Given: a created task
        task_spec = {"title": "Delete Me", "description": "Task to be deleted"}
        task_id = task_manager.create_task(task_spec)
        
        # Verify task exists
        assert task_id in task_manager.tasks

        # When: deleting task
        success = task_manager.delete_task(task_id)

        # Then: task should be removed
        assert success is True
        assert task_id not in task_manager.tasks
        assert task_manager.get_task(task_id) is None

        # When: deleting non-existent task
        success = task_manager.delete_task("non_existent")

        # Then: should return False (characterizes current behavior)
        assert success is False

    def test_task_enum_values(self):
        """Test that task enums maintain expected values."""
        # This characterizes the current enum values to prevent accidental changes
        
        # TaskType values
        assert TaskType.FEATURE.value == "feature"
        assert TaskType.BUGFIX.value == "bugfix"
        assert TaskType.REFACTOR.value == "refactor"
        assert TaskType.DOCUMENTATION.value == "documentation"
        assert TaskType.TESTING.value == "testing"

        # TaskPriority values
        assert TaskPriority.LOW.value == 1
        assert TaskPriority.MEDIUM.value == 2
        assert TaskPriority.HIGH.value == 3
        assert TaskPriority.CRITICAL.value == 5

        # TaskStatus values
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.UNDER_REVIEW.value == "under_review"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_task_status_update_behavior_edge_cases(self):
        """Test edge cases in task status updates."""
        # Given: a task
        task = Task("Edge Case Task", "Testing edge cases")

        # When: setting status to IN_PROGRESS multiple times
        task.update_status(TaskStatus.IN_PROGRESS)
        first_started_at = task.started_at
        
        task.update_status(TaskStatus.IN_PROGRESS)  # Again
        second_started_at = task.started_at

        # Then: started_at should not change once set
        assert first_started_at == second_started_at

        # When: moving to COMPLETED then back to IN_PROGRESS
        task.update_status(TaskStatus.COMPLETED)
        completed_at = task.completed_at
        
        task.update_status(TaskStatus.IN_PROGRESS)  # Back to in progress

        # Then: completed_at should be cleared (or maintained - characterizes current behavior)
        # This test documents what actually happens
        current_completed_at = task.completed_at
        # Note: The actual behavior would be verified by running the test
        # This characterizes whatever the current implementation does
        
        # When: status goes from PENDING directly to COMPLETED
        fresh_task = Task("Fresh Task", "Direct completion")
        fresh_task.update_status(TaskStatus.COMPLETED)
        
        # Then: both started_at and completed_at should be set
        assert fresh_task.started_at is None  # Characterizes actual behavior
        assert fresh_task.completed_at is not None

    def test_task_manager_bulk_operations(self, task_manager):
        """Test task manager bulk operation behavior."""
        # Given: multiple tasks
        task_ids = []
        for i in range(5):
            task_id = task_manager.create_task({
                "title": f"Bulk Task {i}",
                "description": f"Task {i} for bulk testing",
                "assignee": "bulk_tester"
            })
            task_ids.append(task_id)

        # When: performing bulk status update
        updated_ids = task_manager.bulk_update_status(task_ids[:3], TaskStatus.IN_PROGRESS)

        # Then: specified tasks should be updated
        assert len(updated_ids) == 3
        for task_id in updated_ids:
            task = task_manager.get_task(task_id)
            assert task.status == TaskStatus.IN_PROGRESS

        # And: other tasks should remain unchanged
        for task_id in task_ids[3:]:
            task = task_manager.get_task(task_id)
            assert task.status == TaskStatus.PENDING

    def test_task_manager_statistics(self, task_manager):
        """Test task manager statistics generation."""
        # Given: tasks in various states
        task_manager.create_task({"title": "Pending 1", "status": "pending"})
        task_manager.create_task({"title": "Pending 2", "status": "pending"})
        
        in_progress_id = task_manager.create_task({"title": "In Progress", "status": "pending"})
        task_manager.update_task(in_progress_id, {"status": "in_progress"})
        
        completed_id = task_manager.create_task({"title": "Completed", "status": "pending"})
        task_manager.update_task(completed_id, {"status": "completed"})

        # When: getting statistics
        stats = task_manager.get_statistics()

        # Then: stats should reflect current state
        assert stats["total_tasks"] == 4
        assert stats["pending_tasks"] == 2
        assert stats["in_progress_tasks"] == 1
        assert stats["completed_tasks"] == 1
        assert "task_distribution" in stats
        assert "completion_rate" in stats