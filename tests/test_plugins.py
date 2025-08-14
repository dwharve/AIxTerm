"""
Tests for the AIxTerm plugin system.
"""

from unittest.mock import MagicMock

from aixterm.plugins import Plugin, PluginManager


class TestPluginBase:
    """Tests for the Plugin base class."""

    def test_plugin_base(self):
        """Test the basic functionality of the Plugin class."""
        # Create a mock service
        mock_service = MagicMock()
        mock_service.config = {
            "plugins": {"plugins": {"test": {"settings": {"key": "value"}}}}
        }

        # Create a test plugin
        class TestPlugin(Plugin):
            @property
            def id(self):
                return "test"

            @property
            def name(self):
                return "Test Plugin"

            @property
            def version(self):
                return "0.1.0"

        plugin = TestPlugin(mock_service)

        # Test basic properties
        assert plugin.id == "test"
        assert plugin.name == "Test Plugin"
        assert plugin.version == "0.1.0"
        assert "No description" in plugin.description

        # Test config loading
        assert plugin.config == {"key": "value"}

        # Test initialization
        assert plugin.initialized is False
        assert plugin.initialize() is True
        assert plugin.initialized is True

        # Test shutdown
        assert plugin.shutdown() is True
        assert plugin.initialized is False

        # Test commands
        assert plugin.get_commands() == {}

        # Test status
        status = plugin.status()
        assert status["id"] == "test"
        assert status["name"] == "Test Plugin"
        assert status["version"] == "0.1.0"
        assert status["initialized"] is False

        # Test request handling with unknown command
        response = plugin.handle_request({"command": "unknown", "data": {}})
        assert response["status"] == "error"
        assert "unknown_command" in response["error"]["code"]

        # Add a test command
        def test_command(data):
            return {"result": "success"}

        plugin.get_commands = lambda: {"test_cmd": test_command}

        # Test request handling with known command
        response = plugin.handle_request({"command": "test_cmd", "data": {}})
        assert response["status"] == "success"
        assert response["result"]["result"] == "success"


class TestPluginManager:
    """Tests for the PluginManager."""

    def test_plugin_manager(self):
        """Test the basic functionality of the PluginManager."""

        # Create a mock test plugin class
        class MockTestPlugin(Plugin):
            @property
            def id(self):
                return "mock_test"

            @property
            def name(self):
                return "Mock Test Plugin"

            @property
            def version(self):
                return "0.1.0"

            def get_commands(self):
                return {"test": lambda data: {"message": "Test successful!"}}

        # Create a mock service
        mock_service = MagicMock()
        mock_service.config = {
            "plugins": {
                "enabled_plugins": ["mock_test"],
                "auto_discover": False,
                "plugins": {"mock_test": {"settings": {}}},
            }
        }

        # Create the plugin manager
        manager = PluginManager(mock_service)

        # Mock the discover_plugins method to return our test plugin
        manager.discover_plugins = MagicMock(return_value={"mock_test": MockTestPlugin})

        # Test plugin discovery
        plugins = manager.discover_plugins()
        assert "mock_test" in plugins

        # Test loading a specific plugin
        assert manager.load_plugin("mock_test") is True
        assert "mock_test" in manager.plugins
        assert isinstance(manager.plugins["mock_test"], MockTestPlugin)

        # Test loading all plugins
        manager.unload_plugins()
        assert manager.load_plugins() is True
        assert "mock_test" in manager.plugins

        # Test plugin status
        status = manager.get_status()
        assert "mock_test" in status["plugins"]
        assert status["total"] == 1

        # Test request handling
        response = manager.handle_request("mock_test", {"command": "test", "data": {}})
        assert response["status"] == "success"
        assert response["result"]["message"] == "Test successful!"

        # Test unloading a specific plugin
        assert manager.unload_plugin("mock_test") is True
        assert "mock_test" not in manager.plugins

        # Test unloading all plugins
        manager.load_plugin("mock_test")
        assert manager.unload_plugins() is True
        assert len(manager.plugins) == 0

    def test_plugin_dependencies(self):
        """Test plugin dependency management."""
        # Create a mock service
        mock_service = MagicMock()
        mock_service.config = {
            "plugins": {
                "enabled_plugins": ["plugin1", "plugin2"],
                "plugins": {"plugin1": {"dependencies": ["plugin2", "plugin3"]}},
            }
        }

        # Create plugin classes with dependencies
        class Plugin1(Plugin):
            @property
            def id(self):
                return "plugin1"

            @property
            def name(self):
                return "Plugin 1"

            @property
            def version(self):
                return "0.1.0"

        class Plugin2(Plugin):
            @property
            def id(self):
                return "plugin2"

            @property
            def name(self):
                return "Plugin 2"

            @property
            def version(self):
                return "0.1.0"

        # Create the plugin manager
        manager = PluginManager(mock_service)

        # Mock the discover_plugins method
        manager.discover_plugins = MagicMock(
            return_value={
                "plugin1": Plugin1,
                "plugin2": Plugin2,
            }
        )

        # Test dependency checking with no plugins loaded
        status = manager.check_plugin_dependencies("plugin1")
        assert status["satisfied"] is False
        assert "plugin2" in status["available"]
        assert "plugin3" in status["missing"]
        assert len(status["loaded"]) == 0

        # Load plugin2
        manager.plugins = {"plugin2": Plugin2(mock_service)}

        # Test dependency checking with one dependency loaded
        status = manager.check_plugin_dependencies("plugin1")
        assert status["satisfied"] is False
        assert len(status["available"]) == 0
        assert "plugin3" in status["missing"]
        assert "plugin2" in status["loaded"]

        # Test dependency checking with non-existent plugin
        status = manager.check_plugin_dependencies("nonexistent")
        assert status["satisfied"] is False
        assert "error" in status
