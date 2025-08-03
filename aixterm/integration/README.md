# Integration Module

The Integration module is a core component of AIxTerm that provides seamless shell integration for automatic terminal activity logging and context capture. It enables the AI assistant to maintain comprehensive awareness of your terminal sessions across different shell environments.

## Overview

The Integration module consists of:
- **BaseIntegration** - Abstract base class defining the integration interface
- **Shell-specific implementations** - Bash, Zsh, and Fish integrations
- **Automatic logging** - Command execution and output capture
- **Session management** - TTY-based session isolation and log management
- **Cross-platform support** - Works on Linux, macOS, and other Unix-like systems

## Architecture

### Core Components

1. **BaseIntegration (Abstract)** - Foundation class with common functionality
2. **Bash Integration** - Full-featured bash shell integration
3. **Zsh Integration** - Zsh shell integration with advanced features
4. **Fish Integration** - Fish shell integration with modern syntax
5. **Session Management** - TTY-based isolation and log file management
6. **Command Logging** - Intelligent command and output capture

## Key Features

### 🔧 Multi-Shell Support

The integration module supports the three most popular shells:
- **Bash** (.bashrc, .bash_profile)
- **Zsh** (.zshrc) 
- **Fish** (.config/fish/config.fish)

### 📊 Intelligent Logging

- **Command Capture**: Automatically logs all executed commands
- **Output Logging**: Captures command outputs for context
- **Session Isolation**: TTY-based log separation for multiple terminals
- **Metadata**: Timestamps, TTY information, and exit codes

### 🛡️ Safe Integration

- **Backup Creation**: Automatic backup of shell configuration files
- **Clean Uninstall**: Complete removal of integration code
- **Non-destructive**: Preserves existing shell configurations
- **Error Handling**: Graceful handling of integration failures

### 🎯 Context Optimization

- **Smart Filtering**: Excludes internal commands and noise
- **Session Continuity**: Maintains context across terminal sessions
- **Log Management**: Automatic cleanup of old log files
- **Performance**: Minimal impact on shell performance

## API Reference

### BaseIntegration Class

The abstract base class that defines the integration interface.

#### Abstract Properties

```python
@property
@abstractmethod
def shell_name(self) -> str:
    """Return the name of the shell this integration supports."""

@property
@abstractmethod
def config_files(self) -> List[str]:
    """Return list of possible configuration file paths relative to home."""
```

#### Abstract Methods

```python
@abstractmethod
def generate_integration_code(self) -> str:
    """Generate the shell-specific integration code."""

@abstractmethod
def is_available(self) -> bool:
    """Check if the shell is available on the system."""

@abstractmethod
def validate_integration_environment(self) -> bool:
    """Validate that the environment is suitable for integration."""

@abstractmethod
def get_installation_notes(self) -> List[str]:
    """Return shell-specific installation notes."""

@abstractmethod
def get_troubleshooting_tips(self) -> List[str]:
    """Return shell-specific troubleshooting tips."""
```

#### Core Methods

##### `install(force: bool = False, interactive: bool = True) -> bool`
Installs the shell integration to the appropriate configuration file.

**Parameters:**
- `force`: Whether to force reinstall if already installed
- `interactive`: Whether to prompt user for input

**Returns:** True if installation successful

**Example:**
```python
from aixterm.integration import Bash

bash_integration = Bash()
success = bash_integration.install(force=False, interactive=True)
if success:
    print("Bash integration installed successfully!")
```

##### `uninstall() -> bool`
Uninstalls the shell integration from all configuration files.

**Returns:** True if uninstallation successful

**Example:**
```python
success = bash_integration.uninstall()
if success:
    print("Integration removed successfully!")
```

##### `is_integration_installed(config_file: Path) -> bool`
Checks if integration is already installed in the specified config file.

**Parameters:**
- `config_file`: Path to shell config file

**Returns:** True if integration is already installed

##### `find_config_file() -> Optional[Path]`
Finds existing config file or returns path for the primary one.

**Returns:** Path to config file to use

#### Utility Methods

##### `get_selected_config_file() -> Optional[Path]`
Gets the configuration file path that was or will be used.

##### `_create_backup(config_file: Path) -> bool`
Creates a timestamped backup of the configuration file.

##### `_remove_existing_integration(config_file: Path) -> bool`
Removes existing integration code from configuration file.

## Shell-Specific Implementations

### Bash Integration

**Configuration Files:** `.bashrc`, `.bash_profile`

**Key Features:**
- Command logging with BASH_COMMAND variable
- Exit code capture
- TTY-based session isolation
- History integration
- Pre/post command hooks

**Generated Functions:**
```bash
ai()                        # Enhanced AI command with logging
aixterm_status()           # Show integration status
aixterm_flush_session()    # Manual session flush
aixterm_cleanup_logs()     # Clean old log files
aixterm_clear_log()        # Clear current session log
log_with_output()          # Explicit output capture
```

**Example Usage:**
```python
from aixterm.integration import Bash

bash = Bash()
if bash.is_available():
    success = bash.install()
    if success:
        print("Restart your terminal or run: source ~/.bashrc")
```

### Zsh Integration

**Configuration Files:** `.zshrc`

**Key Features:**
- Advanced command logging with zsh hooks
- Precmd/preexec functions
- History management
- TTY detection
- Performance optimizations

**Generated Functions:**
```zsh
ai()                        # Enhanced AI command with logging
aixterm_status()           # Show integration status  
aixterm_flush_session()    # Manual session flush
aixterm_cleanup_logs()     # Clean old log files
aixterm_clear_log()        # Clear current session log
```

**Example Usage:**
```python
from aixterm.integration import Zsh

zsh = Zsh()
if zsh.is_available():
    success = zsh.install()
    if success:
        print("Restart your terminal or run: source ~/.zshrc")
```

### Fish Integration

**Configuration Files:** `.config/fish/config.fish`

**Key Features:**
- Fish-native function syntax
- Event-based command logging
- Modern shell features
- Cross-platform TTY detection
- Performance optimizations

**Generated Functions:**
```fish
ai                         # Enhanced AI command with logging
aixterm_status            # Show integration status
aixterm_flush_session     # Manual session flush  
aixterm_cleanup_logs      # Clean old log files
aixterm_clear_log         # Clear current session log
```

**Example Usage:**
```python
from aixterm.integration import Fish

fish = Fish()
if fish.is_available():
    success = fish.install()
    if success:
        print("Restart your terminal to activate integration")
```

## Session Management

### TTY-Based Isolation

Each terminal session gets its own log file based on TTY:
```
~/.aixterm_log.pts-0        # Terminal 1
~/.aixterm_log.pts-1        # Terminal 2  
~/.aixterm_log.console      # Console session
~/.aixterm_log.default      # Fallback
```

### Log File Structure

Log files contain structured information:
```bash
# Command at 2025-07-01 10:30:15 on /dev/pts/0: ls -la
# Exit code: 0

# AI command executed at 2025-07-01 10:31:20 on /dev/pts/0
$ ai "show me python files"
[AI response content...]

# Session flushed at 2025-07-01 10:35:00
```

### Automatic Cleanup

The integration includes intelligent log cleanup:
- **Active Session Protection**: Never removes logs for active terminals
- **Age-Based Cleanup**: Removes logs older than specified days (default: 7)
- **Safe Removal**: Checks TTY activity before deletion
- **Manual Control**: Functions for manual cleanup

## Installation Process

### Automatic Installation

The integration handles the complete installation process:

1. **Shell Detection**: Identifies available shells
2. **Environment Validation**: Checks prerequisites
3. **Config File Location**: Finds or creates configuration files
4. **Backup Creation**: Creates timestamped backups
5. **Code Injection**: Adds integration code
6. **Verification**: Confirms successful installation

### Installation Workflow

```python
from aixterm.integration import Bash, Zsh, Fish

# Detect and install for all available shells
shells = [Bash(), Zsh(), Fish()]
installed_shells = []

for shell in shells:
    if shell.is_available():
        if shell.validate_integration_environment():
            success = shell.install(interactive=True)
            if success:
                installed_shells.append(shell.shell_name)
                
print(f"Installed for shells: {', '.join(installed_shells)}")
```

### Installation Notes

Each shell provides specific installation guidance:

**Bash:**
- Checks for `.bashrc` vs `.bash_profile` on different systems
- Handles login vs non-login shell differences
- Provides sourcing instructions

**Zsh:**
- Integrates with Oh My Zsh and other frameworks
- Handles plugin conflicts
- Provides framework-specific advice

**Fish:**
- Creates config directory if needed
- Handles Fish-specific syntax
- Provides function-based integration

## Command Logging

### Intelligent Filtering

The integration automatically filters out noise:

**Excluded Commands:**
- Internal shell functions (`_aixterm_*`, `__vsc_*`)
- History commands
- Prompt commands
- Built-in commands
- Trap commands
- IDE/editor integrations

**Included Commands:**
- User-executed commands
- Script executions
- AI assistant commands
- System commands
- Development tools

### Metadata Capture

Each logged command includes:
- **Timestamp**: Exact execution time
- **TTY Information**: Terminal session identifier
- **Exit Code**: Command success/failure status
- **Command Line**: Full command with arguments
- **Context**: Session and environment information

### Output Capture

Different levels of output capture:

**Basic Logging**: Command and exit code only
```bash
# Command at 2025-07-01 10:30:15: ls -la
# Exit code: 0
```

**Enhanced Logging**: With output capture
```bash
# Command with output capture at 2025-07-01 10:30:15: ls -la
# Output:
total 24
drwxr-xr-x  5 user user 4096 Jul  1 10:30 .
drwxr-xr-x 20 user user 4096 Jul  1 10:25 ..
-rw-r--r--  1 user user  220 Jul  1 10:20 .bashrc
# Exit code: 0
```

## Configuration and Customization

### Environment Variables

The integration recognizes several environment variables:

```bash
# Control integration behavior
export _AIXTERM_INTEGRATION_LOADED=1    # Marks integration as loaded
export _AIXTERM_LOG_LEVEL=INFO          # Set logging verbosity
export _AIXTERM_LOG_OUTPUT=true         # Enable output capture
export _AIXTERM_SESSION_ID=custom       # Custom session identifier
```

### Integration Detection

Check if integration is active:
```bash
# In bash/zsh
aixterm_status

# In fish  
aixterm_status
```

### Manual Session Management

Control session logging manually:
```bash
# Flush current session to log
aixterm_flush_session

# Clear current session log
aixterm_clear_log

# Clean up old logs (default: 7 days)
aixterm_cleanup_logs

# Clean up logs older than 14 days
aixterm_cleanup_logs 14
```

## Error Handling and Recovery

### Common Issues and Solutions

#### Integration Not Working
```python
# Check if shell is available
if not bash.is_available():
    print("Bash is not installed or not in PATH")

# Validate environment
if not bash.validate_integration_environment():
    print("Environment validation failed")
    
# Check installation status
config_file = bash.find_config_file()
if not bash.is_integration_installed(config_file):
    print("Integration not installed")
```

#### Log File Issues
```bash
# Check log file permissions
ls -la ~/.aixterm_log.*

# Manually create log file
touch ~/.aixterm_log.$(tty | sed 's|/dev/||g' | sed 's|/|-|g')

# Fix permissions
chmod 644 ~/.aixterm_log.*
```

#### TTY Detection Problems
```bash
# Manual TTY check
tty

# Check TTY in environment
echo $SSH_TTY

# Use default log file
export _AIXTERM_LOG_FILE="$HOME/.aixterm_log.default"
```

### Recovery Procedures

#### Restore from Backup
```python
import glob
from pathlib import Path

# Find backup files
backups = glob.glob(str(Path.home() / ".bashrc.aixterm_backup_*"))
latest_backup = max(backups, key=lambda x: Path(x).stat().st_mtime)

# Restore backup
config_file = Path.home() / ".bashrc"
config_file.write_text(Path(latest_backup).read_text())
```

#### Clean Reinstall
```python
# Uninstall completely
bash.uninstall()

# Force reinstall
bash.install(force=True)
```

#### Manual Cleanup
```python
# Remove all integration-related files
import glob
from pathlib import Path

# Remove log files
for log_file in glob.glob(str(Path.home() / ".aixterm_log.*")):
    Path(log_file).unlink()

# Remove backups (optional)
for backup in glob.glob(str(Path.home() / ".*aixterm_backup_*")):
    Path(backup).unlink()
```

## Testing and Validation

### Integration Testing

Test shell integration functionality:

```python
import tempfile
from pathlib import Path
from aixterm.integration import Bash

def test_bash_integration():
    """Test bash integration installation and removal."""
    bash = Bash()
    
    # Test availability
    assert bash.is_available() == True
    
    # Test config file detection
    config_file = bash.find_config_file()
    assert config_file is not None
    
    # Test integration code generation
    code = bash.generate_integration_code()
    assert "AIxTerm Shell Integration" in code
    assert "ai()" in code
    
    # Test installation in temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.bashrc', delete=False) as f:
        temp_config = Path(f.name)
        
    try:
        # Install integration
        bash._install_integration_code(temp_config)
        
        # Verify installation
        assert bash.is_integration_installed(temp_config) == True
        
        # Test removal
        bash._remove_existing_integration(temp_config)
        assert bash.is_integration_installed(temp_config) == False
        
    finally:
        temp_config.unlink()
```

### Functionality Testing

Test generated shell functions:

```bash
# Test in actual shell environment

# Source the integration
source ~/.bashrc

# Test ai function
ai "test command"

# Test status function
aixterm_status

# Test log management
aixterm_flush_session
aixterm_clear_log

# Verify log file creation
ls -la ~/.aixterm_log.*
```

### Performance Testing

Monitor integration performance impact:

```bash
# Time shell startup with/without integration
time bash -c 'exit'

# Monitor memory usage
ps aux | grep bash

# Check log file growth
watch -n 1 'ls -lh ~/.aixterm_log.*'
```

## Performance Considerations

### Minimal Overhead

The integration is designed for minimal performance impact:

- **Lazy Loading**: Functions loaded only when needed
- **Efficient Filtering**: Quick command exclusion checks
- **Async Logging**: Non-blocking log writes
- **Smart Buffering**: Efficient I/O operations

### Memory Management

- **Log Rotation**: Automatic cleanup of old files
- **Size Limits**: Prevention of excessive log growth  
- **Session Isolation**: Separate logs prevent conflicts
- **Garbage Collection**: Cleanup of temporary data

### Optimization Tips

1. **Regular Cleanup**: Run `aixterm_cleanup_logs` periodically
2. **Monitor Log Size**: Check log file sizes occasionally
3. **Disable When Not Needed**: Temporarily disable for performance-critical tasks
4. **Use Appropriate Shell**: Fish is generally fastest, Bash most compatible

## Security Considerations

### Safe Code Injection

- **Marker-Based Removal**: Clean integration removal
- **Backup Creation**: Automatic configuration backups
- **Validation**: Environment checks before installation
- **Error Handling**: Graceful failure modes

### Log File Security

- **User Permissions**: Log files owned by user only
- **Location**: Logs stored in user home directory
- **Content Filtering**: Sensitive information handling
- **Cleanup**: Automatic removal of old logs

### Shell Safety

- **Non-Destructive**: Preserves existing configurations
- **Reversible**: Complete uninstall capability
- **Isolated**: No interference with other tools
- **Validated**: Environment checks before modifications

## Best Practices

### Installation

1. **Test First**: Test in a non-production environment
2. **Backup Manually**: Create manual backups before installation
3. **Check Compatibility**: Verify shell version compatibility
4. **Read Notes**: Review shell-specific installation notes

### Usage

1. **Monitor Logs**: Occasionally check log file sizes
2. **Clean Regularly**: Run cleanup functions periodically
3. **Update Configs**: Keep shell configurations updated
4. **Test Functions**: Verify integration functions work correctly

### Maintenance

1. **Regular Cleanup**: Schedule log cleanup tasks
2. **Backup Retention**: Manage backup file retention
3. **Performance Monitoring**: Watch for performance impacts
4. **Update Integration**: Keep integration code updated

### Troubleshooting

1. **Check Logs**: Review shell startup logs for errors
2. **Test Functions**: Verify each function works independently
3. **Environment**: Validate environment variables
4. **Permissions**: Check file and directory permissions

## Advanced Usage

### Custom Log Processing

Process log files programmatically:

```python
from pathlib import Path
import re

def parse_aixterm_log(log_file: Path):
    """Parse AIxTerm log file for commands and outputs."""
    commands = []
    
    with open(log_file, 'r') as f:
        content = f.read()
    
    # Extract commands with regex
    command_pattern = r'# Command at (.+?): (.+?)\\n# Exit code: (\\d+)'
    matches = re.findall(command_pattern, content, re.MULTILINE)
    
    for timestamp, command, exit_code in matches:
        commands.append({
            'timestamp': timestamp,
            'command': command,
            'exit_code': int(exit_code)
        })
    
    return commands

# Usage
log_file = Path.home() / '.aixterm_log.pts-0'
if log_file.exists():
    commands = parse_aixterm_log(log_file)
    for cmd in commands[-5:]:  # Last 5 commands
        print(f"{cmd['timestamp']}: {cmd['command']}")
```

### Custom Integration

Create custom shell integration:

```python
from aixterm.integration.base import BaseIntegration

class CustomShell(BaseIntegration):
    """Custom shell integration."""
    
    @property
    def shell_name(self) -> str:
        return "custom"
    
    @property  
    def config_files(self) -> List[str]:
        return [".customrc"]
    
    def generate_integration_code(self) -> str:
        return '''
# Custom Shell Integration
# Add custom shell-specific code here
'''
    
    def is_available(self) -> bool:
        import shutil
        return shutil.which("custom") is not None
    
    def validate_integration_environment(self) -> bool:
        return True
    
    def get_installation_notes(self) -> List[str]:
        return ["Custom shell installation notes"]
    
    def get_troubleshooting_tips(self) -> List[str]:
        return ["Custom shell troubleshooting tips"]

# Usage
custom = CustomShell()
if custom.is_available():
    custom.install()
```

### Integration with CI/CD

Use integration in automated environments:

```python
import os
from aixterm.integration import Bash

def setup_ci_integration():
    """Setup integration for CI/CD environment."""
    if os.environ.get('CI'):
        bash = Bash()
        # Install with non-interactive mode
        success = bash.install(force=True, interactive=False)
        if success:
            print("CI integration setup complete")
        return success
    return False

# Usage in CI script
if setup_ci_integration():
    # Continue with AI-enabled terminal tasks
    pass
```

## Future Enhancements

### Planned Features

- **PowerShell Integration**: Windows PowerShell support
- **Enhanced Output Capture**: Selective output logging
- **Cloud Synchronization**: Cross-device log synchronization
- **Real-time Analysis**: Live command analysis and suggestions
- **Integration API**: REST API for external tool integration

### Integration Opportunities

- **IDE Integration**: VS Code, IntelliJ terminal integration
- **Container Support**: Docker and Kubernetes integration
- **Remote Sessions**: SSH and tmux session support
- **Shell Frameworks**: Oh My Zsh, Prezto, Fish frameworks

## Contributing

### Development Setup

```bash
# Clone and setup development environment
git clone https://github.com/dwharve/aixterm.git
cd aixterm
pip install -e .[dev]

# Run integration tests
pytest tests/test_shell_integration.py -v

# Test specific shell
pytest tests/test_shell_integration.py::TestBashIntegration -v
```

### Adding New Shell Support

1. **Create Shell Class**: Extend `BaseIntegration`
2. **Implement Methods**: All abstract methods must be implemented
3. **Generate Code**: Create shell-specific integration script
4. **Add Tests**: Comprehensive test coverage required
5. **Update Documentation**: Add shell to this README

### Testing Guidelines

1. **Test All Shells**: Bash, Zsh, Fish compatibility
2. **Cross-Platform**: Linux, macOS testing
3. **Edge Cases**: Handle TTY detection failures
4. **Performance**: Measure integration overhead
5. **Security**: Validate safe installation/removal

### Code Standards

1. **Type Hints**: Full type annotation required
2. **Documentation**: Comprehensive docstrings
3. **Error Handling**: Graceful error recovery
4. **Logging**: Appropriate log levels
5. **Shell Safety**: Non-destructive modifications

## License

The Integration module is part of AIxTerm and is licensed under the MIT License. See the main project LICENSE file for details.
