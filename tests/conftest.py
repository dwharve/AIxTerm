"""Pytest configuration and fixtures."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aixterm.cleanup import CleanupManager
from aixterm.config import AIxTermConfig
from aixterm.context import TerminalContext
from aixterm.llm import LLMClient
from aixterm.mcp_client import MCPClient


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    with patch.object(AIxTermConfig, "_load_config") as mock_load:
        mock_load.return_value = {
            "model": "test-model",
            "system_prompt": "You are a test assistant.",
            "api_url": "http://localhost/v1/chat/completions",
            "api_key": "",
            "context_size": 1000,
            "response_buffer_size": 300,
            "mcp_servers": [],
            "cleanup": {
                "enabled": True,
                "max_log_age_days": 30,
                "max_log_files": 10,
                "cleanup_interval_hours": 24,
            },
            "logging": {"level": "INFO", "file": None},
        }

        config = AIxTermConfig()
        yield config


@pytest.fixture
def mock_home_dir(temp_dir, monkeypatch):
    """Mock the home directory to use a temporary directory."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    return temp_dir


@pytest.fixture
def sample_log_file(mock_home_dir):
    """Create a sample log file for testing."""
    log_path = mock_home_dir / ".aixterm_log.test"
    log_content = """$ ls -la
total 12
drwxr-xr-x 2 user user 4096 Jan 1 12:00 .
drwxr-xr-x 3 user user 4096 Jan 1 12:00 ..
-rw-r--r-- 1 user user   42 Jan 1 12:00 test.txt
$ cat test.txt
Hello, world!
$ pwd
/home/user/test
"""
    log_path.write_text(log_content)
    return log_path


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return """Here's how you can list processes:

```bash
ps aux
```

This will show all running processes with detailed information."""


@pytest.fixture
def mock_requests_post():
    """Mock requests.post for LLM API calls."""
    with patch("aixterm.llm.client.requests.post") as mock_post:
        # Mock streaming response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        # Mock streaming response with platform-specific command
        import sys

        if sys.platform == "win32":
            command_output = "\\n\\n```cmd\\ntasklist\\n```"
        else:
            command_output = "\\n\\n```bash\\nps aux\\n```"

        mock_response.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"Here\'s how"}}]}',
            b'data: {"choices":[{"delta":{"content":" to list processes:"}}]}',
            (
                f'data: {{"choices":[{{"delta":{{"content":"{command_output}"'
                f"}}}}]}}"
            ).encode(),
            b"data: [DONE]",
        ]
        mock_post.return_value = mock_response
        yield mock_post


@pytest.fixture
def context_manager(mock_config):
    """Create a TerminalContext instance with mock config."""
    return TerminalContext(mock_config)


@pytest.fixture
def mcp_client(mock_config):
    """Create an MCPClient instance with mock config."""
    return MCPClient(mock_config)


@pytest.fixture
def cleanup_manager(mock_config):
    """Create a CleanupManager instance with mock config."""
    return CleanupManager(mock_config)


@pytest.fixture
def llm_client(mock_config, mcp_client):
    """Create an LLMClient instance with mock config and mcp client."""
    return LLMClient(mock_config, mcp_client)
