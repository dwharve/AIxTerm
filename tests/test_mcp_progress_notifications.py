#!/usr/bin/env python3
"""
Comprehensive unit tests for MCP progress notification functionality.
"""

import os
import sys
import time
import unittest
from unittest.mock import Mock, patch

# Add aixterm to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aixterm.mcp_client import (  # noqa: E402
    MCPClient,
    MCPError,
    MCPServer,
    ProgressCallback,
    ProgressParams,
)


class TestProgressParams(unittest.TestCase):
    """Test ProgressParams dataclass."""

    def test_progress_params_creation(self):
        """Test creating ProgressParams with all fields."""
        params = ProgressParams(
            progress_token="test-token", progress=50, total=100, message="Test progress"
        )

        self.assertEqual(params.progress_token, "test-token")
        self.assertEqual(params.progress, 50)
        self.assertEqual(params.total, 100)
        self.assertEqual(params.message, "Test progress")

    def test_progress_params_minimal(self):
        """Test creating ProgressParams with minimal fields."""
        params = ProgressParams(progress_token=123, progress=75)

        self.assertEqual(params.progress_token, 123)
        self.assertEqual(params.progress, 75)
        self.assertIsNone(params.total)
        self.assertIsNone(params.message)


class TestProgressCallback(unittest.TestCase):
    """Test ProgressCallback class."""

    def test_callback_creation(self):
        """Test creating a progress callback."""
        callback_func = Mock()
        callback = ProgressCallback(callback_func, timeout=60.0)

        self.assertEqual(callback.callback, callback_func)
        self.assertEqual(callback.timeout, 60.0)
        self.assertIsInstance(callback.start_time, float)

    def test_callback_without_timeout(self):
        """Test creating a callback without timeout."""
        callback_func = Mock()
        callback = ProgressCallback(callback_func)

        self.assertIsNone(callback.timeout)
        self.assertFalse(callback.is_expired())

    def test_callback_expiration(self):
        """Test callback expiration logic."""
        callback_func = Mock()
        callback = ProgressCallback(callback_func, timeout=0.1)

        # Should not be expired immediately
        self.assertFalse(callback.is_expired())

        # Wait for expiration
        time.sleep(0.2)
        self.assertTrue(callback.is_expired())

    def test_callback_execution(self):
        """Test calling the progress callback."""
        callback_func = Mock()
        callback = ProgressCallback(callback_func)

        params = ProgressParams("token", 50, 100, "test")
        callback(params)

        callback_func.assert_called_once_with(params)

    def test_callback_error_handling(self):
        """Test error handling in callback execution."""
        callback_func = Mock(side_effect=Exception("Test error"))
        callback = ProgressCallback(callback_func)

        params = ProgressParams("token", 50)

        # Should not raise exception
        with patch("aixterm.mcp_client.get_logger") as mock_logger:
            mock_log = Mock()
            mock_logger.return_value = mock_log
            callback(params)
            mock_log.error.assert_called_once()


class TestMCPClient(unittest.TestCase):
    """Test MCPClient class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.get_mcp_servers.return_value = []
        self.client = MCPClient(self.mock_config)

    def test_client_initialization(self):
        """Test client initialization."""
        self.assertFalse(self.client._initialized)
        self.assertEqual(len(self.client.servers), 0)
        self.assertEqual(len(self.client._progress_callbacks), 0)
        self.assertIsNotNone(self.client._progress_lock)
        self.assertIsNotNone(self.client._executor)

    def test_register_progress_callback(self):
        """Test registering a progress callback."""
        callback_func = Mock()
        token = "test-token"

        self.client.register_progress_callback(token, callback_func, timeout=60.0)

        self.assertIn(token, self.client._progress_callbacks)
        callback = self.client._progress_callbacks[token]
        self.assertEqual(callback.callback, callback_func)
        self.assertEqual(callback.timeout, 60.0)

    def test_unregister_progress_callback(self):
        """Test unregistering a progress callback."""
        callback_func = Mock()
        token = "test-token"

        # Register first
        self.client.register_progress_callback(token, callback_func)
        self.assertIn(token, self.client._progress_callbacks)

        # Then unregister
        self.client.unregister_progress_callback(token)
        self.assertNotIn(token, self.client._progress_callbacks)

    def test_unregister_nonexistent_callback(self):
        """Test unregistering a non-existent callback."""
        # Should not raise an exception
        self.client.unregister_progress_callback("nonexistent")

    def test_handle_progress_notification(self):
        """Test handling progress notifications."""
        callback_func = Mock()
        token = "test-token"

        self.client.register_progress_callback(token, callback_func)

        notification = {
            "method": "notifications/progress",
            "params": {
                "progressToken": token,
                "progress": 75,
                "total": 100,
                "message": "Test progress",
            },
        }

        self.client.handle_progress_notification(notification)

        # Verify callback was called with correct parameters
        callback_func.assert_called_once()
        args = callback_func.call_args[0]
        params = args[0]
        self.assertEqual(params.progress_token, token)
        self.assertEqual(params.progress, 75)
        self.assertEqual(params.total, 100)
        self.assertEqual(params.message, "Test progress")

    def test_handle_progress_notification_no_token(self):
        """Test handling progress notification without token."""
        notification = {"method": "notifications/progress", "params": {"progress": 75}}

        with patch.object(self.client.logger, "warning") as mock_warning:
            self.client.handle_progress_notification(notification)
            mock_warning.assert_called_with(
                "Received progress notification without token"
            )

    def test_handle_progress_notification_no_callback(self):
        """Test handling progress notification for unregistered token."""
        notification = {
            "method": "notifications/progress",
            "params": {"progressToken": "unknown-token", "progress": 75},
        }

        with patch.object(self.client.logger, "debug") as mock_debug:
            self.client.handle_progress_notification(notification)
            mock_debug.assert_called_with(
                "No callback registered for progress token: unknown-token"
            )

    def test_handle_progress_notification_expired_callback(self):
        """Test handling progress notification for expired callback."""
        callback_func = Mock()
        token = "test-token"

        # Register callback with very short timeout
        self.client.register_progress_callback(token, callback_func, timeout=0.01)

        # Wait for expiration
        time.sleep(0.02)

        notification = {
            "method": "notifications/progress",
            "params": {"progressToken": token, "progress": 75},
        }

        self.client.handle_progress_notification(notification)

        # Callback should have been removed and not called
        callback_func.assert_not_called()
        self.assertNotIn(token, self.client._progress_callbacks)

    def test_handle_progress_notification_exception(self):
        """Test handling exception in progress notification."""
        notification = {}  # Invalid notification

        with patch.object(self.client.logger, "warning") as mock_warning:
            self.client.handle_progress_notification(notification)
            mock_warning.assert_called_once()

    def test_cleanup_expired_callbacks(self):
        """Test cleanup of expired callbacks."""
        callback1 = Mock()
        callback2 = Mock()

        # Register callbacks with different timeouts
        self.client.register_progress_callback("token1", callback1, timeout=0.01)
        self.client.register_progress_callback("token2", callback2, timeout=60.0)

        # Wait for first callback to expire
        time.sleep(0.02)

        self.client.cleanup_expired_callbacks()

        # First callback should be removed, second should remain
        self.assertNotIn("token1", self.client._progress_callbacks)
        self.assertIn("token2", self.client._progress_callbacks)

    @patch("aixterm.mcp_client.MCPServer")
    def test_initialize_with_servers(self, mock_server_class):
        """Test initializing client with servers."""
        mock_server = Mock()
        mock_server_class.return_value = mock_server

        self.mock_config.get_mcp_servers.return_value = [
            {"name": "test-server", "command": ["echo"], "auto_start": True}
        ]

        self.client.initialize()

        # Verify server was created and started
        mock_server_class.assert_called_once()
        mock_server.start.assert_called_once()
        self.assertTrue(self.client._initialized)
        self.assertIn("test-server", self.client.servers)

    @patch("aixterm.mcp_client.MCPServer")
    def test_initialize_server_without_auto_start(self, mock_server_class):
        """Test initializing server without auto_start."""
        mock_server = Mock()
        mock_server_class.return_value = mock_server

        self.mock_config.get_mcp_servers.return_value = [
            {"name": "test-server", "command": ["echo"], "auto_start": False}
        ]

        self.client.initialize()

        # Verify server was created but not started
        mock_server_class.assert_called_once()
        mock_server.start.assert_not_called()
        self.assertTrue(self.client._initialized)
        self.assertIn("test-server", self.client.servers)

    @patch("aixterm.mcp_client.MCPServer")
    def test_call_tool_with_progress(self, mock_server_class):
        """Test calling tool with progress callback."""
        mock_server = Mock()
        mock_server.is_running.return_value = True
        mock_server.call_tool.return_value = {"result": "success"}
        mock_server_class.return_value = mock_server

        self.mock_config.get_mcp_servers.return_value = [
            {"name": "test-server", "command": ["echo"]}
        ]

        self.client.initialize()

        callback_func = Mock()

        result = self.client.call_tool_with_progress(
            "test_tool",
            "test-server",
            {"arg": "value"},
            progress_callback=callback_func,
            timeout=60.0,
        )

        # Verify tool was called with progress token
        mock_server.call_tool.assert_called_once()
        args = mock_server.call_tool.call_args[0]
        self.assertEqual(args[0], "test_tool")
        self.assertIn("_progress_token", args[1])

        # Verify result
        self.assertEqual(result, {"result": "success"})

    def test_call_tool_with_progress_no_callback(self):
        """Test calling tool with progress but no callback."""
        mock_server = Mock()
        mock_server.is_running.return_value = True
        mock_server.call_tool.return_value = {"result": "success"}

        self.client.servers["test-server"] = mock_server
        self.client._initialized = True

        result = self.client.call_tool_with_progress(
            "test_tool", "test-server", {"arg": "value"}
        )

        # Verify tool was called
        mock_server.call_tool.assert_called_once()
        self.assertEqual(result, {"result": "success"})

    def test_get_available_tools_server_error(self):
        """Test getting tools when server has an error."""
        mock_server = Mock()
        mock_server.is_running.return_value = True
        mock_server.list_tools.side_effect = Exception("Server error")

        self.client.servers["test-server"] = mock_server
        self.client._initialized = True

        with patch.object(self.client.logger, "error") as mock_error:
            tools = self.client.get_available_tools()
            mock_error.assert_called_once()
            self.assertEqual(tools, [])

    def test_call_tool_error(self):
        """Test error handling in call_tool."""
        mock_server = Mock()
        mock_server.is_running.return_value = True
        mock_server.call_tool.side_effect = Exception("Tool error")

        self.client.servers["test-server"] = mock_server
        self.client._initialized = True

        with self.assertRaises(MCPError):
            self.client.call_tool("test_tool", "test-server", {})

    def test_shutdown_with_server_error(self):
        """Test shutdown when server stop fails."""
        mock_server = Mock()
        mock_server.stop.side_effect = Exception("Stop error")

        self.client.servers["test-server"] = mock_server
        self.client._initialized = True

        with patch.object(self.client.logger, "error") as mock_error:
            self.client.shutdown()
            mock_error.assert_called_once()

    def test_get_server_status(self):
        """Test getting server status."""
        mock_server = Mock()
        mock_server.is_running.return_value = True
        mock_server.get_pid.return_value = 1234
        mock_server.get_uptime.return_value = 60.0
        mock_server.list_tools.return_value = [{"name": "tool1"}, {"name": "tool2"}]

        self.client.servers["test-server"] = mock_server

        status = self.client.get_server_status()

        expected = {
            "test-server": {
                "running": True,
                "pid": 1234,
                "uptime": 60.0,
                "tool_count": 2,
            }
        }

        self.assertEqual(status, expected)

    def test_get_server_status_not_running(self):
        """Test getting server status when not running."""
        mock_server = Mock()
        mock_server.is_running.return_value = False
        mock_server.get_pid.return_value = None
        mock_server.get_uptime.return_value = None

        self.client.servers["test-server"] = mock_server

        status = self.client.get_server_status()

        expected = {
            "test-server": {
                "running": False,
                "pid": None,
                "uptime": None,
                "tool_count": 0,
            }
        }

        self.assertEqual(status, expected)

    def test_shutdown(self):
        """Test client shutdown."""
        # Add a mock server
        mock_server = Mock()
        self.client.servers["test-server"] = mock_server

        # Add a mock callback
        self.client._progress_callbacks["token"] = Mock()

        self.client.shutdown()

        # Verify server was stopped
        mock_server.stop.assert_called_once()

        # Verify cleanup
        self.assertEqual(len(self.client.servers), 0)
        self.assertEqual(len(self.client._progress_callbacks), 0)
        self.assertFalse(self.client._initialized)


class TestMCPServer(unittest.TestCase):
    """Test MCPServer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_logger = Mock()
        self.mock_client = Mock()
        self.config = {
            "name": "test-server",
            "command": ["python", "-c", "print('test')"],
            "args": [],
            "env": {},
        }
        self.server = MCPServer(self.config, self.mock_logger, self.mock_client)

    def test_server_initialization(self):
        """Test server initialization."""
        self.assertEqual(self.server.config, self.config)
        self.assertEqual(self.server.logger, self.mock_logger)
        self.assertEqual(self.server.mcp_client, self.mock_client)
        self.assertIsNone(self.server.process)
        self.assertFalse(self.server._initialized)

    def test_is_running_false(self):
        """Test is_running when server is not running."""
        self.assertFalse(self.server.is_running())

    @patch("subprocess.Popen")
    def test_start_server_success(self, mock_popen):
        """Test successfully starting a server."""
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running
        mock_process.stdin = Mock()
        mock_process.stdout = Mock()
        mock_process.stdout.readline.return_value = (
            '{"jsonrpc":"2.0","id":1,"result":{}}'
        )
        mock_popen.return_value = mock_process

        with patch.object(self.server, "send_request") as mock_send_request:
            mock_send_request.return_value = {"capabilities": {}}
            with patch.object(self.server, "send_notification"):
                with patch.object(self.server, "_start_notification_handler"):
                    self.server.start()

        self.assertTrue(self.server._initialized)
        self.assertIsNotNone(self.server.process)

    @patch("subprocess.Popen")
    def test_start_server_failure(self, mock_popen):
        """Test server start failure."""
        mock_process = Mock()
        mock_process.poll.return_value = 1  # Process failed
        mock_process.stderr = Mock()
        mock_process.stderr.read.return_value = "Error starting server"
        mock_popen.return_value = mock_process

        with self.assertRaises(MCPError):
            self.server.start()

    @patch("subprocess.Popen")
    def test_start_server_exception(self, mock_popen):
        """Test server start with subprocess exception."""
        mock_popen.side_effect = Exception("Process creation failed")

        with self.assertRaises(MCPError):
            self.server.start()

    def test_start_server_already_running(self):
        """Test starting server that's already running."""
        self.server.process = Mock()
        self.server.process.poll.return_value = None  # Still running

        # Should return without doing anything
        self.server.start()

    def test_stop_server(self):
        """Test stopping a server."""
        mock_process = Mock()
        self.server.process = mock_process
        self.server._initialized = True

        self.server.stop()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)
        self.assertIsNone(self.server.process)
        self.assertFalse(self.server._initialized)

    def test_stop_server_no_process(self):
        """Test stopping server when no process exists."""
        # Should not raise any errors
        self.server.stop()

    def test_stop_server_exception(self):
        """Test stop server with exception during termination."""
        mock_process = Mock()
        mock_process.terminate.side_effect = Exception("Terminate failed")
        self.server.process = mock_process

        with patch.object(self.server.logger, "error"):
            self.server.stop()

    def test_get_pid_no_process(self):
        """Test getting PID when no process."""
        self.assertIsNone(self.server.get_pid())

    def test_get_pid_with_process(self):
        """Test getting PID with process."""
        mock_process = Mock()
        mock_process.pid = 1234
        self.server.process = mock_process

        self.assertEqual(self.server.get_pid(), 1234)

    def test_get_uptime_no_start_time(self):
        """Test getting uptime when no start time."""
        self.assertIsNone(self.server.get_uptime())

    def test_get_uptime_with_start_time(self):
        """Test getting uptime with start time."""
        start_time = time.time() - 60  # 60 seconds ago
        self.server.start_time = start_time

        uptime = self.server.get_uptime()
        self.assertIsNotNone(uptime)
        assert uptime is not None  # Type narrowing
        self.assertTrue(uptime >= 59.0)  # Allow some variance

    def test_send_request_not_running(self):
        """Test sending request when server not running."""
        with self.assertRaises(MCPError):
            self.server.send_request("test/method")

    def test_send_request_no_process_stdin(self):
        """Test sending request when process has no stdin."""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.stdin = None
        self.server.process = mock_process

        with self.assertRaises(MCPError):
            self.server.send_request("test/method")

    def test_send_request_no_response(self):
        """Test sending request with no response."""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.stdin = Mock()
        mock_process.stdout = Mock()
        mock_process.stdout.readline.return_value = ""
        self.server.process = mock_process

        with self.assertRaises(MCPError):
            self.server.send_request("test/method")

    def test_send_request_write_exception(self):
        """Test exception during request writing."""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.stdin = Mock()
        mock_process.stdin.write.side_effect = Exception("Write failed")
        self.server.process = mock_process

        with self.assertRaises(MCPError):
            self.server.send_request("test/method")

    @patch("json.loads")
    def test_send_request_success(self, mock_json_loads):
        """Test successful request sending."""
        mock_process = Mock()
        mock_process.stdin = Mock()
        mock_process.stdout = Mock()
        mock_process.stdout.readline.return_value = '{"result": "test"}'
        mock_process.stdout.fileno.return_value = 1
        mock_process.poll.return_value = None

        mock_json_loads.return_value = {"result": "test"}

        self.server.process = mock_process

        with patch("select.select", return_value=([mock_process.stdout], [], [])):
            result = self.server.send_request("test/method", {"param": "value"})

        self.assertEqual(result, "test")
        mock_process.stdin.write.assert_called_once()
        mock_process.stdin.flush.assert_called_once()

    @patch("json.loads")
    def test_send_request_error_response(self, mock_json_loads):
        """Test request with error response."""
        mock_process = Mock()
        mock_process.stdin = Mock()
        mock_process.stdout = Mock()
        mock_process.stdout.readline.return_value = '{"error": "test error"}'
        mock_process.poll.return_value = None

        mock_json_loads.return_value = {"error": "test error"}

        self.server.process = mock_process

        with self.assertRaises(MCPError):
            self.server.send_request("test/method")

    def test_send_notification_not_running(self):
        """Test sending notification when not running."""
        with self.assertRaises(MCPError):
            self.server.send_notification("test/notification")

    def test_list_tools_not_running(self):
        """Test listing tools when server not running."""
        tools = self.server.list_tools()
        self.assertEqual(tools, [])

    @patch("time.time")
    def test_list_tools_cached(self, mock_time):
        """Test listing tools with caching."""
        mock_time.return_value = 1000

        # Set up cache using setattr
        cached_tools = [{"name": "cached_tool"}]
        setattr(self.server, "_tools_brief_cache", cached_tools)
        setattr(
            self.server, "_tools_brief_cache_time", 950
        )  # Within 60 second cache window

        tools = self.server.list_tools(brief=True)

        self.assertEqual(tools, cached_tools)

    def test_list_tools_error(self):
        """Test listing tools with server error."""
        with patch.object(self.server, "send_request") as mock_send_request:
            mock_send_request.side_effect = Exception("Server error")

            with patch.object(self.server.logger, "error"):
                tools = self.server.list_tools()
                self.assertEqual(tools, [])

    def test_call_tool_success(self):
        """Test calling a tool successfully."""
        with patch.object(self.server, "send_request") as mock_send_request:
            mock_send_request.return_value = {"content": [{"text": "result"}]}

            result = self.server.call_tool("test_tool", {"arg": "value"})

            mock_send_request.assert_called_once_with(
                "tools/call", {"name": "test_tool", "arguments": {"arg": "value"}}
            )
            self.assertEqual(result, {"content": [{"text": "result"}]})


class TestIntegration(unittest.TestCase):
    """Integration tests for progress notifications."""

    def test_end_to_end_progress_flow(self):
        """Test complete progress notification flow."""
        mock_config = Mock()
        mock_config.get_mcp_servers.return_value = []

        client = MCPClient(mock_config)

        # Track progress updates
        progress_updates = []

        def progress_callback(params: ProgressParams):
            progress_updates.append(params)

        # Register callback
        token = "test-token"
        client.register_progress_callback(token, progress_callback)

        # Simulate progress notifications
        for i in range(0, 101, 25):
            notification = {
                "method": "notifications/progress",
                "params": {
                    "progressToken": token,
                    "progress": i,
                    "total": 100,
                    "message": f"Step {i//25 + 1}",
                },
            }
            client.handle_progress_notification(notification)

        # Verify all progress updates were received
        self.assertEqual(len(progress_updates), 5)

        for i, update in enumerate(progress_updates):
            expected_progress = i * 25
            self.assertEqual(update.progress, expected_progress)
            self.assertEqual(update.total, 100)
            self.assertEqual(update.message, f"Step {i + 1}")

        # Cleanup
        client.unregister_progress_callback(token)
        self.assertNotIn(token, client._progress_callbacks)


if __name__ == "__main__":
    # Run with coverage if available
    try:
        import coverage

        cov = coverage.Coverage()
        cov.start()

        unittest.main(exit=False, verbosity=2)

        cov.stop()
        cov.save()

        print("\n" + "=" * 50)
        print("COVERAGE REPORT")
        print("=" * 50)
        cov.report(show_missing=True)

    except ImportError:
        print("Coverage module not available, running tests without coverage")
        unittest.main(verbosity=2)
