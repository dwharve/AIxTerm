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

    def get_active_session_logs(self) -> List[Path]:
        """Get log files from currently active TTY sessions.

        Returns:
            List of log file paths from active sessions
        """
        try:
            active_ttys = self._get_active_ttys()
            active_logs = []

            for log_file in Path.home().glob(".aixterm_log.*"):
                tty_name = self._extract_tty_from_log_path(log_file)
                if tty_name and tty_name in active_ttys:
                    active_logs.append(log_file)

            self.logger.debug(f"Found {len(active_logs)} logs from active sessions")
            return active_logs

        except Exception as e:
            self.logger.error(f"Error getting active session logs: {e}")
            # Fallback to current TTY logs
            return self.get_tty_specific_logs()

    def prioritize_logs_by_activity(self, logs: List[Path]) -> List[Path]:
        """Prioritize log files with active sessions first.

        Args:
            logs: List of log file paths

        Returns:
            Sorted list with active session logs first
        """
        try:
            active_ttys = self._get_active_ttys()
            active_logs = []
            inactive_logs = []

            for log_file in logs:
                tty_name = self._extract_tty_from_log_path(log_file)
                if tty_name and tty_name in active_ttys:
                    active_logs.append(log_file)
                else:
                    inactive_logs.append(log_file)

            # Sort each group by modification time (most recent first)
            active_logs.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            inactive_logs.sort(key=lambda f: f.stat().st_mtime, reverse=True)

            # Return active logs first, then inactive
            return active_logs + inactive_logs

        except Exception as e:
            self.logger.error(f"Error prioritizing logs: {e}")
            # Fallback to simple time-based sorting
            return sorted(logs, key=lambda f: f.stat().st_mtime, reverse=True)

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
        smart_summarize: bool,
    ) -> str:
        """Read and intelligently process log file content.

        Args:
            log_path: Path to log file
            max_tokens: Maximum number of tokens to include
            model_name: Name of the model for tokenization
            smart_summarize: Whether to apply intelligent summarization

        Returns:
            Processed log content
        """
        try:
            # Read the full log
            with open(log_path, "r", encoding="utf-8") as f:
                full_text = f.read()

            if not full_text.strip():
                return ""

            # If smart summarization is disabled, use the old method
            if not smart_summarize:
                return self._read_and_truncate_log(log_path, max_tokens, model_name)

            # Apply intelligent processing
            processed_content = self._intelligently_summarize_log(
                full_text, max_tokens, model_name
            )
            return processed_content

        except Exception as e:
            self.logger.error(f"Error processing log file: {e}")
            return f"Error reading log: {e}"

    def _intelligently_summarize_log(
        self, content: str, max_tokens: int, model_name: str
    ) -> str:
        """Apply intelligent summarization to log content.

        Args:
            content: Full log content
            max_tokens: Token limit
            model_name: Model name for tokenization

        Returns:
            Intelligently summarized content
        """
        lines = content.strip().split("\n")
        if not lines:
            return ""

        # Categorize content
        commands = []
        errors = []
        current_command = None
        current_output: List[str] = []

        for line in lines:
            if line.startswith("$ "):
                # Save previous command and output
                if current_command and current_output:
                    commands.append((current_command, "\n".join(current_output)))

                current_command = line[2:]  # Remove '$ '
                current_output = []
            else:
                if "error" in line.lower() or "failed" in line.lower():
                    errors.append(line)
                current_output.append(line)

        # Save last command
        if current_command and current_output:
            commands.append((current_command, "\n".join(current_output)))

        # Build intelligent summary
        summary_parts = []

        # Always include recent errors
        if errors:
            recent_errors = errors[-3:]  # Last 3 errors
            summary_parts.append("Recent errors/failures:")
            summary_parts.extend(f"  {error}" for error in recent_errors)

        # Include most recent commands with their outputs
        recent_commands = commands[-5:]  # Last 5 commands
        if recent_commands:
            summary_parts.append("\nRecent commands:")
            for cmd, output in recent_commands:
                summary_parts.append(f"$ {cmd}")
                # Truncate long outputs
                if len(output) > 200:
                    summary_parts.append(f"{output[:200]}...")
                else:
                    summary_parts.append(output)

        # If we have many commands, add a summary
        if len(commands) > 5:
            unique_commands = list(set(cmd for cmd, _ in commands))
            summary_parts.insert(
                0,
                (
                    f"Session summary: {len(commands)} commands executed "
                    f"including: {', '.join(unique_commands[-10:])}"
                ),
            )

        result = "\n".join(summary_parts)

        # Apply token-based truncation if still too long
        return self._apply_token_limit(result, max_tokens, model_name)

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

            # Keep log file manageable
            max_lines = 1000
            if len(lines) > max_lines:
                with open(log_path, "w", encoding="utf-8") as fw:
                    fw.writelines(lines[-max_lines:])
                lines = lines[-max_lines:]

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

            # Skip empty lines and terminal formatting
            if (
                not line
                or line.startswith("[")
                or line.startswith("┌─")
                or line.startswith("└─")
            ):
                i += 1
                continue

            # Detect AI assistant queries (ai or aixterm commands)
            if line.startswith("$ ai ") or line.startswith("$ aixterm "):
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
                if line.startswith("$ ai "):
                    query_part = line[5:].strip()  # Remove "$ ai "
                elif line.startswith("$ aixterm "):
                    query_part = line[9:].strip()  # Remove "$ aixterm "
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
                if line.startswith("$ "):
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

    def get_terminal_context_without_conversations(self, log_content: str) -> str:
        """Extract terminal context excluding AI conversations.

        This provides command outputs, system information, and user commands
        but excludes AI assistant conversations to avoid duplication with
        the structured conversation history.

        Args:
            log_content: Raw terminal log content

        Returns:
            Clean terminal context without AI conversations
        """
        lines = log_content.split("\n")
        context_lines = []
        skip_until_next_command = False

        for line in lines:
            stripped = line.strip()

            # Skip empty lines and terminal formatting
            if (
                not stripped
                or stripped.startswith("[")
                or stripped.startswith("┌─")
                or stripped.startswith("└─")
            ):
                continue

            # Skip AI/aixterm commands and their responses
            if stripped.startswith("$ ai ") or stripped.startswith("$ aixterm "):
                skip_until_next_command = True
                continue

            # Check if we should stop skipping
            if skip_until_next_command:
                # Stop skipping when we hit a regular command (not AI-related)
                if stripped.startswith("$ ") and not any(
                    ai_cmd in stripped for ai_cmd in ["$ ai ", "$ aixterm "]
                ):
                    skip_until_next_command = False
                    context_lines.append(line)
                else:
                    # Still skipping AI-related content
                    continue
            else:
                # Regular terminal content (commands, outputs, system info)
                context_lines.append(line)

        return "\n".join(context_lines).strip()

    def clear_session_context(self) -> bool:
        """Clear the context for the current terminal session.

        Returns:
            True if a log file was found and cleared, False otherwise
        """
        try:
            log_file = self.find_log_file()
            if log_file and log_file.exists():
                # Remove the log file to clear the session context
                log_file.unlink()
                self.logger.info(f"Cleared session context: {log_file}")
                return True
            else:
                self.logger.debug("No active session log file found to clear")
                return False
        except Exception as e:
            self.logger.error(f"Error clearing session context: {e}")
            return False
