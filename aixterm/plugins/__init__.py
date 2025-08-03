"""
AIxTerm Plugins Package

This package contains the plugin system for AIxTerm.
"""

from .base import Plugin
from .cli import handle_plugin_command, register_plugin_commands
from .manager import PluginManager
from .service import PluginServiceHandlers

__all__ = [
    "Plugin",
    "PluginManager",
    "PluginServiceHandlers",
    "register_plugin_commands",
    "handle_plugin_command",
]
