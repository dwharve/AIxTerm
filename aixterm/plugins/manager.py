"""
AIxTerm Plugin Manager

This module provides the plugin manager for discovering, loading, and managing
AIxTerm plugins.
"""

import importlib
import inspect
import logging
import os
import pkgutil
import sys
from typing import Any, Dict, List, Type

from .base import Plugin

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Plugin manager for AIxTerm.

    This class handles discovering, loading, and managing AIxTerm plugins.
    """

    def __init__(self, service):
        """
        Initialize the plugin manager.

        Args:
            service: The AIxTerm service instance.
        """
        self.service = service
        self.plugins: Dict[str, Plugin] = {}
        self.commands: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("aixterm.plugin_manager")

    def discover_plugins(self) -> Dict[str, Type[Plugin]]:
        """
        Discover available plugins.

        This method looks for plugins in:
        1. Built-in plugins (aixterm.plugins)
        2. Installed plugins (via entry points)
        3. User-defined plugins (from configured directories)
        4. Configured plugins (for testing)

        Returns:
            A dictionary mapping plugin IDs to plugin classes.
        """
        plugins: Dict[str, Type[Plugin]] = {}

        # 1. Discover built-in plugins
        builtin_plugins = self._discover_builtin_plugins()
        plugins.update(builtin_plugins)

        # 2. Discover installed plugins (via entry points)
        installed_plugins = self._discover_installed_plugins()
        plugins.update(installed_plugins)

        # 3. Discover user plugins from configured directories
        user_plugins = self._discover_user_plugins()
        plugins.update(user_plugins)

        return plugins

    def _discover_builtin_plugins(self) -> Dict[str, Type[Plugin]]:
        """
        Discover built-in plugins.

        Returns:
            A dictionary mapping plugin IDs to plugin classes.
        """
        self.logger.debug("Discovering built-in plugins...")
        plugins: Dict[str, Type[Plugin]] = {}

        # Look in the aixterm.plugins package
        # Excluding this file and base.py
        import aixterm.plugins as plugins_package

        for _, name, ispkg in pkgutil.iter_modules(
            plugins_package.__path__, plugins_package.__name__ + "."
        ):
            if ispkg and not name.endswith(".base"):
                try:
                    module = importlib.import_module(name)
                    for item_name, item in inspect.getmembers(module, inspect.isclass):
                        if (
                            issubclass(item, Plugin)
                            and item is not Plugin
                            and hasattr(item, "id")
                        ):
                            # Create a temporary instance to get the ID
                            try:
                                plugin_id = item.id
                                if isinstance(plugin_id, property):

                                    # Skip this class since we can't get the ID without instantiation
                                    continue
                                # Ensure plugin_id is a string
                                plugins[str(plugin_id)] = item
                                self.logger.debug(f"Found built-in plugin: {plugin_id}")
                            except (NotImplementedError, AttributeError):
                                # Skip plugins that don't have ID properly implemented
                                continue
                except Exception as e:
                    self.logger.error(
                        f"Error loading built-in plugin module {name}: {e}"
                    )

        return plugins

    def _discover_installed_plugins(self) -> Dict[str, Type[Plugin]]:
        """
        Discover plugins installed via entry points.

        Returns:
            A dictionary mapping plugin IDs to plugin classes.
        """
        self.logger.debug("Discovering installed plugins...")
        plugins: Dict[str, Type[Plugin]] = {}

        try:
            import importlib.metadata as metadata
        except ImportError:
            # Python < 3.8
            import importlib_metadata as metadata  # type: ignore

        try:
            for entry_point in metadata.entry_points(group="aixterm.plugins"):
                try:
                    plugin_class = entry_point.load()
                    if (
                        inspect.isclass(plugin_class)
                        and issubclass(plugin_class, Plugin)
                        and plugin_class is not Plugin
                    ):
                        # Create a temporary instance to get the ID
                        try:
                            plugin_id = plugin_class.id
                            if isinstance(plugin_id, property):

                                # Skip this class since we can't get the ID without instantiation
                                continue
                            # Ensure plugin_id is a string
                            plugins[str(plugin_id)] = plugin_class
                            self.logger.debug(
                                f"Found installed plugin: {plugin_id} from {entry_point.name}"
                            )
                        except (NotImplementedError, AttributeError):
                            # Skip plugins that don't have ID properly implemented
                            continue
                except Exception as e:
                    self.logger.error(
                        f"Error loading plugin from entry point {entry_point.name}: {e}"
                    )
        except Exception as e:
            self.logger.error(f"Error discovering installed plugins: {e}")

        return plugins

    def _discover_user_plugins(self) -> Dict[str, Type[Plugin]]:
        """
        Discover plugins in user-defined directories.

        Returns:
            A dictionary mapping plugin IDs to plugin classes.
        """
        self.logger.debug("Discovering user plugins...")
        plugins: Dict[str, Type[Plugin]] = {}

        # Get plugin directories from config
        plugin_dirs: List[str] = []

        try:
            plugins_config = self.service.config.get("plugins", {})
            plugin_directory = plugins_config.get("plugin_directory")
            if plugin_directory:
                # Expand user directory (~/...)
                plugin_directory = os.path.expanduser(plugin_directory)
                plugin_dirs.append(plugin_directory)
        except Exception as e:
            self.logger.error(f"Error getting plugin directories from config: {e}")

        # Search each directory for plugins
        for plugin_dir in plugin_dirs:
            if not os.path.isdir(plugin_dir):
                self.logger.warning(f"Plugin directory not found: {plugin_dir}")
                continue

            self.logger.debug(f"Searching for plugins in: {plugin_dir}")

            # Add directory to sys.path temporarily
            sys.path.insert(0, plugin_dir)
            try:
                # Look for Python packages in the directory
                for item in os.listdir(plugin_dir):
                    item_path = os.path.join(plugin_dir, item)
                    if os.path.isdir(item_path) and os.path.isfile(
                        os.path.join(item_path, "__init__.py")
                    ):
                        # This looks like a Python package
                        try:
                            module = importlib.import_module(item)
                            for attr_name, attr_value in inspect.getmembers(
                                module, inspect.isclass
                            ):
                                if (
                                    issubclass(attr_value, Plugin)
                                    and attr_value is not Plugin
                                    and hasattr(attr_value, "id")
                                ):
                                    try:
                                        plugin_id = attr_value.id
                                        if isinstance(plugin_id, property):

                                            # Skip this class since we can't get the ID without instantiation
                                            continue
                                        # Ensure plugin_id is a string
                                        plugins[str(plugin_id)] = attr_value
                                        self.logger.debug(
                                            f"Found user plugin: {plugin_id} in {item_path}"
                                        )
                                    except (NotImplementedError, AttributeError):

                                        # Skip plugins that don't have ID properly implemented
                                        continue
                        except Exception as e:
                            self.logger.error(
                                f"Error loading user plugin from {item_path}: {e}"
                            )
            finally:
                # Remove directory from sys.path
                if plugin_dir in sys.path:
                    sys.path.remove(plugin_dir)

        return plugins

    def load_plugin(self, plugin_id: str) -> bool:
        """
        Load a specific plugin by ID.

        Args:
            plugin_id: The ID of the plugin to load.

        Returns:
            True if the plugin was loaded successfully, False otherwise.
        """
        self.logger.info(f"Loading plugin: {plugin_id}")

        # Check if plugin is already loaded
        if plugin_id in self.plugins:
            self.logger.warning(f"Plugin already loaded: {plugin_id}")
            return True

        # Discover available plugins
        available_plugins = self.discover_plugins()

        if plugin_id not in available_plugins:
            self.logger.error(f"Plugin not found: {plugin_id}")
            return False

        # Check plugin dependencies
        dependency_status = self.check_plugin_dependencies(plugin_id)
        if not dependency_status["satisfied"]:
            # Load available dependencies
            for dep_id in dependency_status["available"]:
                self.logger.info(
                    f"Loading dependency: {dep_id} for plugin: {plugin_id}"
                )
                if not self.load_plugin(dep_id):
                    self.logger.error(
                        f"Failed to load dependency: {dep_id} for plugin: {plugin_id}"
                    )
                    return False

            # Check if there are missing dependencies
            if dependency_status["missing"]:
                missing = ", ".join(dependency_status["missing"])
                self.logger.error(
                    f"Plugin {plugin_id} has missing dependencies: {missing}"
                )
                return False

        # Get plugin class
        plugin_class = available_plugins[plugin_id]

        try:
            # Instantiate plugin
            plugin = plugin_class(self.service)

            # Initialize plugin
            if plugin.initialize():
                self.plugins[plugin_id] = plugin

                # Register commands
                self._register_commands(plugin)

                self.logger.info(f"Plugin loaded successfully: {plugin_id}")
                return True
            else:
                self.logger.error(f"Plugin initialization failed: {plugin_id}")
                return False

        except Exception as e:
            self.logger.error(f"Error loading plugin {plugin_id}: {e}")
            return False

    def load_plugins(self) -> bool:
        """
        Load all enabled plugins.

        Returns:
            True if all plugins were loaded successfully, False otherwise.
        """
        self.logger.info("Loading enabled plugins...")

        # Get enabled plugins from config
        enabled_plugins: List[str] = []
        auto_discover = False

        try:
            plugins_config = self.service.config.get("plugins", {})
            enabled_plugins = plugins_config.get("enabled_plugins", [])
            auto_discover = plugins_config.get("auto_discover", False)
        except Exception as e:
            self.logger.error(f"Error getting enabled plugins from config: {e}")
            return False

        # Discover available plugins
        available_plugins = self.discover_plugins()

        # Load all plugins if auto-discover is enabled
        if auto_discover:
            for plugin_id in available_plugins:
                if plugin_id not in enabled_plugins:
                    enabled_plugins.append(plugin_id)

        # Load each enabled plugin
        success = True
        for plugin_id in enabled_plugins:
            if not self.load_plugin(plugin_id):
                success = False

        return success

    def unload_plugin(self, plugin_id: str) -> bool:
        """
        Unload a plugin by ID.

        Args:
            plugin_id: The ID of the plugin to unload.

        Returns:
            True if the plugin was unloaded successfully, False otherwise.
        """
        self.logger.info(f"Unloading plugin: {plugin_id}")

        if plugin_id not in self.plugins:
            self.logger.warning(f"Plugin not loaded: {plugin_id}")
            return True

        plugin = self.plugins[plugin_id]

        try:
            # Unregister commands
            self._unregister_commands(plugin)

            # Shutdown plugin
            if plugin.shutdown():
                # Remove plugin from registry
                del self.plugins[plugin_id]
                self.logger.info(f"Plugin unloaded successfully: {plugin_id}")
                return True
            else:
                self.logger.error(f"Plugin shutdown failed: {plugin_id}")
                return False

        except Exception as e:
            self.logger.error(f"Error unloading plugin {plugin_id}: {e}")
            return False

    def unload_plugins(self) -> bool:
        """
        Unload all plugins.

        Returns:
            True if all plugins were unloaded successfully, False otherwise.
        """
        self.logger.info("Unloading all plugins...")

        success = True
        # Create a copy of the keys since we'll be modifying the dictionary
        plugin_ids = list(self.plugins.keys())

        for plugin_id in plugin_ids:
            if not self.unload_plugin(plugin_id):
                success = False

        return success

    def handle_request(self, plugin_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route a request to the appropriate plugin.

        Args:
            plugin_id: The ID of the plugin to handle the request.
            request: The request to handle.

        Returns:
            The response from the plugin.
        """
        if plugin_id not in self.plugins:
            return {
                "status": "error",
                "error": {
                    "code": "plugin_not_found",
                    "message": f"Plugin not found: {plugin_id}",
                },
            }

        plugin = self.plugins[plugin_id]
        return plugin.handle_request(request)

    def get_status(self) -> Dict[str, Any]:
        """
        Get status information for all plugins.

        Returns:
            A dictionary with status information for all plugins.
        """
        status: Dict[str, Any] = {
            "plugins": {},
            "total": len(self.plugins),
            "commands": len(self.commands),
        }

        for plugin_id, plugin in self.plugins.items():
            plugin_status = plugin.status()
            if not isinstance(plugin_status, dict):
                plugin_status = {"status": str(plugin_status)}
            plugins_dict = status["plugins"]
            assert isinstance(plugins_dict, dict)
            plugins_dict[plugin_id] = plugin_status

        return status

    def _register_commands(self, plugin: Plugin) -> None:
        """
        Register commands provided by a plugin.

        Args:
            plugin: The plugin providing the commands.
        """
        commands = plugin.get_commands()
        for command_name, handler in commands.items():
            if command_name in self.commands:
                self.logger.warning(
                    f"Command '{command_name}' already registered, overriding with plugin {plugin.id}"
                )

            self.commands[command_name] = {
                "plugin_id": plugin.id,
                "handler": handler,
            }

            self.logger.debug(
                f"Registered command '{command_name}' from plugin {plugin.id}"
            )

    def _unregister_commands(self, plugin: Plugin) -> None:
        """
        Unregister commands provided by a plugin.

        Args:
            plugin: The plugin providing the commands.
        """
        plugin_id = plugin.id
        commands_to_remove = []

        for command_name, command_info in self.commands.items():
            if command_info["plugin_id"] == plugin_id:
                commands_to_remove.append(command_name)

        for command_name in commands_to_remove:
            del self.commands[command_name]
            self.logger.debug(
                f"Unregistered command '{command_name}' from plugin {plugin_id}"
            )

    def check_plugin_dependencies(self, plugin_id: str) -> Dict[str, Any]:
        """
        Check dependencies for a plugin.

        This method checks if all dependencies for a plugin are available and loaded.

        Args:
            plugin_id: The ID of the plugin to check.

        Returns:
            A dictionary with dependency status information:
            {
                "satisfied": bool,  # Whether all dependencies are satisfied
                "missing": List[str],  # Missing dependencies
                "available": List[str],  # Available but not loaded dependencies
                "loaded": List[str],  # Loaded dependencies
            }
        """
        self.logger.debug(f"Checking dependencies for plugin: {plugin_id}")

        # Check if plugin is available
        available_plugins = self.discover_plugins()
        if plugin_id not in available_plugins:
            self.logger.error(f"Plugin not found: {plugin_id}")
            return {
                "satisfied": False,
                "missing": [],
                "available": [],
                "loaded": [],
                "error": f"Plugin not found: {plugin_id}",
            }

        # Get plugin dependencies
        plugin_dependencies = []
        try:
            # Try to get dependencies from plugin class (static property)
            plugin_class = available_plugins[plugin_id]
            if hasattr(plugin_class, "dependencies"):
                try:
                    deps_attr = getattr(plugin_class, "dependencies")
                    if not isinstance(deps_attr, property):
                        plugin_dependencies = deps_attr
                except (AttributeError, TypeError):
                    # Skip if dependencies is not accessible as static attribute
                    pass
            else:
                # Try to get dependencies from configuration
                plugins_config = self.service.config.get("plugins", {})
                plugin_config = plugins_config.get("plugins", {}).get(plugin_id, {})
                plugin_dependencies = plugin_config.get("dependencies", [])
        except Exception as e:
            self.logger.error(f"Error getting dependencies for plugin {plugin_id}: {e}")
            return {
                "satisfied": False,
                "missing": [],
                "available": [],
                "loaded": [],
                "error": f"Error getting dependencies: {str(e)}",
            }

        # Check each dependency
        missing = []
        available_not_loaded = []
        loaded = []

        for dep_id in plugin_dependencies:
            if dep_id not in available_plugins:
                missing.append(dep_id)
            elif dep_id not in self.plugins:
                available_not_loaded.append(dep_id)
            else:
                loaded.append(dep_id)

        # Determine if all dependencies are satisfied
        satisfied = len(missing) == 0 and len(available_not_loaded) == 0

        return {
            "satisfied": satisfied,
            "missing": missing,
            "available": available_not_loaded,
            "loaded": loaded,
        }
