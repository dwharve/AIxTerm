"""LLM submodule for AIxTerm.

This submodule contains all LLM-related functionality including:
- LLM client for communicating with language models
- Tool execution and handling
- Context management and token counting
- Streaming response processing
- Message validation and role alternation
"""

from .client import LLMClient
from .exceptions import LLMError

__all__ = ["LLMClient", "LLMError"]
