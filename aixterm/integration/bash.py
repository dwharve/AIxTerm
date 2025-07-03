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
        """Return the bash integration script content."""
        return """
# AIxTerm Shell Integration
# Automatically captures terminal activity for better AI context

# Only run if we're in an interactive shell
[[ $- == *i* ]] || return

# Function to get current log file based on TTY
_aixterm_get_log_file() {
    local tty_name=$(tty 2>/dev/null | sed 's|/dev/||g' | sed 's|/|-|g')
    echo "$HOME/.aixterm_log.${tty_name:-default}"
}

# Enhanced ai function that ensures proper logging
ai() {
    local log_file=$(_aixterm_get_log_file)
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local tty_name=$(tty 2>/dev/null)

    # Log the AI command with metadata
    {
        echo "# AI command executed at $timestamp on $tty_name"
        echo "$ ai $*"
    } >> "$log_file" 2>/dev/null

    # Run aixterm and log output
    command aixterm "$@" 2>&1 | tee -a "$log_file"
}

# Function to manually flush current session to log
aixterm_flush_session() {
    local log_file=$(_aixterm_get_log_file)
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "# Session flushed at $timestamp" >> "$log_file" 2>/dev/null
    history -a  # Append current session history to history file
}

# Function to show current session status
aixterm_status() {
    echo "AIxTerm Integration Status:"
    echo "  Shell: bash"
    echo "  Active: $(test -n "$_AIXTERM_INTEGRATION_LOADED" && \\
                    echo "Yes" || echo "No")"
    echo "  Log file: $(_aixterm_get_log_file)"
    echo "  TTY: $(tty 2>/dev/null || echo 'unknown')"

    # Show log file size if it exists
    local log_file=$(_aixterm_get_log_file)
    if [[ -f "$log_file" ]]; then
        local size=$(du -h "$log_file" | cut -f1)
        local lines=$(wc -l < "$log_file")
        echo "  Log size: $size ($lines lines)"
    fi
}

# Function to clean up old log files safely
aixterm_cleanup_logs() {
    local days=${1:-7}  # Default to 7 days
    echo "Cleaning up AIxTerm log files..."

    # Get list of currently active TTYs
    local active_ttys=$(who | awk '{print $2}' | sort -u)

    # Find all aixterm log files
    for log_file in "$HOME"/.aixterm_log.*; do
        [[ -f "$log_file" ]] || continue

        # Extract TTY name from log file
        local tty_name=$(basename "$log_file" | sed 's/^\\.aixterm_log\\.//')

        # Check if this TTY is currently active
        local is_active=false
        for active_tty in $active_ttys; do
            if [[ "$tty_name" == "$active_tty" || \\
                 "$tty_name" == "${active_tty//\\//-}" ]]; then
                is_active=true
                break
            fi
        done

        if [[ "$is_active" == "false" ]]; then
            # TTY is not active, check if log is old enough
            if [[ $(find "$log_file" -mtime +$days 2>/dev/null) ]]; then
                echo "  Removing inactive log: $log_file"
                rm -f "$log_file"
            fi
        fi
    done

    echo "Cleanup complete."
}

# Function to ensure fresh log for new sessions
_aixterm_init_fresh_log() {
    local log_file=$(_aixterm_get_log_file)
    local tty_name=$(tty 2>/dev/null | sed 's|/dev/||g' | sed 's|/|-|g')

    # Always start with a fresh log for new terminal sessions
    # Check if log exists and if previous session ended properly
    if [[ -f "$log_file" ]]; then
        # Check the last few lines to see if previous session ended
        local last_lines=$(tail -10 "$log_file" 2>/dev/null)
        if echo "$last_lines" | grep -q "# Session ended at"; then
            # Previous session ended cleanly, start completely fresh
            > "$log_file"
        else
            # Previous session might still be active or ended unexpectedly
            # Check if there are any active processes for this TTY
            local active_processes=$(ps -t "$tty_name" 2>/dev/null | wc -l)
            if [[ $active_processes -le 2 ]]; then
                # Only shell process, safe to clear
                > "$log_file"
            else
                # There might be active processes, append separator
                {
                    echo ""
                    echo "# =============================================="
                    echo "# Previous session may have ended unexpectedly"
                    echo "# New session starting at $(date '+%Y-%m-%d %H:%M:%S')"
                    echo "# =============================================="
                    echo ""
                } >> "$log_file" 2>/dev/null
            fi
        fi
    fi
}

# Function to clear current session log
aixterm_clear_log() {
    local log_file=$(_aixterm_get_log_file)
    if [[ -f "$log_file" ]]; then
        > "$log_file"
        echo "# Log cleared at $(date '+%Y-%m-%d %H:%M:%S')" >> "$log_file"
        echo "Current session log cleared."
    else
        echo "No current session log to clear."
    fi
}

# Skip initialization if already loaded (but functions above are always defined)
[[ -n "$_AIXTERM_INTEGRATION_LOADED" ]] && return

# Function to log commands with optional output capture
_aixterm_log_command() {
    # Only log if we have BASH_COMMAND and it's not an internal command
    if [[ -n "$BASH_COMMAND" ]] && [[ "$BASH_COMMAND" != *"_aixterm_"* ]] && \\
       [[ "$BASH_COMMAND" != *"aixterm"* ]] && [[ "$BASH_COMMAND" != "trap"* ]] && \\
       [[ "$BASH_COMMAND" != "history"* ]] && \\
       [[ "$BASH_COMMAND" != "PROMPT_COMMAND"* ]] && \\
       [[ "$BASH_COMMAND" != *"__vsc_"* ]] && [[ "$BASH_COMMAND" != *"VSCODE"* ]] && \\
       [[ "$BASH_COMMAND" != "builtin "* ]] && [[ "$BASH_COMMAND" != "unset "* ]] && \\
       [[ "$BASH_COMMAND" != "export _AIXTERM_"* ]] && \\
       [[ "$BASH_COMMAND" != "["* ]] && \\
       [[ "$BASH_COMMAND" != "[["* ]] && [[ "$BASH_COMMAND" != "echo #"* ]]; then
        local log_file=$(_aixterm_get_log_file)
        local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

        # Log command with metadata
        {
            echo "# Command at $timestamp on $(tty 2>/dev/null || \\
                  echo 'unknown'): $BASH_COMMAND"
        } >> "$log_file" 2>/dev/null

        # Store last command for exit code logging
        export _AIXTERM_LAST_COMMAND="$BASH_COMMAND"
    fi
}

# Function to capture command output using a wrapper (for explicit use)
log_with_output() {
    local cmd="$*"
    local log_file=$(_aixterm_get_log_file)
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local temp_output=$(mktemp)

    # Log the command
    {
        echo "# Command with output capture at $timestamp: $cmd"
    } >> "$log_file" 2>/dev/null

    # Execute command and capture output
    eval "$cmd" 2>&1 | tee "$temp_output"
    local exit_code=${PIPESTATUS[0]}

    # Log the output
    {
        echo "# Output:"
        cat "$temp_output"
        echo "# Exit code: $exit_code"
        echo ""
    } >> "$log_file" 2>/dev/null

    # Clean up
    rm -f "$temp_output"

    return $exit_code
}

# Post-command function to capture exit codes
_aixterm_post_command() {
    local exit_code=$?
    local log_file=$(_aixterm_get_log_file)

    # Log exit code for the previous command
    if [[ -n "$_AIXTERM_LAST_COMMAND" ]] && \\
       [[ "$_AIXTERM_LAST_COMMAND" != *"_aixterm_"* ]]; then
        {
            echo "# Exit code: $exit_code"
            echo ""
        } >> "$log_file" 2>/dev/null
    fi

    # Clear the last command
    unset _AIXTERM_LAST_COMMAND

    return $exit_code
}

# Function to enable full output logging for current session (experimental)
aixterm_enable_full_logging() {
    echo "Enabling experimental full output logging..."
    echo "This will capture all command output in addition to commands."
    echo "Note: This is experimental and may affect shell performance."

    # Use script command in a clean way
    local log_file=$(_aixterm_get_log_file)
    echo "# Full output logging enabled at $(date '+%Y-%m-%d %H:%M:%S')" >> "$log_file"

    # Start a new shell session with script logging
    exec script -a -f "$log_file.full" -c "$SHELL"
}

# Session cleanup function
_aixterm_cleanup_session() {
    local log_file=$(_aixterm_get_log_file)
    if [[ -n "$log_file" ]] && [[ -f "$log_file" ]]; then
        {
            echo "# Session ended at $(date '+%Y-%m-%d %H:%M:%S')"
            echo ""
        } >> "$log_file" 2>/dev/null
    fi

    # Clean up any temporary files
    rm -f /tmp/.aixterm_* 2>/dev/null

    # Kill any lingering tee processes (cleanup from previous problematic versions)
    pkill -f "tee.*aixterm_log" 2>/dev/null || true
}

# Set up logging
trap '_aixterm_log_command' DEBUG
trap '_aixterm_cleanup_session' EXIT

# Set up PROMPT_COMMAND for exit code capture
if [[ -z "$PROMPT_COMMAND" ]]; then
    PROMPT_COMMAND="_aixterm_post_command"
else
    PROMPT_COMMAND="_aixterm_post_command; $PROMPT_COMMAND"
fi

# Initialize fresh log session
_aixterm_init_fresh_log

# Log session start
{
    echo "# AIxTerm session started at $(date '+%Y-%m-%d %H:%M:%S')"
    echo "# TTY: $(tty 2>/dev/null || echo 'unknown')"
    echo "# PID: $$"
    echo "# Command logging active (use 'log_with_output <cmd>' for output capture)"
    echo "# Use 'aixterm_enable_full_logging' for experimental full output logging"
    echo ""
} >> "$(_aixterm_get_log_file)" 2>/dev/null

# Mark integration as loaded
export _AIXTERM_INTEGRATION_LOADED=1
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
            "Bash integration uses DEBUG trap for command logging",
            "Supports both .bashrc and .bash_profile configuration files",
            "Commands and exit codes are logged automatically",
            "Use 'log_with_output <command>' to capture command output",
            "Use 'aixterm_enable_full_logging' for experimental full output capture",
            "Integration is only active in interactive shells",
            "Use 'aixterm_status' to check integration status",
        ]

    def get_troubleshooting_tips(self) -> List[str]:
        """Return bash-specific troubleshooting tips."""
        return [
            "If logging isn't working, check that DEBUG trap is enabled",
            "Ensure $BASH_COMMAND variable is available",
            "Check file permissions on ~/.aixterm_log.* files",
            "Integration requires interactive shell mode ([[ $- == *i* ]])",
            "Some bash configurations may override DEBUG trap",
            "Use 'log_with_output <cmd>' for commands that need output capture",
            "If shell becomes unresponsive, check for hanging tee processes",
        ]
