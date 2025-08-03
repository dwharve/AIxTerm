"""
Type definitions for the DevTeam plugin.

This module contains enums and type definitions used throughout the DevTeam plugin.
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


class TaskType(Enum):
    """Types of development tasks."""

    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    ANALYSIS = "analysis"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    SECURITY = "security"
    PERFORMANCE = "performance"


class TaskPriority(Enum):
    """Task priority levels."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class TaskStatus(Enum):
    """Task execution status."""

    SUBMITTED = "submitted"
    QUEUED = "queued"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    UNDER_REVIEW = "under_review"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowType(Enum):
    """Types of development workflows."""

    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"


class WorkflowStatus(Enum):
    """Workflow execution status."""

    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRole(Enum):
    """Roles for AI agents in the development team."""

    PROJECT_MANAGER = "project_manager"
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    QA = "qa"
    DOCUMENTATION = "documentation"


# Type aliases for better code readability
TaskId = str
WorkflowId = str
AgentId = str
EventId = str

# Common data structures
TaskData = Dict[str, Any]
WorkflowData = Dict[str, Any]
AgentData = Dict[str, Any]
EventData = Dict[str, Any]
CommandResponse = Dict[str, Any]
