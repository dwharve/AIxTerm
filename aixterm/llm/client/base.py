"""Core LLM client base functionality."""

import time
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

from ...context import TokenManager, ToolOptimizer
from ...utils import get_logger
from ..message_validator import MessageValidator
from ..tools import ToolHandler


class LLMClientBase:
    """Base class for LLM client with core initialization and configuration."""

    def __init__(
        self,
        config_manager: Any,
        mcp_client: Any,
        progress_callback_factory: Optional[Callable] = None,
        display_manager: Any = None,
    ):
        """Initialize LLM client.

        Args:
            config_manager: Configuration manager
            mcp_client: MCP client instance
            progress_callback_factory: Optional callback factory for progress updates
            display_manager: Optional display manager for UI updates
        """
        self.config = config_manager
        self.mcp_client = mcp_client
        self.display_manager = display_manager
        self.logger = get_logger(__name__)

        # Initialize tools handling
        self.progress_callback_factory = progress_callback_factory

        # Initialize OpenAI client
        api_url = self.config.get("api_url", "")
        api_key = self.config.get("api_key", "")

        # Handle OpenAI vs. compatible APIs
        extra_kwargs = {}
        if api_url and "openai.com" not in api_url.lower():
            # Non-OpenAI API endpoint, assume local API server
            # Remove any trailing endpoint paths to get just the base URL
            if api_url.endswith("/chat/completions"):
                api_url = api_url.replace("/chat/completions", "")

            # Use base URL for local servers
            extra_kwargs["base_url"] = api_url

            # For compatibility with local servers
            if not api_key:
                api_key = "dummy_key"

        self.openai_client = OpenAI(api_key=api_key, **extra_kwargs)

        # Initialize helpers
        self.token_manager = TokenManager(self.config, self.logger)
        self.tool_optimizer = ToolOptimizer(
            self.config, self.logger, self.token_manager
        )
        self.tool_handler = ToolHandler(self.config, self.mcp_client, self.logger)
        if self.display_manager:
            self.tool_handler.set_progress_display_manager(self.display_manager)
        self.message_validator = MessageValidator(self.config, self.logger)

        # Initialize timing tracking
        self._response_start_time: Optional[float] = None

    def _clear_progress_displays(self, context: str = "", force: bool = False) -> bool:
        """Clear any progress displays in the UI.

        Args:
            context: Context string to include in logs
            force: Whether to force clearing even when display manager is busy

        Returns:
            Whether displays were cleared
        """
        if not hasattr(self, "display_manager") or not self.display_manager:
            return False

        try:
            self.display_manager.clear_progress()
            return True
        except Exception as e:
            self.logger.debug(f"Could not clear progress displays {context}: {e}")
            return False

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

    def _record_response_start(self) -> None:
        """Record the start time of an API response for timing tracking."""
        self._response_start_time = time.time()

    def _record_response_complete(self) -> None:
        """Record the completion time and update adaptive timing."""
        if (
            hasattr(self, "_response_start_time")
            and self._response_start_time is not None
        ):
            response_time = time.time() - self._response_start_time

            # Update the adaptive timing in config
            try:
                self.config.update_response_timing(response_time)
            except Exception as e:
                self.logger.debug(f"Error updating response timing: {e}")

            self._response_start_time = None

    # Delegation methods for backward compatibility with tests
    def _validate_and_fix_role_alternation(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Delegate to message validator for backward compatibility."""
        return self.message_validator.validate_and_fix_role_alternation(messages)

    def shutdown(self) -> None:
        """Shutdown the LLM client and release resources."""
        self.logger.debug("Shutting down LLM client")

        # Close any active client sessions
        try:
            if hasattr(self, "openai_client") and self.openai_client:
                # Close any open connections
                if hasattr(self.openai_client, "close"):
                    self.openai_client.close()

            # If there are any running threads or resources, clean them up here

            # Notify handlers that we're shutting down
            for handler_name in dir(self):
                handler = getattr(self, handler_name)
                if hasattr(handler, "shutdown") and callable(
                    getattr(handler, "shutdown")
                ):
                    try:
                        handler.shutdown()
                    except Exception as e:
                        self.logger.error(
                            f"Error shutting down handler {handler_name}: {e}"
                        )

        except Exception as e:
            self.logger.error(f"Error during LLM client shutdown: {e}")

        self.logger.debug("LLM client shutdown complete")
