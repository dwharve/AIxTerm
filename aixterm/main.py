"""Main application logic for AIxTerm."""

import signal
import sys
from pathlib import Path
from typing import Any, Callable, List, Optional

from .cleanup import CleanupManager
from .config import AIxTermConfig
from .context import TerminalContext
from .llm import LLMClient, LLMError
from .mcp_client import MCPClient
from .progress_display import create_progress_display
from .utils import get_logger


class AIxTerm:
    """Main AIxTerm application class."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize AIxTerm application.

        Args:
            config_path: Custom configuration file path
        """
        self.config = AIxTermConfig(Path(config_path) if config_path else None)
        self.logger = get_logger(__name__)

        # Initialize progress display
        progress_type = self.config.get("progress_display_type", "bar")
        self.progress_display = create_progress_display(progress_type)

        # Initialize components
        self.context_manager = TerminalContext(self.config)
        self.mcp_client = MCPClient(self.config)
        self.llm_client = LLMClient(
            self.config,
            self.mcp_client,
            self._create_progress_callback_factory(),
            self.progress_display,
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
        file_contexts: Optional[List[str]] = None,
        use_planning: bool = False,
    ) -> None:
        """Run AIxTerm with a user query and optional file contexts.

        Args:
            query: User's question or request
            file_contexts: List of file paths to include as context
            use_planning: Whether to use planning-focused prompt
        """
        try:
            # Initialize MCP client if needed
            if self.config.get_mcp_servers():
                self.mcp_client.initialize()

            # Run cleanup if needed
            if self.cleanup_manager.should_run_cleanup():
                cleanup_results = self.cleanup_manager.run_cleanup()
                if cleanup_results.get("log_files_removed", 0) > 0:
                    self.logger.info(
                        f"Cleanup removed "
                        f"{cleanup_results['log_files_removed']} old log files"
                    )

            # Get optimized context that efficiently uses the context window
            context = self.context_manager.get_optimized_context(file_contexts, query)

            # Get available tools from MCP servers with intelligent management
            tools = None
            if self.config.get_mcp_servers():
                # Show progress for tool discovery
                tool_progress = self.progress_display.create_progress(
                    progress_token="tool_discovery",
                    title="Discovering available tools",
                    total=None,
                    show_immediately=True,
                )

                try:
                    all_tools = self.mcp_client.get_available_tools(brief=True)
                    if all_tools:
                        tool_progress.update(len(all_tools), "Analyzing tool relevance")

                        # Calculate tokens used by context
                        import tiktoken

                        encoding = tiktoken.encoding_for_model("gpt-4")
                        context_tokens = len(encoding.encode(context))

                        # Get available tokens for tools
                        available_tool_tokens = (
                            self.context_manager.get_available_tool_tokens(
                                context_tokens
                            )
                        )

                        # Use context manager for intelligent tool optimization
                        tools = self.context_manager.optimize_tools_for_context(
                            all_tools, query, available_tool_tokens
                        )

                        tool_progress.complete(
                            f"Selected {len(tools)}/{len(all_tools)} relevant tools"
                        )

                        self.logger.info(
                            f"Optimized tools: {len(tools)}/{len(all_tools)} tools "
                            f"selected for context"
                        )
                    else:
                        tools = []
                        tool_progress.complete("No tools available")
                except Exception as e:
                    self.logger.error(f"Failed to get MCP tools: {e}")
                    tool_progress.complete("Tool discovery failed")
                    tools = None

            # Show progress for LLM processing
            llm_progress = self.progress_display.create_progress(
                progress_token="llm_processing",
                title="Processing with AI",
                total=None,
                show_immediately=False,
            )

            try:
                # Send query to LLM with normal streaming
                response = self.llm_client.ask_with_context(
                    query, context, tools, use_planning=use_planning
                )

                # Only complete progress if it was actually shown
                if llm_progress.is_visible:
                    llm_progress.complete("AI processing completed")
            except Exception:
                # Only complete progress if it was actually shown
                if llm_progress.is_visible:
                    llm_progress.complete("AI processing failed")
                raise

            if not response.strip():
                print("No response received from AI.")
                return

            # Extract and potentially execute commands
            self._handle_response(response, query)

        except LLMError as e:
            self.logger.error(f"LLM error: {e}")
            # Provide user-friendly error message
            error_msg = str(e)
            if "Connection refused" in error_msg:
                print("Error: Cannot connect to the AI service.")
                print("Please check that your LLM server is running and accessible.")
                print(
                    f"Current API URL: {self.config.get('api_url', 'Not configured')}"
                )
            elif "timeout" in error_msg.lower():
                print("Error: AI service is not responding (timeout).")
                print("The request took too long. Try again or check your connection.")
            elif (
                "401" in error_msg
                or "403" in error_msg
                or "unauthorized" in error_msg.lower()
            ):
                print("Error: Authentication failed.")
                print("Please check your API key configuration.")
            elif "404" in error_msg:
                print("Error: AI service endpoint not found.")
                print("Please verify your API URL configuration.")
            else:
                print(f"Error communicating with AI: {error_msg}")
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            self.shutdown()
            sys.exit(0)
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            print(f"Unexpected error: {e}")
            sys.exit(1)

    def _handle_response(self, response: str, original_query: str) -> None:
        """Handle LLM response and log the interaction.

        Args:
            response: LLM response text
            original_query: Original user query
        """
        # Log the interaction for context
        self.context_manager.create_log_entry(f"ai '{original_query}'", response)

    def _create_progress_callback_factory(self) -> Callable[[str, str], Callable]:
        """Create a progress callback factory for MCP tool calls.

        Returns:
            A factory function that creates progress callbacks
        """

        def factory(progress_token: str, title: str) -> Callable:
            """Factory function to create progress callbacks.

            Args:
                progress_token: Progress token for this operation
                title: Title to display for the progress

            Returns:
                Progress callback function
            """
            # Create progress display
            progress_display = self.progress_display.create_progress(
                progress_token=progress_token,
                title=title,
                total=None,
                show_immediately=True,
            )

            def progress_callback(params: Any) -> None:
                """Handle progress updates from MCP tools."""
                try:
                    from .mcp_client import ProgressParams

                    if isinstance(params, ProgressParams):
                        # Check if this is a completion signal (progress = 100)
                        if params.progress >= 100:
                            # Complete the progress display to clear it
                            progress_display.complete("")
                        else:
                            # Regular progress update
                            progress_display.update(
                                progress=params.progress,
                                message=params.message,
                                total=params.total,
                            )
                    else:
                        # Handle raw parameters
                        progress = getattr(params, "progress", 0)
                        if progress >= 100:
                            # Complete the progress display to clear it
                            progress_display.complete("")
                        else:
                            progress_display.update(
                                progress=progress,
                                message=getattr(params, "message", None),
                                total=getattr(params, "total", None),
                            )
                except Exception as e:
                    # If there's any error, try to complete the display to clear it
                    try:
                        progress_display.complete("")
                    except Exception:
                        pass
                    self.logger.debug(f"Error updating progress display: {e}")

            return progress_callback

        return factory

    def list_tools(self) -> None:
        """List available MCP tools."""
        if not self.config.get_mcp_servers():
            print("No MCP servers configured.")
            return

        self.mcp_client.initialize()
        tools = self.mcp_client.get_available_tools()

        if not tools:
            print("No tools available from MCP servers.")
            return

        print("\nAvailable MCP Tools:")
        print("=" * 50)

        current_server = None
        for tool in tools:
            server_name = tool.get("server", "unknown")
            if server_name != current_server:
                print(f"\nServer: {server_name}")
                print("-" * 30)
                current_server = server_name

            function = tool.get("function", {})
            name = function.get("name", "unknown")
            description = function.get("description", "No description")

            print(f"  {name}: {description}")

    def status(self) -> None:
        """Show AIxTerm status information."""
        print("AIxTerm Status")
        print("=" * 50)

        # Configuration info
        print(f"Model: {self.config.get('model')}")
        print(f"API URL: {self.config.get('api_url')}")
        print(f"Context Size: {self.config.get_total_context_size()}")
        print(f"Response Buffer: {self.config.get_response_buffer_size()}")
        print(f"Available for Context: {self.config.get_available_context_size()}")

        # MCP servers
        mcp_servers = self.config.get_mcp_servers()
        print(f"\nMCP Servers: {len(mcp_servers)}")
        if mcp_servers:
            self.mcp_client.initialize()
            server_status = self.mcp_client.get_server_status()
            for server_name, status in server_status.items():
                status_text = "Running" if status["running"] else "Stopped"
                tool_count = status["tool_count"]
                print(f"  {server_name}: {status_text} ({tool_count} tools)")

        # Cleanup status
        print("\nCleanup Status:")
        cleanup_status = self.cleanup_manager.get_cleanup_status()
        print(f"  Enabled: {cleanup_status['cleanup_enabled']}")
        print(
            f"  Log Files: {cleanup_status['log_files_count']} "
            f"({cleanup_status['total_log_size']})"
        )
        print(f"  Last Cleanup: {cleanup_status['last_cleanup'] or 'Never'}")
        print(f"  Next Cleanup: {cleanup_status['next_cleanup_due'] or 'Disabled'}")

    def cleanup_now(self) -> None:
        """Force immediate cleanup."""
        print("Running cleanup...")
        results = self.cleanup_manager.force_cleanup_now()

        print("Cleanup completed:")
        print(f"  Log files removed: {results.get('log_files_removed', 0)}")
        print(f"  Log files cleaned: {results.get('log_files_cleaned', 0)}")
        print(f"  Temp files removed: {results.get('temp_files_removed', 0)}")
        print(f"  Space freed: {results.get('bytes_freed', 0)} bytes")

        if results.get("errors"):
            print(f"  Errors: {len(results['errors'])}")
            for error in results["errors"][:3]:  # Show first 3 errors
                print(f"    {error}")

    def clear_context(self) -> None:
        """Clear context for the active session."""
        print("Clearing context for active session...")
        try:
            # Clear the session log file for the current TTY
            cleared = self.context_manager.clear_session_context()
            if cleared:
                print("✓ Session context cleared successfully")
                print(
                    "  The conversation history for this terminal session "
                    "has been removed"
                )
            else:
                print("ℹ No active session context found to clear")
                print("  This may be a new session or context was already empty"[:85])
        except Exception as e:
            self.logger.error(f"Error clearing context: {e}")
            print(f"✗ Failed to clear context: {e}")

    def shutdown(self) -> None:
        """Shutdown AIxTerm gracefully."""
        self.logger.info("Shutting down AIxTerm")
        try:
            # Clean up progress displays
            self.progress_display.cleanup_all()

            # Shutdown MCP client
            self.mcp_client.shutdown()
        except Exception as e:
            self.logger.error(f"Error shutting down MCP client: {e}")

    def init_config(self, force: bool = False) -> None:
        """Initialize default configuration file.

        Args:
            force: Whether to overwrite existing config file
        """
        config_path = self.config.config_path

        if config_path.exists() and not force:
            print(f"Configuration file already exists at: {config_path}")
            print(
                "Use --init-config --force to overwrite the existing " "configuration."
            )
            return

        success = self.config.create_default_config(overwrite=force)

        if success:
            print(f"Default configuration created at: {config_path}")
            print("\nYou can now edit this file to customize your AIxTerm settings.")
            print("Key settings to configure:")
            print("  - api_url: URL of your LLM API endpoint")
            print("  - api_key: API key for authentication (if required)")
            print("  - model: Model name to use")
            print("  - mcp_servers: MCP servers for additional tools")
        else:
            print("Failed to create configuration file.")

    def run_cli_mode(
        self,
        query: str,
        file_contexts: Optional[List[str]] = None,
        use_planning: bool = False,
    ) -> None:
        """Run AIxTerm in CLI mode with automatic MCP server lifecycle management.

        Args:
            query: User's question or request
            file_contexts: List of file paths to include as context
            use_planning: Whether to use planning-focused prompt
        """
        try:
            # Initialize MCP client (starts servers)
            if self.config.get_mcp_servers():
                self.mcp_client.initialize()

            # Run the normal query processing
            self.run(query, file_contexts, use_planning)

        finally:
            # Always clean up MCP servers
            if self.config.get_mcp_servers():
                self.mcp_client.shutdown()

    def install_shell_integration(self, shell: str = "bash") -> None:
        """Install shell integration for automatic terminal session logging.

        Args:
            shell: Target shell type (bash, zsh, fish)
        """
        from typing import Dict, Type, Union

        from .integration import Bash, Fish, Zsh

        print("Installing AIxTerm shell integration...")

        # Get the appropriate integration class
        integration_classes: Dict[str, Type[Union[Bash, Zsh, Fish]]] = {
            "bash": Bash,
            "zsh": Zsh,
            "fish": Fish,
        }

        if shell not in integration_classes:
            print(f"Error: Unsupported shell: {shell}")
            print(f"Supported shells: {', '.join(integration_classes.keys())}")
            return

        integration_class = integration_classes[shell]
        integration = integration_class()

        # Check if shell is available
        if not integration.is_available():
            print(f"Error: {shell} is not available on this system")
            return

        # Validate environment
        if not integration.validate_integration_environment():
            print(f"Error: Environment validation failed for {shell}")
            print("Please check:")
            print("- TTY access is available")
            print("- Home directory is writable")
            return

        # Install the integration
        if integration.install():
            print(f" Shell integration for {shell} installed successfully!")
            print(f" Configuration file: {integration.get_selected_config_file()}")

            # Show installation notes
            notes = integration.get_installation_notes()
            if notes:
                print("\n Installation notes:")
                for note in notes:
                    print(f"  • {note}")

            print(f"\n To activate: source {integration.get_selected_config_file()}")
            print("   Or start a new terminal session")
            print("")
            print(" Usage:")
            print('  ai "your question"     # AI command with automatic logging')
            print("  # All terminal commands will be logged for context")
            print("")
            print(" Log files will be created at:")
            print("  ~/.aixterm_log.*         # Session-specific log files")
        else:
            print(f"Error: Failed to install {shell} integration")

            # Show troubleshooting tips
            tips = integration.get_troubleshooting_tips()
            if tips:
                print("\n Troubleshooting tips:")
                for tip in tips:
                    print(f"  • {tip}")

    def uninstall_shell_integration(self, shell: str = "bash") -> None:
        """Uninstall shell integration.

        Args:
            shell: Target shell type (bash, zsh, fish)
        """
        from typing import Dict, Type, Union

        from .integration import Bash, Fish, Zsh

        print("  Uninstalling AIxTerm shell integration...")

        # Get the appropriate integration class
        integration_classes: Dict[str, Type[Union[Bash, Zsh, Fish]]] = {
            "bash": Bash,
            "zsh": Zsh,
            "fish": Fish,
        }

        if shell not in integration_classes:
            print(f"Error: Unsupported shell: {shell}")
            print(f"Supported shells: {', '.join(integration_classes.keys())}")
            return

        integration_class = integration_classes[shell]
        integration = integration_class()

        # Check if shell is available
        if not integration.is_available():
            print(f"Warning: {shell} is not available on this system")
            print("Attempting to uninstall anyway...")

        # Uninstall the integration
        if integration.uninstall():
            print(f" Shell integration for {shell} uninstalled successfully!")

            # Show any additional cleanup notes
            config_files = integration.config_files
            print(f" Cleaned integration from config files: {', '.join(config_files)}")

            print("\n You may need to:")
            print("  • Restart your terminal or run 'source ~/.{shell}rc'")
            print("  • Remove any remaining ~/.aixterm_log.* files if desired")
        else:
            print(f"Error: Failed to uninstall {shell} integration")

            # Show troubleshooting tips
            tips = integration.get_troubleshooting_tips()
            if tips:
                print("\n Troubleshooting tips:")
                for tip in tips:
                    print(f"  • {tip}")


def main() -> None:
    """Main entry point for the AIxTerm CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="AIxTerm - AI-powered command line assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ai 'how do I list all running processes?'
  ai --plan 'create a backup system for my database'
  ai --file config.py --file main.py 'how can I improve this code?'
  ai --api_url http://127.0.0.1:8080/v1/chat/completions 'help with docker'
  ai --log-level DEBUG 'analyze this error'  # Enable debug logging
  ai -c                               # Clear session context
  ai --clear                          # Clear session context
  ai --server                         # Run in server mode
  ai --init-config                    # Create default config
  ai --init-config --force            # Overwrite existing config
  ai --install-shell                   # Install automatic terminal logging
  ai --uninstall-shell                 # Remove automatic terminal logging
""",
    )

    # Special commands
    parser.add_argument("--status", action="store_true", help="Show AIxTerm status")
    parser.add_argument("--tools", action="store_true", help="List available MCP tools")
    parser.add_argument("--cleanup", action="store_true", help="Force cleanup now")
    parser.add_argument(
        "-c",
        "--clear",
        action="store_true",
        help="Clear context for the active session",
    )
    parser.add_argument("--server", action="store_true", help="Run in server mode")
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="Create default configuration file",
    )
    parser.add_argument(
        "--install-shell",
        action="store_true",
        help="Install shell integration for automatic terminal logging",
    )
    parser.add_argument(
        "--uninstall-shell",
        action="store_true",
        help="Uninstall shell integration",
    )
    parser.add_argument(
        "--shell",
        default="bash",
        choices=["bash", "zsh", "fish"],
        help="Target shell for integration (default: bash)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite when used with --init-config",
    )

    # Configuration overrides
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--api_url", help="Override API URL")
    parser.add_argument("--api_key", help="Override API key")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="WARNING",
        help="Set logging level (default: WARNING)",
    )

    # Planning flag
    parser.add_argument(
        "-p",
        "--plan",
        action="store_true",
        help="Use planning-focused prompt for complex tasks",
    )

    # File context option
    parser.add_argument(
        "-f",
        "--file",
        action="append",
        dest="files",
        help="Include file content as context (can be used multiple times)",
    )

    # Positional arguments for the query
    parser.add_argument("query", nargs="*", help="Question to ask the AI")

    args = parser.parse_args()

    # Handle init-config separately as it doesn't need full app initialization
    if args.init_config:
        from .config import AIxTermConfig

        config = AIxTermConfig()
        force = getattr(args, "force", False)

        config_path = config.config_path

        if config_path.exists() and not force:
            print(f"Configuration file already exists at: {config_path}")
            print(
                "Use --init-config --force to overwrite the existing "
                + "configuration."
            )
            sys.exit(1)

        success = config.create_default_config(overwrite=force)

        if success:
            print(f"Default configuration created at: {config_path}")
            print("\nYou can now edit this file to customize your AIxTerm settings.")
            print("Key settings to configure:")
            print("  - api_url: URL of your LLM API endpoint")
            print("  - api_key: API key for authentication (if required)")
            print("  - model: Model name to use")
            print("  - mcp_servers: MCP servers for additional tools")
        else:
            print("Failed to create configuration file.")
            sys.exit(1)

        sys.exit(0)

    app = AIxTerm(config_path=args.config)

    # Configure logging level from CLI argument
    import logging

    log_level = getattr(args, "log_level", "WARNING")

    # Configure logging for all aixterm modules
    aixterm_logger = logging.getLogger("aixterm")

    # Set the level for aixterm logger and propagate to children
    aixterm_logger.setLevel(getattr(logging, log_level))

    # Ensure all existing handlers in the hierarchy respect the new level
    for logger_name in logging.Logger.manager.loggerDict:
        if logger_name.startswith("aixterm"):
            logger = logging.getLogger(logger_name)
            logger.setLevel(getattr(logging, log_level))
            for handler in logger.handlers:
                handler.setLevel(getattr(logging, log_level))

    # Apply configuration overrides if provided
    if args.api_url:
        app.config.set("api_url", args.api_url)
    if args.api_key:
        app.config.set("api_key", args.api_key)

    try:
        if args.status:
            app.status()
        elif args.tools:
            app.list_tools()
        elif args.cleanup:
            app.cleanup_now()
        elif args.clear:
            app.clear_context()
        elif args.install_shell:
            app.install_shell_integration(args.shell)
        elif args.uninstall_shell:
            app.uninstall_shell_integration(args.shell)
        elif args.server or app.config.is_server_mode_enabled():
            # Run in server mode
            from .server import AIxTermServer

            server = AIxTermServer(app.config)
            server.start()
        elif args.query:
            query = " ".join(args.query)
            file_contexts = args.files or []
            app.run_cli_mode(query, file_contexts, use_planning=args.plan)
        else:
            parser.print_help()
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
