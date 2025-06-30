"""Model Context Protocol (MCP) client implementation."""

import json
import os
import subprocess
import time
from typing import Any, Dict, List, Optional

from .utils import get_logger


class MCPClient:
    """Client for communicating with MCP servers."""

    def __init__(self, config_manager: Any) -> None:
        """Initialize MCP client.

        Args:
               if "error" in response:
                raise MCPError(f"Server error: {response['error']}")

            result: Dict[str, Any] = response.get("result", {})
            return result     config_manager: AIxTermConfig instance
        """
        self.config = config_manager
        self.logger = get_logger(__name__)
        self.servers: Dict[str, Any] = {}  # name -> MCPServer instance
        self._initialized = False

    def initialize(self) -> None:
        """Initialize MCP servers."""
        if self._initialized:
            return

        server_configs = self.config.get_mcp_servers()
        self.logger.info(f"Initializing {len(server_configs)} MCP servers")

        for server_config in server_configs:
            try:
                server = MCPServer(server_config, self.logger)
                if server_config.get("auto_start", True):
                    server.start()
                self.servers[server_config["name"]] = server
                self.logger.info(f"Initialized MCP server: {server_config['name']}")
            except Exception as e:
                self.logger.error(
                    f"Failed to initialize MCP server {server_config['name']}: {e}"
                )

        self._initialized = True

    def initialize_for_cli_mode(self) -> None:
        """Initialize MCP servers specifically for CLI mode.

        This starts only essential servers and marks them for automatic cleanup.
        """
        if self._initialized:
            return

        server_configs = self.config.get_mcp_servers()
        self.logger.info(f"Initializing {len(server_configs)} MCP servers for CLI mode")

        for server_config in server_configs:
            try:
                server = MCPServer(server_config, self.logger)
                # Mark server for CLI mode automatic management
                server._cli_mode = True

                # Start server immediately for CLI mode
                if server_config.get("auto_start", True):
                    server.start()

                self.servers[server_config["name"]] = server
                self.logger.info(
                    f"Initialized MCP server for CLI: {server_config['name']}"
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to initialize MCP server {server_config['name']}: {e}"
                )

        self._initialized = True

    def get_available_tools(self, brief: bool = True) -> List[Dict[str, Any]]:
        """Get all available tools from MCP servers.

        Args:
            brief: Whether to request brief descriptions for LLM prompts

        Returns:
            List of tool definitions compatible with OpenAI function calling
        """
        if not self._initialized:
            self.initialize()

        tools = []
        for server_name, server in self.servers.items():
            if server.is_running():
                try:
                    server_tools = server.list_tools(brief=brief)
                    for tool in server_tools:
                        # Add server name to tool for routing
                        tool["server"] = server_name
                        tools.append(tool)
                except Exception as e:
                    self.logger.error(f"Error getting tools from {server_name}: {e}")

        return tools

    def call_tool(
        self, tool_name: str, server_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool on an MCP server.

        Args:
            tool_name: Name of the tool to call
            server_name: Name of the MCP server
            arguments: Tool arguments

        Returns:
            Tool result
        """
        if not self._initialized:
            self.initialize()

        if server_name not in self.servers:
            raise MCPError(f"MCP server '{server_name}' not found")

        server = self.servers[server_name]
        if not server.is_running():
            self.logger.warning(f"Starting MCP server {server_name}")
            server.start()

        try:
            result: Dict[str, Any] = server.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            self.logger.error(f"Error calling tool {tool_name} on {server_name}: {e}")
            raise MCPError(f"Tool call failed: {e}")

    def shutdown(self) -> None:
        """Shutdown all MCP servers."""
        self.logger.info("Shutting down MCP servers")
        for server_name, server in self.servers.items():
            try:
                server.stop()
                self.logger.info(f"Stopped MCP server: {server_name}")
            except Exception as e:
                self.logger.error(f"Error stopping MCP server {server_name}: {e}")

        self.servers.clear()
        self._initialized = False

    def shutdown_cli_mode_servers(self) -> None:
        """Shutdown all servers that were started for CLI mode."""
        for server_name, server in self.servers.items():
            if hasattr(server, "_cli_mode") and server._cli_mode:
                try:
                    self.logger.info(f"Shutting down CLI mode server: {server_name}")
                    server.stop()
                except Exception as e:
                    self.logger.error(f"Error stopping server {server_name}: {e}")

    def restart_server(self, server_name: str) -> bool:
        """Restart an MCP server.

        Args:
            server_name: Name of server to restart

        Returns:
            True if restart successful
        """
        if server_name not in self.servers:
            return False

        try:
            server = self.servers[server_name]
            server.stop()
            time.sleep(1)  # Give it a moment
            server.start()
            self.logger.info(f"Restarted MCP server: {server_name}")
            return True
        except Exception as e:
            self.logger.error(f"Error restarting MCP server {server_name}: {e}")
            return False

    def get_server_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all MCP servers.

        Returns:
            Dictionary mapping server names to status info
        """
        status = {}
        for server_name, server in self.servers.items():
            status[server_name] = {
                "running": server.is_running(),
                "pid": server.get_pid(),
                "uptime": server.get_uptime(),
                "tool_count": (len(server.list_tools()) if server.is_running() else 0),
            }
        return status

    def describe_tool(self, tool_name: str, server_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific tool.

        Args:
            tool_name: Name of the tool to describe
            server_name: Name of the MCP server

        Returns:
            Detailed tool information
        """
        if not self._initialized:
            self.initialize()

        if server_name not in self.servers:
            raise MCPError(f"MCP server '{server_name}' not found")

        server = self.servers[server_name]
        if not server.is_running():
            self.logger.warning(f"Starting MCP server {server_name}")
            server.start()

        try:
            result: Dict[str, Any] = server.describe_tool(tool_name)
            return result
        except Exception as e:
            self.logger.error(
                f"Error describing tool {tool_name} on {server_name}: {e}"
            )
            raise MCPError(f"Tool description failed: {e}")


class MCPServer:
    """Represents a single MCP server instance."""

    def __init__(self, config: Dict[str, Any], logger: Any) -> None:
        """Initialize MCP server.

        Args:
            config: Server configuration
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.process: Optional[subprocess.Popen[str]] = None
        self.start_time: Optional[float] = None
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        self._tools_cache_time: float = 0
        self._cli_mode: bool = False

    def start(self) -> None:
        """Start the MCP server process."""
        if self.is_running():
            return

        command = self.config["command"] + self.config.get("args", [])
        env = dict(os.environ)
        env.update(self.config.get("env", {}))

        try:
            self.logger.info(f"Starting MCP server with command: {' '.join(command)}")
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=0,
            )
            self.start_time = time.time()

            # Give the server a moment to start
            time.sleep(0.5)

            if self.process.poll() is not None:
                stderr = (
                    self.process.stderr.read()
                    if self.process.stderr
                    else "No error output"
                )
                raise MCPError(f"MCP server failed to start: {stderr}")

        except Exception as e:
            self.logger.error(f"Failed to start MCP server: {e}")
            raise MCPError(f"Failed to start MCP server: {e}")

    def stop(self) -> None:
        """Stop the MCP server process."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            except Exception as e:
                self.logger.error(f"Error stopping MCP server: {e}")
            finally:
                self.process = None
                self.start_time = None
                self._tools_cache = None

    def is_running(self) -> bool:
        """Check if server is running.

        Returns:
            True if server is running
        """
        return self.process is not None and self.process.poll() is None

    def get_pid(self) -> Optional[int]:
        """Get server process PID.

        Returns:
            Process PID or None if not running
        """
        return self.process.pid if self.process else None

    def get_uptime(self) -> Optional[float]:
        """Get server uptime in seconds.

        Returns:
            Uptime in seconds or None if not running
        """
        if not self.start_time:
            return None
        return time.time() - self.start_time

    def send_request(
        self, method: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send JSON-RPC request to server.

        Args:
            method: RPC method name
            params: Method parameters

        Returns:
            Server response
        """
        if not self.is_running():
            raise MCPError("Server is not running")

        request = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),  # Simple ID generation
            "method": method,
        }

        if params:
            request["params"] = params

        try:
            if not self.process or not self.process.stdin or not self.process.stdout:
                raise MCPError("Server process not properly initialized")

            request_json = json.dumps(request) + "\n"
            self.process.stdin.write(request_json)
            self.process.stdin.flush()

            # Read response
            response_line = self.process.stdout.readline()
            if not response_line:
                raise MCPError("No response from server")

            response = json.loads(response_line)

            if "error" in response:
                raise MCPError(f"Server error: {response['error']}")

            result: Dict[str, Any] = response.get("result", {})
            return result

        except Exception as e:
            self.logger.error(f"Error communicating with MCP server: {e}")
            raise MCPError(f"Communication error: {e}")

    def list_tools(self, brief: bool = True) -> List[Dict[str, Any]]:
        """Get list of available tools from server.

        Args:
            brief: Whether to request brief descriptions for LLM prompts

        Returns:
            List of tool definitions
        """
        # Simple caching to avoid repeated requests (separate cache for brief/detailed)
        cache_key = f"tools_{'brief' if brief else 'detailed'}"
        current_time = time.time()

        cached_tools: Optional[List[Dict[str, Any]]] = getattr(
            self, f"_{cache_key}_cache", None
        )
        cache_time = getattr(self, f"_{cache_key}_cache_time", 0)

        if cached_tools and (current_time - cache_time) < 60:
            return cached_tools

        try:
            # Request tools with brief parameter
            params = {"brief": brief} if brief else {}
            result = self.send_request("tools/list", params)
            tools_data: list = result.get("tools", [])

            # Convert to OpenAI function format
            openai_tools = []
            for tool in tools_data:
                openai_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("inputSchema", {}),
                    },
                }
                openai_tools.append(openai_tool)

            # Cache the results
            setattr(self, f"_{cache_key}_cache", openai_tools)
            setattr(self, f"_{cache_key}_cache_time", current_time)

            tools_result: List[Dict[str, Any]] = openai_tools
            return tools_result

        except Exception as e:
            self.logger.error(f"Error listing tools: {e}")
            return []

    def describe_tool(self, tool_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific tool.

        Args:
            tool_name: Name of the tool to describe

        Returns:
            Detailed tool information
        """
        try:
            params = {"name": tool_name}
            result = self.send_request("tools/describe", params)
            tool_info: Dict[str, Any] = result.get("tool", {})
            return tool_info
        except Exception as e:
            self.logger.error(f"Error describing tool {tool_name}: {e}")
            return {}

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the server.

        Args:
            tool_name: Name of tool to call
            arguments: Tool arguments

        Returns:
            Tool result
        """
        params = {"name": tool_name, "arguments": arguments}

        return self.send_request("tools/call", params)


class MCPError(Exception):
    """Exception raised for MCP-related errors."""

    pass
