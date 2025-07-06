"""Server mode implementation for AIxTerm."""

import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional

from .config import AIxTermConfig
from .context import TerminalContext
from .llm import LLMClient
from .mcp_client import MCPClient
from .utils import get_logger


class AIxTermServer:
    """AIxTerm server for handling HTTP requests."""

    def __init__(self, config: AIxTermConfig):
        """Initialize AIxTerm server.

        Args:
            config: AIxTerm configuration
        """
        self.config = config
        self.logger = get_logger(__name__)

        # Initialize components
        self.context_manager = TerminalContext(self.config)
        self.mcp_client = MCPClient(self.config)
        self.llm_client = LLMClient(self.config, self.mcp_client)

        self.server: Optional[HTTPServer] = None

    async def initialize(self) -> None:
        """Initialize server components."""
        # Initialize MCP client if needed
        if self.config.get_mcp_servers():
            self.mcp_client.initialize()

    def start(self) -> None:
        """Start the AIxTerm server."""
        host = self.config.get_server_host()
        port = self.config.get_server_port()

        self.logger.info(f"Starting AIxTerm server on {host}:{port}")

        # Initialize server components
        asyncio.run(self.initialize())

        # Create HTTP server
        handler = self._create_request_handler()
        self.server = HTTPServer((host, port), handler)

        try:
            print(f"AIxTerm server running on http://{host}:{port}")
            print("Endpoints:")
            print("  POST /query - Send AI queries")
            print("  GET /status - Get server status")
            print("  GET /tools - List available tools")
            print("Press Ctrl+C to stop")

            self.server.serve_forever()
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Stop the AIxTerm server."""
        self.logger.info("Stopping AIxTerm server")
        if self.server:
            self.server.shutdown()

        try:
            self.mcp_client.shutdown()
        except Exception as e:
            self.logger.error(f"Error shutting down MCP client: {e}")

    def _create_request_handler(self) -> type:
        """Create HTTP request handler class."""
        server_instance = self

        class AIxTermRequestHandler(BaseHTTPRequestHandler):
            """HTTP request handler for AIxTerm."""

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.server_instance = server_instance
                super().__init__(*args, **kwargs)

        return AIxTermRequestHandler
