# Service Installer Module

This directory contains the modularized components of the service installer that was previously 
contained in a single large `installer.py` file.

## Module Structure

The service installer is now divided into these modules:

### 1. `common.py`

Common utilities and base classes used by all platform-specific installers:
- `is_admin()`: Check for administrative/root privileges
- `get_installer()`: Factory function to get the appropriate installer
- `ServiceInstaller`: Base class for all service installers
- `UnsupportedPlatformError`: Exception for unsupported platforms

### 2. `windows.py`

Windows-specific implementation for service installation:
- `WindowsServiceInstaller`: Windows service manager using pywin32

### 3. `linux.py`

Linux-specific implementation for service installation:
- `LinuxServiceInstaller`: Linux service manager using systemd

### 4. `macos.py`

macOS-specific implementation for service installation:
- `MacOSServiceInstaller`: macOS service manager using launchd

## Usage

The original `installer.py` is maintained for backward compatibility and delegates to these modular components.

```python
# Example usage of the modular components
from aixterm.service.installer import get_installer

# Get platform-specific installer
installer = get_installer()

# Install service
installer.install(config_path="/path/to/config.json", user_mode=True)

# Check status
status = installer.status()

# Uninstall service
installer.uninstall()
```
