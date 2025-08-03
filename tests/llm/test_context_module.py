"""Tests for the LLM client module context handler."""

import unittest
from unittest.mock import MagicMock, patch

from aixterm.llm.client.context import ContextHandler


class TestContextHandler(unittest.TestCase):
    """Test cases for the Context Handler module."""

    def setUp(self):
        """Set up test fixtures."""
        self.logger = MagicMock()
        self.config_manager = MagicMock()
        self.token_manager = MagicMock()
        self.message_validator = MagicMock()

        # Create the context handler
        self.context_handler = ContextHandler(
            self.logger, self.config_manager, self.token_manager, self.message_validator
        )

    def test_prepare_conversation_with_context(self):
        """Test preparing a conversation with context."""
        # Arrange
        query = "Test query"
        context = "Test context"
        self.config_manager.get.side_effect = lambda key, default=None: {
            "system_prompt": "You are a test assistant.",
            "model": "test-model",
        }.get(key, default)

        self.token_manager.estimate_tokens.side_effect = lambda text: len(text) // 4
        self.token_manager.count_tokens_for_tools.return_value = 50
        self.config_manager.get_available_context_size.return_value = 1000

        # Mock the conversation history
        with patch("aixterm.context.TerminalContext") as mock_terminal_context:
            mock_terminal_context_instance = mock_terminal_context.return_value
            mock_terminal_context_instance.get_conversation_history.return_value = [
                {"role": "user", "content": "Previous query"},
                {"role": "assistant", "content": "Previous response"},
            ]

            # Mock the message validator
            self.message_validator.fix_conversation_history_roles.return_value = [
                {"role": "user", "content": "Previous query"},
                {"role": "assistant", "content": "Previous response"},
            ]

            # Act
            messages = self.context_handler.prepare_conversation_with_context(
                query, context
            )

            # Assert
            self.assertEqual(len(messages), 4)
            self.assertEqual(messages[0]["role"], "system")
            self.assertEqual(messages[0]["content"], "You are a test assistant.")
            self.assertEqual(messages[1]["role"], "user")
            self.assertEqual(messages[1]["content"], "Previous query")
            self.assertEqual(messages[2]["role"], "assistant")
            self.assertEqual(messages[2]["content"], "Previous response")
            self.assertEqual(messages[3]["role"], "user")
            self.assertEqual(
                messages[3]["content"], f"{query}\n\nContext:\n{context}\n----"
            )

    def test_enhance_system_prompt_with_tool_info(self):
        """Test enhancing the system prompt with tool information."""
        # Arrange
        base_prompt = "You are a test assistant."
        tools = [
            {
                "function": {
                    "name": "execute_command",
                    "description": "Execute a shell command",
                    "category": "system",
                    "tags": ["execute", "command", "shell"],
                }
            },
            {
                "function": {
                    "name": "read_file",
                    "description": "Read a file from the filesystem",
                    "category": "filesystem",
                    "tags": ["file", "read"],
                }
            },
        ]

        # Act
        enhanced_prompt = self.context_handler._enhance_system_prompt_with_tool_info(
            base_prompt, tools
        )

        # Assert
        self.assertIn("You are a test assistant.", enhanced_prompt)
        self.assertIn("Available tool capabilities:", enhanced_prompt)
        self.assertIn("Categories:", enhanced_prompt)
        self.assertIn("system", enhanced_prompt)
        self.assertIn("filesystem", enhanced_prompt)
        self.assertIn("Common operations:", enhanced_prompt)
        self.assertIn("execute", enhanced_prompt)
        self.assertIn("command", enhanced_prompt)
        self.assertIn("file", enhanced_prompt)
        self.assertIn("read", enhanced_prompt)


if __name__ == "__main__":
    unittest.main()
