"""Terminal context and log file management."""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import tiktoken

from .utils import get_logger


class TerminalContext:
    """Manages terminal context and log file operations."""

    def __init__(self, config_manager: Any) -> None:
        """Initialize terminal context manager.

        Args:
            config_manager: AIxTermConfig instance
        """
        self.config = config_manager
        self.logger = get_logger(__name__)

    def get_terminal_context(
        self, include_files: bool = True, smart_summarize: bool = True
    ) -> str:
        """Retrieve intelligent terminal context with optional summarization.

        Args:
            include_files: Whether to include file listings for context
            smart_summarize: Whether to apply intelligent summarization

        Returns:
            Formatted terminal context string
        """
        max_tokens = self.config.get_available_context_size()
        context_parts = []

        # Get current working directory info
        cwd = os.getcwd()
        context_parts.append(f"Current working directory: {cwd}")

        # Add intelligent directory context if enabled
        if include_files:
            dir_context = self._get_directory_context()
            if dir_context:
                context_parts.append(dir_context)

        try:
            log_path = self._find_log_file()
            if log_path and log_path.exists():
                log_content = self._read_and_process_log(
                    log_path,
                    max_tokens,
                    self.config.get("model", ""),
                    smart_summarize,
                )
                if log_content:
                    context_parts.append(f"Recent terminal output:\n{log_content}")
            else:
                context_parts.append("No recent terminal history available.")
        except Exception as e:
            self.logger.error(f"Error retrieving session log: {e}")
            context_parts.append(f"Error retrieving session log: {e}")

        return "\n\n".join(context_parts)

    def _get_directory_context(self) -> str:
        """Get intelligent context about the current directory.

        Returns:
            Directory context string
        """
        try:
            cwd = Path.cwd()
            context_parts = []

            # Count different file types
            file_counts: Dict[str, int] = {}
            important_files = []

            for item in cwd.iterdir():
                if item.is_file():
                    suffix = item.suffix.lower() or "no_extension"
                    file_counts[suffix] = file_counts.get(suffix, 0) + 1

                    # Identify important files
                    important_names = [
                        "readme.md",
                        "readme.txt",
                        "readme.rst",
                        "package.json",
                        "requirements.txt",
                        "pyproject.toml",
                        "dockerfile",
                        "docker-compose.yml",
                        "makefile",
                        "setup.py",
                        "setup.cfg",
                        ".gitignore",
                        "license",
                    ]
                    if item.name.lower() in important_names:
                        important_files.append(item.name)

            # Summarize file types
            if file_counts:
                file_summary = ", ".join(
                    [f"{count} {ext}" for ext, count in sorted(file_counts.items())]
                )
                context_parts.append(f"Files in directory: {file_summary}")

            # List important files
            if important_files:
                context_parts.append(f"Key files: {', '.join(important_files)}")

            # Check for common project indicators
            project_type = self._detect_project_type(cwd)
            if project_type:
                context_parts.append(f"Project type: {project_type}")

            return "\n".join(context_parts) if context_parts else ""

        except Exception as e:
            self.logger.debug(f"Error getting directory context: {e}")
            return ""

    def _detect_project_type(self, path: Path) -> str:
        """Detect the type of project in the given path.

        Args:
            path: Path to analyze

        Returns:
            Project type description
        """
        indicators = {
            "Python": [
                "requirements.txt",
                "setup.py",
                "pyproject.toml",
                "__pycache__",
            ],
            "Node.js": ["package.json", "node_modules", "yarn.lock"],
            "Java": ["pom.xml", "build.gradle", "src/main/java"],
            "C/C++": ["makefile", "CMakeLists.txt", "*.c", "*.cpp"],
            "Docker": ["dockerfile", "docker-compose.yml"],
            "Git": [".git"],
            "Web": ["index.html", "css", "js"],
        }

        detected = []
        for project_type, files in indicators.items():
            for indicator in files:
                if "*" in indicator:
                    # Handle glob patterns
                    if list(path.glob(indicator)):
                        detected.append(project_type)
                        break
                elif (path / indicator).exists():
                    detected.append(project_type)
                    break

        return ", ".join(detected) if detected else ""

    def _read_and_process_log(
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

    def _find_log_file(self) -> Optional[Path]:
        """Find the appropriate log file for the current terminal session.

        Returns:
            Path to log file or None if not found
        """
        try:
            # Try to get the current TTY for Linux/Unix systems
            if hasattr(os, "ttyname") and hasattr(sys.stdin, "fileno"):
                tty_path = os.ttyname(sys.stdin.fileno())
                tty_name = tty_path.replace("/dev/", "").replace("/", "-")
                expected_log = Path.home() / f".aixterm_log.{tty_name}"

                if expected_log.exists():
                    return expected_log
        except (OSError, AttributeError):
            # TTY not available (e.g., running in IDE, Windows, etc.)
            self.logger.debug("TTY not available, using most recent log")

        # Use most recent log file when TTY is not available
        candidates = sorted(
            Path.home().glob(".aixterm_log.*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

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
        """Get list of all bash AI log files.

        Returns:
            List of log file paths
        """
        return list(Path.home().glob(".aixterm_log.*"))

    def create_log_entry(self, command: str, result: str = "") -> None:
        """Create a log entry for a command.

        Args:
            command: Command that was executed
            result: Result or output of the command
        """
        try:
            log_path = self._get_current_log_file()
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"$ {command}\n")
                if result:
                    f.write(f"{result}\n")
        except Exception as e:
            self.logger.error(f"Error writing to log file: {e}")

    def _get_current_log_file(self) -> Path:
        """Get the current log file path.

        Returns:
            Path to current log file
        """
        try:
            if hasattr(os, "ttyname") and hasattr(sys.stdin, "fileno"):
                tty_path = os.ttyname(sys.stdin.fileno())
                tty_name = tty_path.replace("/dev/", "").replace("/", "-")
                return Path.home() / f".aixterm_log.{tty_name}"
        except (OSError, AttributeError):
            pass

        # Use generic log file when TTY is not available
        return Path.home() / ".aixterm_log.default"

    def get_file_contexts(self, file_paths: List[str]) -> str:
        """Get content from multiple files to use as context.

        Args:
            file_paths: List of file paths to read

        Returns:
            Formatted string containing file contents
        """
        if not file_paths:
            return ""

        file_contents = []
        max_file_size = 50000  # Limit individual file size
        total_content_limit = 200000  # Limit total content size

        for file_path in file_paths:
            try:
                path = Path(file_path)
                if not path.exists():
                    self.logger.warning(f"File not found: {file_path}")
                    continue

                if not path.is_file():
                    self.logger.warning(f"Not a file: {file_path}")
                    continue

                # Check file size
                if path.stat().st_size > max_file_size:
                    self.logger.warning(
                        f"File too large, will be truncated: {file_path}"
                    )

                # Read file content
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read(max_file_size)
                except UnicodeDecodeError:
                    # Try binary files with limited content
                    with open(path, "rb") as f:
                        raw_content = f.read(1000)  # First 1KB for binary files
                        content = f"[Binary file - first 1KB shown]\n{raw_content!r}"
                except Exception as e:
                    # Handle other encoding issues
                    try:
                        with open(path, "r", encoding="latin1") as f:
                            content = f.read(1000)
                            content = (
                                "[File with encoding issues - first 1KB shown]\n"
                                f"{content}"
                            )
                    except Exception:
                        content = f"[Unable to read file: {e}]"

                # Add to collection
                relative_path = str(path.resolve())
                file_contents.append(f"--- File: {relative_path} ---\n{content}")

                # Check total size limit
                current_size = sum(len(fc) for fc in file_contents)
                if current_size > total_content_limit:
                    self.logger.warning(
                        "Total file content size limit reached, stopping"
                    )
                    break

            except Exception as e:
                self.logger.error(f"Error reading file {file_path}: {e}")
                continue

        if not file_contents:
            return ""

        # Format the combined content
        header = f"\n--- File Context ({len(file_contents)} file(s)) ---\n"
        footer = "\n--- End File Context ---\n"

        return header + "\n\n".join(file_contents) + footer

    def get_optimized_context(
        self, file_contexts: Optional[List[str]] = None, query: str = ""
    ) -> str:
        """Get optimized context that efficiently uses the available context window.

        Args:
            file_contexts: List of file paths to include
            query: The user query to optimize context for

        Returns:
            Optimized context string that maximizes useful information
        """
        # Get configuration for context budget using new helper methods
        available_context = self.config.get_available_context_size()

        # Reserve space for essential parts
        system_prompt_tokens = 50  # Estimated
        query_tokens = self._estimate_tokens(query)
        available_for_context = available_context - system_prompt_tokens - query_tokens

        # Allocate context budget intelligently
        context_parts = []
        remaining_tokens = available_for_context

        # 1. Always include current directory (small, essential)
        cwd = os.getcwd()
        cwd_info = f"Current working directory: {cwd}"
        context_parts.append(cwd_info)
        remaining_tokens -= self._estimate_tokens(cwd_info)

        # 2. Directory context (project info, file structure) - 10-15% of budget
        dir_budget = min(int(available_for_context * 0.15), remaining_tokens)
        if dir_budget > 50:
            dir_context = self._get_directory_context()
            if dir_context:
                dir_context = self._apply_token_limit(
                    dir_context, dir_budget, self.config.get("model", "")
                )
                context_parts.append(dir_context)
                remaining_tokens -= self._estimate_tokens(dir_context)

        # 3. File contexts if provided - 40-60% of budget (prioritized)
        if file_contexts and remaining_tokens > 100:
            file_budget = min(int(available_for_context * 0.6), remaining_tokens)
            file_content = self.get_file_contexts(file_contexts)
            if file_content:
                file_content = self._apply_token_limit(
                    file_content, file_budget, self.config.get("model", "")
                )
                context_parts.append(file_content)
                remaining_tokens -= self._estimate_tokens(file_content)

        # 4. Terminal history - remaining budget (but at least 25% if no files)
        if remaining_tokens > 50:
            if not file_contexts:
                # If no files, give more space to terminal history
                terminal_budget = max(
                    remaining_tokens, int(available_for_context * 0.4)
                )
            else:
                terminal_budget = remaining_tokens

            try:
                log_path = self._find_log_file()
                if log_path and log_path.exists():
                    # Read raw log content
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                        f.seek(0, 2)  # Seek to end
                        file_size = f.tell()
                        read_size = min(file_size, 30000)  # Read last 30KB
                        f.seek(file_size - read_size)
                        raw_log = f.read()

                    # Get clean terminal context (without AI conversations)
                    clean_context = self._get_terminal_context_without_conversations(
                        raw_log
                    )

                    if clean_context:
                        # Apply token limit to the clean context
                        log_content = self._apply_token_limit(
                            clean_context,
                            terminal_budget,
                            self.config.get("model", ""),
                        )
                        if log_content.strip():
                            context_parts.append(
                                f"Recent terminal activity:\n{log_content}"
                            )
                    else:
                        context_parts.append("No recent terminal activity available.")
                else:
                    context_parts.append("No recent terminal activity available.")
            except Exception as e:
                self.logger.error(f"Error retrieving session log: {e}")
                context_parts.append(f"Error retrieving session log: {e}")

        final_context = "\n\n".join(context_parts)

        # Final safety check - ensure we're within budget
        final_tokens = self._estimate_tokens(final_context)
        if final_tokens > available_for_context:
            self.logger.warning(
                f"Context too large ({final_tokens} tokens), "
                f"truncating to {available_for_context}"
            )
            final_context = self._apply_token_limit(
                final_context,
                available_for_context,
                self.config.get("model", ""),
            )

        return final_context

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        import tiktoken

        model_name = self.config.get("model", "")

        # Get appropriate tokenizer
        if model_name and model_name.startswith(("gpt-", "text-")):
            try:
                encoder = tiktoken.encoding_for_model(model_name)
            except KeyError:
                encoder = tiktoken.get_encoding("cl100k_base")
        else:
            encoder = tiktoken.get_encoding("cl100k_base")

        return len(encoder.encode(text))

    def _parse_conversation_history(self, log_content: str) -> List[Dict[str, str]]:
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

    def get_conversation_history(
        self, max_tokens: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """Get structured conversation history from terminal logs.

        Args:
            max_tokens: Maximum tokens to use for conversation history

        Returns:
            List of conversation messages formatted for LLM consumption
        """
        if max_tokens is None:
            max_tokens = (
                self.config.get_available_context_size() // 3
            )  # Use 1/3 of available context

        try:
            log_path = self._find_log_file()
            if not log_path or not log_path.exists():
                return []

            # Read the recent log content
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                # Get the last portion of the log file
                f.seek(0, 2)  # Seek to end
                file_size = f.tell()

                # Read last 50KB or whole file if smaller
                read_size = min(file_size, 50000)
                f.seek(file_size - read_size)
                log_content = f.read()

            # Parse into conversation messages
            messages = self._parse_conversation_history(log_content)

            # Filter and limit messages to fit in token budget
            filtered_messages: List[Dict[str, str]] = []
            total_tokens = 0

            # Work backwards from most recent messages
            for message in reversed(messages):
                message_tokens = self._estimate_tokens(message["content"])
                if total_tokens + message_tokens <= max_tokens:
                    filtered_messages.insert(0, message)
                    total_tokens += message_tokens
                else:
                    break

            return filtered_messages

        except Exception as e:
            self.logger.error(f"Error getting conversation history: {e}")
            return []

    def _get_terminal_context_without_conversations(self, log_content: str) -> str:
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

    def optimize_tools_for_context(
        self, tools: List[Dict], query: str, available_tokens: int
    ) -> List[Dict]:
        """Intelligently optimize tools for available context space.

        Args:
            tools: List of tool definitions
            query: User query for context-aware prioritization
            available_tokens: Number of tokens available for tools

        Returns:
            Optimized list of tools that fit within available context
        """
        if not tools:
            return tools

        # Always use intelligent prioritization and token fitting
        prioritized_tools = self._prioritize_tools(tools, query)
        return self._fit_tools_to_tokens(prioritized_tools, available_tokens)

    def _prioritize_tools(self, tools: List[Dict], query: str) -> List[Dict]:
        """Prioritize tools based on relevance and utility.

        Args:
            tools: List of tool definitions
            query: User query for context-aware prioritization

        Returns:
            Tools sorted by priority (highest first)
        """
        query_lower = query.lower()

        def get_tool_priority(tool: Dict) -> int:
            """Calculate priority score for a tool."""
            function = tool.get("function", {})
            name = function.get("name", "").lower()
            description = function.get("description", "").lower()

            score = 0

            # Essential system tools (highest priority)
            essential_keywords = [
                "execute",
                "command",
                "run",
                "shell",
                "terminal",
                "system",
            ]
            if any(keyword in name for keyword in essential_keywords):
                score += 1000

            # File operations (very high priority)
            file_keywords = [
                "file",
                "read",
                "write",
                "list",
                "directory",
                "find",
                "search",
                "create",
                "delete",
                "move",
                "copy",
            ]
            if any(keyword in name for keyword in file_keywords):
                score += 800

            # Development tools (high priority)
            dev_keywords = [
                "git",
                "build",
                "compile",
                "test",
                "debug",
                "package",
                "install",
                "deploy",
            ]
            if any(keyword in name for keyword in dev_keywords):
                score += 600

            # Data processing tools (medium-high priority)
            data_keywords = [
                "parse",
                "format",
                "convert",
                "transform",
                "process",
                "analyze",
            ]
            if any(keyword in name for keyword in data_keywords):
                score += 400

            # Context-aware prioritization based on query
            query_keywords = query_lower.split()
            for keyword in query_keywords:
                if keyword in name:
                    score += 300  # Direct name match
                elif keyword in description:
                    score += 150  # Description match

            # Tool name length (shorter names often indicate core functionality)
            if len(name) <= 10:
                score += 50
            elif len(name) <= 15:
                score += 25

            # Penalize overly complex tools if we have simpler alternatives
            if len(description) > 200:
                score -= 50

            return score

        # Sort tools by priority score (descending)
        tools_with_scores = [(tool, get_tool_priority(tool)) for tool in tools]
        tools_with_scores.sort(key=lambda x: x[1], reverse=True)

        top_5_names = [
            t[0].get("function", {}).get("name", "unknown")
            for t in tools_with_scores[:5]
        ]
        self.logger.debug(f"Tool prioritization complete. Top 5 tools: {top_5_names}")

        return [tool for tool, _ in tools_with_scores]

    def _fit_tools_to_tokens(
        self, tools: List[Dict], available_tokens: int
    ) -> List[Dict]:
        """Fit tools within available token budget.

        Args:
            tools: List of prioritized tools
            available_tokens: Maximum tokens available for tools

        Returns:
            Tools that fit within token budget
        """
        if not tools:
            return tools

        # Calculate precise token usage for tools
        encoding = tiktoken.encoding_for_model("gpt-4")
        fitted_tools = []
        current_tokens = 0

        for tool in tools:
            # Calculate actual tokens for this tool
            tool_json = str(tool)
            tool_tokens = len(encoding.encode(tool_json))

            if current_tokens + tool_tokens <= available_tokens:
                fitted_tools.append(tool)
                current_tokens += tool_tokens
            else:
                # Can't fit any more tools
                break

        self.logger.debug(
            f"Fitted {len(fitted_tools)}/{len(tools)} tools in "
            f"{current_tokens}/{available_tokens} tokens"
        )
        return fitted_tools

    def get_available_tool_tokens(self, context_tokens: int) -> int:
        """Calculate how many tokens are available for tool definitions.

        Args:
            context_tokens: Tokens already used by context

        Returns:
            Number of tokens available for tools
        """
        total_context = self.config.get_total_context_size()
        response_buffer = self.config.get_response_buffer_size()
        tool_reserve_value = self.config.get_tool_tokens_reserve()
        tool_reserve: int = int(tool_reserve_value)

        # Calculate available tokens: total - response_buffer - context_used
        available = total_context - response_buffer - context_tokens

        # Use configured tool reserve, but ensure we have at least some space for tools
        tool_budget: int = min(tool_reserve, max(500, available // 2))

        self.logger.debug(
            f"Tool token budget: {tool_budget} (total: {total_context}, "
            f"response: {response_buffer}, context: {context_tokens})"
        )

        return max(0, tool_budget)
