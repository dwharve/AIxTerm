"""Message validation and role alternation utilities."""

from typing import Any, Dict, List


class MessageValidator:
    """Handles message validation and role alternation for LLM requests."""

    def __init__(self, config_manager: Any, logger: Any):
        """Initialize message validator.

        Args:
            config_manager: Configuration manager instance
            logger: Logger instance
        """
        self.config = config_manager
        self.logger = logger

    def validate_and_fix_role_alternation(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Validate and fix message role alternation for API compatibility.

        OpenAI API requires proper message flow:
        - [system] (optional)
        - user, assistant (with optional tool_calls), tool (responses to tool_calls),
          assistant, ...
        - Tool messages must immediately follow assistant messages with tool_calls

        Args:
            messages: List of message dictionaries

        Returns:
            Fixed list of messages with proper role alternation
        """
        if not messages:
            return messages

        # Check for tool calls - if there are tool calls, preserve all messages
        has_tool_calls = any(
            msg.get("tool_calls") or msg.get("role") == "tool" for msg in messages
        )

        if has_tool_calls:
            # For tool-based conversations, preserve all messages
            fixed_messages = []

            # Handle system message separately
            if messages and messages[0].get("role") == "system":
                fixed_messages.append(messages[0])
                remaining_messages = messages[1:]
            else:
                remaining_messages = messages

            # Process messages while preserving tool calls and tool responses
            i = 0
            while i < len(remaining_messages):
                message = remaining_messages[i]
                role = message.get("role", "")

                if role in ["user", "assistant", "tool"]:
                    # All these roles are valid in OpenAI API
                    fixed_messages.append(message)

                    # If this is an assistant message with tool calls,
                    # make sure any following tool messages are preserved
                    if role == "assistant" and message.get("tool_calls"):
                        # Look ahead for tool response messages
                        j = i + 1
                        while (
                            j < len(remaining_messages)
                            and remaining_messages[j].get("role") == "tool"
                        ):
                            fixed_messages.append(remaining_messages[j])
                            j += 1
                        i = j - 1  # Skip the tool messages we just added

                i += 1

            return fixed_messages

        # For simple conversations without tool calls, ensure proper alternation
        # but preserve the structure if it's already reasonable
        fixed_messages = []

        # Handle system message separately
        if messages and messages[0].get("role") == "system":
            fixed_messages.append(messages[0])
            remaining_messages = messages[1:]
        else:
            remaining_messages = messages

        if not remaining_messages:
            return fixed_messages

        # Check if the sequence is already properly alternating
        non_system_roles = [msg.get("role") for msg in remaining_messages]
        is_properly_alternating = True

        for i, role in enumerate(non_system_roles):
            if role not in ["user", "assistant"]:
                continue
            expected = "user" if i % 2 == 0 else "assistant"
            if role != expected:
                is_properly_alternating = False
                break

        if is_properly_alternating:
            # Already properly alternating, keep as-is
            fixed_messages.extend(remaining_messages)
        else:
            # Apply strict alternation fix, but preserve the last message if it's
            # a user message (which is likely the current query)
            last_message = remaining_messages[-1] if remaining_messages else None

            if last_message and last_message.get("role") == "user":
                # Process all but the last message with strict alternation
                history_to_fix = remaining_messages[:-1]
                current_query = last_message

                # Fix the history part
                fixed_history = self.fix_conversation_history_roles(history_to_fix)
                fixed_messages.extend(fixed_history)

                # Always add the current user query at the end
                fixed_messages.append(current_query)
            else:
                # No special last user message to preserve, apply full fix
                fixed_history = self.fix_conversation_history_roles(remaining_messages)
                fixed_messages.extend(fixed_history)

        # Final validation: ensure we have a reasonable conversation flow
        roles = [msg.get("role") for msg in fixed_messages]
        self.logger.debug(f"Role validation result: {roles}")

        return fixed_messages

    def fix_conversation_history_roles(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fix conversation history to ensure proper role alternation.

        This ensures that conversation history follows the pattern:
        user, assistant, user, assistant, ...
        and filters out incomplete pairs.

        Args:
            messages: List of conversation history messages

        Returns:
            Fixed list of messages with proper role alternation
        """
        if not messages:
            return messages

        fixed_messages = []

        # Group messages into user-assistant pairs
        i = 0
        while i < len(messages):
            message = messages[i]
            role = message.get("role", "")

            if role == "user":
                # Look for the following assistant message
                user_msg = message
                assistant_msg = None

                # Check if there's an assistant response
                if i + 1 < len(messages) and messages[i + 1].get("role") == "assistant":
                    assistant_msg = messages[i + 1]
                    i += 2  # Skip both messages
                else:
                    # Skip incomplete user message without assistant response
                    i += 1
                    continue

                # Add the complete pair
                fixed_messages.append(user_msg)
                fixed_messages.append(assistant_msg)

            elif role == "assistant":
                # Skip assistant messages that don't follow user messages
                # (these are incomplete pairs)
                i += 1
                continue
            else:
                # Skip other roles (system, tool, etc.)
                i += 1
                continue

        self.logger.debug(
            f"Fixed conversation history: {len(messages)} -> "
            f"{len(fixed_messages)} messages"
        )
        roles = [msg.get("role") for msg in fixed_messages]
        self.logger.debug(f"Fixed conversation history roles: {roles}")

        return fixed_messages

    def trim_messages_to_fit(
        self, messages: List[Dict[str, Any]], max_tokens: int, model: str
    ) -> List[Dict[str, Any]]:
        """Trim messages to fit within a token limit.

        Args:
            messages: List of message dictionaries
            max_tokens: Maximum allowed tokens for messages
            model: Model name for tokenizer

        Returns:
            Trimmed messages that fit within token limits
        """
        if not messages:
            return messages

        # Import here to avoid circular imports
        from ..context import TokenManager

        context_manager = TokenManager(self.config, self.logger)

        # Calculate total tokens in current conversation using proper token counting
        total_tokens = context_manager.count_tokens_for_messages(messages, model)

        # If we're within limits, return as-is
        if total_tokens <= max_tokens:
            return messages

        self.logger.warning(
            f"Messages too large ({total_tokens} tokens), trimming to {max_tokens}"
        )

        # Need to trim - keep system message and recent important messages
        # Work backwards from most recent messages
        trimmed_messages = []
        remaining_budget = max_tokens

        # Always keep system message (first message)
        if messages and messages[0].get("role") == "system":
            system_msg = messages[0]
            system_tokens = context_manager.count_tokens_for_messages(
                [system_msg], model
            )
            if system_tokens <= remaining_budget:
                trimmed_messages.append(system_msg)
                remaining_budget -= system_tokens
            remaining_messages = messages[1:]
        else:
            remaining_messages = messages

        # Prioritize recent messages, especially user messages and tool results
        for message in reversed(remaining_messages):
            message_tokens = context_manager.count_tokens_for_messages([message], model)
            role = message.get("role", "")

            # Always try to keep recent user messages and tool results
            if role in ["user", "tool"] or message_tokens <= remaining_budget:
                if message_tokens <= remaining_budget:
                    trimmed_messages.insert(
                        (-1 if len(trimmed_messages) > 1 else len(trimmed_messages)),
                        message,
                    )
                    remaining_budget -= message_tokens
                else:
                    # Try to fit a truncated version for important messages
                    if (
                        role in ["user", "tool"] and remaining_budget > 100
                    ):  # Need reasonable space
                        content = str(message.get("content", ""))
                        # Truncate to fit remaining budget (rough estimation)
                        max_chars = remaining_budget * 3  # Conservative estimate
                        if len(content) > max_chars:
                            truncated_content = (
                                content[:max_chars]
                                + "... [truncated for context limit]"
                            )
                            truncated_message = message.copy()
                            truncated_message["content"] = truncated_content
                            truncated_tokens = (
                                context_manager.count_tokens_for_messages(
                                    [truncated_message], model
                                )
                            )
                            if truncated_tokens <= remaining_budget:
                                trimmed_messages.insert(
                                    (
                                        -1
                                        if len(trimmed_messages) > 1
                                        else len(trimmed_messages)
                                    ),
                                    truncated_message,
                                )
                                remaining_budget -= truncated_tokens
                    break

        final_tokens = context_manager.count_tokens_for_messages(
            trimmed_messages, model
        )
        self.logger.info(
            f"Messages trimmed from {total_tokens} to {final_tokens} tokens"
        )
        return trimmed_messages
