"""Token counting and text truncation utilities."""

from typing import List, Optional

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


def tokenize_text(text: str, model_name: Optional[str] = None) -> List[int]:
    """Tokenize text using the appropriate tokenizer for the model.

    Args:
        text: The text to tokenize
        model_name: Model name for tokenization (e.g., 'gpt-4')

    Returns:
        List of token IDs
    """
    if model_name and model_name.startswith(("gpt-", "text-")):
        try:
            encoder = tiktoken.encoding_for_model(model_name)
        except KeyError:
            encoder = tiktoken.get_encoding("cl100k_base")
    else:
        encoder = tiktoken.get_encoding("cl100k_base")

    return encoder.encode(text)


def truncate_text_to_tokens(
    text: str, max_tokens: Optional[int], model_name: Optional[str] = None
) -> str:
    """Truncate text to specified token limit.

    Args:
        text: Text to truncate
        max_tokens: Maximum number of tokens, if None will return original text
        model_name: Model name for tokenization (e.g., 'gpt-4')

    Returns:
        Truncated text
    """
    if max_tokens is None:
        return text

    # Use proper tokenization
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


def read_and_truncate_log(
    log_path, max_tokens: Optional[int] = None, model_name: Optional[str] = None
) -> str:
    """Read log file and truncate to token limit with proper tokenization.

    Args:
        log_path: Path to log file
        max_tokens: Maximum number of tokens to include, if None will return full content
        model_name: Name of the model for tokenization

    Returns:
        Truncated log content
    """
    try:
        with open(log_path, "r", errors="ignore", encoding="utf-8") as f:
            full_text = f.read().strip()

        if not full_text:
            return ""

        if max_tokens is None:
            return full_text

        return truncate_text_to_tokens(full_text, max_tokens, model_name)

    except Exception as e:
        return f"Error reading log file: {e}"
