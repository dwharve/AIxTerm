"""Tests for LLM client functionality."""

from unittest.mock import Mock, patch

import pytest
import requests

from aixterm.llm import LLMError


class TestLLMClient:
    """Test cases for LLMClient class."""

    def test_chat_completion_streaming(self, llm_client, mock_requests_post):
        """Test streaming chat completion."""
        messages = [
            {"role": "system", "content": "You are a test assistant."},
            {"role": "user", "content": "Hello"},
        ]

        with patch("builtins.print"):  # Suppress print output during tests
            response = llm_client.chat_completion(messages, stream=True)

        assert "Here's how to list processes:" in response
        # Check for platform-specific command
        import sys

        if sys.platform == "win32":
            assert "tasklist" in response
        else:
            assert "ps aux" in response
        mock_requests_post.assert_called_once()

    def test_chat_completion_non_streaming(self, llm_client):
        """Test non-streaming chat completion."""
        messages = [
            {"role": "system", "content": "You are a test assistant."},
            {"role": "user", "content": "Hello"},
        ]

        mock_response_data = {
            "choices": [{"message": {"content": "Hello! How can I help you?"}}]
        }

        with patch("aixterm.llm.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = mock_response_data
            mock_post.return_value = mock_response

            response = llm_client.chat_completion(messages, stream=False)

            assert response == "Hello! How can I help you?"
            mock_post.assert_called_once()

    def test_chat_completion_with_tools(self, llm_client, mock_requests_post):
        """Test chat completion with tools."""
        messages = [{"role": "user", "content": "Test"}]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "description": "A test tool",
                },
            }
        ]

        with patch("builtins.print"):
            llm_client.chat_completion(messages, stream=True, tools=tools)

        # Verify tools were included in the payload
        call_args = mock_requests_post.call_args
        payload = call_args[1]["json"]
        assert "tools" in payload
        assert payload["tools"] == tools
        assert payload["tool_choice"] == "auto"

    def test_request_error_handling(self, llm_client):
        """Test handling of request errors."""
        messages = [{"role": "user", "content": "Test"}]

        with patch("aixterm.llm.requests.post") as mock_post:
            mock_post.side_effect = Exception("Network error")

            with pytest.raises(LLMError, match="Unexpected error"):
                llm_client.chat_completion(messages)

    def test_http_error_handling(self, llm_client):
        """Test handling of HTTP errors."""
        messages = [{"role": "user", "content": "Test"}]

        with patch("aixterm.llm.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = (
                requests.exceptions.RequestException("HTTP 500")
            )
            mock_post.return_value = mock_response

            with pytest.raises(LLMError, match="Error communicating with LLM"):
                llm_client.chat_completion(messages)

    def test_streaming_response_parsing(self, llm_client):
        """Test parsing of streaming response data."""
        mock_lines = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            b'data: {"choices":[{"delta":{"content":" world"}}]}',
            b'data: {"choices":[{"delta":{"content":"!"}}]}',
            b"data: [DONE]",
            b"",  # Empty line
        ]

        with patch("aixterm.llm.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.iter_lines.return_value = mock_lines
            mock_post.return_value = mock_response

            with patch("builtins.print"):
                response = llm_client.chat_completion(
                    [{"role": "user", "content": "Test"}]
                )

            assert response == "Hello world!"

    def test_streaming_response_with_malformed_json(self, llm_client):
        """Test handling of malformed JSON in streaming response."""
        mock_lines = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            b"invalid json line",
            b'data: {"choices":[{"delta":{"content":" world"}}]}',
            b"data: [DONE]",
        ]

        with patch("aixterm.llm.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.iter_lines.return_value = mock_lines
            mock_post.return_value = mock_response

            with patch("builtins.print"):
                response = llm_client.chat_completion(
                    [{"role": "user", "content": "Test"}]
                )

            # Should skip malformed JSON and continue
            assert response == "Hello world"

    def test_tool_call_handling(self, llm_client):
        """Test handling of tool calls in streaming response."""
        mock_lines = [
            (
                b'data: {"choices":[{"delta":{"tool_calls":'
                b'[{"function":{"name":"test_tool"}}]}}]}'
            ),
            b'data: {"choices":[{"delta":{"content":"Result"}}]}',
            b"data: [DONE]",
        ]

        with patch("aixterm.llm.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.iter_lines.return_value = mock_lines
            mock_post.return_value = mock_response

            with patch("builtins.print") as mock_print:
                response = llm_client.chat_completion(
                    [{"role": "user", "content": "Test"}]
                )

            # Should handle tool call and continue with content
            assert response == "Result"
            # Should print tool call notification
            mock_print.assert_any_call("[Tool Call: test_tool]")

    def test_ask_with_context(self, llm_client, mock_requests_post):
        """Test asking with context."""
        query = "How do I list files?"
        context = "Current directory: /home/user"

        with patch("builtins.print"):
            llm_client.ask_with_context(query, context)

        # Verify the request was made with proper message structure
        call_args = mock_requests_post.call_args
        payload = call_args[1]["json"]
        messages = payload["messages"]

        # Should have at least system and user messages, but may include
        # conversation history
        assert len(messages) >= 2
        assert messages[0]["role"] == "system"
        # The last message should be the user query with context
        assert messages[-1]["role"] == "user"
        assert query in messages[-1]["content"]
        assert context in messages[-1]["content"]

    def test_ask_with_context_and_tools(self, llm_client, mock_requests_post):
        """Test asking with context and tools."""
        query = "Test query"
        context = "Test context"
        tools = [{"type": "function", "function": {"name": "test_tool"}}]

        with patch("builtins.print"):
            llm_client.ask_with_context(query, context, tools)

        call_args = mock_requests_post.call_args
        payload = call_args[1]["json"]
        assert "tools" in payload
        assert payload["tools"] == tools

    def test_authorization_header(self, llm_client):
        """Test that authorization header is included when API key is set."""
        llm_client.config.set("api_key", "test-api-key")

        with patch("aixterm.llm.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.iter_lines.return_value = [b"data: [DONE]"]
            mock_post.return_value = mock_response

            with patch("builtins.print"):
                llm_client.chat_completion([{"role": "user", "content": "Test"}])

            headers = mock_post.call_args[1]["headers"]
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer test-api-key"

    def test_no_authorization_header_when_no_api_key(
        self, llm_client, mock_requests_post
    ):
        """Test that no authorization header is included when no API key is set."""
        # Ensure no API key is set
        llm_client.config.set("api_key", "")

        with patch("builtins.print"):
            llm_client.chat_completion([{"role": "user", "content": "Test"}])

        headers = mock_requests_post.call_args[1]["headers"]
        assert "Authorization" not in headers

    def test_timeout_configuration(self, llm_client, mock_requests_post):
        """Test that timeout is properly configured."""
        with patch("builtins.print"):
            llm_client.chat_completion([{"role": "user", "content": "Test"}])

        # Verify timeout was set
        call_args = mock_requests_post.call_args
        assert call_args[1]["timeout"] == 30

    def test_role_alternation_validation(self, llm_client):
        """Test that role alternation validation works correctly."""
        # Test case that simulates conversation history parsing issues
        problematic_messages = [
            {"role": "system", "content": "You are a terminal AI assistant."},
            {"role": "user", "content": "List files"},
            {"role": "assistant", "content": "I'll list the files for you."},
            {"role": "user", "content": "Show processes"},
            {
                "role": "user",
                "content": "What's running?",
            },  # Two consecutive user messages
            {"role": "assistant", "content": "Here are the processes:"},
            {
                "role": "assistant",
                "content": "Process 1: python",
            },  # Two consecutive assistant messages
            {"role": "user", "content": "Current query"},
        ]

        # This should fix the role alternation
        fixed_messages = llm_client._validate_and_fix_role_alternation(
            problematic_messages
        )

        # Verify the pattern is correct
        non_system_roles = [
            msg.get("role") for msg in fixed_messages if msg.get("role") != "system"
        ]
        for i, role in enumerate(non_system_roles):
            expected = "user" if i % 2 == 0 else "assistant"
            assert role == expected, f"Position {i} has {role}, expected {expected}"

        # Should have system message at the start
        assert fixed_messages[0]["role"] == "system"

        # Should start with user message after system
        assert fixed_messages[1]["role"] == "user"
