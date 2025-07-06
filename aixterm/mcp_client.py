"""Model Context Protocol (MCP) client implementation using the official SDK."""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .utils import get_logger


@dataclass
class ProgressParams:
    """Progress notification parameters."""

    progress_token: Union[str, int]
    progress: int
    total: Optional[int] = None
    message: Optional[str] = None


class ProgressCallback:
    """Wrapper for progress callback functions with timeout support."""

    def __init__(
        self,
        callback: Callable[[ProgressParams], None],
        timeout: Optional[float] = None,
    ):
        """Initialize progress callback.

        Args:
            callback: The callback function to execute
            timeout: Optional timeout in seconds
        """
        self.callback = callback
        self.timeout = timeout
        self.start_time = time.time()
        self.logger = get_logger(__name__)

    def __call__(self, params: ProgressParams) -> None:
        """Execute the callback with error handling."""
        try:
            self.callback(params)
        except Exception as e:
            self.logger.error(f"Error in progress callback: {e}")

    def is_expired(self) -> bool:
        """Check if the callback has expired."""
        if self.timeout is None:
            return False
        return time.time() - self.start_time > self.timeout


class MCPError(Exception):
    """Exception raised for MCP-related errors."""

    pass


class MCPClient:
    """Client for communicating with MCP servers using the official SDK."""

    def __init__(self, config_manager: Any) -> None:
        """Initialize MCP client.

        Args:
            config_manager: AIxTermConfig instance
        """
        self.config = config_manager
        self.logger = get_logger(__name__)
        self.servers: Dict[str, "MCPServer"] = {}
        self._initialized = False
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="mcp-client"
        )
        # Event loop for async operations
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._start_event_loop()

        # Progress callback management (for backward compatibility)
        self._progress_callbacks: Dict[Union[str, int], ProgressCallback] = {}
        self._progress_lock = threading.Lock()

    def _start_event_loop(self) -> None:
        """Start background event loop for async operations."""

        def run_loop() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

        # Wait for loop to be ready
        while self._loop is None:
            time.sleep(0.01)

    def register_progress_callback(
        self,
        token: Union[str, int],
        callback: Callable[[ProgressParams], None],
        timeout: Optional[float] = None,
    ) -> None:
        """Register a progress callback for a specific token.

        Args:
            token: Progress token to register callback for
            callback: Callback function to execute
            timeout: Optional timeout in seconds
        """
        with self._progress_lock:
            self._progress_callbacks[token] = ProgressCallback(callback, timeout)

    def unregister_progress_callback(self, token: Union[str, int]) -> None:
        """Unregister a progress callback.

        Args:
            token: Progress token to unregister
        """
        with self._progress_lock:
            self._progress_callbacks.pop(token, None)

    def handle_progress_notification(self, notification: Dict[str, Any]) -> None:
        """Handle progress notifications from MCP servers.

        Args:
            notification: Progress notification from server
        """
        params = notification.get("params", {})
        token = params.get("progressToken")

        if token is None:
            self.logger.warning("Received progress notification without token")
            return

        with self._progress_lock:
            callback = self._progress_callbacks.get(token)
            if callback is None:
                self.logger.debug(f"No callback registered for progress token: {token}")
                return

            if callback.is_expired():
                self.logger.debug(f"Callback for token {token} has expired")
                del self._progress_callbacks[token]
                return

            # Create progress params
            progress_params = ProgressParams(
                progress_token=token,
                progress=params.get("progress", 0),
                total=params.get("total"),
                message=params.get("message"),
            )

            # Execute callback
            try:
                callback(progress_params)
            except Exception as e:
                self.logger.error(f"Error in progress callback for token {token}: {e}")

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

            if expired_tokens:
                self.logger.debug(
                    f"Cleaned up {len(expired_tokens)} expired progress callbacks"
                )

    def initialize(self) -> None:
        """Initialize MCP servers."""
        if self._initialized:
            return

        server_configs = self.config.get_mcp_servers()
        self.logger.info(f"Initializing {len(server_configs)} MCP servers")

        for server_config in server_configs:
            try:
                # Ensure we have a valid loop
                if self._loop is None:
                    raise MCPError("Event loop not initialized")
                server = MCPServer(server_config, self.logger, self._loop)
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
        progress_token = f"tool_{int(time.time() * 1000)}"

        # Register progress callback if provided
        if progress_callback:
            self.register_progress_callback(progress_token, progress_callback, timeout)

        try:
            # Send start progress if callback provided
            if progress_callback:
                start_params = ProgressParams(
                    progress_token=progress_token,
                    progress=0,
                    total=100,
                    message=f"Starting {tool_name}...",
                )
                progress_callback(start_params)

            # Call tool - server will send progress notifications
            result = self.call_tool(tool_name, server_name, arguments)

            # Send completion progress if callback provided
            if progress_callback:
                completion_params = ProgressParams(
                    progress_token=progress_token,
                    progress=100,
                    total=100,
                    message=f"Completed {tool_name}",
                )
                progress_callback(completion_params)

            return result

        except Exception as e:
            # Send error progress if callback provided
            if progress_callback:
                error_params = ProgressParams(
                    progress_token=progress_token,
                    progress=100,
                    total=100,
                    message=f"Failed {tool_name}: {str(e)}",
                )
                progress_callback(error_params)
            raise
        finally:
            # Unregister progress callback
            if progress_callback:
                self.unregister_progress_callback(progress_token)

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

        # Clear progress callbacks
        with self._progress_lock:
            self._progress_callbacks.clear()

        # Shutdown executor
        self._executor.shutdown(wait=True)

        # Stop event loop
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=2.0)

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
    """Represents a single MCP server instance using the official SDK."""

    def __init__(
        self, config: Dict[str, Any], logger: Any, loop: asyncio.AbstractEventLoop
    ) -> None:
        """Initialize MCP server.

        Args:
            config: Server configuration
            logger: Logger instance
            loop: Event loop for async operations
        """
        self.config = config
        self.logger = logger
        self.loop = loop
        self.start_time: Optional[float] = None
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        self._tools_cache_time: float = 0
        self._initialized: bool = False
        self._session: Optional[ClientSession] = None
        self._client_context: Optional[Any] = None  # Type for async context manager
        self._server_params: Optional[StdioServerParameters] = None
        self._notification_task: Optional[asyncio.Task] = None
        self._init_task: Optional[Any] = None  # Weak reference to initialization task

    def start(self) -> None:
        """Start the MCP server."""
        if self.is_running():
            return

        try:
            # Create server parameters
            command = self.config["command"]
            args = self.config.get("args", [])
            env = self.config.get("env", {})

            # Handle different command formats
            if isinstance(command, str):
                command = [command]

            if args:
                command.extend(args)

            self._server_params = StdioServerParameters(
                command=command[0],
                args=command[1:] if len(command) > 1 else [],
                env=env if env else None,
            )

            self.logger.info(f"Starting MCP server: {command}")

            # Initialize session in the event loop
            future = asyncio.run_coroutine_threadsafe(
                self._initialize_session(), self.loop
            )
            future.result(timeout=30)  # 30 second timeout

            self.start_time = time.time()
            self._initialized = True
            self.logger.info("MCP server started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start MCP server: {e}")
            raise MCPError(f"Failed to start MCP server: {e}")

    async def _initialize_session(self) -> None:
        """Initialize MCP session asynchronously."""
        if self._server_params is None:
            raise MCPError("Server parameters not initialized")

        # Store the current task to ensure cleanup happens in the same context
        import weakref

        self._init_task = weakref.ref(asyncio.current_task())

        try:
            self._client_context = stdio_client(self._server_params)
            read_stream, write_stream = await self._client_context.__aenter__()

            self._session = ClientSession(read_stream, write_stream)
            await self._session.__aenter__()

            # Initialize the connection
            await self._session.initialize()

            # Start notification listener
            self._start_notification_listener()
        except Exception:
            # Ensure proper cleanup on initialization failure
            await self._cleanup_session_safely()
            raise

    def _start_notification_listener(self) -> None:
        """Start listening for notifications from the server."""
        if self._session is None:
            return

        # Start a task to listen for notifications
        self._notification_task = asyncio.create_task(self._listen_for_notifications())

    async def _listen_for_notifications(self) -> None:
        """Listen for notifications from the server."""
        if self._session is None:
            return

        try:
            # Create a simple notification listener
            # This is a simplified implementation - in practice, you'd want to
            # integrate with the MCP SDK's notification system
            while True:
                # Check if we have a parent client to route notifications to
                if hasattr(self.logger, "parent_client"):
                    # This is where we would process incoming notifications
                    # For now, just sleep to prevent busy waiting
                    await asyncio.sleep(0.1)
                else:
                    break
        except asyncio.CancelledError:
            # Task was cancelled, exit gracefully
            pass
        except Exception as e:
            self.logger.error(f"Error in notification listener: {e}")

    def stop(self) -> None:
        """Stop the MCP server."""
        if not self.is_running():
            return

        try:
            # Cancel notification task if running
            if self._notification_task and not self._notification_task.done():
                self._notification_task.cancel()
                self._notification_task = None

            # Clean up session in the event loop
            if self._session and self.loop:
                future = asyncio.run_coroutine_threadsafe(
                    self._shielded_cleanup_session(), self.loop
                )
                try:
                    future.result(timeout=5)
                except asyncio.TimeoutError:
                    self.logger.warning("Session cleanup timed out")
                except Exception as e:
                    self.logger.error(f"Error during session cleanup: {e}")

            self.start_time = None
            self._tools_cache = None
            self._initialized = False
            self._session = None
            self._client_context = None

        except Exception as e:
            self.logger.error(f"Error stopping MCP server: {e}")

    async def _cleanup_session_safely(self) -> None:
        """Clean up session safely, checking if we're in the right task context."""
        try:
            # Check if we're in the same task that initialized the session
            current_task = asyncio.current_task()
            if (
                self._init_task
                and self._init_task() is not None
                and self._init_task() == current_task
            ):
                # We're in the same task context, safe to call __aexit__
                if self._session:
                    try:
                        await self._session.__aexit__(None, None, None)
                    except Exception as e:
                        self.logger.debug(f"Session cleanup error: {e}")
                    finally:
                        self._session = None

                if self._client_context:
                    try:
                        await self._client_context.__aexit__(None, None, None)
                    except Exception as e:
                        self.logger.debug(f"Client context cleanup error: {e}")
                    finally:
                        self._client_context = None
            else:
                # Different task context, just clear references
                self._session = None
                self._client_context = None

        except Exception as e:
            self.logger.debug(f"Error during safe session cleanup: {e}")
            # Fallback: just clear references
            self._session = None
            self._client_context = None

    async def _shielded_cleanup_session(self) -> None:
        """Run session cleanup safely to avoid context manager issues."""
        # Use the safe cleanup method that checks task context
        await self._cleanup_session_safely()

    def is_running(self) -> bool:
        """Check if server is running."""
        return self._initialized and self._session is not None

    def get_pid(self) -> Optional[int]:
        """Get server process PID (not available with SDK)."""
        return None  # SDK doesn't expose PID

    def get_uptime(self) -> Optional[float]:
        """Get server uptime in seconds."""
        if not self.start_time:
            return None
        return time.time() - self.start_time

    def list_tools(self, brief: bool = True) -> List[Dict[str, Any]]:
        """List available tools from the server.

        Args:
            brief: Whether to request brief descriptions

        Returns:
            List of tool definitions
        """
        if not self.is_running():
            raise MCPError("Server is not running")

        # Check cache
        cache_timeout = 30  # 30 seconds
        if (
            self._tools_cache is not None
            and time.time() - self._tools_cache_time < cache_timeout
        ):
            return self._tools_cache

        try:
            # Get tools from server
            future = asyncio.run_coroutine_threadsafe(
                self._list_tools_async(), self.loop
            )
            result = future.result(timeout=10)

            # Convert to OpenAI function calling format
            tools = []
            for tool in result.tools:
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema or {},
                    },
                }
                tools.append(tool_def)

            # Cache the result
            self._tools_cache = tools
            self._tools_cache_time = time.time()

            return tools

        except Exception as e:
            self.logger.error(f"Error listing tools: {e}")
            raise MCPError(f"Failed to list tools: {e}")

    async def _list_tools_async(self) -> Any:
        """List tools asynchronously."""
        if not self._session:
            raise MCPError("Session not initialized")
        return await self._session.list_tools()

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result
        """
        if not self.is_running():
            raise MCPError("Server is not running")

        try:
            # Call tool via session
            future = asyncio.run_coroutine_threadsafe(
                self._call_tool_async(tool_name, arguments), self.loop
            )
            result = future.result(timeout=self.config.get("timeout", 30))

            # Extract content from result - handle both MCP and Pythonium formats
            if hasattr(result, "content") and result.content:
                # Standard MCP protocol format
                content_parts = []
                for content in result.content:
                    if hasattr(content, "text"):
                        content_parts.append(content.text)
                    elif hasattr(content, "data"):
                        content_parts.append(str(content.data))
                    else:
                        content_parts.append(str(content))

                return "\n".join(content_parts) if content_parts else ""
            elif hasattr(result, "success") and hasattr(result, "data"):
                # Pythonium Result object format
                if not result.success:
                    # Error result
                    error_msg = getattr(result, "error", "Unknown error")
                    return f"Error: {error_msg}"
                else:
                    # Success result - return the data
                    data = getattr(result, "data", None)
                    return str(data) if data is not None else ""
            else:
                return str(result)

        except Exception as e:
            self.logger.error(f"Error calling tool {tool_name}: {e}")
            raise MCPError(f"Tool call failed: {e}")

    async def _call_tool_async(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call tool asynchronously."""
        if not self._session:
            raise MCPError("Session not initialized")
        return await self._session.call_tool(tool_name, arguments)
