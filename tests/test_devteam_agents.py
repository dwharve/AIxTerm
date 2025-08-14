"""
Tests for the DevTeam plugin agent framework.
"""

import pytest

from aixterm.plugins.devteam.agents import Agent, AgentRegistry
from aixterm.plugins.devteam.agents.project_manager import ProjectManagerAgent


class MockPlugin:
    """Mock plugin for testing."""

    def __init__(self):
        self._plugin_config = {
            "agents": {"project_manager": {"enabled": True, "max_tasks": 10}}
        }


# Define a test agent class - not a pytest test class
class SampleTestAgent(Agent):
    """Sample test agent implementation."""

    @property
    def agent_type(self) -> str:
        return "test_agent"

    @property
    def name(self) -> str:
        return "Test Agent"

    async def process_task(self, task):
        return {"success": True, "task_id": task["id"]}


@pytest.fixture
def mock_plugin():
    """Create a mock plugin for testing."""
    return MockPlugin()


@pytest.fixture
def agent_registry(mock_plugin):
    """Create an agent registry for testing."""
    return AgentRegistry(mock_plugin)


def test_agent_creation():
    """Test agent creation."""
    plugin = MockPlugin()
    agent = SampleTestAgent(plugin)

    assert agent.agent_type == "test_agent"
    assert agent.name == "Test Agent"
    assert agent.version == "0.1.0"
    assert "Test Agent" in agent.description
    assert agent.config["enabled"] is True


def test_agent_initialization():
    """Test agent initialization."""
    plugin = MockPlugin()
    agent = SampleTestAgent(plugin)

    assert agent.initialized is False
    assert agent.initialize() is True
    assert agent.initialized is True
    assert agent.shutdown() is True
    assert agent.initialized is False


def test_agent_registry_registration(agent_registry, mock_plugin):
    """Test agent registration in registry."""
    agent_registry.register_agent_class(SampleTestAgent)

    assert "test_agent" not in agent_registry.agents
    agent = agent_registry.create_agent("test_agent")

    assert agent is not None
    assert agent.agent_type == "test_agent"
    assert "test_agent" in agent_registry.agents


def test_agent_registry_get_agent(agent_registry, mock_plugin):
    """Test getting an agent from registry."""
    agent_registry.register_agent_class(SampleTestAgent)
    agent_registry.create_agent("test_agent")

    agent = agent_registry.get_agent("test_agent")
    assert agent is not None
    assert agent.agent_type == "test_agent"

    nonexistent = agent_registry.get_agent("nonexistent")
    assert nonexistent is None


def test_agent_registry_shutdown(agent_registry, mock_plugin):
    """Test shutting down agents."""
    agent_registry.register_agent_class(SampleTestAgent)
    agent_registry.create_agent("test_agent")

    assert "test_agent" in agent_registry.agents
    assert agent_registry.shutdown_agents() is True
    assert "test_agent" not in agent_registry.agents


@pytest.mark.asyncio
async def test_project_manager_agent():
    """Test ProjectManagerAgent implementation."""
    plugin = MockPlugin()
    agent = ProjectManagerAgent(plugin)

    assert agent.agent_type == "project_manager"
    assert agent.name == "Project Manager"
    assert "prioritizes" in agent.description

    # Test task processing
    task = {"id": "task_1", "title": "Test Task", "priority": "high"}

    result = await agent.process_task(task)

    assert result["success"] is True
    assert result["task_id"] == "task_1"
    assert "plan" in result["result"]
    assert result["result"]["plan"]["priority"] == "high"
