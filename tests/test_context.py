"""Tests for terminal context management."""

import os
import sys
from unittest.mock import Mock, patch


class TestTerminalContext:
    """Test cases for TerminalContext class."""

    def test_get_terminal_context_with_log(self, context_manager, sample_log_file):
        """Test getting terminal context with existing log file."""
        with patch.object(
            context_manager, "_find_log_file", return_value=sample_log_file
        ):
            context = context_manager.get_terminal_context()

            assert "Current working directory:" in context
            assert "Recent terminal output:" in context
            assert "ls -la" in context
            assert "Hello, world!" in context

    def test_get_terminal_context_no_log(self, context_manager):
        """Test getting terminal context when no log file exists."""
        with patch.object(context_manager, "_find_log_file", return_value=None):
            context = context_manager.get_terminal_context()

            assert "Current working directory:" in context
            assert "No recent terminal history available" in context

    def test_find_log_file_with_tty(self, context_manager, mock_home_dir):
        """Test finding log file using TTY information."""
        expected_log = mock_home_dir / ".aixterm_log.pts-0"
        expected_log.write_text("test log content")

        # Test TTY functionality on Unix systems, or mock it on Windows
        if hasattr(os, "ttyname"):
            with patch("os.ttyname", return_value="/dev/pts/0"):
                with patch.object(context_manager.config, "get", return_value=200):
                    log_path = context_manager._find_log_file()
                    assert log_path == expected_log
        else:
            # On Windows, add the ttyname function temporarily and mock stdin.fileno
            def mock_ttyname(fd):
                return "/dev/pts/0"

            os.ttyname = mock_ttyname
            try:
                with patch.object(sys.stdin, "fileno", return_value=0):
                    with patch.object(context_manager.config, "get", return_value=200):
                        log_path = context_manager._find_log_file()
                        assert log_path == expected_log
            finally:
                # Clean up
                delattr(os, "ttyname")

    def test_find_log_file_fallback(self, context_manager, mock_home_dir):
        """Test finding log file using fallback (most recent)."""
        # Create multiple log files with different timestamps
        old_log = mock_home_dir / ".aixterm_log.old"
        new_log = mock_home_dir / ".aixterm_log.new"

        old_log.write_text("old content")
        new_log.write_text("new content")

        # Make new_log more recent
        import time

        time.sleep(0.1)
        new_log.touch()

        # Test fallback behavior when TTY is not available
        if hasattr(os, "ttyname"):
            # On Unix systems, test OSError fallback
            with patch("os.ttyname", side_effect=OSError("No TTY")):
                log_path = context_manager._find_log_file()
                assert log_path == new_log
        else:
            # On Windows, ttyname doesn't exist so fallback is used automatically
            log_path = context_manager._find_log_file()
            assert log_path == new_log  # Should return most recent

    def test_read_and_truncate_log_with_tiktoken(
        self, context_manager, sample_log_file
    ):
        """Test reading and truncating log with tiktoken."""
        with patch("tiktoken.encoding_for_model") as mock_tiktoken:
            mock_encoder = Mock()
            mock_encoder.encode.return_value = list(range(50))  # 50 tokens
            mock_encoder.decode.return_value = "truncated content"
            mock_tiktoken.return_value = mock_encoder

            # Use a known model name that won't trigger fallback
            result = context_manager._read_and_truncate_log(
                sample_log_file, 30, "gpt-3.5-turbo"
            )

            # Should be truncated since we have 50 tokens but limit is 30
            mock_encoder.decode.assert_called_once()
            assert result == "truncated content"

    def test_read_and_truncate_log_fallback(self, context_manager, sample_log_file):
        """Test reading and truncating log with fallback method."""
        with patch("tiktoken.get_encoding", side_effect=Exception("No tiktoken")):
            result = context_manager._read_and_truncate_log(
                sample_log_file, 10, "test-model"
            )

            # Should use character-based fallback (10 tokens * 4 chars = 40 chars)
            assert len(result) <= 40
            assert isinstance(result, str)

    def test_read_and_truncate_log_large_file(self, context_manager, mock_home_dir):
        """Test truncating large log files."""
        large_log = mock_home_dir / ".aixterm_log.large"

        # Create a log with more than 1000 lines
        lines = [f"$ command {i}\noutput {i}\n" for i in range(1500)]
        large_log.write_text("".join(lines))

        original_size = len(lines)

        context_manager._read_and_truncate_log(large_log, 100, "test-model")

        # File should be truncated to 1000 lines
        with open(large_log, "r") as f:
            remaining_lines = f.readlines()

        assert len(remaining_lines) == 1000
        assert len(remaining_lines) < original_size

    def test_get_log_files(self, context_manager, mock_home_dir):
        """Test getting list of all log files."""
        # Create some log files
        log1 = mock_home_dir / ".aixterm_log.test1"
        log2 = mock_home_dir / ".aixterm_log.test2"
        other_file = mock_home_dir / ".other_file"

        log1.write_text("log1")
        log2.write_text("log2")
        other_file.write_text("other")

        log_files = context_manager.get_log_files()

        assert len(log_files) == 2
        assert log1 in log_files
        assert log2 in log_files
        assert other_file not in log_files

    def test_create_log_entry(self, context_manager, mock_home_dir):
        """Test creating log entries."""
        with patch.object(context_manager, "_get_current_log_file") as mock_get_log:
            log_file = mock_home_dir / ".aixterm_log.test"
            mock_get_log.return_value = log_file

            context_manager.create_log_entry("ls -la", "file listing output")

            assert log_file.exists()
            content = log_file.read_text()
            assert "$ ls -la" in content
            assert "file listing output" in content

    def test_get_current_log_file_with_tty(self, context_manager, mock_home_dir):
        """Test getting current log file with TTY."""
        # Test TTY functionality on Unix systems, or mock it on Windows
        if hasattr(os, "ttyname"):
            with patch("os.ttyname", return_value="/dev/pts/1"), patch.object(
                sys.stdin, "fileno", return_value=0
            ):
                log_path = context_manager._get_current_log_file()
                assert log_path == mock_home_dir / ".aixterm_log.pts-1"
        else:
            # On Windows, add the ttyname function temporarily and mock stdin.fileno
            def mock_ttyname(fd):
                return "/dev/pts/1"

            os.ttyname = mock_ttyname
            try:
                with patch.object(sys.stdin, "fileno", return_value=0):
                    log_path = context_manager._get_current_log_file()
                    assert log_path == mock_home_dir / ".aixterm_log.pts-1"
            finally:
                # Clean up
                delattr(os, "ttyname")

    def test_get_current_log_file_fallback(self, context_manager, mock_home_dir):
        """Test getting current log file fallback."""
        # Test fallback behavior when TTY is not available
        if hasattr(os, "ttyname"):
            # On Unix systems, test OSError fallback
            with patch("os.ttyname", side_effect=OSError("No TTY")):
                log_path = context_manager._get_current_log_file()
                assert log_path == mock_home_dir / ".aixterm_log.default"
        else:
            # On Windows, ttyname doesn't exist so fallback is used automatically
            log_path = context_manager._get_current_log_file()
            expected = mock_home_dir / ".aixterm_log.default"
            assert log_path == expected

    def test_error_handling_in_context_retrieval(self, context_manager):
        """Test error handling during context retrieval."""
        with patch.object(
            context_manager,
            "_find_log_file",
            side_effect=Exception("Test error"),
        ):
            context = context_manager.get_terminal_context()

            assert "Error retrieving session log: Test error" in context
            assert "Current working directory:" in context

    def test_file_encoding_handling(self, context_manager, mock_home_dir):
        """Test handling of files with encoding issues."""
        log_file = mock_home_dir / ".aixterm_log.encoding"

        # Write some binary data that might cause encoding issues
        with open(log_file, "wb") as f:
            f.write(b"Valid text\n\xff\xfe\nMore valid text\n")

        # Should handle encoding errors gracefully
        result = context_manager._read_and_truncate_log(log_file, 100, "test-model")
        assert isinstance(result, str)
        assert "Valid text" in result or "More valid text" in result


class TestFileContexts:
    """Test cases for file context functionality."""

    def test_get_file_contexts_single_file(self, context_manager, tmp_path):
        """Test getting context from a single file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('Hello, World!')")

        result = context_manager.get_file_contexts([str(test_file)])

        assert "--- File Context (1 file(s)) ---" in result
        assert "print('Hello, World!')" in result
        assert str(test_file) in result

    def test_get_file_contexts_multiple_files(self, context_manager, tmp_path):
        """Test getting context from multiple files."""
        file1 = tmp_path / "file1.py"
        file2 = tmp_path / "file2.txt"

        file1.write_text("def hello(): pass")
        file2.write_text("This is a text file")

        result = context_manager.get_file_contexts([str(file1), str(file2)])

        assert "--- File Context (2 file(s)) ---" in result
        assert "def hello(): pass" in result
        assert "This is a text file" in result

    def test_get_file_contexts_nonexistent_file(self, context_manager):
        """Test handling of non-existent files."""
        result = context_manager.get_file_contexts(["/nonexistent/file.txt"])

        # Should return empty string since no valid files
        assert result == ""

    def test_get_file_contexts_large_file(self, context_manager, tmp_path):
        """Test handling of large files."""
        large_file = tmp_path / "large.txt"
        large_content = "x" * 60000  # Larger than the 50K limit
        large_file.write_text(large_content)

        result = context_manager.get_file_contexts([str(large_file)])

        # Should be truncated
        assert len(result) < len(large_content) + 1000  # Account for headers
        assert "--- File Context (1 file(s)) ---" in result

    def test_get_file_contexts_binary_file(self, context_manager, tmp_path):
        """Test handling of binary files."""
        binary_file = tmp_path / "binary.bin"
        # Create clearly binary content that will cause UnicodeDecodeError
        binary_content = bytes(range(256)) * 10  # Non-UTF8 bytes
        binary_file.write_bytes(binary_content)

        result = context_manager.get_file_contexts([str(binary_file)])

        assert "[Binary file - first 1KB shown]" in result

    def test_get_file_contexts_empty_list(self, context_manager):
        """Test handling of empty file list."""
        result = context_manager.get_file_contexts([])
        assert result == ""


class TestSmartContextSummarization:
    """Test cases for smart context summarization."""

    def test_get_directory_context(self, context_manager, tmp_path):
        """Test directory context detection."""
        # Create a Python project structure
        (tmp_path / "requirements.txt").write_text("requests==2.28.0")
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "README.md").write_text("# My Project")

        # Change to the test directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            result = context_manager._get_directory_context()

            assert "Python" in result
            assert "requirements.txt" in result
            assert "README.md" in result

        finally:
            os.chdir(original_cwd)

    def test_detect_project_type_python(self, context_manager, tmp_path):
        """Test Python project detection."""
        (tmp_path / "requirements.txt").touch()

        result = context_manager._detect_project_type(tmp_path)
        assert "Python" in result

    def test_detect_project_type_nodejs(self, context_manager, tmp_path):
        """Test Node.js project detection."""
        (tmp_path / "package.json").write_text('{"name": "test"}')

        result = context_manager._detect_project_type(tmp_path)
        assert "Node.js" in result

    def test_intelligent_log_summarization(self, context_manager):
        """Test intelligent log content summarization."""
        log_content = """$ ls -la
total 20
drwxr-xr-x 2 user user 4096 Jan 1 12:00 .
drwxr-xr-x 3 user user 4096 Jan 1 12:00 ..
-rw-r--r-- 1 user user   10 Jan 1 12:00 test.txt
$ cat test.txt
Hello World
$ python script.py
Error: File not found
$ echo "test"
test
"""

        result = context_manager._intelligently_summarize_log(
            log_content, 1000, "gpt-3.5-turbo"
        )

        assert "Recent commands:" in result
        assert "ls -la" in result
        assert "Error: File not found" in result or "Recent errors" in result

    def test_apply_token_limit(self, context_manager):
        """Test token limit application."""
        long_text = "word " * 1000  # Long text

        result = context_manager._apply_token_limit(long_text, 50, "gpt-3.5-turbo")

        # Should be shorter than the original
        assert len(result) < len(long_text)


class TestAdvancedTerminalContext:
    """Test cases for advanced terminal context functionality."""

    def test_get_terminal_context_with_smart_features(self, context_manager, tmp_path):
        """Test terminal context with smart features enabled."""
        # Create a mock log file
        log_file = tmp_path / ".aixterm_log.default"
        log_file.write_text("$ echo hello\nhello\n$ ls\nfile1.txt\nfile2.txt")

        with patch.object(context_manager, "_find_log_file", return_value=log_file):
            with patch("os.getcwd", return_value=str(tmp_path)):
                result = context_manager.get_terminal_context(smart_summarize=True)

                assert str(tmp_path) in result
                assert "Recent commands:" in result or "echo hello" in result

    def test_get_terminal_context_without_smart_features(
        self, context_manager, tmp_path
    ):
        """Test terminal context with smart features disabled."""
        log_file = tmp_path / ".aixterm_log.default"
        log_file.write_text("$ echo hello\nhello")

        with patch.object(context_manager, "_find_log_file", return_value=log_file):
            with patch("os.getcwd", return_value=str(tmp_path)):
                result = context_manager.get_terminal_context(smart_summarize=False)

                assert str(tmp_path) in result
                # Should use the old truncation method
                assert "echo hello" in result


class TestOptimizedContext:
    """Test cases for optimized context functionality."""

    def test_get_optimized_context_basic(self, context_manager, tmp_path):
        """Test basic optimized context functionality."""
        # Create a mock log file
        log_file = tmp_path / ".aixterm_log.default"
        log_file.write_text("$ echo hello\nhello\n$ ls\nfile1.txt\nfile2.txt")

        with patch.object(context_manager, "_find_log_file", return_value=log_file):
            with patch("os.getcwd", return_value=str(tmp_path)):
                result = context_manager.get_optimized_context(query="test query")

                assert str(tmp_path) in result
                assert "echo hello" in result or "Recent terminal output" in result

    def test_get_optimized_context_with_files(self, context_manager, tmp_path):
        """Test optimized context with file contexts."""
        # Create test files
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello world')")

        log_file = tmp_path / ".aixterm_log.default"
        log_file.write_text("$ python test.py\nhello world")

        with patch.object(context_manager, "_find_log_file", return_value=log_file):
            with patch("os.getcwd", return_value=str(tmp_path)):
                result = context_manager.get_optimized_context(
                    [str(test_file)], "analyze this code"
                )

                assert "File Context" in result
                assert "print('hello world')" in result
                assert str(tmp_path) in result

    def test_estimate_tokens(self, context_manager):
        """Test token estimation functionality."""
        # Test with simple text
        short_text = "Hello world"
        tokens = context_manager._estimate_tokens(short_text)

        # Should return a reasonable estimate
        assert isinstance(tokens, int)
        assert tokens > 0
        assert tokens < 100  # Should be small for short text

    def test_estimate_tokens_empty(self, context_manager):
        """Test token estimation with empty text."""
        tokens = context_manager._estimate_tokens("")
        assert tokens == 0

    def test_optimized_context_budget_management(self, context_manager, tmp_path):
        """Test that optimized context respects token budgets."""
        # Create a large log file
        large_content = "$ command\noutput\n" * 1000
        log_file = tmp_path / ".aixterm_log.default"
        log_file.write_text(large_content)

        with patch.object(context_manager, "_find_log_file", return_value=log_file):
            with patch("os.getcwd", return_value=str(tmp_path)):
                result = context_manager.get_optimized_context(
                    query="test with large content"
                )

                # Should not exceed reasonable limits
                assert len(result) < 50000  # Reasonable upper bound
                # Should still have directory info (may be truncated to basename)
                assert tmp_path.name in result or str(tmp_path) in result
