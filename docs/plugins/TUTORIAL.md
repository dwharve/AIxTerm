# Creating Your First AIxTerm Plugin

This tutorial will guide you through creating a simple AIxTerm plugin from scratch.

## Prerequisites

- AIxTerm 0.2.0 or higher
- Basic Python knowledge
- A development environment with Python 3.8+

## Step 1: Set Up Your Plugin Structure

First, create a directory for your plugin:

```bash
mkdir -p ~/dev/aixterm-calculator
cd ~/dev/aixterm-calculator
```

Create a basic Python package structure:

```
aixterm-calculator/
├── calculator/
│   └── __init__.py
├── setup.py
└── README.md
```

## Step 2: Implement the Plugin Class

Edit `calculator/__init__.py` to implement your plugin class:

```python
"""
Calculator Plugin for AIxTerm

A simple calculator plugin demonstrating the AIxTerm plugin system.
"""

from typing import Any, Dict, Callable

from aixterm.plugins import Plugin


class CalculatorPlugin(Plugin):
    """
    A calculator plugin for AIxTerm.
    
    This plugin provides basic arithmetic operations.
    """
    
    @property
    def id(self) -> str:
        """Get the plugin ID."""
        return "calculator"
    
    @property
    def name(self) -> str:
        """Get the plugin name."""
        return "Calculator"
    
    @property
    def version(self) -> str:
        """Get the plugin version."""
        return "0.1.0"
    
    @property
    def description(self) -> str:
        """Get the plugin description."""
        return "A calculator plugin providing basic arithmetic operations"
    
    def initialize(self) -> bool:
        """Initialize the plugin."""
        self.logger.info("Initializing Calculator plugin")
        return super().initialize()
    
    def shutdown(self) -> bool:
        """Shutdown the plugin."""
        self.logger.info("Shutting down Calculator plugin")
        return super().shutdown()
    
    def get_commands(self) -> Dict[str, Callable]:
        """Get the plugin commands."""
        return {
            "add": self.cmd_add,
            "subtract": self.cmd_subtract,
            "multiply": self.cmd_multiply,
            "divide": self.cmd_divide,
        }
    
    def cmd_add(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add two numbers.
        
        Args:
            data: Command data. Should contain 'a' and 'b' fields.
            
        Returns:
            Command result with 'result' field.
        """
        a = data.get("a", 0)
        b = data.get("b", 0)
        
        try:
            a = float(a)
            b = float(b)
            result = a + b
            
            return {
                "result": result,
                "operation": "addition",
                "a": a,
                "b": b
            }
        except ValueError as e:
            return {
                "error": f"Invalid numbers: {str(e)}"
            }
    
    def cmd_subtract(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Subtract b from a.
        
        Args:
            data: Command data. Should contain 'a' and 'b' fields.
            
        Returns:
            Command result with 'result' field.
        """
        a = data.get("a", 0)
        b = data.get("b", 0)
        
        try:
            a = float(a)
            b = float(b)
            result = a - b
            
            return {
                "result": result,
                "operation": "subtraction",
                "a": a,
                "b": b
            }
        except ValueError as e:
            return {
                "error": f"Invalid numbers: {str(e)}"
            }
    
    def cmd_multiply(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Multiply two numbers.
        
        Args:
            data: Command data. Should contain 'a' and 'b' fields.
            
        Returns:
            Command result with 'result' field.
        """
        a = data.get("a", 0)
        b = data.get("b", 0)
        
        try:
            a = float(a)
            b = float(b)
            result = a * b
            
            return {
                "result": result,
                "operation": "multiplication",
                "a": a,
                "b": b
            }
        except ValueError as e:
            return {
                "error": f"Invalid numbers: {str(e)}"
            }
    
    def cmd_divide(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Divide a by b.
        
        Args:
            data: Command data. Should contain 'a' and 'b' fields.
            
        Returns:
            Command result with 'result' field.
        """
        a = data.get("a", 0)
        b = data.get("b", 0)
        
        try:
            a = float(a)
            b = float(b)
            
            if b == 0:
                return {
                    "error": "Division by zero"
                }
            
            result = a / b
            
            return {
                "result": result,
                "operation": "division",
                "a": a,
                "b": b
            }
        except ValueError as e:
            return {
                "error": f"Invalid numbers: {str(e)}"
            }
```

## Step 3: Create setup.py

Create a `setup.py` file to make your plugin installable:

```python
from setuptools import setup, find_packages

setup(
    name="aixterm-calculator",
    version="0.1.0",
    description="Calculator plugin for AIxTerm",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(),
    install_requires=["aixterm>=0.2.0"],
    entry_points={
        "aixterm.plugins": [
            "calculator=calculator:CalculatorPlugin",
        ],
    },
)
```

## Step 4: Create a README.md

Create a README.md file with basic documentation:

```markdown
# AIxTerm Calculator Plugin

A simple calculator plugin for AIxTerm that provides basic arithmetic operations.

## Installation

```bash
pip install .
```

## Usage

After installing the plugin, you can use it with AIxTerm:

```bash
# List available plugins
aixterm plugin list

# Load the calculator plugin
aixterm plugin load calculator

# Add two numbers
aixterm plugin run calculator add --data '{"a": 5, "b": 3}'

# Subtract two numbers
aixterm plugin run calculator subtract --data '{"a": 10, "b": 4}'

# Multiply two numbers
aixterm plugin run calculator multiply --data '{"a": 6, "b": 7}'

# Divide two numbers
aixterm plugin run calculator divide --data '{"a": 20, "b": 5}'
```

## API

The calculator plugin provides the following commands:

- `add`: Add two numbers
- `subtract`: Subtract b from a
- `multiply`: Multiply two numbers
- `divide`: Divide a by b

Each command expects data with `a` and `b` fields.
```

## Step 5: Install Your Plugin

Install your plugin in development mode:

```bash
cd ~/dev/aixterm-calculator
pip install -e .
```

## Step 6: Test Your Plugin

Now you can test your plugin with AIxTerm:

```bash
# Start the AIxTerm service (if not already running)
aixterm service start

# List available plugins
aixterm plugin list

# You should see your calculator plugin in the list
# Load the calculator plugin
aixterm plugin load calculator

# Try using the plugin
aixterm plugin run calculator add --data '{"a": 5, "b": 3}'
```

You should see output like:

```json
{
  "result": 8.0,
  "operation": "addition",
  "a": 5.0,
  "b": 3.0
}
```

## Step 7: Add Plugin to AIxTerm Configuration

To have your plugin automatically loaded when AIxTerm starts, add it to your configuration:

```bash
# Open the AIxTerm configuration file
nano ~/.aixterm/config.yaml
```

Add your plugin to the `enabled_plugins` list:

```yaml
plugins:
  enabled_plugins:
    - calculator
  auto_discover: true
```

## Step 8: Create a Distribution

To create a distribution package for your plugin:

```bash
cd ~/dev/aixterm-calculator
python setup.py sdist bdist_wheel
```

This creates distribution files in the `dist` directory that can be installed with pip.

## Next Steps

Now that you've created a basic plugin, you can:

1. Add more advanced features to your calculator
2. Create unit tests for your plugin
3. Publish your plugin to PyPI
4. Create more complex plugins that integrate with external services

Congratulations on creating your first AIxTerm plugin!
