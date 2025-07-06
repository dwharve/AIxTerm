"""Tests for the modular terminal context management."""

import os
import sys
from unittest.mock import Mock, patch


class TestModularTerminalContext:
    """Test cases for the modular TerminalContext class."""

    def test_get_terminal_context_with_log(self, context_manager, sample_log_file):
        """Test getting terminal context with existing log file."""
        with patch.object(
            context_manager.log_processor, "find_log_file", return_value=sample_log_file
        ):
            context = context_manager.get_terminal_context()

            assert "Current working directory:" in context
            assert "Recent terminal output:" in context
            # With intelligent summarization, commands may be grouped
            assert "ls" in context or "pwd" in context  # Should contain some commands
            assert "Hello, world!" in context

    def test_get_terminal_context_no_log(self, context_manager):
        """Test getting terminal context when no log file exists."""
        with patch.object(
            context_manager.log_processor, "find_log_file", return_value=None
        ):
            context = context_manager.get_terminal_context()

            assert "Current working directory:" in context
            assert "No recent terminal history available" in context

    def test_log_processor_read_and_truncate_log(
        self, context_manager, sample_log_file
    ):
        """Test log processor reading and truncating log with tiktoken."""
        with patch("tiktoken.encoding_for_model") as mock_tiktoken:
            mock_encoder = Mock()
            mock_encoder.encode.return_value = list(range(50))  # 50 tokens
            mock_encoder.decode.return_value = "truncated content"
            mock_tiktoken.return_value = mock_encoder

            # Use a known model name that won't trigger fallback
            result = context_manager.log_processor._read_and_truncate_log(
                sample_log_file, 30, "gpt-3.5-turbo"
            )

            # Should be truncated since we have 50 tokens but limit is 30
            mock_encoder.decode.assert_called_once()
            assert result == "truncated content"

    def test_log_processor_find_log_file_with_tty(self, context_manager, mock_home_dir):
        """Test log processor finding log file using TTY information."""
        expected_log = mock_home_dir / ".aixterm_log.pts-0"
        expected_log.write_text("test log content")

        # Test TTY functionality on Unix systems, or mock it on Windows
        if hasattr(os, "ttyname"):
            with patch("os.ttyname", return_value="/dev/pts/0"):
                with patch(
                    "aixterm.context.log_processor.Path.home",
                    return_value=mock_home_dir,
                ):
                    with patch.object(
                        context_manager.log_processor,
                        "_get_current_tty",
                        return_value="pts-0",
                    ):
                        with patch.dict(
                            os.environ, {"_AIXTERM_LOG_FILE": ""}, clear=False
                        ):
                            log_path = context_manager.log_processor.find_log_file()
                            assert log_path == expected_log
        else:
            # On Windows, add the ttyname function temporarily and mock stdin.fileno
            def mock_ttyname(_):
                return "/dev/pts/0"

            os.ttyname = mock_ttyname
            try:
                with patch.object(sys.stdin, "fileno", return_value=0):
                    log_path = context_manager.log_processor.find_log_file()
                    assert log_path == expected_log
            finally:
                delattr(os, "ttyname")

    def test_log_processor_get_log_files(self, context_manager, mock_home_dir):
        """Test log processor getting list of all log files."""
        # Create some log files
        log1 = mock_home_dir / ".aixterm_log.test1"
        log2 = mock_home_dir / ".aixterm_log.test2"
        other_file = mock_home_dir / ".other_file"

        log1.write_text("log1")
        log2.write_text("log2")
        other_file.write_text("other")

        log_files = context_manager.log_processor.get_log_files()

        assert len(log_files) == 2
        assert log1 in log_files
        assert log2 in log_files
        assert other_file not in log_files

    def test_log_processor_create_log_entry(self, context_manager, mock_home_dir):
        """Test log processor creating log entries."""
        with patch.object(
            context_manager.log_processor, "_get_current_log_file"
        ) as mock_get_log:
            log_file = mock_home_dir / ".aixterm_log.test"
            mock_get_log.return_value = log_file

            context_manager.log_processor.create_log_entry(
                "ls -la", "file listing output"
            )

            assert log_file.exists()
            content = log_file.read_text()
            assert "$ ls -la" in content
            assert "file listing output" in content

    def test_directory_handler_get_directory_context(self, context_manager, tmp_path):
        """Test directory handler getting directory context."""
        # Create some test files
        (tmp_path / "test.py").write_text("print('hello')")
        (tmp_path / "README.md").write_text("# Test Project")
        (tmp_path / "requirements.txt").write_text("requests==2.25.1")

        with patch("os.getcwd", return_value=str(tmp_path)):
            result = context_manager.directory_handler.get_directory_context()

            assert "Files in directory:" in result
            assert "Key files:" in result
            assert "README.md" in result
            assert "requirements.txt" in result
            assert "Project type: Python" in result

    def test_directory_handler_detect_project_type_python(
        self, context_manager, tmp_path
    ):
        """Test directory handler detecting Python project type."""
        # Create Python project indicators
        (tmp_path / "requirements.txt").write_text("requests==2.25.1")
        (tmp_path / "setup.py").write_text("from setuptools import setup")

        result = context_manager.directory_handler._detect_project_type(tmp_path)
        assert "Python" in result

    def test_directory_handler_detect_project_type_nodejs(
        self, context_manager, tmp_path
    ):
        """Test directory handler detecting Node.js project type."""
        # Create Node.js project indicators
        (tmp_path / "package.json").write_text('{"name": "test"}')

        result = context_manager.directory_handler._detect_project_type(tmp_path)
        assert "Node.js" in result

    def test_token_manager_estimate_tokens(self, context_manager):
        """Test token manager token estimation functionality."""
        # Test with simple text
        short_text = "Hello world"
        tokens = context_manager.token_manager.estimate_tokens(short_text)

        # Should return a reasonable estimate
        assert isinstance(tokens, int)
        assert tokens > 0
        assert tokens < 100  # Should be small for short text

    def test_token_manager_estimate_tokens_empty(self, context_manager):
        """Test token manager token estimation with empty text."""
        tokens = context_manager.token_manager.estimate_tokens("")
        assert tokens == 0

    def test_token_manager_apply_token_limit(self, context_manager):
        """Test token manager applying token limits."""
        with patch("tiktoken.encoding_for_model") as mock_tiktoken:
            mock_encoder = Mock()
            mock_encoder.encode.return_value = list(range(100))  # 100 tokens
            mock_encoder.decode.return_value = "limited content"
            mock_tiktoken.return_value = mock_encoder

            result = context_manager.token_manager.apply_token_limit(
                "some long text", 50, "gpt-4"
            )

            assert result == "limited content"
            mock_encoder.decode.assert_called_once()

    def test_get_file_contexts_single_file(self, context_manager, tmp_path):
        """Test getting context from a single file."""
        test_file = tmp_path / "test.py"
        test_content = "print('Hello, world!')\n# This is a test file"
        test_file.write_text(test_content)

        result = context_manager.get_file_contexts([str(test_file)])

        assert "File Context" in result
        assert str(test_file) in result
        assert test_content in result

    def test_get_file_contexts_multiple_files(self, context_manager, tmp_path):
        """Test getting context from multiple files."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"

        file1.write_text("Content of file 1")
        file2.write_text("Content of file 2")

        result = context_manager.get_file_contexts([str(file1), str(file2)])

        assert "File Context" in result
        assert "2 file(s)" in result
        assert "Content of file 1" in result
        assert "Content of file 2" in result
