"""
AIxTerm Plugin Manager

This module provides the plugin management system for AIxTerm, enabling
the discovery, loading, and management of plugins.
"""

import asyncio
import importlib
import importlib.metadata
import importlib.util
import logging
import os
import pkgutil
import sys
from typing import Any, Dict, Optional, Type, TypeVar

# Type for plugin classes
T = TypeVar("T")

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Manager for AIxTerm plugins.

    This class handles plugin discovery, loading, and management.
    """

    def __init__(self, service):
        """
        Initialize the plugin manager.

        Args:
            service: The parent AIxTerm service.
        """
        self.service = service
        self.config = service.config.get("plugins", {})
        self.enabled_plugins = self.config.get("enabled_plugins", [])
        self.plugin_directory = self._get_plugin_directory()
        self.auto_discover = self.config.get("auto_discover", True)

        # Plugin storage
        self.plugins = {}  # id -> plugin instance
        self.commands = {}  # command_name -> (plugin_id, handler)

        # Discovered plugin classes
        self._discovered_plugins = {}  # id -> plugin class

    def _get_plugin_directory(self) -> Optional[str]:
        """
        Get the plugin directory from configuration or use default.

        Returns:
            The plugin directory path, or None if not configured.
        """
        plugin_dir = self.config.get("plugin_directory")
        if plugin_dir:
            return str(os.path.expanduser(plugin_dir))

        # Default location in user's home directory
        return str(os.path.expanduser("~/.aixterm/plugins"))

    async def discover_plugins(self) -> Dict[str, Type]:
        """
        Discover available plugins from multiple sources.

        Returns:
            A dictionary mapping plugin IDs to plugin classes.
        """
        plugins = {}

        # 1. Built-in plugins
        builtin_plugins = await self._discover_builtin_plugins()
        plugins.update(builtin_plugins)

        # 2. Installed plugins (via pip/setuptools entry points)
        if self.auto_discover:
            installed_plugins = await self._discover_installed_plugins()
            plugins.update(installed_plugins)

        # 3. User plugins from specified directory
        if self.plugin_directory and os.path.exists(self.plugin_directory):
            user_plugins = await self._discover_user_plugins(self.plugin_directory)
            plugins.update(user_plugins)

        logger.info(f"Discovered {len(plugins)} plugins: {', '.join(plugins.keys())}")
        return plugins

    async def _discover_builtin_plugins(self) -> Dict[str, Type]:
        """
        Discover built-in plugins from the aixterm.plugins package.

        Returns:
            A dictionary mapping plugin IDs to plugin classes.
        """
        plugin_dict = {}

        try:
            from ..plugins import base

            plugin_base = base.Plugin

            # Import all modules in the plugins package
            from .. import plugins as plugins_module

            for _, name, is_pkg in pkgutil.iter_modules(plugins_module.__path__):
                if is_pkg:  # Only consider packages, not modules
                    try:
                        module = importlib.import_module(f"aixterm.plugins.{name}")

                        # Find plugin classes in the module
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (
                                isinstance(attr, type)
                                and issubclass(attr, plugin_base)
                                and attr != plugin_base
                            ):
                                try:
                                    plugin_instance = attr(self.service)
                                    plugin_id = plugin_instance.id
                                    plugin_dict[plugin_id] = attr
                                    logger.debug(
                                        f"Found built-in plugin: {plugin_id} ({attr.__name__})"
                                    )
                                except Exception as e:
                                    logger.warning(
                                        f"Could not get ID from plugin class {attr.__name__}: {e}"
                                    )
                    except Exception as e:
                        logger.warning(f"Error importing plugin module {name}: {e}")
        except ImportError:
            logger.debug("No built-in plugins package found")
        except Exception as e:
            logger.warning(f"Error discovering built-in plugins: {e}")

        return plugin_dict

    async def _discover_installed_plugins(self) -> Dict[str, Type]:
        """
        Discover plugins installed via pip with entry points.

        Returns:
            A dictionary mapping plugin IDs to plugin classes.
        """
        plugins = {}

        try:
            # Get plugin base class for isinstance check
            from ..plugins import base

            plugin_base = base.Plugin

            # Find entry points
            entry_points = []
            try:
                # Python 3.8+ with importlib.metadata
                entry_points = list(
                    importlib.metadata.entry_points(group="aixterm.plugins")
                )
            except (AttributeError, ImportError):
                # Fallback for older Python
                import pkg_resources

                entry_points = list(pkg_resources.iter_entry_points("aixterm.plugins"))

            # Load plugin classes from entry points
            for entry_point in entry_points:
                try:
                    plugin_class = entry_point.load()
                    if isinstance(plugin_class, type) and issubclass(
                        plugin_class, plugin_base
                    ):
                        try:
                            plugin_instance = plugin_class(self.service)
                            plugin_id = plugin_instance.id
                            plugins[plugin_id] = plugin_class
                            logger.debug(
                                f"Found installed plugin: {plugin_id} ({plugin_class.__name__})"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Could not get ID from plugin class {plugin_class.__name__}: {e}"
                            )
                except Exception as e:
                    logger.warning(
                        f"Error loading plugin from entry point {entry_point.name}: {e}"
                    )
        except ImportError:
            logger.debug("Could not import plugin base class")
        except Exception as e:
            logger.warning(f"Error discovering installed plugins: {e}")

        return plugins

    async def _discover_user_plugins(self, directory: str) -> Dict[str, Type]:
        """
        Discover plugins in user-defined directory.

        Args:
            directory: The directory to search for plugins.

        Returns:
            A dictionary mapping plugin IDs to plugin classes.
        """
        plugins = {}

        try:
            # Get plugin base class for isinstance check
            from ..plugins import base

            plugin_base = base.Plugin

            # Ensure directory is in Python path for imports
            if directory not in sys.path:
                sys.path.append(directory)

            # Find all Python files in directory
            plugin_files = []
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.endswith(".py") and not file.startswith("_"):
                        plugin_files.append(os.path.join(root, file))

            # Import modules and look for plugin classes
            for plugin_file in plugin_files:
                try:
                    module_name = os.path.splitext(os.path.basename(plugin_file))[0]
                    spec = importlib.util.spec_from_file_location(
                        module_name, plugin_file
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        # Find plugin classes in the module
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (
                                isinstance(attr, type)
                                and issubclass(attr, plugin_base)
                                and attr != plugin_base
                            ):
                                try:
                                    plugin_id = attr(self.service).id
                                    plugins[plugin_id] = attr
                                    logger.debug(
                                        f"Found user plugin: {plugin_id} ({attr.__name__})"
                                    )
                                except Exception as e:
                                    logger.warning(
                                        f"Could not get ID from plugin class {attr.__name__}: {e}"
                                    )
                except Exception as e:
                    logger.warning(f"Error importing plugin from {plugin_file}: {e}")
        except ImportError:
            logger.debug("Could not import plugin base class")
        except Exception as e:
            logger.warning(f"Error discovering user plugins: {e}")

        return plugins

    async def load_plugins(self):
        """Load all enabled plugins."""
        # Discover available plugins
        self._discovered_plugins = await self.discover_plugins()

        # Load enabled plugins
        loaded_count = 0
        for plugin_id in self.enabled_plugins:
            if await self.load_plugin(plugin_id):
                loaded_count += 1

        logger.info(f"Loaded {loaded_count} plugins")

    async def load_plugin(self, plugin_id: str) -> bool:
        """
        Load a specific plugin by ID.

        Args:
            plugin_id: The ID of the plugin to load.

        Returns:
            True if the plugin was loaded successfully, False otherwise.
        """
        if plugin_id in self.plugins:
            logger.debug(f"Plugin {plugin_id} is already loaded")
            return True

        logger.info(f"Loading plugin: {plugin_id}")

        # Check if plugin is discovered
        if plugin_id not in self._discovered_plugins:
            logger.warning(f"Plugin {plugin_id} not found")
            return False

        try:
            # Get plugin class and instantiate it
            plugin_class = self._discovered_plugins[plugin_id]
            plugin = plugin_class(self.service)

            # Initialize plugin
            success = await self._initialize_plugin(plugin)
            if not success:
                logger.warning(f"Failed to initialize plugin {plugin_id}")
                return False

            # Register plugin
            self.plugins[plugin_id] = plugin

            # Register plugin commands
            await self._register_plugin_commands(plugin)

            logger.info(f"Plugin {plugin_id} loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Error loading plugin {plugin_id}: {e}")
            return False

    async def _initialize_plugin(self, plugin) -> bool:
        """
        Initialize a plugin.

        Args:
            plugin: The plugin instance to initialize.

        Returns:
            True if initialization was successful, False otherwise.
        """
        try:
            # Check if plugin has async initialize method
            if hasattr(plugin, "initialize") and asyncio.iscoroutinefunction(
                plugin.initialize
            ):
                result = await plugin.initialize()
                return bool(result) if result is not None else True
            elif hasattr(plugin, "initialize"):
                result = plugin.initialize()
                return bool(result) if result is not None else True
            else:
                # No initialize method, assume success
                return True
        except Exception as e:
            logger.error(f"Error initializing plugin {plugin.id}: {e}")
            return False

    async def unload_plugins(self):
        """Unload all loaded plugins."""
        plugin_ids = list(self.plugins.keys())
        for plugin_id in plugin_ids:
            await self.unload_plugin(plugin_id)

    async def unload_plugin(self, plugin_id: str) -> bool:
        """
        Unload a plugin by ID.

        Args:
            plugin_id: The ID of the plugin to unload.

        Returns:
            True if the plugin was unloaded successfully, False otherwise.
        """
        if plugin_id not in self.plugins:
            logger.warning(f"Plugin {plugin_id} is not loaded")
            return False

        logger.info(f"Unloading plugin: {plugin_id}")

        try:
            # Get plugin instance
            plugin = self.plugins[plugin_id]

            # Shutdown plugin
            success = await self._shutdown_plugin(plugin)
            if not success:
                logger.warning(f"Failed to shutdown plugin {plugin_id}")
                # Continue anyway to clean up

            # Unregister plugin commands
            await self._unregister_plugin_commands(plugin)

            # Remove plugin from registry
            del self.plugins[plugin_id]

            logger.info(f"Plugin {plugin_id} unloaded successfully")
            return True

        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_id}: {e}")
            return False

    async def _shutdown_plugin(self, plugin) -> bool:
        """
        Shutdown a plugin.

        Args:
            plugin: The plugin instance to shutdown.

        Returns:
            True if shutdown was successful, False otherwise.
        """
        try:
            # Check if plugin has async shutdown method
            if hasattr(plugin, "shutdown") and asyncio.iscoroutinefunction(
                plugin.shutdown
            ):
                result = await plugin.shutdown()
                return bool(result) if result is not None else True
            elif hasattr(plugin, "shutdown"):
                result = plugin.shutdown()
                return bool(result) if result is not None else True
            else:
                # No shutdown method, assume success
                return True
        except Exception as e:
            logger.error(f"Error shutting down plugin {plugin.id}: {e}")
            return False

    async def _register_plugin_commands(self, plugin):
        """
        Register commands provided by a plugin.

        Args:
            plugin: The plugin instance.
        """
        try:
            # Get commands from plugin
            if hasattr(plugin, "get_commands") and callable(plugin.get_commands):
                commands = plugin.get_commands()
                if isinstance(commands, dict):
                    for command_name, handler in commands.items():
                        self.commands[command_name] = (plugin.id, handler)
                        logger.debug(
                            f"Registered command '{command_name}' from plugin {plugin.id}"
                        )
        except Exception as e:
            logger.error(f"Error registering commands for plugin {plugin.id}: {e}")

    async def _unregister_plugin_commands(self, plugin):
        """
        Unregister commands provided by a plugin.

        Args:
            plugin: The plugin instance.
        """
        try:
            # Remove commands associated with this plugin
            to_remove = []
            for command_name, (plugin_id, _) in self.commands.items():
                if plugin_id == plugin.id:
                    to_remove.append(command_name)

            for command_name in to_remove:
                del self.commands[command_name]
                logger.debug(
                    f"Unregistered command '{command_name}' from plugin {plugin.id}"
                )
        except Exception as e:
            logger.error(f"Error unregistering commands for plugin {plugin.id}: {e}")

    async def handle_request(self, plugin_id: str, command: str, data: Dict) -> Any:
        """
        Handle a request for a plugin.

        Args:
            plugin_id: The ID of the plugin to handle the request.
            command: The command name.
            data: The command data.

        Returns:
            The result of the command execution.

        Raises:
            ValueError: If the plugin is not loaded or the command is unknown.
        """
        # Check if plugin is loaded
        if plugin_id not in self.plugins:
            raise ValueError(f"Plugin {plugin_id} is not loaded")

        plugin = self.plugins[plugin_id]

        # Check if plugin has handle_request method
        if hasattr(plugin, "handle_request") and callable(plugin.handle_request):
            # Create request object
            request = {"command": command, "data": data}

            # Call plugin's handle_request method
            if asyncio.iscoroutinefunction(plugin.handle_request):
                return await plugin.handle_request(request)
            else:
                return plugin.handle_request(request)

        # Check if command is registered directly
        if command in self.commands and self.commands[command][0] == plugin_id:
            handler = self.commands[command][1]

            # Call handler with data
            if asyncio.iscoroutinefunction(handler):
                return await handler(data)
            else:
                return handler(data)

        raise ValueError(f"Unknown command '{command}' for plugin {plugin_id}")

    def get_status(self) -> Dict[str, Any]:
        """
        Get status information for all loaded plugins.

        Returns:
            A dictionary with plugin status information.
        """
        status = {}

        for plugin_id, plugin in self.plugins.items():
            try:
                if hasattr(plugin, "status") and callable(plugin.status):
                    plugin_status = plugin.status()
                else:
                    plugin_status = {
                        "id": plugin_id,
                        "name": getattr(plugin, "name", plugin_id),
                        "version": getattr(plugin, "version", "unknown"),
                    }

                status[plugin_id] = plugin_status
            except Exception as e:
                logger.error(f"Error getting status for plugin {plugin_id}: {e}")
                status[plugin_id] = {"id": plugin_id, "error": str(e)}

        return status
