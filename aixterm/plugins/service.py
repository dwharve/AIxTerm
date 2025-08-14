"""
AIxTerm Plugin Service Integration

This module provides handlers for integrating plugins with the AIxTerm service.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class PluginServiceHandlers:
    """
    Plugin-related handlers for the AIxTerm service.

    This class provides handlers for plugin-related API endpoints in the
    AIxTerm service.
    """

    def __init__(self, service):
        """
        Initialize the plugin service handlers.

        Args:
            service: The AIxTerm service instance.
        """
        self.service = service
        self.logger = logging.getLogger("aixterm.plugin_service")

    def register_handlers(self) -> Dict[str, Any]:
        """
        Register plugin-related handlers with the service server.

        Returns:
            A dictionary mapping endpoint names to handler functions.
        """
        return {
            "plugin.list": self.handle_list_plugins,
            "plugin.info": self.handle_plugin_info,
            "plugin.status": self.handle_plugin_status,
            "plugin.load": self.handle_load_plugin,
            "plugin.unload": self.handle_unload_plugin,
            "plugin.command": self.handle_plugin_command,
        }

    def handle_list_plugins(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a request to list available plugins.

        Args:
            request: The request data.

        Returns:
            A response with available plugin information.
        """
        try:
            # Discover available plugins
            available_plugins = self.service.plugin_manager.discover_plugins()

            # Get loaded plugins
            loaded_plugins = self.service.plugin_manager.plugins

            # Prepare response data
            plugins_data = []
            for plugin_id, plugin_class in available_plugins.items():
                plugin_info = {
                    "id": plugin_id,
                    "loaded": plugin_id in loaded_plugins,
                }

                # Add additional info if the plugin is loaded
                if plugin_id in loaded_plugins:
                    plugin = loaded_plugins[plugin_id]
                    plugin_info.update(
                        {
                            "name": plugin.name,
                            "version": plugin.version,
                            "description": plugin.description,
                        }
                    )

                plugins_data.append(plugin_info)

            return {
                "status": "success",
                "plugins": plugins_data,
                "total": len(plugins_data),
                "loaded": len(loaded_plugins),
            }

        except Exception as e:
            self.logger.error(f"Error listing plugins: {e}")
            return {
                "status": "error",
                "error": {
                    "code": "list_plugins_error",
                    "message": str(e),
                },
            }

    def handle_plugin_info(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a request to get detailed information about a plugin.

        Args:
            request: The request data. Should contain a 'plugin_id' field.

        Returns:
            A response with plugin information.
        """
        try:
            plugin_id = request.get("plugin_id")
            if not plugin_id:
                return {
                    "status": "error",
                    "error": {
                        "code": "missing_plugin_id",
                        "message": "No plugin ID provided",
                    },
                }

            # Check if the plugin is loaded
            loaded_plugins = self.service.plugin_manager.plugins
            if plugin_id in loaded_plugins:
                plugin = loaded_plugins[plugin_id]
                return {
                    "status": "success",
                    "plugin": {
                        "id": plugin_id,
                        "name": plugin.name,
                        "version": plugin.version,
                        "description": plugin.description,
                        "loaded": True,
                        "initialized": plugin.initialized,
                        "commands": list(plugin.get_commands().keys()),
                    },
                }

            # If not loaded, try to find it in available plugins
            available_plugins = self.service.plugin_manager.discover_plugins()
            if plugin_id in available_plugins:
                return {
                    "status": "success",
                    "plugin": {
                        "id": plugin_id,
                        "loaded": False,
                    },
                }

            return {
                "status": "error",
                "error": {
                    "code": "plugin_not_found",
                    "message": f"Plugin not found: {plugin_id}",
                },
            }

        except Exception as e:
            self.logger.error(f"Error getting plugin info: {e}")
            return {
                "status": "error",
                "error": {
                    "code": "plugin_info_error",
                    "message": str(e),
                },
            }

    def handle_plugin_status(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a request to get the status of all plugins.

        Args:
            request: The request data.

        Returns:
            A response with plugin status information.
        """
        try:
            status = self.service.plugin_manager.get_status()
            return {
                "status": "success",
                "plugin_status": status,
            }

        except Exception as e:
            self.logger.error(f"Error getting plugin status: {e}")
            return {
                "status": "error",
                "error": {
                    "code": "plugin_status_error",
                    "message": str(e),
                },
            }

    def handle_load_plugin(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a request to load a plugin.

        Args:
            request: The request data. Should contain a 'plugin_id' field.

        Returns:
            A response indicating success or failure.
        """
        try:
            plugin_id = request.get("plugin_id")
            if not plugin_id:
                return {
                    "status": "error",
                    "error": {
                        "code": "missing_plugin_id",
                        "message": "No plugin ID provided",
                    },
                }

            # Check if the plugin is already loaded
            if plugin_id in self.service.plugin_manager.plugins:
                return {
                    "status": "success",
                    "message": f"Plugin already loaded: {plugin_id}",
                    "already_loaded": True,
                }

            # Load the plugin
            if self.service.plugin_manager.load_plugin(plugin_id):
                return {
                    "status": "success",
                    "message": f"Plugin loaded: {plugin_id}",
                    "loaded": True,
                }

            return {
                "status": "error",
                "error": {
                    "code": "plugin_load_failed",
                    "message": f"Failed to load plugin: {plugin_id}",
                },
            }

        except Exception as e:
            self.logger.error(f"Error loading plugin: {e}")
            return {
                "status": "error",
                "error": {
                    "code": "plugin_load_error",
                    "message": str(e),
                },
            }

    def handle_unload_plugin(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a request to unload a plugin.

        Args:
            request: The request data. Should contain a 'plugin_id' field.

        Returns:
            A response indicating success or failure.
        """
        try:
            plugin_id = request.get("plugin_id")
            if not plugin_id:
                return {
                    "status": "error",
                    "error": {
                        "code": "missing_plugin_id",
                        "message": "No plugin ID provided",
                    },
                }

            # Check if the plugin is loaded
            if plugin_id not in self.service.plugin_manager.plugins:
                return {
                    "status": "success",
                    "message": f"Plugin not loaded: {plugin_id}",
                    "already_unloaded": True,
                }

            # Unload the plugin
            if self.service.plugin_manager.unload_plugin(plugin_id):
                return {
                    "status": "success",
                    "message": f"Plugin unloaded: {plugin_id}",
                    "unloaded": True,
                }

            return {
                "status": "error",
                "error": {
                    "code": "plugin_unload_failed",
                    "message": f"Failed to unload plugin: {plugin_id}",
                },
            }

        except Exception as e:
            self.logger.error(f"Error unloading plugin: {e}")
            return {
                "status": "error",
                "error": {
                    "code": "plugin_unload_error",
                    "message": str(e),
                },
            }

    def handle_plugin_command(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a request to execute a plugin command.

        Args:
            request: The request data. Should contain 'plugin_id' and 'command' fields.

        Returns:
            A response with the command result.
        """
        try:
            plugin_id = request.get("plugin_id")
            command = request.get("command")
            data = request.get("data", {})

            if not plugin_id:
                return {
                    "status": "error",
                    "error": {
                        "code": "missing_plugin_id",
                        "message": "No plugin ID provided",
                    },
                }

            if not command:
                return {
                    "status": "error",
                    "error": {
                        "code": "missing_command",
                        "message": "No command provided",
                    },
                }

            # Route the command to the plugin
            response = self.service.plugin_manager.handle_request(
                plugin_id, {"command": command, "data": data}
            )
            # Ensure a dictionary response
            if isinstance(response, dict):
                return response
            return {"status": "error", "error": {"code": "invalid_response"}}

        except Exception as e:
            self.logger.error(f"Error executing plugin command: {e}")
            return {
                "status": "error",
                "error": {
                    "code": "plugin_command_error",
                    "message": str(e),
                },
            }
