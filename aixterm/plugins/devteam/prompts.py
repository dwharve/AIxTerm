"""
DevTeam Plugin Prompt Optimization

This module provides prompt optimization functionality for the DevTeam plugin.
It helps optimize prompts for different LLM providers and contexts.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PromptTemplate:
    """
    A template for a prompt that can be formatted with parameters.
    """

    def __init__(
        self,
        template: str,
        template_vars: Optional[List[str]] = None,
        name: str = "default",
    ):
        """
        Initialize a prompt template.

        Args:
            template: The template string.
            template_vars: The template variables.
            name: The name of the template.
        """
        self.template = template
        self.name = name

        # Extract template variables from the template if not provided
        if template_vars is None:
            # Find all {variable} patterns
            pattern = r"\{([^{}]+)\}"
            self.template_vars = re.findall(pattern, template)
        else:
            self.template_vars = template_vars

    def format(self, **kwargs) -> str:
        """
        Format the template with the given variables.

        Args:
            **kwargs: The variables to format the template with.

        Returns:
            The formatted prompt.
        """
        # Check that all required variables are provided
        missing_vars = [var for var in self.template_vars if var not in kwargs]
        if missing_vars:
            raise ValueError(f"Missing template variables: {', '.join(missing_vars)}")

        # Format the template with the variables
        return self.template.format(**kwargs)

    def __str__(self) -> str:
        """
        Return the template string.
        """
        return self.template


class PromptOptimizer:
    """
    A class for optimizing prompts for different LLM providers and contexts.
    """

    def __init__(self):
        """
        Initialize a prompt optimizer.
        """
        self.templates: Dict[str, PromptTemplate] = {}

    def add_template(self, template: PromptTemplate) -> None:
        """
        Add a template to the optimizer.

        Args:
            template: The prompt template to add.
        """
        self.templates[template.name] = template
        logger.debug(f"Added template '{template.name}'")

    def get_template(self, name: str) -> PromptTemplate:
        """
        Get a template by name.

        Args:
            name: The name of the template.

        Returns:
            The prompt template.
        """
        if name not in self.templates:
            raise ValueError(f"Template '{name}' not found")

        return self.templates[name]

    def optimize(
        self,
        prompt: str,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Optimize a prompt for a specific model and parameters.

        Args:
            prompt: The prompt to optimize.
            model: The LLM model to optimize for.
            temperature: The temperature parameter.
            max_tokens: The maximum number of tokens.

        Returns:
            A dictionary with the optimized prompt parameters.
        """
        # In a real implementation, this would use more sophisticated logic
        # to optimize the prompt for the given model. For now, we'll just
        # return a dictionary with the prompt and parameters.

        result = {"prompt": prompt, "model": model, "temperature": temperature}

        if max_tokens is not None:
            result["max_tokens"] = max_tokens

        return result


# Default prompt templates for agents
DEFAULT_TEMPLATES = {
    "project_manager": PromptTemplate(
        name="project_manager",
        template="""
You are a Project Manager AI agent that helps manage software development projects.
Your goal is to break down complex tasks into smaller, manageable subtasks and
coordinate the work of other agents.

Project Context:
{project_context}

Task:
{task_description}

Available Resources:
{available_resources}

Please create a plan to accomplish this task, breaking it down into subtasks.
For each subtask, specify:
1. The objective
2. Priority level (High, Medium, Low)
3. Dependencies (if any)
4. Estimated effort
5. Required skills or knowledge

Be concise, practical, and focused on delivering value.
""",
    ),
    "code_analyst": PromptTemplate(
        name="code_analyst",
        template="""
You are a Code Analyst AI agent specialized in understanding and analyzing codebases.
Your goal is to analyze code, identify patterns, and provide insights that can help
improve code quality and maintainability.

Code Context:
{code_context}

Analysis Request:
{analysis_request}

Available Tools:
{available_tools}

Please provide your analysis based on the given context and request.
Include:
1. Key observations
2. Identified patterns or anti-patterns
3. Suggestions for improvement
4. Any potential issues or risks

Focus on being insightful, practical, and actionable in your analysis.
""",
    ),
    "developer": PromptTemplate(
        name="developer",
        template="""
You are a Developer AI agent specialized in writing high-quality code.
Your goal is to implement features, fix bugs, and improve existing code.

Task:
{task_description}

Code Context:
{code_context}

Requirements:
{requirements}

Available Tools:
{available_tools}

Please implement a solution that addresses the task.
Your solution should be:
1. Correct - it should fully address the requirements
2. Efficient - it should use appropriate algorithms and data structures
3. Readable - it should follow best practices for code style and documentation
4. Maintainable - it should be easy to modify and extend
5. Tested - it should include tests to verify correctness

Provide your solution along with an explanation of your approach and any trade-offs you made.
""",
    ),
    "qa_tester": PromptTemplate(
        name="qa_tester",
        template="""
You are a QA Tester AI agent specialized in testing software applications.
Your goal is to identify bugs, edge cases, and potential issues in code.

Test Target:
{test_target}

Requirements:
{requirements}

Available Tools:
{available_tools}

Please design and execute tests for the given target.
Your test approach should include:
1. Test cases covering main functionality
2. Edge case testing
3. Error handling verification
4. Performance considerations (if relevant)

For each issue found, provide:
1. A clear description
2. Steps to reproduce
3. Expected vs actual behavior
4. Severity level

Focus on being thorough, methodical, and detail-oriented in your testing.
""",
    ),
}


def create_default_optimizer() -> PromptOptimizer:
    """
    Create a prompt optimizer with default templates.

    Returns:
        A prompt optimizer with default templates.
    """
    optimizer = PromptOptimizer()

    # Add default templates
    for template in DEFAULT_TEMPLATES.values():
        optimizer.add_template(template)

    return optimizer
