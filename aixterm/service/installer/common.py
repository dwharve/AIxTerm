"""
Common utilities for service installation across platforms.
"""

import logging
import os
import platform
import shutil
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def is_admin() -> bool:
    """
    Check if the current process has administrator/root privileges.

    Returns:
        True if running with admin privileges, False otherwise.
    """
    if platform.system() == "Windows":
        try:
            import ctypes

            shell32 = getattr(ctypes, "windll", None)
            if shell32 is None:
                return False
            return bool(shell32.shell32.IsUserAnAdmin() != 0)
        except Exception:  # Use specific exception instead of bare except
            return False
    else:
        try:
            # Check if geteuid exists first to avoid the AttributeError
            if hasattr(os, "geteuid"):
                return bool(os.geteuid() == 0)
            else:
                return False  # OS doesn't support geteuid
        except Exception:
            return False


def get_installer():
    """
    Get the appropriate service installer for the current platform.

    Returns:
        A ServiceInstaller instance for the current platform.

    Raises:
        UnsupportedPlatformError: If the current platform is not supported.
    """
    system = platform.system()

    if system == "Windows":
        from .windows import WindowsServiceInstaller

        return WindowsServiceInstaller()
    elif system == "Linux":
        from .linux import LinuxServiceInstaller

        return LinuxServiceInstaller()
    elif system == "Darwin":  # macOS
        from .macos import MacOSServiceInstaller

        return MacOSServiceInstaller()
    else:
        raise UnsupportedPlatformError(f"Unsupported platform: {system}")


class UnsupportedPlatformError(Exception):
    """Exception raised when the platform is not supported."""

    pass


class ServiceInstaller:
    """Base class for service installers."""

    def install(
        self, config_path: Optional[str] = None, user_mode: bool = True
    ) -> bool:
        """
        Install the AIxTerm service.

        Args:
            config_path: Optional path to a configuration file.
            user_mode: Whether to install for the current user only.

        Returns:
            True if installation was successful, False otherwise.
        """
        raise NotImplementedError("Subclasses must implement install")

    def uninstall(self, user_mode: bool = True) -> bool:
        """
        Uninstall the AIxTerm service.

        Args:
            user_mode: Whether to uninstall from the current user only.

        Returns:
            True if uninstallation was successful, False otherwise.
        """
        raise NotImplementedError("Subclasses must implement uninstall")

    def status(self) -> Dict[str, Any]:
        """
        Get the status of the AIxTerm service.

        Returns:
            A dictionary with service status information.
        """
        raise NotImplementedError("Subclasses must implement status")

    def _get_python_executable(self) -> str:
        """
        Get the path to the Python executable.

        Returns:
            The path to the Python executable.
        """
        return sys.executable

    def _get_aixterm_script(self) -> str:
        """
        Get the path to the AIxTerm service script.

        Returns:
            The path to the AIxTerm service script.
        """
        # Try to find the script in the same directory as the current script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(
            script_dir, "..", "..", "..", "bin", "aixterm_service"
        )

        # If not found, assume it's in the PATH
        if not os.path.exists(script_path):
            script_path = shutil.which("aixterm_service") or "aixterm_service"

        return script_path

    def _get_service_name(self) -> str:
        """
        Get the name of the service.

        Returns:
            The name of the service.
        """
        return "aixterm"

    def _get_service_display_name(self) -> str:
        """
        Get the display name of the service.

        Returns:
            The display name of the service.
        """
        return "AIxTerm Service"

    def _get_service_description(self) -> str:
        """
        Get the description of the service.

        Returns:
            The description of the service.
        """
        return "AI-powered command-line assistant service."
