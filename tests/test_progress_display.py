"""Tests for tqdm-based progress display functionality."""

import unittest
from unittest.mock import Mock

from aixterm.progress_display import (
    ProgressDisplay,
    ProgressDisplayType,
    TqdmProgress,
    create_progress_display,
)


class TestProgressDisplayTqdm(unittest.TestCase):
    """Test the ProgressDisplay class with tqdm backend."""

    def setUp(self):
        """Set up test fixtures."""
        self.progress_display = ProgressDisplay(ProgressDisplayType.PROGRESS_BAR)

    def test_create_progress(self):
        """Test creating a progress display."""
        progress = self.progress_display.create_progress(
            progress_token="test-token",
            title="Test Progress",
            total=100,
            show_immediately=False,
        )

        self.assertIsInstance(progress, TqdmProgress)
        self.assertEqual(progress.token, "test-token")
        self.assertEqual(progress.title, "Test Progress")
        self.assertEqual(progress.total, 100)
        self.assertFalse(progress.is_visible)

    def test_update_progress(self):
        """Test updating progress."""
        token = "test-token"
        self.progress_display.create_progress(
            progress_token=token, title="Test", show_immediately=False
        )

        # Update progress
        self.progress_display.update_progress(token, 50, "Half done", 100)

        # Verify progress was updated
        active_progress = self.progress_display._active_displays[token]
        self.assertEqual(active_progress.current_progress, 50)
        self.assertEqual(active_progress.message, "Half done")
        self.assertEqual(active_progress.total, 100)

    def test_complete_progress(self):
        """Test completing progress."""
        token = "test-token"
        self.progress_display.create_progress(
            progress_token=token, title="Test", show_immediately=False
        )

        # Complete progress
        self.progress_display.complete_progress(token, "Done!")

        # Verify progress was removed
        self.assertNotIn(token, self.progress_display._active_displays)

    def test_cleanup_all(self):
        """Test cleaning up all progress displays."""
        # Create multiple progress displays
        for i in range(3):
            self.progress_display.create_progress(
                progress_token=f"test-{i}", title=f"Test {i}", show_immediately=False
            )

        self.assertEqual(len(self.progress_display._active_displays), 3)

        # Cleanup all
        self.progress_display.cleanup_all()

        # Verify all were removed
        self.assertEqual(len(self.progress_display._active_displays), 0)
        self.assertEqual(self.progress_display._position_counter, 0)


class TestTqdmProgressBasic(unittest.TestCase):
    """Test the TqdmProgress class basic functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.parent = Mock()

        self.progress = TqdmProgress(
            token="test-token",
            title="Test Progress",
            total=100,
            display_type=ProgressDisplayType.PROGRESS_BAR,
            position=0,
            parent=self.parent,
        )

    def test_initialization(self):
        """Test TqdmProgress initialization."""
        self.assertEqual(self.progress.token, "test-token")
        self.assertEqual(self.progress.title, "Test Progress")
        self.assertEqual(self.progress.total, 100)
        self.assertEqual(self.progress.current_progress, 0)
        self.assertEqual(self.progress.message, "")
        self.assertFalse(self.progress.is_visible)
        self.assertFalse(self.progress.is_completed)
        self.assertIsNone(self.progress._tqdm)

    def test_update_basic(self):
        """Test basic progress updates."""
        self.progress.update(50, "Half way", 200)

        self.assertEqual(self.progress.current_progress, 50)
        self.assertEqual(self.progress.message, "Half way")
        self.assertEqual(self.progress.total, 200)

    def test_complete_basic(self):
        """Test completing progress."""
        self.progress.complete("Finished!")

        self.assertTrue(self.progress.is_completed)
        self.assertEqual(self.progress.message, "Finished!")


class TestProgressDisplayTypes(unittest.TestCase):
    """Test different progress display types."""

    def test_create_progress_display_types(self):
        """Test creating different display types."""
        # Test valid types
        simple = create_progress_display("simple")
        self.assertEqual(simple.display_type, ProgressDisplayType.SIMPLE)

        bar = create_progress_display("bar")
        self.assertEqual(bar.display_type, ProgressDisplayType.PROGRESS_BAR)

        spinner = create_progress_display("spinner")
        self.assertEqual(spinner.display_type, ProgressDisplayType.SPINNER)

        detailed = create_progress_display("detailed")
        self.assertEqual(detailed.display_type, ProgressDisplayType.DETAILED)

        # Test invalid type defaults to progress bar
        invalid = create_progress_display("invalid")
        self.assertEqual(invalid.display_type, ProgressDisplayType.PROGRESS_BAR)


class TestProgressIntegration(unittest.TestCase):
    """Test progress display integration scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.progress_display = ProgressDisplay(ProgressDisplayType.PROGRESS_BAR)

    def test_multi_progress_handling(self):
        """Test handling multiple concurrent progress displays."""
        # Create multiple progress displays
        tokens = ["task1", "task2", "task3"]

        for token in tokens:
            self.progress_display.create_progress(
                progress_token=token,
                title=f"Task {token}",
                total=100,
                show_immediately=False,
            )

        # Update them independently
        self.progress_display.update_progress("task1", 30)
        self.progress_display.update_progress("task2", 60)
        self.progress_display.update_progress("task3", 90)

        # Complete some
        self.progress_display.complete_progress("task1", "Task 1 done")
        self.progress_display.complete_progress("task3", "Task 3 done")

        # Should have 1 remaining
        self.assertEqual(len(self.progress_display._active_displays), 1)
        self.assertIn("task2", self.progress_display._active_displays)

    def test_progress_without_total(self):
        """Test progress display without known total."""
        self.progress_display.create_progress(
            progress_token="unknown-total",
            title="Processing items",
            total=None,
            show_immediately=False,
        )

        # Update with unknown total
        self.progress_display.update_progress("unknown-total", 42, "Processing item 42")

        # Should handle gracefully
        active = self.progress_display._active_displays["unknown-total"]
        self.assertEqual(active.current_progress, 42)
        self.assertEqual(active.message, "Processing item 42")
        # Note: total might be None initially but could be updated

    def test_progress_error_handling(self):
        """Test error handling in progress display."""
        # Try to update non-existent progress
        self.progress_display.update_progress("non-existent", 50)

        # Should not raise exception
        self.assertEqual(len(self.progress_display._active_displays), 0)

        # Try to complete non-existent progress
        self.progress_display.complete_progress("non-existent")

        # Should not raise exception
        self.assertEqual(len(self.progress_display._active_displays), 0)

    def test_position_assignment(self):
        """Test that positions are assigned correctly for concurrent displays."""
        # Create multiple progress displays
        tokens = ["task1", "task2", "task3"]

        for i, token in enumerate(tokens):
            progress = self.progress_display.create_progress(
                progress_token=token,
                title=f"Task {token}",
                total=100,
                show_immediately=False,
            )
            self.assertEqual(progress.position, i)

        # Position counter should be updated
        self.assertEqual(self.progress_display._position_counter, 3)

        # After cleanup, position counter should reset
        self.progress_display.cleanup_all()
        self.assertEqual(self.progress_display._position_counter, 0)


class TestTqdmIntegration(unittest.TestCase):
    """Test integration with actual tqdm functionality."""

    def test_tqdm_creation_and_update(self):
        """Test that tqdm instances are created and updated properly."""
        progress_display = ProgressDisplay(ProgressDisplayType.PROGRESS_BAR)

        # Create progress and show it
        progress_display.create_progress(
            progress_token="tqdm-test",
            title="Testing tqdm",
            total=10,
            show_immediately=True,
        )

        progress = progress_display._active_displays["tqdm-test"]

        # Verify tqdm instance was created
        self.assertIsNotNone(progress._tqdm)
        self.assertTrue(progress.is_visible)

        # Update progress
        progress_display.update_progress("tqdm-test", 5, "Halfway there")
        self.assertEqual(progress.current_progress, 5)
        self.assertEqual(progress.message, "Halfway there")

        # Complete progress
        progress_display.complete_progress("tqdm-test", "All done!")
        self.assertTrue(progress.is_completed)
        self.assertIsNone(progress._tqdm)  # Should be closed


if __name__ == "__main__":
    unittest.main()
