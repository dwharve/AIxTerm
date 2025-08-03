# Display Module

This module provides a unified display system for AIxTerm, providing functionality for:

- Progress bars and spinners
- Streaming content output with thinking state handling
- Status message formatting and display
- Terminal control operations

## Module Structure

The module is organized into these files:

### 1. `types.py` 

Contains enum definitions for display types:
- `DisplayType`: Defines visual display styles (SIMPLE, PROGRESS_BAR, SPINNER, DETAILED)
- `MessageType`: Defines message categories (INFO, WARNING, ERROR, SUCCESS, TOOL_CALL)

### 2. `progress.py`

Contains classes for progress display:
- `_ProgressDisplay`: Implementation of tqdm-based progress displays
- `_MockProgress`: Mock implementation for use during shutdown

### 3. `manager.py`

Contains the main display manager:
- `DisplayManager`: Core class that manages all display functionality
- `create_display_manager`: Factory function to create a display manager with the specified style

## Usage

```python
from aixterm.display import create_display_manager, DisplayType

# Create a display manager with progress bars
display = create_display_manager("bar")

# Create a progress display
progress = display.create_progress(
    token="task1",
    title="Processing data",
    total=100
)

# Update progress
display.update_progress("task1", 50, "Halfway done")

# Complete progress
display.complete_progress("task1", "Task completed")

# Stream content
display.start_streaming()
display.stream_content("Hello, world!")
display.end_streaming()

# Show messages
display.show_error("Something went wrong")
display.show_success("Operation completed successfully")
```
