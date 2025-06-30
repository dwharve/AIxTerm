"""Main application logic for AIxTerm."""

import signal
import sys
from pathlib import Path
from typing import Any, List, Optional

from .cleanup import CleanupManager
from .config import AIxTermConfig
from .context import TerminalContext
from .llm import LLMClient, LLMError
from .mcp_client import MCPClient
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

        # Initialize components
        self.context_manager = TerminalContext(self.config)
        self.mcp_client = MCPClient(self.config)
        self.llm_client = LLMClient(self.config, self.mcp_client)
        self.cleanup_manager = CleanupManager(self.config)

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
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
                try:
                    all_tools = self.mcp_client.get_available_tools(brief=True)
                    if all_tools:
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

                        self.logger.info(
                            f"Optimized tools: {len(tools)}/{len(all_tools)} tools "
                            f"selected for context"
                        )
                    else:
                        tools = []
                except Exception as e:
                    self.logger.error(f"Failed to get MCP tools: {e}")
                    tools = None

            # Send query to LLM
            response = self.llm_client.ask_with_context(
                query, context, tools, use_planning=use_planning
            )

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

    def shutdown(self) -> None:
        """Shutdown AIxTerm gracefully."""
        self.logger.info("Shutting down AIxTerm")
        try:
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
            print("Use --init-config --force to overwrite the existing configuration.")
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
            # Initialize MCP client for CLI mode (starts servers)
            if self.config.get_mcp_servers():
                self.mcp_client.initialize_for_cli_mode()

            # Run the normal query processing
            self.run(query, file_contexts, use_planning)

        finally:
            # Always clean up MCP servers started for CLI mode
            if self.config.get_mcp_servers():
                self.mcp_client.shutdown_cli_mode_servers()

    def install_shell_integration(self, shell: str = "bash") -> None:
        """Install shell integration for automatic terminal session logging.

        Args:
            shell: Target shell type (bash, zsh, fish)
        """
        from pathlib import Path

        print("Installing AIxTerm shell integration...")

        # Determine shell configuration file
        shell_configs = {
            "bash": [".bashrc", ".bash_profile"],
            "zsh": [".zshrc"],
            "fish": [".config/fish/config.fish"],
        }

        if shell not in shell_configs:
            print(f"Error: Unsupported shell: {shell}")
            print("Supported shells: bash, zsh, fish")
            return

        home = Path.home()
        config_files = shell_configs[shell]

        # Find existing config file or use the first one
        config_file = None
        for cf in config_files:
            cf_path = home / cf
            if cf_path.exists():
                config_file = cf_path
                break

        if not config_file:
            config_file = home / config_files[0]
            if shell == "fish":
                config_file.parent.mkdir(parents=True, exist_ok=True)

        # Create integration script content based on shell
        if shell in ["bash", "zsh"]:
            integration_code = """
# AIxTerm Shell Integration
# Automatically captures terminal activity for better AI context

# Only run if we're in an interactive shell
[[ $- == *i* ]] || return

# Function to get current log file
_aixterm_get_log_file() {
    local tty_name=$(tty 2>/dev/null | sed 's/\\/dev\\///g' | sed 's/\\//-/g')
    echo "$HOME/.aixterm_log.${tty_name:-default}"
}

# Function to log commands for aixterm context
_aixterm_log_command() {
    # Only log if this isn't an aixterm command and we have BASH_COMMAND
    if [[ -n "$BASH_COMMAND" ]] && [[ "$BASH_COMMAND" != *"_aixterm_"* ]] && \\
       [[ "$BASH_COMMAND" != *"aixterm"* ]]; then
        local log_file=$(_aixterm_get_log_file)
        echo "$ $BASH_COMMAND" >> "$log_file" 2>/dev/null
    fi
}

# Set up command logging
if [[ -z "$_AIXTERM_INTEGRATION_LOADED" ]]; then
    trap '_aixterm_log_command' DEBUG
    export _AIXTERM_INTEGRATION_LOADED=1
fi

# Enhanced ai function that ensures proper logging
ai() {
    local log_file=$(_aixterm_get_log_file)

    # Log the AI command
    echo "$ ai $*" >> "$log_file" 2>/dev/null

    # Run aixterm and log output
    command aixterm "$@" 2>&1 | tee -a "$log_file"
}
"""
        elif shell == "fish":
            integration_code = """
# AIxTerm Shell Integration for Fish
# Automatically captures terminal activity for better AI context

# Function to get current log file
function _aixterm_get_log_file
    set tty_name (tty 2>/dev/null | sed 's/\\/dev\\///g' | sed 's/\\//-/g')
    echo "$HOME/.aixterm_log."(test -n "$tty_name"; and echo "$tty_name"; \\
        or echo "default")
end

# Function to log commands for aixterm context
function _aixterm_log_command --on-event fish_preexec
    # Skip aixterm commands
    if not string match -q "*aixterm*" -- $argv[1]
        set log_file (_aixterm_get_log_file)
        echo "$ $argv[1]" >> $log_file 2>/dev/null
    end
end

# Enhanced ai function
function ai
    set log_file (_aixterm_get_log_file)

    # Log the AI command
    echo "$ ai $argv" >> $log_file 2>/dev/null

    # Run aixterm and log output
    command aixterm $argv 2>&1 | tee -a $log_file
end
"""

        # Check if integration is already installed
        integration_marker = "# AIxTerm Shell Integration"
        try:
            if config_file.exists():
                content = config_file.read_text()
                if integration_marker in content:
                    print(
                        f"Warning: AIxTerm shell integration already "
                        f"installed in {config_file}"
                    )
                    response = (
                        input("Do you want to reinstall? (y/N): ").strip().lower()
                    )
                    if response != "y":
                        print("Installation cancelled.")
                        return

                    # Remove existing integration
                    lines = content.split("\n")
                    filtered_lines = []
                    skip = False
                    for line in lines:
                        if integration_marker in line:
                            skip = True
                        elif skip and line.strip() == "" and not line.startswith("#"):
                            skip = False
                        if not skip:
                            filtered_lines.append(line)

                    content = "\n".join(filtered_lines)
                    config_file.write_text(content)
        except Exception as e:
            print(f"Warning: Could not check existing integration: {e}")

        # Install integration
        try:
            # Create backup
            backup_file = config_file.with_suffix(
                config_file.suffix + f".aixterm_backup_{int(__import__('time').time())}"
            )
            if config_file.exists():
                backup_file.write_text(config_file.read_text())
                print(f" Backup created: {backup_file}")

            # Add integration
            with open(config_file, "a") as f:
                f.write(integration_code)

            print(f" Shell integration installed to: {config_file}")
            print(f" To activate: source {config_file}")
            print("   Or start a new terminal session")
            print("")
            print(" Usage:")
            print('  ai "your question"     # AI command with automatic logging')
            print("  # All terminal commands will be logged for context")
            print("")
            print(" Log files will be created at:")
            print("  ~/.aixterm_log.*         # Session-specific log files")

        except Exception as e:
            print(f"Error: Failed to install integration: {e}")

    def uninstall_shell_integration(self, shell: str = "bash") -> None:
        """Uninstall shell integration.

        Args:
            shell: Target shell type (bash, zsh, fish)
        """
        from pathlib import Path

        print("  Uninstalling AIxTerm shell integration...")

        shell_configs = {
            "bash": [".bashrc", ".bash_profile"],
            "zsh": [".zshrc"],
            "fish": [".config/fish/config.fish"],
        }

        if shell not in shell_configs:
            print(f"Error: Unsupported shell: {shell}")
            return

        home = Path.home()
        integration_marker = "# AIxTerm Shell Integration"

        for config_name in shell_configs[shell]:
            config_file = home / config_name
            if not config_file.exists():
                continue

            try:
                content = config_file.read_text()
                if integration_marker not in content:
                    continue

                # Remove integration section
                lines = content.split("\n")
                filtered_lines = []
                skip = False
                for line in lines:
                    if integration_marker in line:
                        skip = True
                    elif (
                        skip
                        and line.strip() == ""
                        and not line.startswith("#")
                        and not line.startswith(" ")
                    ):
                        skip = False
                    if not skip:
                        filtered_lines.append(line)

                # Write back cleaned content
                config_file.write_text("\n".join(filtered_lines))
                print(f" Removed integration from: {config_file}")

            except Exception as e:
                print(f"Error: Failed to remove integration from {config_file}: {e}")


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

    # Planning flag
    parser.add_argument(
        "-p",
        "--plan",
        action="store_true",
        help="Use planning-focused prompt for complex tasks",
    )

    # File context option
    parser.add_argument(
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
            print("Use --init-config --force to overwrite the existing configuration.")
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
            # Regular query with optional file context and planning in CLI mode
            # Use CLI mode to automatically manage MCP server lifecycle
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
