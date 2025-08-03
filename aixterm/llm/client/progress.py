"""Progress tracking and display for LLM interactions."""

import threading
import time
from typing import Any, Dict, Optional


class ProgressManager:
    """Manages progress tracking and display for LLM interactions."""

    def __init__(
        self, logger: Any, config_manager: Any, display_manager: Optional[Any] = None
    ):
        """Initialize progress manager.

        Args:
            logger: Logger instance
            config_manager: Configuration manager
            display_manager: Optional display manager for UI updates
        """
        self.logger = logger
        self.config = config_manager
        self.display_manager = display_manager

    def start_smart_progress_update(
        self, progress: Any, timing_config: Dict[str, Any]
    ) -> None:
        """Start a background timer to update progress based on expected timing.

        Args:
            progress: Progress indicator to update
            timing_config: Timing configuration with intervals and limits
        """

        def update_progress() -> None:
            """Update progress in the background until completion or timeout."""
            try:
                update_interval = timing_config.get("progress_update_interval", 0.1)
                max_time = timing_config.get("max_progress_time", 30.0)
                avg_time = timing_config.get("average_response_time", 10.0)

                # Convert to deciseconds to match the total from create_progress
                total_steps = int(avg_time * 10)
                steps_per_update = max(1, int(update_interval * 10))
                max_updates = int(max_time / update_interval)

                current_step = 0
                updates = 0

                while current_step < total_steps and updates < max_updates:
                    time.sleep(update_interval)
                    current_step += steps_per_update
                    updates += 1

                    # Check if progress is still active (not completed or cancelled)
                    if hasattr(progress, "_completed") and progress._completed:
                        break

                    try:
                        # Update progress with current step, capped at total
                        progress.update(min(current_step, total_steps))
                    except Exception as e:
                        self.logger.debug(f"Error updating progress: {e}")
                        break

            except Exception as e:
                self.logger.debug(f"Error in smart progress update thread: {e}")

        # Start the update thread
        try:
            thread = threading.Thread(target=update_progress, daemon=True)
            thread.start()
        except Exception as e:
            self.logger.debug(f"Could not start progress update thread: {e}")

    def create_api_progress(self, silent: bool = False) -> Optional[Any]:
        """Create a progress indicator for API requests with smart timing.

        Args:
            silent: If True, don't create visual progress indicator

        Returns:
            Progress indicator object or None
        """
        if silent or not self.display_manager:
            return None

        try:
            # Get timing configuration for smart progress
            timing_config = self.config.get("tool_management.response_timing", {})
            avg_time = timing_config.get("average_response_time", 10.0)

            # Use the average time as the total for the progress bar
            # This gives users a sense of expected completion time
            progress = self.display_manager.create_progress(
                token="api_request",
                title="Waiting for AI response",
                total=int(
                    avg_time * 10
                ),  # Convert to deciseconds for smoother progress
                show_immediately=True,
            )

            # Start a background task to update progress based on time
            self.start_smart_progress_update(progress, timing_config)

            return progress

        except Exception as e:
            self.logger.debug(f"Error creating API progress: {e}")
            return None

    def create_thinking_progress(self) -> Optional[Any]:
        """Create a progress indicator for AI thinking process.

        Returns:
            Progress indicator or None
        """
        if not self.display_manager:
            return None

        try:
            return self.display_manager.create_indeterminate_progress(
                token="thinking",
                title="AI is thinking...",
                show_immediately=True,
            )
        except Exception as e:
            self.logger.debug(f"Could not create thinking progress: {e}")
            return None

    def complete_progress(self, progress: Any, message: str = "") -> None:
        """Complete a progress indicator safely.

        Args:
            progress: Progress indicator to complete
            message: Optional completion message
        """
        if not progress:
            return

        try:
            progress.complete(message)
        except Exception as e:
            self.logger.debug(f"Error completing progress: {e}")

    def clear_all_progress(self) -> None:
        """Clear all progress indicators."""
        if not self.display_manager:
            return

        try:
            self.display_manager.clear_progress()
        except Exception as e:
            self.logger.debug(f"Could not clear progress displays: {e}")
