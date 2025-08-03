"""
Tests for the AIxTerm plugin CLI integration.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from aixterm.mcp_client import MCPServer
from aixterm.plugins.cli import (
    handle_list_plugins,
    handle_load_plugin,
    handle_plugin_command,
    handle_plugin_info,
    handle_plugin_status,
    handle_run_plugin_command,
    handle_unload_plugin,
    register_plugin_commands,
)
from tests.conftest import mock_coro


class TestPluginCLI:
    """Tests for the plugin CLI integration."""

    def setup_method(self):
        """Set up the test environment."""
        self.mock_client = MagicMock()
        self.mock_subparsers = MagicMock()

    def test_register_plugin_commands(self):
        """Test registering plugin commands."""
        # Mock coroutines to avoid warnings
        with (
            patch.object(MCPServer, "_initialize_session", mock_coro()),
            patch.object(MCPServer, "_list_tools_async", mock_coro()),
            patch.object(MCPServer, "_call_tool_async", mock_coro()),
            patch.object(MCPServer, "_shielded_cleanup_session", mock_coro()),
        ):
            register_plugin_commands(self.mock_subparsers)

            # Verify that the plugin parser was created
            self.mock_subparsers.add_parser.assert_called_with(
                "plugin", help="Manage AIxTerm plugins"
            )

    def test_handle_plugin_command_missing(self):
        """Test handling plugin command with missing subcommand."""
        # Mock coroutines to avoid warnings
        with (
            patch.object(MCPServer, "_initialize_session", mock_coro()),
            patch.object(MCPServer, "_list_tools_async", mock_coro()),
            patch.object(MCPServer, "_call_tool_async", mock_coro()),
            patch.object(MCPServer, "_shielded_cleanup_session", mock_coro()),
        ):
            args = MagicMock()
            delattr(args, "plugin_command")

            result = handle_plugin_command(args, self.mock_client)
            assert result != 0  # Should return non-zero for error

    def test_handle_list_plugins(self):
        """Test handling the list plugins command."""
        args = MagicMock()
        args.verbose = False

        # Mock the client response
        self.mock_client.send_request.return_value = {
            "status": "success",
            "plugins": [
                {
                    "id": "hello",
                    "loaded": True,
                    "name": "Hello World",
                    "version": "0.1.0",
                },
                {"id": "other", "loaded": False},
            ],
            "total": 2,
            "loaded": 1,
        }

        result = handle_list_plugins(args, self.mock_client)
        assert result == 0  # Should return 0 for success

        # Test with verbose flag
        args.verbose = True
        result = handle_list_plugins(args, self.mock_client)
        assert result == 0

        # Test with error response
        self.mock_client.send_request.return_value = {
            "status": "error",
            "error": {"message": "Test error"},
        }

        result = handle_list_plugins(args, self.mock_client)
        assert result != 0  # Should return non-zero for error

    def test_handle_plugin_info(self):
        """Test handling the plugin info command."""
        args = MagicMock()
        args.plugin_id = "hello"

        # Mock the client response for a loaded plugin
        self.mock_client.send_request.return_value = {
            "status": "success",
            "plugin": {
                "id": "hello",
                "name": "Hello World",
                "version": "0.1.0",
                "description": "A test plugin",
                "loaded": True,
                "initialized": True,
                "commands": ["hello", "hello_name"],
            },
        }

        result = handle_plugin_info(args, self.mock_client)
        assert result == 0  # Should return 0 for success

        # Mock the client response for a not loaded plugin
        self.mock_client.send_request.return_value = {
            "status": "success",
            "plugin": {
                "id": "hello",
                "loaded": False,
            },
        }

        result = handle_plugin_info(args, self.mock_client)
        assert result == 0  # Should return 0 for success

        # Test with error response
        self.mock_client.send_request.return_value = {
            "status": "error",
            "error": {"message": "Test error"},
        }

        result = handle_plugin_info(args, self.mock_client)
        assert result != 0  # Should return non-zero for error

    def test_handle_load_plugin(self):
        """Test handling the load plugin command."""
        args = MagicMock()
        args.plugin_id = "hello"

        # Mock the client response for a successful load
        self.mock_client.send_request.return_value = {
            "status": "success",
            "message": "Plugin loaded: hello",
            "loaded": True,
        }

        result = handle_load_plugin(args, self.mock_client)
        assert result == 0  # Should return 0 for success

        # Mock the client response for an already loaded plugin
        self.mock_client.send_request.return_value = {
            "status": "success",
            "message": "Plugin already loaded: hello",
            "already_loaded": True,
        }

        result = handle_load_plugin(args, self.mock_client)
        assert result == 0  # Should return 0 for success

        # Test with error response
        self.mock_client.send_request.return_value = {
            "status": "error",
            "error": {"message": "Test error"},
        }

        result = handle_load_plugin(args, self.mock_client)
        assert result != 0  # Should return non-zero for error

    def test_handle_unload_plugin(self):
        """Test handling the unload plugin command."""
        args = MagicMock()
        args.plugin_id = "hello"

        # Mock the client response for a successful unload
        self.mock_client.send_request.return_value = {
            "status": "success",
            "message": "Plugin unloaded: hello",
            "unloaded": True,
        }

        result = handle_unload_plugin(args, self.mock_client)
        assert result == 0  # Should return 0 for success

        # Mock the client response for a plugin that's not loaded
        self.mock_client.send_request.return_value = {
            "status": "success",
            "message": "Plugin not loaded: hello",
            "already_unloaded": True,
        }

        result = handle_unload_plugin(args, self.mock_client)
        assert result == 0  # Should return 0 for success

        # Test with error response
        self.mock_client.send_request.return_value = {
            "status": "error",
            "error": {"message": "Test error"},
        }

        result = handle_unload_plugin(args, self.mock_client)
        assert result != 0  # Should return non-zero for error

    def test_handle_run_plugin_command(self):
        """Test handling the run plugin command."""
        args = MagicMock()
        args.plugin_id = "hello"
        args.command = "hello_name"
        args.data = '{"name": "Alice"}'

        # Mock coroutines to avoid warnings
        with (
            patch.object(MCPServer, "_initialize_session", mock_coro()),
            patch.object(MCPServer, "_call_tool_async", mock_coro()),
            patch.object(MCPServer, "_list_tools_async", mock_coro()),
            patch.object(MCPServer, "_shielded_cleanup_session", mock_coro()),
        ):

            # Mock the client response for a successful command execution
            self.mock_client.send_request.return_value = {
                "status": "success",
                "result": {"message": "Hello, Alice!"},
            }

            result = handle_run_plugin_command(args, self.mock_client)
            assert result == 0  # Should return 0 for success

        # Test with invalid JSON data
        args.data = "{invalid json}"
        result = handle_run_plugin_command(args, self.mock_client)
        assert result != 0  # Should return non-zero for error

        # Test with error response
        args.data = "{}"
        self.mock_client.send_request.return_value = {
            "status": "error",
            "error": {"message": "Test error"},
        }

        result = handle_run_plugin_command(args, self.mock_client)
        assert result != 0  # Should return non-zero for error

    def test_handle_plugin_status(self):
        """Test handling the plugin status command."""
        args = MagicMock()
        args.verbose = False

        # Mock the client response
        self.mock_client.send_request.return_value = {
            "status": "success",
            "plugin_status": {
                "total": 1,
                "commands": 2,
                "plugins": {
                    "hello": {
                        "name": "Hello World",
                        "version": "0.1.0",
                        "description": "A test plugin",
                        "initialized": True,
                    }
                },
            },
        }

        result = handle_plugin_status(args, self.mock_client)
        assert result == 0  # Should return 0 for success

        # Test with verbose flag
        args.verbose = True
        result = handle_plugin_status(args, self.mock_client)
        assert result == 0

        # Test with error response
        self.mock_client.send_request.return_value = {
            "status": "error",
            "error": {"message": "Test error"},
        }

        result = handle_plugin_status(args, self.mock_client)
        assert result != 0  # Should return non-zero for error
