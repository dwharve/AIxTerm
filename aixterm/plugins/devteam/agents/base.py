"""
Abstract base class for DevTeam agents to eliminate duplication.

This module provides AbstractAgentBase which captures the common interface
and default implementations shared across all DevTeam agents.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict


class AbstractAgentBase(ABC):
    """
    Abstract base class for DevTeam agents that eliminates common boilerplate.

    This class provides default implementations for commonly duplicated methods
    while maintaining the abstract interface for agent-specific behavior.
    
    Agents can optionally use declarative attributes instead of property methods:
    - _agent_type: str
    - _name: str 
    - _description: str
    """

    # Declarative attributes (can be overridden in subclasses)
    _agent_type: str = ""
    _name: str = ""
    _description: str = ""

    def __init__(self, plugin):
        """
        Initialize the agent.

        Args:
            plugin: The plugin instance that owns this agent.
        """
        self.plugin = plugin
        self.logger = logging.getLogger(f"aixterm.agent.{self.agent_type}")
        self.initialized = False

    @property
    def agent_type(self) -> str:
        """
        Get the agent type identifier.

        Returns:
            The unique agent type string.
        """
        if self._agent_type:
            return self._agent_type
        raise NotImplementedError("Agents must implement agent_type property or set _agent_type attribute")

    @property
    def name(self) -> str:
        """
        Get the human-readable agent name.

        Returns:
            The agent display name.
        """
        if self._name:
            return self._name
        raise NotImplementedError("Agents must implement name property or set _name attribute")

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

        Default implementation provides a generic description.
        Agents can override this property or set _description attribute.

        Returns:
            The agent description.
        """
        if self._description:
            return self._description
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
            "max_retries": 3,
            "timeout_seconds": 30,
            "debug": False,
            "enabled": True,
            "max_tasks": 5,
        }
        
        try:
            # DevTeam plugin specific config structure
            if hasattr(self.plugin, '_plugin_config'):
                plugin_config = self.plugin._plugin_config
                agents_config = plugin_config.get("agents", {})
                agent_config = agents_config.get(self.agent_type, {})
                
                # Merge default and user config
                config = default_config.copy()
                config.update(agent_config)
                return config
            # Fallback for other plugins
            elif hasattr(self.plugin, '_get_agent_config'):
                agent_config = self.plugin._get_agent_config()
                agent_specific = agent_config.get(self.agent_type, {})
                default_config.update(agent_specific)
        except Exception as e:
            self.logger.error(f"Error getting agent configuration: {e}")

        return default_config