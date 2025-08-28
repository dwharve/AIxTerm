"""
AIxTerm Service Context Manager

This module provides the context management system for the AIxTerm service,
including terminal history, file context, and project detection.
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Context manager for AIxTerm service.

    This class manages terminal history, file context, and project detection
    to provide relevant context for LLM queries.
    """

    def __init__(self, service):
        """
        Initialize the context manager.

        Args:
            service: The parent AIxTerm service.
        """
        self.service = service
        self.config = service.config.get("context", {})
        self.context_tokens = self.config.get("context_tokens", 500)

    async def get_context(
        self, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get context for a query based on the provided options.

        Args:
            options: Context options, including:
                - files: List of file paths to include in context
                - directory: Directory to analyze for context
                - project_type: Manually specified project type
                - terminal_history: Whether to include terminal history

        Returns:
            A dictionary containing context information.
        """
        if options is None:
            options = {}

        context: Dict[str, Any] = {
            "terminal_history": None,
            "files": {},
            "project_info": None,
            "directory_info": None,
        }

        # Get terminal history if requested
        if options.get("terminal_history", True):
            context["terminal_history"] = await self._get_terminal_history()

        # Get file context if specified
        files = options.get("files", [])
        if files:
            context["files"] = await self._get_file_context(files)

        # Get project info if requested
        directory = options.get("directory")
        if directory:
            context["directory_info"] = await self._get_directory_info(directory)
            context["project_info"] = await self._detect_project_type(directory)

        return context

    async def _get_terminal_history(self) -> Dict[str, Any]:
        """
        Get terminal history context.

        Returns:
            A dictionary containing terminal history information.
        """
        try:
            # Import lazily to avoid circular deps at service init time
            from ..context.terminal_context import TerminalContext
            from ..context.log_processor.processor import LogProcessor
            from ..context.log_processor.tokenization import read_and_truncate_log
            from ..context.log_processor.parsing import extract_commands_from_log

            # Build helpers
            term_ctx = TerminalContext(self.service.config)
            log_proc = LogProcessor(self.service.config, logger)

            # Locate active log file
            log_file = log_proc.find_log_file()
            if not log_file or not log_file.exists():
                return {
                    "recent_commands": [],
                    "recent_output": "",
                    "summary": "No terminal history available",
                }

            # Token budget for safe truncation
            model_name = self.service.config.get("model", "")
            token_budget = self.service.config.get_available_context_size()

            # Read a truncated tail of the log for parsing
            log_tail = read_and_truncate_log(log_file, token_budget, model_name)
            if not log_tail:
                return {
                    "recent_commands": [],
                    "recent_output": "",
                    "summary": "No terminal history available",
                }

            # Extract commands and errors
            commands, errors = extract_commands_from_log(log_tail)

            # Compose recent commands list (just the command strings)
            max_recent = 20
            recent_commands = [cmd for (cmd, _out) in commands[-max_recent:]]

            # Compose recent output (from the last command if present)
            recent_output = ""
            if commands:
                try:
                    last_cmd, last_out = commands[-1]
                    # Keep output concise
                    recent_output = (last_out or "").strip()[:2000]
                except Exception:
                    recent_output = ""

            # Build a summary using the higher-level API for consistency
            session = term_ctx.log_processor.get_session_context(
                token_budget=token_budget, model_name=model_name
            )
            summary = session.get("summary") if isinstance(session, dict) else None
            if not summary:
                summary = "Recent terminal activity available."

            return {
                "recent_commands": recent_commands,
                "recent_output": recent_output,
                "summary": summary,
            }
        except Exception as e:
            logger.error(f"Error retrieving terminal history: {e}")
            return {
                "recent_commands": [],
                "recent_output": "",
                "summary": "No terminal history available",
            }

    async def _get_file_context(self, files: List[str]) -> Dict[str, Any]:
        """
        Get context from specified files.

        Args:
            files: List of file paths.

        Returns:
            A dictionary mapping file paths to file content.
        """
        file_context = {}

        for file_path in files:
            try:
                # Expand user directory
                expanded_path = os.path.expanduser(file_path)

                # Check if file exists
                if not os.path.isfile(expanded_path):
                    logger.warning(f"File does not exist: {file_path}")
                    continue

                # Read file content
                with open(expanded_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Add to context
                file_context[file_path] = {"content": content, "size": len(content)}

            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")

        return file_context

    async def _get_directory_info(self, directory: str) -> Dict[str, Any]:
        """
        Get information about a directory.

        Args:
            directory: Directory path.

        Returns:
            A dictionary containing directory information.
        """
        info: Dict[str, Any] = {
            "path": directory,
            "files": [],
            "directories": [],
            "summary": "",
        }

        try:
            # Expand user directory
            expanded_path = os.path.expanduser(directory)

            # Check if directory exists
            if not os.path.isdir(expanded_path):
                logger.warning(f"Directory does not exist: {directory}")
                return info

            # List directory contents
            entries = os.listdir(expanded_path)

            # Separate files and directories
            for entry in entries:
                entry_path = os.path.join(expanded_path, entry)
                if os.path.isdir(entry_path):
                    info["directories"].append(entry)
                else:
                    info["files"].append(entry)

            # Generate summary
            num_files = len(info["files"])
            num_dirs = len(info["directories"])
            info["summary"] = (
                f"Directory {directory} contains {num_files} files and {num_dirs} subdirectories."
            )

        except Exception as e:
            logger.error(f"Error getting directory info for {directory}: {e}")

        return info

    async def _detect_project_type(self, directory: str) -> Dict[str, Any]:
        """
        Detect the project type in the specified directory.

        Args:
            directory: Directory path.

        Returns:
            A dictionary containing project information.
        """
        project_info: Dict[str, Any] = {
            "type": "unknown",
            "languages": [],
            "frameworks": [],
            "details": {},
        }

        try:
            # Expand user directory
            expanded_path = os.path.expanduser(directory)

            # Check if directory exists
            if not os.path.isdir(expanded_path):
                logger.warning(f"Directory does not exist: {directory}")
                return project_info

            # Check for Python project
            if (
                os.path.exists(os.path.join(expanded_path, "requirements.txt"))
                or os.path.exists(os.path.join(expanded_path, "setup.py"))
                or os.path.exists(os.path.join(expanded_path, "pyproject.toml"))
            ):
                project_info["type"] = "python"
                project_info["languages"].append("python")

                # Check for frameworks
                if os.path.exists(os.path.join(expanded_path, "manage.py")):
                    project_info["frameworks"].append("django")
                elif os.path.exists(
                    os.path.join(expanded_path, "app.py")
                ) or self._check_file_content(
                    os.path.join(expanded_path, "requirements.txt"), "flask"
                ):
                    project_info["frameworks"].append("flask")

            # Check for Node.js project
            elif os.path.exists(os.path.join(expanded_path, "package.json")):
                project_info["type"] = "node"
                project_info["languages"].append("javascript")

                # Check for frameworks
                if self._check_file_content(
                    os.path.join(expanded_path, "package.json"), "react"
                ):
                    project_info["frameworks"].append("react")
                elif self._check_file_content(
                    os.path.join(expanded_path, "package.json"), "vue"
                ):
                    project_info["frameworks"].append("vue")
                elif self._check_file_content(
                    os.path.join(expanded_path, "package.json"), "angular"
                ):
                    project_info["frameworks"].append("angular")

            # Check for Java project
            elif os.path.exists(
                os.path.join(expanded_path, "pom.xml")
            ) or os.path.exists(os.path.join(expanded_path, "build.gradle")):
                project_info["type"] = "java"
                project_info["languages"].append("java")

                # Check for frameworks
                if self._check_file_content(
                    os.path.join(expanded_path, "pom.xml"), "spring-boot"
                ) or self._check_file_content(
                    os.path.join(expanded_path, "build.gradle"), "spring-boot"
                ):
                    project_info["frameworks"].append("spring-boot")

        except Exception as e:
            logger.error(f"Error detecting project type for {directory}: {e}")

        return project_info

    def _check_file_content(self, file_path: str, search_term: str) -> bool:
        """
        Check if a file contains a specific term.

        Args:
            file_path: Path to the file.
            search_term: Term to search for.

        Returns:
            True if the file contains the term, False otherwise.
        """
        try:
            if not os.path.isfile(file_path):
                return False

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                return search_term in content
        except Exception:
            return False
