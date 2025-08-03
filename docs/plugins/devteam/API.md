# DevTeam Plugin API Reference

This document provides the API reference for the DevTeam plugin in AIxTerm.

## Core Components

### DevTeamPlugin

The main plugin class responsible for task management, agent orchestration, and workflow management.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | `str` | Plugin identifier ("devteam") |
| `name` | `str` | Plugin name ("DevTeam") |
| `version` | `str` | Plugin version |
| `description` | `str` | Plugin description |
| `dependencies` | `List[str]` | Plugin dependencies |

#### Methods

| Method | Description | Parameters | Return Value |
|--------|-------------|------------|--------------|
| `initialize()` | Initialize the plugin | None | `bool`: Success status |
| `shutdown()` | Shutdown the plugin | None | `bool`: Success status |
| `get_commands()` | Get plugin commands | None | `Dict[str, Any]`: Command mapping |
| `handle_request(request)` | Handle plugin requests | `request`: Request data | `Dict[str, Any]`: Response |

## Task Management

### Task Types

Available task types defined in the `TaskType` enum:

| Type | Description |
|------|-------------|
| `FEATURE` | New feature development |
| `BUGFIX` | Bug fix implementation |
| `REFACTOR` | Code refactoring |
| `ANALYSIS` | Code or system analysis |
| `DOCUMENTATION` | Documentation work |
| `TESTING` | Testing-related tasks |
| `SECURITY` | Security-related tasks |
| `PERFORMANCE` | Performance optimization |

### Task Priorities

Available task priorities defined in the `TaskPriority` enum:

| Priority | Level | Description |
|----------|-------|-------------|
| `LOW` | 1 | Low priority task |
| `MEDIUM` | 2 | Medium priority task (default) |
| `HIGH` | 3 | High priority task |
| `URGENT` | 4 | Urgent priority task |
| `CRITICAL` | 5 | Critical priority task |

### Task Status

Available task statuses defined in the `TaskStatus` enum:

| Status | Description |
|--------|-------------|
| `SUBMITTED` | Task has been submitted |
| `QUEUED` | Task is in the queue |
| `PLANNING` | Task is in planning phase |
| `IN_PROGRESS` | Task is being worked on |
| `UNDER_REVIEW` | Task is being reviewed |
| `TESTING` | Task is being tested |
| `COMPLETED` | Task is completed |
| `FAILED` | Task has failed |
| `CANCELLED` | Task has been cancelled |

## API Endpoints

### Submit Task

Submit a new development task.

**Command**: `devteam:submit`

**Request**:
```json
{
  "command": "devteam:submit",
  "parameters": {
    "title": "Add login feature",
    "description": "Create a login form with validation",
    "type": "feature",
    "priority": "high"
  }
}
```

**Response**:
```json
{
  "success": true,
  "task_id": "task_20250715123045",
  "message": "Task submitted successfully: task_20250715123045"
}
```

### List Tasks

List all tasks or filter by status.

**Command**: `devteam:list`

**Request**:
```json
{
  "command": "devteam:list",
  "parameters": {
    "status": "in_progress"
  }
}
```

**Response**:
```json
{
  "success": true,
  "tasks": [
    {
      "id": "task_20250715123045",
      "title": "Add login feature",
      "type": "feature",
      "priority": "high",
      "status": "in_progress",
      "submitted_at": "2025-07-15T12:30:45.123456"
    }
  ]
}
```

### Task Status

Get detailed status of a specific task.

**Command**: `devteam:status`

**Request**:
```json
{
  "command": "devteam:status",
  "parameters": {
    "task_id": "task_20250715123045"
  }
}
```

**Response**:
```json
{
  "success": true,
  "task": {
    "id": "task_20250715123045",
    "title": "Add login feature",
    "description": "Create a login form with validation",
    "type": "feature",
    "priority": "high",
    "status": "in_progress",
    "progress": {
      "percent_complete": 60,
      "current_phase": "development",
      "estimated_completion": "2025-07-15T14:30:00"
    },
    "submitted_at": "2025-07-15T12:30:45.123456"
  }
}
```

### Cancel Task

Cancel a running or queued task.

**Command**: `devteam:cancel`

**Request**:
```json
{
  "command": "devteam:cancel",
  "parameters": {
    "task_id": "task_20250715123045"
  }
}
```

**Response**:
```json
{
  "success": true,
  "message": "Task cancelled: task_20250715123045"
}
```

## Error Handling

Error responses follow this format:

```json
{
  "success": false,
  "error": "Error message"
}
```

Common error scenarios:
- Missing required parameters
- Task not found
- Invalid task status
- Plugin not initialized

## Configuration Schema

The DevTeam plugin configuration schema:

```json
{
  "max_concurrent_tasks": 5,
  "default_timeout_hours": 24,
  "agent_timeout_minutes": 30,
  "agents": {
    "project_manager": { "enabled": true, "max_tasks": 10 },
    "architect": { "enabled": true, "max_tasks": 3 },
    "developer": { "enabled": true, "instances": 2, "max_tasks": 5 },
    "reviewer": { "enabled": true, "max_tasks": 8 },
    "qa": { "enabled": true, "max_tasks": 5 },
    "documentation": { "enabled": true, "max_tasks": 3 }
  },
  "workflow": {
    "require_architecture_review": true,
    "require_code_review": true,
    "require_testing": true,
    "require_documentation": true,
    "parallel_development": true
  }
}
```
