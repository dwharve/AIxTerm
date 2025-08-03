"""Core application logic for AIxTerm."""

import signal
import sys
from pathlib import Path
from typing import Any, Callable, List, Optional

from aixterm.cleanup import CleanupManager
from aixterm.config import AIxTermConfig
from aixterm.context import TerminalContext
from aixterm.display import create_display_manager
from aixterm.llm import LLMClient, LLMError
from aixterm.mcp_client import MCPClient
from aixterm.utils import get_logger


class AIxTermApp:
    """Main AIxTerm application class."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize AIxTerm application.

        Args:
            config_path: Custom configuration file path
        """
        self.config = AIxTermConfig(Path(config_path) if config_path else None)
        self.logger = get_logger(__name__)

        # Initialize display manager
        progress_type = self.config.get("progress_display_type", "bar")
        self.display_manager = create_display_manager(progress_type)

        # Initialize components
        self.context_manager = TerminalContext(self.config)
        self.mcp_client = MCPClient(self.config)
        self.llm_client = LLMClient(
            self.config,
            self.mcp_client,
            self._create_progress_callback_factory(),
            self.display_manager,
        )
        self.cleanup_manager = CleanupManager(self.config)

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, _frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down gracefully")
        self.shutdown()
        sys.exit(0)

    def run(
        self,
        query: str,
        context: Optional[List[str]] = None,
        show_thinking: bool = True,
        no_prompt: bool = False,
        use_planning: bool = False,
        files: Optional[List[str]] = None,
    ) -> None:
        """Run AIxTerm with the given query.

        Args:
            query: Query text
            context: Optional context lines

            show_thinking: Whether to show thinking content
            no_prompt: Whether to suppress prompt collection
            use_planning: Whether to use planning mode
            files: Optional list of file paths to include in context
        """
        self.logger.info(f"Processing query: {query}")

        # Initialize MCP client if servers are configured
        if self.config.get("mcp_servers", []):
            self.mcp_client.initialize()

        # Check if cleanup should be run and run it if needed
        if self.cleanup_manager.should_run_cleanup():
            self.cleanup_manager.run_cleanup()

        # Update context with current environment and files
        self.context_manager.update_context(query, force_collect=not no_prompt)

        # Add file context if provided
        if files:
            for file_path in files:
                try:
                    with open(file_path, "r") as f:
                        file_content = f.read()
                        self.context_manager.add_file_context(file_path, file_content)
                except Exception as e:
                    self.logger.error(f"Error reading file {file_path}: {e}")
                    continue

        try:
            # Process query with LLM
            if use_planning:
                # Add planning mode instructions to the query
                planning_prompt = (
                    "Please create a detailed plan for addressing this request. "
                    "Structure your response with clear sections including:\n"
                    "1. Problem Analysis: Break down the request\n"
                    "2. Approach: Outline the overall strategy\n"
                    "3. Step-by-Step Plan: List specific actions to take\n"
                    "4. Potential Challenges: Identify possible issues\n"
                    "5. Success Criteria: Define what completion looks like\n\n"
                    "REQUEST: "
                ) + query

                self.logger.info("Using planning mode")
                response = self.llm_client.process_query(
                    query=planning_prompt,
                    context_lines=context,
                    show_thinking=show_thinking,
                )
            else:
                response = self.llm_client.process_query(
                    query=query,
                    context_lines=context,
                    show_thinking=show_thinking,
                )
            self._handle_response(response, query)
        except LLMError as e:
            self.logger.error(f"LLM error: {e}")
            self.display_manager.show_error(f"Error: {e}")

    def _handle_response(self, response: Any, original_query: str) -> None:
        """Handle the response from the LLM.

        Args:
            response: Response text or response object
            original_query: Original query text
        """
        # Handle empty responses
        if isinstance(response, dict) and not response.get("content"):
            self.logger.warning("No response received from AI.")
            return
        if not response:
            self.logger.warning("No response received from AI.")
            return
        # Only check strip() for string responses
        if isinstance(response, str) and not response.strip():
            self.logger.warning("No response received from AI.")
            return

        # Display and store the response
        self.display_manager.show_response(response)

        # Store the interaction
        self.context_manager.store_interaction(
            query=original_query,
            response=response,
        )

    def _create_progress_callback_factory(self) -> Callable[[str, str], Callable]:
        """Create a factory for progress callbacks.

        Returns:
            A factory function that creates progress callbacks
        """

        def factory(progress_token: str, title: str) -> Callable:
            """Create a progress callback.

            Args:
                progress_token: Progress token
                title: Progress title

            Returns:
                A progress callback function
            """
            # Create progress display
            progress = self.display_manager.create_progress(
                title=title or "Processing",
            )
            progress.start()

            def progress_callback(params: Any) -> None:
                """Update progress based on parameters.

                Args:
                    params: Progress parameters
                """
                if params and isinstance(params, dict):
                    # Update progress based on parameters
                    if "completed" in params:
                        progress.stop()
                    elif "message" in params:
                        progress.update(status=params["message"])
                    elif "percent" in params:
                        progress.update(percent=params["percent"])
                    else:
                        progress.update()
                else:
                    # Simple update
                    progress.update()

            return progress_callback

        return factory

    def shutdown(self) -> None:
        """Shut down the application and clean up resources."""
        self.logger.info("Shutting down AIxTerm")

        # Shutdown components in reverse initialization order
        if hasattr(self, "cleanup_manager"):
            self.cleanup_manager.shutdown()

        if hasattr(self, "llm_client"):
            self.llm_client.shutdown()

        if hasattr(self, "mcp_client"):
            self.mcp_client.shutdown()

        if hasattr(self, "context_manager"):
            self.context_manager.shutdown()

        self.logger.info("AIxTerm shutdown complete")
