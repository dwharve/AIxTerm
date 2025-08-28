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
import time

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
    # Track last client activity (query/any processed request) for idle shutdown logic
    # Timestamp (float seconds) of last processed client request
        # Use monotonic loop time reference for consistent comparison
        try:
            self.last_activity = asyncio.get_event_loop().time()
        except Exception:
            self.last_activity = time.time()

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
        buffer = bytearray()
        try:
            while self._running:
                try:
                    chunk = await loop.sock_recv(client_sock, 4096)
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # socket-level error
                    logger.debug(f"Socket recv error, closing client connection: {e}")
                    break

                if not chunk:  # client closed connection
                    break
                buffer.extend(chunk)

                # Process all complete lines (messages) in buffer
                while b"\n" in buffer:
                    line, _, remainder = buffer.partition(b"\n")
                    buffer = bytearray(remainder)  # keep remainder (could be partial next msg)
                    if not line:
                        continue
                    try:
                        try:
                            request = json.loads(line.decode("utf-8"))
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
                            response = await self._process_request(request, client_sock)
                            # Update last activity after successful processing
                            try:
                                self.last_activity = asyncio.get_event_loop().time()
                            except Exception:
                                self.last_activity = time.time()

                        # If handler already streamed and sent final response, skip default send
                        if not (isinstance(response, dict) and response.get("already_sent")):
                            response_data = json.dumps(response).encode("utf-8") + b"\n"
                            await loop.sock_sendall(client_sock, response_data)
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        logger.error(f"Error processing client message: {e}")
                        # Send generic error then continue (don't drop connection unless severe)
                        try:
                            err_resp = json.dumps({
                                "status": "error",
                                "error": {"code": "handler_error", "message": str(e)},
                            }).encode("utf-8") + b"\n"
                            await loop.sock_sendall(client_sock, err_resp)
                        except Exception:
                            # If we can't send the error, close
                            buffer.clear()
                            break
        except asyncio.CancelledError:
            logger.debug("Client handler task cancelled")
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    # HTTP handlers removed.

    async def _process_request(self, request: Dict, client_sock=None) -> Dict:
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
                # Pass client_sock to handlers that accept it (like _handle_query for streaming)
                try:
                    result = await handler(request, client_sock)  # type: ignore[arg-type]
                except TypeError:
                    result = await handler(request)  # type: ignore[misc]
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

    async def _handle_query(self, request: Dict, client_sock=None) -> Dict:
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
            # Get context (currently not deeply consumed by process_query; OK to prepare)
            context = await self.service.context_manager.get_context(
                options.get("context", {})
            )

            # Prepare simple context lines from terminal history
            context_lines = None
            try:
                th = (context or {}).get("terminal_history") or {}
                recent = th.get("recent_commands") or []
                if isinstance(recent, list) and recent:
                    context_lines = [str(c) for c in recent]
            except Exception:
                context_lines = None

            use_stream = bool(options.get("stream", False)) and client_sock is not None

            # If streaming requested, set up a queue and sender to relay chunks
            if use_stream:
                import asyncio as _asyncio
                loop = _asyncio.get_event_loop()
                queue: _asyncio.Queue = _asyncio.Queue()

                async def _sender():
                    try:
                        # Send stream_start
                        start_msg = {
                            "status": "success",
                            "event": "stream_start",
                            "request_id": request.get("id"),
                            "timestamp": datetime.datetime.now().isoformat(),
                        }
                        await loop.sock_sendall(client_sock, (json.dumps(start_msg) + "\n").encode("utf-8"))
                        while True:
                            item = await queue.get()
                            if item is None:
                                break
                            chunk_msg = {
                                "status": "success",
                                "event": "stream_chunk",
                                "text": item,
                                "request_id": request.get("id"),
                            }
                            await loop.sock_sendall(client_sock, (json.dumps(chunk_msg) + "\n").encode("utf-8"))
                    except Exception as e:
                        logger.error(f"Error sending stream chunk: {e}")

                sender_task = _asyncio.create_task(_sender())

                def _cb(text: str) -> None:
                    try:
                        queue.put_nowait(text)
                    except Exception:
                        pass

                # Run process_query with streaming and our callback in executor
                result = await loop.run_in_executor(
                    None,
                    lambda: self.service.llm_client.process_query(
                        query=question,
                        context_lines=context_lines,
                        show_thinking=True,
                        stream=True,
                        stream_callback=_cb,
                    ),
                )

                # Signal sender to finish and wait
                try:
                    queue.put_nowait(None)
                except Exception:
                    pass
                try:
                    await sender_task
                except Exception:
                    pass

                # Send stream_end with final result
                end_msg = {
                    "status": "success",
                    "event": "stream_end",
                    "result": result,
                    "request_id": request.get("id"),
                    "timestamp": datetime.datetime.now().isoformat(),
                }
                await loop.sock_sendall(client_sock, (json.dumps(end_msg) + "\n").encode("utf-8"))

                # Indicate that we've already sent the final response
                return {"already_sent": True}

            # Non-streaming path: delegate to synchronous process_query in a worker thread
            import asyncio as _asyncio
            loop = _asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.service.llm_client.process_query(
                    query=question,
                    context_lines=context_lines,
                    show_thinking=True,
                    stream=False,
                ),
            )

            return {"status": "success", "result": result}
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
            # Schedule restart asynchronously so we can reply before socket closes
            try:
                import asyncio as _asyncio

                async def _restart_task():
                    try:
                        await self.service.stop()
                        # Assign a new service_id to differentiate after restart
                        import uuid as _uuid

                        self.service.service_id = str(_uuid.uuid4())
                        await self.service.start()
                        logger.info("Service restarted successfully (ID: %s)", self.service.service_id)
                    except Exception as e:
                        logger.error(f"Failed to restart service asynchronously: {e}")

                # give a tiny delay to ensure response is flushed to client first
                async def _delayed_restart():
                    try:
                        await _asyncio.sleep(0.05)
                    except Exception:
                        pass
                    await _restart_task()

                _asyncio.create_task(_delayed_restart())

                return {"status": "success", "result": {"message": "Service restart initiated"}}
            except Exception as e:
                logger.error(f"Failed to schedule restart: {e}")
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
