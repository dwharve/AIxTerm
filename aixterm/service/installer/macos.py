"""
macOS service installer implementation.
"""

import logging
import os
import plistlib
from typing import Any, Dict, Optional

from .common import ServiceInstaller, is_admin

logger = logging.getLogger(__name__)


class MacOSServiceInstaller(ServiceInstaller):
    """Service installer for macOS."""

    def install(
        self, config_path: Optional[str] = None, user_mode: bool = True
    ) -> bool:
        """
        Install the AIxTerm service on macOS.

        Args:
            config_path: Optional path to a configuration file.
            user_mode: Whether to install for the current user only.

        Returns:
            True if installation was successful, False otherwise.
        """
        try:
            # Check if we're running with admin privileges for system-wide installation
            if not user_mode and not is_admin():
                logger.error("Admin privileges required for system-wide installation")
                return False

            # Prepare service arguments
            python_exe = self._get_python_executable()
            script_path = self._get_aixterm_script()
            service_name = self._get_service_name()

            # Generate the plist content
            plist_content = self._generate_launchd_plist(
                python_exe, script_path, config_path, user_mode
            )

            # Determine where to write the plist file
            if user_mode:
                # User mode: write to user LaunchAgents directory
                launchd_dir = os.path.expanduser("~/Library/LaunchAgents")
                os.makedirs(launchd_dir, exist_ok=True)
                plist_file = os.path.join(launchd_dir, f"com.{service_name}.plist")

                # Write plist file
                with open(plist_file, "w") as f:
                    f.write(plist_content)

                # Load the service
                os.system(f"launchctl load {plist_file}")

            else:
                # System mode: write to system LaunchDaemons directory
                launchd_dir = "/Library/LaunchDaemons"
                plist_file = os.path.join(launchd_dir, f"com.{service_name}.plist")

                # Write plist file
                with open(plist_file, "w") as f:
                    f.write(plist_content)

                # Set permissions
                os.chmod(plist_file, 0o644)
                os.system(f"chown root:wheel {plist_file}")

                # Load the service
                os.system(f"launchctl load {plist_file}")

            logger.info(f"Service {service_name} installed and loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Error installing service: {e}")
            return False

    def uninstall(self, user_mode: bool = True) -> bool:
        """
        Uninstall the AIxTerm service on macOS.

        Args:
            user_mode: Whether to uninstall from the current user only.

        Returns:
            True if uninstallation was successful, False otherwise.
        """
        try:
            # Get service name
            service_name = self._get_service_name()

            # Determine plist file location
            if user_mode:
                plist_file = os.path.expanduser(
                    f"~/Library/LaunchAgents/com.{service_name}.plist"
                )
            else:
                plist_file = f"/Library/LaunchDaemons/com.{service_name}.plist"

            # Check if service exists
            if not os.path.exists(plist_file):
                logger.warning(f"Service {service_name} not found at {plist_file}")
                return False

            # Unload the service
            os.system(f"launchctl unload {plist_file}")

            # Remove plist file
            os.unlink(plist_file)

            logger.info(f"Service {service_name} uninstalled successfully")
            return True

        except Exception as e:
            logger.error(f"Error uninstalling service: {e}")
            return False

    def status(self) -> Dict[str, Any]:
        """
        Get the status of the AIxTerm service on macOS.

        Returns:
            A dictionary with service status information.
        """
        try:
            # Get service name
            service_name = self._get_service_name()
            label = f"com.{service_name}"

            # Check if we're in user mode
            user_mode = not is_admin()

            # Determine plist file location
            if user_mode:
                plist_file = os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")
                check_cmd = f"launchctl list | grep {label}"
            else:
                plist_file = f"/Library/LaunchDaemons/{label}.plist"
                check_cmd = f"sudo launchctl list | grep {label}"

            # Check if plist file exists
            installed = os.path.exists(plist_file)

            # If installed, check if it's loaded
            if installed:
                status_output = os.popen(check_cmd).read().strip()
                loaded = bool(status_output)

                return {
                    "installed": True,
                    "loaded": loaded,
                    "status": "loaded" if loaded else "not_loaded",
                    "service_name": service_name,
                    "plist_file": plist_file,
                    "user_mode": user_mode,
                }
            else:
                return {
                    "installed": False,
                    "loaded": False,
                    "status": "not_installed",
                    "service_name": service_name,
                    "user_mode": user_mode,
                }

        except Exception as e:
            return {"error": "Error getting service status", "message": str(e)}

    def _generate_launchd_plist(
        self,
        python_exe: str,
        script_path: str,
        config_path: Optional[str],
        user_mode: bool,
    ) -> str:
        """
        Generate launchd plist file content.

        Args:
            python_exe: Path to Python executable
            script_path: Path to AIxTerm service script
            config_path: Optional path to config file
            user_mode: Whether this is a user-level service

        Returns:
            Content for launchd plist file
        """
        # Build command arguments
        program_args = [python_exe, script_path]
        if config_path:
            program_args.extend(["--config", config_path])

        service_name = self._get_service_name()
        label = f"com.{service_name}"

        # Build plist dictionary
        plist_dict = {
            "Label": label,
            "ProgramArguments": program_args,
            "RunAtLoad": True,
            "KeepAlive": True,
            "StandardErrorPath": os.path.expanduser(
                f"~/Library/Logs/{service_name}.error.log"
            ),
            "StandardOutPath": os.path.expanduser(f"~/Library/Logs/{service_name}.log"),
        }

        # Convert to XML and return
        return plistlib.dumps(plist_dict).decode("utf-8")
