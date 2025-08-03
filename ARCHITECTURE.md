# AIxTerm Service Architecture & Plugin System Design

## Service Architecture

### Overview

The new AIxTerm service architecture transforms the application from a command-line utility to a persistent background service with client applications that communicate with it. This design enables:

- **Persistent Context**: Maintain context across multiple client sessions
- **Resource Sharing**: More efficient use of resources by sharing LLM connections
- **Enhanced Features**: Support for plugins, background tasks, and continuous monitoring
- **Improved Performance**: Reduced startup time for client operations

### Core Components

#### 1. AIxTermService

The central service/daemon component responsible for:

- Managing the service lifecycle (start, stop, restart, status)
- Handling client connections and requests
- Loading and managing plugins
- Maintaining shared resources (LLM clients, context, etc.)
- Monitoring system health and performance

```python
# Conceptual class structure
class AIxTermService:
    def __init__(self, config_path=None):
        self.config = load_config(config_path)
        self.plugin_manager = PluginManager(self)
        self.server = ServiceServer(self)
        self.context_manager = ContextManager(self)
        self.llm_client = LLMClient(self.config)
        self._running = False
    
    def start(self):
        """Start the service and all components."""
        self._running = True
        self.plugin_manager.load_plugins()
        self.server.start()
    
    def stop(self):
        """Gracefully shutdown the service."""
        self._running = False
        self.server.stop()
        self.plugin_manager.unload_plugins()
    
    def status(self):
        """Return service status information."""
        return {
            "running": self._running,
            "plugins": self.plugin_manager.get_status(),
            "uptime": self.get_uptime(),
            "resource_usage": self.get_resource_usage()
        }
```

#### 2. ServiceServer

Handles the communication layer between clients and the service:

- Socket or HTTP-based communication server
- Request routing to appropriate handlers
- Authentication and security (if needed)
- Response formatting and delivery

```python
class ServiceServer:
    def __init__(self, service):
        self.service = service
        self.config = service.config.server
        self.socket_path = self.config.socket_path
        self.handlers = self._register_handlers()
    
    def _register_handlers(self):
        """Register request handlers."""
        return {
            "query": self._handle_query,
            "status": self._handle_status,
            "plugin": self._handle_plugin_request,
            # Additional handlers
        }
    
    def start(self):
        """Start the server on the configured socket or port."""
        # Implementation depends on chosen communication method
    
    def stop(self):
        """Stop the server gracefully."""
        # Clean up connections and resources
    
    def _handle_query(self, request):
        """Handle a query from a client."""
        # Process query and return response
    
    def _handle_status(self, request):
        """Return service status."""
        return self.service.status()
    
    def _handle_plugin_request(self, request):
        """Route request to appropriate plugin."""
        plugin_id = request.get("plugin_id")
        return self.service.plugin_manager.handle_request(plugin_id, request)
```

#### 3. Service Installation

Platform-specific service installation and management:

**Windows Service**:
- Use `win32serviceutil` for Windows service registration
- Create appropriate registry entries and service definitions
- Handle startup parameters and user contexts

**Linux systemd**:
- Generate appropriate systemd unit files
- Register with systemctl for service management
- Handle user/system installation options

**macOS launchd**:
- Create appropriate plist files for launchd
- Register with launchctl
- Support user/system-wide installation

```python
class ServiceInstaller:
    @staticmethod
    def install(config=None, user_mode=True):
        """Install the service for the current platform."""
        platform = platform.system()
        if platform == "Windows":
            return WindowsServiceInstaller.install(config, user_mode)
        elif platform == "Darwin":
            return MacOSServiceInstaller.install(config, user_mode)
        elif platform == "Linux":
            return LinuxServiceInstaller.install(config, user_mode)
        else:
            raise UnsupportedPlatformError(f"Platform {platform} not supported")
    
    @staticmethod
    def uninstall(user_mode=True):
        """Uninstall the service for the current platform."""
        # Similar platform-specific approach
```

### Client Components

#### 1. AIxTermClient

The client application that communicates with the service:

- Connects to the service using the appropriate protocol
- Formats and sends requests
- Processes responses
- Handles connection errors and fallbacks
- Provides command-line interface

```python
class AIxTermClient:
    def __init__(self, config_path=None):
        self.config = load_config(config_path)
        self.connection = ServiceConnection(self.config)
    
    def connect(self):
        """Establish connection to the service."""
        try:
            return self.connection.connect()
        except ConnectionError:
            # Handle connection failure (fallback to direct operation?)
            return False
    
    def query(self, question, **options):
        """Send a query to the service."""
        request = {
            "type": "query",
            "question": question,
            "options": options
        }
        return self.connection.send_request(request)
    
    def status(self):
        """Get service status."""
        request = {"type": "status"}
        return self.connection.send_request(request)
```

#### 2. ServiceConnection

Handles the actual communication with the service:

- Manages socket or HTTP connection
- Implements the client side of the protocol
- Handles errors, timeouts, and retries
- Supports streaming responses

```python
class ServiceConnection:
    def __init__(self, config):
        self.config = config
        self.socket_path = config.service.socket_path
        self.connected = False
    
    def connect(self):
        """Connect to the service."""
        # Implementation depends on chosen communication method
        self.connected = True
        return True
    
    def disconnect(self):
        """Close the connection."""
        if self.connected:
            # Close connection
            self.connected = False
    
    def send_request(self, request):
        """Send a request to the service and return the response."""
        if not self.connected and not self.connect():
            raise ConnectionError("Could not connect to AIxTerm service")
        
        # Send request and receive response
        # Implementation depends on chosen communication method
```

### Communication Protocol

A simple JSON-based protocol for client-service communication:

**Request Format**:
```json
{
  "type": "query|status|plugin|...",
  "id": "unique-request-id",
  "timestamp": "2025-07-12T12:00:00Z",
  "payload": {
    // Request-specific data
  }
}
```

**Response Format**:
```json
{
  "request_id": "unique-request-id",
  "timestamp": "2025-07-12T12:00:05Z",
  "status": "success|error|partial",
  "payload": {
    // Response-specific data
  },
  "error": {
    "code": "error-code",
    "message": "Error message"
  }
}
```

**Streaming Response Format**:
```json
{
  "request_id": "unique-request-id",
  "timestamp": "2025-07-12T12:00:01Z",
  "status": "partial",
  "chunk": "text chunk",
  "done": false
}
```

## Plugin System Design

### Overview

The AIxTerm plugin system provides a modular way to extend functionality without modifying the core code. Key aspects include:

- **Lifecycle Management**: Consistent loading, initialization, and unloading
- **Configuration Management**: Structured configuration handling
- **Event System**: Communication between plugins and core service
- **Command Registration**: Adding new commands to the CLI interface
- **Resource Access**: Controlled access to shared resources

### Core Components

#### 1. Plugin Base Class

The foundation for all plugins:

```python
class Plugin:
    """Base class for all AIxTerm plugins."""
    
    def __init__(self, service):
        self.service = service
        self.config = {}
        self.logger = logging.getLogger(f"aixterm.plugin.{self.id}")
        self.initialized = False
    
    @property
    def id(self):
        """Unique identifier for the plugin."""
        raise NotImplementedError("Plugins must implement the id property")
    
    @property
    def name(self):
        """Human-readable name of the plugin."""
        raise NotImplementedError("Plugins must implement the name property")
    
    @property
    def version(self):
        """Plugin version string."""
        raise NotImplementedError("Plugins must implement the version property")
    
    @property
    def description(self):
        """Plugin description."""
        return "No description provided"
    
    def initialize(self):
        """Initialize the plugin."""
        self.initialized = True
        return True
    
    def shutdown(self):
        """Clean up resources and prepare for unloading."""
        self.initialized = False
        return True
    
    def get_commands(self):
        """Return a dict of commands this plugin provides."""
        return {}
    
    def handle_request(self, request):
        """Process a request directed at this plugin."""
        command = request.get("command")
        commands = self.get_commands()
        
        if command in commands:
            handler = commands[command]
            return handler(request)
        
        return {
            "status": "error",
            "error": {
                "code": "unknown_command",
                "message": f"Unknown command: {command}"
            }
        }
    
    def status(self):
        """Return plugin status information."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "initialized": self.initialized
        }
```

#### 2. Plugin Manager

Responsible for discovering, loading, and managing plugins:

```python
class PluginManager:
    """Manages AIxTerm plugins."""
    
    def __init__(self, service):
        self.service = service
        self.config = service.config.plugins
        self.plugins = {}
        self.commands = {}
    
    def discover_plugins(self):
        """Discover available plugins."""
        plugins = []
        # Look in standard locations for plugin packages/modules
        # 1. Built-in plugins
        # 2. Site-packages plugins
        # 3. User-defined plugin directory
        return plugins
    
    def load_plugin(self, plugin_id):
        """Load a specific plugin by ID."""
        if plugin_id in self.plugins:
            return True  # Already loaded
        
        try:
            # Import and instantiate the plugin
            plugin_class = self._import_plugin(plugin_id)
            plugin = plugin_class(self.service)
            success = plugin.initialize()
            
            if success:
                self.plugins[plugin_id] = plugin
                self._register_commands(plugin)
                return True
            else:
                return False
        except Exception as e:
            self.service.logger.error(f"Failed to load plugin {plugin_id}: {e}")
            return False
    
    def load_plugins(self):
        """Load all enabled plugins."""
        for plugin_id in self.config.enabled_plugins:
            self.load_plugin(plugin_id)
    
    def unload_plugin(self, plugin_id):
        """Unload a plugin by ID."""
        if plugin_id not in self.plugins:
            return False
        
        try:
            plugin = self.plugins[plugin_id]
            success = plugin.shutdown()
            
            if success:
                self._unregister_commands(plugin)
                del self.plugins[plugin_id]
                return True
            else:
                return False
        except Exception as e:
            self.service.logger.error(f"Failed to unload plugin {plugin_id}: {e}")
            return False
    
    def unload_plugins(self):
        """Unload all plugins."""
        plugin_ids = list(self.plugins.keys())
        for plugin_id in plugin_ids:
            self.unload_plugin(plugin_id)
    
    def handle_request(self, plugin_id, request):
        """Route a request to the appropriate plugin."""
        if plugin_id not in self.plugins:
            return {
                "status": "error",
                "error": {
                    "code": "unknown_plugin",
                    "message": f"Unknown plugin: {plugin_id}"
                }
            }
        
        return self.plugins[plugin_id].handle_request(request)
    
    def get_status(self):
        """Return status information for all plugins."""
        return {
            plugin_id: plugin.status()
            for plugin_id, plugin in self.plugins.items()
        }
    
    def _import_plugin(self, plugin_id):
        """Import and return the plugin class."""
        # Implementation depends on plugin discovery approach
    
    def _register_commands(self, plugin):
        """Register commands provided by the plugin."""
        commands = plugin.get_commands()
        for command, handler in commands.items():
            self.commands[command] = (plugin.id, handler)
    
    def _unregister_commands(self, plugin):
        """Unregister commands provided by the plugin."""
        commands = plugin.get_commands()
        for command in commands:
            if command in self.commands and self.commands[command][0] == plugin.id:
                del self.commands[command]
```

#### 3. Plugin Configuration

A structured approach to plugin configuration:

```python
# In config.py
class PluginConfig(BaseModel):
    """Configuration for a specific plugin."""
    enabled: bool = True
    settings: Dict[str, Any] = {}

class PluginsConfig(BaseModel):
    """Configuration for the plugin system."""
    enabled_plugins: List[str] = []
    plugin_directory: Optional[str] = None
    auto_discover: bool = True
    plugins: Dict[str, PluginConfig] = {}
```

Example configuration:
```yaml
plugins:
  enabled_plugins:
    - devteam
    - code_search
  plugin_directory: "~/.aixterm/plugins"
  auto_discover: true
  plugins:
    devteam:
      enabled: true
      settings:
        max_agents: 5
        default_workflow: "feature"
    code_search:
      enabled: true
      settings:
        max_files: 100
        include_patterns:
          - "*.py"
          - "*.js"
```

#### 4. Plugin Discovery

Methods for discovering and loading plugins:

1. **Built-in Plugins**: Included in the main package
2. **Installed Plugins**: In site-packages with appropriate entry points
3. **User Plugins**: In user-defined directories

```python
def discover_plugins(plugin_directories=None):
    """Discover available plugins from multiple sources."""
    plugins = {}
    
    # 1. Built-in plugins
    builtin_plugins = discover_builtin_plugins()
    plugins.update(builtin_plugins)
    
    # 2. Installed plugins (via pip/setuptools entry points)
    installed_plugins = discover_installed_plugins()
    plugins.update(installed_plugins)
    
    # 3. User plugins from specified directories
    if plugin_directories:
        user_plugins = discover_user_plugins(plugin_directories)
        plugins.update(user_plugins)
    
    return plugins

def discover_builtin_plugins():
    """Discover built-in plugins."""
    # Look in aixterm.plugins package
    
def discover_installed_plugins():
    """Discover plugins installed via pip with entry points."""
    # Use entrypoints to find plugins
    
def discover_user_plugins(directories):
    """Discover plugins in user-defined directories."""
    # Search directories for plugin modules/packages
```

### Plugin Development

Guidelines for creating new plugins:

1. **Create Plugin Class**:
   ```python
   from aixterm.plugins import Plugin
   
   class DevTeamPlugin(Plugin):
       @property
       def id(self):
           return "devteam"
       
       @property
       def name(self):
           return "DevTeam"
       
       @property
       def version(self):
           return "0.1.0"
       
       @property
       def description(self):
           return "AI-powered software development team"
       
       def initialize(self):
           # Setup resources and state
           self.devteam = DevTeamCore(self.service)
           return self.devteam.initialize()
       
       def shutdown(self):
           # Clean up resources
           return self.devteam.shutdown()
       
       def get_commands(self):
           return {
               "task_submit": self.handle_task_submit,
               "task_status": self.handle_task_status,
               # Other commands
           }
       
       def handle_task_submit(self, request):
           # Process task submission
           payload = request.get("payload", {})
           task = self.devteam.create_task(
               title=payload.get("title"),
               description=payload.get("description"),
               task_type=payload.get("task_type", "feature"),
               priority=payload.get("priority", "medium")
           )
           return {
               "status": "success",
               "task_id": task.id
           }
       
       def handle_task_status(self, request):
           # Get task status
           task_id = request.get("payload", {}).get("task_id")
           status = self.devteam.get_task_status(task_id)
           return {
               "status": "success",
               "task_status": status
           }
   ```

2. **Package the Plugin**:
   - Create a proper Python package
   - Include setup.py with entry points
   - Add plugin-specific dependencies

3. **Register Entry Points**:
   ```python
   # In setup.py
   setup(
       name="aixterm-devteam",
       # ...
       entry_points={
           "aixterm.plugins": [
               "devteam=aixterm_devteam.plugin:DevTeamPlugin",
           ],
       },
   )
   ```

## DevTeam Plugin Design

### Overview

The DevTeam plugin for AIxTerm will port the functionality of the DevTeam manager from Pythonium, adapting it to the AIxTerm plugin architecture while preserving all key features:

- AI agent orchestration
- Task management workflow
- LangGraph-based agent coordination
- Performance optimization system
- Event-driven communication

### Component Mapping

This section maps Pythonium DevTeam manager components to AIxTerm plugin components:

| Pythonium Component | AIxTerm Plugin Component |
|---------------------|--------------------------|
| `DevTeamManager` | `DevTeamPlugin` |
| Event bus integration | Plugin event system |
| Manager lifecycle | Plugin lifecycle |
| Task submission | Plugin commands |
| Agent framework | Internal plugin structure |
| LangGraph integration | Preserved as-is |
| Prompt optimization | Preserved as-is |

### Implementation Structure

```
aixterm_devteam/
├── __init__.py
├── plugin.py             # Main plugin class
├── core.py               # Core plugin functionality
├── config.py             # Configuration schemas
├── agents/               # Agent implementations
│   ├── __init__.py
│   ├── base.py
│   ├── project_manager.py
│   ├── architect.py
│   └── ...
├── workflows/            # LangGraph workflows
│   ├── __init__.py
│   ├── base.py
│   ├── feature.py
│   └── ...
├── orchestration/        # Advanced orchestration
│   ├── __init__.py
│   ├── complexity.py
│   ├── patterns.py
│   └── ...
└── optimization/         # Prompt optimization
    ├── __init__.py
    ├── analyzer.py
    ├── testing.py
    └── ...
```

### Core Functionality

```python
class DevTeamCore:
    """Core functionality for the DevTeam plugin."""
    
    def __init__(self, plugin):
        self.plugin = plugin
        self.service = plugin.service
        self.config = plugin.service.config.plugins.get("devteam", {}).get("settings", {})
        self.tasks = {}
        self.agents = {}
        self.workflows = {}
    
    def initialize(self):
        """Initialize the DevTeam core."""
        # Setup agents
        self._setup_agents()
        
        # Setup workflows
        self._setup_workflows()
        
        # Setup event listeners
        self._setup_events()
        
        return True
    
    def shutdown(self):
        """Shutdown the DevTeam core."""
        # Clean up resources
        # Stop running tasks
        # Unregister events
        return True
    
    def create_task(self, title, description, task_type="feature", priority="medium"):
        """Create a new development task."""
        task_id = f"task-{uuid.uuid4()}"
        task = {
            "id": task_id,
            "title": title,
            "description": description,
            "type": task_type,
            "priority": priority,
            "status": "created",
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat()
        }
        self.tasks[task_id] = task
        
        # Start task processing in background
        asyncio.create_task(self._process_task(task_id))
        
        return task
    
    def get_task_status(self, task_id):
        """Get the status of a task."""
        if task_id not in self.tasks:
            return None
        return self.tasks[task_id]
    
    async def _process_task(self, task_id):
        """Process a task in the background."""
        task = self.tasks[task_id]
        
        # Update status
        task["status"] = "processing"
        task["updated_at"] = datetime.datetime.now().isoformat()
        
        try:
            # Determine workflow based on task type
            workflow = self._get_workflow(task["type"])
            
            # Execute workflow
            result = await workflow.execute(task)
            
            # Update task with results
            task["status"] = "completed"
            task["result"] = result
            task["updated_at"] = datetime.datetime.now().isoformat()
        except Exception as e:
            # Handle errors
            task["status"] = "failed"
            task["error"] = str(e)
            task["updated_at"] = datetime.datetime.now().isoformat()
    
    def _setup_agents(self):
        """Set up agent instances."""
        # Initialize agent registry with all agent types
        pass
    
    def _setup_workflows(self):
        """Set up workflow instances."""
        # Initialize workflow registry with all workflow types
        pass
    
    def _setup_events(self):
        """Set up event listeners."""
        # Register event handlers
        pass
    
    def _get_workflow(self, task_type):
        """Get the appropriate workflow for a task type."""
        if task_type not in self.workflows:
            raise ValueError(f"Unsupported task type: {task_type}")
        return self.workflows[task_type]
```

## Context System Architecture

The AIxTerm Context System is a sophisticated, modular framework designed to provide intelligent, relevant context to the LLM. It consists of several specialized components that work together to generate rich, token-optimized context.

### Core Components

#### 1. TerminalContext

The central coordination point for all context-related functionality:

- Integrates all context components into a cohesive system
- Manages the overall context generation workflow
- Coordinates between different context sources
- Balances token usage across context components

```python
class TerminalContext:
    def __init__(self, config_manager, logger):
        self.config = config_manager
        self.logger = logger
        self.log_processor = LogProcessor(config_manager, logger)
        self.directory_handler = DirectoryHandler(config_manager, logger)
        self.token_manager = TokenManager(config_manager, logger)
        self.tool_optimizer = ToolOptimizer(config_manager, logger)
```

#### 2. Log Processor (Modular Implementation)

The Log Processor has been fully modularized into specialized components:

**Modular Architecture**:
- `processor.py`: Main LogProcessor class integrating all components
- `tty_utils.py`: TTY detection and management utilities
- `parsing.py`: Log content parsing with command extraction
- `tokenization.py`: Text truncation and token management
- `summary.py`: Intelligent summarization of terminal history

```python
# processor.py
class LogProcessor:
    """Handles log file processing and conversation history."""

    def __init__(self, config_manager, logger):
        self.config = config_manager
        self.logger = logger
    
    def find_log_file(self) -> Optional[Path]:
        """Find the appropriate log file for the current terminal session."""
        # Using tty_utils for TTY detection
        current_tty = self._get_current_tty()
        expected_log = Path.home() / f".aixterm_log.{current_tty}"
        return expected_log if expected_log.exists() else None
        
    def read_and_process_log(self, log_path, max_tokens=None, model_name=None, smart_summarize=True):
        """Read and process log file content with intelligent summarization."""
        # Using tokenization and summary modules
```

**Key Capabilities**:
- Cross-platform TTY detection and log file matching
- Intelligent truncation of log content based on token limits
- Command extraction and conversation history parsing
- Tiered summarization of terminal history
- TTY validation for log file security

#### 3. Directory Handler

Analyzes the file system to provide project context:

- Detects project types based on file signatures
- Generates directory structure summaries
- Identifies important files for context
- Creates file content summaries

#### 4. Token Manager

Manages token usage across context components:

- Estimates token counts for different content
- Allocates token budgets to context components
- Truncates content to stay within token limits
- Provides token-aware content optimization

#### 5. Tool Optimizer

Selects and prioritizes tools based on the context:

- Determines which tools are relevant to the current task
- Manages tool definitions and examples
- Optimizes tool parameters based on context

## Integration and Implementation Plan

To implement this architecture, we will:

1. **Start with Service Framework**:
   - Create service and client base classes
   - Implement communication protocol
   - Build service installation for all platforms

2. **Add Plugin System**:
   - Implement plugin base class and manager
   - Add plugin discovery and loading
   - Create plugin command registration

3. **Migrate DevTeam**:
   - Port DevTeam manager to plugin architecture
   - Adapt event system to plugin events
   - Migrate advanced features

4. **Integrate with AIxTerm**:
   - Connect to existing context system
   - Use existing LLM clients
   - Preserve CLI interface

## Conclusion

This design document outlines the service architecture, plugin system, and DevTeam plugin migration approach for AIxTerm. By implementing this architecture, we'll transform AIxTerm into a more powerful, flexible system capable of supporting advanced AI development workflows while maintaining its core functionality and user experience.

The service-based approach and plugin system provide a solid foundation for future extensions, while the DevTeam plugin brings sophisticated AI-powered development capabilities from Pythonium into the AIxTerm ecosystem.
