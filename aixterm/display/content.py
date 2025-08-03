"""Content streaming functionality for the display system."""

import re
import sys
import threading
from typing import Any, Optional

from ..utils import get_logger
from .types import DisplayType


class ContentStreamer:
    """Handles streaming content to the terminal with special tag processing."""

    def __init__(self, parent_manager: Any):  # Use Any to avoid circular imports
        """Initialize content streamer.

        Args:
            parent_manager: The DisplayManager instance that owns this streamer
        """
        self.logger = get_logger(__name__)
        self._parent = parent_manager

        # Streaming state
        self._streaming_active = False
        self._thinking_active = False
        self._thinking_progress: Optional[Any] = (
            None  # Using Any to avoid circular imports
        )

    def start_streaming(self, clear_progress: bool = True) -> None:
        """Start streaming content output.

        Args:
            clear_progress: Whether to clear progress displays first
        """
        if clear_progress:
            self._parent.clear_all_progress()
            self._parent.clear_terminal_line()
        self._streaming_active = True

    def stream_content(self, content: str, filter_thinking: bool = True) -> str:
        """Stream content to output, handling thinking tags if needed.

        Args:
            content: Content to stream
            filter_thinking: Whether to filter thinking content

        Returns:
            Content that was actually output (thinking content filtered)
        """
        if not content:
            return ""

        if filter_thinking:
            return self._process_thinking_content(content)
        else:
            print(content, end="", flush=True)
            return content

    def end_streaming(self, add_newline: bool = True) -> None:
        """End streaming content output.

        Args:
            add_newline: Whether to add a final newline
        """
        if self._streaming_active and add_newline:
            print()  # Add newline after streaming
        self._streaming_active = False

        # Clean up thinking progress if active
        if self._thinking_progress:
            try:
                self._thinking_progress.complete("Thinking complete")
            except Exception as e:
                self.logger.debug(f"Error completing thinking progress: {e}")
            finally:
                self._thinking_progress = None
        self._thinking_active = False

    def _process_thinking_content(self, content: str) -> str:
        """Process content for thinking tags and handle display appropriately.

        Args:
            content: Raw content that may contain thinking tags

        Returns:
            Content that was actually output (thinking filtered)
        """
        output_text = ""
        remaining_content = content

        while remaining_content:
            if not self._thinking_active:
                # Look for thinking start
                thinking_start = remaining_content.find("<thinking>")
                if thinking_start == -1:
                    # No thinking content, output everything
                    output_text += remaining_content
                    print(remaining_content, end="", flush=True)
                    break
                else:
                    # Output content before thinking
                    before_thinking = remaining_content[:thinking_start]
                    if before_thinking:
                        output_text += before_thinking
                        print(before_thinking, end="", flush=True)

                    # Start thinking mode
                    self._thinking_active = True
                    self._start_thinking_progress()
                    remaining_content = remaining_content[
                        thinking_start + 10 :
                    ]  # Skip "<thinking>"
            else:
                # In thinking mode, look for end
                thinking_end = remaining_content.find("</thinking>")
                if thinking_end == -1:
                    # No end tag yet, consume all remaining content silently
                    break
                else:
                    # End thinking mode
                    self._thinking_active = False
                    self._end_thinking_progress()
                    remaining_content = remaining_content[
                        thinking_end + 11 :
                    ]  # Skip "</thinking>"

        return output_text

    def filter_thinking_content(self, content: str) -> str:
        """Filter out thinking content from text (for non-streaming use).

        Args:
            content: Content that may contain thinking tags

        Returns:
            Content with thinking sections removed
        """
        # Remove thinking content using regex
        filtered = re.sub(r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL)

        # Clean up extra whitespace
        filtered = re.sub(r"\n\s*\n\s*\n", "\n\n", filtered)
        return filtered.strip()

    def _start_thinking_progress(self) -> None:
        """Start thinking progress indicator."""
        if not self._thinking_progress:
            try:
                self._thinking_progress = self._parent.create_progress(
                    token="thinking",
                    title="AI is thinking",
                    total=None,
                    display_type=DisplayType.SPINNER,
                    show_immediately=True,
                    clear_others=False,
                )
            except Exception as e:
                self.logger.debug(f"Error starting thinking progress: {e}")

    def _end_thinking_progress(self) -> None:
        """End thinking progress indicator."""
        if self._thinking_progress:
            try:
                self._parent.complete_progress("thinking", "")
            except Exception as e:
                self.logger.debug(f"Error ending thinking progress: {e}")
            finally:
                self._thinking_progress = None

    def show_thinking(self, thinking_content: str) -> None:
        """Show thinking content with special formatting.

        Args:
            thinking_content: The thinking content to show
        """
        if not thinking_content:
            return

        # Start streaming mode if not already active
        if not self._streaming_active:
            self.start_streaming()

        print("\033[3m\033[2m", end="")  # Italic and dim text
        print("Thinking:", file=sys.stderr)
        print(thinking_content, file=sys.stderr)
        print("\033[0m", end="")  # Reset formatting
        print("\n", end="", file=sys.stderr)

    def show_response(self, response_content: str) -> None:
        """Show response content with appropriate formatting.

        Args:
            response_content: The response content to show
        """
        if not response_content:
            return

        # Start streaming mode if not already active
        if not self._streaming_active:
            self.start_streaming()

        # Just print the response directly
        print(response_content)
