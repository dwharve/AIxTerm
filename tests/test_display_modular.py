"""Tests for the display module.

These tests verify the functionality of the modularized display system.
"""


def test_display_types():
    """Test that display types can be created and used correctly."""
    from aixterm.display.types import DisplayType

    # Test that all display types can be instantiated
    assert DisplayType.SIMPLE.value == "simple"
    assert DisplayType.PROGRESS_BAR.value == "bar"
    assert DisplayType.SPINNER.value == "spinner"
    assert DisplayType.DETAILED.value == "detailed"

    # Test that the display type can be looked up from a string
    assert DisplayType("simple") == DisplayType.SIMPLE
    assert DisplayType("bar") == DisplayType.PROGRESS_BAR


def test_message_types():
    """Test that message types can be created and used correctly."""
    from aixterm.display.types import MessageType

    # Test that all message types can be instantiated
    assert MessageType.INFO.value == "info"
    assert MessageType.WARNING.value == "warning"
    assert MessageType.ERROR.value == "error"
    assert MessageType.SUCCESS.value == "success"
    assert MessageType.TOOL_CALL.value == "tool_call"


def test_create_display_manager():
    """Test that display manager can be created with the factory function."""
    import aixterm.display

    # Test that the factory function creates a display manager
    manager = aixterm.display.create_display_manager()
    assert manager is not None

    # Test with explicit display type
    manager = aixterm.display.create_display_manager("spinner")
    assert manager.default_display_type == aixterm.display.DisplayType.SPINNER
