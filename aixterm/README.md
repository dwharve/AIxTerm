# AIxTerm Module

AI-powered terminal assistant with modular context management, MCP support, and intelligent shell integration.

## Architecture

### Core Components

- **AIxTerm** - Main application orchestrator
- **Context Submodule** - Modular context management:
  - **TerminalContext** - Context coordinator
  - **DirectoryHandler** - File/directory processing
  - **LogProcessor** - Terminal log analysis
  - **TokenManager** - Token budget management
  - **ToolOptimizer** - Intelligent tool selection
- **Integration Submodule** - Shell integration (Bash/Zsh/Fish)
- **LLMClient/MCPClient** - LLM communication and tool execution
- **AIxTermConfig** - Configuration management
- **AIxTermServer** - HTTP API server

### Features

- **Natural Language Interface** with context-aware responses
- **MCP Protocol Support** for extensible tool ecosystem
- **Multi-Shell Integration** with automatic command logging
- **Token-Optimized Context** with intelligent summarization
- **CLI and Server Modes** for flexible deployment

## Quick Start

### Basic Usage

```python
from aixterm.main import AIxTerm

# Initialize and run query
app = AIxTerm()
app.run("how do I list running processes?")

# Query with file context
app.run("analyze this code", file_contexts=["main.py"])

# Planning mode for complex tasks
app.run("create a backup system", use_planning=True)
```

### Shell Integration

```python
# Install automatic command logging
app.install_shell_integration("bash")  # or "zsh", "fish"

# Uninstall integration
app.uninstall_shell_integration("bash")
```

### Server Mode

```python
# Start HTTP API server
app.start_server(host="localhost", port=8000)

# API endpoints:
# POST /query - Send queries with JSON body
# GET /health - Health check
# POST /context - Get context information
```

## API Reference

### TerminalContext

Main context coordinator managing all context-related functionality.

```python
from aixterm.context import TerminalContext

context = TerminalContext(config)

# Get terminal context with smart summarization
context_str = context.get_terminal_context(include_files=True, smart_summarize=True)

# Get optimized context for available tokens
optimized = context.get_optimized_context(file_contexts=["main.py"], query="debug issue")

# Get conversation history from logs
history = context.get_conversation_history(max_tokens=2000)

# Get file contents
file_content = context.get_file_contexts(["src/main.py", "tests/test_main.py"])

# Optimize tools for context space
optimized_tools = context.optimize_tools_for_context(tools, query, available_tokens)
```

### Configuration

```python
from aixterm.config import AIxTermConfig

# Load from file
config = AIxTermConfig.from_file("config.json")

# Key configuration options
config.llm.model = "gpt-4"
config.llm.base_url = "https://api.openai.com/v1"
config.context.max_context_tokens = 8000
config.mcp.servers = [{"name": "filesystem", "command": ["mcp-server-filesystem", "/path"]}]
```

## Configuration

Default configuration location: `~/.config/aixterm/config.json`

### Key Settings

```json
{
  "llm": {
    "model": "gpt-4",
    "base_url": "https://api.openai.com/v1",
    "api_key": "your-api-key"
  },
  "context": {
    "max_context_tokens": 8000,
    "max_file_size": 1048576,
    "include_hidden_files": false
  },
  "mcp": {
    "servers": [
      {
        "name": "filesystem", 
        "command": ["mcp-server-filesystem", "/path"],
        "auto_start": true
      }
    ]
  },
  "cleanup": {
    "enabled": true,
    "max_log_age_days": 7,
    "max_log_files": 100
  }
}
```

## Component Details

### Context Components

- **DirectoryHandler**: Project detection, file reading, size limits
- **LogProcessor**: TTY-based log discovery, command extraction, smart summarization  
- **TokenManager**: Accurate token counting, budget allocation, context optimization
- **ToolOptimizer**: Query-aware tool prioritization, token budget fitting

### Shell Integration

- **Multi-Shell Support**: Bash, Zsh, Fish with native syntax
- **Safe Installation**: Non-destructive with automatic backups
- **TTY-Based Logging**: Session-specific log files
- **Clean Uninstall**: Complete removal capability

## Troubleshooting

### Common Issues

- **MCP Server Connection**: Check server command paths and permissions
- **Token Limits**: Adjust `max_context_tokens` or enable smart summarization
- **Shell Integration**: Verify shell configuration files and restart terminal
- **File Access**: Check file permissions and encoding for context files

### Debug Commands

```python
# Check status
app.status()

# List available tools
app.list_tools()

# Force cleanup
app.cleanup_now()

# Restart MCP servers
mcp_client.shutdown()
mcp_client.initialize()
```

## Development

### Testing

```bash
# Install development dependencies
pip install -e .[dev]

# Run all tests
pytest tests/ -v

# Run specific component tests
pytest tests/test_context/ -v
pytest tests/test_integration/ -v
```

### Contributing

1. Fork and create feature branch
2. Maintain test coverage and documentation
3. Follow type annotations and error handling patterns
4. Ensure component modularity and API compatibility

## License

MIT License. See main project LICENSE file for details.

## Component Details

### Context Components

- **DirectoryHandler**: Project detection, file reading, size limits
- **LogProcessor**: TTY-based log discovery, command extraction, smart summarization  
- **TokenManager**: Accurate token counting, budget allocation, context optimization
- **ToolOptimizer**: Query-aware tool prioritization, token budget fitting

### Shell Integration

- **Multi-Shell Support**: Bash, Zsh, Fish with native syntax
- **Safe Installation**: Non-destructive with automatic backups
- **TTY-Based Logging**: Session-specific log files
- **Clean Uninstall**: Complete removal capability

## Configuration

Default configuration location: `~/.config/aixterm/config.json`

### Key Settings

```json
{
  "llm": {
    "model": "gpt-4",
    "base_url": "https://api.openai.com/v1",
    "api_key": "your-api-key"
  },
  "context": {
    "max_context_tokens": 8000,
    "max_file_size": 1048576,
    "include_hidden_files": false
  },
  "mcp": {
    "servers": [
      {
        "name": "filesystem", 
        "command": ["mcp-server-filesystem", "/path"],
        "auto_start": true
      }
    ]
  },
  "cleanup": {
    "enabled": true,
    "max_log_age_days": 7,
    "max_log_files": 100
  }
}
```

## Troubleshooting

### Common Issues

- **MCP Server Connection**: Check server command paths and permissions
- **Token Limits**: Adjust `max_context_tokens` or enable smart summarization
- **Shell Integration**: Verify shell configuration files and restart terminal
- **File Access**: Check file permissions and encoding for context files

### Debug Commands

```python
# Check status
app.status()

# List available tools
app.list_tools()

# Force cleanup
app.cleanup_now()

# Restart MCP servers
mcp_client.shutdown()
mcp_client.initialize()
```

## Development

### Testing

```bash
# Install development dependencies
pip install -e .[dev]

# Run all tests
pytest tests/ -v

# Run specific component tests
pytest tests/test_context/ -v
pytest tests/test_integration/ -v
```

### Contributing

1. Fork and create feature branch
2. Maintain test coverage and documentation
3. Follow type annotations and error handling patterns
4. Ensure component modularity and API compatibility

## License

MIT License. See main project LICENSE file for details.

    "query": "How do I list running processes?",
    "file_contexts": ["script.py", "config.json"],
    "use_planning": false
}
```

**Response:**
```json
{
    "response": "You can list running processes using the `ps` command...",
    "status": "success"
}
```

##### `GET /status`
Get server status information.

**Response:**
```json
{
    "status": "running",
    "version": "0.1.3",
    "model": "gpt-4",
    "mcp_servers": {
        "filesystem": {"running": true, "tools": 15},
        "database": {"running": true, "tools": 8}
    }
}
```

##### `GET /tools`
List available MCP tools.

**Response:**
```json
{
    "tools": [
        {
            "name": "execute_command",
            "description": "Execute shell command",
            "server": "filesystem"
        }
    ]
}
```

### CleanupManager Class

Automatic maintenance and file cleanup.

#### Initialization

```python
from aixterm.cleanup import CleanupManager
from aixterm.config import AIxTermConfig

config = AIxTermConfig()
cleanup_manager = CleanupManager(config)
```

#### Core Methods

##### `should_run_cleanup() -> bool`
Check if cleanup should run based on configured interval.

**Returns:** True if cleanup should run

##### `run_cleanup(force: bool = False) -> Dict[str, Any]`
Run cleanup operations.

**Parameters:**
- `force`: Force cleanup regardless of interval

**Returns:** Cleanup results summary

**Example:**
```python
results = cleanup_manager.run_cleanup()
print(f"Removed {results['log_files_removed']} log files")
print(f"Freed {results['bytes_freed']} bytes")
```

##### `get_cleanup_status() -> Dict[str, Any]`
Get current cleanup status and statistics.

**Returns:** Cleanup status information

**Example:**
```python
status = cleanup_manager.get_cleanup_status()
print(f"Cleanup enabled: {status['cleanup_enabled']}")
print(f"Log files: {status['log_files_count']}")
print(f"Last cleanup: {status['last_cleanup']}")
```

## Command Line Interface

### Basic Usage

```bash
# Ask a question
ai "how do I list running processes?"

# Include file context
ai --file config.py --file main.py "how can I improve this code?"

# Use planning mode for complex tasks
ai --plan "create a backup system for my database"

# Override configuration
ai --api_url http://localhost:8080/v1/chat/completions "help with docker"
```

### Management Commands

```bash
# Show status
ai --status

# List available tools
ai --tools

# Force cleanup
ai --cleanup

# Initialize configuration
ai --init-config

# Run in server mode
ai --server
```

### Shell Integration

```bash
# Install shell integration for automatic logging
ai --install-shell --shell bash

# Install for other shells
ai --install-shell --shell zsh
ai --install-shell --shell fish

# Uninstall shell integration
ai --uninstall-shell --shell bash
```

### Advanced Options

```bash
# Use with configuration overrides
ai --config /path/to/custom/config.json "your query"

# Combined file context and planning
ai --file src/main.py --file tests/test.py --plan "refactor this code"
```

## Configuration

### Default Configuration Structure

```json
{
    "model": "local-model",
    "api_url": "http://localhost/v1/chat/completions",
    "api_key": "",
    "context_size": 4000,
    "response_buffer_size": 1000,
    "system_prompt": "You are a terminal AI assistant...",
    "planning_system_prompt": "You are a strategic planning AI assistant...",
    "mcp_servers": [
        {
            "name": "filesystem",
            "command": "mcp-server-filesystem",
            "args": ["/path/to/project"],
            "auto_start": true
        }
    ],
    "cleanup": {
        "enabled": true,
        "max_log_age_days": 30,
        "max_log_files": 10,
        "cleanup_interval_hours": 24
    },
    "tool_management": {
        "reserve_tokens_for_tools": 2000
    },
    "server_mode": {
        "enabled": false,
        "host": "localhost",
        "port": 8081,
        "transport": "http",
        "keep_alive": true
    },
    "logging": {
        "level": "INFO",
        "file": null
    }
}
```

### Configuration File Location

**Default Path:** `~/.aixterm`

**Custom Path:** Specify with `--config` flag or `config_path` parameter

### Environment Variables

```bash
# Override configuration via environment
export AIXTERM_API_URL="http://localhost:8080/v1/chat/completions"
export AIXTERM_API_KEY="your-api-key"
export AIXTERM_MODEL="gpt-4"
```

## MCP Server Integration

### Server Configuration

```json
{
    "mcp_servers": [
        {
            "name": "filesystem",
            "command": "mcp-server-filesystem",
            "args": ["/path/to/project"],
            "auto_start": true,
            "timeout": 30
        },
        {
            "name": "database",
            "command": "python",
            "args": ["-m", "my_mcp_server.database"],
            "auto_start": true,
            "env": {
                "DB_URL": "postgresql://localhost/mydb"
            }
        }
    ]
}
```

### Tool Discovery

Tools are automatically discovered from running MCP servers:

1. **Server Initialization**: Servers start automatically when AIxTerm runs
2. **Tool Enumeration**: Available tools are fetched from each server
3. **Tool Optimization**: Tools are intelligently selected based on context
4. **Tool Execution**: LLM can call tools through the MCP protocol

### Custom MCP Servers

Create custom MCP servers by implementing the MCP protocol:

```python
# Example custom MCP server
from mcp_server import Server

server = Server("my-custom-server")

@server.tool("custom_analysis")
def analyze_code(file_path: str) -> str:
    """Analyze code quality and provide recommendations."""
    # Implementation here
    return analysis_result

if __name__ == "__main__":
    server.run()
```

## Error Handling

### Graceful Error Recovery

AIxTerm includes comprehensive error handling:

```python
try:
    app.run("analyze this project")
except LLMError as e:
    # Handle LLM communication errors
    print(f"AI service error: {e}")
except MCPError as e:
    # Handle MCP server errors
    print(f"Tool execution error: {e}")
except ConfigurationError as e:
    # Handle configuration errors
    print(f"Configuration error: {e}")
```

### Common Error Scenarios

#### LLM Connection Issues
```
Error: Cannot connect to the AI service.
Please check that your LLM server is running and accessible.
Current API URL: http://localhost:8080/v1/chat/completions
```

#### Authentication Failures
```
Error: Authentication failed.
Please check your API key configuration.
```

#### MCP Server Issues
```
Warning: MCP server 'filesystem' failed to start
Tool functionality may be limited
```

### Error Recovery Strategies

1. **Automatic Retry**: Transient network errors are retried
2. **Graceful Degradation**: Continue operation with reduced functionality
3. **User Feedback**: Clear error messages with resolution steps
4. **Logging**: Detailed error logging for debugging

## Token Management and Optimization

### Intelligent Token Budgeting

The TokenManager component provides sophisticated token management:

```python
# Context allocation follows intelligent budgeting:
total_context = 4000  # tokens
response_buffer = 1000  # reserved for response
tool_reserve = 2000  # reserved for tools
available_context = 1000  # remaining for context

# Intelligent allocation by component:
# - Directory context: 10-15% (DirectoryHandler)
# - File contexts: 40-60% (DirectoryHandler) 
# - Terminal history: 25-40% (LogProcessor)
# - Tool definitions: Auto-fitted (ToolOptimizer)
```

### Context Optimization Strategies

1. **Component-Based Allocation**: Each component gets optimal budget allocation
2. **Query-Aware Prioritization**: Content prioritized based on user query
3. **Recency Bias**: More recent information weighted higher
4. **Essential Information Preservation**: Critical context never truncated

### Tool Optimization

The ToolOptimizer component intelligently selects tools based on:

1. **Query Relevance**: Tools matching query keywords get priority
2. **Essential Tools**: System commands always included
3. **Token Budget**: Intelligent fitting within available token space
4. **Usage Patterns**: Frequently used tools prioritized
5. **Component Integration**: Coordinated with other context components

### Performance Optimizations

- **Modular Loading**: Components loaded on demand
- **Intelligent Caching**: Context reuse where appropriate
- **Resource Cleanup**: Automatic cleanup of temporary data
- **Connection Pooling**: Efficient MCP server communication
- **Log Rotation**: Automatic cleanup of old log files

## Security Considerations

### Safe Command Execution

- **User Confirmation**: Potentially dangerous commands require confirmation
- **Command Validation**: Basic safety checks before execution
- **Sandboxing**: MCP servers can run in isolated environments
- **Audit Logging**: All commands and outputs are logged

### Configuration Security

- **File Permissions**: Configuration files protected with appropriate permissions
- **API Key Protection**: Secure storage and transmission of API keys
- **Server Security**: HTTP server includes basic security measures
- **Input Validation**: All inputs are validated and sanitized

### Privacy Protection

- **Local Processing**: Context processing happens locally
- **Selective Logging**: Sensitive information can be filtered
- **User Control**: Users control what information is shared
- **Data Retention**: Configurable cleanup policies

## Advanced Usage

### Custom Prompts

Customize system prompts for specific use cases:

```python
config.set("system_prompt", """
You are a specialized DevOps AI assistant focused on:
- Infrastructure automation
- Container orchestration  
- CI/CD pipeline optimization
- Monitoring and alerting

Provide practical, production-ready solutions.
""")
```

### Integration with CI/CD

Use AIxTerm in automated environments:

```bash
#!/bin/bash
# CI/CD script
export AIXTERM_API_URL="$CI_LLM_ENDPOINT"
export AIXTERM_API_KEY="$CI_LLM_TOKEN"

# Analyze test results
ai --file test_results.xml "analyze these test failures and suggest fixes"

# Generate deployment docs
ai --file deployment.yaml "create deployment documentation"
```

### Webhook Integration

Use server mode for webhook integrations:

```python
import requests

# Send query via HTTP API
response = requests.post("http://localhost:8081/query", json={
    "query": "analyze recent errors",
    "file_contexts": ["logs/error.log"]
})

result = response.json()
print(result["response"])
```

### Custom Tool Development

Develop custom MCP tools for specific workflows:

```python
# Custom deployment tool
@server.tool("deploy_application")
def deploy_app(environment: str, version: str) -> str:
    """Deploy application to specified environment."""
    # Custom deployment logic
    return f"Deployed version {version} to {environment}"

# Custom monitoring tool  
@server.tool("check_system_health")
def check_health() -> str:
    """Check overall system health status."""
    # Health check implementation
    return health_report
```

## Testing and Development

### Context Component Testing

Test modular context components:

```python
from aixterm.context import TerminalContext
from aixterm.context.directory_handler import DirectoryHandler
from aixterm.context.log_processor import LogProcessor
from aixterm.context.token_manager import TokenManager
from aixterm.context.tool_optimizer import ToolOptimizer

def test_directory_handler():
    """Test directory context processing."""
    config = AIxTermConfig()
    logger = get_logger(__name__)
    handler = DirectoryHandler(config, logger)
    
    # Test project detection
    project_type = handler.detect_project_type(Path.cwd())
    assert project_type is not None
    
    # Test file context extraction
    files = ["README.md", "setup.py"]
    context = handler.get_file_contexts(files)
    assert len(context) > 0

def test_token_manager():
    """Test token management functionality."""
    config = AIxTermConfig()
    logger = get_logger(__name__)
    manager = TokenManager(config, logger)
    
    # Test token estimation
    tokens = manager.estimate_tokens("Hello world")
    assert tokens > 0
    
    # Test budget allocation
    budget = manager.allocate_context_budget(1000)
    assert sum(budget.values()) <= 1000
```

### Integration Testing

Test complete workflows including shell integration:

```python
def test_shell_integration_workflow():
    """Test complete shell integration workflow."""
    app = AIxTerm()
    
    # Test installation
    app.install_shell_integration("bash")
    
    # Verify integration files exist
    from aixterm.integration import Bash
    bash_integration = Bash()
    config_file = bash_integration.find_config_file()
    assert bash_integration.is_integration_installed(config_file)
    
    # Test uninstallation
    app.uninstall_shell_integration("bash")
    assert not bash_integration.is_integration_installed(config_file)

def test_query_processing_with_context():
    """Test query processing with modular context."""
    app = AIxTerm()
    
    # Mock LLM response
    with patch('aixterm.llm.LLMClient.chat_completion') as mock:
        mock.return_value = "Use the `ps aux` command"
        
        # Test query with file context
        app.run("how do I list processes?", file_contexts=["README.md"])
        
        # Verify components were called
        assert mock.called
        assert app.context_manager.directory_handler is not None
```

### Performance Testing

Monitor performance of modular components:

```python
import time
from memory_profiler import profile

@profile
def test_context_component_performance():
    """Test context component performance."""
    app = AIxTerm()
    
    start_time = time.time()
    
    # Test directory handler performance
    dir_context = app.context_manager.directory_handler.get_directory_context()
    
    # Test log processor performance  
    log_files = app.context_manager.log_processor.get_log_files()
    
    # Test token manager performance
    tokens = app.context_manager.token_manager.estimate_tokens(dir_context)
    
    end_time = time.time()
    
    assert end_time - start_time < 2.0  # Should complete in under 2 seconds
    assert len(dir_context) > 0
    assert tokens > 0

def test_shell_integration_performance():
    """Test shell integration installation performance."""
    app = AIxTerm()
    
    start_time = time.time()
    app.install_shell_integration("bash")
    app.uninstall_shell_integration("bash")
    end_time = time.time()
    
    assert end_time - start_time < 5.0  # Should complete quickly
```

## Deployment Strategies

### Local Development

```bash
# Install in development mode
pip install -e .

# Run with local LLM
ai --api_url http://localhost:1234/v1/chat/completions "test query"
```

### Server Deployment

```bash
# Run as HTTP server
ai --server

# Run with custom configuration
ai --config /etc/aixterm/config.json --server

# Docker deployment
docker run -d -p 8081:8081 -v /path/to/config:/config aixterm --server
```

### Multi-User Environments

```bash
# System-wide configuration
sudo mkdir -p /etc/aixterm
sudo cp config.json /etc/aixterm/

# User-specific overrides
cp /etc/aixterm/config.json ~/.aixterm
# Edit ~/.aixterm for user-specific settings
```

## Monitoring and Observability

### Logging Configuration

```json
{
    "logging": {
        "level": "INFO",
        "file": "/var/log/aixterm.log",
        "max_size": "10MB",
        "backup_count": 5
    }
}
```

### Metrics Collection

Monitor key metrics:

- Query response times
- MCP server health
- Context processing time
- Tool execution success rates
- Memory usage patterns

### Health Checks

```bash
# Check server health
curl http://localhost:8081/status

# Check tool availability
curl http://localhost:8081/tools

# Monitor log files
tail -f ~/.aixterm_log.*
```

## Troubleshooting

### Common Issues

#### Context Component Issues
```bash
# Test individual components
python -c "from aixterm.context.directory_handler import DirectoryHandler; print('DirectoryHandler works')"
python -c "from aixterm.context.log_processor import LogProcessor; print('LogProcessor works')"
python -c "from aixterm.context.token_manager import TokenManager; print('TokenManager works')"

# Check component integration
ai --status  # Should show component status
```

#### Shell Integration Issues
```bash
# Check shell integration status
ai --install-shell --shell bash  # Install/reinstall
ai --uninstall-shell --shell bash  # Clean uninstall

# Manual verification
grep -n "AIxTerm Shell Integration" ~/.bashrc
ls -la ~/.aixterm_log.*

# Test shell functions (after installing integration)
source ~/.bashrc
aixterm_status  # Should show integration status
```

#### MCP Servers Not Working
```bash
# Check server status
ai --tools

# Test server manually
mcp-server-filesystem /path/to/project

# Check server logs
tail -f ~/.aixterm_log.*
```

#### Poor Response Quality
```bash
# Increase context size
ai --config /path/to/config.json
# Edit config: "context_size": 8000

# Add more file context
ai --file relevant1.py --file relevant2.py "your query"

# Use planning mode
ai --plan "complex task description"
```

### Debug Mode

Enable detailed logging:

```json
{
    "logging": {
        "level": "DEBUG",
        "file": "debug.log"
    }
}
```

### Recovery Procedures

#### Reset Configuration
```bash
# Backup current config
cp ~/.aixterm ~/.aixterm.backup

# Reset to defaults
ai --init-config --force
```

#### Clean State Reset
```bash
# Remove all logs and temp files
ai --cleanup

# Or manual cleanup
rm -f ~/.aixterm_log.*
rm -rf /tmp/aixterm_*
```

## Best Practices

### Configuration Management

1. **Version Control**: Keep configuration files in version control
2. **Environment Separation**: Use different configs for dev/prod
3. **Security**: Protect API keys and sensitive configuration
4. **Validation**: Test configuration changes before deployment

### Context Management

1. **Component Optimization**: Tune individual context components for your use case
2. **Relevant Files Only**: Include only files directly relevant to the query
3. **Size Management**: Monitor context size through TokenManager component
4. **Smart Summarization**: Enable intelligent context summarization in LogProcessor
5. **Cache Efficiency**: Reuse context when possible across components

### Shell Integration

1. **Proper Installation**: Use the built-in installation commands rather than manual setup
2. **Shell Compatibility**: Test integration across different shell versions
3. **Log Management**: Regularly clean up log files using cleanup commands
4. **Session Isolation**: Verify TTY-based session separation works correctly
5. **Backup Management**: Keep integration backups for recovery

### Tool Management

1. **Essential Tools**: Ensure critical tools are always available through ToolOptimizer
2. **Custom Tools**: Develop domain-specific tools for workflows
3. **Performance**: Monitor tool execution times and optimize accordingly
4. **Error Handling**: Implement robust error handling in custom tools
5. **Integration Testing**: Test tool integration with modular context system

### Monitoring

1. **Health Checks**: Regular monitoring of all components
2. **Performance Metrics**: Track response times and resource usage
3. **Error Tracking**: Monitor and alert on error patterns
4. **Capacity Planning**: Plan for growth and scaling

## Future Enhancements

### Planned Features

- **Enhanced Context Components**: Additional specialized context processors
- **Multi-Modal Support**: Image and document analysis through context components
- **Conversation Memory**: Persistent conversation history via LogProcessor
- **Team Collaboration**: Shared context and knowledge base
- **Advanced Planning**: Multi-step task decomposition with context awareness
- **Real-time Collaboration**: Live assistance and pair programming
- **Shell Integration Extensions**: Additional shell support and advanced features

### Integration Roadmap

- **IDE Plugins**: VS Code, IntelliJ, Vim integrations with context sharing
- **Cloud Services**: AWS, GCP, Azure tool integrations via MCP
- **Container Orchestration**: Kubernetes and Docker tools with context awareness
- **Monitoring Systems**: Prometheus, Grafana integrations
- **CI/CD Platforms**: GitHub Actions, Jenkins, GitLab CI with shell integration
- **Advanced Shell Features**: Enhanced logging and context capture

## Contributing

### Development Setup

```bash
# Clone repository
git clone https://github.com/dwharve/aixterm.git
cd aixterm

# Install development dependencies
pip install -e .[dev]

# Run context component tests
pytest tests/test_context/ -v

# Run shell integration tests  
pytest tests/test_integration/ -v

# Run specific component test
pytest tests/test_context/test_directory_handler.py::TestDirectoryHandler -v
```

### Code Standards

1. **Type Annotations**: Full type hints required for all components
2. **Documentation**: Comprehensive docstrings for all public APIs and components
3. **Testing**: Unit tests for all new functionality including context components
4. **Error Handling**: Graceful error recovery across all components
5. **Performance**: Optimize for common use cases and component interactions
6. **Modularity**: Maintain clean separation between context components

### Contribution Guidelines

1. **Fork and Branch**: Create feature branches for development
2. **Test Coverage**: Maintain high test coverage for all components
3. **Documentation**: Update documentation for new features and components
4. **Backward Compatibility**: Maintain API compatibility across components
5. **Security**: Follow security best practices in all components
6. **Component Integration**: Ensure new components integrate properly with existing architecture

## License

The AIxTerm module is licensed under the MIT License. See the main project LICENSE file for details.
