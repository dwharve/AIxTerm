# Context Submodule

The Context submodule provides intelligent context management for AIxTerm's AI-powered terminal assistant. It implements a modular architecture with specialized components for handling different aspects of context processing, optimization, and management.

## Architecture

The context system is composed of five specialized components orchestrated by the main `TerminalContext` class:

```
TerminalContext (Main Coordinator)
├── DirectoryHandler (File/Project Context)
├── LogProcessor (Terminal History & Logs)
├── TokenManager (Token Estimation & Limits)
└── ToolOptimizer (Tool Selection & Optimization)
```

### Core Components

- **TerminalContext** - Main coordinator that orchestrates all context operations
- **DirectoryHandler** - Handles file reading, project detection, and directory context
- **LogProcessor** - Processes terminal logs and extracts conversation history  
- **TokenManager** - Manages token estimation and content truncation using tiktoken
- **ToolOptimizer** - Intelligently selects and optimizes tools for available context space

## Key Features

### 🧠 Modular Context Management
Each component handles a specific aspect of context processing, allowing for maintainable and extensible context operations.

### 📁 Intelligent File Context
- Project type detection (Python, Node.js, Docker, etc.)
- Important file identification (README, package.json, requirements.txt)
- Multi-file content integration with encoding fallback
- Size limits and safety checks

### 📊 Smart Log Processing
- TTY-based session isolation for accurate context
- Intelligent conversation history extraction from shell integration logs
- Command and output summarization
- Cross-session continuity

### � Token-Aware Optimization
- Accurate token estimation using tiktoken
- Intelligent content truncation strategies
- Context budget allocation across components
- Tool optimization for available token space

## API Reference

### TerminalContext

Main coordinator class that provides the primary interface for context operations.

```python
from aixterm.context import TerminalContext

context = TerminalContext(config_manager)
```

#### Core Methods

##### `get_terminal_context(include_files: bool = True, smart_summarize: bool = True) -> str`
Get comprehensive terminal context with optional file information and intelligent summarization.

```python
# Get full context with files and summarization
context_str = context.get_terminal_context(
    include_files=True, 
    smart_summarize=True
)

# Get minimal context without files  
minimal_context = context.get_terminal_context(include_files=False)
```

##### `get_optimized_context(file_contexts: Optional[List[str]] = None, query: str = "") -> str`
Get context optimized for available token budget with optional file inclusion.

```python
# Optimized context with specific files
optimized = context.get_optimized_context(
    file_contexts=["main.py", "config.json"],
    query="debug authentication issues"
)

# Query-optimized context without additional files
optimized = context.get_optimized_context(query="setup development environment")
```

##### `get_file_contexts(file_paths: List[str]) -> str`
Get formatted content from multiple files.

```python
file_content = context.get_file_contexts([
    "src/main.py",
    "tests/test_main.py", 
    "README.md"
])
```

##### `get_conversation_history(max_tokens: Optional[int] = None) -> List[Dict[str, str]]`
Extract structured conversation history from terminal logs.

```python
# Get recent conversation history
history = context.get_conversation_history(max_tokens=2000)
for message in history:
    print(f"{message['role']}: {message['content']}")
```

##### `optimize_tools_for_context(tools: List[Dict], query: str, available_tokens: int) -> List[Dict]`
Optimize tool selection for available context space.

```python
optimized_tools = context.optimize_tools_for_context(
    tools=available_tools,
    query="help with Python debugging",
    available_tokens=5000
)
```

##### `create_log_entry(command: str, result: str = "") -> None`
Create a log entry for a command (fallback method when shell integration unavailable).

**Note**: This is a fallback method. Primary log creation is handled by shell integration which provides automatic command capture and richer logging.

```python
# Fallback log creation (shell integration preferred)
context.create_log_entry("ls -la", "directory listing output")
```

### Component APIs

#### DirectoryHandler

Handles file and directory operations for context.

```python
# Direct component access
dir_handler = context.directory_handler

# Get directory context
dir_context = dir_handler.get_directory_context()

# Detect project type
project_type = dir_handler.detect_project_type(Path.cwd())

# Get file contexts with encoding handling
file_content = dir_handler.get_file_contexts(["file1.py", "file2.json"])
```

#### LogProcessor

Manages terminal log processing and conversation extraction.

```python
# Direct component access
log_processor = context.log_processor

# Find current session log file
log_file = log_processor.find_log_file()

# Process log with intelligent summarization
log_content = log_processor.read_and_process_log(
    log_file, max_tokens=3000, model_name="gpt-4", smart_summarize=True
)

# Extract conversation history
history = log_processor.get_conversation_history(max_tokens=2000)
```

#### TokenManager

Handles token estimation and content management.

```python
# Direct component access
token_manager = context.token_manager

# Estimate tokens for content
token_count = token_manager.estimate_tokens("Sample text content")

# Apply token limits to content
limited_content = token_manager.apply_token_limit(
    text=long_content, max_tokens=1000, model_name="gpt-4"
)

# Allocate context budget
budget = token_manager.allocate_context_budget(total_tokens=8000)
```

#### ToolOptimizer

Manages intelligent tool selection and optimization.

```python
# Direct component access
tool_optimizer = context.tool_optimizer

# Optimize tools for context
optimized_tools = tool_optimizer.optimize_tools_for_context(
    tools=all_tools, query="debug Python script", available_tokens=4000
)

# Prioritize tools by relevance
prioritized = tool_optimizer._prioritize_tools(tools, "file operations")
```

## Component Details

### DirectoryHandler Features

- **Project Detection**: Automatically detects Python, Node.js, Java, Docker, and other project types
- **Important Files**: Identifies key files like README, package.json, requirements.txt, Dockerfile
- **Encoding Support**: Handles UTF-8, Latin-1, and binary files with graceful fallbacks
- **Size Management**: Enforces file size limits (50KB individual, 200KB total)
- **File Type Counting**: Provides statistics on file types in directory

### LogProcessor Features

- **TTY-Based Sessions**: Uses TTY information for accurate session isolation
- **Log File Processing**: Reads log files created by shell integration
- **Intelligent Parsing**: Extracts commands, outputs, and AI conversations from shell logs
- **Smart Summarization**: Compresses long logs while preserving important information
- **Conversation Extraction**: Separates AI interactions from regular terminal output
- **Cross-Platform Support**: Works on Unix-like systems with TTY support
- **Fallback Log Creation**: Provides basic log creation when shell integration unavailable

### TokenManager Features

- **Model-Aware Tokenization**: Uses appropriate tokenizer for different models
- **Accurate Estimation**: Leverages tiktoken for precise token counting
- **Intelligent Truncation**: Preserves important content when applying limits
- **Budget Allocation**: Distributes tokens across different context types
- **Performance Optimization**: Caches encoder instances for efficiency

### ToolOptimizer Features

- **Relevance Scoring**: Prioritizes tools based on query keywords and importance
- **Essential Tools**: Always includes critical system tools (execute, file operations)
- **Token Fitting**: Optimizes tool selection to fit within available token budget
- **Context-Aware**: Adapts tool selection based on user query and available space
- **Performance Balancing**: Balances tool capability with token efficiency

## Configuration Integration

The context system respects configuration settings:

```python
# Token limits and budgets
available_context = config.get_available_context_size()
tool_reserve = config.get_tool_tokens_reserve()
max_file_size = config.get("max_file_size", 51200)  # 50KB default

# Model settings
model_name = config.get("model", "gpt-4")
include_hidden = config.get("include_hidden_files", False)

# Context behavior
smart_summarize = config.get("context_summarization.enabled", True)
preserve_recent = config.get("context_summarization.preserve_recent", True)
```

## Log Processing and Shell Integration

### Primary Log Creation: Shell Integration

Log files are primarily created by the **shell integration submodule** which provides:
- Automatic command capture via shell hooks
- Real-time logging of terminal activity  
- Rich metadata and formatting
- TTY-specific log file management (`.aixterm_log.{tty}`)

### Log Processing: Context Submodule

The context submodule's LogProcessor **consumes and processes** these log files:
- Reads log files created by shell integration
- Extracts conversation history and commands
- Applies intelligent summarization
- Provides TTY-based log discovery
- Offers fallback log creation when shell integration unavailable

### Relationship

```
Shell Integration (Primary) ──creates──> Log Files ──processes──> Context LogProcessor
       │                                                               │
       ├─ Automatic command capture                                    ├─ Intelligent parsing
       ├─ Real-time logging                                           ├─ Conversation extraction  
       ├─ Rich formatting                                             ├─ Smart summarization
       └─ TTY-specific files                                          └─ Context optimization
```

## Error Handling

All components include comprehensive error handling:

- **File Access Errors**: Graceful handling of permissions and missing files
- **Encoding Issues**: Multiple fallback strategies for different file encodings
- **TTY Detection**: Safe fallbacks when TTY information is unavailable
- **Token Calculation**: Error recovery for token estimation failures
- **Log Processing**: Continues operation with degraded log functionality

- **File Access Errors**: Graceful handling of permissions and missing files
- **Encoding Issues**: Multiple fallback strategies for different file encodings
- **TTY Detection**: Safe fallbacks when TTY information is unavailable
- **Token Calculation**: Error recovery for token estimation failures
- **Log Processing**: Continues operation with degraded log functionality

## Usage Examples

### Basic Context Retrieval

```python
from aixterm.context import TerminalContext
from aixterm.config import AIxTermConfig

# Initialize
config = AIxTermConfig()
context = TerminalContext(config)

# Get comprehensive terminal context
terminal_context = context.get_terminal_context()
print(f"Context: {terminal_context}")
```

### File-Specific Context

```python
# Include specific files for context
important_files = [
    "src/main.py",
    "config/settings.json", 
    "README.md"
]

file_context = context.get_file_contexts(important_files)
print(f"File content length: {len(file_context)}")
```

### Optimized Context with Query

```python
# Get context optimized for specific query
query = "help me debug the authentication module"
optimized_context = context.get_optimized_context(
    file_contexts=["src/auth.py", "config/auth.json"],
    query=query
)
```

### Tool Optimization

```python
# Optimize tools for available context space
available_tools = [
    {"function": {"name": "execute_command", "description": "Run shell commands"}},
    {"function": {"name": "read_file", "description": "Read file contents"}},
    {"function": {"name": "search_files", "description": "Search in files"}},
    # ... more tools
]

optimized_tools = context.optimize_tools_for_context(
    tools=available_tools,
    query="debug Python application",
    available_tokens=6000
)

print(f"Optimized from {len(available_tools)} to {len(optimized_tools)} tools")
```

### Conversation History Analysis

```python
# Get recent conversation history
history = context.get_conversation_history(max_tokens=3000)

print(f"Found {len(history)} conversation entries")
for entry in history[-3:]:  # Last 3 entries
    print(f"Role: {entry['role']}")
    print(f"Content: {entry['content'][:100]}...")
    print("---")
```

## Best Practices

### Context Management
1. **Use Optimized Context**: Prefer `get_optimized_context()` for token-efficient results
2. **Include Relevant Files**: Only include files directly related to the query
3. **Enable Smart Summarization**: Use smart summarization for large contexts
4. **Monitor Token Usage**: Check available tokens before including large content

### File Context
1. **Limit File Count**: Include 3-10 most relevant files rather than entire directories
2. **Check File Sizes**: Large files may be truncated, prioritize key smaller files
3. **Mix File Types**: Include source code, configuration, and documentation
4. **Handle Encoding**: The system handles various encodings automatically

### Tool Optimization
1. **Provide Context**: Include query information for better tool prioritization
2. **Monitor Token Budget**: Ensure essential tools fit within available space
3. **Review Selection**: Check that critical tools are included in optimization
4. **Balance Capability**: Choose tools that provide value within token constraints

## Troubleshooting

### Common Issues

#### No Terminal History
```python
# Check for log files created by shell integration
log_files = Path.home().glob(".aixterm_log.*")
print(f"Available logs: {list(log_files)}")

# Check if shell integration is installed
from aixterm.integration import Bash
bash = Bash()
config_file = bash.find_config_file()
is_installed = bash.is_integration_installed(config_file)
print(f"Shell integration installed: {is_installed}")

# If no shell integration, use fallback log creation
if not is_installed:
    context.create_log_entry("ls -la", "directory listing")
```

#### Context Too Large
```python
# Check token usage
token_count = context.token_manager.estimate_tokens(context_str)
available = config.get_available_context_size()
print(f"Context tokens: {token_count}/{available}")

# Enable smart summarization
context_str = context.get_terminal_context(smart_summarize=True)
```

#### File Reading Errors
```python
# Verify file access
import os
files = ["file1.py", "file2.json"]
accessible = [f for f in files if os.path.exists(f)]
file_context = context.get_file_contexts(accessible)
```

## Future Enhancements

- **Semantic Context Scoring**: AI-powered relevance scoring for context selection
- **Cross-Session Memory**: Persistent context across terminal sessions  
- **Performance Metrics**: Detailed context usage and optimization statistics
- **Custom Processors**: Pluggable context processors for specific domains
- **Context Templates**: Predefined context configurations for common scenarios

## Contributing

When contributing to the context submodule:

1. **Maintain Component Separation**: Keep components focused and modular
2. **Add Comprehensive Tests**: Test each component independently and together
3. **Handle Edge Cases**: Consider various file types, encodings, and environments
4. **Document Token Costs**: Clearly document token implications of new features
5. **Preserve Backward Compatibility**: Maintain existing APIs when adding features

### Development Setup

```bash
# Run context-specific tests
pytest tests/test_context/ -v

# Test individual components
pytest tests/test_context/test_directory_handler.py -v
pytest tests/test_context/test_log_processor.py -v
pytest tests/test_context/test_token_manager.py -v
pytest tests/test_context/test_tool_optimizer.py -v
```

## License

Part of AIxTerm, licensed under the MIT License. See the main project LICENSE file for details.
