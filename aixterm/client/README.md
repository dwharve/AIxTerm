# Client Module

## Overview
The client module provides HTTP client functionality for AIxTerm's server mode. This enables remote communication with AIxTerm instances running as web services.

## Key Components

### client.py
- **AIxTermClient**: Main client class for communicating with AIxTerm service
- **Dual Transport**: Supports both socket and HTTP communication modes
- **Cross-Platform**: Handles Unix sockets on Linux/macOS, TCP on Windows
- **Connection Management**: Automatic connection handling and error recovery
- **Configuration Integration**: Uses AIxTermConfig for transport settings

## Architecture

```
client/
├── client.py          # Main HTTP client implementation
└── __init__.py        # Module exports
```

## Usage Patterns

### Basic Client Usage
```python
from aixterm.client import AIxTermClient

# Initialize with default config
client = AIxTermClient()

# Connect to service (auto-detects transport mode)
if client.connect():
    response = client.send_request("list running processes")
    print(response)
```

### Transport Modes
- **Socket Mode**: Fast Unix socket communication (Linux/macOS)
- **HTTP Mode**: Web-based communication for remote access
- **Auto-Detection**: Automatically selects best transport method
- **Cross-Platform**: TCP fallback on Windows systems
- **Configuration**: Transport mode configurable via AIxTermConfig

## Integration Points
- **Server Module**: Communicates with `aixterm.server` endpoints
- **Main Module**: Used by CLI when connecting to remote instances
- **Config Module**: Inherits server URL and authentication settings

## Error Handling
- Connection timeouts and retries
- Authentication failures
- Server error responses
- Network connectivity issues

## Security Considerations
- API key management
- HTTPS enforcement for production
- Request/response validation
- Rate limiting compliance
