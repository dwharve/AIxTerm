"""Zsh shell integration for AIxTerm terminal logging."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

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

# Skip initialization if already loaded (but functions above are always defined)
[[ -n "$_AIXTERM_INTEGRATION_LOADED" ]] && return

# Zsh-specific command logging using preexec hook
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

        # Store last command for exit code logging
        export _AIXTERM_LAST_COMMAND="$cmd"
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

# Post-command function to capture exit codes
_aixterm_precmd() {
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
    echo ""
} >> "$(_aixterm_get_log_file)" 2>/dev/null
"""

    def get_integration_snippet(self) -> str:
        """Get the snippet to add to shell config."""
        return """
# AIxTerm integration
if [[ -n "$TERM" && "$TERM" != "dumb" ]]; then
    python3 -c "
try:
    from aixterm.integration import setup_shell_integration
    setup_shell_integration('zsh')
except ImportError:
    pass
" 2>/dev/null
fi
"""

    def is_integration_installed(self, config_file: Path) -> bool:
        """Check if integration is installed in the given config file."""
        return super().is_integration_installed(config_file)

    def get_installation_status(self) -> Dict[str, Any]:
        """Get detailed installation status."""
        status: Dict[str, Any] = {"installed": False, "config_files": []}

        for config_file in self.config_files:
            config_path = Path.home() / config_file
            file_status = {
                "path": str(config_path),
                "exists": config_path.exists(),
                "has_integration": False,
                "writable": False,
            }

            if config_path.exists():
                try:
                    content = config_path.read_text()
                    file_status["has_integration"] = "# AIxTerm integration" in content
                    file_status["writable"] = os.access(config_path, os.W_OK)
                    if file_status["has_integration"]:
                        status["installed"] = True
                except Exception as e:
                    file_status["error"] = str(e)

            status["config_files"].append(file_status)

        return status

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
            "Commands and exit codes are logged automatically",
            "Use 'log_with_output <command>' to capture command output",
            "Use 'aixterm_enable_full_logging' for experimental full output capture",
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
            "Use 'log_with_output <cmd>' for commands that need output capture",
            "If shell becomes unresponsive, check for hanging tee processes",
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
