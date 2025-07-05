"""Tool execution and handling for LLM requests."""

import json
from typing import Any, Callable, Dict, List, Optional


class ToolHandler:
    """Handles tool execution and processing for LLM requests."""

    def __init__(self, config_manager: Any, mcp_client: Any, logger: Any):
        """Initialize tool handler.

        Args:
            config_manager: Configuration manager instance
            mcp_client: MCP client instance for tool execution
            logger: Logger instance
        """
        self.config = config_manager
        self.mcp_client = mcp_client
        self.logger = logger
        self.progress_display_manager = None

    def set_progress_display_manager(self, progress_display_manager: Any) -> None:
        """Set the progress display manager for clearing displays during tool execution.

        Args:
            progress_display_manager: Progress display manager instance
        """
        self.progress_display_manager = progress_display_manager

    def execute_tool_call(
        self,
        function_name: str,
        arguments_str: str,
        tools: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None,
    ) -> Any:
        """Execute a tool call via the MCP client.

        Args:
            function_name: Name of the function to call
            arguments_str: JSON string of function arguments
            tools: List of available tools

        Returns:
            Tool execution result
        """
        # Find the tool and its server
        tool_info = None
        for tool in tools:
            if tool.get("function", {}).get("name") == function_name:
                tool_info = tool
                break

        if not tool_info:
            raise Exception(f"Tool {function_name} not found")

        server_name = tool_info.get("server")
        if not server_name:
            raise Exception(f"No server specified for tool {function_name}")

        # Parse arguments
        try:
            arguments = json.loads(arguments_str) if arguments_str else {}
            self.logger.debug(
                f"Calling tool {function_name} with arguments: {arguments}"
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid tool arguments: {e}")

        # Execute via MCP client with progress support if callback provided
        if progress_callback:
            return self.mcp_client.call_tool_with_progress(
                function_name, server_name, arguments, progress_callback
            )
        else:
            return self.mcp_client.call_tool(function_name, server_name, arguments)

    def process_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        conversation_messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        iteration: int,
        max_context_size: int,
        progress_callback_factory: Optional[Callable[[str, str], Callable]] = None,
    ) -> None:
        """Process tool calls and add results to conversation.

        Args:
            tool_calls: List of tool call objects
            conversation_messages: Current conversation messages
            tools: Available tools
            iteration: Current iteration number
            max_context_size: Maximum context size in tokens
            progress_callback_factory: Optional factory function to create
                progress callbacks
        """
        # Import here to avoid circular imports
        from ..context import TokenManager

        token_manager = TokenManager(self.config, self.logger)

        # Execute each tool call
        for tool_call in tool_calls:
            tool_call_id = tool_call.get("id", f"call_{iteration}")
            function = tool_call.get("function", {})
            function_name = function.get("name", "")

            self.logger.info(f"Executing tool: {function_name}")

            # Display tool execution to user
            self._display_tool_execution(function_name, function.get("arguments", "{}"))

            # Create progress callback if factory provided
            progress_callback = None
            if progress_callback_factory:
                try:
                    progress_callback = progress_callback_factory(
                        f"tool_{tool_call_id}", f"Executing {function_name}"
                    )
                except Exception as e:
                    self.logger.debug(f"Failed to create progress callback: {e}")

            # Execute the tool
            try:
                result = self.execute_tool_call(
                    function_name,
                    function.get("arguments", "{}"),
                    tools,
                    progress_callback,
                )

                # Debug: log the raw tool result to understand its format
                self.logger.debug(
                    f"Raw tool result for {function_name}: {type(result)} = "
                    f"{str(result)[:300]}..."
                )

                # Extract and format tool result for LLM consumption
                result_content = self.extract_tool_result_content(result)

                # Fresh tool results should NOT be truncated - they contain critical
                # information that the AI needs to see in full. Only apply token
                # limits to older tool results in conversation history during
                # intelligent summarization phases.

                # Log the full result size for monitoring
                result_tokens = token_manager.estimate_tokens(result_content)
                self.logger.debug(
                    f"Fresh tool result for {function_name}: {result_tokens} tokens, "
                    f"preserving full content for AI analysis"
                )

                self.logger.debug(
                    f"Processed tool result for {function_name}: "
                    f"{result_content[:200]}..."
                )

                # Display tool result to user
                self._display_tool_result(function_name, result_content, success=True)

                # Add tool result to conversation
                conversation_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": result_content,
                    }
                )

                self.logger.debug(
                    f"Tool {function_name} result: {result_content[:200]}..."
                )

            except Exception as e:
                self.logger.error(f"Tool execution failed: {e}")

                # Display tool failure to user
                self._display_tool_result(function_name, str(e), success=False)

                # Add error result to conversation
                conversation_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": f"Error: {str(e)}",
                    }
                )

    def extract_tool_result_content(self, result: Any) -> str:
        """Extract content from tool result.

        Args:
            result: Tool execution result

        Returns:
            Formatted content string
        """
        result_content = ""

        if isinstance(result, dict):
            # Handle Pythonium Result format with success/error fields
            if "success" in result and not result.get("success", True):
                # This is a failed result, extract the error message
                error_msg = result.get("error", "Unknown error occurred")
                return f"Error: {error_msg}"

            # Handle MCP response format
            if "content" in result:
                content_obj = result.get("content")
                if isinstance(content_obj, list) and len(content_obj) > 0:
                    # MCP format: {"content": [{"type": "text", "text": "..."}]}
                    first_content = content_obj[0]
                    if isinstance(first_content, dict) and "text" in first_content:
                        result_content = first_content["text"]
                    else:
                        result_content = str(first_content)
                elif isinstance(content_obj, str):
                    # Simple string content
                    result_content = content_obj
                else:
                    result_content = str(content_obj)
            elif "data" in result:
                # Handle Pythonium Result format with data field
                data_obj = result.get("data")
                if isinstance(data_obj, dict):
                    # For structured data, format it as JSON for better readability
                    result_content = json.dumps(data_obj, indent=2)
                else:
                    result_content = str(data_obj) if data_obj is not None else ""
            elif "result" in result:
                # Alternative result format
                result_content = str(result["result"])
            elif "output" in result:
                # Handle output format
                result_content = str(result["output"])
            elif "stdout" in result:
                # Handle stdout format
                result_content = str(result["stdout"])
            elif "response" in result:
                # Handle response format
                result_content = str(result["response"])
            else:
                # Unknown dict format - convert to readable JSON
                result_content = json.dumps(result, indent=2)
        else:
            # Non-dict result
            result_content = str(result)

        return result_content

    def _display_tool_execution(self, function_name: str, arguments_str: str) -> None:
        """Display tool execution to user.

        Args:
            function_name: Name of the tool being executed
            arguments_str: JSON string of arguments
        """
        try:
            # Parse arguments for display
            arguments = json.loads(arguments_str) if arguments_str else {}

            # Format arguments for display
            arg_display = []
            for key, value in arguments.items():
                if isinstance(value, str) and len(value) > 50:
                    # Truncate long string values
                    value_display = value[:47] + "..."
                else:
                    value_display = value
                arg_display.append(f"{key}: {json.dumps(value_display)}")

            args_formatted = ", ".join(arg_display) if arg_display else "(no arguments)"

            # Display the tool execution
            print(f"{function_name}: {args_formatted}")

        except Exception as e:
            # Fallback display if argument parsing fails
            print(f"{function_name}: {arguments_str}")
            self.logger.debug(f"Failed to parse tool arguments for display: {e}")

    def _display_tool_result(
        self, function_name: str, result_content: str, success: bool = True
    ) -> None:
        """Display tool execution result to user.

        Args:
            function_name: Name of the tool that was executed
            result_content: The result content
            success: Whether the execution was successful
        """
        try:
            if success:
                # Try to extract key information for brief display
                if "Found" in result_content and "result" in result_content:
                    # Extract result count from "Found X results" pattern
                    lines = result_content.split("\n")
                    if lines:
                        header = lines[0]
                        if "Found 0" in header or "No results" in result_content:
                            print(f"→ {function_name} completed (no results found)")
                        else:
                            # Extract number from "Found X results" or search results
                            import re

                            match = re.search(r"Found (\d+) (?:search )?result", header)
                            if match:
                                count = match.group(1)
                                print(
                                    f"→ {function_name} completed "
                                    f"({count} results found)"
                                )
                            else:
                                print(f"→ {function_name} completed")
                    else:
                        print(f"→ {function_name} completed")
                else:
                    # Generic success display for other tools
                    print(f"→ {function_name} completed")
            else:
                # Error display
                print(f"→ {function_name} failed")

        except Exception as e:
            # Fallback display
            status = "completed" if success else "failed"
            print(f"→ {function_name} {status}")
            self.logger.debug(f"Failed to format tool result display: {e}")
