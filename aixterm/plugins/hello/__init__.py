"""
Hello World Plugin for AIxTerm

A simple example plugin that demonstrates the AIxTerm plugin system.
"""

from typing import Any, Callable, Dict

from aixterm.plugins import Plugin


class HelloPlugin(Plugin):
    """
    A simple Hello World plugin for AIxTerm.

    This plugin demonstrates the basic structure of an AIxTerm plugin.
    """

    # Example of dependency declaration (no actual dependencies)
    dependencies = []

    @property
    def id(self) -> str:
        """Get the plugin ID."""
        return "hello"

    @property
    def name(self) -> str:
        """Get the plugin name."""
        return "Hello World"

    @property
    def version(self) -> str:
        """Get the plugin version."""
        return "0.1.0"

    @property
    def description(self) -> str:
        """Get the plugin description."""
        return "A simple Hello World plugin for AIxTerm"

    def initialize(self) -> bool:
        """
        Initialize the plugin.

        Returns:
            True if initialization was successful, False otherwise.
        """
        self.logger.info("Initializing Hello World plugin")
        return super().initialize()

    def shutdown(self) -> bool:
        """
        Shutdown the plugin.

        Returns:
            True if shutdown was successful, False otherwise.
        """
        self.logger.info("Shutting down Hello World plugin")
        return super().shutdown()

    def get_commands(self) -> Dict[str, Callable]:
        """
        Get the commands provided by this plugin.

        Returns:
            A dictionary mapping command names to handler functions.
        """
        return {
            "hello": self.cmd_hello,
            "hello_name": self.cmd_hello_name,
        }

    def cmd_hello(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the 'hello' command.

        Args:
            data: Command data.

        Returns:
            Command result.
        """
        return {"message": "Hello, World!"}

    def cmd_hello_name(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the 'hello_name' command.

        Args:
            data: Command data. Should contain a 'name' field.

        Returns:
            Command result.
        """
        name = data.get("name", "anonymous")
        return {"message": f"Hello, {name}!"}
