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
    ) -> None:
        """Process tool calls and add results to conversation.

        Args:
            tool_calls: List of tool call objects
            conversation_messages: Current conversation messages
            tools: Available tools
            iteration: Current iteration number
            max_context_size: Maximum context size in tokens
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
            self.logger.info(f"[Tool Call: {function_name}]")

            # Execute the tool
            try:
                result = self.execute_tool_call(
                    function_name,
                    function.get("arguments", "{}"),
                    tools,
                )

                # Debug: log the raw tool result to understand its format
                self.logger.debug(
                    f"Raw tool result for {function_name}: {type(result)} = "
                    f"{str(result)[:300]}..."
                )

                # Smart context management for tool results
                # Calculate remaining context budget after conversation
                # so far using proper token counting
                conversation_tokens = token_manager.count_tokens_for_messages(
                    conversation_messages,
                    self.config.get("model", "gpt-3.5-turbo"),
                )
                remaining_context = max_context_size - conversation_tokens

                # Reserve space for continued conversation (at least 200 tokens)
                available_for_result = max(200, remaining_context // 2)
                # Use token-aware truncation instead of character estimation
                max_result_tokens = available_for_result

                # Extract and format tool result for LLM consumption
                result_content = self.extract_tool_result_content(result)

                # Apply token-based truncation
                result_content = token_manager.apply_token_limit(
                    result_content,
                    max_result_tokens,
                    self.config.get("model", "gpt-3.5-turbo"),
                )

                self.logger.debug(
                    f"Processed tool result for {function_name}: "
                    f"{result_content[:200]}..."
                )

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
            elif "result" in result:
                # Alternative result format
                result_content = str(result["result"])
            else:
                # Fallback: stringify the entire dict but make it readable
                if len(str(result)) > 500:
                    # For large results, try to extract key information
                    important_keys = [
                        "output",
                        "stdout",
                        "result",
                        "data",
                        "response",
                    ]
                    for key in important_keys:
                        if key in result:
                            result_content = str(result[key])
                            break
                if not result_content:
                    result_content = json.dumps(result, indent=2)
        else:
            # Non-dict result
            result_content = str(result)

        return result_content
