"""
DevTeam Plugin Events Module

This module provides event types and an event bus for the DevTeam plugin.
Events are used for communication between components of the plugin.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

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

    # Agent events
    AGENT_ASSIGNED = "agent_assigned"
    AGENT_STARTED_WORK = "agent_started_work"
    AGENT_COMPLETED_WORK = "agent_completed_work"
    AGENT_FAILED = "agent_failed"

    # Workflow events
    WORKFLOW_CREATED = "workflow_created"
    WORKFLOW_UPDATED = "workflow_updated"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"

    # System events
    SYSTEM_ERROR = "system_error"
    SYSTEM_INFO = "system_info"


class Event:
    """
    Base class for all events in the DevTeam plugin.

    An event represents something that has happened in the system that
    other components might be interested in.
    """

    def __init__(
        self,
        event_type: EventType,
        source: str,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ):
        """
        Initialize an event.

        Args:
            event_type: The type of event.
            source: The source of the event (e.g., component name).
            data: The event data.
            timestamp: The event timestamp (defaults to now).
        """
        self.event_type = event_type
        self.source = source
        self.data = data
        self.timestamp = timestamp or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the event to a dictionary.

        Returns:
            A dictionary representation of the event.
        """
        return {
            "event_type": self.event_type.value,
            "source": self.source,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, event_dict: Dict[str, Any]) -> "Event":
        """
        Create an event from a dictionary.

        Args:
            event_dict: The event dictionary.

        Returns:
            An event instance.
        """
        return cls(
            event_type=EventType(event_dict["event_type"]),
            source=event_dict["source"],
            data=event_dict["data"],
            timestamp=datetime.fromisoformat(event_dict["timestamp"]),
        )


class TaskEvent(Event):
    """Event related to a task."""

    def __init__(
        self,
        event_type: EventType,
        source: str,
        task_id: str,
        data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ):
        """
        Initialize a task event.

        Args:
            event_type: The event type.
            source: The source of the event.
            task_id: The ID of the task.
            data: Additional event data.
            timestamp: The event timestamp.
        """
        if data is None:
            data = {}

        data["task_id"] = task_id
        super().__init__(event_type, source, data, timestamp)

        self.task_id = task_id


class AgentEvent(Event):
    """Event related to an agent."""

    def __init__(
        self,
        event_type: EventType,
        source: str,
        agent_id: str,
        data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ):
        """
        Initialize an agent event.

        Args:
            event_type: The event type.
            source: The source of the event.
            agent_id: The ID of the agent.
            data: Additional event data.
            timestamp: The event timestamp.
        """
        if data is None:
            data = {}

        data["agent_id"] = agent_id
        super().__init__(event_type, source, data, timestamp)

        self.agent_id = agent_id


class WorkflowEvent(Event):
    """Event related to a workflow."""

    def __init__(
        self,
        event_type: EventType,
        source: str,
        workflow_id: str,
        data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ):
        """
        Initialize a workflow event.

        Args:
            event_type: The event type.
            source: The source of the event.
            workflow_id: The ID of the workflow.
            data: Additional event data.
            timestamp: The event timestamp.
        """
        if data is None:
            data = {}

        data["workflow_id"] = workflow_id
        super().__init__(event_type, source, data, timestamp)

        self.workflow_id = workflow_id


class EventBus:
    """
    Event bus for the DevTeam plugin.

    The event bus allows components to publish events and subscribe to event types.
    """

    def __init__(self):
        """Initialize the event bus."""
        self._subscribers = {}
        self._history: List[Event] = []
        self._max_history = 1000
        self._lock = asyncio.Lock()

    def subscribe(
        self, event_type: EventType, callback: Callable[[Event], None]
    ) -> None:
        """
        Subscribe to events of a given type.

        Args:
            event_type: The event type to subscribe to.
            callback: The callback function to call when an event of this type is published.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = set()

        self._subscribers[event_type].add(callback)
        logger.debug(f"Subscribed to {event_type.value} events")

    def unsubscribe(
        self, event_type: EventType, callback: Callable[[Event], None]
    ) -> None:
        """
        Unsubscribe from events of a given type.

        Args:
            event_type: The event type to unsubscribe from.
            callback: The callback function to unsubscribe.
        """
        if event_type in self._subscribers:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"Unsubscribed from {event_type.value} events")

            # Remove the set if it's empty
            if not self._subscribers[event_type]:
                del self._subscribers[event_type]

    async def publish(self, event: Event) -> None:
        """
        Publish an event.

        Args:
            event: The event to publish.
        """
        # Add to history (with max size limit)
        async with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history :]

        # Notify subscribers
        subscribers = self._subscribers.get(event.event_type, set())
        logger.debug(
            f"Publishing {event.event_type.value} event to {len(subscribers)} subscribers"
        )

        for callback in subscribers:
            try:
                # Call the callback with the event
                # Note: We're not awaiting these, assuming they're sync functions
                # If async callbacks are needed, this would need to be modified
                callback(event)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

    def get_history(
        self, event_types: Optional[List[EventType]] = None, limit: int = 100
    ) -> List[Event]:
        """
        Get event history.

        Args:
            event_types: Optional list of event types to filter by.
            limit: Maximum number of events to return.

        Returns:
            A list of events.
        """
        if event_types:
            # Filter by event types
            events = [e for e in self._history if e.event_type in event_types]
        else:
            events = self._history.copy()

        # Return the most recent events up to the limit
        return events[-limit:]
