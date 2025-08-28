# Client Module

## Overview
The client module provides communication with the unified local AIxTerm service
over a Unix domain socket located in the user's home runtime directory:

```
~/.aixterm/server.sock
```

The application now auto-starts a single local socket service on demand.

## Key Components

### client.py
- **AIxTermClient**: Main client class for communicating with AIxTerm service
- **Unified Transport**: Unix domain socket IPC (`.aixterm/server.sock`)
- **Auto Start**: Launches the service transparently if not running
- **Connection Management**: Automatic connection handling and error recovery
- **Configuration Integration**: Uses AIxTermConfig for transport settings

## Architecture

```
client/
├── client.py          # Socket client implementation
└── __init__.py        # Module exports
```

## Usage Patterns

### Basic Client Usage
```python
from aixterm.client import AIxTermClient

# Initialize with default config
client = AIxTermClient()

# Send a request (auto-starts service & connects transparently)
response = client.send_request("list running processes")
print(response)
```

### Transport
All requests go through the local Unix domain socket. No configuration flags
are required.

## Integration Points
- **Service Layer**: Communicates with the unified local service via socket
- **Main Module**: Used by CLI when connecting to remote instances
- **Config Module**: Inherits server URL and authentication settings

## Error Handling
- Connection timeouts and retries
- Authentication failures
- Server error responses
- Socket availability & auto-start race handling

## Security Considerations
- Minimal local attack surface (no open TCP port)
- Local-only IPC (Unix domain socket)
- Request/response validation
