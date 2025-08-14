"""
Adaptive Learning System for DevTeam Plugin

This module provides adaptive learning capabilities for prompt optimization.
It tracks performance of prompts and adapts them based on success metrics.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .prompts import PromptOptimizer, PromptTemplate

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """
    Performance metrics for prompt templates.

    Tracks various metrics like success rate, completion time,
    token usage, and user satisfaction ratings.
    """

    def __init__(self, template_name: str):
        """
        Initialize performance metrics for a template.

        Args:
            template_name: Name of the template being tracked.
        """
        self.template_name = template_name

        # Usage metrics
        self.total_usage = 0
        self.successful_usage = 0
        self.failed_usage = 0

        # Time metrics (ms)
        self.total_completion_time = 0
        self.min_completion_time = float("inf")
        self.max_completion_time = 0

        # Token usage
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # User feedback (1-5 scale)
        self.feedback_scores: List[int] = []

        # Timestamps
        self.first_used_at: Optional[str] = None
        self.last_used_at: Optional[str] = None

    def record_usage(
        self,
        success: bool,
        completion_time_ms: int,
        input_tokens: int,
        output_tokens: int,
        feedback_score: Optional[int] = None,
    ) -> None:
        """
        Record usage metrics for the template.

        Args:
            success: Whether the usage was successful.
            completion_time_ms: Time to completion in milliseconds.
            input_tokens: Number of input tokens used.
            output_tokens: Number of output tokens generated.
            feedback_score: Optional user feedback score (1-5).
        """
        # Update usage counts
        self.total_usage += 1
        if success:
            self.successful_usage += 1
        else:
            self.failed_usage += 1

        # Update time metrics
        self.total_completion_time += completion_time_ms
        self.min_completion_time = min(self.min_completion_time, completion_time_ms)
        self.max_completion_time = max(self.max_completion_time, completion_time_ms)

        # Update token usage
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        # Add feedback if provided
        if feedback_score is not None and 1 <= feedback_score <= 5:
            self.feedback_scores.append(feedback_score)

        # Update timestamps
        now = datetime.now().isoformat()
        if self.first_used_at is None:
            self.first_used_at = now
        self.last_used_at = now

    def get_success_rate(self) -> float:
        """
        Get the success rate for the template.

        Returns:
            Success rate as a percentage (0-100).
        """
        if self.total_usage == 0:
            return 0.0
        return (self.successful_usage / self.total_usage) * 100

    def get_average_completion_time(self) -> float:
        """
        Get the average completion time for the template.

        Returns:
            Average completion time in milliseconds.
        """
        if self.total_usage == 0:
            return 0.0
        return self.total_completion_time / self.total_usage

    def get_average_feedback_score(self) -> float:
        """
        Get the average user feedback score for the template.

        Returns:
            Average feedback score (1-5) or 0 if no feedback.
        """
        if not self.feedback_scores:
            return 0.0
        return sum(self.feedback_scores) / len(self.feedback_scores)

    def get_efficiency_score(self) -> float:
        """
        Get the efficiency score for the template.

        This is a combined metric that considers success rate,
        token usage, and completion time.

        Returns:
            Efficiency score (0-100).
        """
        if self.total_usage == 0:
            return 0.0

        # Calculate component metrics
        success_rate = self.get_success_rate()

        # Token efficiency (lower is better)
        avg_tokens = (
            self.total_input_tokens + self.total_output_tokens
        ) / self.total_usage
        token_efficiency = max(0, 100 - (avg_tokens / 10))  # Normalize

        # Time efficiency (lower is better)
        avg_time = self.get_average_completion_time()
        time_efficiency = max(0, 100 - (avg_time / 100))  # Normalize

        # Combine with weights
        return (success_rate * 0.6) + (token_efficiency * 0.2) + (time_efficiency * 0.2)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert metrics to dictionary for serialization.

        Returns:
            Dictionary representation of metrics.
        """
        return {
            "template_name": self.template_name,
            "usage": {
                "total": self.total_usage,
                "successful": self.successful_usage,
                "failed": self.failed_usage,
                "success_rate": self.get_success_rate(),
            },
            "time": {
                "average_ms": self.get_average_completion_time(),
                "min_ms": (
                    self.min_completion_time
                    if self.min_completion_time != float("inf")
                    else 0
                ),
                "max_ms": self.max_completion_time,
            },
            "tokens": {
                "input": self.total_input_tokens,
                "output": self.total_output_tokens,
                "average_input": (
                    self.total_input_tokens / self.total_usage
                    if self.total_usage > 0
                    else 0
                ),
                "average_output": (
                    self.total_output_tokens / self.total_usage
                    if self.total_usage > 0
                    else 0
                ),
            },
            "feedback": {
                "count": len(self.feedback_scores),
                "average": self.get_average_feedback_score(),
            },
            "efficiency_score": self.get_efficiency_score(),
            "first_used_at": self.first_used_at,
            "last_used_at": self.last_used_at,
        }


class AdaptiveLearningSystem:
    """
    Adaptive Learning System for prompt optimization.

    This system tracks the performance of different prompt templates,
    experiments with variations, and adapts the prompts based on their
    performance metrics.
    """

    def __init__(self, optimizer: PromptOptimizer):
        """
        Initialize the adaptive learning system.

        Args:
            optimizer: The prompt optimizer to use.
        """
        self.optimizer = optimizer
        self.metrics: Dict[str, PerformanceMetrics] = {}

        # Templates currently being tested
        self.active_experiments: Dict[str, List[str]] = (
            {}
        )  # agent_type -> [template_ids]

        # Minimum sample size for experiments
        self.min_sample_size = 10

        # Experiment success threshold (percentage)
        self.experiment_threshold = 10.0  # 10% improvement needed

        # Flag to track if metrics were loaded from storage
        self._metrics_loaded = False

    async def initialize(self, storage_path: Optional[str] = None) -> None:
        """
        Initialize the learning system, optionally loading data from storage.

        Args:
            storage_path: Optional path to metrics storage file.
        """
        if storage_path and not self._metrics_loaded:
            await self._load_metrics(storage_path)

    async def record_prompt_usage(
        self,
        template_id: str,
        success: bool,
        start_time: float,
        end_time: float,
        input_tokens: int,
        output_tokens: int,
        feedback_score: Optional[int] = None,
    ) -> None:
        """
        Record the usage of a prompt template.

        Args:
            template_id: The ID of the template.
            success: Whether the usage was successful.
            start_time: Timestamp when usage started.
            end_time: Timestamp when usage ended.
            input_tokens: Number of input tokens used.
            output_tokens: Number of output tokens generated.
            feedback_score: Optional user feedback score (1-5).
        """
        # Create metrics entry if it doesn't exist
        if template_id not in self.metrics:
            self.metrics[template_id] = PerformanceMetrics(template_id)

        # Calculate completion time in milliseconds
        completion_time_ms = int((end_time - start_time) * 1000)

        # Record metrics
        self.metrics[template_id].record_usage(
            success=success,
            completion_time_ms=completion_time_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            feedback_score=feedback_score,
        )

        # Check if this is part of an active experiment
        for agent_type, template_ids in self.active_experiments.items():
            if template_id in template_ids:
                await self._check_experiment(agent_type)

    async def start_experiment(self, agent_type: str, variation_count: int = 2) -> None:
        """
        Start an experiment for an agent type.

        This creates variations of the current best template for the agent type
        and begins tracking their performance.

        Args:
            agent_type: The agent type to experiment with.
            variation_count: Number of variations to create.
        """
        if agent_type in self.active_experiments:
            logger.warning(f"Experiment already active for agent type: {agent_type}")
            return

        # Get the current template for this agent type
        try:
            current_template = self.optimizer.get_template(agent_type)
        except ValueError:
            logger.error(f"No template found for agent type: {agent_type}")
            return

        # Create variations
        variations = []
        for i in range(variation_count):
            # Create a variation with slight modifications
            variation = self._create_template_variation(
                current_template, agent_type, i + 1
            )
            variation_name = f"{agent_type}_var_{i + 1}"

            # Add to optimizer
            self.optimizer.add_template(variation)
            variations.append(variation_name)

        # Set up the experiment
        self.active_experiments[agent_type] = [agent_type] + variations
        logger.info(
            f"Started experiment for {agent_type} with {variation_count} variations"
        )

    def _create_template_variation(
        self, template: PromptTemplate, agent_type: str, variant: int
    ) -> PromptTemplate:
        """
        Create a variation of a template for experimentation.

        Args:
            template: The template to vary.
            agent_type: The agent type.
            variant: The variant number.

        Returns:
            A new template with variations.
        """
        # Create a new template with a variation based on the variant number
        variation_name = f"{agent_type}_var_{variant}"

        # Get the original template string
        template_str = template.template

        # Create variations
        if variant == 1:
            # Add more detail to the instructions
            template_str = f"{template_str}\n\nPlease provide detailed explanations for your decisions and be as thorough as possible."
        elif variant == 2:
            # Make the instructions more concise
            template_str = (
                f"{template_str}\n\nFocus on efficiency and concise responses."
            )
        elif variant == 3:
            # Add a collaborative framing
            template_str = f"{template_str}\n\nApproach this task collaboratively, considering how your response will integrate with other agents' work."

        # Create a new template with the varied instructions
        return PromptTemplate(template=template_str, name=variation_name)

    async def _check_experiment(self, agent_type: str) -> None:
        """
        Check if an experiment has enough data to make a decision.

        Args:
            agent_type: The agent type to check.
        """
        if agent_type not in self.active_experiments:
            return

        template_ids = self.active_experiments[agent_type]

        # Check if we have enough data for all templates
        for template_id in template_ids:
            if template_id not in self.metrics:
                return
            if self.metrics[template_id].total_usage < self.min_sample_size:
                return

        # We have enough data, compare performance
        await self._evaluate_experiment(agent_type)

    async def _evaluate_experiment(self, agent_type: str) -> None:
        """
        Evaluate the results of an experiment and update templates if needed.

        Args:
            agent_type: The agent type to evaluate.
        """
        template_ids = self.active_experiments[agent_type]

        # Get the baseline (current) template
        baseline_id = template_ids[0]
        baseline_metrics = self.metrics[baseline_id]
        baseline_score = baseline_metrics.get_efficiency_score()

        # Find the best template
        best_id = baseline_id
        best_score = baseline_score

        for template_id in template_ids[1:]:
            metrics = self.metrics[template_id]
            score = metrics.get_efficiency_score()

            if score > best_score:
                best_id = template_id
                best_score = score

        # Check if improvement is significant
        if best_id != baseline_id:
            improvement = ((best_score - baseline_score) / baseline_score) * 100
            if improvement >= self.experiment_threshold:
                # Significant improvement found, update the template
                logger.info(
                    f"Experiment for {agent_type} found better template: "
                    f"{best_id} (score: {best_score:.2f}) vs "
                    f"{baseline_id} (score: {baseline_score:.2f}), "
                    f"improvement: {improvement:.2f}%"
                )
                await self._update_template(agent_type, best_id)
            else:
                logger.info(
                    f"Experiment for {agent_type} found improvement of {improvement:.2f}%, "
                    f"but below threshold of {self.experiment_threshold}%"
                )
        else:
            logger.info(
                f"Experiment for {agent_type} found no improvement. "
                f"Baseline {baseline_id} remains best with score {baseline_score:.2f}"
            )

        # End experiment
        del self.active_experiments[agent_type]

    async def _update_template(self, agent_type: str, template_name: str) -> None:
        """
        Update the default template for an agent type.

        Args:
            agent_type: The agent type.
            template_name: The name of the best template.
        """
        try:
            # Get the template
            template = self.optimizer.get_template(template_name)

            # We need to replace the existing template with this one
            # Since we can't directly update a template in the optimizer,
            # we'll create a new one with the original agent name
            new_template = PromptTemplate(template=template.template, name=agent_type)

            # Add the new template to the optimizer (will replace the existing one)
            self.optimizer.add_template(new_template)

            # Log the change
            logger.info(
                f"Updated template for agent type {agent_type} based on {template_name}"
            )
        except ValueError as e:
            logger.error(f"Template update failed: {e}")

    async def get_metrics_report(self) -> Dict[str, Any]:
        """
        Get a report of all tracked metrics.

        Returns:
            A dictionary with metrics data.
        """
        agent_types = set()
        for template_id in self.metrics:
            parts = template_id.split("_var_")
            agent_types.add(parts[0])

        report: Dict[str, Any] = {
            "agent_types": {},
            "active_experiments": list(self.active_experiments.keys()),
            "total_templates": len(self.metrics),
            "generated_at": datetime.now().isoformat(),
        }

        for agent_type in agent_types:
            agent_metrics = []
            for template_id, metrics in self.metrics.items():
                if template_id.startswith(agent_type):
                    agent_metrics.append(metrics.to_dict())

            # Check if this agent type has a template in the optimizer
            has_template = False
            try:
                self.optimizer.get_template(agent_type)
                has_template = True
            except ValueError:
                pass

            # Ensure proper typing for nested dict assignment
            agent_types_dict = report.get("agent_types")
            if not isinstance(agent_types_dict, dict):
                agent_types_dict = {}
                report["agent_types"] = agent_types_dict
            agent_types_dict[agent_type] = {
                "templates": agent_metrics,
                "has_template": has_template,
                "in_experiment": agent_type in self.active_experiments,
            }

        return report

    async def save_metrics(self, storage_path: str) -> None:
        """
        Save metrics data to storage.

        Args:
            storage_path: Path to save metrics data to.
        """
        try:
            metrics_data = {
                template_id: metrics.to_dict()
                for template_id, metrics in self.metrics.items()
            }

            data = {
                "metrics": metrics_data,
                "active_experiments": self.active_experiments,
                "saved_at": datetime.now().isoformat(),
                "version": "1.0",
            }

            with open(storage_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved metrics data to {storage_path}")
        except Exception as e:
            logger.error(f"Failed to save metrics data: {e}")

    async def _load_metrics(self, storage_path: str) -> None:
        """
        Load metrics data from storage.

        Args:
            storage_path: Path to load metrics data from.
        """
        try:
            import os

            if not os.path.exists(storage_path):
                logger.info(f"No metrics data file found at {storage_path}")
                return

            with open(storage_path, "r") as f:
                data = json.load(f)

            # Load metrics
            metrics_data = data.get("metrics", {})
            for template_id, metrics_dict in metrics_data.items():
                metrics = PerformanceMetrics(template_id)

                # Populate metrics
                metrics.total_usage = metrics_dict["usage"]["total"]
                metrics.successful_usage = metrics_dict["usage"]["successful"]
                metrics.failed_usage = metrics_dict["usage"]["failed"]

                metrics.total_completion_time = (
                    metrics_dict["time"]["average_ms"] * metrics.total_usage
                )
                metrics.min_completion_time = metrics_dict["time"]["min_ms"]
                metrics.max_completion_time = metrics_dict["time"]["max_ms"]

                metrics.total_input_tokens = metrics_dict["tokens"]["input"]
                metrics.total_output_tokens = metrics_dict["tokens"]["output"]

                if "feedback" in metrics_dict:
                    avg_feedback = metrics_dict["feedback"]["average"]
                    count = metrics_dict["feedback"]["count"]
                    if count > 0:
                        # Recreate feedback scores (approximate)
                        metrics.feedback_scores = [round(avg_feedback)] * count

                metrics.first_used_at = metrics_dict.get("first_used_at")
                metrics.last_used_at = metrics_dict.get("last_used_at")

                self.metrics[template_id] = metrics

            # Load active experiments
            self.active_experiments = data.get("active_experiments", {})

            logger.info(
                f"Loaded metrics for {len(self.metrics)} templates from {storage_path}"
            )
            self._metrics_loaded = True
        except Exception as e:
            logger.error(f"Failed to load metrics data: {e}")


def create_adaptive_learning_system(
    optimizer: Optional[PromptOptimizer] = None,
) -> AdaptiveLearningSystem:
    """
    Create an adaptive learning system.

    Args:
        optimizer: Optional prompt optimizer to use.

    Returns:
        Initialized adaptive learning system.
    """
    # Use provided optimizer or create default
    if optimizer is None:
        from .prompts import create_default_optimizer

        optimizer = create_default_optimizer()

    return AdaptiveLearningSystem(optimizer)
