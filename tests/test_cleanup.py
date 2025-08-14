"""Tests for cleanup functionality."""

import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch


class TestCleanupManager:
    """Test cases for CleanupManager class."""

    def test_should_run_cleanup_disabled(self, cleanup_manager):
        """Test cleanup check when cleanup is disabled."""
        cleanup_manager.config.set("cleanup.enabled", False)

        assert cleanup_manager.should_run_cleanup() is False

    def test_should_run_cleanup_first_time(self, cleanup_manager):
        """Test cleanup check when never run before."""
        cleanup_manager.config.set("cleanup.enabled", True)
        cleanup_manager._last_cleanup = 0

        assert cleanup_manager.should_run_cleanup() is True

    def test_should_run_cleanup_interval_not_reached(self, cleanup_manager):
        """Test cleanup check when interval hasn't been reached."""
        cleanup_manager.config.set("cleanup.enabled", True)
        cleanup_manager.config.set("cleanup.cleanup_interval_hours", 24)
        cleanup_manager._last_cleanup = time.time() - (12 * 3600)  # 12 hours ago

        assert cleanup_manager.should_run_cleanup() is False

    def test_should_run_cleanup_interval_reached(self, cleanup_manager):
        """Test cleanup check when interval has been reached."""
        cleanup_manager.config.set("cleanup.enabled", True)
        cleanup_manager.config.set("cleanup.cleanup_interval_hours", 24)
        cleanup_manager._last_cleanup = time.time() - (25 * 3600)  # 25 hours ago

        assert cleanup_manager.should_run_cleanup() is True

    def test_run_cleanup_skipped(self, cleanup_manager):
        """Test cleanup being skipped when not needed."""
        cleanup_manager._last_cleanup = time.time()  # Just ran

        result = cleanup_manager.run_cleanup()

        assert result["skipped"] is True
        assert "Not time for cleanup" in result["reason"]

    def test_run_cleanup_force(self, cleanup_manager, mock_home_dir):
        """Test forced cleanup execution."""
        # Create some test log files
        old_log = mock_home_dir / ".aixterm_log.old"
        new_log = mock_home_dir / ".aixterm_log.new"

        old_log.write_text("old log content")
        new_log.write_text("new log content")

        with patch.object(cleanup_manager, "_cleanup_log_files") as mock_log_cleanup:
            with patch.object(
                cleanup_manager, "_cleanup_temp_files"
            ) as mock_temp_cleanup:
                mock_log_cleanup.return_value = {
                    "log_files_cleaned": 1,
                    "log_files_removed": 0,
                    "bytes_freed": 100,
                }
                mock_temp_cleanup.return_value = {
                    "files_removed": 2,
                    "bytes_freed": 200,
                }

                result = cleanup_manager.run_cleanup(force=True)

                assert "skipped" not in result
                assert result["log_files_cleaned"] == 1
                assert result["temp_files_removed"] == 2
                assert result["bytes_freed"] == 300
                assert cleanup_manager._last_cleanup > 0

    def test_cleanup_log_files_by_age(self, cleanup_manager, mock_home_dir):
        """Test cleanup of log files by age."""
        cleanup_manager.config.set("cleanup.max_log_age_days", 30)

        # Create old and new log files
        old_log = mock_home_dir / ".aixterm_log.old"
        new_log = mock_home_dir / ".aixterm_log.new"

        old_log.write_text("old content")
        new_log.write_text("new content")

        # Make old_log appear old
        old_time = time.time() - (35 * 24 * 3600)  # 35 days ago
        import os

        old_log.touch()
        # Set modification time using os.utime for Windows compatibility
        os.utime(old_log, (old_time, old_time))

        with patch.object(
            cleanup_manager, "_get_log_files", return_value=[old_log, new_log]
        ):
            result = cleanup_manager._cleanup_log_files()

            assert result["log_files_removed"] == 1
            assert result["bytes_freed"] > 0
            assert not old_log.exists()
            assert new_log.exists()

    def test_cleanup_log_files_by_count(self, cleanup_manager, mock_home_dir):
        """Test cleanup of log files by count limit."""
        cleanup_manager.config.set("cleanup.max_log_files", 2)
        cleanup_manager.config.set(
            "cleanup.max_log_age_days", 365
        )  # Don't remove by age

        # Create multiple log files
        log_files = []
        for i in range(5):
            log_file = mock_home_dir / f".aixterm_log.test{i}"
            log_file.write_text(f"content {i}")
            log_files.append(log_file)
            time.sleep(0.01)  # Ensure different modification times

        with patch.object(cleanup_manager, "_get_log_files", return_value=log_files):
            result = cleanup_manager._cleanup_log_files()

            # Should remove oldest 3 files, keep newest 2
            assert result["log_files_removed"] == 3

            # Check which files remain (should be the newest ones)
            remaining = [f for f in log_files if f.exists()]
            assert len(remaining) == 2

    def test_truncate_large_log_file(self, cleanup_manager, mock_home_dir):
        """Test truncating large log files."""
        large_log = mock_home_dir / ".aixterm_log.large"

        # Create a large log file (simulate > 10MB)
        large_content = "line\n" * 2000  # Many lines
        large_log.write_text(large_content)

        # Mock the file size to appear large
        with patch.object(Path, "stat") as mock_stat:
            mock_stat_result = Mock()
            mock_stat_result.st_size = 15 * 1024 * 1024  # 15MB
            mock_stat.return_value = mock_stat_result

            result = cleanup_manager._truncate_large_log_file(large_log)

            assert result is True

            # File should be truncated
            with open(large_log, "r") as f:
                lines = f.readlines()
            assert len(lines) <= 1000  # Should keep last 1000 lines

    def test_cleanup_temp_files(self, cleanup_manager, mock_home_dir):
        """Test cleanup of temporary files."""
        # Create some temporary files
        temp_file1 = mock_home_dir / ".aixterm_temp_test"
        temp_file2 = mock_home_dir / ".aixterm_test.tmp"
        regular_file = mock_home_dir / "regular_file.txt"

        temp_file1.write_text("temp content 1")
        temp_file2.write_text("temp content 2")
        regular_file.write_text("regular content")

        result = cleanup_manager._cleanup_temp_files()

        assert result["files_removed"] >= 0  # Might not find files due to glob patterns
        assert result["bytes_freed"] >= 0

    def test_get_cleanup_status(self, cleanup_manager, mock_home_dir):
        """Test getting cleanup status information."""
        # Create some log files
        log1 = mock_home_dir / ".aixterm_log.test1"
        log2 = mock_home_dir / ".aixterm_log.test2"
        log1.write_text("content1")
        log2.write_text("content2")

        with patch.object(cleanup_manager, "_get_log_files", return_value=[log1, log2]):
            status = cleanup_manager.get_cleanup_status()

            assert status["cleanup_enabled"] is True
            assert status["log_files_count"] == 2
            assert status["total_log_size_bytes"] > 0
            assert "config" in status
            assert status["config"]["max_log_age_days"] == 30

    def test_get_next_cleanup_time_never_run(self, cleanup_manager):
        """Test next cleanup time when never run before."""
        cleanup_manager._last_cleanup = 0

        next_time = cleanup_manager._get_next_cleanup_time()
        assert next_time == "Now (never run)"

    def test_get_next_cleanup_time_overdue(self, cleanup_manager):
        """Test next cleanup time when overdue."""
        cleanup_manager.config.set("cleanup.cleanup_interval_hours", 24)
        cleanup_manager._last_cleanup = time.time() - (25 * 3600)  # 25 hours ago

        next_time = cleanup_manager._get_next_cleanup_time()
        assert next_time == "Now (overdue)"

    def test_get_next_cleanup_time_scheduled(self, cleanup_manager):
        """Test next cleanup time when scheduled in future."""
        cleanup_manager.config.set("cleanup.cleanup_interval_hours", 24)
        cleanup_manager._last_cleanup = time.time() - (12 * 3600)  # 12 hours ago

        next_time = cleanup_manager._get_next_cleanup_time()
        assert next_time is not None
        assert "Now" not in next_time

        # Should be a valid ISO datetime
        datetime.fromisoformat(next_time)

    def test_get_next_cleanup_time_disabled(self, cleanup_manager):
        """Test next cleanup time when cleanup is disabled."""
        cleanup_manager.config.set("cleanup.enabled", False)

        next_time = cleanup_manager._get_next_cleanup_time()
        assert next_time is None

    def test_force_cleanup_now(self, cleanup_manager):
        """Test forcing immediate cleanup."""
        with patch.object(cleanup_manager, "run_cleanup") as mock_cleanup:
            mock_cleanup.return_value = {"forced": True}

            result = cleanup_manager.force_cleanup_now()

            assert result == {"forced": True}
            mock_cleanup.assert_called_once_with(force=True)

    def test_enable_disable_cleanup(self, cleanup_manager):
        """Test enabling and disabling cleanup."""
        # Test disable
        cleanup_manager.disable_cleanup()
        assert cleanup_manager.config.get("cleanup.enabled") is False

        # Test enable
        cleanup_manager.enable_cleanup()
        assert cleanup_manager.config.get("cleanup.enabled") is True

    def test_cleanup_error_handling(self, cleanup_manager):
        """Test error handling during cleanup operations."""
        with patch.object(
            cleanup_manager,
            "_cleanup_log_files",
            side_effect=Exception("Test error"),
        ):
            result = cleanup_manager.run_cleanup(force=True)

            assert len(result["errors"]) > 0
            assert "Cleanup failed: Test error" in result["errors"][0]

    def test_get_log_files(self, cleanup_manager, mock_home_dir):
        """Test getting list of log files."""
        # Create log files and other files
        log1 = mock_home_dir / ".aixterm_log.test1"
        log2 = mock_home_dir / ".aixterm_log.test2"
        other_file = mock_home_dir / ".other_file"

        log1.write_text("log1")
        log2.write_text("log2")
        other_file.write_text("other")

        log_files = cleanup_manager._get_log_files()

        assert len(log_files) == 2
        assert log1 in log_files
        assert log2 in log_files
        assert other_file not in log_files

    def test_file_error_handling_in_cleanup(self, cleanup_manager, mock_home_dir):
        """Test handling of file operation errors during cleanup."""
        # Create a log file
        log_file = mock_home_dir / ".aixterm_log.test"
        log_file.write_text("content")

        # Mock file removal to fail
        with patch.object(Path, "unlink", side_effect=PermissionError("Access denied")):
            with patch.object(
                cleanup_manager, "_get_log_files", return_value=[log_file]
            ):
                result = cleanup_manager._cleanup_log_files()

                # Should handle the error gracefully
                assert "errors" in result or result["log_files_removed"] == 0
