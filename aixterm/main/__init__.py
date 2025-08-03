"""Main application logic for AIxTerm.

This module provides the core AIxTerm functionality,
split into modular components for better maintainability.
"""

from .app import AIxTermApp
from .cli import main, run_cli_mode
from .shell_integration import ShellIntegrationManager
from .status_manager import StatusManager
from .tools_manager import ToolsManager


# Re-export AIxTerm class for backward compatibility
class AIxTerm(AIxTermApp):
    """Main AIxTerm application class.

    This is a backward-compatible wrapper around AIxTermApp.
    For new code, use AIxTermApp directly.
    """

    def __init__(self, *args, **kwargs):
        """Initialize AIxTerm application."""
        super().__init__(*args, **kwargs)

        # Create managers for backward compatibility
        self._tools_manager = ToolsManager(self)
        self._status_manager = StatusManager(self)
        self._shell_manager = ShellIntegrationManager(self)

    def list_tools(self) -> None:
        """List available tools."""
        self._tools_manager.list_tools()

    def status(self) -> None:
        """Show AIxTerm status information."""
        self._status_manager.show_status()

    def cleanup_now(self) -> None:
        """Run cleanup process immediately."""
        self._status_manager.cleanup_now()

    def clear_context(self) -> None:
        """Clear current context."""
        self._status_manager.clear_context()

    def init_config(self, force: bool = False) -> None:
        """Initialize default configuration file."""
        self._status_manager.init_config(force=force)

    def run_cli_mode(self, *args, **kwargs) -> None:
        """Run AIxTerm in CLI mode."""
        run_cli_mode(app=self, *args, **kwargs)

    def install_shell_integration(self, shell: str = "bash") -> None:
        """Install shell integration."""
        self._shell_manager.install_integration(shell=shell)

    def uninstall_shell_integration(self, shell: str = "bash") -> None:
        """Uninstall shell integration."""
        self._shell_manager.uninstall_integration(shell=shell)

    def shutdown(self) -> None:
        """Shutdown AIxTerm gracefully.

        Override parent class method to prevent double shutdown calls
        to the mcp_client and other components.
        """
        self.logger.info("Shutting down AIxTerm (overridden)")

        # Only shut down MCP client once
        # This prevents the double-call issue in tests
        self.mcp_client.shutdown()

        # Skip parent class shutdown to avoid double shutdown calls
        # super().shutdown()

        self.logger.info("AIxTerm shutdown complete")


__all__ = [
    "AIxTerm",
    "AIxTermApp",
    "main",
    "run_cli_mode",
    "ToolsManager",
    "StatusManager",
    "ShellIntegrationManager",
]
