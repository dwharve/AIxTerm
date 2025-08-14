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


def mock_coro(return_value=None):
    """
    Create a mock coroutine function that returns the specified value.

    This helper function can be used to mock async functions without causing
    "coroutine was never awaited" warnings during tests.

    Args:
        return_value: The value to be returned when the coroutine is awaited.

    Returns:
        A coroutine function that returns the specified value.
    """

    async def mock_async_function(*args, **kwargs):
        return return_value

    return mock_async_function


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
def mock_openai_client():
    """Mock OpenAI client for LLM API calls."""
    with patch("aixterm.llm.client.OpenAI") as mock_openai_class:
        # Create mock client instance
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock streaming response
        mock_chunk1 = Mock()
        mock_chunk1.choices = [Mock()]
        mock_chunk1.choices[0].delta = Mock()
        mock_chunk1.choices[0].delta.content = "Here's how to "
        mock_chunk1.choices[0].delta.tool_calls = None

        mock_chunk2 = Mock()
        mock_chunk2.choices = [Mock()]
        mock_chunk2.choices[0].delta = Mock()
        mock_chunk2.choices[0].delta.tool_calls = None

        # Mock platform-specific command output
        import sys

        if sys.platform == "win32":
            mock_chunk2.choices[0].delta.content = "list processes: tasklist"
        else:
            mock_chunk2.choices[0].delta.content = "list processes: ps aux"

        mock_chunks = [mock_chunk1, mock_chunk2]

        # Mock non-streaming response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = (
            "Here's how to list processes: ps aux"
        )
        mock_response.choices[0].message.tool_calls = None

        # Configure the mock to return either streaming or non-streaming
        # based on the stream parameter
        def create_side_effect(**kwargs):
            if kwargs.get("stream", False):
                return iter(mock_chunks)
            else:
                return mock_response

        mock_client.chat.completions.create.side_effect = create_side_effect

        yield mock_client


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
