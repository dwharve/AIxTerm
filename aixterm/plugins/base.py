"""
AIxTerm Plugin Base

This module provides the base class for AIxTerm plugins.
"""

import logging
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)


class Plugin:
    """
    Base class for all AIxTerm plugins.

    All plugins must inherit from this class and implement the required properties
    and methods.
    """

    def __init__(self, service):
        """
        Initialize the plugin.

        Args:
            service: The AIxTerm service instance.
        """
        self.service = service
        self.config = self._get_plugin_config()
        self.logger = logging.getLogger(f"aixterm.plugin.{self.id}")
        self.initialized = False

    @property
    def id(self) -> str:
        """
        Get the unique identifier for the plugin.

        Returns:
            The plugin ID.

        Raises:
            NotImplementedError: If the plugin doesn't implement this property.
        """
        raise NotImplementedError("Plugins must implement the id property")

    @property
    def name(self) -> str:
        """
        Get the human-readable name of the plugin.

        Returns:
            The plugin name.

        Raises:
            NotImplementedError: If the plugin doesn't implement this property.
        """
        raise NotImplementedError("Plugins must implement the name property")

    @property
    def version(self) -> str:
        """
        Get the version of the plugin.

        Returns:
            The plugin version.

        Raises:
            NotImplementedError: If the plugin doesn't implement this property.
        """
        raise NotImplementedError("Plugins must implement the version property")

    @property
    def description(self) -> str:
        """
        Get the description of the plugin.

        Returns:
            The plugin description.
        """
        return "No description provided"

    def _get_plugin_config(self) -> Dict[str, Any]:
        """
        Get the plugin configuration from the service config.

        Returns:
            The plugin configuration dictionary.
        """
        try:
            plugins_config = self.service.config.get("plugins", {})
            plugin_config = plugins_config.get("plugins", {}).get(self.id, {})
            settings: Dict[str, Any] = plugin_config.get("settings", {})
            return settings
        except Exception as e:
            self.logger.error(f"Error getting plugin configuration: {e}")
            return {}

    def initialize(self) -> bool:
        """
        Initialize the plugin. This method is called when the plugin is loaded.

        Returns:
            True if initialization was successful, False otherwise.
        """
        self.initialized = True
        return True

    def shutdown(self) -> bool:
        """
        Shutdown the plugin. This method is called when the plugin is unloaded.

        Returns:
            True if shutdown was successful, False otherwise.
        """
        self.initialized = False
        return True

    def get_commands(self) -> Dict[str, Callable]:
        """
        Get the commands that this plugin provides.

        Returns:
            A dictionary mapping command names to handler functions.
        """
        return {}

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a request for this plugin.

        Args:
            request: The request dictionary.

        Returns:
            The response dictionary.
        """
        command = request.get("command")
        data = request.get("data", {})

        # Get commands from this plugin
        commands = self.get_commands()

        if command in commands:
            handler = commands[command]
            try:
                result = handler(data)
                return {"status": "success", "result": result}
            except Exception as e:
                self.logger.error(f"Error handling command '{command}': {e}")
                return {
                    "status": "error",
                    "error": {"code": "command_error", "message": str(e)},
                }

        return {
            "status": "error",
            "error": {
                "code": "unknown_command",
                "message": f"Unknown command: {command}",
            },
        }

    def status(self) -> Dict[str, Any]:
        """
        Get the status of this plugin.

        Returns:
            A dictionary with plugin status information.
        """
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "initialized": self.initialized,
        }
