"""Tests for MCP client functionality."""

import time
from unittest.mock import Mock, patch

import pytest

from aixterm.mcp_client import MCPClient, MCPError, MCPServer


class TestMCPClient:
    """Test MCP client functionality."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = Mock()
        config.get_mcp_servers.return_value = []
        return config

    @pytest.fixture
    def mcp_client(self, mock_config):
        """Create MCP client for testing."""
        return MCPClient(mock_config)

    def test_initialize_no_servers(self, mcp_client):
        """Test initializing with no servers."""
        mcp_client.initialize()
        assert mcp_client._initialized
        assert len(mcp_client.servers) == 0

    @patch("aixterm.mcp_client.MCPServer")
    def test_initialize_with_servers(self, mock_server_class, mcp_client):
        """Test initializing with servers."""
        mock_server = Mock()
        mock_server_class.return_value = mock_server

        server_config = {
            "name": "test-server",
            "command": ["python", "-c", "print('test')"],
            "auto_start": True,
        }
        mcp_client.config.get_mcp_servers.return_value = [server_config]

        mcp_client.initialize()

        assert mcp_client._initialized
        assert "test-server" in mcp_client.servers
        mock_server.start.assert_called_once()

    @patch("aixterm.mcp_client.MCPServer")
    def test_initialize_server_error(self, mock_server_class, mcp_client):
        """Test handling server initialization errors."""
        mock_server_class.side_effect = Exception("Server init failed")

        server_config = {
            "name": "test-server",
            "command": ["python", "-c", "print('test')"],
        }
        mcp_client.config.get_mcp_servers.return_value = [server_config]

        # Should not raise exception, just log error
        mcp_client.initialize()
        assert mcp_client._initialized
        assert len(mcp_client.servers) == 0

    def test_get_available_tools(self, mcp_client):
        """Test getting available tools."""
        mock_server = Mock()
        mock_server.is_running.return_value = True
        mock_server.list_tools.return_value = [
            {"type": "function", "function": {"name": "test_tool"}}
        ]

        mcp_client.servers["test-server"] = mock_server
        mcp_client._initialized = True

        tools = mcp_client.get_available_tools()

        assert len(tools) == 1
        assert tools[0]["server"] == "test-server"
        assert tools[0]["type"] == "function"

    def test_get_available_tools_server_not_running(self, mcp_client):
        """Test getting tools when server is not running."""
        mock_server = Mock()
        mock_server.is_running.return_value = False

        mcp_client.servers["test-server"] = mock_server
        mcp_client._initialized = True

        tools = mcp_client.get_available_tools()
        assert len(tools) == 0

    def test_call_tool(self, mcp_client):
        """Test calling a tool."""
        mock_server = Mock()
        mock_server.is_running.return_value = True
        mock_server.call_tool.return_value = {"result": "success"}

        mcp_client.servers["test-server"] = mock_server
        mcp_client._initialized = True

        result = mcp_client.call_tool("test_tool", "test-server", {"arg": "value"})

        assert result == {"result": "success"}
        mock_server.call_tool.assert_called_once_with("test_tool", {"arg": "value"})

    def test_call_tool_server_not_found(self, mcp_client):
        """Test calling tool on non-existent server."""
        mcp_client._initialized = True

        with pytest.raises(MCPError, match="MCP server 'nonexistent' not found"):
            mcp_client.call_tool("test_tool", "nonexistent", {})

    def test_call_tool_start_stopped_server(self, mcp_client):
        """Test calling tool on stopped server starts it."""
        mock_server = Mock()
        mock_server.is_running.return_value = False
        mock_server.call_tool.return_value = {"result": "success"}

        mcp_client.servers["test-server"] = mock_server
        mcp_client._initialized = True

        result = mcp_client.call_tool("test_tool", "test-server", {})

        mock_server.start.assert_called_once()
        assert result == {"result": "success"}

    def test_shutdown(self, mcp_client):
        """Test shutting down client."""
        mock_server = Mock()
        mcp_client.servers["test-server"] = mock_server
        mcp_client._initialized = True

        mcp_client.shutdown()

        mock_server.stop.assert_called_once()
        assert len(mcp_client.servers) == 0
        assert not mcp_client._initialized

    def test_get_server_status(self, mcp_client):
        """Test getting server status."""
        mock_server = Mock()
        mock_server.is_running.return_value = True
        mock_server.get_pid.return_value = None  # SDK doesn't expose PID
        mock_server.get_uptime.return_value = 60.0
        mock_server.list_tools.return_value = [{"name": "tool1"}]

        mcp_client.servers["test-server"] = mock_server

        status = mcp_client.get_server_status()

        expected = {
            "test-server": {
                "running": True,
                "pid": None,  # SDK doesn't expose PID
                "uptime": 60.0,
                "tool_count": 1,
            }
        }
        assert status == expected


class TestMCPServer:
    """Test MCP server functionality."""

    @pytest.fixture
    def config(self):
        """Create test server config."""
        return {
            "name": "test-server",
            "command": ["python", "-c", "print('test')"],
            "args": [],
            "env": {},
        }

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger."""
        return Mock()

    @pytest.fixture
    def mock_loop(self):
        """Create mock event loop."""
        loop = Mock()
        loop.is_running.return_value = True
        return loop

    def test_server_initialization(self, config, mock_logger, mock_loop):
        """Test server initialization."""
        server = MCPServer(config, mock_logger, mock_loop)

        assert server.config == config
        assert server.logger == mock_logger
        assert server.loop == mock_loop
        assert server._session is None
        assert not server._initialized

    @patch("aixterm.mcp_client.asyncio.run_coroutine_threadsafe")
    def test_start_server(self, mock_run_coro, config, mock_logger, mock_loop):
        """Test starting server."""
        mock_future = Mock()
        mock_future.result.return_value = None
        mock_run_coro.return_value = mock_future

        server = MCPServer(config, mock_logger, mock_loop)
        server.start()

        assert server._initialized
        assert server.start_time is not None
        mock_run_coro.assert_called_once()

    @patch("aixterm.mcp_client.asyncio.run_coroutine_threadsafe")
    def test_start_server_failure(self, mock_run_coro, config, mock_logger, mock_loop):
        """Test server start failure."""
        mock_future = Mock()
        mock_future.result.side_effect = Exception("Start failed")
        mock_run_coro.return_value = mock_future

        server = MCPServer(config, mock_logger, mock_loop)

        with pytest.raises(MCPError, match="Failed to start MCP server"):
            server.start()

    def test_stop_server(self, config, mock_logger, mock_loop):
        """Test stopping server."""
        server = MCPServer(config, mock_logger, mock_loop)
        server._initialized = True
        server._session = Mock()

        with patch(
            "aixterm.mcp_client.asyncio.run_coroutine_threadsafe"
        ) as mock_run_coro:
            mock_future = Mock()
            mock_future.result.return_value = None
            mock_run_coro.return_value = mock_future

            server.stop()

            assert not server._initialized
            assert server._session is None

    def test_is_running(self, config, mock_logger, mock_loop):
        """Test is_running status."""
        server = MCPServer(config, mock_logger, mock_loop)

        # Not running initially
        assert not server.is_running()

        # Running when initialized and has session
        server._initialized = True
        server._session = Mock()
        assert server.is_running()

        # Not running if no session
        server._session = None
        assert not server.is_running()

    def test_get_pid(self, config, mock_logger, mock_loop):
        """Test get_pid (always returns None with SDK)."""
        server = MCPServer(config, mock_logger, mock_loop)
        assert server.get_pid() is None

    def test_get_uptime(self, config, mock_logger, mock_loop):
        """Test get_uptime."""
        server = MCPServer(config, mock_logger, mock_loop)

        # No uptime when not started
        assert server.get_uptime() is None

        # Has uptime when started
        server.start_time = time.time() - 60
        uptime = server.get_uptime()
        assert uptime is not None
        assert uptime > 59  # Should be around 60 seconds

    @patch("aixterm.mcp_client.asyncio.run_coroutine_threadsafe")
    def test_list_tools(self, mock_run_coro, config, mock_logger, mock_loop):
        """Test listing tools."""
        server = MCPServer(config, mock_logger, mock_loop)
        server._initialized = True
        server._session = Mock()

        # Mock the async result
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool"
        mock_tool.inputSchema = {"type": "object"}

        mock_result = Mock()
        mock_result.tools = [mock_tool]

        mock_future = Mock()
        mock_future.result.return_value = mock_result
        mock_run_coro.return_value = mock_future

        tools = server.list_tools()

        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "test_tool"

    def test_list_tools_not_running(self, config, mock_logger, mock_loop):
        """Test listing tools when server not running."""
        server = MCPServer(config, mock_logger, mock_loop)

        with pytest.raises(MCPError, match="Server is not running"):
            server.list_tools()

    @patch("aixterm.mcp_client.asyncio.run_coroutine_threadsafe")
    def test_call_tool(self, mock_run_coro, config, mock_logger, mock_loop):
        """Test calling a tool."""
        server = MCPServer(config, mock_logger, mock_loop)
        server._initialized = True
        server._session = Mock()

        # Mock the async result
        mock_result = Mock()
        mock_result.content = [Mock(text="Tool result")]

        mock_future = Mock()
        mock_future.result.return_value = mock_result
        mock_run_coro.return_value = mock_future

        result = server.call_tool("test_tool", {"arg": "value"})

        assert result == "Tool result"
        mock_run_coro.assert_called_once()

    def test_call_tool_not_running(self, config, mock_logger, mock_loop):
        """Test calling tool when server not running."""
        server = MCPServer(config, mock_logger, mock_loop)

        with pytest.raises(MCPError, match="Server is not running"):
            server.call_tool("test_tool", {})
