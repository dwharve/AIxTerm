"""Context handling for LLM client."""

from typing import Any, Dict, List, Optional


class ContextHandler:
    """Handles context preparation for LLM client."""

    def __init__(
        self,
        logger: Any,
        config_manager: Any,
        token_manager: Any,
        message_validator: Any,
    ):
        """Initialize context handler.

        Args:
            logger: Logger instance
            config_manager: Configuration manager
            token_manager: Token counting manager
            message_validator: Message validator
        """
        self.logger = logger
        self.config = config_manager
        self.token_manager = token_manager
        self.message_validator = message_validator

    def prepare_conversation_with_context(
        self,
        query: str,
        context: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        use_planning: bool = False,
    ) -> List[Dict[str, str]]:
        """Prepare conversation with user query and context.

        Args:
            query: User query
            context: Terminal context
            tools: Optional tools for the LLM
            use_planning: Whether to use planning-focused prompt

        Returns:
            List of message dictionaries for LLM API
        """
        if use_planning:
            base_system_prompt = self.config.get(
                "planning_system_prompt",
                "You are a strategic planning AI assistant. When given a task "
                "or problem, break it down into clear, actionable steps. Create "
                "detailed plans that consider dependencies, potential issues, and "
                "alternative approaches. Use tool calls to execute commands and "
                "perform actions. Always think through the complete workflow "
                "before starting and explain your reasoning.",
            )
        else:
            base_system_prompt = self.config.get(
                "system_prompt", "You are a terminal AI assistant."
            )

        # System prompt should NOT include tool descriptions - tools are provided
        # via API field. This follows OpenAI API and MCP specifications properly
        # and saves tokens. However, we can enhance with categories and tags.
        system_prompt = self._enhance_system_prompt_with_tool_info(
            base_system_prompt, tools
        )

        # Build initial messages
        messages = [{"role": "system", "content": system_prompt}]

        # Get conversation history using proper token counting
        try:
            # Import here to avoid circular imports
            from ...context import TerminalContext

            context_manager_terminal = TerminalContext(self.config)

            # Use proper token counting for space calculation
            model = self.config.get("model", "gpt-3.5-turbo")
            system_tokens = self.token_manager.estimate_tokens(system_prompt)
            query_context_tokens = self.token_manager.estimate_tokens(
                f"{query}\n\nContext:\n{context}\n----"
            )

            # Calculate available space for history (reserve some space for tools)
            available_context = self.config.get_available_context_size()
            tools_tokens = (
                self.token_manager.count_tokens_for_tools(tools, model) if tools else 0
            )
            used_tokens = system_tokens + query_context_tokens + tools_tokens

            # Reserve at least 200 tokens for conversation buffer, use conservative
            # limit for history
            available_for_history = max(
                0, min(500, (available_context - used_tokens - 200))
            )

            conversation_history = context_manager_terminal.get_conversation_history(
                available_for_history
            )
            self.logger.debug(
                f"Loaded {len(conversation_history)} history messages, "
                f"targeting {available_for_history} tokens"
            )

            # Ensure conversation history has proper role alternation
            conversation_history = (
                self.message_validator.fix_conversation_history_roles(
                    conversation_history
                )
            )
            messages.extend(conversation_history)

        except Exception as e:
            self.logger.warning(f"Could not get conversation history: {e}")

        # Add current query with context and enriched stats
        enriched_context = context
        try:
            # Attach terminal context stats to help the model answer meta-context questions
            stats = context_manager_terminal.get_context_stats()  # type: ignore[name-defined]
            # Prefer session-level metrics for commands and token usage
            session_ctx = None
            try:
                session_ctx = context_manager_terminal.log_processor.get_session_context(
                    token_budget=self.config.get_available_context_size(),
                    model_name=self.config.get("model", ""),
                )
            except Exception:
                session_ctx = None

            if isinstance(stats, dict):
                parts = []
                # Conversation history (messages) count
                history_count = stats.get("history_count")
                # Session metrics
                command_count = (
                    session_ctx.get("command_count") if isinstance(session_ctx, dict) else None
                )
                error_count = (
                    session_ctx.get("error_count") if isinstance(session_ctx, dict) else None
                )
                session_tokens = (
                    session_ctx.get("tokens") if isinstance(session_ctx, dict) else None
                )
                last_updated = stats.get("last_updated")
                if command_count is not None:
                    parts.append(f"command_count: {command_count}")
                if error_count is not None:
                    parts.append(f"error_count: {error_count}")
                if history_count is not None:
                    parts.append(f"message_history_count: {history_count}")
                # Prefer session tokens over raw token_count for clarity
                if session_tokens is not None:
                    parts.append(f"tokens: {session_tokens}")
                else:
                    token_count = stats.get("token_count")
                    if token_count is not None:
                        parts.append(f"tokens: {token_count}")
                if last_updated:
                    parts.append(f"last_updated: {last_updated}")
                # Include log file path when available
                log_info = stats.get("log_info") or {}
                if isinstance(log_info, dict) and log_info.get("log_file"):
                    parts.append(f"log_file: {log_info.get('log_file')}")
                if parts:
                    stats_text = "\n".join(parts)
                    enriched_context = (
                        f"{context}\n\nContext Stats:\n{stats_text}" if context else f"Context Stats:\n{stats_text}"
                    )
        except Exception:
            # Non-fatal; proceed without stats
            enriched_context = context

        messages.append(
            {
                "role": "user",
                "content": f"{query}\n\nContext:\n{enriched_context}\n----",
            }
        )

        return messages

    def _enhance_system_prompt_with_tool_info(
        self, base_prompt: str, tools: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Enhance system prompt with dynamically generated tool categories and tags.

        Args:
            base_prompt: Base system prompt
            tools: Available tools to analyze

        Returns:
            Enhanced system prompt with tool information
        """
        if not tools:
            return base_prompt

        try:
            # Extract categories and tags from available tools
            categories = set()
            tags = set()

            for tool in tools:
                function = tool.get("function", {})

                # Try to extract category from tool metadata if available
                if "category" in function:
                    categories.add(function["category"])

                # Try to extract tags from tool metadata if available
                if "tags" in function:
                    tool_tags = function["tags"]
                    if isinstance(tool_tags, list):
                        tags.update(tool_tags)
                    elif isinstance(tool_tags, str):
                        tags.add(tool_tags)

                # Infer categories and tags from tool names and descriptions
                name = function.get("name", "").lower()
                description = function.get("description", "").lower()

                # Infer categories from names
                if any(
                    keyword in name
                    for keyword in ["execute", "command", "run", "shell"]
                ):
                    categories.add("system")
                elif any(
                    keyword in name
                    for keyword in ["file", "read", "write", "find", "search"]
                ):
                    categories.add("filesystem")
                elif any(
                    keyword in name for keyword in ["web", "http", "search", "download"]
                ):
                    categories.add("network")
                elif any(
                    keyword in name for keyword in ["git", "build", "test", "deploy"]
                ):
                    categories.add("development")
                elif any(keyword in name for keyword in ["tool", "describe", "list"]):
                    categories.add("introspection")

                # Infer tags from names and descriptions
                common_tags = [
                    "file",
                    "command",
                    "search",
                    "web",
                    "git",
                    "build",
                    "test",
                    "read",
                    "write",
                    "execute",
                    "download",
                    "upload",
                    "process",
                    "analyze",
                    "convert",
                    "format",
                    "backup",
                    "security",
                ]

                for tag in common_tags:
                    if tag in name or tag in description:
                        tags.add(tag)

            # Format the enhanced prompt
            if categories or tags:
                tool_info = "\n\nAvailable tool capabilities:"

                if categories:
                    sorted_categories = sorted(categories)
                    tool_info += f"\nCategories: {', '.join(sorted_categories)}"

                if tags:
                    # Limit tags to most relevant ones to avoid bloating prompt
                    sorted_tags = sorted(tags)[:15]  # Limit to 15 most common tags
                    tool_info += f"\nCommon operations: {', '.join(sorted_tags)}"

                tool_info += (
                    "\n\nUse search_tools to find specific tools for tasks, "
                    "or describe_tool for detailed information about any tool."
                )

                return base_prompt + tool_info

        except Exception as e:
            self.logger.debug(f"Error enhancing system prompt with tool info: {e}")

        return base_prompt
