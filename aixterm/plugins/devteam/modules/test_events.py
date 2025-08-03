"""
Tests for the DevTeam plugin events module.
"""

from unittest.mock import Mock

import pytest

from aixterm.plugins.devteam.modules.events import (
    Event,
    EventBus,
    EventType,
    TaskEvent,
    WorkflowEvent,
)
from aixterm.plugins.devteam.modules.types import TaskId, WorkflowId


class TestEvents:
    """Tests for the events module."""

    def test_event_creation(self):
        """Test creating events."""
        event = Event(EventType.PLUGIN_INITIALIZED)
        assert event.event_type == EventType.PLUGIN_INITIALIZED
        assert event.data == {}
        assert event.event_id is not None

        event_with_data = Event(EventType.CONFIG_UPDATED, data={"key": "value"})
        assert event_with_data.event_type == EventType.CONFIG_UPDATED
        assert event_with_data.data == {"key": "value"}

    def test_task_event_creation(self):
        """Test creating task events."""
        task_id = "task-123"
        event = TaskEvent(
            EventType.TASK_CREATED, task_id=task_id, data={"title": "Test Task"}
        )

        assert event.event_type == EventType.TASK_CREATED
        assert event.task_id == task_id
        assert event.data["task_id"] == task_id
        assert event.data["title"] == "Test Task"

    def test_event_to_dict(self):
        """Test converting event to dictionary."""
        event = Event(
            EventType.PLUGIN_INITIALIZED,
            data={"version": "1.0.0"},
            event_id="event-123",
        )

        event_dict = event.to_dict()
        assert event_dict["event_id"] == "event-123"
        assert event_dict["event_type"] == EventType.PLUGIN_INITIALIZED.value
        assert event_dict["data"] == {"version": "1.0.0"}

    def test_event_from_dict(self):
        """Test creating event from dictionary."""
        event_dict = {
            "event_id": "event-123",
            "event_type": EventType.PLUGIN_INITIALIZED.value,
            "data": {"version": "1.0.0"},
        }

        event = Event.from_dict(event_dict)
        assert event.event_id == "event-123"
        assert event.event_type == EventType.PLUGIN_INITIALIZED
        assert event.data == {"version": "1.0.0"}


class TestEventBus:
    """Tests for the EventBus."""

    def test_subscribe_and_publish(self):
        """Test subscribing to events and publishing events."""
        event_bus = EventBus()
        handler = Mock()

        event_bus.subscribe(EventType.TASK_CREATED, handler)

        event = Event(EventType.TASK_CREATED, data={"task_id": "task-123"})
        event_bus.publish(event)

        handler.assert_called_once_with(event)

    def test_subscribe_all(self):
        """Test subscribing to all events."""
        event_bus = EventBus()
        handler = Mock()

        event_bus.subscribe_all(handler)

        event1 = Event(EventType.TASK_CREATED)
        event2 = Event(EventType.TASK_COMPLETED)

        event_bus.publish(event1)
        event_bus.publish(event2)

        assert handler.call_count == 2
        handler.assert_any_call(event1)
        handler.assert_any_call(event2)

    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        event_bus = EventBus()
        handler = Mock()

        event_bus.subscribe(EventType.TASK_CREATED, handler)
        event_bus.unsubscribe(EventType.TASK_CREATED, handler)

        event = Event(EventType.TASK_CREATED)
        event_bus.publish(event)

        handler.assert_not_called()

    def test_unsubscribe_all(self):
        """Test unsubscribing from all events."""
        event_bus = EventBus()
        handler = Mock()

        event_bus.subscribe_all(handler)
        event_bus.unsubscribe_all(handler)

        event = Event(EventType.TASK_CREATED)
        event_bus.publish(event)

        handler.assert_not_called()

    def test_get_history(self):
        """Test getting event history."""
        event_bus = EventBus()

        event1 = Event(EventType.TASK_CREATED, event_id="event-1")
        event2 = Event(EventType.TASK_COMPLETED, event_id="event-2")

        event_bus.publish(event1)
        event_bus.publish(event2)

        history = event_bus.get_history()
        assert len(history) == 2
        assert history[0].event_id == "event-1"
        assert history[1].event_id == "event-2"
