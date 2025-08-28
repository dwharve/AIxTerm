# Context Module

## Overview
The context module is the intelligent brain of AIxTerm, responsible for gathering, processing, and managing contextual information from the terminal environment. It provides sophisticated context management with token optimization, intelligent summarization, and dynamic context adaptation based on user queries.

## Key Components

### Core Context Management
- **TerminalContext**: Main context coordinator and orchestrator (terminal_context.py)
- **DirectoryHandler**: File and directory content processing with project type detection (directory_handler.py)
- **LogProcessor**: Modular terminal command history analysis with TTY-aware log management (log_processor/)
- **TokenManager**: Intelligent token budget management with tiktoken integration (token_manager.py)
- **ToolOptimizer**: Context-aware tool selection and prioritization (tool_optimizer.py)

### Context Sources
- TTY-specific terminal command history and output
- Current working directory contents with intelligent file categorization
- Project type detection (Python, Node.js, Java, Docker, Git, etc.)
- Token-optimized file contexts with content truncation
- User-specified file contexts with budget allocation

## Architecture

```
context/
├── __init__.py              # Module exports and imports
├── terminal_context.py      # Main TerminalContext coordinator
├── directory_handler.py     # File/directory processing with project detection
├── log_processor/           # Modular log analysis subsystem
│   ├── __init__.py         # Module exports
│   ├── processor.py        # Main LogProcessor with TTY-aware log handling
│   ├── parsing.py          # Command and conversation extraction
│   ├── summary.py          # Tiered intelligent summarization
│   ├── tokenization.py     # Text tokenization and truncation
│   └── tty_utils.py        # TTY detection and management
├── token_manager.py         # Token budget optimization with tiktoken
└── tool_optimizer.py        # Intelligent tool selection and context fitting
```

## Core Functionality

### Context Collection and Processing
- **Dynamic Context Assembly**: Intelligently allocates context budget across directory info, file content, and terminal history
- **TTY-Aware Log Management**: Uses dedicated TTY-specific logs (~/.aixterm/tty/{tty}.log) with fallback to default.log
- **Smart File Filtering**: Handles binary files, encoding issues, and excludes irrelevant content automatically
- **Project Type Detection**: Automatically identifies Python, Node.js, Java, Docker, Git, and other project types

### Token Optimization and Management
- **Intelligent Budget Allocation**: Distributes available context tokens across content types (directory: 15%, files: 60%, terminal: 25-40%)
- **Per-File Token Limits**: Applies individual file token limits while respecting total budget constraints
- **Model-Aware Tokenization**: Uses tiktoken for accurate token counting with graceful fallbacks
- **Context Window Management**: Ensures entire requests (messages + tools + context) fit within model limits

### Intelligent Summarization Features
- **Tiered Command Summarization**: Recent commands get full detail, older commands are abbreviated, ancient commands are counted
- **Error-Aware Processing**: Extracts and prioritizes error messages from terminal output
- **Command History Analysis**: Parses both traditional ($ command) and script formats (└──╼ $command)
- **Smart Content Truncation**: Applies token limits while preserving the most relevant information

### Tool Integration and Optimization
- **Context-Aware Tool Selection**: Prioritizes tools based on query keywords and functionality relevance
- **Token-Aware Tool Fitting**: Ensures tool definitions fit within available context budget
- **Tiered Tool Priorities**: Essential (1000) > File ops (800) > Development (600) > Data processing (400) > Web/network (300)
- **Intelligent Tool Management**: Handles context overflow by optimizing tools first, then removing tools, then trimming messages

## Integration Points
- **Main Module**: Primary consumer of optimized context information via get_optimized_context()
- **LLM Module**: Receives token-optimized context that fits within model limits
- **Config Module**: Provides context size limits, token budgets, and model configuration
- **Tool Management**: Integrates with tool optimization for context-aware tool selection
- **TTY System**: Manages per-TTY log files with automatic TTY detection and validation

## Performance Characteristics
- **On-Demand Processing**: Context is generated when requested to minimize overhead
- **Token-Aware Operations**: All operations respect token budgets to prevent context overflow
- **Efficient File Handling**: Handles binary files, encoding issues, and large files gracefully
- **Memory-Conscious Design**: Uses streaming and truncation to avoid memory issues with large logs
- **Modular Architecture**: Separated concerns allow for independent optimization of each component

## Dynamic Context Features

### Adaptive Context Allocation
The system dynamically allocates context budget based on content availability:
- **Directory context**: 10-15% of budget for project structure and file summaries
- **File contexts**: 40-60% of budget when files are specified, distributed across files
- **Terminal history**: Remaining budget, minimum 25% when files present, up to 40% when no files

### Intelligent Log Processing
- **Session Isolation**: Each TTY gets its own log file for better context accuracy
- **Smart Summarization**: Recent commands get full output, older commands are summarized
- **Error Detection**: Automatically identifies and highlights error messages and failures
- **Format Recognition**: Handles multiple terminal output formats and command styles

### Context Optimization Strategies
- **Query-Aware Prioritization**: Uses user queries to prioritize relevant context information
- **Progressive Degradation**: Removes less important context when hitting token limits
- **Model Compatibility**: Adapts token counting and limits based on the configured model
- **Fallback Mechanisms**: Graceful handling when primary context sources are unavailable
