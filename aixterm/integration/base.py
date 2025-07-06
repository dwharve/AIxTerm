"""Base class for shell integrations."""

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Optional


class BaseIntegration(ABC):
    """Base class for shell integration implementations."""

    def __init__(self, logger: Any) -> None:
        """Initialize the integration.

        Args:
            logger: Logger instance
        """
        self.logger = logger
        self.integration_marker = "# AIxTerm Shell Integration"

    @property
    @abstractmethod
    def shell_name(self) -> str:
        """Return the name of the shell this integration supports."""
        pass

    @property
    @abstractmethod
    def config_files(self) -> List[str]:
        """Return list of possible configuration file paths relative to home."""
        pass

    @abstractmethod
    def generate_integration_code(self) -> str:
        """Generate the shell-specific integration code.

        This should include:
        - TTY detection
        - Command logging with stdin/stdout/stderr capture
        - AI command wrapper

        Returns:
            Shell script code as string
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the shell is available on the system."""
        pass

    @abstractmethod
    def validate_integration_environment(self) -> bool:
        """Validate that the environment is suitable for integration."""
        pass

    @abstractmethod
    def get_installation_notes(self) -> List[str]:
        """Return shell-specific installation notes."""
        pass

    @abstractmethod
    def get_troubleshooting_tips(self) -> List[str]:
        """Return shell-specific troubleshooting tips."""
        pass

    def find_config_file(self) -> Optional[Path]:
        """Find existing config file or return path for first one.

        Returns:
            Path to config file to use
        """
        home = Path.home()

        # Find existing config file
        for config_name in self.config_files:
            config_path = home / config_name
            if config_path.exists():
                self.logger.debug(f"Found existing config file: {config_path}")
                return config_path

        # Return path for first config file (will be created)
        config_path = home / self.config_files[0]
        self.logger.debug(f"Using config file: {config_path}")
        return config_path

    def get_selected_config_file(self) -> Optional[Path]:
        """Get the selected configuration file path.

        Returns:
            Path to the configuration file that was or will be used
        """
        return self.find_config_file()

    def is_integration_installed(self, config_file: Path) -> bool:
        """Check if integration is already installed in config file.

        Args:
            config_file: Path to shell config file

        Returns:
            True if integration is already installed
        """
        if not config_file.exists():
            return False

        try:
            content = config_file.read_text()
            return self.integration_marker in content
        except Exception as e:
            self.logger.error(f"Error checking integration status: {e}")
            return False

    def install(self, force: bool = False, interactive: bool = True) -> bool:
        """Install the shell integration.

        Args:
            force: Whether to force reinstall if already installed
            interactive: Whether to prompt user for input

        Returns:
            True if installation successful
        """
        print(f"Installing AIxTerm {self.shell_name} integration...")

        config_file = self.find_config_file()
        if not config_file:
            print(f"Error: Could not determine {self.shell_name} config file location")
            return False

        # Check if shell is available
        if not self.is_available():
            print(f"Error: {self.shell_name} is not available on this system")
            return False

        # Validate environment
        if not self.validate_integration_environment():
            print(f"Error: Environment validation failed for {self.shell_name}")
            return False

        # Ensure parent directory exists (important for fish)
        config_file.parent.mkdir(parents=True, exist_ok=True)

        # Check if already installed
        if self.is_integration_installed(config_file):
            if not force:
                print(
                    f"Warning: AIxTerm integration already installed in {config_file}"
                )
                if interactive:
                    response = (
                        input("Do you want to reinstall? (y/N): ").strip().lower()
                    )
                    if response != "y":
                        print("Installation cancelled.")
                        return False
                else:
                    # In non-interactive mode, don't reinstall by default
                    print("Installation cancelled (already installed).")
                    return False

            # Remove existing integration
            if not self._remove_existing_integration(config_file):
                print("Error: Failed to remove existing integration")
                return False

        # Create backup
        if not self._create_backup(config_file):
            print("Warning: Failed to create backup")

        # Install integration
        return self._install_integration_code(config_file)

    def uninstall(self) -> bool:
        """Uninstall the shell integration.

        Returns:
            True if uninstallation successful
        """
        print(f"Uninstalling AIxTerm {self.shell_name} integration...")

        success = True
        config_files_to_check = []

        # Try to find the primary config file first
        primary_config = self.find_config_file()
        if primary_config and primary_config.exists():
            config_files_to_check.append(primary_config)
        else:
            # Fall back to checking all potential config files in home directory
            home = Path.home()
            for config_name in self.config_files:
                config_file = home / config_name
                if config_file.exists():
                    config_files_to_check.append(config_file)

        for config_file in config_files_to_check:
            if self.is_integration_installed(config_file):
                if self._remove_existing_integration(config_file):
                    print(f" Removed integration from: {config_file}")
                else:
                    print(f"Error: Failed to remove integration from {config_file}")
                    success = False

        return success

    def _create_backup(self, config_file: Path) -> bool:
        """Create backup of config file.

        Args:
            config_file: Path to config file

        Returns:
            True if backup created successfully
        """
        if not config_file.exists():
            return True

        try:
            backup_file = config_file.with_suffix(
                config_file.suffix + f".aixterm_backup_{int(time.time())}"
            )
            backup_file.write_text(config_file.read_text())
            print(f" Backup created: {backup_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            return False

    def _remove_existing_integration(self, config_file: Path) -> bool:
        """Remove existing integration from config file.

        Args:
            config_file: Path to config file

        Returns:
            True if removal successful
        """
        try:
            content = config_file.read_text()
            if self.integration_marker not in content:
                return True

            lines = content.split("\n")

            # Find the start and end of the integration block
            start_idx = None
            for i, line in enumerate(lines):
                if self.integration_marker in line:
                    start_idx = i
                    break

            if start_idx is None:
                return True  # No marker found

            # Find the end of the integration block by looking for the next
            # non-integration content
            end_idx = len(lines)  # Default to end of file

            for i in range(start_idx + 1, len(lines)):
                line = lines[i].strip()

                # If we hit an empty line and the next non-empty line doesn't
                # look like integration
                if line == "":
                    # Look ahead to see if the next non-empty line is
                    # integration-related
                    for j in range(i + 1, len(lines)):
                        next_line = lines[j].strip()
                        if next_line == "":
                            continue

                        # Check if this line looks like integration code
                        if not (
                            (
                                next_line.startswith("#")
                                and any(
                                    keyword in next_line.lower()
                                    for keyword in [
                                        "aixterm",
                                        "shell integration",
                                        "ai command",
                                        "session",
                                        "log",
                                        "tty",
                                        "timestamp",
                                    ]
                                )
                            )
                            or "_aixterm" in next_line
                            or "aixterm" in next_line.lower()
                            or "AIXTERM" in next_line
                            or next_line.startswith("ai()")
                            or "trap " in next_line
                            or "[[ $- == *i* ]]" in next_line
                            or '[[ -n "$_AIXTERM' in next_line
                            or "history -a" in next_line
                            or "tty 2>/dev/null" in next_line
                            or "date '+%Y-%m-%d" in next_line
                            or next_line.startswith("local ")
                            or next_line.startswith("echo ")
                            or next_line.startswith("command ")
                            or next_line.startswith("export ")
                            or next_line.startswith("}")
                            or next_line.startswith("return")
                            or next_line.startswith("fi")
                            or "set -" in next_line
                            or "autoload -Uz" in next_line
                            or "add-zsh-hook" in next_line
                            or next_line.startswith("if ")
                            or next_line.startswith("function ")
                            or next_line.startswith("then")
                            or next_line.startswith("else")
                            or next_line.startswith("elif")
                            or next_line.startswith("end")  # fish
                            or next_line.startswith("begin")  # fish
                            or "test -" in next_line  # fish test
                        ):
                            # This looks like non-integration code
                            # Use j, not i, since j is where the non-integration
                            # content starts
                            end_idx = j
                            break
                        else:
                            # Still looks like integration code, keep going
                            break
                    else:
                        # We reached the end of the file
                        end_idx = len(lines)
                        break

            # Remove the integration block
            filtered_lines = lines[:start_idx] + lines[end_idx:]

            # Clean up any extra blank lines at the end
            while filtered_lines and filtered_lines[-1].strip() == "":
                filtered_lines.pop()

            config_file.write_text("\n".join(filtered_lines))
            return True

        except Exception as e:
            self.logger.error(f"Error removing existing integration: {e}")
            return False

    def _install_integration_code(self, config_file: Path) -> bool:
        """Install the integration code to config file.

        Args:
            config_file: Path to config file

        Returns:
            True if installation successful
        """
        try:
            integration_code = self.generate_integration_code()

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

            return True

        except Exception as e:
            self.logger.error(f"Error installing integration: {e}")
            print(f"Error: Failed to install integration: {e}")
            return False
