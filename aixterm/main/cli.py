"""Command-line interface for AIxTerm."""

import argparse
import sys
from typing import List, Optional

from aixterm.utils import get_current_shell, get_logger

from .app import AIxTermApp
from .shell_integration import ShellIntegrationManager
from .status_manager import StatusManager
from .tools_manager import ToolsManager


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="AIxTerm - Terminal AI Assistant",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Main query argument
    parser.add_argument(
        "query",
        nargs="*",
        help="Query text (can be provided as positional arguments)",
    )

    # Configuration options
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Path to custom configuration file",
    )

    # Context options
    parser.add_argument(
        "-c",
        "--clear-context",
        action="store_true",
        help="Clear current context",
    )

    # Tools options
    parser.add_argument(
        "-l",
        "--list-tools",
        action="store_true",
        help="List available tools",
    )

    # Status options
    parser.add_argument(
        "-s",
        "--status",
        action="store_true",
        help="Show AIxTerm status information",
    )

    # Debug options
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output",
    )

    # Cleanup options
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Run cleanup process now",
    )

    # Shell integration options
    parser.add_argument(
        "-i",
        "--install-shell",
        metavar="SHELL",
        nargs="?",
        const="__DEFAULT__",  # Special marker to indicate flag was provided without value
        default=None,  # Not provided at all
        help="Install shell integration (bash, zsh, fish). Defaults to current shell.",
    )

    parser.add_argument(
        "-u",
        "--uninstall-shell",
        metavar="SHELL",
        nargs="?",
        const="__DEFAULT__",  # Special marker to indicate flag was provided without value
        default=None,  # Not provided at all
        help="Uninstall shell integration (bash, zsh, fish). Defaults to current shell.",
    )

    # Advanced options
    parser.add_argument(
        "-t",
        "--thinking",
        action="store_true",
        help="Show thinking content in responses (hidden by default)",
    )

    # Planning options
    parser.add_argument(
        "-p",
        "--plan",
        action="store_true",
        help="Use planning mode for detailed problem analysis",
    )

    # File options
    parser.add_argument(
        "-",
        "--file",
        action="append",
        metavar="PATH",
        help="Path to a file to include in context",
    )

    # API options
    parser.add_argument(
        "--api_url",
        metavar="URL",
        help="Override the API URL",
    )

    parser.add_argument(
        "--api_key",
        metavar="KEY",
        help="Override the API key",
    )

    return parser.parse_args()


def run_cli_mode(
    app: AIxTermApp,
    query: Optional[List[str]] = None,
    context_lines: Optional[int] = None,  # Kept for compatibility but ignored
    show_thinking: bool = False,  # Changed default to False (hidden by default)
    no_prompt: bool = False,  # Kept for compatibility but ignored
    use_planning: bool = False,
    files: Optional[List[str]] = None,
) -> None:
    """Run AIxTerm in CLI mode.

    Args:
        app: AIxTerm application instance
        query: Optional query text as list of arguments
        context_lines: Optional number of context lines (deprecated, ignored)

        show_thinking: Whether to show thinking content (hidden by default)
        no_prompt: Whether to suppress prompt collection (deprecated, ignored)
        use_planning: Whether to use planning mode
        files: Optional list of file paths to include in context
    """
    logger = get_logger(__name__)

    # Check if we have input from stdin
    has_stdin = not sys.stdin.isatty()

    # Determine query source
    if has_stdin:
        # Read from stdin
        logger.debug("Reading query from stdin")
        query_text = sys.stdin.read().strip()
    elif query and query[0] == "-":
        # Single dash means read from stdin
        logger.debug("Reading query from stdin (- argument)")
        query_text = sys.stdin.read().strip()
    elif query:
        # Use provided query
        logger.debug(f"Using provided query: {query}")
        query_text = " ".join(query)
    else:
        # No query provided
        logger.error("No query provided")
        app.display_manager.show_error("Error: No query provided.")
        return

    # Run query
    app.run(
        query=query_text,
        context=[str(i) for i in range(context_lines)] if context_lines else None,
        show_thinking=show_thinking,
        no_prompt=no_prompt,
        use_planning=use_planning,
        files=files or [],
    )


def main() -> None:
    """Main entry point for AIxTerm."""
    # Parse arguments
    args = parse_arguments()

    # Set default shell for install/uninstall if not specified
    # Only set defaults if the arguments were actually provided (marked with __DEFAULT__)
    current_shell = get_current_shell()
    if hasattr(args, "install_shell") and args.install_shell == "__DEFAULT__":
        args.install_shell = current_shell
    if hasattr(args, "uninstall_shell") and args.uninstall_shell == "__DEFAULT__":
        args.uninstall_shell = current_shell

    try:
        # Initialize application
        app = AIxTermApp(config_path=args.config)

        # Handle API overrides
        if hasattr(args, "api_url") and args.api_url:
            app.config.set("api_url", args.api_url)

        if hasattr(args, "api_key") and args.api_key:
            app.config.set("api_key", args.api_key)

        # Create managers
        tools_manager = ToolsManager(app)
        status_manager = StatusManager(app)
        shell_manager = ShellIntegrationManager(app)

        # Handle context clearing
        if args.clear_context:
            status_manager.clear_context()
            return

        # Handle cleanup
        if args.cleanup:
            status_manager.cleanup_now()
            return

        # Handle status display
        if args.status:
            status_manager.show_status()
            return

        # Handle tool listing
        if args.list_tools:
            tools_manager.list_tools()
            return

        # Handle shell integration - only if arguments were actually provided
        if args.install_shell is not None:
            shell_manager.install_integration(args.install_shell)
            return

        if args.uninstall_shell is not None:
            shell_manager.uninstall_integration(args.uninstall_shell)
            return

        # Run in CLI mode
        run_cli_mode(
            app=app,
            query=args.query,
            context_lines=None,  # Removed context lines support
            show_thinking=args.thinking,  # Now defaults to False (hidden)
            no_prompt=False,  # Removed no_prompt argument
            use_planning=args.plan if hasattr(args, "plan") else False,
            files=args.file if hasattr(args, "file") and args.file else [],
        )
    except KeyboardInterrupt:
        logger = get_logger(__name__)
        logger.info("Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
