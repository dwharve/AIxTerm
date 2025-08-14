# Plugin API Reference

This document provides a detailed reference of the AIxTerm plugin API.

## Plugin Base Class

The `Plugin` class is the base class for all AIxTerm plugins. It provides the core functionality and interface that all plugins must implement.

### Properties

| Property | Type | Description | Required |
|----------|------|-------------|----------|
| `id` | `str` | Unique identifier for the plugin | Yes |
| `name` | `str` | Human-readable name of the plugin | Yes |
| `version` | `str` | Version string of the plugin | Yes |
| `description` | `str` | Description of the plugin | No |

### Methods

| Method | Description | Parameters | Return Type |
|--------|-------------|------------|------------|
| `__init__(service)` | Constructor | `service`: The AIxTerm service instance | - |
| `initialize()` | Initialize the plugin | - | `bool`: Success status |
| `shutdown()` | Clean up and shut down the plugin | - | `bool`: Success status |
| `get_commands()` | Get the commands provided by the plugin | - | `Dict[str, Callable]`: Map of command names to handler functions |
| `handle_request(request)` | Handle a plugin request | `request`: Request data | `Dict[str, Any]`: Response data |
| `status()` | Get the status of the plugin | - | `Dict[str, Any]`: Status information |

## Plugin Manager

The `PluginManager` class manages the lifecycle of plugins, including discovery, loading, and unloading.

### Methods

| Method | Description | Parameters | Return Type |
|--------|-------------|------------|------------|
| `__init__(service)` | Constructor | `service`: The AIxTerm service instance | - |
| `discover_plugins()` | Discover available plugins | - | `Dict[str, Type[Plugin]]`: Map of plugin IDs to plugin classes |
| `load_plugin(plugin_id)` | Load a specific plugin | `plugin_id`: Plugin ID | `bool`: Success status |
| `load_plugins()` | Load all enabled plugins | - | `bool`: Success status |
| `unload_plugin(plugin_id)` | Unload a specific plugin | `plugin_id`: Plugin ID | `bool`: Success status |
| `unload_plugins()` | Unload all plugins | - | `bool`: Success status |
| `handle_request(plugin_id, request)` | Route a request to a plugin | `plugin_id`: Plugin ID, `request`: Request data | `Dict[str, Any]`: Response data |
| `get_status()` | Get the status of all plugins | - | `Dict[str, Any]`: Status information |
| `check_plugin_dependencies(plugin_id)` | Check dependencies for a plugin | `plugin_id`: Plugin ID | `Dict[str, Any]`: Dependency status information |

## Plugin Service Handlers

The `PluginServiceHandlers` class provides API endpoints for interacting with plugins through the AIxTerm service.

### Methods

| Method | Description | Parameters | Return Type |
|--------|-------------|------------|------------|
| `__init__(service)` | Constructor | `service`: The AIxTerm service instance | - |
| `register_handlers()` | Register plugin-related handlers | - | `Dict[str, Callable]`: Map of endpoint names to handler functions |
| `handle_list_plugins(request)` | Handle a request to list plugins | `request`: Request data | `Dict[str, Any]`: Response data |
| `handle_plugin_info(request)` | Handle a request to get plugin info | `request`: Request data | `Dict[str, Any]`: Response data |
| `handle_plugin_status(request)` | Handle a request to get plugin status | `request`: Request data | `Dict[str, Any]`: Response data |
| `handle_load_plugin(request)` | Handle a request to load a plugin | `request`: Request data | `Dict[str, Any]`: Response data |
| `handle_unload_plugin(request)` | Handle a request to unload a plugin | `request`: Request data | `Dict[str, Any]`: Response data |
| `handle_plugin_command(request)` | Handle a request to execute a plugin command | `request`: Request data | `Dict[str, Any]`: Response data |

## Plugin CLI Commands

The plugin CLI provides commands for managing plugins through the command line.

### Functions

| Function | Description | Parameters |
|----------|-------------|------------|
| `register_plugin_commands(subparsers)` | Register plugin-related commands | `subparsers`: argparse subparsers object |
| `handle_plugin_command(args, client)` | Handle plugin-related CLI commands | `args`: Parsed command-line arguments, `client`: AIxTerm client instance |
| `handle_list_plugins(args, client)` | Handle the 'plugin list' command | `args`: Parsed command-line arguments, `client`: AIxTerm client instance |
| `handle_plugin_info(args, client)` | Handle the 'plugin info' command | `args`: Parsed command-line arguments, `client`: AIxTerm client instance |
| `handle_load_plugin(args, client)` | Handle the 'plugin load' command | `args`: Parsed command-line arguments, `client`: AIxTerm client instance |
| `handle_unload_plugin(args, client)` | Handle the 'plugin unload' command | `args`: Parsed command-line arguments, `client`: AIxTerm client instance |
| `handle_run_plugin_command(args, client)` | Handle the 'plugin run' command | `args`: Parsed command-line arguments, `client`: AIxTerm client instance |
| `handle_plugin_status(args, client)` | Handle the 'plugin status' command | `args`: Parsed command-line arguments, `client`: AIxTerm client instance |

## Plugin Configuration

Plugin configuration is defined in the AIxTerm configuration file:

```yaml
plugins:
  # Enable plugin system
  enabled: true
  
  # Auto-discover plugins
  auto_discover: true
  
  # Plugins to enable at startup
  enabled_plugins:
    - plugin1
    - plugin2
  
  # User plugin directory
  plugin_directory: "~/.aixterm/plugins"
  
  # Plugin-specific settings
  plugins:
    plugin1:
      settings:
        setting1: value1
        setting2: value2
    plugin2:
      settings:
        setting3: value3
```

### Plugin Configuration Schema

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | `bool` | Enable/disable the plugin system |
| `auto_discover` | `bool` | Automatically discover and load available plugins |
| `enabled_plugins` | `List[str]` | List of plugin IDs to enable at startup |
| `plugin_directory` | `str` | Directory for user-installed plugins |
| `plugins` | `Dict[str, Dict]` | Plugin-specific settings |

## Plugin Dependencies

Plugins can declare dependencies on other plugins. Dependencies are managed by the Plugin Manager and are automatically resolved during loading.

### Declaring Dependencies

There are two ways to declare plugin dependencies:

1. **Static class attribute**:
```python
class MyPlugin(Plugin):
    dependencies = ["other-plugin", "another-plugin"]
    
    @property
    def id(self) -> str:
        return "my-plugin"
    # ...
```

2. **Configuration**:
```yaml
plugins:
  plugins:
    my-plugin:
      dependencies:
        - other-plugin
        - another-plugin
```

### Dependency Status Format

The dependency status information returned by `check_plugin_dependencies()` has the following format:

```json
{
  "satisfied": false,
  "missing": ["missing-plugin1", "missing-plugin2"],
  "available": ["available-plugin1"],
  "loaded": ["loaded-plugin1", "loaded-plugin2"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `satisfied` | `bool` | Whether all dependencies are satisfied (all required plugins are loaded) |
| `missing` | `List[str]` | List of dependencies that are not available (not installed) |
| `available` | `List[str]` | List of dependencies that are available but not loaded |
| `loaded` | `List[str]` | List of dependencies that are already loaded |
| `error` | `str` | Error message (only present if there was an error checking dependencies) |

## Plugin API Protocol

### Request Format

```json
{
  "endpoint": "plugin.command",
  "data": {
    "plugin_id": "devteam",
    "command": "submit",
    "data": {
      "title": "Example Task",
      "description": "Create a simple function"
    }
  }
}
```

### Response Format

```json
{
  "status": "success",
  "result": {
    "task_id": "task-123",
    "message": "Task submitted successfully"
  }
}
```

### Error Response Format

```json
{
  "status": "error",
  "error": {
    "code": "plugin_not_found",
    "message": "Plugin not found: nonexistent"
  }
}
```

## Plugin API Endpoints

| Endpoint | Description | Request Data | Response Data |
|----------|-------------|--------------|--------------|
| `plugin.list` | List available plugins | - | `plugins`: List of plugin information, `total`: Total number of plugins, `loaded`: Number of loaded plugins |
| `plugin.info` | Get plugin information | `plugin_id`: Plugin ID | `plugin`: Plugin information |
| `plugin.status` | Get plugin status | - | `plugin_status`: Plugin status information |
| `plugin.load` | Load a plugin | `plugin_id`: Plugin ID | `message`: Result message, `loaded`: Whether the plugin was loaded |
| `plugin.unload` | Unload a plugin | `plugin_id`: Plugin ID | `message`: Result message, `unloaded`: Whether the plugin was unloaded |
| `plugin.command` | Execute a plugin command | `plugin_id`: Plugin ID, `command`: Command name, `data`: Command data | `result`: Command result |
