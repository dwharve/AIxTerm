"""
DevTeam Agent Framework

This module provides the base classes and registry for AI agents in the DevTeam plugin.
"""

import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Type

from .base import AbstractAgentBase
from ....lifecycle import LifecycleManager

logger = logging.getLogger(__name__)


class Agent(AbstractAgentBase):
    """Base class for all AI agents in the DevTeam plugin.

    Agents are specialized AI components that handle specific roles in the software
    development process, such as project management, architecture, coding, etc.
    
    This class now inherits from AbstractAgentBase to eliminate duplication.
    Inherited methods include: agent_type, name, version, description, initialize, 
    shutdown, process_task, and _get_agent_config.
    """

    def __init__(self, plugin):
        """
        Initialize the agent.

        Args:
            plugin: The DevTeam plugin instance.
        """
        super().__init__(plugin)
        # Update logger format to match existing pattern
        self.logger = logging.getLogger(
            f"aixterm.plugin.devteam.agent.{self.agent_type}"
        )
        self.config = self._get_agent_config()


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
        lifecycle_manager = LifecycleManager(self.logger)
        success = lifecycle_manager.shutdown_registry(self.agents, "agents")
        
        # Clear the registry after successful shutdown
        if success:
            self.agents.clear()
            
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

    return registry
