"""Model Context Protocol (MCP) client implementation."""

import json
import os
import select
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union

from .utils import get_logger


@dataclass
class ProgressParams:
    """Progress notification parameters."""

    progress_token: Union[str, int]
    progress: int
    total: Optional[int] = None
    message: Optional[str] = None


class ProgressCallback:
    """Represents a progress callback for a specific operation."""

    def __init__(
        self,
        callback: Callable[[ProgressParams], None],
        timeout: Optional[float] = None,
    ):
        self.callback = callback
        self.timeout = timeout
        self.start_time = time.time()

    def is_expired(self) -> bool:
        """Check if this callback has expired."""
        if self.timeout is None:
            return False
        return time.time() - self.start_time > self.timeout

    def __call__(self, params: ProgressParams) -> None:
        """Call the progress callback."""
        try:
            self.callback(params)
        except Exception as e:
            logger = get_logger(__name__)
            logger.error(f"Error in progress callback: {e}")


class MCPError(Exception):
    """Exception raised for MCP-related errors."""

    pass


class MCPClient:
    """Client for communicating with MCP servers with progress notification support."""

    def __init__(self, config_manager: Any) -> None:
        """Initialize MCP client.

        Args:
            config_manager: AIxTermConfig instance
        """
        self.config = config_manager
        self.logger = get_logger(__name__)
        self.servers: Dict[str, "MCPServer"] = {}
        self._initialized = False

        # Progress notification support
        self._progress_callbacks: Dict[Union[str, int], ProgressCallback] = {}
        self._progress_lock = threading.RLock()
        self._executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="mcp-client"
        )

    def initialize(self) -> None:
        """Initialize MCP servers."""
        if self._initialized:
            return

        server_configs = self.config.get_mcp_servers()
        self.logger.info(f"Initializing {len(server_configs)} MCP servers")

        for server_config in server_configs:
            try:
                server = MCPServer(server_config, self.logger, self)
                if server_config.get("auto_start", True):
                    server.start()
                self.servers[server_config["name"]] = server
                self.logger.info(f"Initialized MCP server: {server_config['name']}")
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
                        tool["server"] = server_name
                        tools.append(tool)
                except Exception as e:
                    self.logger.error(f"Error getting tools from {server_name}: {e}")

        return tools

    def call_tool(
        self, tool_name: str, server_name: str, arguments: Dict[str, Any]
    ) -> Any:
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
            return server.call_tool(tool_name, arguments)
        except Exception as e:
            self.logger.error(f"Error calling tool {tool_name} on {server_name}: {e}")
            raise MCPError(f"Tool call failed: {e}")

    def register_progress_callback(
        self,
        progress_token: Union[str, int],
        callback: Callable[[ProgressParams], None],
        timeout: Optional[float] = 300.0,
    ) -> None:
        """Register a progress callback for a specific progress token.

        Args:
            progress_token: Token to associate with this callback
            callback: Function to call when progress updates are received
            timeout: Callback timeout in seconds (default: 5 minutes)
        """
        with self._progress_lock:
            self._progress_callbacks[progress_token] = ProgressCallback(
                callback, timeout
            )
            self.logger.debug(
                f"Registered progress callback for token: {progress_token}"
            )

    def unregister_progress_callback(self, progress_token: Union[str, int]) -> None:
        """Unregister a progress callback.

        Args:
            progress_token: Token to remove callback for
        """
        with self._progress_lock:
            if progress_token in self._progress_callbacks:
                del self._progress_callbacks[progress_token]
                self.logger.debug(
                    f"Unregistered progress callback for token: {progress_token}"
                )

    def call_tool_with_progress(
        self,
        tool_name: str,
        server_name: str,
        arguments: Dict[str, Any],
        progress_callback: Optional[Callable[[ProgressParams], None]] = None,
        timeout: Optional[float] = 300.0,
    ) -> Any:
        """Call a tool with progress notification support.

        Args:
            tool_name: Name of the tool to call
            server_name: Name of the MCP server
            arguments: Tool arguments
            progress_callback: Optional callback for progress updates
            timeout: Callback timeout in seconds

        Returns:
            Tool result
        """
        progress_token = str(uuid.uuid4())

        if progress_callback:
            self.register_progress_callback(progress_token, progress_callback, timeout)

        try:
            enhanced_arguments = arguments.copy()
            enhanced_arguments["_progress_token"] = progress_token

            result = self.call_tool(tool_name, server_name, enhanced_arguments)
            return result

        finally:
            if progress_callback:
                time.sleep(0.1)  # Allow final progress notifications
                self.unregister_progress_callback(progress_token)

    def handle_progress_notification(self, notification: Dict[str, Any]) -> None:
        """Handle incoming progress notification.

        Args:
            notification: Progress notification message
        """
        try:
            params = notification.get("params", {})
            progress_token = params.get("progressToken")

            if progress_token is None:
                self.logger.warning("Received progress notification without token")
                return

            progress_params = ProgressParams(
                progress_token=progress_token,
                progress=params.get("progress", 0),
                total=params.get("total"),
                message=params.get("message"),
            )

            with self._progress_lock:
                callback = self._progress_callbacks.get(progress_token)
                if callback:
                    if callback.is_expired():
                        del self._progress_callbacks[progress_token]
                        self.logger.debug(
                            f"Removed expired progress callback for token: "
                            f"{progress_token}"
                        )
                    else:
                        callback(progress_params)
                else:
                    self.logger.debug(
                        f"No callback registered for progress token: {progress_token}"
                    )

        except Exception as e:
            self.logger.error(f"Error handling progress notification: {e}")

    def cleanup_expired_callbacks(self) -> None:
        """Clean up expired progress callbacks."""
        with self._progress_lock:
            expired_tokens = [
                token
                for token, callback in self._progress_callbacks.items()
                if callback.is_expired()
            ]

            for token in expired_tokens:
                del self._progress_callbacks[token]
                self.logger.debug(
                    f"Cleaned up expired progress callback for token: {token}"
                )

    def shutdown(self) -> None:
        """Shutdown all MCP servers."""
        self._executor.shutdown(wait=True)

        self.logger.info("Shutting down MCP servers")
        for server_name, server in self.servers.items():
            try:
                server.stop()
                self.logger.info(f"Stopped MCP server: {server_name}")
            except Exception as e:
                self.logger.error(f"Error stopping MCP server {server_name}: {e}")

        self.servers.clear()
        self._initialized = False

        with self._progress_lock:
            self._progress_callbacks.clear()

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
                "tool_count": len(server.list_tools()) if server.is_running() else 0,
            }
        return status


class MCPServer:
    """Represents a single MCP server instance with progress notification support."""

    def __init__(
        self, config: Dict[str, Any], logger: Any, mcp_client: MCPClient
    ) -> None:
        """Initialize MCP server.

        Args:
            config: Server configuration
            logger: Logger instance
            mcp_client: Reference to parent MCPClient for progress notifications
        """
        self.config = config
        self.logger = logger
        self.mcp_client = mcp_client
        self.process: Optional[subprocess.Popen[str]] = None
        self.start_time: Optional[float] = None
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        self._tools_cache_time: float = 0
        self._initialized: bool = False

        # Progress notification support
        self._stop_notifications = threading.Event()
        self._notification_thread: Optional[threading.Thread] = None

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

            time.sleep(0.5)  # Give the server a moment to start

            if self.process.poll() is not None:
                stderr = (
                    self.process.stderr.read()
                    if self.process.stderr
                    else "No error output"
                )
                raise MCPError(f"MCP server failed to start: {stderr}")

            self.initialize_mcp_session()
            self._initialized = True
            self.logger.info("MCP session initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to start MCP server: {e}")
            raise MCPError(f"Failed to start MCP server: {e}")

    def stop(self) -> None:
        """Stop the MCP server process."""
        self._stop_notifications.set()

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
                self._initialized = False

        if self._notification_thread and self._notification_thread.is_alive():
            self._notification_thread.join(timeout=2.0)

    def is_running(self) -> bool:
        """Check if server is running."""
        return self.process is not None and self.process.poll() is None

    def get_pid(self) -> Optional[int]:
        """Get server process PID."""
        return self.process.pid if self.process else None

    def get_uptime(self) -> Optional[float]:
        """Get server uptime in seconds."""
        if not self.start_time:
            return None
        return time.time() - self.start_time

    def initialize_mcp_session(self) -> Dict[str, Any]:
        """Initialize MCP session with proper protocol handshake."""
        if not self.is_running():
            raise MCPError("Server is not running")

        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {},
                "progress": True,
            },
            "clientInfo": {"name": "aixterm-mcp-client", "version": "1.0.0"},
        }

        try:
            result = self.send_request("initialize", params)
            self.send_notification("notifications/initialized")
            self._start_notification_handler()
            return result if isinstance(result, dict) else {}

        except Exception as e:
            self.logger.error(f"Error initializing MCP session: {e}")
            raise MCPError(f"Initialization failed: {e}")

    def _start_notification_handler(self) -> None:
        """Start background thread to handle incoming notifications."""
        if self._notification_thread and self._notification_thread.is_alive():
            return

        def notification_handler() -> None:
            """Background thread to handle notifications from server."""
            while not self._stop_notifications.is_set() and self.is_running():
                try:
                    if self.process and self.process.stdout:
                        if sys.platform != "win32":
                            ready, _, _ = select.select(
                                [self.process.stdout], [], [], 0.1
                            )
                            if ready:
                                line = self.process.stdout.readline()
                                if line:
                                    try:
                                        message = json.loads(line)
                                        if (
                                            "id" not in message
                                            and message.get("method")
                                            == "notifications/progress"
                                        ):
                                            self.mcp_client.handle_progress_notification(  # noqa: E501
                                                message
                                            )
                                    except json.JSONDecodeError:
                                        pass
                        else:
                            time.sleep(0.1)
                except Exception as e:
                    self.logger.debug(f"Error in notification handler: {e}")

        self._notification_thread = threading.Thread(
            target=notification_handler,
            name=f"mcp-notifications-{self.config.get('name', 'unknown')}",
            daemon=True,
        )
        self._notification_thread.start()

    def send_notification(
        self, method: str, params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send a notification to the server."""
        if not self.is_running():
            raise MCPError("Server is not running")

        notification: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }

        if params:
            notification["params"] = params

        try:
            if not self.process or not self.process.stdin:
                raise MCPError("Server process not properly initialized")

            notification_json = json.dumps(notification) + "\n"
            self.process.stdin.write(notification_json)
            self.process.stdin.flush()

        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            raise MCPError(f"Notification error: {e}")

    def send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send JSON-RPC request to server."""
        if not self.is_running():
            raise MCPError("Server is not running")

        request = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
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

            # Add timeout to prevent hanging on unresponsive servers
            timeout = self.config.get("timeout", 30)
            if sys.platform != "win32":
                ready, _, _ = select.select([self.process.stdout], [], [], timeout)
                if not ready:
                    raise MCPError(f"Server did not respond within {timeout} seconds")
                response_line = self.process.stdout.readline()
            else:
                # Windows doesn't support select on pipes, use a simple timeout approach
                import signal

                def timeout_handler(signum, frame):
                    raise TimeoutError("Request timeout")

                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout)
                try:
                    response_line = self.process.stdout.readline()
                    signal.alarm(0)  # Cancel the alarm
                except TimeoutError:
                    raise MCPError(f"Server did not respond within {timeout} seconds")

            if not response_line:
                raise MCPError("No response from server")

            response = json.loads(response_line)

            if "error" in response:
                raise MCPError(f"Server error: {response['error']}")

            return response.get("result", {})

        except Exception as e:
            self.logger.error(f"Error communicating with MCP server: {e}")
            raise MCPError(f"Communication error: {e}")

    def list_tools(self, brief: bool = True) -> List[Dict[str, Any]]:
        """Get list of available tools from server."""
        cache_key = f"tools_{'brief' if brief else 'detailed'}"
        current_time = time.time()

        cached_tools = getattr(self, f"_{cache_key}_cache", None)
        cache_time = getattr(self, f"_{cache_key}_cache_time", 0)

        if cached_tools and (current_time - cache_time) < 60:
            return cached_tools if isinstance(cached_tools, list) else []

        try:
            params = {"brief": brief} if brief else {}
            result = self.send_request("tools/list", params)
            tools_data = result.get("tools", []) if isinstance(result, dict) else []

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

            setattr(self, f"_{cache_key}_cache", openai_tools)
            setattr(self, f"_{cache_key}_cache_time", current_time)

            return openai_tools

        except Exception as e:
            self.logger.error(f"Error listing tools: {e}")
            return []

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the server."""
        params = {"name": tool_name, "arguments": arguments}
        return self.send_request("tools/call", params)
