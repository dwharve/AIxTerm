"""
AIxTerm Service Package

This package contains the service implementation for AIxTerm.
"""

from .context import ContextManager
from .installer.common import (
    ServiceInstaller,
    UnsupportedPlatformError,
    get_installer,
    is_admin,
)
from .installer.linux import LinuxServiceInstaller
from .installer.macos import MacOSServiceInstaller
from .installer.windows import WindowsServiceInstaller
from .plugin_manager import PluginManager
from .server import ServiceServer
from .service import AIxTermService, run_service

__all__ = [
    "AIxTermService",
    "run_service",
    "ServiceServer",
    "PluginManager",
    "ContextManager",
    "is_admin",
    "get_installer",
    "ServiceInstaller",
    "WindowsServiceInstaller",
    "LinuxServiceInstaller",
    "MacOSServiceInstaller",
    "UnsupportedPlatformError",
]
