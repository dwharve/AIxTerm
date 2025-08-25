"""
Tests for the DevTeam plugin.
"""

import pytest

from aixterm.plugins.devteam.modules.types import TaskStatus
from aixterm.plugins.devteam.plugin.core import DevTeamPlugin


class MockService:
    """Mock service for testing."""

    def __init__(self):
        self.config = {"plugins": {"devteam": {}}}


@pytest.fixture
def devteam_plugin():
    """Create a DevTeam plugin instance for testing."""
    service = MockService()
    plugin = DevTeamPlugin(service)
    yield plugin
    # Ensure background tasks are stopped to prevent pending task warnings
    try:
        plugin.shutdown()
    except Exception:
        pass


def test_plugin_properties(devteam_plugin):
    """Test plugin properties."""
    assert devteam_plugin.id == "devteam"
    assert devteam_plugin.name == "DevTeam"
    assert devteam_plugin.version == "0.1.0"
    assert "AI-powered" in devteam_plugin.description


def test_plugin_initialization(devteam_plugin):
    """Test plugin initialization."""
    assert devteam_plugin.initialize() is True
    assert devteam_plugin._active_tasks == {}
    assert devteam_plugin._task_queue == []
    assert devteam_plugin._task_status == {}


def test_plugin_commands(devteam_plugin):
    """Test plugin commands."""
    commands = devteam_plugin.get_commands()
    assert "devteam:submit" in commands
    assert "devteam:list" in commands
    assert "devteam:status" in commands
    assert "devteam:cancel" in commands


def test_submit_task(devteam_plugin):
    """Test task submission."""
    devteam_plugin.initialize()

    request = {
        "command": "devteam:submit",
        "parameters": {
            "title": "Test Task",
            "description": "This is a test task",
            "type": "feature",
            "priority": "medium",
        },
    }

    response = devteam_plugin.handle_request(request)

    assert response["success"] is True
    assert "task_id" in response
    task_id = response["task_id"]

    # Verify task was added
    assert task_id in devteam_plugin._active_tasks
    assert task_id in devteam_plugin._task_queue
    assert devteam_plugin._task_status[task_id] == TaskStatus.SUBMITTED


def test_list_tasks(devteam_plugin):
    """Test task listing."""
    devteam_plugin.initialize()

    # Submit a task first
    submit_request = {
        "command": "devteam:submit",
        "parameters": {"title": "Test Task", "description": "This is a test task"},
    }
    # submit_response = devteam_plugin.handle_request(submit_request)
    devteam_plugin.handle_request(submit_request)

    # List tasks
    list_request = {"command": "devteam:list", "parameters": {}}
    list_response = devteam_plugin.handle_request(list_request)

    assert list_response["success"] is True
    assert len(list_response["tasks"]) == 1
    assert list_response["tasks"][0]["title"] == "Test Task"


def test_task_status(devteam_plugin):
    """Test task status retrieval."""
    devteam_plugin.initialize()

    # Submit a task first
    submit_request = {
        "command": "devteam:submit",
        "parameters": {"title": "Test Task", "description": "This is a test task"},
    }
    submit_response = devteam_plugin.handle_request(submit_request)
    task_id = submit_response["task_id"]

    # Get status
    status_request = {"command": "devteam:status", "parameters": {"task_id": task_id}}
    status_response = devteam_plugin.handle_request(status_request)

    assert status_response["success"] is True
    assert status_response["task"]["id"] == task_id
    assert status_response["task"]["title"] == "Test Task"
    assert status_response["task"]["status"] == "submitted"


def test_cancel_task(devteam_plugin):
    """Test task cancellation."""
    devteam_plugin.initialize()

    # Submit a task first
    submit_request = {
        "command": "devteam:submit",
        "parameters": {"title": "Test Task", "description": "This is a test task"},
    }
    submit_response = devteam_plugin.handle_request(submit_request)
    task_id = submit_response["task_id"]

    # Cancel task
    cancel_request = {"command": "devteam:cancel", "parameters": {"task_id": task_id}}
    cancel_response = devteam_plugin.handle_request(cancel_request)

    assert cancel_response["success"] is True
    assert devteam_plugin._task_status[task_id] == TaskStatus.CANCELLED
    assert task_id not in devteam_plugin._task_queue


def test_shutdown(devteam_plugin):
    """Test plugin shutdown."""
    devteam_plugin.initialize()
    assert devteam_plugin.shutdown() is True
