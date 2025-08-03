# DevTeam Plugin Submodule

This is the modularized version of the original plugin.py. It has been split into multiple files for better organization and maintainability.

## Files

- `__init__.py` - Exports the main DevTeamPlugin class
- `core.py` - Contains the main DevTeamPlugin class
- `command_handler.py` - Handles plugin commands
- `adaptive_learning.py` - Provides adaptive learning functionality
- `agent_management.py` - Manages agent registry
- `workflow_templates.py` - Provides workflow template creation

## Integration with Modules

This plugin submodule integrates with the following modules in the `modules/` directory:

- `types.py` - Type definitions and enums
- `config.py` - Configuration management
- `events.py` - Event system
- `task_manager.py` - Task creation, tracking, and management
- `workflow_engine.py` - Workflow creation, execution, and management

## Main Functionality

The DevTeam plugin provides:

1. **Task Management** - Creation, tracking, and cancellation of development tasks
2. **Workflow Engine** - Orchestration of complex development workflows
3. **Agent Management** - Registry and coordination of specialized development agents
4. **Adaptive Learning** - Performance tracking and prompt optimization

## Usage

The plugin is accessed through the main DevTeamPlugin class, which registers command handlers for:

- `devteam:submit` - Submit a new development task
- `devteam:list` - List all current tasks
- `devteam:status` - Check the status of a specific task
- `devteam:cancel` - Cancel a running task

## Testing

All plugin functionality is tested in:
- `tests/test_devteam_plugin.py` - Basic plugin functionality
- `tests/test_devteam_agents.py` - Agent management
- `tests/test_adaptive_learning.py` - Adaptive learning system
