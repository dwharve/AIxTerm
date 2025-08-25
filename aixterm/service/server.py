"""
AIxTerm Service Server

This module provides the server component for the AIxTerm service, handling
communication with clients via sockets or HTTP.
"""

import asyncio
import datetime
import json
import logging
import os
import socket
import tempfile
import uuid
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)


class ServiceServer:
    """Socket server component for AIxTerm service (unified mode)."""

    def __init__(self, service):
        self.service = service
        from ..runtime_paths import get_socket_path

        # Maintain compatibility with any legacy server config keys
        self.config = service.config.get("server", {})
        self.socket_path = str(get_socket_path())
        self.socket: socket.socket | None = None
        self.mode = "socket"
        self._running = False
        self._tasks: set = set()
        self.handlers = self._register_handlers()

    def _register_handlers(self) -> Dict[str, Callable]:
        """
        Register request handlers for different request types.

        Returns:
            A dictionary mapping request types to handler functions.
        """
        return {
            "query": self._handle_query,
            "status": self._handle_status,
            "plugin": self._handle_plugin_request,
            "control": self._handle_control_request,
        }

    async def start(self):
        """Start server and begin accepting connections."""
        if self._running:
            logger.warning("Server is already running")
            return
        self._running = True
        await self._start_socket_server()

    async def _start_socket_server(self):
        """Start the socket-based server."""
        # Remove socket file if it already exists
        socket_path = self.socket_path
        try:
            if os.path.exists(socket_path):
                os.unlink(socket_path)
        except OSError as e:
            logger.error(f"Error removing existing socket file: {e}")
            raise

        # Create directory for socket if it doesn't exist
        os.makedirs(os.path.dirname(socket_path), exist_ok=True)

        # Start server
        logger.info(f"Starting socket server at {socket_path}")

        try:
            # On Unix systems, use AF_UNIX; on Windows, use AF_INET
            import platform

            if platform.system() != "Windows":
                self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                # type: ignore
                self.socket.bind(socket_path)
            else:
                # Use a TCP socket on Windows
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.bind(("127.0.0.1", 0))  # Use a random available port
                # Store the socket path to maintain interface consistency
                logger.info("Using TCP socket on Windows instead of Unix socket")

            self.socket.listen(5)
            self.socket.setblocking(False)

            # Start accepting connections
            accept_task = asyncio.create_task(self._accept_connections())
            self._tasks.add(accept_task)
            accept_task.add_done_callback(self._tasks.discard)

            logger.info("Socket server started successfully")

        except Exception as e:
            logger.error(f"Failed to start socket server: {e}")
            self._running = False
            raise

    # Unified socket mode only; HTTP implementation removed.

    async def stop(self):
        """Stop the server and close all connections."""
        if not self._running:
            logger.warning("Server is not running")
            return

        logger.info("Stopping server")
        self._running = False

        # Cancel all running tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    # Close socket
        if self.mode == "socket":
            if self.socket:
                self.socket.close()

            # Remove socket file
            try:
                if os.path.exists(self.socket_path):
                    os.unlink(self.socket_path)
            except OSError as e:
                logger.error(f"Error removing socket file: {e}")

    # No HTTP branch

        logger.info("Server stopped successfully")

    async def _accept_connections(self):
        """Accept client connections on the socket server."""
        logger.debug("Starting to accept connections")

        loop = asyncio.get_event_loop()

        while self._running:
            try:
                if self.socket:
                    client_sock, _ = await loop.sock_accept(self.socket)
                    client_sock.setblocking(False)

                    # Handle client connection in a separate task
                    client_task = asyncio.create_task(self._handle_client(client_sock))
                    self._tasks.add(client_task)
                    client_task.add_done_callback(self._tasks.discard)

            except asyncio.CancelledError:
                logger.debug("Accept connections task cancelled")
                break
            except Exception as e:
                if self._running:  # Only log if we're still supposed to be running
                    logger.error(f"Error accepting client connection: {e}")
                    # Add a small delay to avoid tight loop on errors
                    await asyncio.sleep(0.1)

    async def _handle_client(self, client_sock):
        """
        Handle communication with a connected client.

        Args:
            client_sock: The client socket.
        """
        loop = asyncio.get_event_loop()
        request_data = bytearray()

        try:
            # Read request data
            while True:
                chunk = await loop.sock_recv(client_sock, 4096)
                if not chunk:
                    break
                request_data.extend(chunk)

                # Check if we've received a complete message
                if b"\n" in request_data:
                    break

            if not request_data:
                logger.warning("Received empty request from client")
                return

            # Parse request
            try:
                request = json.loads(request_data.decode("utf-8"))
            except json.JSONDecodeError:
                logger.error("Received invalid JSON request")
                response = {
                    "status": "error",
                    "error": {
                        "code": "invalid_json",
                        "message": "Invalid JSON request",
                    },
                }
            else:
                # Process request
                response = await self._process_request(request)

            # Send response
            response_data = json.dumps(response).encode("utf-8") + b"\n"
            await loop.sock_sendall(client_sock, response_data)

        except asyncio.CancelledError:
            logger.debug("Client handler task cancelled")
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            # Close client socket
            try:
                client_sock.close()
            except Exception:
                pass

    # HTTP handlers removed.

    async def _process_request(self, request: Dict) -> Dict:
        """
        Process a request from a client.

        Args:
            request: The parsed request dictionary.

        Returns:
            A response dictionary.
        """
        # Extract request information
        request_id = request.get("id", str(uuid.uuid4()))
        request_type = request.get("type")
        # Get payload if needed for specific request types
        # payload = request.get("payload", {})

        logger.debug(f"Processing request {request_id} of type {request_type}")

        # Create base response
        response = {
            "request_id": request_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "status": "success",
        }

        try:
            # Route request to appropriate handler
            if request_type in self.handlers:
                handler = self.handlers[request_type]
                result = await handler(request)
                response.update(result)
            else:
                response.update(
                    {
                        "status": "error",
                        "error": {
                            "code": "unknown_request_type",
                            "message": f"Unknown request type: {request_type}",
                        },
                    }
                )
        except Exception as e:
            logger.error(f"Error processing request {request_id}: {e}")
            response.update(
                {
                    "status": "error",
                    "error": {"code": "processing_error", "message": str(e)},
                }
            )

        return response

    async def _handle_query(self, request: Dict) -> Dict:
        """
        Handle a query request.

        Args:
            request: The request dictionary.

        Returns:
            A response dictionary.
        """
        payload = request.get("payload", {})
        question = payload.get("question")
        options = payload.get("options", {})

        if not question:
            return {
                "status": "error",
                "error": {
                    "code": "missing_question",
                    "message": "No question provided",
                },
            }

        try:
            # Get context
            context = await self.service.context_manager.get_context(
                options.get("context", {})
            )

            # Query LLM
            response = await self.service.llm_client.query(
                question=question, context=context, stream=options.get("stream", False)
            )

            return {"status": "success", "result": response}
        except Exception as e:
            logger.error(f"Error handling query: {e}")
            return {
                "status": "error",
                "error": {"code": "query_error", "message": str(e)},
            }

    async def _handle_status(self, request: Dict) -> Dict:
        """
        Handle a status request.

        Args:
            request: The request dictionary.

        Returns:
            A response dictionary with service status.
        """
        status = self.service.status()
        return {"status": "success", "result": status}

    async def _handle_control_request(self, request: Dict) -> Dict:
        """Handle control commands (restart, etc.).

        Args:
            request: Request dict containing payload with 'command'.

        Returns:
            Response dict.
        """
        payload = request.get("payload", {})
        command = payload.get("command")
        if not command:
            return {
                "status": "error",
                "error": {"code": "missing_control_command", "message": "No control command provided"},
            }
        if command == "restart":
            # Perform async restart: stop then start fresh. Update service_id.
            try:
                await self.service.stop()
                # Assign a new service_id to differentiate after restart
                import uuid

                self.service.service_id = str(uuid.uuid4())
                await self.service.start()
                return {"status": "success", "result": {"message": "Service restarted", "service_id": self.service.service_id}}
            except Exception as e:
                logger.error(f"Failed to restart service: {e}")
                return {
                    "status": "error",
                    "error": {"code": "restart_failed", "message": str(e)},
                }
        else:
            return {"status": "error", "error": {"code": "unknown_control_command", "message": f"Unknown control command: {command}"}}

    async def _handle_plugin_request(self, request: Dict) -> Dict:
        """
        Handle a plugin request.

        Args:
            request: The request dictionary.

        Returns:
            A response dictionary from the plugin.
        """
        payload = request.get("payload", {})
        plugin_id = payload.get("plugin_id")
        plugin_command = payload.get("command")
        plugin_data = payload.get("data", {})

        if not plugin_id:
            return {
                "status": "error",
                "error": {
                    "code": "missing_plugin_id",
                    "message": "No plugin_id provided",
                },
            }

        if not plugin_command:
            return {
                "status": "error",
                "error": {
                    "code": "missing_plugin_command",
                    "message": "No command provided",
                },
            }

        try:
            # Forward request to plugin manager
            result = await self.service.plugin_manager.handle_request(
                plugin_id=plugin_id, command=plugin_command, data=plugin_data
            )

            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"Error handling plugin request: {e}")
            return {
                "status": "error",
                "error": {"code": "plugin_error", "message": str(e)},
            }

    def get_status(self) -> Dict[str, Any]:
        """
        Get server status information.

        Returns:
            A dictionary with server status.
        """
        status = {
            "running": self._running,
            "mode": self.mode,
            "connections": len(self._tasks),
            "socket_path": self.socket_path,
        }
        return status
