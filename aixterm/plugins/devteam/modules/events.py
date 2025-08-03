"""
Event system for the DevTeam plugin.

This module provides an event bus for plugin components to communicate through events.
"""

import asyncio
import logging
import uuid
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

from .types import EventData, EventId, TaskId, WorkflowId

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events in the DevTeam plugin."""

    # Task events
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"

    # Workflow events
    WORKFLOW_CREATED = "workflow_created"
    WORKFLOW_UPDATED = "workflow_updated"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    WORKFLOW_STEP_STARTED = "workflow_step_started"
    WORKFLOW_STEP_COMPLETED = "workflow_step_completed"

    # Agent events
    AGENT_TASK_ASSIGNED = "agent_task_assigned"
    AGENT_TASK_STARTED = "agent_task_started"
    AGENT_TASK_COMPLETED = "agent_task_completed"
    AGENT_TASK_FAILED = "agent_task_failed"

    # System events
    PLUGIN_INITIALIZED = "plugin_initialized"
    PLUGIN_SHUTDOWN = "plugin_shutdown"
    CONFIG_UPDATED = "config_updated"


class Event:
    """Base event class for the DevTeam plugin event system."""

    def __init__(
        self,
        event_type: EventType,
        data: Optional[Dict[str, Any]] = None,
        event_id: Optional[EventId] = None,
    ):
        """
        Initialize an event.

        Args:
            event_type: Type of the event
            data: Event data (optional)
            event_id: Unique event ID (auto-generated if not provided)
        """
        self.event_id = event_id or str(uuid.uuid4())
        self.event_type = event_type
        self.data = data or {}

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the event to a dictionary.

        Returns:
            Dictionary representation of the event.
        """
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, event_dict: Dict[str, Any]) -> "Event":
        """
        Create an event from a dictionary.

        Args:
            event_dict: Dictionary containing event data

        Returns:
            Event object.
        """
        event_type_value = event_dict.get("event_type")
        event_type = EventType(event_type_value)

        return cls(
            event_type=event_type,
            data=event_dict.get("data", {}),
            event_id=event_dict.get("event_id"),
        )


class TaskEvent(Event):
    """Event related to a task."""

    def __init__(
        self,
        event_type: EventType,
        task_id: TaskId,
        data: Optional[Dict[str, Any]] = None,
        event_id: Optional[EventId] = None,
    ):
        """
        Initialize a task event.

        Args:
            event_type: Type of the event
            task_id: ID of the task
            data: Event data (optional)
            event_id: Unique event ID (auto-generated if not provided)
        """
        super().__init__(event_type, data, event_id)
        self.task_id = task_id
        self.data["task_id"] = task_id

    @classmethod
    def from_dict(cls, event_dict: Dict[str, Any]) -> "TaskEvent":
        """
        Create a task event from a dictionary.

        Args:
            event_dict: Dictionary containing event data

        Returns:
            TaskEvent object.
        """
        event_type_value = event_dict.get("event_type")
        event_type = EventType(event_type_value)
        data = event_dict.get("data", {})
        task_id = data.get("task_id")

        if not task_id:
            raise ValueError("Task event requires a task_id")

        return cls(
            event_type=event_type,
            task_id=task_id,
            data=data,
            event_id=event_dict.get("event_id"),
        )


class WorkflowEvent(Event):
    """Event related to a workflow."""

    def __init__(
        self,
        event_type: EventType,
        workflow_id: WorkflowId,
        data: Optional[Dict[str, Any]] = None,
        event_id: Optional[EventId] = None,
    ):
        """
        Initialize a workflow event.

        Args:
            event_type: Type of the event
            workflow_id: ID of the workflow
            data: Event data (optional)
            event_id: Unique event ID (auto-generated if not provided)
        """
        super().__init__(event_type, data, event_id)
        self.workflow_id = workflow_id
        self.data["workflow_id"] = workflow_id


# Type for event handlers
EventHandler = Callable[[Event], None]
AsyncEventHandler = Callable[[Event], Awaitable[Any]]


class EventBus:
    """Event bus for the DevTeam plugin."""

    def __init__(self):
        """Initialize the event bus."""
        self._subscribers: Dict[EventType, Set[EventHandler]] = {}
        self._async_subscribers: Dict[EventType, Set[AsyncEventHandler]] = {}
        self._all_subscribers: Set[EventHandler] = set()
        self._all_async_subscribers: Set[AsyncEventHandler] = set()
        self._event_history: List[Event] = []
        self._max_history = 1000

    def subscribe(
        self, event_type: EventType, handler: EventHandler, store_history: bool = True
    ) -> None:
        """
        Subscribe to an event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Function to call when event is published
            store_history: Whether to store events in history
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = set()

        self._subscribers[event_type].add(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """
        Subscribe to all events.

        Args:
            handler: Function to call when any event is published
        """
        self._all_subscribers.add(handler)

    def async_subscribe(
        self, event_type: EventType, handler: AsyncEventHandler
    ) -> None:
        """
        Subscribe to an event type with an async handler.

        Args:
            event_type: Type of event to subscribe to
            handler: Async function to call when event is published
        """
        if event_type not in self._async_subscribers:
            self._async_subscribers[event_type] = set()

        self._async_subscribers[event_type].add(handler)

    def async_subscribe_all(self, handler: AsyncEventHandler) -> None:
        """
        Subscribe to all events with an async handler.

        Args:
            handler: Async function to call when any event is published
        """
        self._all_async_subscribers.add(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> bool:
        """
        Unsubscribe from an event type.

        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler to remove

        Returns:
            True if unsubscribed successfully, False otherwise
        """
        if event_type in self._subscribers and handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            return True
        return False

    def unsubscribe_all(self, handler: EventHandler) -> bool:
        """
        Unsubscribe from all events.

        Args:
            handler: Handler to remove

        Returns:
            True if unsubscribed successfully, False otherwise
        """
        if handler in self._all_subscribers:
            self._all_subscribers.remove(handler)
            return True
        return False

    def publish(self, event: Event) -> None:
        """
        Publish an event to subscribers.

        Args:
            event: Event to publish
        """
        # Store event in history
        self._add_to_history(event)

        # Notify all subscribers
        for handler in self._all_subscribers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")

        # Notify subscribers for this event type
        event_type = event.event_type
        if event_type in self._subscribers:
            for handler in self._subscribers[event_type]:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")

        # Process async subscribers in the background
        if (
            event_type in self._async_subscribers
            and self._async_subscribers[event_type]
        ) or self._all_async_subscribers:
            asyncio.create_task(self._process_async_subscribers(event))

    async def _process_async_subscribers(self, event: Event) -> None:
        """
        Process async subscribers for an event.

        Args:
            event: Event to process
        """
        # Notify all async subscribers
        for handler in self._all_async_subscribers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Error in async event handler: {e}")

        # Notify async subscribers for this event type
        event_type = event.event_type
        if event_type in self._async_subscribers:
            for handler in self._async_subscribers[event_type]:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Error in async event handler: {e}")

    def _add_to_history(self, event: Event) -> None:
        """
        Add an event to the history.

        Args:
            event: Event to add
        """
        self._event_history.append(event)

        # Trim history if needed
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history :]

    def get_history(self, limit: int = 100) -> List[Event]:
        """
        Get event history.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent events.
        """
        return self._event_history[-limit:]
