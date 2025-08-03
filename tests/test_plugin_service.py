"""
Tests for the AIxTerm plugin service integration.
"""

from unittest.mock import MagicMock

import pytest

from aixterm.plugins import PluginServiceHandlers
from aixterm.plugins.hello import HelloPlugin


class TestPluginServiceHandlers:
    """Tests for the PluginServiceHandlers class."""

    def setup_method(self):
        """Set up the test environment."""
        # Create a mock service
        self.mock_service = MagicMock()
        self.mock_plugin_manager = MagicMock()
        self.mock_service.plugin_manager = self.mock_plugin_manager

        # Create the service handlers
        self.handlers = PluginServiceHandlers(self.mock_service)

    def test_register_handlers(self):
        """Test registering handlers."""
        handlers = self.handlers.register_handlers()

        # Check that all required handlers are registered
        assert "plugin.list" in handlers
        assert "plugin.info" in handlers
        assert "plugin.status" in handlers
        assert "plugin.load" in handlers
        assert "plugin.unload" in handlers
        assert "plugin.command" in handlers

    def test_handle_list_plugins(self):
        """Test handling plugin list requests."""
        # Mock the plugin manager's discover_plugins method
        self.mock_plugin_manager.discover_plugins.return_value = {"hello": HelloPlugin}

        # Mock the plugins attribute
        self.mock_plugin_manager.plugins = {}

        # Test with no loaded plugins
        response = self.handlers.handle_list_plugins({})
        assert response["status"] == "success"
        assert len(response["plugins"]) == 1
        assert response["plugins"][0]["id"] == "hello"
        assert response["plugins"][0]["loaded"] is False

        # Test with loaded plugins
        hello_plugin = MagicMock()
        hello_plugin.name = "Hello World"
        hello_plugin.version = "0.1.0"
        hello_plugin.description = "Test plugin"
        self.mock_plugin_manager.plugins = {"hello": hello_plugin}

        response = self.handlers.handle_list_plugins({})
        assert response["status"] == "success"
        assert len(response["plugins"]) == 1
        assert response["plugins"][0]["id"] == "hello"
        assert response["plugins"][0]["loaded"] is True
        assert response["plugins"][0]["name"] == "Hello World"
        assert response["plugins"][0]["version"] == "0.1.0"
        assert response["plugins"][0]["description"] == "Test plugin"

    def test_handle_plugin_info(self):
        """Test handling plugin info requests."""
        # Mock the plugins attribute
        hello_plugin = MagicMock()
        hello_plugin.name = "Hello World"
        hello_plugin.version = "0.1.0"
        hello_plugin.description = "Test plugin"
        hello_plugin.initialized = True
        hello_plugin.get_commands.return_value = {"hello": lambda x: x}

        self.mock_plugin_manager.plugins = {"hello": hello_plugin}

        # Test with valid loaded plugin
        response = self.handlers.handle_plugin_info({"plugin_id": "hello"})
        assert response["status"] == "success"
        assert response["plugin"]["id"] == "hello"
        assert response["plugin"]["name"] == "Hello World"
        assert response["plugin"]["version"] == "0.1.0"
        assert response["plugin"]["description"] == "Test plugin"
        assert response["plugin"]["loaded"] is True
        assert response["plugin"]["initialized"] is True
        assert "hello" in response["plugin"]["commands"]

        # Test with missing plugin_id
        response = self.handlers.handle_plugin_info({})
        assert response["status"] == "error"
        assert "missing_plugin_id" in response["error"]["code"]

        # Test with non-existent plugin
        self.mock_plugin_manager.discover_plugins.return_value = {}
        response = self.handlers.handle_plugin_info({"plugin_id": "nonexistent"})
        assert response["status"] == "error"
        assert "plugin_not_found" in response["error"]["code"]

    def test_handle_plugin_status(self):
        """Test handling plugin status requests."""
        # Mock the get_status method
        self.mock_plugin_manager.get_status.return_value = {
            "plugins": {"hello": {"name": "Hello World"}},
            "total": 1,
            "commands": 1,
        }

        response = self.handlers.handle_plugin_status({})
        assert response["status"] == "success"
        assert "plugin_status" in response
        assert response["plugin_status"]["total"] == 1
        assert response["plugin_status"]["commands"] == 1
        assert "hello" in response["plugin_status"]["plugins"]

    def test_handle_load_plugin(self):
        """Test handling plugin load requests."""
        # Mock the load_plugin method
        self.mock_plugin_manager.load_plugin.return_value = True

        # Test with valid plugin ID
        response = self.handlers.handle_load_plugin({"plugin_id": "hello"})
        assert response["status"] == "success"
        assert response["loaded"] is True
        self.mock_plugin_manager.load_plugin.assert_called_with("hello")

        # Test with already loaded plugin
        self.mock_plugin_manager.plugins = {"hello": MagicMock()}
        response = self.handlers.handle_load_plugin({"plugin_id": "hello"})
        assert response["status"] == "success"
        assert response["already_loaded"] is True

        # Test with missing plugin ID
        response = self.handlers.handle_load_plugin({})
        assert response["status"] == "error"
        assert "missing_plugin_id" in response["error"]["code"]

        # Test with failed load
        self.mock_plugin_manager.plugins = {}
        self.mock_plugin_manager.load_plugin.return_value = False
        response = self.handlers.handle_load_plugin({"plugin_id": "hello"})
        assert response["status"] == "error"
        assert "plugin_load_failed" in response["error"]["code"]

    def test_handle_unload_plugin(self):
        """Test handling plugin unload requests."""
        # Mock the unload_plugin method
        self.mock_plugin_manager.unload_plugin.return_value = True

        # Mock the plugins attribute
        self.mock_plugin_manager.plugins = {"hello": MagicMock()}

        # Test with valid plugin ID
        response = self.handlers.handle_unload_plugin({"plugin_id": "hello"})
        assert response["status"] == "success"
        assert response["unloaded"] is True
        self.mock_plugin_manager.unload_plugin.assert_called_with("hello")

        # Test with already unloaded plugin
        self.mock_plugin_manager.plugins = {}
        response = self.handlers.handle_unload_plugin({"plugin_id": "hello"})
        assert response["status"] == "success"
        assert response["already_unloaded"] is True

        # Test with missing plugin ID
        response = self.handlers.handle_unload_plugin({})
        assert response["status"] == "error"
        assert "missing_plugin_id" in response["error"]["code"]

        # Test with failed unload
        self.mock_plugin_manager.plugins = {"hello": MagicMock()}
        self.mock_plugin_manager.unload_plugin.return_value = False
        response = self.handlers.handle_unload_plugin({"plugin_id": "hello"})
        assert response["status"] == "error"
        assert "plugin_unload_failed" in response["error"]["code"]

    def test_handle_plugin_command(self):
        """Test handling plugin command requests."""
        # Mock the handle_request method
        self.mock_plugin_manager.handle_request.return_value = {
            "status": "success",
            "result": {"message": "Hello, World!"},
        }

        # Test with valid command
        response = self.handlers.handle_plugin_command(
            {"plugin_id": "hello", "command": "hello", "data": {}}
        )
        assert response["status"] == "success"
        assert response["result"]["message"] == "Hello, World!"
        self.mock_plugin_manager.handle_request.assert_called_with(
            "hello", {"command": "hello", "data": {}}
        )

        # Test with missing plugin ID
        response = self.handlers.handle_plugin_command({"command": "hello", "data": {}})
        assert response["status"] == "error"
        assert "missing_plugin_id" in response["error"]["code"]

        # Test with missing command
        response = self.handlers.handle_plugin_command(
            {"plugin_id": "hello", "data": {}}
        )
        assert response["status"] == "error"
        assert "missing_command" in response["error"]["code"]
