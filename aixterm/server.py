"""Server mode implementation for AIxTerm."""

import asyncio
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional
from urllib.parse import urlparse

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
        self.server_thread = None

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

            def do_GET(self) -> None:
                """Handle GET requests."""
                parsed_path = urlparse(self.path)
                path = parsed_path.path

                if path == "/status":
                    self._handle_status()
                elif path == "/tools":
                    self._handle_tools()
                elif path == "/":
                    self._handle_root()
                else:
                    self._send_error(404, "Not Found")

            def do_POST(self) -> None:
                """Handle POST requests."""
                parsed_path = urlparse(self.path)
                path = parsed_path.path

                if path == "/query":
                    self._handle_query()
                else:
                    self._send_error(404, "Not Found")

            def _handle_root(self) -> None:
                """Handle root endpoint."""
                response = {
                    "service": "AIxTerm",
                    "status": "running",
                    "endpoints": {
                        "POST /query": "Send AI queries",
                        "GET /status": "Get server status",
                        "GET /tools": "List available tools",
                    },
                }
                self._send_json_response(response)

            def _handle_status(self) -> None:
                """Handle status endpoint."""
                mcp_servers = self.server_instance.config.get_mcp_servers()

                # Get MCP server status if available
                server_status = {}
                if mcp_servers:
                    try:
                        server_status = (
                            self.server_instance.mcp_client.get_server_status()
                        )
                    except Exception as e:
                        self.server_instance.logger.error(
                            f"Error getting MCP status: {e}"
                        )

                response = {
                    "status": "running",
                    "config": {
                        "model": self.server_instance.config.get("model"),
                        "api_url": self.server_instance.config.get("api_url"),
                        "context_size": (
                            self.server_instance.config.get_total_context_size()
                        ),
                        "mcp_servers": len(mcp_servers),
                    },
                    "mcp_servers": server_status,
                }
                self._send_json_response(response)

            def _handle_tools(self) -> None:
                """Handle tools endpoint."""
                try:
                    if not self.server_instance.config.get_mcp_servers():
                        response: dict = {
                            "tools": [],
                            "message": "No MCP servers configured",
                        }
                    else:
                        tools = self.server_instance.mcp_client.get_available_tools()
                        response = {"tools": tools}

                    self._send_json_response(response)
                except Exception as e:
                    self.server_instance.logger.error(f"Error getting tools: {e}")
                    self._send_error(500, f"Error getting tools: {e}")

            def _handle_query(self) -> None:
                """Handle query endpoint."""
                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                    post_data = self.rfile.read(content_length)

                    try:
                        data = json.loads(post_data.decode("utf-8"))
                    except json.JSONDecodeError:
                        self._send_error(400, "Invalid JSON")
                        return

                    query = data.get("query")
                    if not query:
                        self._send_error(400, "Missing 'query' field")
                        return

                    file_contexts = data.get("file_contexts", [])
                    use_planning = data.get("use_planning", False)

                    # Process the query
                    response = self._process_query(query, file_contexts, use_planning)
                    self._send_json_response(response)

                except Exception as e:
                    self.server_instance.logger.error(f"Error processing query: {e}")
                    self._send_error(500, f"Error processing query: {e}")

            def _process_query(
                self, query: str, file_contexts: list, use_planning: bool
            ) -> dict:
                """Process an AI query and return response."""
                try:
                    # Get optimized context
                    context = (
                        self.server_instance.context_manager.get_optimized_context(
                            file_contexts, query
                        )
                    )

                    # Get available tools
                    tools = None
                    if self.server_instance.config.get_mcp_servers():
                        try:
                            all_tools = (
                                self.server_instance.mcp_client.get_available_tools(
                                    brief=True
                                )
                            )
                            if all_tools:
                                import tiktoken

                                encoding = tiktoken.encoding_for_model("gpt-4")
                                context_tokens = len(encoding.encode(context))

                                context_manager = self.server_instance.context_manager
                                available_tool_tokens = (
                                    context_manager.get_available_tool_tokens(
                                        context_tokens
                                    )
                                )

                                tools = context_manager.optimize_tools_for_context(
                                    all_tools, query, available_tool_tokens
                                )
                        except Exception as e:
                            self.server_instance.logger.error(
                                f"Failed to get MCP tools: {e}"
                            )

                    # Send query to LLM
                    ai_response = self.server_instance.llm_client.ask_with_context(
                        query, context, tools, use_planning=use_planning
                    )

                    # Log the interaction
                    self.server_instance.context_manager.create_log_entry(
                        f"ai '{query}'", ai_response
                    )

                    return {
                        "success": True,
                        "query": query,
                        "response": ai_response,
                        "context_used": len(context),
                        "tools_available": len(tools) if tools else 0,
                    }

                except Exception as e:
                    return {"success": False, "query": query, "error": str(e)}

            def _send_json_response(self, data: dict, status_code: int = 200) -> None:
                """Send JSON response."""
                response_data = json.dumps(data, indent=2).encode("utf-8")

                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response_data)))
                self.send_header("Access-Control-Allow-Origin", "*")  # Enable CORS
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

                self.wfile.write(response_data)

            def _send_error(self, status_code: int, message: str) -> None:
                """Send error response."""
                error_response = {
                    "success": False,
                    "error": message,
                    "status_code": status_code,
                }
                self._send_json_response(error_response, status_code)

            def log_message(self, format: str, *args: Any) -> None:
                """Override to use our logger."""
                self.server_instance.logger.info(format % args)

        return AIxTermRequestHandler
