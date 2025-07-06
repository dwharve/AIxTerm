"""Directory and file operations for terminal context."""

from pathlib import Path
from typing import Any, Dict, List


class DirectoryHandler:
    """Handles directory and file operations for context management."""

    def __init__(
        self, config_manager: Any, logger: Any, token_manager: Any = None
    ) -> None:
        """Initialize directory handler.

        Args:
            config_manager: Configuration manager instance
            logger: Logger instance
            token_manager: Token manager for counting tokens
        """
        self.config = config_manager
        self.logger = logger
        self.token_manager = token_manager

    def get_directory_context(self) -> str:
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

    def get_file_contexts(
        self,
        file_paths: List[str],
        max_file_tokens: int = 1000,
        max_total_tokens: int = 3000,
    ) -> str:
        """Get content from multiple files to use as context with token-aware limits.

        Args:
            file_paths: List of file paths to read
            max_file_tokens: Maximum tokens per individual file (default: 1000)
            max_total_tokens: Maximum total tokens for all file content (default: 3000)

        Returns:
            Formatted string containing file contents
        """
        if not file_paths:
            return ""

        # If no token manager is available, fall back to byte limits
        if not self.token_manager:
            return self._get_file_contexts_bytes_fallback(file_paths)

        file_contents = []
        total_tokens_used = 0
        model_name = self.config.get("model", "")

        for file_path in file_paths:
            try:
                path = Path(file_path)
                if not path.exists():
                    self.logger.warning(f"File not found: {file_path}")
                    continue

                if not path.is_file():
                    self.logger.warning(f"Not a file: {file_path}")
                    continue

                # Read file content with size limit to avoid tiktoken performance issues
                max_content_bytes = min(
                    100000, max_file_tokens * 4
                )  # Rough estimate: 4 chars per token
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read(max_content_bytes)
                except UnicodeDecodeError:
                    # Try binary files with limited content
                    try:
                        with open(path, "rb") as f:
                            raw_content = f.read(5000)  # First 5KB for binary files
                            content = (
                                f"[Binary file - first 5KB shown]\n{raw_content!r}"
                            )
                    except Exception as e:
                        content = f"[Unable to read binary file: {e}]"
                except Exception as e:
                    # Handle other encoding issues
                    try:
                        with open(path, "r", encoding="latin1") as f:
                            content = f.read(5000)
                            content = (
                                "[File with encoding issues - first 5KB shown]\n"
                                f"{content}"
                            )
                    except Exception:
                        content = f"[Unable to read file: {e}]"

                # Apply token limit to individual file content
                if content.strip():
                    content = self.token_manager.apply_token_limit(
                        content, max_file_tokens, model_name
                    )

                # Calculate tokens for this file entry
                relative_path = str(path.resolve())
                file_entry = f"--- File: {relative_path} ---\n{content}"
                entry_tokens = self.token_manager.estimate_tokens(file_entry)

                # Check if adding this file would exceed total token limit
                if total_tokens_used + entry_tokens > max_total_tokens:
                    remaining_tokens = max_total_tokens - total_tokens_used
                    if (
                        remaining_tokens > 100
                    ):  # Only include if we have meaningful space
                        # Truncate the content to fit remaining space
                        header = f"--- File: {relative_path} ---\n"
                        header_tokens = self.token_manager.estimate_tokens(header)
                        content_tokens_available = remaining_tokens - header_tokens

                        if content_tokens_available > 50:  # Minimum useful content
                            content = self.token_manager.apply_token_limit(
                                content, content_tokens_available, model_name
                            )
                            file_entry = header + content
                            file_contents.append(file_entry)
                            total_tokens_used += self.token_manager.estimate_tokens(
                                file_entry
                            )

                    self.logger.warning(
                        f"Total file content token limit reached "
                        f"({max_total_tokens}), stopping at {len(file_contents)} files"
                    )
                    break

                # Add to collection
                file_contents.append(file_entry)
                total_tokens_used += entry_tokens

                self.logger.debug(
                    f"Added file {relative_path}: {entry_tokens} tokens "
                    f"(total: {total_tokens_used}/{max_total_tokens})"
                )

            except Exception as e:
                self.logger.error(f"Error reading file {file_path}: {e}")
                continue

        if not file_contents:
            return ""

        # Format the combined content
        header = (
            f"\n--- File Context ({len(file_contents)} file(s), "
            f"~{total_tokens_used} tokens) ---\n"
        )
        footer = "\n--- End File Context ---\n"

        return header + "\n\n".join(file_contents) + footer

    def _get_file_contexts_bytes_fallback(self, file_paths: List[str]) -> str:
        """Fallback method using byte limits when token manager is not available.

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
