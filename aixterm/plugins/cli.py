"""
AIxTerm Plugin CLI Integration

This module provides CLI commands for managing AIxTerm plugins.
"""

import argparse
import json
import logging
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def register_plugin_commands(subparsers):
    """
    Register plugin-related commands with the AIxTerm CLI.

    Args:
        subparsers: The argparse subparsers object.
    """
    # Plugin commands
    plugin_parser = subparsers.add_parser("plugin", help="Manage AIxTerm plugins")
    plugin_subparsers = plugin_parser.add_subparsers(dest="plugin_command")

    # List plugins
    list_parser = plugin_subparsers.add_parser("list", help="List available plugins")
    list_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed plugin information"
    )

    # Show plugin info
    info_parser = plugin_subparsers.add_parser(
        "info", help="Show information about a plugin"
    )
    info_parser.add_argument("plugin_id", help="ID of the plugin")

    # Load a plugin
    load_parser = plugin_subparsers.add_parser("load", help="Load a plugin")
    load_parser.add_argument("plugin_id", help="ID of the plugin to load")

    # Unload a plugin
    unload_parser = plugin_subparsers.add_parser("unload", help="Unload a plugin")
    unload_parser.add_argument("plugin_id", help="ID of the plugin to unload")

    # Run a plugin command
    run_parser = plugin_subparsers.add_parser("run", help="Run a plugin command")
    run_parser.add_argument("plugin_id", help="ID of the plugin")
    run_parser.add_argument("command", help="Command to run")
    run_parser.add_argument(
        "--data", "-d", help="JSON data for the command", default="{}"
    )

    # Show plugin status
    status_parser = plugin_subparsers.add_parser("status", help="Show plugin status")
    status_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed status information"
    )


def handle_plugin_command(args, client):
    """
    Handle plugin-related CLI commands.

    Args:
        args: The parsed command-line arguments.
        client: The AIxTerm client instance.

    Returns:
        0 on success, non-zero on error.
    """
    if not hasattr(args, "plugin_command") or not args.plugin_command:
        from aixterm.utils import get_logger

        logger = get_logger(__name__)
        logger.error("No plugin command specified")
        logger.info("Use 'aixterm plugin --help' to see available commands")
        return 1

    try:
        if args.plugin_command == "list":
            return handle_list_plugins(args, client)
        elif args.plugin_command == "info":
            return handle_plugin_info(args, client)
        elif args.plugin_command == "load":
            return handle_load_plugin(args, client)
        elif args.plugin_command == "unload":
            return handle_unload_plugin(args, client)
        elif args.plugin_command == "run":
            return handle_run_plugin_command(args, client)
        elif args.plugin_command == "status":
            return handle_plugin_status(args, client)
        else:
            from aixterm.utils import get_logger

            logger = get_logger(__name__)
            logger.error(f"Unknown plugin command: {args.plugin_command}")
            return 1
    except Exception as e:
        from aixterm.utils import get_logger

        logger = get_logger(__name__)
        logger.error(f"Error: {e}")
        return 1


def handle_list_plugins(args, client):
    """
    Handle the 'plugin list' command.

    Args:
        args: The parsed command-line arguments.
        client: The AIxTerm client instance.

    Returns:
        0 on success, non-zero on error.
    """
    response = client.send_request("plugin.list", {})

    if response["status"] != "success":
        print(f"Error: {response.get('error', {}).get('message', 'Unknown error')}")
        return 1

    plugins = response["plugins"]
    total = response["total"]
    loaded = response["loaded"]

    print(f"Available plugins ({total} total, {loaded} loaded):")

    for plugin in plugins:
        plugin_id = plugin["id"]
        loaded_status = "loaded" if plugin.get("loaded", False) else "not loaded"

        if args.verbose and plugin.get("loaded", False):
            name = plugin.get("name", "Unknown")
            version = plugin.get("version", "Unknown")
            description = plugin.get("description", "No description")
            print(f"- {plugin_id} ({name} v{version}): {description} [{loaded_status}]")
        else:
            print(f"- {plugin_id} [{loaded_status}]")

    return 0


def handle_plugin_info(args, client):
    """
    Handle the 'plugin info' command.

    Args:
        args: The parsed command-line arguments.
        client: The AIxTerm client instance.

    Returns:
        0 on success, non-zero on error.
    """
    plugin_id = args.plugin_id
    response = client.send_request("plugin.info", {"plugin_id": plugin_id})

    if response["status"] != "success":
        print(f"Error: {response.get('error', {}).get('message', 'Unknown error')}")
        return 1

    plugin = response["plugin"]
    loaded = plugin.get("loaded", False)

    print(f"Plugin: {plugin_id}")
    print(f"Status: {'Loaded' if loaded else 'Not loaded'}")

    if loaded:
        print(f"Name: {plugin.get('name', 'Unknown')}")
        print(f"Version: {plugin.get('version', 'Unknown')}")
        print(f"Description: {plugin.get('description', 'No description')}")
        print(f"Initialized: {plugin.get('initialized', False)}")

        commands = plugin.get("commands", [])
        if commands:
            print("\nAvailable commands:")
            for command in commands:
                print(f"- {command}")

    return 0


def handle_load_plugin(args, client):
    """
    Handle the 'plugin load' command.

    Args:
        args: The parsed command-line arguments.
        client: The AIxTerm client instance.

    Returns:
        0 on success, non-zero on error.
    """
    plugin_id = args.plugin_id
    response = client.send_request("plugin.load", {"plugin_id": plugin_id})

    if response["status"] != "success":
        print(f"Error: {response.get('error', {}).get('message', 'Unknown error')}")
        return 1

    if response.get("already_loaded", False):
        print(f"Plugin '{plugin_id}' is already loaded")
    else:
        print(f"Plugin '{plugin_id}' loaded successfully")

    return 0


def handle_unload_plugin(args, client):
    """
    Handle the 'plugin unload' command.

    Args:
        args: The parsed command-line arguments.
        client: The AIxTerm client instance.

    Returns:
        0 on success, non-zero on error.
    """
    plugin_id = args.plugin_id
    response = client.send_request("plugin.unload", {"plugin_id": plugin_id})

    if response["status"] != "success":
        print(f"Error: {response.get('error', {}).get('message', 'Unknown error')}")
        return 1

    if response.get("already_unloaded", False):
        print(f"Plugin '{plugin_id}' is not loaded")
    else:
        print(f"Plugin '{plugin_id}' unloaded successfully")

    return 0


def handle_run_plugin_command(args, client):
    """
    Handle the 'plugin run' command.

    Args:
        args: The parsed command-line arguments.
        client: The AIxTerm client instance.

    Returns:
        0 on success, non-zero on error.
    """
    plugin_id = args.plugin_id
    command = args.command

    try:
        data = json.loads(args.data)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON data: {args.data}")
        return 1

    response = client.send_request(
        "plugin.command", {"plugin_id": plugin_id, "command": command, "data": data}
    )

    if response["status"] != "success":
        print(f"Error: {response.get('error', {}).get('message', 'Unknown error')}")
        return 1

    result = response["result"]
    print(json.dumps(result, indent=2))

    return 0


def handle_plugin_status(args, client):
    """
    Handle the 'plugin status' command.

    Args:
        args: The parsed command-line arguments.
        client: The AIxTerm client instance.

    Returns:
        0 on success, non-zero on error.
    """
    response = client.send_request("plugin.status", {})

    if response["status"] != "success":
        print(f"Error: {response.get('error', {}).get('message', 'Unknown error')}")
        return 1

    status = response["plugin_status"]
    total = status["total"]
    commands = status["commands"]

    print(f"Plugins: {total} loaded, {commands} commands registered")

    if args.verbose:
        plugins = status["plugins"]
        for plugin_id, plugin_status in plugins.items():
            name = plugin_status.get("name", "Unknown")
            version = plugin_status.get("version", "Unknown")
            description = plugin_status.get("description", "No description")
            initialized = plugin_status.get("initialized", False)

            print(f"\nPlugin: {plugin_id}")
            print(f"Name: {name}")
            print(f"Version: {version}")
            print(f"Description: {description}")
            print(f"Initialized: {initialized}")

    return 0
