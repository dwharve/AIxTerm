"""Tests for MCP client functionality."""

import subprocess
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
        mock_server.get_pid.return_value = 12345
        mock_server.get_uptime.return_value = 60.0
        mock_server.list_tools.return_value = [{"name": "tool1"}]

        mcp_client.servers["test-server"] = mock_server

        status = mcp_client.get_server_status()

        expected = {
            "test-server": {
                "running": True,
                "pid": 12345,
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
    def mock_client(self):
        """Create mock MCP client."""
        return Mock()

    def test_server_initialization(self, config, mock_client):
        """Test server initialization."""
        server = MCPServer(config, Mock(), mock_client)

        assert server.config == config
        assert server.mcp_client == mock_client
        assert server.process is None
        assert not server._initialized

    @patch("subprocess.Popen")
    def test_start_server(self, mock_popen, config, mock_client):
        """Test starting server."""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        server = MCPServer(config, Mock(), mock_client)

        with patch.object(server, "initialize_mcp_session"):
            server.start()

        assert server.process == mock_process
        assert server._initialized

    @patch("subprocess.Popen")
    def test_start_server_failure(self, mock_popen, config, mock_client):
        """Test server start failure."""
        mock_process = Mock()
        mock_process.poll.return_value = 1  # Exit code 1
        mock_process.stderr.read.return_value = "Error message"
        mock_popen.return_value = mock_process

        server = MCPServer(config, Mock(), mock_client)

        with pytest.raises(MCPError):
            server.start()

    def test_stop_server(self, config, mock_client):
        """Test stopping server."""
        server = MCPServer(config, Mock(), mock_client)
        mock_process = Mock()
        server.process = mock_process
        server._initialized = True

        server.stop()

        mock_process.terminate.assert_called_once()
        assert server.process is None
        assert not server._initialized

    def test_stop_server_force_kill(self, config, mock_client):
        """Test force killing server on timeout."""
        server = MCPServer(config, Mock(), mock_client)
        mock_process = Mock()
        mock_process.wait.side_effect = [subprocess.TimeoutExpired("cmd", 5), None]
        server.process = mock_process

        server.stop()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_is_running(self, config, mock_client):
        """Test checking if server is running."""
        server = MCPServer(config, Mock(), mock_client)

        # Not running initially
        assert not server.is_running()

        # Running with process
        mock_process = Mock()
        mock_process.poll.return_value = None
        server.process = mock_process
        assert server.is_running()

        # Not running when process exited
        mock_process.poll.return_value = 0
        assert not server.is_running()

    def test_send_request(self, config, mock_client):
        """Test sending request to server."""
        server = MCPServer(config, Mock(), mock_client)
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.stdout.readline.return_value = '{"result": "test"}'
        # Mock stdout to have a fileno that works with select
        mock_process.stdout.fileno.return_value = 1
        server.process = mock_process

        with patch("json.loads", return_value={"result": "test"}):
            with patch("select.select", return_value=([mock_process.stdout], [], [])):
                result = server.send_request("test/method", {"param": "value"})

        assert result == "test"
        mock_process.stdin.write.assert_called_once()

    def test_send_request_server_error(self, config, mock_client):
        """Test handling server error response."""
        server = MCPServer(config, Mock(), mock_client)
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.stdout.readline.return_value = '{"error": "test error"}'
        server.process = mock_process

        with patch("json.loads", return_value={"error": "test error"}):
            with pytest.raises(MCPError):
                server.send_request("test/method")

    def test_list_tools(self, config, mock_client):
        """Test listing tools."""
        server = MCPServer(config, Mock(), mock_client)

        mock_tools_response = {
            "tools": [
                {
                    "name": "test_tool",
                    "description": "A test tool",
                    "inputSchema": {"type": "object"},
                }
            ]
        }

        with patch.object(server, "send_request", return_value=mock_tools_response):
            tools = server.list_tools()

        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "test_tool"

    def test_call_tool(self, config, mock_client):
        """Test calling a tool."""
        server = MCPServer(config, Mock(), mock_client)
        expected_result = {"content": [{"type": "text", "text": "result"}]}

        with patch.object(server, "send_request", return_value=expected_result):
            result = server.call_tool("test_tool", {"arg": "value"})

        assert result == expected_result

    def test_get_uptime(self, config, mock_client):
        """Test getting server uptime."""
        server = MCPServer(config, Mock(), mock_client)

        # No uptime when not started
        assert server.get_uptime() is None

        # Uptime when started
        server.start_time = time.time() - 30
        uptime = server.get_uptime()
        assert uptime is not None
        assert uptime >= 29  # Allow some variance
