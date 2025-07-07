"""Tests for LLM client functionality."""

from unittest.mock import Mock, patch

import pytest

from aixterm.llm import LLMError


class TestLLMClient:
    """Test cases for LLMClient class."""

    def test_chat_completion_streaming(self, llm_client):
        """Test streaming chat completion."""
        messages = [
            {"role": "system", "content": "You are a test assistant."},
            {"role": "user", "content": "Hello"},
        ]

        # Mock the OpenAI client's chat.completions.create method for streaming
        mock_chunk1 = Mock()
        mock_chunk1.choices = [Mock()]
        mock_chunk1.choices[0].delta = Mock()
        mock_chunk1.choices[0].delta.content = "Here's how to "
        mock_chunk1.choices[0].delta.tool_calls = None

        mock_chunk2 = Mock()
        mock_chunk2.choices = [Mock()]
        mock_chunk2.choices[0].delta = Mock()
        mock_chunk2.choices[0].delta.content = "list processes: ps aux"
        mock_chunk2.choices[0].delta.tool_calls = None

        mock_chunks = [mock_chunk1, mock_chunk2]

        with patch.object(
            llm_client.openai_client.chat.completions, "create"
        ) as mock_create:
            mock_create.return_value = iter(mock_chunks)

            with patch("builtins.print"):  # Suppress print output during tests
                response = llm_client.chat_completion(messages, stream=True)

        assert "Here's how to list processes: ps aux" == response
        mock_create.assert_called_once()

    def test_chat_completion_non_streaming(self, llm_client):
        """Test non-streaming chat completion."""
        messages = [
            {"role": "system", "content": "You are a test assistant."},
            {"role": "user", "content": "Hello"},
        ]

        # Mock the OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Hello! How can I help you?"

        with patch.object(
            llm_client.openai_client.chat.completions, "create"
        ) as mock_create:
            mock_create.return_value = mock_response

            response = llm_client.chat_completion(messages, stream=False)

            assert response == "Hello! How can I help you?"
            mock_create.assert_called_once()

    def test_chat_completion_with_tools(self, llm_client):
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

        # Mock OpenAI response with tool calls
        mock_chunk = Mock()
        mock_chunk.choices = [Mock()]
        mock_chunk.choices[0].delta = Mock()
        mock_chunk.choices[0].delta.content = "I'll use the test tool."
        mock_chunk.choices[0].delta.tool_calls = None

        with patch.object(
            llm_client.openai_client.chat.completions, "create"
        ) as mock_create:
            mock_create.return_value = iter([mock_chunk])

            with patch("builtins.print"):
                llm_client.chat_completion(messages, stream=True, tools=tools)

            # Verify tools were included in the call
            call_args = mock_create.call_args
            assert call_args[1]["tools"] == tools
            assert call_args[1]["tool_choice"] == "auto"

    def test_request_error_handling(self, llm_client):
        """Test handling of request errors."""
        messages = [{"role": "user", "content": "Test"}]

        with patch.object(
            llm_client.openai_client.chat.completions, "create"
        ) as mock_create:
            mock_create.side_effect = Exception("Network error")

            with pytest.raises(LLMError, match="Error communicating with LLM"):
                llm_client.chat_completion(messages)

    def test_http_error_handling(self, llm_client):
        """Test handling of HTTP errors."""
        messages = [{"role": "user", "content": "Test"}]

        with patch.object(
            llm_client.openai_client.chat.completions, "create"
        ) as mock_create:
            mock_create.side_effect = Exception("HTTP 500")

            with pytest.raises(LLMError, match="Error communicating with LLM"):
                llm_client.chat_completion(messages)

    def test_streaming_response_parsing(self, llm_client):
        """Test parsing of streaming response data."""
        # Mock streaming chunks
        mock_chunk1 = Mock()
        mock_chunk1.choices = [Mock()]
        mock_chunk1.choices[0].delta = Mock()
        mock_chunk1.choices[0].delta.content = "Hello"
        mock_chunk1.choices[0].delta.tool_calls = None

        mock_chunk2 = Mock()
        mock_chunk2.choices = [Mock()]
        mock_chunk2.choices[0].delta = Mock()
        mock_chunk2.choices[0].delta.content = " world"
        mock_chunk2.choices[0].delta.tool_calls = None

        mock_chunk3 = Mock()
        mock_chunk3.choices = [Mock()]
        mock_chunk3.choices[0].delta = Mock()
        mock_chunk3.choices[0].delta.content = "!"
        mock_chunk3.choices[0].delta.tool_calls = None

        mock_chunks = [mock_chunk1, mock_chunk2, mock_chunk3]

        with patch.object(
            llm_client.openai_client.chat.completions, "create"
        ) as mock_create:
            mock_create.return_value = iter(mock_chunks)

            with patch("builtins.print"):
                response = llm_client.chat_completion(
                    [{"role": "user", "content": "Test"}]
                )

            assert response == "Hello world!"

    def test_streaming_response_with_malformed_json(self, llm_client):
        """Test handling of malformed JSON in streaming response."""
        # With OpenAI client, malformed JSON handling is internal to the client
        # We test that the client continues to work even if some chunks are problematic
        mock_chunk1 = Mock()
        mock_chunk1.choices = [Mock()]
        mock_chunk1.choices[0].delta = Mock()
        mock_chunk1.choices[0].delta.content = "Hello"
        mock_chunk1.choices[0].delta.tool_calls = None

        # Simulate a chunk with no content (like malformed JSON would be skipped)
        mock_chunk2 = Mock()
        mock_chunk2.choices = [Mock()]
        mock_chunk2.choices[0].delta = Mock()
        mock_chunk2.choices[0].delta.content = None
        mock_chunk2.choices[0].delta.tool_calls = None

        mock_chunk3 = Mock()
        mock_chunk3.choices = [Mock()]
        mock_chunk3.choices[0].delta = Mock()
        mock_chunk3.choices[0].delta.content = " world"
        mock_chunk3.choices[0].delta.tool_calls = None

        mock_chunks = [mock_chunk1, mock_chunk2, mock_chunk3]

        with patch.object(
            llm_client.openai_client.chat.completions, "create"
        ) as mock_create:
            mock_create.return_value = iter(mock_chunks)

            with patch("builtins.print"):
                response = llm_client.chat_completion(
                    [{"role": "user", "content": "Test"}]
                )

            # Should skip None content and continue
            assert response == "Hello world"

    def test_tool_call_handling(self, llm_client):
        """Test handling of tool calls in streaming response."""
        # Mock tool call chunk
        mock_tool_call = Mock()
        mock_tool_call.id = "call_123"
        mock_tool_call.type = "function"
        mock_tool_call.function = Mock()
        mock_tool_call.function.name = "test_tool"
        mock_tool_call.function.arguments = "{}"

        mock_chunk1 = Mock()
        mock_chunk1.choices = [Mock()]
        mock_chunk1.choices[0].delta = Mock()
        mock_chunk1.choices[0].delta.content = None
        mock_chunk1.choices[0].delta.tool_calls = [Mock()]
        mock_chunk1.choices[0].delta.tool_calls[0].index = 0
        mock_chunk1.choices[0].delta.tool_calls[0].id = "call_123"
        mock_chunk1.choices[0].delta.tool_calls[0].type = "function"
        mock_chunk1.choices[0].delta.tool_calls[0].function = Mock()
        mock_chunk1.choices[0].delta.tool_calls[0].function.name = "test_tool"
        mock_chunk1.choices[0].delta.tool_calls[0].function.arguments = "{}"

        mock_chunk2 = Mock()
        mock_chunk2.choices = [Mock()]
        mock_chunk2.choices[0].delta = Mock()
        mock_chunk2.choices[0].delta.content = "Result"
        mock_chunk2.choices[0].delta.tool_calls = None

        mock_chunks = [mock_chunk1, mock_chunk2]

        with patch.object(
            llm_client.openai_client.chat.completions, "create"
        ) as mock_create:
            mock_create.return_value = iter(mock_chunks)

            with patch("builtins.print"):
                response = llm_client._handle_streaming_with_tools(
                    [{"role": "user", "content": "Test"}]
                )

            # Should handle tool call and return both content and tool calls
            assert response[0] == "Result"  # content
            assert response[1] is not None  # tool_calls
            assert len(response[1]) == 1
            assert response[1][0]["function"]["name"] == "test_tool"

    def test_ask_with_context(self, llm_client):
        """Test asking with context."""
        query = "How do I list files?"
        context = "Current directory: /home/user"

        # Mock OpenAI response
        mock_chunk = Mock()
        mock_chunk.choices = [Mock()]
        mock_chunk.choices[0].delta = Mock()
        mock_chunk.choices[0].delta.content = "Use 'ls' command"
        mock_chunk.choices[0].delta.tool_calls = None

        with patch.object(
            llm_client.openai_client.chat.completions, "create"
        ) as mock_create:
            mock_create.return_value = iter([mock_chunk])

            with patch("builtins.print"):
                llm_client.ask_with_context(query, context)

            # Verify the request was made with proper message structure
            call_args = mock_create.call_args
            kwargs = call_args[1]
            messages = kwargs["messages"]

            # Should have at least system and user messages, but may include
            # conversation history
            assert len(messages) >= 2
            assert messages[0]["role"] == "system"
            # The last message should be the user query with context
            assert messages[-1]["role"] == "user"
            assert query in messages[-1]["content"]
            assert context in messages[-1]["content"]

    def test_ask_with_context_and_tools(self, llm_client):
        """Test asking with context and tools."""
        query = "Test query"
        context = "Test context"
        tools = [{"type": "function", "function": {"name": "test_tool"}}]

        # Mock OpenAI response
        mock_chunk = Mock()
        mock_chunk.choices = [Mock()]
        mock_chunk.choices[0].delta = Mock()
        mock_chunk.choices[0].delta.content = "I'll use the tool"
        mock_chunk.choices[0].delta.tool_calls = None

        # Temporarily disable MCP client to test basic tool handling
        original_mcp_client = llm_client.mcp_client
        llm_client.mcp_client = None

        try:
            with patch.object(
                llm_client.openai_client.chat.completions, "create"
            ) as mock_create:
                mock_create.return_value = iter([mock_chunk])

                with patch("builtins.print"):
                    llm_client.ask_with_context(query, context, tools)

                call_args = mock_create.call_args
                kwargs = call_args[1]
                assert "tools" in kwargs
                assert kwargs["tools"] == tools
        finally:
            # Restore the original MCP client
            llm_client.mcp_client = original_mcp_client

    def test_authorization_header(self, llm_client):
        """Test that authorization header is included when API key is set."""
        # The OpenAI client handles authorization internally
        # We test that the client is initialized with the correct API key
        llm_client.config.set("api_key", "test-api-key")

        # Reinitialize client with new API key
        from aixterm.llm.client import LLMClient

        new_client = LLMClient(
            llm_client.config,
            llm_client.mcp_client,
            llm_client.progress_callback_factory,
            llm_client.display_manager,
        )

        # Verify the OpenAI client was initialized with the API key
        assert new_client.openai_client.api_key == "test-api-key"

    def test_no_authorization_header_when_no_api_key(self, llm_client):
        """Test that dummy key is used when no API key is set."""
        # Ensure no API key is set
        llm_client.config.set("api_key", "")

        # Reinitialize client with no API key
        from aixterm.llm.client import LLMClient

        new_client = LLMClient(
            llm_client.config,
            llm_client.mcp_client,
            llm_client.progress_callback_factory,
            llm_client.display_manager,
        )

        # Should use dummy key for local APIs
        assert new_client.openai_client.api_key == "dummy-key"

    def test_timeout_configuration(self, llm_client):
        """Test that base URL is properly configured."""
        # Test that the OpenAI client uses the configured base URL
        configured_url = llm_client.config.get("api_url", "http://localhost/v1")

        # The client should convert full endpoint URLs to base URLs
        if configured_url.endswith("/chat/completions"):
            expected_url = configured_url.replace("/chat/completions", "")
        else:
            expected_url = configured_url

        # Convert to string and normalize trailing slash
        actual_url = str(llm_client.openai_client.base_url).rstrip("/")
        expected_url = expected_url.rstrip("/")
        assert actual_url == expected_url

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

    def test_thinking_content_filtering(self, llm_client):
        """Test that thinking content is filtered out from responses."""
        from unittest.mock import Mock, patch

        # Mock OpenAI response with thinking content
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = (
            "Hello! <thinking>I need to think about this carefully. "
            "Let me consider the options...</thinking> Here's my response."
        )
        mock_response.choices = [mock_choice]

        messages = [
            {"role": "system", "content": "You are a test assistant."},
            {"role": "user", "content": "Test query"},
        ]

        with patch.object(
            llm_client.openai_client.chat.completions, "create"
        ) as mock_create:
            mock_create.return_value = mock_response

            response = llm_client.chat_completion(messages, stream=False)

        # Thinking content should be filtered out
        assert "<thinking>" not in response
        assert "</thinking>" not in response
        assert "Hello!" in response
        assert "Here's my response." in response
        assert "I need to think about this" not in response

    def test_streaming_thinking_content_filtering(self, llm_client):
        """Test that thinking content is filtered during streaming."""
        from unittest.mock import patch

        # Create mock streaming chunks with thinking content
        chunks = [
            self._create_chunk("Hello! <thinking>Let me think"),
            self._create_chunk(" about this problem carefully."),
            self._create_chunk("</thinking> Here is my"),
            self._create_chunk(" actual response."),
        ]

        messages = [
            {"role": "system", "content": "You are a test assistant."},
            {"role": "user", "content": "Test query"},
        ]

        with patch.object(
            llm_client.openai_client.chat.completions, "create"
        ) as mock_create:
            mock_create.return_value = iter(chunks)

            # Capture printed output
            import io
            from contextlib import redirect_stdout

            captured_output = io.StringIO()
            with redirect_stdout(captured_output):
                response = llm_client.chat_completion(messages, stream=True)

        # The response should be filtered
        assert "<thinking>" not in response
        assert "</thinking>" not in response
        assert "Hello!" in response
        assert "Here is my actual response." in response
        assert "Let me think about this" not in response

        # Check that thinking content wasn't printed to stdout
        printed_output = captured_output.getvalue()
        assert "Let me think about this" not in printed_output

    def _create_chunk(self, content):
        """Helper to create a mock streaming chunk."""
        from unittest.mock import MagicMock

        chunk = MagicMock()
        choice = MagicMock()
        delta = MagicMock()
        delta.content = content
        choice.delta = delta
        chunk.choices = [choice]
        return chunk
