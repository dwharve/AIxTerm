"""
AIxTerm Service Installation

This module provides utilities for installing and uninstalling AIxTerm as a system service.
This package contains modular components for service installation across different platforms.
"""

from .common import ServiceInstaller, UnsupportedPlatformError, get_installer, is_admin
from .linux import LinuxServiceInstaller
from .macos import MacOSServiceInstaller
from .windows import WindowsServiceInstaller

__all__ = [
    "is_admin",
    "get_installer",
    "ServiceInstaller",
    "WindowsServiceInstaller",
    "LinuxServiceInstaller",
    "MacOSServiceInstaller",
    "UnsupportedPlatformError",
]
