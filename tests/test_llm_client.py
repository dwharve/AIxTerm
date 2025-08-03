"""
Test cases for the LLM client V2.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock the dependencies before importing the module
patch("aixterm.context.TokenManager").start()
patch("aixterm.context.ToolOptimizer").start()
patch("aixterm.llm.message_validator.MessageValidator").start()
patch("aixterm.llm.tools.ToolHandler").start()
patch("aixterm.utils.get_logger", return_value=MagicMock()).start()

from aixterm.llm.client import LLMClient as LLMClientV2


@pytest.fixture
def mock_config():
    """Mock configuration manager."""
    config = MagicMock()
    config.get = MagicMock(
        side_effect=lambda key, default=None: {
            "model": "gpt-3.5-turbo",
            "temperature": 0.0,
            "max_tokens": 1000,
        }.get(key, default)
    )
    # Fix the base_url issue
    config.get_openai_base_url = MagicMock(return_value=None)
    return config


@pytest.fixture
def mock_mcp_client():
    """Mock MCP client."""
    return MagicMock()


@pytest.fixture
def mock_display_manager():
    """Mock display manager."""
    display_manager = MagicMock()
    progress = MagicMock()
    progress.start = MagicMock()
    progress.update = MagicMock()
    progress.stop = MagicMock()
    display_manager.create_llm_progress = MagicMock(return_value=progress)
    return display_manager


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    client = MagicMock()
    completions = MagicMock()
    chat = MagicMock()
    chat.completions = completions
    client.chat = chat
    return client


@pytest.fixture
def client(mock_config, mock_mcp_client, mock_display_manager, mock_openai_client):
    """Test LLM client V2 instance."""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        # Create the client
        client = LLMClientV2(
            config_manager=mock_config,
            mcp_client=mock_mcp_client,
            display_manager=mock_display_manager,
        )

        # Replace the OpenAI client with our mock
        client.openai_client = mock_openai_client

        yield client


def test_complete_non_streaming(client, mock_openai_client):
    """Test non-streaming completion."""
    # Set up mock response
    mock_message = MagicMock()
    mock_message.content = "This is a test response"

    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_choice.index = 0
    mock_choice.finish_reason = "stop"

    mock_completion = MagicMock()
    mock_completion.id = "test-completion-id"
    mock_completion.created = 1616784000
    mock_completion.model = "gpt-3.5-turbo"
    mock_completion.choices = [mock_choice]

    # Set up the client to use our mock
    client.openai_client = mock_openai_client
    mock_openai_client.chat.completions.create.return_value = mock_completion

    # Fix the base_url issue
    client.config.get_openai_base_url = lambda: None

    # Test messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    # Create a mock for _handle_non_streaming
    mock_handle = MagicMock(return_value="This is a test response")

    # Replace the method with our mock
    original_handle = client._handle_non_streaming
    client._handle_non_streaming = mock_handle

    try:
        # Call the client with the chat_completion method
        response = client.chat_completion(messages, stream=False)

        # Check the response
        assert response == "This is a test response"

        # Verify our mock was called correctly
        mock_handle.assert_called_once_with(messages, None)
    finally:
        # Restore the original method
        client._handle_non_streaming = original_handle


def test_complete_streaming(client, mock_openai_client):
    """Test streaming completion."""
    # Set up mock stream
    mock_delta1 = MagicMock()
    mock_delta1.content = "This "

    mock_choice1 = MagicMock()
    mock_choice1.delta = mock_delta1
    mock_choice1.index = 0
    mock_choice1.finish_reason = None

    mock_chunk1 = MagicMock()
    mock_chunk1.id = "test-chunk-id-1"
    mock_chunk1.choices = [mock_choice1]

    mock_delta2 = MagicMock()
    mock_delta2.content = "is a "

    mock_choice2 = MagicMock()
    mock_choice2.delta = mock_delta2
    mock_choice2.index = 0
    mock_choice2.finish_reason = None

    mock_chunk2 = MagicMock()
    mock_chunk2.id = "test-chunk-id-2"
    mock_chunk2.choices = [mock_choice2]

    mock_delta3 = MagicMock()
    mock_delta3.content = "test."

    mock_choice3 = MagicMock()
    mock_choice3.delta = mock_delta3
    mock_choice3.index = 0
    mock_choice3.finish_reason = "stop"

    mock_chunk3 = MagicMock()
    mock_chunk3.id = "test-chunk-id-3"
    mock_chunk3.choices = [mock_choice3]

    mock_stream = [mock_chunk1, mock_chunk2, mock_chunk3]

    # Set up the client to use our mock
    client.openai_client = mock_openai_client
    mock_openai_client.chat.completions.create.return_value = mock_stream

    # Fix the base_url issue
    client.config.get_openai_base_url = lambda: None

    # Test messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    # Create a mock for _handle_streaming
    mock_handle = MagicMock(return_value="This is a test response")

    # Replace the method with our mock
    original_handle = client._handle_streaming
    client._handle_streaming = mock_handle

    try:
        # Call the client with the chat_completion method using stream=True
        response = client.chat_completion(messages, stream=True)

        # Check the response
        assert response == "This is a test response"

        # Verify our mock was called correctly
        mock_handle.assert_called_once_with(messages, None)
    finally:
        # Restore the original method
        client._handle_streaming = original_handle
