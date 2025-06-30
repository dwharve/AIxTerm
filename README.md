# AIxTerm

An AI-powered command-line assistant that helps you discover and execute shell commands through natural language queries. AIxTerm integrates with Large Language Models to provide intelligent, context-aware assistance for your terminal operations.

**Current Version**: 0.1.3

## Features

### Core Functionality
- **Natural Language Interface**: Ask questions in plain English and get executable shell commands
- **Safe Command Execution**: Built-in safety checks with user confirmation for potentially dangerous commands
- **Context-Aware**: Maintains session history and provides relevant context to improve responses
- **Cross-Platform**: Works on Windows, macOS, and Linux with platform-specific command detection

### Enhanced Context System
- **File Context Integration**: Include specific files as context using `--file` flag (can be used multiple times)
- **Smart Context Summarization**: Intelligently summarizes terminal history to provide relevant context without overwhelming the LLM
- **Project Detection**: Automatically detects project types (Python, Node.js, Java, etc.) for better context
- **Directory Analysis**: Provides intelligent summaries of current directory structure and important files

### Advanced Features
- **MCP Server Support**: Integrates with Model Context Protocol servers for extended functionality
- **HTTP Server Mode**: Can run as an HTTP server for integration with other applications
- **Automatic Cleanup**: Manages log files and temporary data with configurable cleanup policies
- **Token Management**: Intelligent token counting and content truncation for optimal LLM performance
- **Command Extraction**: Advanced regex patterns to extract commands from various code block formats

### Developer-Friendly
- **Comprehensive Testing**: Full test coverage with 160+ tests including cross-platform compatibility
- **Modular Architecture**: Clean separation of concerns with dedicated modules for different functionality
- **Configurable**: Extensive configuration options via JSON config files
- **Well Documented**: Comprehensive documentation and type hints throughout

## Installation

### Prerequisites
- Python 3.8+
- pip or conda

### Install from PyPI (Recommended)
```bash
pip install aixterm
```

### Install from Source
```bash
git clone https://github.com/dwharve/aixterm.git
cd aixterm
pip install -e .
```

### Development Installation
```bash
git clone https://github.com/dwharve/aixterm.git
cd aixterm
make venv  # Sets up virtual environment and installs dependencies
source venv/bin/activate
```

**Note**: AIxTerm provides two command aliases after installation:
- `aixterm` - Full command name
- `ai` - Short alias for convenience

## Configuration

AIxTerm uses a configuration file located at `~/.aixterm_config.json`. You can create this file manually or let AIxTerm create it with default values on first run.

### Example Configuration
```json
{
  "api_url": "http://localhost/v1/chat/completions",
  "api_key": "",
  "model": "llama2",
  "streaming": true,
  "context_tokens": 500,
  "timeout": 30,
  "mcp_servers": [],
  "cleanup": {
    "enabled": true,
    "max_log_files": 50,
    "max_log_age_days": 30,
    "max_log_size_mb": 10,
    "cleanup_interval_hours": 24
  }
}
```

### Configuration Options

- **api_url**: URL of your LLM API endpoint
- **api_key**: API key for authentication (if required)
- **model**: Model name to use
- **streaming**: Enable streaming responses
- **context_tokens**: Maximum tokens to include from terminal history
- **timeout**: Request timeout in seconds
- **mcp_servers**: List of MCP server configurations
- **cleanup**: Automatic cleanup settings

## Dependencies

AIxTerm has minimal core dependencies:
- `requests>=2.25.0` - HTTP client for API communication
- `tiktoken>=0.5.0` - Token counting for LLM context management

Additional development dependencies are listed in `requirements-dev.txt`.

## Usage

### Basic Usage
```bash
# Ask a simple question
ai "how do I list all running processes?"

# Get help with specific commands
ai "what does the grep command do?"

# Ask for file operations
ai "how do I find large files in the current directory?"
```

### Planning Mode
```bash
# Use planning mode for complex tasks
ai --plan "set up a complete CI/CD pipeline for my Python project"

# Planning mode with file context
ai -p --file docker-compose.yml "optimize this deployment for production"

# Complex system administration planning
ai --plan "create a disaster recovery strategy for our database"
```

### File Context Integration
```bash
# Include single file as context
ai --file script.py "how can I improve this code?"

# Include multiple files
ai --file main.py --file config.py "analyze the architecture of this application"

# Combine with queries
ai --file requirements.txt "what Python packages does this project use and what are they for?"
```

### Management Commands
```bash
# Show AIxTerm status
ai --status

# List available MCP tools
ai --tools

# Force cleanup now
ai --cleanup

# Show help
ai --help
```

### Server Mode
```bash
# Run AIxTerm as an HTTP server
ai --server --port 8080

# Server mode with custom configuration
ai --server --port 8080 --config custom_config.json

# Server mode with specific host binding
ai --server --host 0.0.0.0 --port 8080
```

## Advanced Features

### Smart Context System

AIxTerm includes an intelligent context system that:

1. **Analyzes Current Directory**: Automatically detects project types and important files
2. **Summarizes Terminal History**: Provides relevant recent commands and outputs
3. **Manages Token Limits**: Intelligently truncates content to stay within model limits
4. **Prioritizes Recent Activity**: Focuses on the most recent and relevant information

#### Terminal Session Logging

For optimal context, AIxTerm automatically logs terminal sessions to provide better context for AI responses. The logging system:

- **Automatic Log Files**: Creates session-specific logs at `~/.aixterm_log.{tty_name}` 
- **TTY Detection**: Automatically detects current terminal session using TTY information
- **Conversation History**: Maintains structured conversation records for context
- **Smart Summarization**: Intelligently summarizes terminal history to avoid overwhelming the LLM

#### Setting Up Shell Integration

For optimal context, AIxTerm can automatically capture all terminal activity. Use the built-in installation command:

**Automatic Installation (Recommended)**
```bash
# Install shell integration for automatic terminal logging
ai --install-shell

# For different shells
ai --install-shell --shell zsh
ai --install-shell --shell fish

# Uninstall if needed
ai --uninstall-shell
```

**Manual Methods**
To capture all terminal activity manually, you can set up shell integration:

**Method 1: Using `script` command**
```bash
# Start a logged session
script -f ~/.aixterm_log.$(tty | sed 's/\/dev\///g' | sed 's/\//-/g')
# Then use aixterm normally in this session
```

**Method 2: Add to ~/.bashrc manually**
```bash
# Basic terminal logging for aixterm
log_for_aixterm() {
    local tty_name=$(tty 2>/dev/null | sed 's/\/dev\///g' | sed 's/\//-/g')
    local log_file="$HOME/.aixterm_log.${tty_name:-default}"
    echo "$ $BASH_COMMAND" >> "$log_file" 2>/dev/null
}
trap 'log_for_aixterm' DEBUG
```

### MCP Server Integration

AIxTerm supports Model Context Protocol (MCP) servers for extended functionality:

```json
{
  "mcp_servers": [
    {
      "name": "file-manager",
      "command": ["python", "file_manager_server.py"],
      "enabled": true
    }
  ]
}
```

### Automatic Cleanup

The cleanup system automatically manages:
- Log file rotation and deletion
- Temporary file cleanup
- Configurable retention policies
- Background cleanup scheduling

## Development

### Project Structure
```
aixterm/
├── __init__.py
├── main.py           # Main application logic
├── config.py         # Configuration management
├── context.py        # Context and history management
├── llm.py           # LLM client integration
├── mcp_client.py    # MCP server integration
├── cleanup.py       # Cleanup management
├── server.py        # Server functionality
└── utils.py         # Utility functions

tests/
├── test_*.py        # Comprehensive test suite
└── conftest.py      # Test configuration

requirements.txt     # Dependencies
setup.py            # Package setup
```

### Running Tests
```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=aixterm

# Run specific test file
python -m pytest tests/test_integration.py -v

# Quick test run
python -m pytest tests/ -q
```

### Testing Results
- **145 tests passing**
- **0 tests skipped**
- **Full cross-platform compatibility**
- **Comprehensive integration test coverage**

## Examples

### Code Analysis
```bash
# Analyze Python code
ai --file app.py "what does this application do and how can I improve it?"

# Review configuration
ai --file docker-compose.yml "explain this Docker setup"

# Security review
ai --file script.sh "are there any security issues in this script?"
```

### System Administration
```bash
# Process management
ai "how do I kill a process by name?"

# Disk usage
ai "show me disk usage by directory"

# Network diagnostics
ai "how do I check if a port is open?"
```

### Development Workflow
```bash
# Git operations
ai "how do I undo the last commit?"

# Package management
ai --file requirements.txt "update these Python packages to latest versions"

# Planning complex development tasks
ai --plan "refactor this monolithic application into microservices"

# Debugging with planning approach
ai -p "debug a memory leak in my Python application"
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Add tests for new functionality
4. Ensure all tests pass (`python -m pytest tests/`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

For a detailed history of changes, see [CHANGELOG.md](CHANGELOG.md).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Project Status

AIxTerm is in **Beta** status with the following characteristics:
- Core functionality is stable and well-tested (145 passing tests)
- API may still evolve based on user feedback
- Production-ready for individual and team use
- Active development and maintenance

## Acknowledgments

- Built with support for various LLM providers (OpenAI, Ollama, etc.)
- Integrates with Model Context Protocol for extensibility
- Inspired by the need for intelligent command-line assistance
