"""
Test DevTeam plugin workflow with a task that engages all agents.

This test case simulates a complete workflow where a task is submitted to the DevTeam plugin
and processed through the plugin's task handling system.
"""

import pytest

from aixterm.plugins.devteam.modules.types import TaskStatus
from aixterm.plugins.devteam.plugin.core import DevTeamPlugin


class MockService:
    """Mock service for testing."""

    def __init__(self):
        self.config = {
            "plugins": {
                "devteam": {
                    "agents": {
                        "project_manager": {"enabled": True, "max_tasks": 10},
                        "code_analyst": {"enabled": True, "max_tasks": 5},
                        "developer": {"enabled": True, "instances": 2, "max_tasks": 5},
                        "qa_tester": {"enabled": True, "max_tasks": 5},
                    },
                    "workflow": {
                        "require_architecture_review": True,
                        "require_code_review": True,
                        "require_testing": True,
                        "parallel_development": True,
                    },
                }
            }
        }


@pytest.fixture
def mock_service():
    """Create a mock service for testing."""
    return MockService()


@pytest.fixture
def devteam_plugin(mock_service):
    """Create a DevTeam plugin instance for testing."""
    # Create the plugin with our mock service
    plugin = DevTeamPlugin(mock_service)
    plugin.initialize()
    return plugin


def test_devteam_submit_complex_task(devteam_plugin):
    """Test submitting a complex task that would engage all agents."""
    # Submit a task that would require collaboration between all agents
    request = {
        "command": "devteam:submit",
        "parameters": {
            "title": "Implement Authentication System",
            "description": """
            Implement a complete authentication system with the following features:
            - User registration and login
            - Password reset functionality
            - Two-factor authentication
            - Session management
            - RBAC (Role-Based Access Control)

            The system should follow security best practices and include comprehensive testing.
            """,
            "type": "feature",  # Can be feature, bug_fix, refactor, etc.
            "priority": "high",
            "complexity": "high",
            "required_skills": ["security", "backend", "database", "testing"],
            "artifacts_needed": ["code", "tests", "documentation"],
        },
    }

    # Submit the task
    response = devteam_plugin.handle_request(request)

    # Verify basic response structure
    assert response["success"] is True
    assert "task_id" in response
    task_id = response["task_id"]

    # Check that the task was added to internal tracking
    assert task_id in devteam_plugin._active_tasks
    assert task_id in devteam_plugin._task_queue
    assert task_id in devteam_plugin._task_status
    assert devteam_plugin._task_status[task_id] == TaskStatus.SUBMITTED

    # Get status of the task
    status_request = {"command": "devteam:status", "parameters": {"task_id": task_id}}

    status_response = devteam_plugin.handle_request(status_request)

    # Verify the status response
    assert status_response["success"] is True
    assert status_response["task"]["id"] == task_id
    assert status_response["task"]["title"] == "Implement Authentication System"
    assert status_response["task"]["status"] == "submitted"

    # List tasks and verify our task is included
    list_request = {"command": "devteam:list", "parameters": {}}

    list_response = devteam_plugin.handle_request(list_request)

    assert list_response["success"] is True
    assert len(list_response["tasks"]) >= 1

    # Find our task in the list
    found_task = False
    for task in list_response["tasks"]:
        if task["task_id"] == task_id:
            found_task = True
            assert task["title"] == "Implement Authentication System"
            assert task["status"] == "submitted"
            break

    assert found_task, "Task not found in list response"


def test_devteam_task_with_subtasks(devteam_plugin):
    """
    Test a complex task that could be broken down into subtasks.

    This demonstrates how the DevTeam plugin handles complex tasks.
    """
    # Submit a complex task
    request = {
        "command": "devteam:submit",
        "parameters": {
            "title": "Build API Gateway Service",
            "description": """
            Create an API Gateway service with the following components:
            1. Request routing
            2. Authentication/Authorization
            3. Rate limiting
            4. Request/Response transformation
            5. Logging and monitoring
            6. Circuit breaker pattern implementation

            The service should be containerized and include Swagger documentation.
            """,
            "type": "feature",
            "priority": "high",
            "complexity": "high",
            "is_decomposable": True,  # Flag indicating this task can be broken down
        },
    }

    # Submit the task
    response = devteam_plugin.handle_request(request)

    assert response["success"] is True
    assert "task_id" in response
    task_id = response["task_id"]

    # Verify task was registered
    assert task_id in devteam_plugin._active_tasks
    assert devteam_plugin._task_status[task_id] == TaskStatus.SUBMITTED

    # Get status to verify task details
    status_request = {"command": "devteam:status", "parameters": {"task_id": task_id}}

    status_response = devteam_plugin.handle_request(status_request)

    assert status_response["success"] is True
    assert status_response["task"]["id"] == task_id
    assert status_response["task"]["title"] == "Build API Gateway Service"
    assert status_response["task"]["status"] == "submitted"

    # Cancel the task to test cancellation
    cancel_request = {"command": "devteam:cancel", "parameters": {"task_id": task_id}}

    cancel_response = devteam_plugin.handle_request(cancel_request)

    # Verify cancellation
    assert cancel_response["success"] is True

    # Check that status was updated to cancelled
    status_response = devteam_plugin.handle_request(status_request)
    if (
        "status" in status_response["task"]
    ):  # Some implementations might remove cancelled tasks
        assert status_response["task"]["status"] == "cancelled"
