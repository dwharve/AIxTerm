"""
AIxTerm Client Implementation

This module provides the client implementation for AIxTerm, enabling connection to the AIxTerm service.
"""

import json
import logging
import os
import platform
import socket
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import AIxTermConfig

logger = logging.getLogger(__name__)


class AIxTermClient:
    """
    Client for AIxTerm service.

    This class provides the client-side functionality for communicating with the
    AIxTerm service.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the AIxTerm client.

        Args:
            config_path: Optional path to a configuration file.
        """
        # Load configuration
        self.config = AIxTermConfig(Path(config_path) if config_path else None)
        self.server_config = self.config.get("server_mode", {})
        self.mode = self.server_config.get("transport", "socket")

        # Socket settings
        self.socket_path = self._get_socket_path()

        # HTTP settings
        self.http_host = self.server_config.get("http_host", "localhost")
        self.http_port = self.server_config.get("http_port", 8087)

        # Client state
        self.connected = False
        self.client_id = str(uuid.uuid4())
        self.connection: Optional[socket.socket] = None

    def _get_socket_path(self) -> str:
        """
        Get the socket path from configuration or use a default.

        Returns:
            The path to the socket file.
        """
        socket_path = self.server_config.get("socket_path")

        if socket_path:
            path: str = os.path.expanduser(socket_path)
            return path

        # Default: use a socket file in the user's temp directory
        socket_dir = os.path.join(tempfile.gettempdir(), "aixterm")
        socket_path = os.path.join(socket_dir, "aixterm.sock")
        return socket_path

    def connect(self) -> bool:
        """
        Connect to the AIxTerm service.

        Returns:
            True if connection was successful, False otherwise.
        """
        if self.connected:
            return True

        if self.mode == "socket":
            return self._connect_socket()
        elif self.mode == "http":
            return self._connect_http()
        else:
            logger.error(f"Unsupported connection mode: {self.mode}")
            return False

    def _connect_socket(self) -> bool:
        """
        Connect to the AIxTerm service via socket.

        Returns:
            True if connection was successful, False otherwise.
        """
        try:
            # Check if socket file exists
            if not os.path.exists(self.socket_path):
                logger.error(f"Socket file not found: {self.socket_path}")
                logger.error("AIxTerm service may not be running")
                return False

            # Create socket based on platform
            # Windows doesn't support Unix sockets, use TCP instead
            if platform.system() == "Windows" or not hasattr(socket, "AF_UNIX"):
                # Use TCP socket on Windows or if AF_UNIX is not available
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(("localhost", 8087))  # Default port
                self.connection = sock
                logger.debug("Using TCP socket connection")
            else:
                # Use Unix socket on Unix-like systems
                unix_socket = getattr(socket, "AF_UNIX")
                sock = socket.socket(unix_socket, socket.SOCK_STREAM)
                sock.connect(self.socket_path)
                self.connection = sock
                logger.debug(f"Using Unix socket connection at {self.socket_path}")

            self.connected = True

            logger.debug("Connected to AIxTerm service via socket")
            return True

        except Exception as e:
            logger.error(f"Error connecting to AIxTerm service: {e}")
            self.connected = False
            self.connection = None
            return False

    def _connect_http(self) -> bool:
        """
        Connect to the AIxTerm service via HTTP.

        Returns:
            True if connection was successful, False otherwise.
        """
        try:
            # No actual connection needed for HTTP
            # Just check if the server is reachable
            import urllib.error
            import urllib.request

            url = f"http://{self.http_host}:{self.http_port}/status"
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    status_code = getattr(response, "status", 200)
            except urllib.error.HTTPError as e:
                status_code = e.code
            except urllib.error.URLError:
                status_code = 0

            if status_code == 200:
                self.connected = True
                logger.debug("Connected to AIxTerm service via HTTP")
                return True
            else:
                logger.error(f"Error connecting to AIxTerm service: HTTP {status_code}")
                self.connected = False
                return False

        except Exception as e:
            logger.error(f"HTTP check failed: {e}")
            self.connected = False
            return False

        except Exception as e:
            logger.error(f"Error connecting to AIxTerm service: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from the AIxTerm service."""
        if not self.connected:
            return

        if self.mode == "socket" and self.connection:
            try:
                self.connection.close()
            except Exception as e:
                logger.error(f"Error disconnecting from AIxTerm service: {e}")

        self.connected = False
        self.connection = None

    def query(self, question: str, **options) -> Dict[str, Any]:
        """
        Send a query to the AIxTerm service.

        Args:
            question: The question to ask.
            **options: Additional options for the query.

        Returns:
            The response from the service.
        """
        request = {
            "id": str(uuid.uuid4()),
            "type": "query",
            "timestamp": self._get_timestamp(),
            "payload": {"question": question, "options": options},
        }

        return self.send_request(request)

    def status(self) -> Dict[str, Any]:
        """
        Get the status of the AIxTerm service.

        Returns:
            The status information from the service.
        """
        request = {
            "id": str(uuid.uuid4()),
            "type": "status",
            "timestamp": self._get_timestamp(),
        }

        return self.send_request(request)

    def plugin_request(
        self, plugin_id: str, command: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a request to a plugin.

        Args:
            plugin_id: The ID of the plugin.
            command: The command to send to the plugin.
            data: Additional data for the command.

        Returns:
            The response from the plugin.
        """
        if data is None:
            data = {}

        request = {
            "id": str(uuid.uuid4()),
            "type": "plugin",
            "timestamp": self._get_timestamp(),
            "payload": {"plugin_id": plugin_id, "command": command, "data": data},
        }

        return self.send_request(request)

    def send_request(self, request: Dict) -> Dict[str, Any]:
        """
        Send a request to the AIxTerm service.

        Args:
            request: The request to send.

        Returns:
            The response from the service.
        """
        # Ensure we're connected
        if not self.connected and not self.connect():
            return {
                "status": "error",
                "error": {
                    "code": "connection_error",
                    "message": "Could not connect to AIxTerm service",
                },
            }

        if self.mode == "socket":
            return self._send_socket_request(request)
        elif self.mode == "http":
            return self._send_http_request(request)
        else:
            return {
                "status": "error",
                "error": {
                    "code": "unsupported_mode",
                    "message": f"Unsupported connection mode: {self.mode}",
                },
            }

    def _send_socket_request(self, request: Dict) -> Dict[str, Any]:
        """
        Send a request to the AIxTerm service via socket.

        Args:
            request: The request to send.

        Returns:
            The response from the service.
        """
        try:
            # Convert request to JSON
            request_data = json.dumps(request).encode("utf-8") + b"\n"

            # Check connection
            if not self.connection:
                logger.error("Not connected to AIxTerm service")
                return {
                    "status": "error",
                    "error": {
                        "code": "not_connected",
                        "message": "Not connected to AIxTerm service",
                    },
                }

            # Send request
            self.connection.sendall(request_data)

            # Read response
            response_data = b""
            while True:
                chunk = self.connection.recv(4096)
                if not chunk:
                    break
                response_data += chunk

                # Check if we've received a complete message
                if b"\n" in response_data:
                    break

            # Parse response
            response_text = response_data.decode("utf-8")
            response: Dict[str, Any] = json.loads(response_text)
            return response

        except Exception as e:
            logger.error(f"Error sending request to AIxTerm service: {e}")
            self.connected = False
            self.connection = None

            return {
                "status": "error",
                "error": {"code": "communication_error", "message": str(e)},
            }

    def _send_http_request(self, request: Dict) -> Dict[str, Any]:
        """
        Send a request to the AIxTerm service via HTTP.

        Args:
            request: The request to send.

        Returns:
            The response from the service.
        """
        try:
            import urllib.error
            import urllib.request

            url = f"http://{self.http_host}:{self.http_port}/api"
            data = json.dumps(request).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_body = resp.read().decode("utf-8")
                    json_response: Dict[str, Any] = json.loads(resp_body)
                    return json_response
            except urllib.error.HTTPError as e:
                return {
                    "status": "error",
                    "error": {
                        "code": f"http_{e.code}",
                        "message": f"HTTP error: {e.code}",
                    },
                }
            except urllib.error.URLError as e:
                return {
                    "status": "error",
                    "error": {
                        "code": "connection_error",
                        "message": f"Failed to connect: {e.reason}",
                    },
                }

        except Exception as e:
            logger.error(f"Error sending HTTP request to AIxTerm service: {e}")

            return {
                "status": "error",
                "error": {"code": "communication_error", "message": str(e)},
            }

    def _get_timestamp(self) -> str:
        """
        Get the current timestamp in ISO format.

        Returns:
            The current timestamp.
        """
        import datetime

        return datetime.datetime.now().isoformat()

    def __enter__(self):
        """Enter context manager."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        self.disconnect()
