"""Directory and file operations for terminal context."""

from pathlib import Path
from typing import Any, Dict, List


class DirectoryHandler:
    """Handles directory and file operations for context management."""

    def __init__(self, config_manager: Any, logger: Any) -> None:
        """Initialize directory handler.

        Args:
            config_manager: Configuration manager instance
            logger: Logger instance
        """
        self.config = config_manager
        self.logger = logger

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
