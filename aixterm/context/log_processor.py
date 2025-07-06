"""Log processing and conversation history management."""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


class LogProcessor:
    """Handles log file processing and conversation history."""

    def __init__(self, config_manager: Any, logger: Any) -> None:
        """Initialize log processor.

        Args:
            config_manager: Configuration manager instance
            logger: Logger instance
        """
        self.config = config_manager
        self.logger = logger

    def find_log_file(self) -> Optional[Path]:
        """Find the appropriate log file for the current terminal session.

        Returns:
            Path to log file or None if not found
        """
        # First, check if we're in a script session with an active log file
        active_log_env = os.environ.get("_AIXTERM_LOG_FILE")
        if active_log_env:
            active_log_path = Path(active_log_env)
            if active_log_path.exists():
                self.logger.debug(f"Using active session log file: {active_log_path}")
                return active_log_path

        current_tty = self._get_current_tty()
        if current_tty:
            # Strict TTY matching - only use logs from the exact same TTY
            expected_log = Path.home() / f".aixterm_log.{current_tty}"
            if expected_log.exists():
                self.logger.debug(f"Using TTY-matched log file: {expected_log}")
                return expected_log
            else:
                self.logger.debug(f"No log file found for current TTY: {current_tty}")
                return None
        else:
            # TTY not available - fallback to most recent log but warn about it
            self.logger.warning(
                "TTY not available, using most recent log file. "
                "Context may be from different session."
            )
            candidates = sorted(
                Path.home().glob(".aixterm_log.*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            return candidates[0] if candidates else None

    def _get_current_tty(self) -> Optional[str]:
        """Get the current TTY name for log file matching.

        Returns:
            TTY name string or None if not available
        """
        try:
            # Try multiple methods to get TTY
            tty_path = None

            # Method 1: From stdin
            if hasattr(os, "ttyname") and hasattr(sys.stdin, "fileno"):
                try:
                    tty_path = os.ttyname(sys.stdin.fileno())
                except (OSError, AttributeError):
                    pass

            # Method 2: From stdout if stdin failed
            if (
                not tty_path
                and hasattr(os, "ttyname")
                and hasattr(sys.stdout, "fileno")
            ):
                try:
                    tty_path = os.ttyname(sys.stdout.fileno())
                except (OSError, AttributeError):
                    pass

            # Method 3: From stderr if others failed
            if (
                not tty_path
                and hasattr(os, "ttyname")
                and hasattr(sys.stderr, "fileno")
            ):
                try:
                    tty_path = os.ttyname(sys.stderr.fileno())
                except (OSError, AttributeError):
                    pass

            # Method 4: From /proc/self/fd/0 on Linux
            if not tty_path:
                try:
                    import subprocess as sp

                    result = sp.run(["tty"], capture_output=True, text=True, timeout=1)
                    if result.returncode == 0:
                        tty_path = result.stdout.strip()
                except (
                    sp.SubprocessError,
                    FileNotFoundError,
                    sp.TimeoutExpired,
                ):
                    pass

            if tty_path:
                # Normalize TTY name for consistent log file naming
                tty_name = tty_path.replace("/dev/", "").replace("/", "-")
                self.logger.debug(f"Detected TTY: {tty_path} -> {tty_name}")
                return tty_name

        except Exception as e:
            self.logger.debug(f"Error detecting TTY: {e}")

        return None

    def validate_log_tty_match(self, log_path: Path) -> bool:
        """Validate that a log file belongs to the current TTY session.

        Args:
            log_path: Path to the log file to validate

        Returns:
            True if the log file matches current TTY, False otherwise
        """
        current_tty = self._get_current_tty()
        if not current_tty:
            # If we can't detect TTY, allow any log (backward compatibility)
            self.logger.debug("Cannot detect current TTY, allowing log file")
            return True

        # Extract TTY from log file name
        log_filename = log_path.name
        if log_filename.startswith(".aixterm_log."):
            log_tty = log_filename[13:]  # Remove ".aixterm_log." prefix
            if log_tty == current_tty:
                self.logger.debug(f"Log file TTY matches current TTY: {current_tty}")
                return True
            else:
                self.logger.warning(
                    f"Log file TTY mismatch: log={log_tty}, current={current_tty}"
                )
                return False
        else:
            self.logger.warning(f"Invalid log file format: {log_filename}")
            return False

    def get_tty_specific_logs(self) -> List[Path]:
        """Get all log files that match the current TTY.

        Returns:
            List of log file paths for the current TTY only
        """
        current_tty = self._get_current_tty()
        if not current_tty:
            # Return all logs if TTY detection fails
            return list(Path.home().glob(".aixterm_log.*"))

        # Only return logs matching current TTY
        tty_log_pattern = f".aixterm_log.{current_tty}"
        matching_logs = list(Path.home().glob(tty_log_pattern))

        self.logger.debug(f"Found {len(matching_logs)} logs for TTY {current_tty}")
        return matching_logs

    def _get_active_ttys(self) -> List[str]:
        """Get list of currently active TTY sessions.

        Returns:
            List of active TTY names
        """
        active_ttys = []
        try:
            import subprocess

            # Use 'who' command to get active TTYs
            result = subprocess.run(["who"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            tty_name = parts[1]
                            # Normalize TTY name (remove /dev/ prefix, replace / with -)
                            normalized_tty = tty_name.replace("/dev/", "").replace(
                                "/", "-"
                            )
                            active_ttys.append(normalized_tty)
        except Exception as e:
            self.logger.warning(f"Could not determine active TTYs: {e}")

        return active_ttys

    def _extract_tty_from_log_path(self, log_path: Path) -> Optional[str]:
        """Extract TTY name from log file path.

        Args:
            log_path: Path to log file

        Returns:
            TTY name or None if not a TTY-based log
        """
        filename = log_path.name
        if filename.startswith(".aixterm_log."):
            tty_name = filename[13:]  # Remove ".aixterm_log." prefix
            return tty_name if tty_name != "default" else None
        return None

    def read_and_process_log(
        self,
        log_path: Path,
        max_tokens: int,
        model_name: str,
        smart_summarize: bool = True,
    ) -> str:
        """Read and intelligently process log file content with tiered summarization.

        Args:
            log_path: Path to log file
            max_tokens: Maximum number of tokens to include
            model_name: Name of the model for tokenization
            smart_summarize: Whether to apply intelligent summarization
                (always True for optimal results)

        Returns:
            Processed log content with tiered detail levels
        """
        try:
            # Apply file size management BEFORE reading to avoid processing huge files
            self._manage_log_file_size(log_path)

            # Read the managed (truncated) log
            with open(log_path, "r", encoding="utf-8") as f:
                full_text = f.read()

            if not full_text.strip():
                return "No terminal activity recorded yet."

            # Always use intelligent tiered summarization for optimal context management
            if smart_summarize:
                return self._intelligently_summarize_log(
                    full_text, max_tokens, model_name
                )
            else:
                # Fallback to simple token-based truncation only if explicitly requested
                return self._apply_token_limit(full_text, max_tokens, model_name)

        except Exception as e:
            self.logger.error(f"Error processing log file: {e}")
            return f"Error reading log: {e}"

    def _intelligently_summarize_log(
        self, content: str, max_tokens: int, model_name: str
    ) -> str:
        """Apply tiered intelligent summarization to log content.

        Recent data gets full detail, older data gets increasingly
        generalized to optimize context size while preserving important
        information.

        Args:
            content: Full log content
            max_tokens: Token limit
            model_name: Model name for tokenization

        Returns:
            Intelligently summarized content with tiered detail levels
        """
        lines = content.strip().split("\n")
        if not lines:
            return ""

        # Parse all commands and categorize content
        commands, errors = self._parse_commands_and_errors(lines)

        if not commands:
            return "No commands found in session."

        # Apply tiered summarization based on recency
        summary_parts = self._build_tiered_summary(commands, errors)

        result = "\n".join(summary_parts)

        # Apply token-based truncation if still too long
        return self._apply_token_limit(result, max_tokens, model_name)

    def _parse_commands_and_errors(
        self, lines: List[str]
    ) -> tuple[List[tuple[str, str]], List[str]]:
        """Parse log lines to extract commands and errors.

        Args:
            lines: Log file lines

        Returns:
            Tuple of (commands, errors) where commands is list of
            (command, output) tuples
        """
        commands = []
        errors = []
        current_command = None
        current_output: List[str] = []

        for line in lines:
            # Clean ANSI escape sequences for parsing
            clean_line = self._clean_ansi_sequences(line)

            # Handle both traditional format ($ command) and
            # script format (└──╼ $command)
            command_match = None
            if clean_line.startswith("$ "):
                command_match = clean_line[2:]  # Remove '$ '
            elif "└──╼ $" in clean_line:
                # Extract command from script format: └──╼ $command
                dollar_pos = clean_line.find("└──╼ $")
                if dollar_pos != -1:
                    command_match = clean_line[dollar_pos + 6 :]  # Remove '└──╼ $'

            if command_match:
                # Save previous command and output
                if current_command and current_output:
                    commands.append((current_command, "\n".join(current_output)))

                current_command = command_match
                current_output = []
            else:
                if "error" in line.lower() or "failed" in line.lower():
                    errors.append(line)
                current_output.append(line)

        # Save last command
        if current_command and current_output:
            commands.append((current_command, "\n".join(current_output)))

        return commands, errors

    def _build_tiered_summary(
        self, commands: List[tuple[str, str]], errors: List[str]
    ) -> List[str]:
        """Build tiered summary with different detail levels based on recency.

        Args:
            commands: List of (command, output) tuples
            errors: List of error messages

        Returns:
            List of summary parts
        """
        summary_parts = []
        total_commands = len(commands)

        if total_commands == 0:
            return ["No commands executed in this session."]

        # Calculate tier boundaries
        recent_count = max(1, int(total_commands * 0.2))  # Last 20% (min 1)
        middle_count = max(1, int(total_commands * 0.3))  # Next 30% (min 1)

        # Split commands into tiers
        recent_commands = commands[-recent_count:]
        middle_commands = (
            commands[-(recent_count + middle_count) : -recent_count]
            if recent_count < total_commands
            else []
        )
        older_commands = (
            commands[: -(recent_count + middle_count)]
            if (recent_count + middle_count) < total_commands
            else []
        )

        # Add session overview
        if total_commands > 10:
            unique_commands = list(set(cmd for cmd, _ in commands))
            summary_parts.append(
                f"Session overview: {total_commands} commands executed "
                f"including: {', '.join(unique_commands[-15:])}"
            )

        # Add recent errors (always high priority)
        if errors:
            recent_errors = errors[-3:]  # Last 3 errors
            summary_parts.append("\n🔴 Recent errors/failures:")
            summary_parts.extend(
                f"  {error[:100]}..." if len(error) > 100 else f"  {error}"
                for error in recent_errors
            )

        # Tier 1: Recent commands (full detail)
        if recent_commands:
            summary_parts.append(f"\n📋 Recent commands (last {len(recent_commands)}):")
            for cmd, output in recent_commands:
                summary_parts.append(f"$ {cmd}")
                if output.strip():
                    # Full output for recent commands, but reasonable limit
                    if len(output) > 200:
                        summary_parts.append(f"{output[:200]}...")
                    else:
                        summary_parts.append(output)

        # Tier 2: Middle commands (moderate detail)
        if middle_commands:
            summary_parts.append(
                f"\n📝 Earlier commands (previous {len(middle_commands)}):"
            )
            for cmd, output in middle_commands:
                summary_parts.append(f"$ {cmd}")
                if output.strip():
                    # Truncated output for middle commands
                    if len(output) > 80:
                        summary_parts.append(f"{output[:80]}...")
                    else:
                        summary_parts.append(output)

        # Tier 3: Older commands (summary only)
        if older_commands:
            older_cmd_names = [cmd for cmd, _ in older_commands]
            # Group similar commands
            cmd_counts: Dict[str, int] = {}
            for cmd in older_cmd_names:
                # Simplify command for grouping (remove arguments)
                base_cmd = cmd.split()[0] if cmd else "unknown"
                cmd_counts[base_cmd] = cmd_counts.get(base_cmd, 0) + 1

            summary_parts.append(
                f"\n📊 Session history ({len(older_commands)} earlier commands):"
            )
            for cmd, count in sorted(
                cmd_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]:
                if count > 1:
                    summary_parts.append(f"  {cmd}: {count} times")
                else:
                    summary_parts.append(f"  {cmd}")

        return summary_parts

    def _apply_token_limit(self, text: str, max_tokens: int, model_name: str) -> str:
        """Apply token limit to text content.

        Args:
            text: Text to limit
            max_tokens: Maximum tokens
            model_name: Model name for tokenization

        Returns:
            Token-limited text
        """
        import tiktoken

        if not text.strip():
            return text

        # Get appropriate encoder
        if model_name and model_name.startswith(("gpt-", "text-")):
            try:
                encoder = tiktoken.encoding_for_model(model_name)
            except KeyError:
                encoder = tiktoken.get_encoding("cl100k_base")
        else:
            encoder = tiktoken.get_encoding("cl100k_base")

        tokens = encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text

        # Truncate to token limit (keep the end for recency)
        truncated_tokens = tokens[-max_tokens:]
        return encoder.decode(truncated_tokens)

    def _read_and_truncate_log(
        self, log_path: Path, max_tokens: int, model_name: str
    ) -> str:
        """Read log file and truncate to token limit with proper tokenization.

        Args:
            log_path: Path to log file
            max_tokens: Maximum number of tokens to include
            model_name: Name of the model for tokenization

        Returns:
            Truncated log content
        """
        try:
            with open(log_path, "r", errors="ignore", encoding="utf-8") as f:
                lines = f.readlines()

            full_text = "".join(lines)

            # Use proper tokenization
            import tiktoken

            if model_name and model_name.startswith(("gpt-", "text-")):
                try:
                    encoder = tiktoken.encoding_for_model(model_name)
                except KeyError:
                    encoder = tiktoken.get_encoding("cl100k_base")
            else:
                encoder = tiktoken.get_encoding("cl100k_base")

            tokens = encoder.encode(full_text)
            if len(tokens) <= max_tokens:
                return full_text.strip()

            # Truncate to token limit
            truncated_tokens = tokens[-max_tokens:]
            return encoder.decode(truncated_tokens).strip()

        except Exception as e:
            self.logger.error(f"Error reading log file {log_path}: {e}")
            return f"Error reading log file: {e}"

    def get_log_files(self) -> List[Path]:
        """Get list of all bash AI log files for the current TTY.

        Returns:
            List of log file paths (TTY-specific when possible)
        """
        # Use TTY-specific logs when available for better isolation
        return self.get_tty_specific_logs()

    def create_log_entry(self, command: str, result: str = "") -> None:
        """Create a log entry for a command.

        Args:
            command: Command that was executed
            result: Result or output of the command
        """
        try:
            log_path = self._get_current_log_file()
            timestamp = self._get_timestamp()

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"# Log entry at {timestamp}\n")
                f.write(f"$ {command}\n")
                if result:
                    f.write(f"{result}\n")
        except Exception as e:
            self.logger.error(f"Error writing to log file: {e}")

    def _get_timestamp(self) -> str:
        """Get current timestamp for log entries.

        Returns:
            Formatted timestamp string
        """
        import datetime

        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _get_current_log_file(self) -> Path:
        """Get the current log file path.

        Returns:
            Path to current log file
        """
        current_tty = self._get_current_tty()
        if current_tty:
            return Path.home() / f".aixterm_log.{current_tty}"
        else:
            # Use generic log file when TTY is not available
            return Path.home() / ".aixterm_log.default"

    def parse_conversation_history(self, log_content: str) -> List[Dict[str, str]]:
        """Parse terminal log content into structured conversation history.

        Extracts only the actual AI assistant conversations, not regular
        terminal commands and their outputs.

        Args:
            log_content: Raw terminal log content

        Returns:
            List of conversation messages with role and content
        """
        messages = []
        lines = log_content.split("\n")
        current_ai_response: List[str] = []
        collecting_response = False

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            # Clean ANSI escape sequences for parsing
            clean_line = self._clean_ansi_sequences(line)

            # Skip empty lines and terminal formatting
            if (
                not clean_line
                or clean_line.startswith("[")
                or clean_line.startswith("┌─")
                or clean_line.startswith("└─")
            ):
                i += 1
                continue

            # Detect AI assistant queries (ai or aixterm commands)
            # Handle both traditional format ($ command) and
            # script format (└──╼ $command)
            ai_command_match = None
            if clean_line.startswith("$ ai ") or clean_line.startswith("$ aixterm "):
                ai_command_match = clean_line
            elif "└──╼ $ai " in clean_line or "└──╼ $aixterm " in clean_line:
                # Extract command from script format
                dollar_pos = clean_line.find("└──╼ $")
                if dollar_pos != -1:
                    ai_command_match = (
                        "$" + clean_line[dollar_pos + 6 :]
                    )  # Convert to standard format

            if ai_command_match:
                # Save any ongoing AI response first
                if current_ai_response and collecting_response:
                    ai_content = "\n".join(current_ai_response).strip()
                    if ai_content:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": ai_content,
                            }
                        )
                    current_ai_response = []
                    collecting_response = False

                # Extract and save the user query
                if ai_command_match.startswith("$ ai "):
                    query_part = ai_command_match[5:].strip()  # Remove "$ ai "
                elif ai_command_match.startswith("$ aixterm "):
                    query_part = ai_command_match[9:].strip()  # Remove "$ aixterm "
                else:
                    query_part = ""

                if query_part:
                    query = query_part.strip("\"'")  # Remove quotes
                    messages.append(
                        {
                            "role": "user",
                            "content": query,
                        }
                    )
                    collecting_response = True  # Start collecting the response
                    current_ai_response = []

            # If we're collecting a response, continue until we hit another command
            elif collecting_response:
                # Stop collecting if we hit another command
                # (traditional or script format)
                is_command = clean_line.startswith("$ ") or "└──╼ $" in clean_line
                if is_command:
                    # Save the collected response
                    if current_ai_response:
                        ai_content = "\n".join(current_ai_response).strip()
                        if ai_content:
                            messages.append(
                                {
                                    "role": "assistant",
                                    "content": ai_content,
                                }
                            )
                        current_ai_response = []
                    collecting_response = False

                    # Check if this is another AI command to continue processing
                    if line.startswith("$ ai ") or line.startswith("$ aixterm "):
                        i -= 1  # Reprocess this line
                else:
                    # Include content as part of AI response, skip system messages
                    if not any(
                        skip in line
                        for skip in [
                            "Error communicating",
                            "Operation cancelled",
                        ]
                    ):
                        current_ai_response.append(line)

            i += 1

        # Handle any remaining AI response
        if current_ai_response and collecting_response:
            ai_content = "\n".join(current_ai_response).strip()
            if ai_content:
                messages.append(
                    {
                        "role": "assistant",
                        "content": ai_content,
                    }
                )

        return messages

    def clear_session_context(self) -> bool:
        """Clear the context for the current terminal session.

        Truncates the log file instead of deleting it to keep the shell
        integration working properly.

        Returns:
            True if a log file was found and cleared, False otherwise
        """
        try:
            log_file = self.find_log_file()
            if log_file and log_file.exists():
                # Truncate the log file to clear the session context
                # This keeps the file intact so shell integration continues working
                with open(log_file, "w", encoding="utf-8") as f:
                    f.write("")  # Clear the file contents
                self.logger.info(f"Cleared session context: {log_file}")
                return True
            else:
                self.logger.debug("No active session log file found to clear")
                return False
        except Exception as e:
            self.logger.error(f"Error clearing session context: {e}")
            return False

    def _clean_ansi_sequences(self, text: str) -> str:
        """Remove ANSI escape sequences from text.

        Args:
            text: Text potentially containing ANSI escape sequences

        Returns:
            Text with ANSI sequences removed
        """
        import re

        # Pattern to match ANSI escape sequences
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    def _manage_log_file_size(self, log_path: Path) -> None:
        """Manage log file size by truncating if it gets too large.

        Args:
            log_path: Path to the log file to manage
        """
        try:
            max_lines = 300  # Further reduced from 500 to prevent token
            # overflow

            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if len(lines) > max_lines:
                self.logger.debug(
                    f"Truncating log file {log_path} from {len(lines)} "
                    f"to {max_lines} lines"
                )

                # Keep the last max_lines
                with open(log_path, "w", encoding="utf-8") as fw:
                    fw.writelines(lines[-max_lines:])

        except Exception as e:
            self.logger.warning(f"Could not manage log file size for {log_path}: {e}")
