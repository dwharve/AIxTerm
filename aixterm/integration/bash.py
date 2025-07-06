"""Bash shell integration for AIxTerm terminal logging."""

import os
from pathlib import Path
from typing import List, Optional

from .base import BaseIntegration


class Bash(BaseIntegration):
    """Bash shell integration handler."""

    def __init__(self) -> None:
        """Initialize bash integration."""

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
        return "bash"

    @property
    def config_files(self) -> List[str]:
        """Return list of potential bash config files."""
        return [".bashrc", ".bash_profile"]

    def generate_integration_code(self) -> str:
        """Return the simplified bash integration script that uses script for
        full terminal logging."""
        return """
# AIxTerm Shell Integration - Simplified Script-Based Logger
# Logs complete terminal sessions using the script command

# Only run if we're in an interactive shell
[[ $- == *i* ]] || return

# Skip auto-start initialization if already loaded, but always define functions in script sessions
if [[ -n "$_AIXTERM_LOADED" ]] && [[ -z "$_AIXTERM_IN_SCRIPT" ]]; then
    return
fi

# Get log file based on original TTY, with proper fallback for script sessions
_aixterm_get_log_file() {
    # If we're in a script session and have the log file set, use that
    if [[ -n "$_AIXTERM_LOG_FILE" ]]; then
        echo "$_AIXTERM_LOG_FILE"
        return
    fi

    # Use original TTY if available, otherwise current TTY
    local tty_name
    if [[ -n "$_AIXTERM_ORIGINAL_TTY" ]]; then
        tty_name="$_AIXTERM_ORIGINAL_TTY"
    else
        tty_name=$(tty 2>/dev/null | sed 's|/dev/||g' | tr '/' '-')
    fi
    echo "$HOME/.aixterm_log.${tty_name:-default}"
}

# Show integration status
aixterm_status() {
    echo "AIxTerm Integration Status:"
    echo "  Shell: bash"
    echo "  Integration: $(test -n "$_AIXTERM_LOADED" && echo "Active" || echo "Inactive")"
    echo "  Log file: $(_aixterm_get_log_file)"
    echo "  Current TTY: $(tty 2>/dev/null || echo 'unknown')"

    if [[ -n "$_AIXTERM_ORIGINAL_TTY" ]]; then
        echo "  Original TTY: $_AIXTERM_ORIGINAL_TTY"
    fi

    local log_file=$(_aixterm_get_log_file)
    if [[ -f "$log_file" ]]; then
        local size=$(du -h "$log_file" 2>/dev/null | cut -f1)
        local lines=$(wc -l < "$log_file" 2>/dev/null)
        echo "  Log size: ${size:-0} (${lines:-0} lines)"
        echo "  Last modified: $(date -r "$log_file" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo 'unknown')"
    else
        echo "  Log file: Not created yet"
    fi

    # Show if we're in a script session
    if [[ -n "$_AIXTERM_IN_SCRIPT" ]]; then
        echo "  Script session: Active"
    else
        echo "  Script session: Not active"
    fi

    # Show environment variables for debugging
    echo "  Environment:"
    echo "    _AIXTERM_LOG_FILE=$_AIXTERM_LOG_FILE"
    echo "    _AIXTERM_IN_SCRIPT=$_AIXTERM_IN_SCRIPT"
    echo "    _AIXTERM_ORIGINAL_TTY=$_AIXTERM_ORIGINAL_TTY"
}

# Start logging with script command
aixterm_start_logging() {
    if [[ -n "$_AIXTERM_IN_SCRIPT" ]]; then
        echo "AIxTerm: Already inside a script session"
        return 1
    fi

    local log_file=$(_aixterm_get_log_file)

    if ! command -v script >/dev/null 2>&1; then
        echo "AIxTerm: 'script' command not available"
        return 1
    fi

    echo "Starting AIxTerm logging session..."
    echo "All terminal activity will be captured to: $log_file"

    # Add session header
    {
        echo "# ========================================"
        echo "# AIxTerm session started: $(date)"
        echo "# Original TTY: $(tty 2>/dev/null || echo 'unknown')"
        echo "# ========================================"
    } >> "$log_file" 2>/dev/null

    # Start script session with all necessary environment variables
    export _AIXTERM_IN_SCRIPT=1
    export _AIXTERM_LOG_FILE="$log_file"
    export _AIXTERM_ORIGINAL_TTY="$(tty 2>/dev/null | sed 's|/dev/||g' | tr '/' '-')"
    exec script -a -f "$log_file" -c "bash -i"
}

# Stop current script session
aixterm_stop_logging() {
    if [[ -z "$_AIXTERM_IN_SCRIPT" ]]; then
        echo "AIxTerm: Not in a script session"
        return 1
    fi

    local log_file=$(_aixterm_get_log_file)

    # Add session footer
    {
        echo ""
        echo "# ========================================"
        echo "# AIxTerm session ended: $(date)"
        echo "# ========================================"
    } >> "$log_file" 2>/dev/null

    echo "Ending AIxTerm logging session..."
    exit
}

# Toggle logging on/off
aixterm_toggle_logging() {
    if [[ -n "$_AIXTERM_IN_SCRIPT" ]]; then
        aixterm_stop_logging
    else
        aixterm_start_logging
    fi
}

# Clean up old log files
aixterm_cleanup_logs() {
    local days=${1:-7}
    echo "Cleaning up AIxTerm logs older than $days days..."
    find "$HOME" -name ".aixterm_log.*" -type f -mtime +$days -delete 2>/dev/null
    echo "Cleanup complete."
}

# Clear current log
aixterm_clear_log() {
    local log_file=$(_aixterm_get_log_file)
    if [[ -f "$log_file" ]]; then
        > "$log_file"
        echo "Log cleared: $log_file"
    else
        echo "No log file to clear."
    fi
}

# Enhanced ai function
ai() {
    local log_file=$(_aixterm_get_log_file)

    # Log the command (works in both script and non-script sessions)
    {
        echo "# AI command: $(date)"
        echo "$ ai $*"
    } >> "$log_file" 2>/dev/null

    # Run aixterm
    command aixterm "$@"
}

# Mark as loaded and export environment variables
export _AIXTERM_LOADED=1

# Always export the environment variables if they exist
[[ -n "$_AIXTERM_LOG_FILE" ]] && export _AIXTERM_LOG_FILE
[[ -n "$_AIXTERM_ORIGINAL_TTY" ]] && export _AIXTERM_ORIGINAL_TTY
[[ -n "$_AIXTERM_IN_SCRIPT" ]] && export _AIXTERM_IN_SCRIPT

# Only auto-start if not already in a script session and not already auto-started
if command -v script >/dev/null 2>&1 && [[ -z "$_AIXTERM_IN_SCRIPT" ]] && [[ -z "$_AIXTERM_AUTO_STARTED" ]]; then
    auto_log_file=$(_aixterm_get_log_file)

    echo "AIxTerm: Starting full session logging..."
    echo "All terminal activity will be logged to: $auto_log_file"

    # Add session header
    {
        echo "# ========================================"
        echo "# AIxTerm session started: $(date)"
        echo "# Original TTY: $(tty 2>/dev/null || echo 'unknown')"
        echo "# Auto-started full logging with script"
        echo "# ========================================"
    } >> "$auto_log_file" 2>/dev/null

    # Mark that we're starting the script session
    export _AIXTERM_AUTO_STARTED=1

    # Start script session with all necessary environment variables
    export _AIXTERM_IN_SCRIPT=1
    export _AIXTERM_LOG_FILE="$auto_log_file"
    export _AIXTERM_ORIGINAL_TTY="$(tty 2>/dev/null | sed 's|/dev/||g' | tr '/' '-')"
    exec script -a -f "$auto_log_file" -c "bash -i"
elif [[ -n "$_AIXTERM_IN_SCRIPT" ]]; then
    echo "AIxTerm: Integration loaded in script session. Use 'aixterm_status' for info."
else
    echo "AIxTerm: Integration loaded. Use 'aixterm_status' for info."
fi
"""

    def is_available(self) -> bool:
        """Check if bash is available on the system."""
        try:
            import subprocess

            result = subprocess.run(
                ["bash", "--version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_current_shell_version(self) -> Optional[str]:
        """Get the current bash version."""
        try:
            import subprocess

            result = subprocess.run(
                ["bash", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # Extract version from first line
                first_line = result.stdout.split("\n")[0]
                return first_line.strip()
            return None
        except Exception:
            return None

    def validate_integration_environment(self) -> bool:
        """Validate that the bash environment supports our integration."""
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

    def get_installation_notes(self) -> List[str]:
        """Return bash-specific installation notes."""
        return [
            "Simplified bash integration using 'script' command for complete "
            "terminal logging",
            "Automatically adds integration to .bashrc (and ensures .bash_profile "
            "sources .bashrc)",
            "Use 'aixterm_start_logging' to begin full terminal session capture",
            "Use 'aixterm_status' to check integration and log file status",
            "Integration is only active in interactive shells",
            "Full terminal sessions (commands + output) logged with 'script' command",
            "Basic command logging happens automatically when integration loads",
        ]

    def get_troubleshooting_tips(self) -> List[str]:
        """Return bash-specific troubleshooting tips."""
        return [
            "Integration requires the 'script' command (part of util-linux package)",
            "Check that the shell is interactive ([[ $- == *i* ]])",
            "Ensure write permissions to ~/.aixterm_log.* files",
            "Use 'aixterm_status' to check integration and log file status",
            "If script session is stuck, use Ctrl+D or 'exit' to end it",
            "Full session logging uses 'exec script' which replaces the current shell",
            "Clean up old logs with 'aixterm_cleanup_logs' if disk space is an issue",
            "Integration loads automatically; check for conflicts with other "
            "shell customizations",
        ]
