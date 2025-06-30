"""
AIxTerm - Terminal AI Assistant with MCP Support

A command-line AI assistant that provides intelligent shell command suggestions
based on your terminal context, with support for Model Context Protocol
(MCP) servers.
"""

__version__ = "0.1.3"
__author__ = "AIxTerm Team"

from .cleanup import CleanupManager
from .config import AIxTermConfig
from .context import TerminalContext
from .llm import LLMClient
from .mcp_client import MCPClient

__all__ = [
    "__main__",
    "AIxTermConfig",
    "TerminalContext",
    "LLMClient",
    "MCPClient",
    "CleanupManager",
]
