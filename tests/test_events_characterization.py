#!/usr/bin/env python3
"""
Characterization tests for aixterm.plugins.devteam.modules.events

These tests capture the current behavior of the events module to prevent
unintended changes during refactoring. They focus on testing the API
surface and key behaviors without testing implementation details.
"""

import asyncio
import pytest
from unittest.mock import Mock
from typing import List

from aixterm.plugins.devteam.modules.events import (
    Event,
    TaskEvent,
    WorkflowEvent,
    AgentEvent,
    EventType,
    EventBus,
    EventHandler,
    AsyncEventHandler,
)


class TestEventTypes:
    """Test EventType enum and its values."""

    def test_event_types_exist(self):
        """Test that all expected event types are defined."""
        # Task events
        assert EventType.TASK_CREATED.value == "task_created"
        assert EventType.TASK_UPDATED.value == "task_updated"
        assert EventType.TASK_STARTED.value == "task_started"
        assert EventType.TASK_COMPLETED.value == "task_completed"
        assert EventType.TASK_FAILED.value == "task_failed"
        assert EventType.TASK_CANCELLED.value == "task_cancelled"

        # Workflow events
        assert EventType.WORKFLOW_CREATED.value == "workflow_created"
        assert EventType.WORKFLOW_UPDATED.value == "workflow_updated"
        assert EventType.WORKFLOW_STARTED.value == "workflow_started"
        assert EventType.WORKFLOW_COMPLETED.value == "workflow_completed"
        assert EventType.WORKFLOW_FAILED.value == "workflow_failed"
        assert EventType.WORKFLOW_CANCELLED.value == "workflow_cancelled"
        assert EventType.WORKFLOW_STEP_STARTED.value == "workflow_step_started"
        assert EventType.WORKFLOW_STEP_COMPLETED.value == "workflow_step_completed"

        # Agent events (old and new)
        assert EventType.AGENT_ASSIGNED.value == "agent_assigned"
        assert EventType.AGENT_STARTED_WORK.value == "agent_started_work"
        assert EventType.AGENT_COMPLETED_WORK.value == "agent_completed_work"
        assert EventType.AGENT_FAILED.value == "agent_failed"
        assert EventType.AGENT_TASK_ASSIGNED.value == "agent_task_assigned"
        assert EventType.AGENT_TASK_STARTED.value == "agent_task_started"
        assert EventType.AGENT_TASK_COMPLETED.value == "agent_task_completed"
        assert EventType.AGENT_TASK_FAILED.value == "agent_task_failed"

        # System events
        assert EventType.SYSTEM_ERROR.value == "system_error"
        assert EventType.SYSTEM_INFO.value == "system_info"
        assert EventType.PLUGIN_INITIALIZED.value == "plugin_initialized"
        assert EventType.PLUGIN_SHUTDOWN.value == "plugin_shutdown"
        assert EventType.CONFIG_UPDATED.value == "config_updated"


class TestEvent:
    """Test base Event class."""

    def test_event_creation(self):
        """Test basic event creation."""
        event = Event(EventType.TASK_CREATED, {"key": "value"})

        assert event.event_type == EventType.TASK_CREATED
        assert event.data == {"key": "value"}
        assert event.event_id is not None
        assert isinstance(event.event_id, str)

    def test_event_creation_with_id(self):
        """Test event creation with specific ID."""
        event_id = "test-123"
        event = Event(EventType.TASK_CREATED, {"key": "value"}, event_id)

        assert event.event_id == event_id

    def test_event_creation_no_data(self):
        """Test event creation without data."""
        event = Event(EventType.TASK_CREATED)

        assert event.data == {}

    def test_event_to_dict(self):
        """Test event serialization to dictionary."""
        event = Event(EventType.TASK_CREATED, {"key": "value"}, "test-123")
        result = event.to_dict()

        expected = {
            "event_id": "test-123",
            "event_type": "task_created",
            "data": {"key": "value"},
        }
        assert result == expected

    def test_event_from_dict(self):
        """Test event deserialization from dictionary."""
        event_dict = {
            "event_id": "test-123",
            "event_type": "task_created",
            "data": {"key": "value"},
        }

        event = Event.from_dict(event_dict)

        assert event.event_id == "test-123"
        assert event.event_type == EventType.TASK_CREATED
        assert event.data == {"key": "value"}

    def test_event_from_dict_minimal(self):
        """Test event deserialization with minimal data."""
        event_dict = {"event_type": "task_created"}

        event = Event.from_dict(event_dict)

        assert event.event_type == EventType.TASK_CREATED
        assert event.data == {}
        # NOTE: The Event constructor auto-generates an ID if None is provided
        assert event.event_id is not None
        assert isinstance(event.event_id, str)


class TestTaskEvent:
    """Test TaskEvent class."""

    def test_task_event_creation(self):
        """Test TaskEvent creation."""
        task_id = "task-123"
        event = TaskEvent(EventType.TASK_CREATED, task_id, {"extra": "data"})

        assert event.event_type == EventType.TASK_CREATED
        assert event.task_id == task_id
        assert event.data["task_id"] == task_id
        assert event.data["extra"] == "data"

    def test_task_event_from_dict(self):
        """Test TaskEvent deserialization."""
        event_dict = {
            "event_type": "task_created",
            "data": {"task_id": "task-123", "extra": "data"},
            "event_id": "event-123",
        }

        event = TaskEvent.from_dict(event_dict)

        assert isinstance(event, TaskEvent)
        assert event.task_id == "task-123"
        assert event.data["extra"] == "data"

    def test_task_event_from_dict_missing_task_id(self):
        """Test TaskEvent deserialization fails without task_id."""
        event_dict = {"event_type": "task_created", "data": {"extra": "data"}}

        with pytest.raises(ValueError, match="Task event requires a task_id"):
            TaskEvent.from_dict(event_dict)


class TestWorkflowEvent:
    """Test WorkflowEvent class."""

    def test_workflow_event_creation(self):
        """Test WorkflowEvent creation."""
        workflow_id = "workflow-123"
        event = WorkflowEvent(
            EventType.WORKFLOW_CREATED, workflow_id, {"extra": "data"}
        )

        assert event.event_type == EventType.WORKFLOW_CREATED
        assert event.workflow_id == workflow_id
        assert event.data["workflow_id"] == workflow_id
        assert event.data["extra"] == "data"


class TestAgentEvent:
    """Test AgentEvent class."""

    def test_agent_event_creation(self):
        """Test AgentEvent creation."""
        agent_id = "agent-123"
        event = AgentEvent(EventType.AGENT_ASSIGNED, agent_id, {"extra": "data"})

        assert event.event_type == EventType.AGENT_ASSIGNED
        assert event.agent_id == agent_id
        assert event.data["agent_id"] == agent_id
        assert event.data["extra"] == "data"

    def test_agent_event_from_dict(self):
        """Test AgentEvent deserialization."""
        event_dict = {
            "event_type": "agent_assigned",
            "data": {"agent_id": "agent-123", "extra": "data"},
            "event_id": "event-123",
        }

        event = AgentEvent.from_dict(event_dict)

        assert isinstance(event, AgentEvent)
        assert event.agent_id == "agent-123"
        assert event.data["extra"] == "data"

    def test_agent_event_from_dict_missing_agent_id(self):
        """Test AgentEvent deserialization fails without agent_id."""
        event_dict = {"event_type": "agent_assigned", "data": {"extra": "data"}}

        with pytest.raises(ValueError, match="Agent event requires an agent_id"):
            AgentEvent.from_dict(event_dict)


class TestEventBus:
    """Test EventBus class."""

    def test_event_bus_creation(self):
        """Test EventBus creation."""
        bus = EventBus()
        assert bus is not None

    def test_subscribe_sync_handler(self):
        """Test subscribing to sync event handlers."""
        bus = EventBus()
        handler = Mock()

        bus.subscribe(EventType.TASK_CREATED, handler)

        # Verify handler is registered (internal state)
        assert EventType.TASK_CREATED in bus._subscribers
        assert handler in bus._subscribers[EventType.TASK_CREATED]

    def test_subscribe_all_events_sync(self):
        """Test subscribing to all events with sync handler."""
        bus = EventBus()
        handler = Mock()

        bus.subscribe_all(handler)

        # Verify handler is registered
        assert handler in bus._all_subscribers

    @pytest.mark.asyncio
    async def test_subscribe_async_handler(self):
        """Test subscribing to async event handlers."""
        bus = EventBus()

        async def handler(event):
            pass

        bus.async_subscribe(EventType.TASK_CREATED, handler)

        # Verify handler is registered
        assert EventType.TASK_CREATED in bus._async_subscribers
        assert handler in bus._async_subscribers[EventType.TASK_CREATED]

    @pytest.mark.asyncio
    async def test_subscribe_all_events_async(self):
        """Test subscribing to all events with async handler."""
        bus = EventBus()

        async def handler(event):
            pass

        bus.async_subscribe_all(handler)

        # Verify handler is registered
        assert handler in bus._all_async_subscribers

    def test_publish_event_sync(self):
        """Test publishing events to sync handlers."""
        bus = EventBus()
        handler = Mock()

        bus.subscribe(EventType.TASK_CREATED, handler)

        event = Event(EventType.TASK_CREATED, {"test": "data"})
        bus.publish(event)

        handler.assert_called_once_with(event)

    def test_publish_event_all_sync(self):
        """Test publishing events to all-event sync handlers."""
        bus = EventBus()
        handler = Mock()

        bus.subscribe_all(handler)

        event = Event(EventType.TASK_CREATED, {"test": "data"})
        bus.publish(event)

        handler.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_publish_event_async(self):
        """Test publishing events to async handlers."""
        bus = EventBus()
        handler_called = False

        async def handler(event):
            nonlocal handler_called
            handler_called = True

        bus.async_subscribe(EventType.TASK_CREATED, handler)

        event = Event(EventType.TASK_CREATED, {"test": "data"})
        bus.publish(event)

        # Give async handler time to run
        await asyncio.sleep(0.1)

        assert handler_called

    def test_unsubscribe_sync_handler(self):
        """Test unsubscribing sync handlers."""
        bus = EventBus()
        handler = Mock()

        bus.subscribe(EventType.TASK_CREATED, handler)
        bus.unsubscribe(EventType.TASK_CREATED, handler)

        event = Event(EventType.TASK_CREATED, {"test": "data"})
        bus.publish(event)

        handler.assert_not_called()

    def test_unsubscribe_all_sync_handler(self):
        """Test unsubscribing all-event sync handlers."""
        bus = EventBus()
        handler = Mock()

        bus.subscribe_all(handler)
        bus.unsubscribe_all(handler)

        event = Event(EventType.TASK_CREATED, {"test": "data"})
        bus.publish(event)

        handler.assert_not_called()

    @pytest.mark.skip(
        reason="Async unsubscribe methods not implemented in current EventBus"
    )
    @pytest.mark.asyncio
    async def test_unsubscribe_async_handler(self):
        """Test unsubscribing async handlers."""
        # NOTE: This test is skipped because the current EventBus implementation
        # does not provide async unsubscribe methods. This represents a gap in the API.
        bus = EventBus()
        handler_called = False

        async def handler(event):
            nonlocal handler_called
            handler_called = True

        bus.async_subscribe(EventType.TASK_CREATED, handler)
        # bus.async_unsubscribe(EventType.TASK_CREATED, handler)  # Not implemented

        event = Event(EventType.TASK_CREATED, {"test": "data"})
        bus.publish(event)

        # Give potential async handler time to run
        await asyncio.sleep(0.1)

        assert not handler_called

    def test_event_history(self):
        """Test event history functionality."""
        bus = EventBus()

        event1 = Event(EventType.TASK_CREATED, {"id": 1})
        event2 = Event(EventType.TASK_STARTED, {"id": 2})

        bus.publish(event1)
        bus.publish(event2)

        history = bus.get_history()

        assert len(history) == 2
        assert history[0] == event1
        assert history[1] == event2

    def test_event_history_with_limit(self):
        """Test event history with limit."""
        bus = EventBus()

        for i in range(5):
            event = Event(EventType.TASK_CREATED, {"id": i})
            bus.publish(event)

        history = bus.get_history(limit=3)

        assert len(history) == 3
        # Should get the last 3 events
        assert history[0].data["id"] == 2
        assert history[1].data["id"] == 3
        assert history[2].data["id"] == 4

    def test_handler_error_handling(self):
        """Test that errors in handlers don't break the event bus."""
        bus = EventBus()

        def failing_handler(event):
            raise RuntimeError("Handler error")

        working_handler = Mock()

        bus.subscribe(EventType.TASK_CREATED, failing_handler)
        bus.subscribe(EventType.TASK_CREATED, working_handler)

        event = Event(EventType.TASK_CREATED, {"test": "data"})

        # Should not raise exception
        bus.publish(event)

        # Working handler should still be called
        working_handler.assert_called_once_with(event)


class TestEventIntegration:
    """Integration tests for the events system."""

    @pytest.mark.asyncio
    async def test_mixed_sync_async_handlers(self):
        """Test that both sync and async handlers work together."""
        bus = EventBus()
        sync_called = False
        async_called = False

        def sync_handler(event):
            nonlocal sync_called
            sync_called = True

        async def async_handler(event):
            nonlocal async_called
            async_called = True

        bus.subscribe(EventType.TASK_CREATED, sync_handler)
        bus.async_subscribe(EventType.TASK_CREATED, async_handler)

        event = Event(EventType.TASK_CREATED, {"test": "data"})
        bus.publish(event)

        # Give async handler time to run
        await asyncio.sleep(0.1)

        assert sync_called
        assert async_called

    def test_task_event_workflow(self):
        """Test a typical task event workflow."""
        bus = EventBus()
        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe_all(handler)

        # Simulate task lifecycle
        task_id = "task-123"

        created_event = TaskEvent(
            EventType.TASK_CREATED, task_id, {"description": "Test task"}
        )
        bus.publish(created_event)

        started_event = TaskEvent(
            EventType.TASK_STARTED, task_id, {"started_by": "agent-1"}
        )
        bus.publish(started_event)

        completed_event = TaskEvent(
            EventType.TASK_COMPLETED, task_id, {"result": "success"}
        )
        bus.publish(completed_event)

        assert len(events_received) == 3
        assert events_received[0].event_type == EventType.TASK_CREATED
        assert events_received[1].event_type == EventType.TASK_STARTED
        assert events_received[2].event_type == EventType.TASK_COMPLETED

        # Verify all events have the same task_id
        for event in events_received:
            assert event.data["task_id"] == task_id


if __name__ == "__main__":
    pytest.main([__file__])
