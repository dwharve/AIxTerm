"""
Linux service installer implementation.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .common import ServiceInstaller

logger = logging.getLogger(__name__)


class LinuxServiceInstaller(ServiceInstaller):
    """Linux-specific service installer using systemd."""

    def install(
        self, config_path: Optional[str] = None, user_mode: bool = True
    ) -> bool:
        """
        Install the AIxTerm service on Linux using systemd.

        Args:
            service_path: Path to the service executable
            user_mode: Whether to install for the current user only

        Returns:
            True if installation successful
        """
        try:
            service_name = self._get_service_name()
            # Resolve python and script paths
            python_exe = self._get_python_executable()
            script_path = self._get_aixterm_script()
            service_content = self._generate_service_file(
                python_exe, script_path, config_path, user_mode
            )

            # Determine service directory
            if user_mode:
                service_dir = Path.home() / ".config" / "systemd" / "user"
            else:
                service_dir = Path("/etc/systemd/system")

            service_dir.mkdir(parents=True, exist_ok=True)
            service_file = service_dir / f"{service_name}.service"

            # Write service file
            with open(service_file, "w") as f:
                f.write(service_content)

            os.chmod(service_file, 0o644)

            # Reload systemd and enable/start service
            systemctl_cmd = "systemctl --user" if user_mode else "systemctl"
            os.system(f"{systemctl_cmd} daemon-reload")
            os.system(f"{systemctl_cmd} enable {service_name}.service")
            os.system(f"{systemctl_cmd} start {service_name}.service")

            logger.info(f"Service {service_name} installed and started successfully")
            return True

        except Exception as e:
            logger.error(f"Error installing service: {e}")
            return False

    def uninstall(self, user_mode: bool = True) -> bool:
        """
        Uninstall the AIxTerm service on Linux.

        Args:
            user_mode: Whether to uninstall from the current user only.

        Returns:
            True if uninstallation was successful, False otherwise.
        """
        try:
            # Get service name
            service_name = self._get_service_name()

            # Determine systemctl command
            systemctl_cmd = "systemctl --user" if user_mode else "systemctl"

            # Stop and disable the service
            os.system(f"{systemctl_cmd} stop {service_name}.service")
            os.system(f"{systemctl_cmd} disable {service_name}.service")

            # Determine service file location
            if user_mode:
                service_file = os.path.expanduser(
                    f"~/.config/systemd/user/{service_name}.service"
                )
            else:
                service_file = f"/etc/systemd/system/{service_name}.service"

            # Remove service file
            if os.path.exists(service_file):
                os.unlink(service_file)

                # Reload systemd
                os.system(f"{systemctl_cmd} daemon-reload")

            logger.info(f"Service {service_name} uninstalled successfully")
            return True

        except Exception as e:
            logger.error(f"Error uninstalling service: {e}")
            return False

    def status(self) -> Dict[str, Any]:
        """
        Get the status of the AIxTerm service on Linux.

        Returns:
            A dictionary with service status information.
        """
        try:
            # Get service name
            service_name = self._get_service_name()

            # Determine likely mode: prefer user mode when user systemd dir exists
            user_mode = os.path.isdir(os.path.expanduser("~/.config/systemd/user"))

            # Build the systemctl command
            systemctl_cmd = "systemctl --user" if user_mode else "systemctl"
            cmd = f"{systemctl_cmd} is-active {service_name}.service"

            # Run the command
            status_output = os.popen(cmd).read().strip()

            # Check if service exists
            if status_output in ["inactive", "active"]:
                installed = True
            else:
                installed = False

            # If installed, get more details
            if installed:
                # Get service status
                status_cmd = f"{systemctl_cmd} status {service_name}.service"
                status_detail = os.popen(status_cmd).read().strip()

                return {
                    "installed": True,
                    "status": status_output,
                    "detail": status_detail,
                    "service_name": service_name,
                    "user_mode": user_mode,
                }
            else:
                return {
                    "installed": False,
                    "status": "not_installed",
                    "service_name": service_name,
                    "user_mode": user_mode,
                }

        except Exception as e:
            return {"error": "Error getting service status", "message": str(e)}

    def _generate_systemd_service(
        self,
        python_exe: str,
        script_path: str,
        config_path: Optional[str],
        user_mode: bool,
    ) -> str:
        """
        Generate systemd service file content.

        Args:
            python_exe: Path to Python executable
            script_path: Path to AIxTerm service script
            config_path: Optional path to config file
            user_mode: Whether this is a user-level service

        Returns:
            Content for systemd service file
        """
        # Build command
        exec_start = f'"{python_exe}" "{script_path}"'
        if config_path:
            exec_start += f' --config "{config_path}"'

        # Build service file content
        content = [
            "[Unit]",
            "Description=AIxTerm Service",
            "After=network.target",
            "",
            "[Service]",
            f"ExecStart={exec_start}",
            "Restart=on-failure",
            "RestartSec=5s",
            "",
            "[Install]",
            "WantedBy=default.target" if user_mode else "WantedBy=multi-user.target",
        ]

        return "\n".join(content)

    # Backward-compatibility shim for mypy which expects this method name
    def _generate_service_file(
        self,
        python_exe: str,
        script_path: str,
        config_path: Optional[str],
        user_mode: bool,
    ) -> str:
        return self._generate_systemd_service(
            python_exe, script_path, config_path, user_mode
        )
