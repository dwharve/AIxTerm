"""Fish shell integration for AIxTerm terminal logging."""

import os
from pathlib import Path
from typing import List, Optional

from .base import BaseIntegration


class Fish(BaseIntegration):
    """Fish shell integration handler."""

    def __init__(self) -> None:
        """Initialize fish integration."""

        # Create a mock logger that does nothing
        class NullLogger:
            def debug(self, msg: str) -> None:
                pass

            def info(self, msg: str) -> None:
                pass

            def warning(self, msg: str) -> None:
                pass

            def error(self, msg: str) -> None:
                pass

        super().__init__(NullLogger())

    @property
    def shell_name(self) -> str:
        """Return the shell name."""
        return "fish"

    @property
    def config_files(self) -> List[str]:
        """Return list of potential fish config files."""
        return [".config/fish/config.fish"]

    def generate_integration_code(self) -> str:
        """Return the fish integration script content."""
        return r"""
# AIxTerm Shell Integration for Fish
# Automatically captures terminal activity for better AI context

# Function to get current log file based on TTY
function _aixterm_get_log_file
    set tty_name (tty 2>/dev/null | sed 's|/dev/||g' | sed 's|/|-|g')
    echo "$HOME/.aixterm_log."(
        test -n "$tty_name"; and echo "$tty_name"; or echo "default"
    )
end

# Enhanced ai function that ensures proper logging
function ai
    set log_file (_aixterm_get_log_file)
    set timestamp (date '+%Y-%m-%d %H:%M:%S')
    set tty_name (tty 2>/dev/null; or echo 'unknown')

    # Log the AI command with metadata
    begin
        echo "# AI command executed at $timestamp on $tty_name"
        echo "$ ai $argv"
    end >> "$log_file" 2>/dev/null

    # Run aixterm and log output
    command aixterm $argv 2>&1 | tee -a "$log_file"
end

# Function to manually flush current session to log
function aixterm_flush_session
    set log_file (_aixterm_get_log_file)
    set timestamp (date '+%Y-%m-%d %H:%M:%S')

    echo "# Session flushed at $timestamp" >> "$log_file" 2>/dev/null
    history save  # Save current session history
end

# Function to show current session status
function aixterm_status
    echo "AIxTerm Integration Status:"
    echo "  Shell: fish"
    echo "  Active: "(test -n "$_AIXTERM_INTEGRATION_LOADED"; \\
                     and echo "Yes"; or echo "No")
    echo "  Log file: "(_aixterm_get_log_file)
    echo "  TTY: "(tty 2>/dev/null; or echo 'unknown')

    # Show log file size if it exists
    set log_file (_aixterm_get_log_file)
    if test -f "$log_file"
        set size (du -h "$log_file" | cut -f1)
        set lines (wc -l < "$log_file")
        echo "  Log size: $size ($lines lines)"
    end
end

# Function to clean up old log files safely
function aixterm_cleanup_logs
    set days $argv[1]
    test -z "$days"; and set days 7  # Default to 7 days
    echo "Cleaning up AIxTerm log files..."

    # Get list of currently active TTYs
    set active_ttys (who | awk '{print $2}' | sort -u)

    # Find all aixterm log files
    for log_file in "$HOME"/.aixterm_log.*
        test -f "$log_file"; or continue

        # Extract TTY name from log file
        set tty_name (basename "$log_file" | sed 's/^\.aixterm_log\.//')

        # Check if this TTY is currently active
        set is_active false
        for active_tty in $active_ttys
            if test "$tty_name" = "$active_tty"; or \\
               string match -q "*$tty_name*" -- (string replace '/' '-' "$active_tty")
                set is_active true
                break
            end
        end

        if test "$is_active" = "false"
            # TTY is not active, check if log is old enough
            if find "$log_file" -mtime +$days 2>/dev/null | read
                echo "  Removing inactive log: $log_file"
                rm -f "$log_file"
            end
        end
    end

    echo "Cleanup complete."
end

# Function to ensure fresh log for new sessions
function _aixterm_init_fresh_log
    set log_file (_aixterm_get_log_file)
    set tty_name (tty 2>/dev/null | sed 's|/dev/||g' | sed 's|/|-|g')

    # Always start with a fresh log for new terminal sessions
    # Check if log exists and if previous session ended properly
    if test -f "$log_file"
        # Check the last few lines to see if previous session ended
        set last_lines (tail -10 "$log_file" 2>/dev/null)
        if echo "$last_lines" | grep -q "# Session ended at"
            # Previous session ended cleanly, start completely fresh
            echo "" > "$log_file"
        else
            # Previous session might still be active or ended unexpectedly
            # Check if there are any active processes for this TTY
            set active_processes (ps -t "$tty_name" 2>/dev/null | wc -l)
            if test $active_processes -le 2
                # Only shell process, safe to clear
                echo "" > "$log_file"
            else
                # There might be active processes, append separator
                begin
                    echo ""
                    echo "# =============================================="
                    echo "# Previous session may have ended unexpectedly"
                    echo "# New session starting at "(date '+%Y-%m-%d %H:%M:%S')
                    echo "# =============================================="
                    echo ""
                end >> "$log_file" 2>/dev/null
            end
        end
    end
end

# Function to clear current session log
function aixterm_clear_log
    set log_file (_aixterm_get_log_file)
    if test -f "$log_file"
        echo "" > "$log_file"
        echo "# Log cleared at "(date '+%Y-%m-%d %H:%M:%S') >> "$log_file"
        echo "Current session log cleared."
    else
        echo "No current session log to clear."
    end
end

# Function to capture command output using a wrapper (for explicit use)
function log_with_output
    set cmd $argv
    set log_file (_aixterm_get_log_file)
    set timestamp (date '+%Y-%m-%d %H:%M:%S')
    set temp_output (mktemp)

    # Log the command
    begin
        echo "# Command with output capture at $timestamp: $cmd"
    end >> "$log_file" 2>/dev/null

    # Execute command and capture output
    eval $cmd 2>&1 | tee "$temp_output"
    set exit_code $status

    # Log the output
    begin
        echo "# Output:"
        cat "$temp_output"
        echo "# Exit code: $exit_code"
        echo ""
    end >> "$log_file" 2>/dev/null

    # Clean up
    rm -f "$temp_output"

    return $exit_code
end

# Function to enable full output logging for current session (experimental)
function aixterm_enable_full_logging
    echo "Enabling experimental full output logging..."
    echo "This will capture all command output in addition to commands."
    echo "Note: This is experimental and may affect shell performance."

    # Use script command in a clean way
    set log_file (_aixterm_get_log_file)
    echo "# Full output logging enabled at "(date '+%Y-%m-%d %H:%M:%S') >> "$log_file"

    # Start a new shell session with script logging
    exec script -a -f "$log_file.full" -c fish
end

# Skip initialization if already loaded (but functions above are always defined)
if set -q _AIXTERM_INTEGRATION_LOADED
    exit 0
end

# Fish-specific command logging using preexec event
function _aixterm_log_command --on-event fish_preexec
    # Enhanced filtering to skip internal commands
    set cmd $argv[1]
    if not string match -q "*aixterm*" -- "$cmd"; \\
       and not string match -q "*_aixterm_*" -- "$cmd"; \\
       and not string match -q "builtin *" -- "$cmd"; \\
       and not string match -q "set _AIXTERM_*" -- "$cmd"
        set log_file (_aixterm_get_log_file)
        set timestamp (date '+%Y-%m-%d %H:%M:%S')

        begin
            echo "# Command at $timestamp on "(tty 2>/dev/null; \\
                  or echo 'unknown')": $cmd"
        end >> "$log_file" 2>/dev/null

        # Store last command for exit code logging
        set -g _AIXTERM_LAST_COMMAND "$cmd"
    end
end

# Post-command function to capture exit codes
function _aixterm_post_command --on-event fish_postexec
    set exit_code $status
    set log_file (_aixterm_get_log_file)

    # Log exit code for the previous command
    if set -q _AIXTERM_LAST_COMMAND; \\
       and not string match -q "*_aixterm_*" -- "$_AIXTERM_LAST_COMMAND"
        begin
            echo "# Exit code: $exit_code"
            echo ""
        end >> "$log_file" 2>/dev/null
    end

    # Clear the last command
    set -e _AIXTERM_LAST_COMMAND
end

# Session cleanup function
function _aixterm_cleanup_session --on-process-exit $fish_pid
    set log_file (_aixterm_get_log_file)
    if test -n "$log_file"; and test -f "$log_file"
        begin
            echo "# Session ended at "(date '+%Y-%m-%d %H:%M:%S')
            echo ""
        end >> "$log_file" 2>/dev/null
    end

    # Clean up any temporary files
    rm -f /tmp/.aixterm_* 2>/dev/null

    # Kill any lingering tee processes (cleanup from previous problematic versions)
    pkill -f "tee.*aixterm_log" 2>/dev/null; or true
end

# Initialize fresh log session
_aixterm_init_fresh_log

# Log session start
begin
    echo "# AIxTerm session started at "(date '+%Y-%m-%d %H:%M:%S')
    echo "# TTY: "(tty 2>/dev/null; or echo 'unknown')
    echo "# PID: "(echo %self)
    echo "# Command logging active (use 'log_with_output <cmd>' for output capture)"
    echo "# Use 'aixterm_enable_full_logging' for experimental full output logging"
    echo ""
end >> (_aixterm_get_log_file) 2>/dev/null

# Mark integration as loaded
set -g _AIXTERM_INTEGRATION_LOADED 1
"""

    def is_available(self) -> bool:
        """Check if fish is available on the system."""
        try:
            import subprocess

            result = subprocess.run(
                ["fish", "--version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_current_shell_version(self) -> Optional[str]:
        """Get the current fish version."""
        try:
            import subprocess

            result = subprocess.run(
                ["fish", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None

    def validate_integration_environment(self) -> bool:
        """Validate that the fish environment supports our integration."""
        try:
            # Check if we can detect TTY
            tty_result = os.system("tty >/dev/null 2>&1")
            if tty_result != 0:
                return False

            # Check if we can write to home directory
            home = Path.home()
            test_file = home / ".aixterm_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
                return True
            except Exception:
                return False
        except Exception:
            return False

    def prepare_config_directory(self) -> bool:
        """Create fish config directory if it doesn't exist."""
        try:
            config_dir = Path.home() / ".config" / "fish"
            config_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False

    def install(self, force: bool = False, interactive: bool = True) -> bool:
        """Install fish shell integration."""
        # Ensure config directory exists
        if not self.prepare_config_directory():
            return False

        return super().install(force, interactive)

    def get_installation_notes(self) -> List[str]:
        """Return fish-specific installation notes."""
        return [
            "Fish integration uses event-driven hooks (fish_preexec and fish_postexec)",
            "Configuration is stored in ~/.config/fish/config.fish",
            "Commands and exit codes are logged automatically",
            "Use 'log_with_output <command>' to capture command output",
            "Use 'aixterm_enable_full_logging' for experimental full output capture",
            "Integration is only active in interactive shells",
            "Use 'aixterm_status' to check integration status",
        ]

    def get_troubleshooting_tips(self) -> List[str]:
        """Return fish-specific troubleshooting tips."""
        return [
            "If logging isn't working, check fish event system with "
            + "'functions --handlers'",
            "Ensure ~/.config/fish directory exists and is writable",
            "Check file permissions on ~/.aixterm_log.* files",
            "Fish events require fish version 2.3.0 or later",
            "Use 'fish --version' to verify fish version compatibility",
            "Use 'log_with_output <cmd>' for commands that need output capture",
            "If shell becomes unresponsive, check for hanging tee processes",
        ]

    def get_fish_features(self) -> List[str]:
        """Return fish-specific feature descriptions."""
        return [
            "Event-driven command logging with fish_preexec",
            "Automatic session cleanup on shell exit",
            "Native fish event system for reliable logging",
            "TTY-based log file separation",
            "Enhanced ai function with automatic logging",
            "Session status and flush utilities",
        ]

    def check_fish_events_support(self) -> bool:
        """Check if the fish version supports events."""
        try:
            import subprocess

            result = subprocess.run(
                ["fish", "-c", "functions --handlers"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # If the command succeeds, events are supported
            return result.returncode == 0
        except Exception:
            return False

    def get_compatibility_info(self) -> dict:
        """Get detailed compatibility information."""
        version = self.get_current_shell_version()
        events_support = self.check_fish_events_support()

        return {
            "version": version,
            "events_supported": events_support,
            "config_dir_exists": (Path.home() / ".config" / "fish").exists(),
            "min_version_met": (
                self._check_min_fish_version(version) if version else False
            ),
        }

    def _check_min_fish_version(self, version_string: str) -> bool:
        """Check if fish version meets minimum requirements (2.3.0+)."""
        try:
            # Extract version number from version string
            import re

            version_match = re.search(
                r"fish, version (\d+)\.(\d+)\.(\d+)", version_string
            )
            if not version_match:
                return False

            major, minor, patch = map(int, version_match.groups())

            # Check if version is 2.3.0 or later
            if major > 2:
                return True
            elif major == 2 and minor >= 3:
                return True
            else:
                return False
        except Exception:
            return False
