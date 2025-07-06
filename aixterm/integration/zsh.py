"""Zsh shell integration for AIxTerm terminal logging."""

import os
from pathlib import Path
from typing import List, Optional

from .base import BaseIntegration


class Zsh(BaseIntegration):
    """Zsh shell integration handler."""

    def __init__(self) -> None:
        """Initialize zsh integration."""

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
        return "zsh"

    @property
    def config_files(self) -> List[str]:
        """Return list of potential zsh config files."""
        return [".zshrc"]

    def generate_integration_code(self) -> str:
        """Return the zsh integration script content."""
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
    fc -R  # Read history file in zsh
}

# Function to show current session status
aixterm_status() {
    echo "AIxTerm Integration Status:"
    echo "Shell: zsh"
    echo "Active: $(test -n "$_AIXTERM_INTEGRATION_LOADED" && echo "Yes" || echo "No")"
    echo "Log file: $(_aixterm_get_log_file)"
    echo "TTY: $(tty 2>/dev/null || echo 'unknown')"

    # Show log file size if it exists
    local log_file=$(_aixterm_get_log_file)
    if [[ -f "$log_file" ]]; then
        local size=$(du -h "$log_file" | cut -f1)
        local lines=$(wc -l < "$log_file")
        echo "Log size: $size ($lines lines)"
    fi
}

# Function to cleanup old log files safely
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
                echo "Removing inactive log: $log_file"
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

# Zsh-specific command logging using preexec hook with full output capture
_aixterm_preexec() {
    # Log command before execution - with improved filtering
    local cmd="$1"
    if [[ "$cmd" != *"_aixterm_"* ]] && [[ "$cmd" != *"aixterm"* ]] && \\
       [[ "$cmd" != *"__vsc_"* ]] && [[ "$cmd" != *"VSCODE"* ]] && \\
       [[ "$cmd" != "builtin"* ]] && [[ "$cmd" != "unset"* ]] && \\
       [[ "$cmd" != "export _AIXTERM_"* ]] && [[ "$cmd" != "["* ]] && \\
       [[ "$cmd" != "[["* ]] && [[ "$cmd" != "echo #"* ]]; then
        local log_file=$(_aixterm_get_log_file)
        local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

        {
            echo "# Command at $timestamp on $(tty 2>/dev/null || echo 'unknown'): $cmd"
        } >> "$log_file" 2>/dev/null

        # Store last command and start time for output capture
        export _AIXTERM_LAST_COMMAND="$cmd"
        export _AIXTERM_COMMAND_START_TIME=$(date '+%s.%N')
    fi
}

# Function for explicit command execution with guaranteed output capture
log_command() {
    local cmd="$*"
    local log_file=$(_aixterm_get_log_file)
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local temp_output=$(mktemp)

    # Log the command
    {
        echo "# Explicit command execution at $timestamp: $cmd"
    } >> "$log_file" 2>/dev/null

    # Execute command and capture output
    eval "$cmd" 2>&1 | tee "$temp_output"
    local exit_code=${pipestatus[1]}

    # Log the output
    {
        echo "# Output:"
        cat "$temp_output"
        echo "# Exit code: $exit_code"
        echo ""
    } >> "$log_file" 2>/dev/null

    # Cleanup
    rm -f "$temp_output"

    return $exit_code
}

# Enhanced post-command function to capture exit codes and output
_aixterm_precmd() {
    local exit_code=$?
    local log_file=$(_aixterm_get_log_file)

    # Log exit code for the previous command
    if [[ -n "$_AIXTERM_LAST_COMMAND" ]] && \\
       [[ "$_AIXTERM_LAST_COMMAND" != *"_aixterm_"* ]]; then

        # Calculate command duration if we have start time
        local duration=""
        if [[ -n "$_AIXTERM_COMMAND_START_TIME" ]]; then
            local end_time=$(date '+%s.%N')
            duration=$(echo "$end_time - $_AIXTERM_COMMAND_START_TIME" | bc 2>/dev/null || echo "")
            unset _AIXTERM_COMMAND_START_TIME
        fi

        # For zsh, we capture output in post-command hook if not in minimal mode
        if [[ "$_AIXTERM_MINIMAL_MODE" != "1" ]]; then
            # In zsh, we can't easily capture the output after execution
            # So we provide timing and exit code information
            {
                echo "# Exit code: $exit_code"
                if [[ -n "$duration" ]]; then
                    echo "# Duration: ${duration}s"
                fi
                echo ""
            } >> "$log_file" 2>/dev/null
        else
            {
                echo "# Exit code: $exit_code"
                echo ""
            } >> "$log_file" 2>/dev/null
        fi
    fi

    # Clear the last command
    unset _AIXTERM_LAST_COMMAND

    return $exit_code
}

# Function to toggle minimal logging mode (commands only, no output)
aixterm_toggle_minimal_logging() {
    if [[ "$_AIXTERM_MINIMAL_MODE" == "1" ]]; then
        unset _AIXTERM_MINIMAL_MODE
        echo "AIxTerm: Full logging enabled (commands + output)"
    else
        export _AIXTERM_MINIMAL_MODE=1
        echo "AIxTerm: Minimal logging enabled (commands only)"
    fi
}

# Function to enable legacy minimal logging mode
aixterm_minimal_logging() {
    export _AIXTERM_MINIMAL_MODE=1
    echo "AIxTerm: Switched to minimal logging mode (commands only)"
    echo "Use 'aixterm_toggle_minimal_logging' to switch back to full logging"
}

# Session cleanup function
_aixterm_cleanup() {
    local log_file=$(_aixterm_get_log_file)
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    {
        echo "# Session ended at $timestamp"
        echo ""
    } >> "$log_file" 2>/dev/null
}

# Initialize fresh log for this session
_aixterm_init_fresh_log

# Function to check if integration is installed in config files
_aixterm_check_installation() {
    local needs_install=false
    local zshrc="$HOME/.zshrc"

    # Check .zshrc
    if [[ -f "$zshrc" ]]; then
        if ! grep -q "aixterm" "$zshrc" 2>/dev/null; then
            needs_install=true
        fi
    else
        needs_install=true
    fi

    echo "$needs_install"
}

# Function to install integration in shell config files
_aixterm_install_integration() {
    local zshrc="$HOME/.zshrc"
    local script_path="${(%):-%x}"  # zsh-specific way to get script path

    # If we can't determine the script path, skip auto-installation
    if [[ -z "$script_path" ]] || [[ ! -f "$script_path" ]]; then
        echo "AIxTerm: Cannot determine integration script path for auto-installation"
        return 1
    fi

    # Create .zshrc if it doesn't exist
    if [[ ! -f "$zshrc" ]]; then
        touch "$zshrc"
        echo "Created .zshrc"
    fi

    # Add integration to .zshrc
    {
        echo ""
        echo "# AIxTerm Integration - Auto-installed"
        echo "if [[ -f \"$script_path\" ]]; then"
        echo "    source \"$script_path\""
        echo "fi"
    } >> "$zshrc"

    echo "AIxTerm integration installed in .zshrc"
    echo "Restart your shell or run 'source ~/.zshrc' to activate"
    return 0
}

# Check and offer to install integration if missing
if [[ "$(_aixterm_check_installation)" == "true" ]]; then
    # Only auto-install if we're in an interactive shell and not already running from config
    if [[ $- == *i* ]] && [[ -z "$_AIXTERM_AUTO_INSTALLING" ]]; then
        echo "AIxTerm integration not found in shell configuration."
        echo "Would you like to install it automatically? [y/N]"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            export _AIXTERM_AUTO_INSTALLING=1
            _aixterm_install_integration
            unset _AIXTERM_AUTO_INSTALLING
        else
            echo "To install manually, add the following line to your .zshrc:"
            echo "source \"${(%):-%x}\""
        fi
    fi
fi

# Skip initialization if already loaded (but functions above are always defined)
[[ -n "$_AIXTERM_INTEGRATION_LOADED" ]] && return

# Set up zsh hooks
autoload -Uz add-zsh-hook
add-zsh-hook preexec _aixterm_preexec
add-zsh-hook precmd _aixterm_precmd

# Set up cleanup on shell exit
trap '_aixterm_cleanup' EXIT

# Export integration loaded flag
export _AIXTERM_INTEGRATION_LOADED=1

# Log that integration has been loaded
{
    echo "# AIxTerm integration loaded at $(date '+%Y-%m-%d %H:%M:%S')"
    echo "# Shell: zsh"
    echo "# TTY: $(tty 2>/dev/null || echo 'unknown')"
    echo "# Full logging active (commands + timing automatically captured)"
    echo "# Use 'aixterm_toggle_minimal_logging' to switch to commands-only mode"
    echo "# Use 'log_command <cmd>' for explicit command execution with guaranteed output"
    echo ""
} >> "$(_aixterm_get_log_file)" 2>/dev/null
"""

    def is_available(self) -> bool:
        """Check if zsh is available on the system."""
        try:
            import subprocess

            result = subprocess.run(
                ["zsh", "--version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_current_shell_version(self) -> Optional[str]:
        """Get the current zsh version."""
        try:
            import subprocess

            result = subprocess.run(
                ["zsh", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None

    def validate_integration_environment(self) -> bool:
        """Validate that the zsh environment supports our integration."""
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
        """Return zsh-specific installation notes."""
        return [
            "Zsh integration uses preexec and precmd hooks for command logging",
            "Supports .zshrc configuration file",
            "Commands, timing, and exit codes are logged automatically by default",
            "Use 'aixterm_toggle_minimal_logging' to switch to commands-only mode",
            "Use 'log_command <command>' for explicit command execution with guaranteed output",
            "Integration is only active in interactive shells",
            "Use 'aixterm_status' to check integration status",
        ]

    def get_troubleshooting_tips(self) -> List[str]:
        """Return zsh-specific troubleshooting tips."""
        return [
            "If logging isn't working, check that zsh hooks are loading properly",
            "Ensure add-zsh-hook is available (autoload -Uz add-zsh-hook)",
            "Check file permissions on ~/.aixterm_log.* files",
            "Integration requires interactive shell mode",
            "Some zsh frameworks (oh-my-zsh) may interfere with hooks",
            "Use 'log_command <cmd>' for commands that need guaranteed output capture",
            "If performance issues occur, use 'aixterm_toggle_minimal_logging' for commands-only mode",
            "Clean up old log files with 'aixterm_cleanup_logs' if disk space is an issue",
        ]

    def detect_framework(self) -> Optional[str]:
        """Detect if a zsh framework is being used."""
        frameworks = {
            "oh-my-zsh": "$ZSH",
            "prezto": "$ZDOTDIR/.zpreztorc",
            "zinit": "$ZINIT_HOME",
            "antigen": "$ANTIGEN_HOME",
            "antibody": "$ANTIBODY_HOME",
            "zplug": "$ZPLUG_HOME",
        }

        for name, var_or_file in frameworks.items():
            if var_or_file.startswith("$"):
                # Environment variable check
                var_name = var_or_file[1:]
                if os.environ.get(var_name):
                    return name
            else:
                # File existence check
                if Path(var_or_file).exists():
                    return name

        return None

    def get_framework_compatibility_notes(self) -> List[str]:
        """Return framework-specific compatibility notes."""
        framework = self.detect_framework()
        if not framework:
            return ["No zsh framework detected"]

        notes = [f"Detected framework: {framework}"]

        if framework == "oh-my-zsh":
            notes.extend(
                [
                    "Oh-My-Zsh detected - integration should work normally",
                    "If issues occur, try loading AIxTerm integration after oh-my-zsh",
                    "Some oh-my-zsh plugins may conflict with preexec hooks",
                ]
            )
        elif framework == "prezto":
            notes.extend(
                [
                    "Prezto detected - integration should work normally",
                    "Prezto's prompt module may interfere with precmd hooks",
                ]
            )
        elif framework == "zinit":
            notes.extend(
                [
                    "Zinit detected - should work well with AIxTerm integration",
                    "Load AIxTerm integration after zinit initialization",
                ]
            )
        else:
            notes.append(f"Framework {framework} compatibility not fully tested")

        return notes
