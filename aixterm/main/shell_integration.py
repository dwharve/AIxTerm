"""Shell integration functionality for AIxTerm."""

import os
import shutil
import stat
from pathlib import Path
from typing import Any, Dict, Optional

from aixterm.integration import get_shell_integration_manager
from aixterm.utils import get_logger


class ShellIntegrationManager:
    """Manages shell integration for AIxTerm."""

    def __init__(self, app_instance: Any):
        """Initialize the shell integration manager.

        Args:
            app_instance: The AIxTerm application instance
        """
        self.app = app_instance
        self.logger = get_logger(__name__)
        self.config = self.app.config
        self.display_manager = self.app.display_manager

    def install_integration(self, shell: str = "bash") -> None:
        """Install shell integration.

        Args:
            shell: Shell name (bash, zsh, fish)
        """
        self.logger.info(f"Installing shell integration for {shell}")

        try:
            # Get shell integration manager
            shell_manager = get_shell_integration_manager(shell)

            if not shell_manager:
                self.display_manager.show_error(
                    f"Shell {shell} is not supported. "
                    "Supported shells: bash, zsh, fish."
                )
                return

            # Install integration
            success = shell_manager.install()

            # Check results - install() returns boolean
            if success:
                # Show success message
                self.display_manager.show_success(
                    f"{shell} integration installed successfully!\n\n"
                    "Restart your shell to activate the integration.\n"
                    "You can now use 'ai' command in your terminal."
                )
            else:
                # Show error message
                self.display_manager.show_error(
                    f"Failed to install {shell} integration. "
                    "Check the logs for more details."
                )
        except Exception as e:
            self.logger.error(f"Error installing shell integration: {e}")
            self.display_manager.show_error(f"Error installing shell integration: {e}")

    def uninstall_integration(self, shell: str = "bash") -> None:
        """Uninstall shell integration.

        Args:
            shell: Shell name (bash, zsh, fish)
        """
        self.logger.info(f"Uninstalling shell integration for {shell}")

        try:
            # Get shell integration manager
            shell_manager = get_shell_integration_manager(shell)

            if not shell_manager:
                self.display_manager.show_error(
                    f"Shell {shell} is not supported. "
                    "Supported shells: bash, zsh, fish."
                )
                return

            # Uninstall integration
            success = shell_manager.uninstall()

            # Check results - uninstall() returns boolean
            if success:
                # Show success message
                self.display_manager.show_success(
                    f"{shell} integration uninstalled successfully!\n\n"
                    "Restart your shell for changes to take effect."
                )
            else:
                # Show error message
                self.display_manager.show_error(
                    f"Failed to uninstall {shell} integration. "
                    "Check the logs for more details."
                )
        except Exception as e:
            self.logger.error(f"Error uninstalling shell integration: {e}")
            self.display_manager.show_error(
                f"Error uninstalling shell integration: {e}"
            )

    def get_integration_status(self, shell: Optional[str] = None) -> Dict[str, Any]:
        """Get shell integration status.

        Args:
            shell: Optional shell name (bash, zsh, fish)

        Returns:
            Integration status information
        """
        # Initialize status dict
        status = {}

        # If specific shell requested, check only that one
        if shell:
            shell_manager = get_shell_integration_manager(shell)
            if shell_manager:
                status[shell] = shell_manager.get_status()
            return status

        # Otherwise check all supported shells
        for shell_name in ["bash", "zsh", "fish"]:
            shell_manager = get_shell_integration_manager(shell_name)
            if shell_manager:
                status[shell_name] = shell_manager.get_status()

        return status
