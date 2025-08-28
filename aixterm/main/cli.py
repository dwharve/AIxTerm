"""Command-line interface for AIxTerm."""

import argparse
import os
import sys
from typing import List, Optional

from aixterm.utils import get_current_shell, get_logger
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

    # Streaming control (default: stream enabled)
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming output (non-streamed response)",
    )

    # Plugin help
    parser.add_argument(
        "--plugins-help",
        action="store_true",
        help="Show help information about plugins (e.g., devteam)",
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

    # Service control options
    parser.add_argument(
        "-r",
        "--restart",
        action="store_true",
        help="Restart the background AIxTerm service (for config/plugin reload)",
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
        "-f",
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


def _resolve_query_from_args(args_query: Optional[List[str]]) -> Optional[str]:
    """Resolve the query text from CLI args or stdin.

    Priority:
    1) If args provided, use them (join with spaces).
    2) If args is ["-"], read stdin.
    3) If no args and stdin is not a TTY, read stdin.
    """
    logger = get_logger(__name__)
    if args_query:
        if len(args_query) == 1 and args_query[0] == "-":
            logger.debug("Reading query from stdin (- argument)")
            return sys.stdin.read().strip()
        logger.debug(f"Using provided query: {args_query}")
        return " ".join(args_query)
    # No args; fallback to stdin if available
    if not sys.stdin.isatty():
        logger.debug("Reading query from stdin (no args)")
        return sys.stdin.read().strip()
    return None


def main() -> None:
    """Main entry point for AIxTerm."""
    # Parse arguments
    args = parse_arguments()

    # Apply debug flag early so all subsequent component initializations inherit it.
    # We intentionally set both environment variable (picked up by get_logger) and
    # adjust any already-created root/logger levels to DEBUG.
    if getattr(args, "debug", False):  # compatibility guard
        os.environ["AIXTERM_LOG_LEVEL"] = "DEBUG"
        import logging

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        # Bump any existing named loggers that may have been created prior to this point
        for name in list(logging.Logger.manager.loggerDict.keys()):
            try:
                logging.getLogger(name).setLevel(logging.DEBUG)
            except Exception:
                pass

    # Set default shell for install/uninstall if not specified
    # Only set defaults if the arguments were actually provided (marked with __DEFAULT__)
    current_shell = get_current_shell()
    if hasattr(args, "install_shell") and args.install_shell == "__DEFAULT__":
        args.install_shell = current_shell
    if hasattr(args, "uninstall_shell") and args.uninstall_shell == "__DEFAULT__":
        args.uninstall_shell = current_shell

    try:
        # Delay heavy application construction unless needed for non-query commands
        app = None

        # If debug, also push into runtime config later if we construct app

        # For service-backed queries we do not mutate runtime config here; service owns config

        # Managers will be created lazily only if needed (requires app)
        tools_manager = status_manager = shell_manager = None

        # Handle context clearing
        if args.clear_context:
            from .app import AIxTermApp  # lazy
            app = app or AIxTermApp(config_path=args.config)
            status_manager = status_manager or StatusManager(app)
            # Determine if a prompt will follow (positional args or stdin)
            has_stdin = not sys.stdin.isatty()
            has_args = bool(args.query)
            will_run_prompt = has_stdin or has_args

            # Suppress output when a prompt is present to avoid extra lines before inference output
            status_manager.clear_context(suppress_output=will_run_prompt)

            # If no prompt is provided, exit after clearing
            if not will_run_prompt:
                return

        # Handle cleanup
        if args.cleanup:
            from .app import AIxTermApp  # lazy
            app = app or AIxTermApp(config_path=args.config)
            status_manager = status_manager or StatusManager(app)
            status_manager.cleanup_now()
            return

        # Handle status display
        if args.status:
            from .app import AIxTermApp  # lazy
            app = app or AIxTermApp(config_path=args.config)
            status_manager = status_manager or StatusManager(app)
            status_manager.show_status()
            return

        # Handle plugins help
        if getattr(args, "plugins_help", False):
            from .app import AIxTermApp  # lazy
            app = app or AIxTermApp(config_path=args.config)
            app.display_manager.show_info("Plugins Help")
            app.display_manager.show_info(
                "- devteam: An example MCP plugin that exposes project/team tools.\n"
                "  Enable via config under mcp_servers. After enabling, restart the service (ai --restart).\n"
                "  Then, the LLM can discover and call devteam tools automatically.\n"
                "  See docs/plugins/README.md and docs/plugins/API.md for details."
            )
            return

        # Handle service restart (full process restart)
        if getattr(args, "restart", False):  # use getattr for compatibility with older mocks
            from aixterm.client.client import AIxTermClient  # local import to avoid startup cost
            from .app import AIxTermApp  # lazy for display only
            app = app or AIxTermApp(config_path=args.config)
            app.display_manager.show_info("Restarting AIxTerm service (full process restart)...")
            client = AIxTermClient(config_path=args.config)
            try:
                response = client.full_restart()
            except Exception as e:  # errors during restart
                app.display_manager.show_error(f"Failed to restart service: {e}")
                return

            if response.get("status") == "success":
                app.display_manager.show_success("Service fully restarted.")
            else:
                err = response.get("error", {})
                msg = err.get("message", "Unknown error")
                app.display_manager.show_error(f"Service restart failed: {msg}")
            return

        # Handle tool listing
        if args.list_tools:
            from .app import AIxTermApp  # lazy
            app = app or AIxTermApp(config_path=args.config)
            tools_manager = tools_manager or ToolsManager(app)
            tools_manager.list_tools()
            return

        # Handle shell integration - only if arguments were actually provided
        if args.install_shell is not None:
            from .app import AIxTermApp  # lazy
            app = app or AIxTermApp(config_path=args.config)
            shell_manager = shell_manager or ShellIntegrationManager(app)
            shell_manager.install_integration(args.install_shell)
            return

        if args.uninstall_shell is not None:
            from .app import AIxTermApp  # lazy
            app = app or AIxTermApp(config_path=args.config)
            shell_manager = shell_manager or ShellIntegrationManager(app)
            shell_manager.uninstall_integration(args.uninstall_shell)
            return

        # Default path: send query to running service (no local CLI mode)
        query_text = _resolve_query_from_args(args.query)
        if not query_text:
            logger = get_logger(__name__)
            logger.error("No query provided")
            print("Error: No query provided.")
            return

        from aixterm.client.client import AIxTermClient
        client = AIxTermClient(config_path=args.config)
        # Pass user's stream preference through
        stream_flag = not getattr(args, "no_stream", False)
        debug_flag = getattr(args, "debug", False)
        response = client.query(query_text, stream=stream_flag, debug=debug_flag)
        if response.get("status") != "success":
            err = response.get("error", {})
            print(f"Error: {err.get('message', 'Unknown error')}")
            return
        # If streaming occurred, chunks were already printed live
        if response.get("already_streamed") or (
            isinstance(response.get("result"), dict) and response["result"].get("already_streamed")
        ):
            return
        result = response.get("result", {})
        content = result if isinstance(result, str) else result.get("content", "")
        
        # Show debug information if present
        if isinstance(result, dict) and "debug" in result:
            print("\n" + "="*50)
            print("DEBUG INFORMATION")
            print("="*50)
            
            debug_info = result["debug"]
            
            # Show request information
            if "request" in debug_info:
                print("\nLLM API REQUEST:")
                print("-" * 20)
                req = debug_info["request"]
                print(f"Model: {req.get('model')}")
                print(f"Stream: {req.get('stream')}")
                print(f"Messages ({len(req.get('messages', []))} total):")
                for i, msg in enumerate(req.get("messages", [])[:3]):  # Show first 3 messages
                    role = msg.get("role", "unknown")
                    content_preview = str(msg.get("content", ""))[:100]
                    if len(str(msg.get("content", ""))) > 100:
                        content_preview += "..."
                    print(f"  [{i+1}] {role}: {content_preview}")
                if len(req.get("messages", [])) > 3:
                    print(f"  ... and {len(req.get('messages', [])) - 3} more messages")
                
                if req.get("tools"):
                    print(f"Tools: {len(req['tools'])} tools available")
                    print(f"Tool Choice: {req.get('tool_choice')}")
                
            # Show request metadata
            if "request_metadata" in debug_info:
                print("\nREQUEST METADATA:")
                print("-" * 20)
                meta = debug_info["request_metadata"]
                print(f"Message Count: {meta.get('message_count')}")
                print(f"Tool Count: {meta.get('tool_count')}")
                print(f"Total Message Characters: {meta.get('total_message_chars')}")
                print(f"Estimated Tokens: {meta.get('estimated_tokens')}")
            
            # Show response information
            if "response" in debug_info:
                print("\nLLM API RESPONSE:")
                print("-" * 20)
                resp = debug_info["response"]
                if resp.get("type") == "stream":
                    print(resp.get("note", "Streaming response"))
                else:
                    print(f"Response ID: {resp.get('id')}")
                    print(f"Model: {resp.get('model')}")
                    print(f"Created: {resp.get('created')}")
                    
                    if resp.get("usage"):
                        usage = resp["usage"]
                        print(f"Token Usage:")
                        print(f"  Prompt tokens: {usage.get('prompt_tokens')}")
                        print(f"  Completion tokens: {usage.get('completion_tokens')}")
                        print(f"  Total tokens: {usage.get('total_tokens')}")
                    
                    choices = resp.get("choices", [])
                    if choices:
                        choice = choices[0]
                        print(f"Finish Reason: {choice.get('finish_reason')}")
                        message = choice.get("message", {})
                        content_preview = str(message.get("content", ""))[:200]
                        if len(str(message.get("content", ""))) > 200:
                            content_preview += "..."
                        print(f"Content Preview: {content_preview}")
                        
                        if message.get("tool_calls"):
                            print(f"Tool Calls: {len(message['tool_calls'])} calls made")
            
            # Show error information if present
            if "error" in debug_info:
                print("\nERROR INFORMATION:")
                print("-" * 20)
                error = debug_info["error"]
                print(f"Error Type: {error.get('type')}")
                print(f"Error Message: {error.get('message')}")
            
            print("="*50)
            print()
        
        if content:
            print(content)
        else:
            print("(no content)")
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
