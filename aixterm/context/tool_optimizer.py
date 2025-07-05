"""Tool optimization for context management."""

from typing import Any, Dict, List, Optional

import tiktoken


class ToolOptimizer:
    """Handles tool optimization and prioritization for context management."""

    def __init__(self, config_manager: Any, logger: Any, token_manager: Any) -> None:
        """Initialize tool optimizer.

        Args:
            config_manager: Configuration manager instance
            logger: Logger instance
            token_manager: Token manager instance
        """
        self.config = config_manager
        self.logger = logger
        self.token_manager = token_manager

    def optimize_tools_for_context(
        self, tools: List[Dict], query: str, available_tokens: int
    ) -> List[Dict]:
        """Intelligently optimize tools for available context space.

        Args:
            tools: List of tool definitions
            query: User query for context-aware prioritization
            available_tokens: Number of tokens available for tools

        Returns:
            Optimized list of tools that fit within available context
        """
        if not tools:
            return tools

        # Always use intelligent prioritization and token fitting
        prioritized_tools = self._prioritize_tools(tools, query)
        return self._fit_tools_to_tokens(prioritized_tools, available_tokens)

    def _prioritize_tools(self, tools: List[Dict], query: str) -> List[Dict]:
        """Prioritize tools based on relevance and utility.

        Args:
            tools: List of tool definitions
            query: User query for context-aware prioritization

        Returns:
            Tools sorted by priority (highest first)
        """
        query_lower = query.lower()

        def get_tool_priority(tool: Dict) -> int:
            """Calculate priority score for a tool."""
            function = tool.get("function", {})
            name = function.get("name", "").lower()
            description = function.get("description", "").lower()

            # Start with configured tool priorities
            configured_priorities = self.config.get(
                "tool_management.tool_priorities", {}
            )
            score: int = configured_priorities.get(name, 0)

            # If no specific priority configured, use keyword-based scoring
            if score == 0:
                # Essential system tools (highest priority)
                essential_keywords = [
                    "execute",
                    "command",
                    "run",
                    "shell",
                    "terminal",
                    "system",
                ]
                if any(keyword in name for keyword in essential_keywords):
                    score = 1000

                # File operations (very high priority)
                elif any(
                    keyword in name
                    for keyword in [
                        "file",
                        "read",
                        "write",
                        "list",
                        "directory",
                        "find",
                        "search",
                        "create",
                        "delete",
                        "move",
                        "copy",
                    ]
                ):
                    score = 800

                # Development tools (high priority)
                elif any(
                    keyword in name
                    for keyword in [
                        "git",
                        "build",
                        "compile",
                        "test",
                        "debug",
                        "package",
                        "install",
                        "deploy",
                    ]
                ):
                    score = 600

                # Data processing tools (medium-high priority)
                elif any(
                    keyword in name
                    for keyword in [
                        "parse",
                        "format",
                        "convert",
                        "transform",
                        "process",
                        "analyze",
                    ]
                ):
                    score = 400

                # Web and network tools
                elif any(
                    keyword in name
                    for keyword in [
                        "web",
                        "search",
                        "download",
                        "request",
                        "url",
                        "http",
                    ]
                ):
                    score = 300

                # Default priority for unmatched tools
                else:
                    score = 100

            # Context-aware prioritization based on query
            query_keywords = query_lower.split()
            for keyword in query_keywords:
                if keyword in name:
                    score += 300  # Direct name match
                elif keyword in description:
                    score += 150  # Description match

            # Tool name length (shorter names often indicate core functionality)
            if len(name) <= 10:
                score += 50
            elif len(name) <= 15:
                score += 25

            # Penalize overly complex tools if we have simpler alternatives
            if len(description) > 200:
                score -= 50

            return score

        # Sort tools by priority score (descending)
        tools_with_scores = [(tool, get_tool_priority(tool)) for tool in tools]
        tools_with_scores.sort(key=lambda x: x[1], reverse=True)

        # Log top tools with their priorities for debugging
        top_5_tools = tools_with_scores[:5]
        top_5_info = [
            f"{t[0].get('function', {}).get('name', 'unknown')}({t[1]})"
            for t in top_5_tools
        ]
        self.logger.debug(f"Tool prioritization complete. Top 5 tools: {top_5_info}")

        return [tool for tool, _ in tools_with_scores]

    def _fit_tools_to_tokens(
        self, tools: List[Dict], available_tokens: int
    ) -> List[Dict]:
        """Fit tools within available token budget.

        Args:
            tools: List of prioritized tools
            available_tokens: Maximum tokens available for tools

        Returns:
            Tools that fit within token budget
        """
        if not tools:
            return tools

        # Calculate precise token usage for tools
        encoding = tiktoken.encoding_for_model("gpt-4")
        fitted_tools = []
        current_tokens = 0

        for tool in tools:
            # Calculate actual tokens for this tool
            tool_json = str(tool)
            tool_tokens = len(encoding.encode(tool_json))

            if current_tokens + tool_tokens <= available_tokens:
                fitted_tools.append(tool)
                current_tokens += tool_tokens
            else:
                # Can't fit any more tools
                break

        self.logger.debug(
            f"Fitted {len(fitted_tools)}/{len(tools)} tools in "
            f"{current_tokens}/{available_tokens} tokens"
        )
        return fitted_tools

    def manage_context_with_tools(
        self, messages: List[Dict], tools: Optional[List[Dict]] = None
    ) -> Optional[Dict[str, Any]]:
        """Comprehensive context management for messages and tools.

        This method ensures the entire request (messages + tools) fits within
        the model's context window, following both OpenAI API and MCP specifications.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tool definitions

        Returns:
            Managed payload dict with 'messages' and optionally 'tools', or None
            if impossible to fit
        """
        model = self.config.get("model", "gpt-3.5-turbo")
        max_context = (
            self.config.get_total_context_size()
            - self.config.get_response_buffer_size()
        )

        # Start with current messages and tools
        current_messages = messages.copy()
        current_tools = tools.copy() if tools else None

        # Calculate total tokens needed
        def calculate_total_tokens() -> int:
            msg_tokens = self.token_manager.count_tokens_for_messages(
                current_messages, model
            )
            tool_tokens = (
                self.token_manager.count_tokens_for_tools(current_tools, model)
                if current_tools
                else 0
            )
            total: int = msg_tokens + tool_tokens
            return total

        total_tokens = calculate_total_tokens()
        self.logger.debug(
            f"Initial request size: {total_tokens} tokens (max: {max_context})"
        )

        # If we fit, return as-is
        if total_tokens <= max_context:
            return {"messages": current_messages, "tools": current_tools}

        self.logger.warning(
            f"Request too large ({total_tokens} tokens), applying context management"
        )

        # Step 1: Use intelligent tool optimization
        if current_tools:
            # Use our existing intelligent tool optimization
            query_text = ""
            if messages:
                # Extract query from the last user message for
                # context-aware optimization
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        query_text = msg.get("content", "")
                        break

            available_tokens = self.token_manager.get_available_tool_tokens(
                self.token_manager.count_tokens_for_messages(current_messages, model)
            )
            current_tools = self.optimize_tools_for_context(
                current_tools, query_text, available_tokens
            )
            total_tokens = calculate_total_tokens()

            if total_tokens <= max_context:
                self.logger.info("Optimized tools to fit context")
                return {"messages": current_messages, "tools": current_tools}

        # Step 2: If still too large, try without tools entirely
        if total_tokens > max_context:
            current_tools = None
            total_tokens = calculate_total_tokens()

            if total_tokens <= max_context:
                self.logger.warning("Removed all tools to fit context limit")
                return {"messages": current_messages, "tools": None}

        # Step 3: Trim messages (import here to avoid circular imports)
        if total_tokens > max_context:
            self.logger.info("Trimming messages to fit context")
            # Calculate available space for messages (accounting for tools if any)
            tool_tokens = (
                self.token_manager.count_tokens_for_tools(current_tools, model)
                if current_tools
                else 0
            )
            available_for_messages = max_context - tool_tokens

            # Use token manager to trim messages
            # First, let's calculate how much we need to trim
            current_msg_tokens = self.token_manager.count_tokens_for_messages(
                current_messages, model
            )
            if current_msg_tokens > available_for_messages:
                # Simple message trimming: keep system message and recent messages
                trimmed_messages = []
                if current_messages and current_messages[0].get("role") == "system":
                    trimmed_messages.append(current_messages[0])

                # Add messages from the end until we reach the limit
                remaining_tokens = (
                    available_for_messages
                    - self.token_manager.count_tokens_for_messages(
                        trimmed_messages, model
                    )
                )

                for msg in reversed(
                    current_messages[1:] if trimmed_messages else current_messages
                ):
                    msg_tokens = self.token_manager.count_tokens_for_messages(
                        [msg], model
                    )
                    if msg_tokens <= remaining_tokens:
                        trimmed_messages.insert(
                            (
                                -1
                                if trimmed_messages
                                and trimmed_messages[0].get("role") == "system"
                                else 0
                            ),
                            msg,
                        )
                        remaining_tokens -= msg_tokens
                    else:
                        break

                current_messages = trimmed_messages

            total_tokens = calculate_total_tokens()

            if total_tokens <= max_context:
                final_msg_tokens = self.token_manager.count_tokens_for_messages(
                    current_messages, model
                )
                final_tool_tokens = (
                    self.token_manager.count_tokens_for_tools(current_tools, model)
                    if current_tools
                    else 0
                )
                self.logger.info(
                    f"Final context: {final_msg_tokens} message tokens + "
                    f"{final_tool_tokens} tool tokens = {total_tokens} total"
                )
                return {"messages": current_messages, "tools": current_tools}

        # Step 4: Last resort - minimal payload
        if total_tokens > max_context:
            self.logger.error("Cannot fit request even with aggressive trimming")
            # Try with just system message and latest user message, no tools
            minimal_messages = []
            if current_messages and current_messages[0].get("role") == "system":
                minimal_messages.append(current_messages[0])

            # Add the most recent user message
            for msg in reversed(current_messages):
                if msg.get("role") == "user":
                    minimal_messages.append(msg)
                    break

            minimal_tokens = self.token_manager.count_tokens_for_messages(
                minimal_messages, model
            )
            if minimal_tokens <= max_context:
                self.logger.warning(
                    "Using minimal payload: system + last user message only"
                )
                return {"messages": minimal_messages, "tools": None}

        # If we can't fit even the minimal payload, something is very wrong
        self.logger.error("Cannot fit even minimal request within context limits")
        return None
