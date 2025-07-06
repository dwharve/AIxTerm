"""Main terminal context management class."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils import get_logger
from .directory_handler import DirectoryHandler
from .log_processor import LogProcessor
from .token_manager import TokenManager
from .tool_optimizer import ToolOptimizer


class TerminalContext:
    """Manages terminal context and log file operations."""

    def __init__(self, config_manager: Any) -> None:
        """Initialize terminal context manager.

        Args:
            config_manager: AIxTermConfig instance
        """
        self.config = config_manager
        self.logger = get_logger(__name__)

        # Initialize component handlers
        self.token_manager = TokenManager(config_manager, self.logger)
        self.directory_handler = DirectoryHandler(
            config_manager, self.logger, self.token_manager
        )
        self.log_processor = LogProcessor(config_manager, self.logger)
        self.tool_optimizer = ToolOptimizer(
            config_manager, self.logger, self.token_manager
        )

    def get_terminal_context(
        self, include_files: bool = True, smart_summarize: bool = True
    ) -> str:
        """Retrieve intelligent terminal context with optional summarization.

        Args:
            include_files: Whether to include file listings for context
            smart_summarize: Whether to apply intelligent summarization

        Returns:
            Formatted terminal context string
        """
        max_tokens = self.config.get_available_context_size()
        context_parts = []

        # Get current working directory info
        cwd = os.getcwd()
        context_parts.append(f"Current working directory: {cwd}")

        # Add intelligent directory context if enabled
        if include_files:
            dir_context = self.directory_handler.get_directory_context()
            if dir_context:
                context_parts.append(dir_context)

        try:
            log_path = self.log_processor.find_log_file()
            if log_path and log_path.exists():
                log_content = self.log_processor.read_and_process_log(
                    log_path,
                    max_tokens,
                    self.config.get("model", ""),
                    smart_summarize,
                )
                if log_content:
                    context_parts.append(f"Recent terminal output:\n{log_content}")
            else:
                context_parts.append("No recent terminal history available.")
        except Exception as e:
            self.logger.error(f"Error retrieving session log: {e}")
            context_parts.append(f"Error retrieving session log: {e}")

        return "\n\n".join(context_parts)

    def get_file_contexts(
        self,
        file_paths: List[str],
        max_file_tokens: int = 1000,
        max_total_tokens: int = 3000,
    ) -> str:
        """Get content from multiple files to use as context.

        Args:
            file_paths: List of file paths to read
            max_file_tokens: Maximum tokens per individual file
            max_total_tokens: Maximum total tokens for all file content

        Returns:
            Formatted string containing file contents
        """
        return self.directory_handler.get_file_contexts(
            file_paths, max_file_tokens, max_total_tokens
        )

    def get_optimized_context(
        self, file_contexts: Optional[List[str]] = None, query: str = ""
    ) -> str:
        """Get optimized context that efficiently uses the available context window.

        Args:
            file_contexts: List of file paths to include
            query: The user query to optimize context for

        Returns:
            Optimized context string that maximizes useful information
        """
        # Get configuration for context budget using new helper methods
        available_context = self.config.get_available_context_size()

        # Reserve space for essential parts
        system_prompt_tokens = 50  # Estimated
        query_tokens = self.token_manager.estimate_tokens(query)
        available_for_context = available_context - system_prompt_tokens - query_tokens

        # Allocate context budget intelligently
        context_parts = []
        remaining_tokens = available_for_context

        # 1. Always include current directory (small, essential)
        cwd = os.getcwd()
        cwd_info = f"Current working directory: {cwd}"
        context_parts.append(cwd_info)
        remaining_tokens -= self.token_manager.estimate_tokens(cwd_info)

        # 2. Directory context (project info, file structure) - 10-15% of budget
        dir_budget = min(int(available_for_context * 0.15), remaining_tokens)
        if dir_budget > 50:
            dir_context = self.directory_handler.get_directory_context()
            if dir_context:
                dir_context = self.token_manager.apply_token_limit(
                    dir_context, dir_budget, self.config.get("model", "")
                )
                context_parts.append(dir_context)
                remaining_tokens -= self.token_manager.estimate_tokens(dir_context)

        # 3. File contexts if provided - 40-60% of budget (prioritized)
        if file_contexts and remaining_tokens > 100:
            file_budget = min(int(available_for_context * 0.6), remaining_tokens)
            # Use token-aware file context method directly
            max_file_tokens = min(
                1500, file_budget // max(1, len(file_contexts))
            )  # Distribute per file
            file_content = self.directory_handler.get_file_contexts(
                file_contexts, max_file_tokens, file_budget
            )
            if file_content:
                context_parts.append(file_content)
                remaining_tokens -= self.token_manager.estimate_tokens(file_content)

        # 4. Terminal history - remaining budget (but at least 25% if no files)
        if remaining_tokens > 50:
            if not file_contexts:
                # If no files, give more space to terminal history
                terminal_budget = max(
                    remaining_tokens, int(available_for_context * 0.4)
                )
            else:
                terminal_budget = remaining_tokens

            try:
                log_path = self.log_processor.find_log_file()
                if log_path and log_path.exists():
                    # Use intelligent summarization for consistency
                    log_content = self.log_processor.read_and_process_log(
                        log_path,
                        terminal_budget,
                        self.config.get("model", ""),
                        smart_summarize=True,
                    )
                    if log_content and log_content.strip():
                        context_parts.append(
                            f"Recent terminal activity:\n{log_content}"
                        )
                    else:
                        context_parts.append("No recent terminal activity available.")
                else:
                    context_parts.append("No recent terminal activity available.")
            except Exception as e:
                self.logger.error(f"Error retrieving session log: {e}")
                context_parts.append(f"Error retrieving session log: {e}")

        final_context = "\n\n".join(context_parts)

        # Final safety check - ensure we're within budget
        final_tokens = self.token_manager.estimate_tokens(final_context)
        if final_tokens > available_for_context:
            self.logger.warning(
                f"Context too large ({final_tokens} tokens), "
                f"truncating to {available_for_context}"
            )
            final_context = self.token_manager.apply_token_limit(
                final_context,
                available_for_context,
                self.config.get("model", ""),
            )

        return final_context

    def get_conversation_history(
        self, max_tokens: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """Get structured conversation history from terminal logs.

        Args:
            max_tokens: Maximum tokens to use for conversation history

        Returns:
            List of conversation messages formatted for LLM consumption
        """
        if max_tokens is None:
            max_tokens = (
                self.config.get_available_context_size() // 3
            )  # Use 1/3 of available context

        try:
            log_path = self.log_processor.find_log_file()
            if not log_path or not log_path.exists():
                return []

            # Read the recent log content
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                # Get the last portion of the log file
                f.seek(0, 2)  # Seek to end
                file_size = f.tell()

                # Read last 50KB or whole file if smaller
                read_size = min(file_size, 50000)
                f.seek(file_size - read_size)
                log_content = f.read()

            # Parse into conversation messages
            messages = self.log_processor.parse_conversation_history(log_content)

            # Filter and limit messages to fit in token budget
            filtered_messages: List[Dict[str, str]] = []
            total_tokens = 0

            # Work backwards from most recent messages
            for message in reversed(messages):
                message_tokens = self.token_manager.estimate_tokens(message["content"])
                if total_tokens + message_tokens <= max_tokens:
                    filtered_messages.insert(0, message)
                    total_tokens += message_tokens
                else:
                    break

            return filtered_messages

        except Exception as e:
            self.logger.error(f"Error getting conversation history: {e}")
            return []

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
        return self.tool_optimizer.optimize_tools_for_context(
            tools, query, available_tokens
        )

    def get_available_tool_tokens(self, context_tokens: int) -> int:
        """Calculate how many tokens are available for tool definitions.

        Args:
            context_tokens: Tokens already used by context

        Returns:
            Number of tokens available for tools
        """
        return self.token_manager.get_available_tool_tokens(context_tokens)

    def get_log_files(self) -> List[Path]:
        """Get list of all bash AI log files.

        Returns:
            List of log file paths
        """
        return self.log_processor.get_log_files()

    def create_log_entry(self, command: str, result: str = "") -> None:
        """Create a log entry for a command (fallback method).

        Note: This is a fallback when shell integration is not available.
        The primary log creation is handled by shell integration (bash, zsh, fish)
        which provides automatic command capture and richer logging.

        Args:
            command: Command that was executed
            result: Result or output of the command
        """
        self.log_processor.create_log_entry(command, result)

    def clear_session_context(self) -> bool:
        """Clear the context for the active terminal session.

        Returns:
            True if context was cleared, False if no context was found
        """
        return self.log_processor.clear_session_context()
