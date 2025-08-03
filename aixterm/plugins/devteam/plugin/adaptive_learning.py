"""
Adaptive learning module for the DevTeam plugin.

This module provides functionality for adaptive learning and prompt optimization.
"""

import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


def create_adaptive_learning_system(prompt_optimizer):
    """
    Create an adaptive learning system.

    Args:
        prompt_optimizer: The prompt optimizer to use

    Returns:
        An adaptive learning system instance
    """
    from ..adaptive import AdaptiveLearningSystem

    return AdaptiveLearningSystem(prompt_optimizer)
