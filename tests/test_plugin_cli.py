"""Tests for the AIxTerm plugin CLI integration."""

from unittest.mock import MagicMock

from aixterm.plugins.cli import handle_plugin_status


class TestPluginCLI:
    """Test cases for plugin CLI functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock()

    def test_handle_plugin_status_success(self):
        """Test successful plugin status handling."""
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

    def test_handle_plugin_status_error(self):
        """Test error handling in plugin status."""
        args = MagicMock()
        args.verbose = False

        # Test with error response
        self.mock_client.send_request.return_value = {
            "status": "error",
            "error": {"message": "Test error"},
        }

        result = handle_plugin_status(args, self.mock_client)
        assert result != 0  # Should return non-zero for error
