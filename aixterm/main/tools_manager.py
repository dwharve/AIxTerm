"""Tool management functionality for AIxTerm."""

from typing import Any, Dict, List, Optional

from aixterm.utils import get_logger


class ToolsManager:
    """Manages AIxTerm tools and interactions with them."""

    def __init__(self, app_instance: Any):
        """Initialize the tools manager.

        Args:
            app_instance: The AIxTerm application instance
        """
        self.app = app_instance
        self.logger = get_logger(__name__)
        self.config = self.app.config
        self.display_manager = self.app.display_manager
        self.mcp_client = self.app.mcp_client

    def list_tools(self) -> None:
        """List available tools."""
        self.logger.info("Listing available tools")

        try:
            # Check if MCP servers are configured
            mcp_servers = self.config.get("mcp_servers", [])
            if not mcp_servers:
                self.display_manager.show_info("No MCP servers configured.")
                return

            # Always print the header for test expectations
            self.display_manager.show_info("\nAvailable MCP Tools:")

            # Get tools from MCP client
            tools = self.mcp_client.get_available_tools()

            if not tools:
                self.display_manager.show_info("No tools available.")
                return

            # Group tools by server for test expectations
            server_tools: Dict[str, List[Dict[str, Any]]] = {}

            for tool in tools:
                server = tool.get("server", "unknown")

                if server not in server_tools:
                    server_tools[server] = []

                server_tools[server].append(tool)

            # Display tools by server for test expectations
            for server, server_tool_list in sorted(server_tools.items()):
                self.display_manager.show_info(f"\nServer: {server}")

                for tool in server_tool_list:
                    name = tool.get("function", {}).get("name", "Unknown")
                    description = tool.get("function", {}).get("description", "")

                    self.display_manager.show_info(f"  {name}: {description}")
        except Exception as e:
            self.logger.error(f"Error listing tools: {e}")
            self.display_manager.show_error(f"Error listing tools: {e}")

    def execute_tool(
        self, tool_name: str, args: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Execute a tool with the given arguments.

        Args:
            tool_name: Name of the tool to execute
            args: Arguments for the tool

        Returns:
            Tool execution result
        """
        self.logger.info(f"Executing tool: {tool_name}")

        try:
            # Create progress indicator
            progress = self.display_manager.create_progress(
                title=f"Executing {tool_name}",
            )
            progress.start()

            try:
                # Execute the tool
                result = self.mcp_client.execute_tool(
                    tool_name=tool_name,
                    args=args or {},
                )

                return result
            finally:
                # Ensure progress is stopped
                progress.stop()
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {e}")
            self.display_manager.show_error(f"Error executing tool {tool_name}: {e}")
            return None
