"""
DevTeam Agent Framework

This module provides the base classes and registry for AI agents in the DevTeam plugin.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class Agent(ABC):
    """
    Base class for all AI agents in the DevTeam plugin.

    Agents are specialized AI components that handle specific roles in the software
    development process, such as project management, architecture, coding, etc.
    """

    def __init__(self, plugin):
        """
        Initialize the agent.

        Args:
            plugin: The DevTeam plugin instance.
        """
        self.plugin = plugin
        self.logger = logging.getLogger(
            f"aixterm.plugin.devteam.agent.{self.agent_type}"
        )
        self.config = self._get_agent_config()
        self.initialized = False

    @property
    @abstractmethod
    def agent_type(self) -> str:
        """
        Get the agent type.

        Returns:
            The agent type identifier.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the agent name.

        Returns:
            The human-readable agent name.
        """
        pass

    @property
    def version(self) -> str:
        """
        Get the agent version.

        Returns:
            The agent version string.
        """
        return "0.1.0"

    @property
    def description(self) -> str:
        """
        Get the agent description.

        Returns:
            The agent description.
        """
        return f"{self.name} agent for DevTeam"

    def initialize(self) -> bool:
        """
        Initialize the agent.

        Returns:
            True if initialization was successful, False otherwise.
        """
        self.logger.debug(f"Initializing agent: {self.agent_type}")
        self.initialized = True
        return True

    def shutdown(self) -> bool:
        """
        Shutdown the agent.

        Returns:
            True if shutdown was successful, False otherwise.
        """
        self.logger.debug(f"Shutting down agent: {self.agent_type}")
        self.initialized = False
        return True

    @abstractmethod
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a task.

        Args:
            task: The task to process.

        Returns:
            The processing result.
        """
        pass

    def _get_agent_config(self) -> Dict[str, Any]:
        """
        Get agent configuration.

        Returns:
            The agent configuration.
        """
        default_config = {
            "enabled": True,
            "max_tasks": 5,
        }

        try:
            plugin_config = self.plugin._plugin_config
            agents_config = plugin_config.get("agents", {})
            agent_config = agents_config.get(self.agent_type, {})

            # Merge default and user config
            config = default_config.copy()
            config.update(agent_config)

            return config
        except Exception as e:
            self.logger.error(f"Error getting agent config: {e}")
            return default_config


class AgentRegistry:
    """
    Registry for DevTeam agents.

    This class manages agent registration, instantiation, and lifecycle.
    """

    def __init__(self, plugin):
        """
        Initialize the agent registry.

        Args:
            plugin: The DevTeam plugin instance.
        """
        self.plugin = plugin
        self.logger = logging.getLogger("aixterm.plugin.devteam.agent_registry")
        self.agent_classes: Dict[str, Type[Agent]] = {}
        self.agents: Dict[str, Agent] = {}

    def register_agent_class(self, agent_class: Type[Agent]) -> None:
        """
        Register an agent class.

        Args:
            agent_class: The agent class to register.
        """
        try:
            # Create temporary instance to get agent type
            temp_agent = agent_class(self.plugin)
            agent_type = temp_agent.agent_type

            # Don't keep the temp instance, just register the class
            self.agent_classes[agent_type] = agent_class
            self.logger.debug(f"Registered agent class: {agent_type}")
        except Exception as e:
            self.logger.error(f"Error registering agent class: {e}")

    def create_agent(self, agent_type: str) -> Optional[Agent]:
        """
        Create an agent instance.

        Args:
            agent_type: The type of agent to create.

        Returns:
            The created agent instance, or None if creation failed.
        """
        if agent_type not in self.agent_classes:
            self.logger.error(f"Agent class not found: {agent_type}")
            return None

        try:
            agent_class = self.agent_classes[agent_type]
            agent = agent_class(self.plugin)

            if agent.initialize():
                self.agents[agent_type] = agent
                self.logger.debug(f"Created agent: {agent_type}")
                return agent
            else:
                self.logger.error(f"Agent initialization failed: {agent_type}")
                return None
        except Exception as e:
            self.logger.error(f"Error creating agent: {e}")
            return None

    def get_agent(self, agent_type: str) -> Optional[Agent]:
        """
        Get an agent instance.

        Args:
            agent_type: The type of agent to get.

        Returns:
            The agent instance, or None if not found.
        """
        return self.agents.get(agent_type)

    def shutdown_agents(self) -> bool:
        """
        Shutdown all agents.

        Returns:
            True if all agents were shutdown successfully, False otherwise.
        """
        success = True

        for agent_type, agent in list(self.agents.items()):
            try:
                if agent.shutdown():
                    del self.agents[agent_type]
                else:
                    success = False
            except Exception as e:
                self.logger.error(f"Error shutting down agent {agent_type}: {e}")
                success = False

        return success


def create_default_registry(plugin) -> AgentRegistry:
    """
    Create a default agent registry with standard agents.

    Args:
        plugin: The DevTeam plugin instance.

    Returns:
        The initialized agent registry.
    """
    # Import agents as they're implemented
    from .code_analyst import CodeAnalystAgent
    from .developer import DeveloperAgent
    from .project_manager import ProjectManagerAgent
    from .qa_tester import QATesterAgent

    registry = AgentRegistry(plugin)

    # Register available agents
    registry.register_agent_class(ProjectManagerAgent)
    registry.register_agent_class(CodeAnalystAgent)
    registry.register_agent_class(DeveloperAgent)
    registry.register_agent_class(QATesterAgent)

    # TODO: Register other agents as they're implemented
    # - ArchitectAgent
    # - ReviewerAgent
    # - DocumentationAgent

    return registry
