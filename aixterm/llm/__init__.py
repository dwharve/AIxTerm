"""LLM submodule for AIxTerm.

This submodule contains all LLM-related functionality including:
- LLM client for communicating with language models
- Tool execution and handling
- Context management and token counting
- Streaming response processing
- Message validation and role alternation
"""

from .client import LLMClient
from .client.base import LLMClientBase
from .client.context import ContextHandler
from .client.progress import ProgressManager
from .client.requests import RequestHandler
from .client.streaming import StreamingHandler
from .client.thinking import ThinkingProcessor
from .client.tools import ToolCompletionHandler
from .exceptions import LLMError

__all__ = [
    "LLMClient",
    "LLMError",
    "LLMClientBase",
    "ContextHandler",
    "ProgressManager",
    "RequestHandler",
    "StreamingHandler",
    "ThinkingProcessor",
    "ToolCompletionHandler",
]
