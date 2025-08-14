"""
Windows service installer implementation.
"""

import logging
from typing import Any, Dict, Optional

from .common import ServiceInstaller, is_admin

logger = logging.getLogger(__name__)


class WindowsServiceInstaller(ServiceInstaller):
    """Service installer for Windows."""

    def install(
        self, config_path: Optional[str] = None, user_mode: bool = True
    ) -> bool:
        """
        Install the AIxTerm service on Windows.

        Args:
            config_path: Optional path to a configuration file.
            user_mode: Whether to install for the current user only.

        Returns:
            True if installation was successful, False otherwise.
        """
        try:
            # Check if we're running with admin privileges
            if not user_mode and not is_admin():
                logger.error("Admin privileges required for system-wide installation")
                return False

            # Import required modules
            import win32service
            import win32serviceutil

            # Prepare service arguments
            python_exe = self._get_python_executable()
            script_path = self._get_aixterm_script()
            service_name = self._get_service_name()
            display_name = self._get_service_display_name()
            description = self._get_service_description()

            # Create service command line
            cmd_args = f'"{python_exe}" "{script_path}"'
            if config_path:
                cmd_args += f' --config "{config_path}"'

            # Check if service already exists
            try:
                win32serviceutil.QueryServiceStatus(service_name)
                logger.warning(f"Service {service_name} already exists")

                # Remove existing service first
                try:
                    win32serviceutil.StopService(service_name)
                except Exception:
                    pass  # Ignore errors when stopping

                win32serviceutil.RemoveService(service_name)
                logger.info(f"Existing service {service_name} removed")
            except Exception:
                # Service doesn't exist, that's fine
                pass

            # Create and start the service
            win32serviceutil.InstallService(
                pythonClassString="",  # No class required
                serviceName=service_name,
                displayName=display_name,
                description=description,
                startType=win32service.SERVICE_AUTO_START,
                exeArgs=cmd_args,
                exeName=python_exe,
                perfMonIni=None,
                perfMonDll=None,
                exeMachine=None,
                interactive=False,
            )

            # Start the service
            win32serviceutil.StartService(service_name)

            logger.info(f"Service {service_name} installed and started successfully")
            return True

        except ImportError:
            logger.error("Required modules for Windows service installation not found")
            logger.error("Please install pywin32: pip install pywin32")
            return False
        except Exception as e:
            logger.error(f"Error installing service: {e}")
            return False

    def uninstall(self, user_mode: bool = True) -> bool:
        """
        Uninstall the AIxTerm service on Windows.

        Args:
            user_mode: Whether to uninstall from the current user only.

        Returns:
            True if uninstallation was successful, False otherwise.
        """
        try:
            # Import required modules
            import win32serviceutil

            # Get service name
            service_name = self._get_service_name()

            # Check if service exists
            try:
                win32serviceutil.QueryServiceStatus(service_name)
            except Exception:
                logger.warning(f"Service {service_name} does not exist")
                return False

            # Stop and remove the service
            try:
                win32serviceutil.StopService(service_name)
            except Exception:
                pass  # Ignore errors when stopping

            win32serviceutil.RemoveService(service_name)

            logger.info(f"Service {service_name} uninstalled successfully")
            return True

        except ImportError:
            logger.error(
                "Required modules for Windows service uninstallation not found"
            )
            logger.error("Please install pywin32: pip install pywin32")
            return False
        except Exception as e:
            logger.error(f"Error uninstalling service: {e}")
            return False

    def status(self) -> Dict[str, Any]:
        """
        Get the status of the AIxTerm service on Windows.

        Returns:
            A dictionary with service status information.
        """
        try:
            # Import required modules
            import win32service
            import win32serviceutil

            # Get service name
            service_name = self._get_service_name()

            # Check if service exists
            try:
                status_info = win32serviceutil.QueryServiceStatus(service_name)

                # Map status code to string
                status_map = {
                    win32service.SERVICE_STOPPED: "stopped",
                    win32service.SERVICE_START_PENDING: "starting",
                    win32service.SERVICE_STOP_PENDING: "stopping",
                    win32service.SERVICE_RUNNING: "running",
                    win32service.SERVICE_CONTINUE_PENDING: "continuing",
                    win32service.SERVICE_PAUSE_PENDING: "pausing",
                    win32service.SERVICE_PAUSED: "paused",
                }

                statuscode = status_info[1]
                status_string = status_map.get(statuscode, f"unknown ({statuscode})")

                return {
                    "installed": True,
                    "status": status_string,
                    "code": statuscode,
                    "service_name": service_name,
                }
            except Exception as e:
                logger.debug(f"Error checking service status: {e}")
                return {
                    "installed": False,
                    "status": "not_installed",
                    "service_name": service_name,
                }

        except ImportError:
            return {
                "error": "Required modules not found",
                "message": "Please install pywin32: pip install pywin32",
            }
        except Exception as e:
            return {"error": "Error getting service status", "message": str(e)}
