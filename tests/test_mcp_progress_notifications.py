#!/usr/bin/env python3
"""
Comprehensive unit tests for MCP progress notification functionality.
"""

import time
import unittest
from unittest.mock import Mock, patch

from aixterm.mcp_client import (
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

        # Mock the logger
        callback.logger = Mock()

        params = ProgressParams("token", 50)

        # Should not raise exception
        callback(params)

        # Should have logged the error
        callback.logger.error.assert_called_once()


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
        self.client.register_progress_callback(token, callback_func, timeout=0.001)

        # Wait for expiration
        time.sleep(0.01)

        notification = {
            "method": "notifications/progress",
            "params": {"progressToken": token, "progress": 75},
        }

        with patch.object(self.client.logger, "debug") as mock_debug:
            self.client.handle_progress_notification(notification)
            mock_debug.assert_called_with(f"Callback for token {token} has expired")

        # Should be removed from callbacks
        self.assertNotIn(token, self.client._progress_callbacks)

    def test_handle_progress_notification_exception(self):
        """Test handling exception in progress callback."""
        callback_func = Mock(side_effect=Exception("Callback error"))
        token = "test-token"

        self.client.register_progress_callback(token, callback_func)

        notification = {
            "method": "notifications/progress",
            "params": {"progressToken": token, "progress": 75},
        }

        with patch.object(self.client.logger, "error") as mock_error:
            self.client.handle_progress_notification(notification)
            mock_error.assert_called()

    def test_cleanup_expired_callbacks(self):
        """Test cleaning up expired callbacks."""
        # Register some callbacks
        self.client.register_progress_callback("active", Mock(), timeout=60.0)
        self.client.register_progress_callback("expired", Mock(), timeout=0.001)

        # Wait for one to expire
        time.sleep(0.01)

        with patch.object(self.client.logger, "debug") as mock_debug:
            self.client.cleanup_expired_callbacks()
            mock_debug.assert_called()

        # Only active should remain
        self.assertIn("active", self.client._progress_callbacks)
        self.assertNotIn("expired", self.client._progress_callbacks)

    @patch("aixterm.mcp_client.MCPServer")
    def test_initialize_with_servers(self, mock_server_class):
        """Test initializing with servers."""
        mock_server = Mock()
        mock_server_class.return_value = mock_server

        server_config = {
            "name": "test-server",
            "command": ["python", "-c", "print('test')"],
            "auto_start": True,
        }
        self.client.config.get_mcp_servers.return_value = [server_config]

        self.client.initialize()

        self.assertTrue(self.client._initialized)
        self.assertIn("test-server", self.client.servers)
        mock_server.start.assert_called_once()

    @patch("aixterm.mcp_client.MCPServer")
    def test_initialize_server_without_auto_start(self, mock_server_class):
        """Test initializing server with auto_start=False."""
        mock_server = Mock()
        mock_server_class.return_value = mock_server

        server_config = {
            "name": "test-server",
            "command": ["python", "-c", "print('test')"],
            "auto_start": False,
        }
        self.client.config.get_mcp_servers.return_value = [server_config]

        self.client.initialize()

        self.assertTrue(self.client._initialized)
        self.assertIn("test-server", self.client.servers)
        mock_server.start.assert_not_called()

    @patch("aixterm.mcp_client.MCPServer")
    def test_call_tool_with_progress(self, mock_server_class):
        """Test calling tool with progress callback."""
        mock_server = Mock()
        mock_server.is_running.return_value = True
        mock_server.call_tool.return_value = {"result": "success"}
        mock_server_class.return_value = mock_server

        self.client.servers["test-server"] = mock_server
        self.client._initialized = True

        callback_func = Mock()

        result = self.client.call_tool_with_progress(
            "test_tool",
            "test-server",
            {"arg": "value"},
            progress_callback=callback_func,
            timeout=60.0,
        )

        # Verify tool was called
        mock_server.call_tool.assert_called_once()
        args = mock_server.call_tool.call_args[0]
        self.assertEqual(args[0], "test_tool")
        self.assertEqual(args[1], {"arg": "value"})  # Arguments should be unchanged

        # Verify result
        self.assertEqual(result, {"result": "success"})

        # Verify progress callbacks were made
        self.assertEqual(callback_func.call_count, 2)  # Start and completion

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
            mock_error.assert_called()

    def test_get_server_status(self):
        """Test getting server status."""
        mock_server = Mock()
        mock_server.is_running.return_value = True
        mock_server.get_pid.return_value = None  # SDK doesn't expose PID
        mock_server.get_uptime.return_value = 60.0
        mock_server.list_tools.return_value = [{"name": "tool1"}, {"name": "tool2"}]

        self.client.servers["test-server"] = mock_server

        status = self.client.get_server_status()

        expected = {
            "test-server": {
                "running": True,
                "pid": None,  # SDK doesn't expose PID
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
    """Test MCPServer class with new SDK implementation."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_logger = Mock()
        self.mock_loop = Mock()
        self.mock_loop.is_running.return_value = True
        self.config = {
            "name": "test-server",
            "command": ["python", "-c", "print('test')"],
            "args": [],
            "env": {},
        }
        self.server = MCPServer(self.config, self.mock_logger, self.mock_loop)

    def test_server_initialization(self):
        """Test server initialization."""
        self.assertEqual(self.server.config, self.config)
        self.assertEqual(self.server.logger, self.mock_logger)
        self.assertEqual(self.server.loop, self.mock_loop)
        self.assertIsNone(self.server._session)
        self.assertFalse(self.server._initialized)

    def test_is_running_false(self):
        """Test is_running when server is not running."""
        self.assertFalse(self.server.is_running())

    @patch("aixterm.mcp_client.asyncio.run_coroutine_threadsafe")
    def test_start_server_success(self, mock_run_coro):
        """Test successfully starting a server."""
        mock_future = Mock()
        mock_future.result.return_value = None
        mock_run_coro.return_value = mock_future

        self.server.start()

        self.assertTrue(self.server._initialized)
        self.assertIsNotNone(self.server.start_time)
        mock_run_coro.assert_called_once()

    @patch("aixterm.mcp_client.asyncio.run_coroutine_threadsafe")
    def test_start_server_failure(self, mock_run_coro):
        """Test server start failure."""
        mock_future = Mock()
        mock_future.result.side_effect = Exception("Start failed")
        mock_run_coro.return_value = mock_future

        with self.assertRaisesRegex(MCPError, "Failed to start MCP server"):
            self.server.start()

    def test_start_server_already_running(self):
        """Test starting server that's already running."""
        self.server._initialized = True
        self.server._session = Mock()

        # Should return early without doing anything
        self.server.start()

    def test_stop_server(self):
        """Test stopping server."""
        self.server._initialized = True
        self.server._session = Mock()

        with patch(
            "aixterm.mcp_client.asyncio.run_coroutine_threadsafe"
        ) as mock_run_coro:
            mock_future = Mock()
            mock_future.result.return_value = None
            mock_run_coro.return_value = mock_future

            self.server.stop()

            self.assertFalse(self.server._initialized)
            self.assertIsNone(self.server._session)

    def test_stop_server_no_session(self):
        """Test stopping server with no session."""
        # Should not fail
        self.server.stop()

    def test_stop_server_exception(self):
        """Test exception during server stop."""
        self.server._initialized = True
        self.server._session = Mock()

        with patch(
            "aixterm.mcp_client.asyncio.run_coroutine_threadsafe"
        ) as mock_run_coro:
            mock_future = Mock()
            mock_future.result.side_effect = Exception("Stop failed")
            mock_run_coro.return_value = mock_future

            # Should not raise, just log
            self.server.stop()

    def test_get_pid_no_process(self):
        """Test get_pid (always returns None with SDK)."""
        self.assertIsNone(self.server.get_pid())

    def test_get_pid_with_process(self):
        """Test get_pid returns None with SDK implementation."""
        self.assertIsNone(self.server.get_pid())

    def test_get_uptime_no_start_time(self):
        """Test get_uptime when not started."""
        self.assertIsNone(self.server.get_uptime())

    def test_get_uptime_with_start_time(self):
        """Test get_uptime with start time."""
        self.server.start_time = time.time() - 60
        uptime = self.server.get_uptime()
        self.assertIsNotNone(uptime)
        assert uptime is not None  # Type narrowing for mypy
        self.assertGreater(uptime, 59.0)

    def test_list_tools_not_running(self):
        """Test listing tools when server not running."""
        with self.assertRaisesRegex(MCPError, "Server is not running"):
            self.server.list_tools()

    @patch("aixterm.mcp_client.asyncio.run_coroutine_threadsafe")
    def test_list_tools_cached(self, mock_run_coro):
        """Test listing tools with caching."""
        self.server._initialized = True
        self.server._session = Mock()

        # Set up cache
        cached_tools = [{"type": "function", "function": {"name": "cached_tool"}}]
        self.server._tools_cache = cached_tools
        self.server._tools_cache_time = time.time()

        tools = self.server.list_tools(brief=True)

        # Should return cached result without calling async method
        self.assertEqual(tools, cached_tools)
        mock_run_coro.assert_not_called()

    @patch("aixterm.mcp_client.asyncio.run_coroutine_threadsafe")
    def test_list_tools_error(self, mock_run_coro):
        """Test listing tools with server error."""
        self.server._initialized = True
        self.server._session = Mock()

        mock_future = Mock()
        mock_future.result.side_effect = Exception("Server error")
        mock_run_coro.return_value = mock_future

        with self.assertRaisesRegex(MCPError, "Failed to list tools"):
            self.server.list_tools()

    @patch("aixterm.mcp_client.asyncio.run_coroutine_threadsafe")
    def test_call_tool_success(self, mock_run_coro):
        """Test calling a tool successfully."""
        self.server._initialized = True
        self.server._session = Mock()

        mock_result = Mock()
        mock_result.content = [Mock(text="Tool result")]

        mock_future = Mock()
        mock_future.result.return_value = mock_result
        mock_run_coro.return_value = mock_future

        result = self.server.call_tool("test_tool", {"arg": "value"})

        self.assertEqual(result, "Tool result")
        mock_run_coro.assert_called_once()


class TestIntegration(unittest.TestCase):
    """Test integration scenarios."""

    def test_end_to_end_progress_flow(self):
        """Test complete progress notification flow."""
        config = Mock()
        config.get_mcp_servers.return_value = []
        client = MCPClient(config)

        progress_updates = []

        def progress_callback(params: ProgressParams):
            progress_updates.append(params)

        # Register callback
        client.register_progress_callback("test-token", progress_callback)

        # Simulate progress notifications
        notifications = [
            {
                "method": "notifications/progress",
                "params": {
                    "progressToken": "test-token",
                    "progress": 25,
                    "total": 100,
                    "message": "Starting...",
                },
            },
            {
                "method": "notifications/progress",
                "params": {
                    "progressToken": "test-token",
                    "progress": 50,
                    "total": 100,
                    "message": "Half way...",
                },
            },
            {
                "method": "notifications/progress",
                "params": {
                    "progressToken": "test-token",
                    "progress": 100,
                    "total": 100,
                    "message": "Complete!",
                },
            },
        ]

        for notification in notifications:
            client.handle_progress_notification(notification)

        # Verify all progress updates were received
        self.assertEqual(len(progress_updates), 3)
        self.assertEqual(progress_updates[0].progress, 25)
        self.assertEqual(progress_updates[1].progress, 50)
        self.assertEqual(progress_updates[2].progress, 100)


if __name__ == "__main__":
    unittest.main()
