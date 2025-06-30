"""Tests for MCP client functionality."""

import json
import subprocess
import time
from unittest.mock import Mock, patch

import pytest

from aixterm.mcp_client import MCPError, MCPServer


class TestMCPClient:
    """Test cases for MCPClient class."""

    def test_initialize_no_servers(self, mcp_client, mock_config):
        """Test initialization with no MCP servers configured."""
        mock_config._config["mcp_servers"] = []

        mcp_client.initialize()

        assert mcp_client._initialized is True
        assert len(mcp_client.servers) == 0

    def test_initialize_with_servers(self, mcp_client, mock_config):
        """Test initialization with MCP servers configured."""
        mock_config._config["mcp_servers"] = [
            {
                "name": "test-server",
                "command": ["python", "server.py"],
                "enabled": True,
                "auto_start": True,
            }
        ]

        with patch("aixterm.mcp_client.MCPServer") as MockServer:
            mock_server = Mock()
            MockServer.return_value = mock_server

            mcp_client.initialize()

            assert mcp_client._initialized is True
            assert "test-server" in mcp_client.servers
            mock_server.start.assert_called_once()

    def test_initialize_server_error(self, mcp_client, mock_config):
        """Test handling of server initialization errors."""
        mock_config._config["mcp_servers"] = [
            {
                "name": "failing-server",
                "command": ["invalid-command"],
                "enabled": True,
                "auto_start": True,
            }
        ]

        with patch("aixterm.mcp_client.MCPServer") as MockServer:
            MockServer.side_effect = Exception("Server failed to start")

            # Should not raise exception, just log error
            mcp_client.initialize()

            assert mcp_client._initialized is True
            assert len(mcp_client.servers) == 0

    def test_get_available_tools(self, mcp_client):
        """Test getting available tools from servers."""
        mock_server = Mock()
        mock_server.is_running.return_value = True
        mock_server.list_tools.return_value = [
            {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "description": "A test tool",
                },
            }
        ]

        mcp_client.servers["test-server"] = mock_server
        mcp_client._initialized = True

        tools = mcp_client.get_available_tools()

        assert len(tools) == 1
        assert tools[0]["server"] == "test-server"
        assert tools[0]["function"]["name"] == "test_tool"

    def test_get_available_tools_server_not_running(self, mcp_client):
        """Test getting tools when server is not running."""
        mock_server = Mock()
        mock_server.is_running.return_value = False

        mcp_client.servers["test-server"] = mock_server
        mcp_client._initialized = True

        tools = mcp_client.get_available_tools()

        assert len(tools) == 0
        mock_server.list_tools.assert_not_called()

    def test_call_tool(self, mcp_client):
        """Test calling a tool on an MCP server."""
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

        with pytest.raises(MCPError, match="MCP server 'non-existent' not found"):
            mcp_client.call_tool("test_tool", "non-existent", {})

    def test_call_tool_start_stopped_server(self, mcp_client):
        """Test calling tool on stopped server (should start it)."""
        mock_server = Mock()
        mock_server.is_running.return_value = False
        mock_server.call_tool.return_value = {"result": "success"}

        mcp_client.servers["test-server"] = mock_server
        mcp_client._initialized = True

        result = mcp_client.call_tool("test_tool", "test-server", {})

        assert result == {"result": "success"}
        mock_server.start.assert_called_once()

    def test_shutdown(self, mcp_client):
        """Test shutting down all servers."""
        mock_server1 = Mock()
        mock_server2 = Mock()

        mcp_client.servers = {"server1": mock_server1, "server2": mock_server2}
        mcp_client._initialized = True

        mcp_client.shutdown()

        mock_server1.stop.assert_called_once()
        mock_server2.stop.assert_called_once()
        assert len(mcp_client.servers) == 0
        assert mcp_client._initialized is False

    def test_restart_server(self, mcp_client):
        """Test restarting a specific server."""
        mock_server = Mock()
        mcp_client.servers["test-server"] = mock_server

        with patch("time.sleep"):  # Speed up test
            result = mcp_client.restart_server("test-server")

        assert result is True
        mock_server.stop.assert_called_once()
        mock_server.start.assert_called_once()

    def test_restart_nonexistent_server(self, mcp_client):
        """Test restarting non-existent server."""
        result = mcp_client.restart_server("non-existent")
        assert result is False

    def test_get_server_status(self, mcp_client):
        """Test getting server status information."""
        mock_server = Mock()
        mock_server.is_running.return_value = True
        mock_server.get_pid.return_value = 12345
        mock_server.get_uptime.return_value = 120.5
        mock_server.list_tools.return_value = [{"tool": "test"}]

        mcp_client.servers["test-server"] = mock_server

        status = mcp_client.get_server_status()

        assert "test-server" in status
        assert status["test-server"]["running"] is True
        assert status["test-server"]["pid"] == 12345
        assert status["test-server"]["uptime"] == 120.5
        assert status["test-server"]["tool_count"] == 1


class TestMCPServer:
    """Test cases for MCPServer class."""

    def test_server_initialization(self):
        """Test server initialization."""
        config = {
            "name": "test-server",
            "command": ["python", "server.py"],
            "args": ["--port", "8080"],
            "env": {"TEST_VAR": "value"},
            "enabled": True,
            "timeout": 30,
        }

        server = MCPServer(config, Mock())

        assert server.config == config
        assert server.process is None
        assert server.start_time is None

    def test_start_server(self):
        """Test starting MCP server."""
        config = {
            "command": ["python", "server.py"],
            "args": ["--test"],
            "env": {"TEST": "value"},
        }

        with patch("subprocess.Popen") as mock_popen:
            mock_process = Mock()
            mock_process.poll.return_value = None  # Still running
            mock_popen.return_value = mock_process

            server = MCPServer(config, Mock())

            with patch("time.sleep"):  # Speed up test
                server.start()

            assert server.process == mock_process
            assert server.start_time is not None

            # Verify command construction
            call_args = mock_popen.call_args
            expected_command = ["python", "server.py", "--test"]
            assert call_args[0][0] == expected_command

    def test_start_server_failure(self):
        """Test handling of server start failure."""
        config = {"command": ["invalid-command"], "args": []}

        with patch("subprocess.Popen") as mock_popen:
            mock_process = Mock()
            mock_process.poll.return_value = 1  # Exited with error
            mock_process.stderr.read.return_value = "Command not found"
            mock_popen.return_value = mock_process

            server = MCPServer(config, Mock())

            with pytest.raises(MCPError, match="MCP server failed to start"):
                with patch("time.sleep"):
                    server.start()

    def test_stop_server(self):
        """Test stopping MCP server."""
        config = {"command": ["test"], "args": []}
        server = MCPServer(config, Mock())

        mock_process = Mock()
        mock_process.wait.return_value = None
        server.process = mock_process
        server.start_time = time.time()

        server.stop()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)
        assert server.process is None
        assert server.start_time is None

    def test_stop_server_force_kill(self):
        """Test force killing server when terminate fails."""
        config = {"command": ["test"], "args": []}
        server = MCPServer(config, Mock())

        mock_process = Mock()
        mock_process.wait.side_effect = [
            subprocess.TimeoutExpired("test", 5),
            None,
        ]
        server.process = mock_process

        server.stop()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_is_running(self):
        """Test checking if server is running."""
        config = {"command": ["test"], "args": []}
        server = MCPServer(config, Mock())

        # No process
        assert server.is_running() is False

        # Running process
        mock_process = Mock()
        mock_process.poll.return_value = None
        server.process = mock_process
        assert server.is_running() is True

        # Stopped process
        mock_process.poll.return_value = 0
        assert server.is_running() is False

    def test_send_request(self):
        """Test sending JSON-RPC request to server."""
        config = {"command": ["test"], "args": []}
        server = MCPServer(config, Mock())

        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.stdin = Mock()
        mock_process.stdout = Mock()
        mock_process.stdout.readline.return_value = (
            '{"jsonrpc":"2.0","id":1,"result":{"success":true}}\n'
        )

        server.process = mock_process

        result = server.send_request("test_method", {"param": "value"})

        assert result == {"success": True}

        # Verify request was written
        written_data = mock_process.stdin.write.call_args[0][0]
        request = json.loads(written_data.strip())
        assert request["method"] == "test_method"
        assert request["params"] == {"param": "value"}

    def test_send_request_server_error(self):
        """Test handling of server errors in response."""
        config = {"command": ["test"], "args": []}
        server = MCPServer(config, Mock())

        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.stdin = Mock()
        mock_process.stdout = Mock()
        mock_process.stdout.readline.return_value = (
            '{"jsonrpc":"2.0","id":1,"error":{"code":-1,"message":"Test error"}}\n'
        )

        server.process = mock_process

        with pytest.raises(MCPError, match="Server error"):
            server.send_request("test_method")

    def test_list_tools(self):
        """Test listing available tools."""
        config = {"command": ["test"], "args": []}
        server = MCPServer(config, Mock())

        mock_tools_response = {
            "tools": [
                {
                    "name": "test_tool",
                    "description": "A test tool",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"arg1": {"type": "string"}},
                    },
                }
            ]
        }

        with patch.object(server, "send_request", return_value=mock_tools_response):
            tools = server.list_tools()

            assert len(tools) == 1
            assert tools[0]["type"] == "function"
            assert tools[0]["function"]["name"] == "test_tool"
            assert tools[0]["function"]["description"] == "A test tool"

    def test_call_tool(self):
        """Test calling a tool."""
        config = {"command": ["test"], "args": []}
        server = MCPServer(config, Mock())

        expected_result = {"output": "success"}

        with patch.object(server, "send_request", return_value=expected_result):
            result = server.call_tool("test_tool", {"arg": "value"})

            assert result == expected_result

    def test_get_uptime(self):
        """Test getting server uptime."""
        config = {"command": ["test"], "args": []}
        server = MCPServer(config, Mock())

        # No start time
        assert server.get_uptime() is None

        # With start time
        start_time = time.time() - 100  # 100 seconds ago
        server.start_time = start_time

        uptime = server.get_uptime()
        assert uptime is not None
        assert uptime >= 99  # Should be around 100 seconds
        assert uptime <= 101
