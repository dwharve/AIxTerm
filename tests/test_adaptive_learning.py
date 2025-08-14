"""
Tests for the DevTeam plugin's adaptive learning system.
"""

import pytest

from aixterm.plugins.devteam.adaptive import (
    AdaptiveLearningSystem,
    PerformanceMetrics,
    create_adaptive_learning_system,
)
from aixterm.plugins.devteam.prompts import PromptOptimizer, PromptTemplate


class TestPerformanceMetrics:
    """Tests for the PerformanceMetrics class."""

    def test_init(self):
        """Test initialization of performance metrics."""
        metrics = PerformanceMetrics("test_template")
        assert metrics.template_name == "test_template"
        assert metrics.total_usage == 0
        assert metrics.successful_usage == 0
        assert metrics.failed_usage == 0

    def test_record_usage(self):
        """Test recording usage metrics."""
        metrics = PerformanceMetrics("test_template")

        # Record a successful usage
        metrics.record_usage(
            success=True, completion_time_ms=100, input_tokens=50, output_tokens=150
        )

        assert metrics.total_usage == 1
        assert metrics.successful_usage == 1
        assert metrics.failed_usage == 0
        assert metrics.total_completion_time == 100
        assert metrics.min_completion_time == 100
        assert metrics.max_completion_time == 100
        assert metrics.total_input_tokens == 50
        assert metrics.total_output_tokens == 150

        # Record a failed usage
        metrics.record_usage(
            success=False, completion_time_ms=200, input_tokens=60, output_tokens=20
        )

        assert metrics.total_usage == 2
        assert metrics.successful_usage == 1
        assert metrics.failed_usage == 1
        assert metrics.total_completion_time == 300
        assert metrics.min_completion_time == 100
        assert metrics.max_completion_time == 200
        assert metrics.total_input_tokens == 110
        assert metrics.total_output_tokens == 170

    def test_feedback_recording(self):
        """Test recording user feedback."""
        metrics = PerformanceMetrics("test_template")

        # Record usage with feedback
        metrics.record_usage(
            success=True,
            completion_time_ms=100,
            input_tokens=50,
            output_tokens=150,
            feedback_score=4,
        )

        assert len(metrics.feedback_scores) == 1
        assert metrics.feedback_scores[0] == 4
        assert metrics.get_average_feedback_score() == 4.0

        # Record another usage with feedback
        metrics.record_usage(
            success=True,
            completion_time_ms=100,
            input_tokens=50,
            output_tokens=150,
            feedback_score=2,
        )

        assert len(metrics.feedback_scores) == 2
        assert metrics.get_average_feedback_score() == 3.0

    def test_success_rate(self):
        """Test success rate calculation."""
        metrics = PerformanceMetrics("test_template")

        # No usage yet
        assert metrics.get_success_rate() == 0.0

        # Record usages
        metrics.record_usage(True, 100, 50, 150)
        assert metrics.get_success_rate() == 100.0

        metrics.record_usage(False, 200, 60, 20)
        assert metrics.get_success_rate() == 50.0

        metrics.record_usage(True, 150, 55, 130)
        # Use pytest's approx for floating point comparison
        from pytest import approx

        assert metrics.get_success_rate() == approx(100 * 2 / 3)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metrics = PerformanceMetrics("test_template")
        metrics.record_usage(True, 100, 50, 150, 5)

        result = metrics.to_dict()
        assert result["template_name"] == "test_template"
        assert result["usage"]["total"] == 1
        assert result["usage"]["successful"] == 1
        assert result["usage"]["failed"] == 0
        assert result["usage"]["success_rate"] == 100.0
        assert result["feedback"]["average"] == 5.0


class TestAdaptiveLearningSystem:
    """Tests for the AdaptiveLearningSystem class."""

    @pytest.fixture
    def optimizer(self):
        """Create a mock prompt optimizer."""
        optimizer = PromptOptimizer()
        optimizer.add_template(
            PromptTemplate(
                template="This is a test template for {agent_type}",
                name="project_manager",
            )
        )
        optimizer.add_template(
            PromptTemplate(
                template="Another template for {agent_type}", name="developer"
            )
        )
        return optimizer

    @pytest.fixture
    def learning_system(self, optimizer):
        """Create an adaptive learning system."""
        return AdaptiveLearningSystem(optimizer)

    @pytest.mark.asyncio
    async def test_record_prompt_usage(self, learning_system):
        """Test recording prompt usage."""
        # Record usage
        await learning_system.record_prompt_usage(
            template_id="project_manager",
            success=True,
            start_time=1000.0,
            end_time=1000.1,
            input_tokens=50,
            output_tokens=150,
            feedback_score=5,
        )

        # Check that metrics were recorded
        assert "project_manager" in learning_system.metrics
        metrics = learning_system.metrics["project_manager"]
        assert metrics.total_usage == 1
        assert metrics.successful_usage == 1
        assert metrics.failed_usage == 0
        assert len(metrics.feedback_scores) == 1
        assert metrics.feedback_scores[0] == 5

    @pytest.mark.asyncio
    async def test_get_metrics_report(self, learning_system):
        """Test getting metrics report."""
        # Record usage for two templates
        await learning_system.record_prompt_usage(
            template_id="project_manager",
            success=True,
            start_time=1000.0,
            end_time=1000.1,
            input_tokens=50,
            output_tokens=150,
        )

        await learning_system.record_prompt_usage(
            template_id="developer",
            success=False,
            start_time=2000.0,
            end_time=2000.2,
            input_tokens=100,
            output_tokens=50,
        )

        # Get metrics report
        report = await learning_system.get_metrics_report()

        # Check report structure
        assert "agent_types" in report
        assert "project_manager" in report["agent_types"]
        assert "developer" in report["agent_types"]
        assert "total_templates" in report
        assert report["total_templates"] == 2

    @pytest.mark.asyncio
    async def test_create_template_variation(self, learning_system, optimizer):
        """Test creating template variations."""
        template = optimizer.get_template("project_manager")

        # Create variation
        variation = learning_system._create_template_variation(
            template, "project_manager", 1
        )

        # Check variation properties
        assert variation.name == "project_manager_var_1"
        assert "This is a test template for" in variation.template
        assert "provide detailed explanations" in variation.template


def test_create_adaptive_learning_system():
    """Test creating an adaptive learning system with default optimizer."""
    system = create_adaptive_learning_system()
    assert isinstance(system, AdaptiveLearningSystem)
    assert isinstance(system.optimizer, PromptOptimizer)
