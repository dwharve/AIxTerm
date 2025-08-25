"""Base class for shell integrations."""

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Optional


class BaseIntegration(ABC):
    """Base class for shell integration implementations."""

    def __init__(self, logger: Any | None = None) -> None:
        """Initialize the integration.

        Args:
            logger: Logger instance
        """
        # Lazy default logger to avoid requiring subclasses to pass one
        if logger is None:

            class _NullLogger:
                def debug(self, msg: str) -> None:  # pragma: no cover - simple stub
                    pass

                def info(self, msg: str) -> None:  # pragma: no cover - simple stub
                    pass

                def warning(self, msg: str) -> None:  # pragma: no cover - simple stub
                    pass

                def error(self, msg: str) -> None:  # pragma: no cover - simple stub
                    pass

            self.logger = _NullLogger()
        else:
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
        """Return True if user config contains a source line for rc file."""
        if not config_file.exists():
            return False
        try:
            content = config_file.read_text()
            rc_ref = f".aixterm/{self.shell_name}.rc"
            return rc_ref in content
        except Exception as e:  # pragma: no cover - defensive
            self.logger.error(f"Error checking integration status: {e}")
            return False

    def install(self, force: bool = False, interactive: bool = True) -> bool:
        """Install integration using standalone rc file under ~/.aixterm.

        Strategy:
        - Write full script to ~/.aixterm/{shell}.rc (always refresh if force).
        - Append a small sourcing block to user config if missing or force.
        - Do not inline entire script into user config anymore.
        """
        print(f"Installing AIxTerm {self.shell_name} integration (rc mode)...")

        config_file = self.find_config_file()
        if not config_file:
            print(f"Error: Could not determine {self.shell_name} config file location")
            return False
        if not self.is_available():
            print(f"Error: {self.shell_name} is not available on this system")
            return False
        if not self.validate_integration_environment():
            print(f"Error: Environment validation failed for {self.shell_name}")
            return False

        config_file.parent.mkdir(parents=True, exist_ok=True)
        rc_dir = Path.home() / ".aixterm"
        try:
            if not rc_dir.exists():
                rc_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:  # pragma: no cover - race/parallel safety
            # Directory was created between exists() check and mkdir; safe to proceed
            pass
        except Exception:
            print("Error: Unable to create AIxTerm rc directory")
            return False
        rc_file = rc_dir / f"{self.shell_name}.rc"

        if force or not rc_file.exists():
            try:
                rc_file.write_text(self.generate_integration_code().lstrip())
                print(f" Wrote rc file: {rc_file}")
            except Exception as e:  # pragma: no cover - defensive
                print(f"Error writing rc file: {e}")
                return False

        installed = self.is_integration_installed(config_file)
        if installed and not force:
            print(f" Integration already installed in {config_file}")
            return True

        # Backup before modifying user config
        if not self._create_backup(config_file):
            print("Warning: Failed to create backup of shell config")

        # If force reinstall, remove existing snippet after backup so user can recover
        if force:
            self._remove_existing_integration(config_file)

        snippet = self._get_source_snippet(rc_file)
        # Ensure config file exists before reading
        if not config_file.exists():
            try:
                config_file.touch()
            except Exception as e:  # pragma: no cover
                print(f"Error creating shell config file: {e}")
                return False
        if not force:
            try:
                # Re-check after potential backup to avoid duplicate snippet
                if f".aixterm/{self.shell_name}.rc" in config_file.read_text():
                    return True
            except Exception:  # pragma: no cover
                pass
        try:
            with open(config_file, "a") as f:
                if not snippet.endswith("\n"):
                    snippet += "\n"
                f.write(snippet)
            print(f" Added sourcing snippet to {config_file}")
        except Exception as e:  # pragma: no cover - defensive
            print(f"Error updating shell config: {e}")
            return False

        print(" Installation complete. Source your shell config or open a new shell.")
        return True

    def _get_source_snippet(self, rc_file: Path) -> str:
        """Return snippet inserted into user config to source rc file."""
        return (
            f"\n{self.integration_marker}\n"
            f"# Source AIxTerm {self.shell_name} integration rc file\n"
            f"AIXTERM_RC=\"$HOME/.aixterm/{rc_file.name}\"\n"
            f"if [ -f \"$AIXTERM_RC\" ]; then\n"
            f"    . \"$AIXTERM_RC\"\n"
            f"fi\n"
        )

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
        """Remove previously added sourcing snippet from user config."""
        try:
            if not config_file.exists():
                return True
            lines = config_file.read_text().splitlines()
            rc_ref = f".aixterm/{self.shell_name}.rc"
            filtered: list[str] = []
            i = 0
            total = len(lines)
            while i < total:
                line = lines[i]
                # Primary (current) snippet starts with integration marker
                if self.integration_marker in line:
                    j = i + 1
                    # Advance until we find closing 'fi' of the snippet block
                    while j < total and lines[j].strip() != "fi":
                        j += 1
                    if j < total and lines[j].strip() == "fi":
                        j += 1  # include fi
                    # Skip trailing blank lines directly following the block
                    while j < total and lines[j].strip() == "":
                        j += 1
                    i = j
                    continue
                # Legacy snippet patterns that might lack variable or marker handling
                if rc_ref in line or "AIXTERM_RC=\"$HOME/.aixterm/" in line:
                    # Attempt to skip an enclosing if block if present (line may be 'if [ -f ...')
                    j = i + 1
                    while j < total and lines[j].strip() != "fi":
                        j += 1
                    if j < total and lines[j].strip() == "fi":
                        j += 1
                    while j < total and lines[j].strip() == "":
                        j += 1
                    i = j
                    continue
                # Fallback legacy source comment line
                if line.startswith("# Source AIxTerm "):
                    i += 1
                    continue
                filtered.append(line)
                i += 1
            # Trim trailing blank lines
            while filtered and filtered[-1].strip() == "":
                filtered.pop()
            new_content = "\n".join(filtered)
            if new_content:
                new_content += "\n"
            config_file.write_text(new_content)
            return True
        except Exception as e:  # pragma: no cover - defensive
            self.logger.error(f"Error removing existing integration: {e}")
            return False

    def _install_integration_code(self, config_file: Path) -> bool:
        """Install the integration code to config file.

        Args:
            config_file: Path to config file

        Returns:
            True if installation successful
        """
        # Legacy method retained for backward compatibility; now a no-op since
        # installation is handled via rc file + sourcing snippet.
        print(" Deprecated inline installation path invoked; no action taken.")
        return True

    def get_status(self) -> dict[str, Any]:
        """Get integration installation status for this shell.

        Returns:
            A dictionary with status information.
        """
        try:
            config_file = self.find_config_file()
            installed = False
            cfg_path = None
            if config_file:
                cfg_path = str(config_file)
                installed = self.is_integration_installed(config_file)

            return {
                "shell": self.shell_name,
                "installed": installed,
                "config_file": cfg_path,
            }
        except Exception as e:  # pragma: no cover - defensive
            self.logger.debug(f"Error getting integration status: {e}")
            return {"shell": self.shell_name, "installed": False, "error": str(e)}
