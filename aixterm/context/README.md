# Context Module

## Overview
The context module is the intelligent brain of AIxTerm, responsible for gathering, processing, and managing contextual information from the terminal environment. It provides sophisticated context management with token optimization and intelligent summarization.

## Key Components

### Core Context Management
- **TerminalContext**: Main context coordinator and orchestrator (terminal_context.py)
- **DirectoryHandler**: File and directory content processing (directory_handler.py)
- **LogProcessor**: Terminal command history analysis and insights (log_processor/)
- **TokenManager**: Intelligent token budget management and optimization (token_manager.py)
- **ToolOptimizer**: Smart tool selection based on context (tool_optimizer.py)

### Context Sources
- Terminal command history and output
- Current working directory contents
- File modifications and git status
- Environment variables and system state
- User-specified file contexts

## Architecture

```
context/
├── __init__.py           # Module exports and imports
├── terminal_context.py   # Main TerminalContext coordinator
├── directory_handler.py  # File/directory processing
├── log_processor.py      # Standalone log processor (legacy)
├── log_processor/        # Modular log analysis subsystem
├── token_manager.py      # Token budget optimization
└── tool_optimizer.py     # Intelligent tool selection
```

## Core Functionality

### Context Collection
- **Automatic Discovery**: Scans terminal environment for relevant context
- **Smart Filtering**: Excludes irrelevant files (binaries, cache, etc.)
- **Git Integration**: Includes repository status and recent changes
- **Command History**: Analyzes recent terminal commands and outputs

### Token Optimization
- **Budget Management**: Respects LLM token limits intelligently
- **Priority Ranking**: Prioritizes most relevant context information
- **Summarization**: Compresses large contexts while preserving key information
- **Dynamic Adjustment**: Adapts context size based on query complexity

### Intelligence Features
- **Pattern Recognition**: Identifies common development patterns and workflows
- **Error Context**: Captures and analyzes error states and debugging information
- **Tool Recommendations**: Suggests optimal tools based on current context
- **Context Persistence**: Maintains context across multiple interactions

## Integration Points
- **Main Module**: Primary consumer of context information
- **LLM Module**: Receives optimized context for AI processing
- **Display Module**: Shows context information to users
- **Config Module**: Inherits context preferences and settings

## Performance Characteristics
- **Lazy Loading**: Context gathered on-demand to minimize overhead
- **Caching**: Intelligent caching of expensive operations
- **Incremental Updates**: Only processes changed files and directories
- **Memory Efficiency**: Optimized for long-running terminal sessions
