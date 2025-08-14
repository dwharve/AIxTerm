"""
Agent management module for the DevTeam plugin.

This module provides functionality for agent management and registry.
"""

import logging

logger = logging.getLogger(__name__)


def create_default_registry(plugin):
    """
    Create a default agent registry.

    Args:
        plugin: The DevTeam plugin instance

    Returns:
        An agent registry instance
    """
    from ..agents import AgentRegistry

    return AgentRegistry(plugin)
