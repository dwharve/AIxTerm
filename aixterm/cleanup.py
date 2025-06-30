"""File cleanup and maintenance utilities."""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils import format_file_size, get_logger


class CleanupManager:
    """Manages cleanup of log files and temporary data."""

    def __init__(self, config_manager: Any) -> None:
        """Initialize cleanup manager.

        Args:
            config_manager: AIxTermConfig instance
        """
        self.config = config_manager
        self.logger = get_logger(__name__)
        self._last_cleanup: float = 0.0

    def should_run_cleanup(self) -> bool:
        """Check if cleanup should be run based on configured interval.

        Returns:
            True if cleanup should run
        """
        if not self.config.get("cleanup.enabled", True):
            return False

        interval_hours_value = self.config.get("cleanup.cleanup_interval_hours", 24)
        interval_hours: int = int(interval_hours_value)
        interval_seconds = interval_hours * 3600
        current_time = time.time()

        should_cleanup: bool = (current_time - self._last_cleanup) >= interval_seconds
        return should_cleanup

    def run_cleanup(self, force: bool = False) -> Dict[str, Any]:
        """Run cleanup operations.

        Args:
            force: Force cleanup regardless of interval

        Returns:
            Cleanup results summary
        """
        if not force and not self.should_run_cleanup():
            return {"skipped": True, "reason": "Not time for cleanup"}

        self.logger.info("Starting cleanup operations")
        results: Dict[str, Any] = {
            "started_at": datetime.now().isoformat(),
            "log_files_cleaned": 0,
            "log_files_removed": 0,
            "bytes_freed": 0,
            "temp_files_removed": 0,
            "errors": [],
        }

        try:
            # Clean up log files
            log_results = self._cleanup_log_files()
            results.update(log_results)

            # Clean up temporary files
            temp_results = self._cleanup_temp_files()
            results["temp_files_removed"] = temp_results["files_removed"]
            results["bytes_freed"] += temp_results["bytes_freed"]

            # Update last cleanup time
            self._last_cleanup = time.time()

            self.logger.info(f"Cleanup completed: {results}")

        except Exception as e:
            error_msg = f"Cleanup failed: {e}"
            self.logger.error(error_msg)
            results["errors"].append(error_msg)

        results["completed_at"] = datetime.now().isoformat()
        return results

    def _cleanup_log_files(self) -> Dict[str, Any]:
        """Clean up old and excessive log files.

        Returns:
            Dictionary with cleanup results
        """
        results: Dict[str, Any] = {
            "log_files_cleaned": 0,
            "log_files_removed": 0,
            "bytes_freed": 0,
        }

        log_files = self._get_log_files()
        max_age_days = self.config.get("cleanup.max_log_age_days", 30)
        max_files = self.config.get("cleanup.max_log_files", 10)

        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        # Remove files older than max_age_days
        for log_file in log_files:
            try:
                file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_time < cutoff_date:
                    file_size = log_file.stat().st_size
                    log_file.unlink()
                    results["log_files_removed"] += 1
                    results["bytes_freed"] += file_size
                    self.logger.debug(f"Removed old log file: {log_file}")
            except Exception as e:
                error_msg = f"Error removing old log file {log_file}: {e}"
                self.logger.error(error_msg)
                results.setdefault("errors", []).append(error_msg)

        # If still too many files, remove oldest ones
        remaining_files = [f for f in log_files if f.exists()]
        if len(remaining_files) > max_files:
            # Sort by modification time (oldest first)
            remaining_files.sort(key=lambda f: f.stat().st_mtime)
            files_to_remove = remaining_files[:-max_files]

            for log_file in files_to_remove:
                try:
                    file_size = log_file.stat().st_size
                    log_file.unlink()
                    results["log_files_removed"] += 1
                    results["bytes_freed"] += file_size
                    self.logger.debug(f"Removed excess log file: {log_file}")
                except Exception as e:
                    error_msg = f"Error removing excess log file {log_file}: {e}"
                    self.logger.error(error_msg)
                    results.setdefault("errors", []).append(error_msg)

        # Truncate large log files
        for log_file in remaining_files:
            if log_file.exists():
                try:
                    if self._truncate_large_log_file(log_file):
                        results["log_files_cleaned"] += 1
                except Exception as e:
                    error_msg = f"Error truncating log file {log_file}: {e}"
                    self.logger.error(error_msg)
                    results.setdefault("errors", []).append(error_msg)

        return results

    def _truncate_large_log_file(self, log_file: Path, max_size_mb: int = 10) -> bool:
        """Truncate log file if it's too large.

        Args:
            log_file: Path to log file
            max_size_mb: Maximum size in MB

        Returns:
            True if file was truncated
        """
        max_size_bytes = max_size_mb * 1024 * 1024

        try:
            if log_file.stat().st_size > max_size_bytes:
                # Read last portion of file
                with open(log_file, "r", errors="ignore", encoding="utf-8") as f:
                    lines = f.readlines()

                # Keep last 1000 lines or half the max size, whichever is smaller
                keep_lines = min(1000, len(lines) // 2)
                if keep_lines > 0:
                    with open(log_file, "w", encoding="utf-8") as f:
                        f.writelines(lines[-keep_lines:])

                    self.logger.debug(f"Truncated log file: {log_file}")
                    return True
        except Exception as e:
            self.logger.error(f"Error truncating log file {log_file}: {e}")

        return False

    def _cleanup_temp_files(self) -> Dict[str, Any]:
        """Clean up temporary files.

        Returns:
            Dictionary with cleanup results
        """
        results: Dict[str, Any] = {"files_removed": 0, "bytes_freed": 0}

        # Look for temporary files in common locations
        temp_patterns = [
            Path.home() / ".aixterm_temp*",
            Path.home() / ".aixterm_*.tmp",
            (
                Path("/tmp") / "aixterm_*"
                if os.name != "nt"
                else Path.home() / "AppData" / "Local" / "Temp" / "aixterm_*"
            ),
        ]

        for pattern in temp_patterns:
            try:
                for temp_file in pattern.parent.glob(pattern.name):
                    if temp_file.is_file():
                        try:
                            file_size = temp_file.stat().st_size
                            temp_file.unlink()
                            results["files_removed"] += 1
                            results["bytes_freed"] += file_size
                            self.logger.debug(f"Removed temp file: {temp_file}")
                        except Exception as e:
                            self.logger.error(
                                f"Error removing temp file {temp_file}: {e}"
                            )
            except Exception as e:
                self.logger.error(
                    f"Error cleaning temp files with pattern {pattern}: {e}"
                )

        return results

    def _get_log_files(self) -> List[Path]:
        """Get list of all AIxTerm log files.

        Returns:
            List of log file paths
        """
        return list(Path.home().glob(".aixterm_log.*"))

    def get_cleanup_status(self) -> Dict[str, Any]:
        """Get cleanup status and statistics.

        Returns:
            Dictionary with cleanup status information
        """
        log_files = self._get_log_files()
        total_log_size = sum(f.stat().st_size for f in log_files if f.exists())

        return {
            "cleanup_enabled": self.config.get("cleanup.enabled", True),
            "last_cleanup": (
                datetime.fromtimestamp(self._last_cleanup).isoformat()
                if self._last_cleanup
                else None
            ),
            "next_cleanup_due": self._get_next_cleanup_time(),
            "log_files_count": len(log_files),
            "total_log_size": format_file_size(total_log_size),
            "total_log_size_bytes": total_log_size,
            "config": {
                "max_log_age_days": self.config.get("cleanup.max_log_age_days", 30),
                "max_log_files": self.config.get("cleanup.max_log_files", 10),
                "cleanup_interval_hours": self.config.get(
                    "cleanup.cleanup_interval_hours", 24
                ),
            },
        }

    def _get_next_cleanup_time(self) -> Optional[str]:
        """Get next scheduled cleanup time.

        Returns:
            ISO format datetime string or None
        """
        if not self.config.get("cleanup.enabled", True):
            return None

        if self._last_cleanup == 0.0:
            return "Now (never run)"

        interval_hours = self.config.get("cleanup.cleanup_interval_hours", 24)
        next_time = self._last_cleanup + (interval_hours * 3600)

        if next_time <= time.time():
            return "Now (overdue)"

        return datetime.fromtimestamp(next_time).isoformat()

    def force_cleanup_now(self) -> Dict[str, Any]:
        """Force immediate cleanup regardless of schedule.

        Returns:
            Cleanup results
        """
        return self.run_cleanup(force=True)

    def disable_cleanup(self) -> None:
        """Disable automatic cleanup."""
        self.config.set("cleanup.enabled", False)
        self.logger.info("Automatic cleanup disabled")

    def enable_cleanup(self) -> None:
        """Enable automatic cleanup."""
        self.config.set("cleanup.enabled", True)
        self.logger.info("Automatic cleanup enabled")
