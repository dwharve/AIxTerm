# AIxTerm Main Module

This directory contains the modularized components of the AIxTerm main application logic, which was previously contained in a single large `main.py` file (now backed up as `main.py.bk`).

## Module Structure

The AIxTerm application logic is now divided into these modules:

### 1. `app.py`

The core AIxTerm application class that handles:
- Initialization and configuration
- Component setup and coordination
- Basic application flow
- Signal handling and graceful shutdown

### 2. `cli.py`

Command-line interface implementation that handles:
- Argument parsing
- Command routing
- Main entry point
- Integration with other modules

### 3. `tools_manager.py`

Tool management functionality:
- Listing available tools
- Executing tools
- Processing tool results

### 4. `status_manager.py`

Status reporting and maintenance:
- Displaying application status
- Managing context operations
- Running cleanup tasks
- Initializing configuration

### 5. `shell_integration.py`

Shell integration management:
- Installing shell integration
- Uninstalling shell integration
- Checking integration status

## Usage

The main entry point is now via the `main/__init__.py` file, which imports and uses these modular components. This preserves backward compatibility while making the codebase more maintainable.

```python
# Example usage of the modular components
from aixterm.main import AIxTermApp
from aixterm.main import ToolsManager

# Initialize application
app = AIxTermApp()

# Create tools manager
tools_manager = ToolsManager(app)

# List available tools
tools_manager.list_tools()
```

For backward compatibility, you can also use:

```python
from aixterm.main import AIxTerm

# This provides the same interface as the original main.py
app = AIxTerm()
app.list_tools()
```

## Benefits of Modularization

1. **Improved Maintainability**: Each module has a clear, focused responsibility
2. **Better Testability**: Modules can be tested in isolation
3. **Easier Navigation**: Smaller files make it easier to find and understand code
4. **Clearer Dependencies**: Module relationships are explicitly defined
5. **Extensibility**: New functionality can be added without modifying existing modules

## Migration Strategy

The original `main.py` is being maintained for backward compatibility during transition. Future development should use these modular components.

## Modularization Progress

Files modularized:
- ✅ `main.py` → `main/` module (July 2025)

Files to be modularized next (>600 lines):
- `context/log_processor.py` (613 lines)
- `service/installer.py` (615 lines)
- `llm/client.py` (1019 lines) - Partial work started with client_v2.py
