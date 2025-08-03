# Plugin System Guide

AIxTerm's plugin system allows you to extend the functionality of the service with custom plugins. This guide explains how to create, install, and manage plugins.

## Plugin Structure

An AIxTerm plugin is a Python class that inherits from the `aixterm.plugins.Plugin` base class. It must implement the### Plugin Dependencies

AIxTerm plugins can specify dependencies on other plugins. Dependencies are automatically loaded before the dependent plugin.

You can specify dependencies in two ways:

1. **Class Attribute**: Define a `dependencies` class attribute in your plugin class:

```python
class MyPlugin(Plugin):
    dependencies = ["other-plugin", "another-plugin"]
    
    @property
    def id(self) -> str:
        return "my-plugin"
    # ...
```

2. **Configuration**: Specify dependencies in the AIxTerm configuration:

```yaml
plugins:
  plugins:
    my-plugin:
      dependencies:
        - other-plugin
        - another-plugin
      settings:
        # Other plugin settings...
```

### Plugin Best Practices

1. **Unique IDs**: Ensure your plugin ID is unique and descriptive.
2. **Error Handling**: Handle errors gracefully in your command methods.
3. **Resource Management**: Clean up resources in the `shutdown()` method.
4. **Configuration**: Use the plugin configuration for customizable settings.
5. **Logging**: Use the provided logger (`self.logger`) for plugin logs.
6. **Dependencies**: Properly declare plugin dependencies to ensure correct loading order.ed properties and methods:

```python
from aixterm.plugins import Plugin

class MyPlugin(Plugin):
    @property
    def id(self) -> str:
        return "my-plugin"  # Unique identifier for the plugin
    
    @property
    def name(self) -> str:
        return "My Plugin"  # Human-readable name
    
    @property
    def version(self) -> str:
        return "0.1.0"  # Version string
    
    @property
    def description(self) -> str:
        return "My custom AIxTerm plugin"  # Optional description
    
    def initialize(self) -> bool:
        # Plugin initialization code here
        return super().initialize()
    
    def shutdown(self) -> bool:
        # Plugin cleanup code here
        return super().shutdown()
    
    def get_commands(self) -> dict:
        # Register plugin commands
        return {
            "my-command": self.cmd_my_command
        }
    
    def cmd_my_command(self, data):
        # Command implementation
        name = data.get("name", "World")
        return {"message": f"Hello, {name}!"}
```

## Plugin Lifecycle

Plugins go through the following lifecycle:

1. **Discovery**: The plugin manager discovers available plugins.
2. **Loading**: The plugin is instantiated and initialized.
3. **Execution**: The plugin commands are registered and can be called.
4. **Unloading**: The plugin is shut down and removed from the service.

## Creating a Plugin

To create a new plugin:

1. Create a new Python package or module that defines a class inheriting from `aixterm.plugins.Plugin`.
2. Implement the required properties and methods.
3. Install the plugin using one of the installation methods below.

### Example Plugin

Here's a complete example of a simple "Hello World" plugin:

```python
"""
Hello World Plugin for AIxTerm

A simple example plugin that demonstrates the AIxTerm plugin system.
"""

from typing import Any, Dict, Callable

from aixterm.plugins import Plugin


class HelloPlugin(Plugin):
    """
    A simple Hello World plugin for AIxTerm.
    
    This plugin demonstrates the basic structure of an AIxTerm plugin.
    """
    
    @property
    def id(self) -> str:
        """Get the plugin ID."""
        return "hello"
    
    @property
    def name(self) -> str:
        """Get the plugin name."""
        return "Hello World"
    
    @property
    def version(self) -> str:
        """Get the plugin version."""
        return "0.1.0"
    
    @property
    def description(self) -> str:
        """Get the plugin description."""
        return "A simple Hello World plugin for AIxTerm"
    
    def initialize(self) -> bool:
        """Initialize the plugin."""
        self.logger.info("Initializing Hello World plugin")
        return super().initialize()
    
    def shutdown(self) -> bool:
        """Shutdown the plugin."""
        self.logger.info("Shutting down Hello World plugin")
        return super().shutdown()
    
    def get_commands(self) -> Dict[str, Callable]:
        """Get the plugin commands."""
        return {
            "hello": self.cmd_hello,
            "hello_name": self.cmd_hello_name,
        }
    
    def cmd_hello(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the 'hello' command.
        
        Args:
            data: Command data.
            
        Returns:
            Command result.
        """
        return {
            "message": "Hello, World!"
        }
    
    def cmd_hello_name(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the 'hello_name' command.
        
        Args:
            data: Command data. Should contain a 'name' field.
            
        Returns:
            Command result.
        """
        name = data.get("name", "anonymous")
        return {
            "message": f"Hello, {name}!"
        }
```

## Plugin Installation Methods

There are three ways to install a plugin:

### 1. Built-in Plugins

Put your plugin code directly in the AIxTerm package:

```
aixterm/
├── plugins/
│   ├── __init__.py
│   ├── base.py
│   ├── manager.py
│   └── my_plugin/
│       └── __init__.py  # Contains your plugin class
```

### 2. Python Package Installation

Create a Python package and use the setuptools entry point system:

```python
# setup.py
from setuptools import setup, find_packages

setup(
    name="aixterm-my-plugin",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        "aixterm.plugins": [
            "my-plugin=my_plugin:MyPlugin",
        ],
    },
)
```

Then install with pip:

```
pip install .
```

### 3. User Plugin Directory

Place your plugin in the user plugin directory specified in the AIxTerm configuration:

```yaml
# ~/.aixterm/config.yaml
plugins:
  enabled_plugins:
    - my-plugin
  plugin_directory: "~/.aixterm/plugins"
```

Then create your plugin in that directory:

```
~/.aixterm/plugins/
└── my_plugin/
    └── __init__.py  # Contains your plugin class
```

## Managing Plugins with CLI

AIxTerm provides CLI commands for managing plugins:

### List Available Plugins

```
aixterm plugin list
```

With detailed information:

```
aixterm plugin list --verbose
```

### Show Plugin Information

```
aixterm plugin info hello
```

### Load a Plugin

```
aixterm plugin load hello
```

### Unload a Plugin

```
aixterm plugin unload hello
```

### Run a Plugin Command

```
aixterm plugin run hello hello
```

With parameters:

```
aixterm plugin run hello hello_name --data '{"name": "Alice"}'
```

### Show Plugin Status

```
aixterm plugin status
```

With detailed information:

```
aixterm plugin status --verbose
```

## Configuration

Configure plugins in your AIxTerm configuration file:

```yaml
# ~/.aixterm/config.yaml
plugins:
  # Enable plugin system
  enabled: true
  
  # Auto-discover plugins
  auto_discover: true
  
  # Plugins to enable at startup
  enabled_plugins:
    - hello
  
  # User plugin directory
  plugin_directory: "~/.aixterm/plugins"
  
  # Plugin-specific settings
  plugins:
    hello:
      settings:
        greeting: "Hello there"
```

## Using Plugin API in Code

To interact with plugins from your code:

```python
from aixterm.client import AIxTermClient

client = AIxTermClient()
client.connect()

# List available plugins
response = client.send_request("plugin.list", {})

# Run a plugin command
response = client.send_request(
    "plugin.command", 
    {"plugin_id": "hello", "command": "hello_name", "data": {"name": "Alice"}}
)
print(response["result"]["message"])  # Prints: Hello, Alice!
```

## Plugin Best Practices

1. **Unique IDs**: Ensure your plugin ID is unique and descriptive.
2. **Error Handling**: Handle errors gracefully in your command methods.
3. **Resource Management**: Clean up resources in the `shutdown()` method.
4. **Configuration**: Use the plugin configuration for customizable settings.
5. **Logging**: Use the provided logger (`self.logger`) for plugin logs.

## Troubleshooting

### Plugin Not Found

Make sure your plugin is installed correctly and the plugin ID matches.

### Plugin Fails to Load

Check your plugin's `initialize()` method and verify it returns `True` on success.

### Command Not Found

Ensure your `get_commands()` method returns the correct command names and handler functions.

### Permission Issues

Check file permissions if using a user plugin directory.
