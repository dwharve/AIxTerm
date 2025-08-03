"""
Workflow templates module for the DevTeam plugin.

This module provides workflow template creation functionality.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


def create_feature_workflow_template():
    """
    Create a feature development workflow template.

    Returns:
        A workflow template for feature development
    """
    import uuid

    from ..workflow import WorkflowTemplate

    # Create step templates
    step_templates = [
        {
            "id": "requirements",
            "name": "Requirements Analysis",
            "agent_type": "project_manager",
            "depends_on": [],
        },
        {
            "id": "design",
            "name": "Design",
            "agent_type": "architect",
            "depends_on": ["requirements"],
        },
        {
            "id": "implementation",
            "name": "Implementation",
            "agent_type": "developer",
            "depends_on": ["design"],
        },
        {
            "id": "testing",
            "name": "Testing",
            "agent_type": "qa",
            "depends_on": ["implementation"],
        },
        {
            "id": "review",
            "name": "Code Review",
            "agent_type": "reviewer",
            "depends_on": ["implementation"],
        },
        {
            "id": "documentation",
            "name": "Documentation",
            "agent_type": "documentation",
            "depends_on": ["implementation"],
        },
        {
            "id": "final_approval",
            "name": "Final Approval",
            "agent_type": "project_manager",
            "depends_on": ["testing", "review", "documentation"],
        },
    ]

    # Create a new workflow template
    template = WorkflowTemplate(
        template_id=f"feature_{uuid.uuid4().hex[:8]}",
        name="Feature Development",
        description="A workflow for developing new features",
        step_templates=step_templates,
    )

    return template
