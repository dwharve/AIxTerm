"""Token management and estimation for context optimization."""

from typing import Any, Optional

import tiktoken


class TokenManager:
    """Handles token estimation and management for context optimization."""

    def __init__(self, config_manager: Any, logger: Any) -> None:
        """Initialize token manager.

        Args:
            config_manager: Configuration manager instance
            logger: Logger instance
        """
        self.config = config_manager
        self.logger = logger

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        model_name = self.config.get("model", "")

        # Get appropriate tokenizer
        if model_name and model_name.startswith(("gpt-", "text-")):
            try:
                encoder = tiktoken.encoding_for_model(model_name)
            except KeyError:
                encoder = tiktoken.get_encoding("cl100k_base")
        else:
            encoder = tiktoken.get_encoding("cl100k_base")

        return len(encoder.encode(text))

    def apply_token_limit(self, text: str, max_tokens: int, model_name: str) -> str:
        """Apply token limit to text content.

        Args:
            text: Text to limit
            max_tokens: Maximum tokens
            model_name: Model name for tokenization

        Returns:
            Token-limited text
        """
        if not text.strip():
            return text

        # Get appropriate encoder
        if model_name and model_name.startswith(("gpt-", "text-")):
            try:
                encoder = tiktoken.encoding_for_model(model_name)
            except KeyError:
                encoder = tiktoken.get_encoding("cl100k_base")
        else:
            encoder = tiktoken.get_encoding("cl100k_base")

        tokens = encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text

        # Truncate to token limit (keep the end for recency)
        truncated_tokens = tokens[-max_tokens:]
        return encoder.decode(truncated_tokens)

    def get_available_tool_tokens(self, context_tokens: int) -> int:
        """Calculate how many tokens are available for tool definitions.

        Args:
            context_tokens: Tokens already used by context

        Returns:
            Number of tokens available for tools
        """
        total_context = self.config.get_total_context_size()
        response_buffer = self.config.get_response_buffer_size()
        tool_reserve_value = self.config.get_tool_tokens_reserve()
        tool_reserve: int = int(tool_reserve_value)

        # Calculate available tokens: total - response_buffer - context_used
        available = total_context - response_buffer - context_tokens

        # Use configured tool reserve, but ensure we have at least some space for tools
        tool_budget: int = min(tool_reserve, max(500, available // 2))

        self.logger.debug(
            f"Tool token budget: {tool_budget} (total: {total_context}, "
            f"response: {response_buffer}, context: {context_tokens})"
        )

        return max(0, tool_budget)

    def count_tokens_for_messages(
        self, messages: list, model_name: Optional[str] = None
    ) -> int:
        """Count tokens for a list of messages including OpenAI format overhead.

        Args:
            messages: List of message dictionaries
            model_name: Model name for tokenizer (uses config default if None)

        Returns:
            Total token count including message formatting overhead
        """
        if not messages:
            return 0

        if model_name is None:
            model_name = self.config.get("model", "gpt-3.5-turbo")

        try:
            if model_name and model_name.startswith(("gpt-", "text-")):
                try:
                    encoding = tiktoken.encoding_for_model(model_name)
                except KeyError:
                    encoding = tiktoken.get_encoding("cl100k_base")
            else:
                encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fallback to simple estimation
            total_chars = sum(
                len(str(msg.get("content", ""))) + len(str(msg.get("role", "")))
                for msg in messages
            )
            return total_chars // 3

        total_tokens = 0

        for message in messages:
            # Each message has overhead tokens for role and message structure
            total_tokens += 4  # Base overhead per message

            for key, value in message.items():
                if isinstance(value, str):
                    total_tokens += len(encoding.encode(value))
                elif isinstance(value, list):
                    # Handle tool_calls or other list content
                    total_tokens += len(encoding.encode(str(value)))

        # Add overhead for conversation structure
        total_tokens += 2  # Conversation-level overhead

        return total_tokens

    def count_tokens_for_tools(
        self, tools: list, model_name: Optional[str] = None
    ) -> int:
        """Count tokens for tools definition including JSON overhead.

        Args:
            tools: List of tool definitions
            model_name: Model name for tokenizer (uses config default if None)

        Returns:
            Total token count for tools
        """
        if not tools:
            return 0

        if model_name is None:
            model_name = self.config.get("model", "gpt-3.5-turbo")

        try:
            import json

            tools_json = json.dumps(tools)
            return self.estimate_tokens(tools_json)
        except Exception as e:
            self.logger.warning(f"Tools token counting failed: {e}")
            # Fallback estimation
            return len(str(tools)) // 3

    def count_tokens_for_payload(
        self, payload: dict, model_name: Optional[str] = None
    ) -> int:
        """Count tokens for a complete API payload including all fields.

        Args:
            payload: Complete API payload dictionary
            model_name: Model name for tokenizer (uses config default if None)

        Returns:
            Total token count for the payload
        """
        if model_name is None:
            model_name = self.config.get("model", "gpt-3.5-turbo")

        try:
            import json

            payload_json = json.dumps(payload)
            return self.estimate_tokens(payload_json)
        except Exception as e:
            self.logger.warning(f"Payload token counting failed: {e}")
            # Fallback: sum individual components
            total = 0

            # Count messages
            if "messages" in payload:
                total += self.count_tokens_for_messages(payload["messages"], model_name)

            # Count tools
            if "tools" in payload:
                total += self.count_tokens_for_tools(payload["tools"], model_name)

            # Add overhead for other fields (model, stream, etc.)
            total += 50  # Conservative overhead estimate

            return total
