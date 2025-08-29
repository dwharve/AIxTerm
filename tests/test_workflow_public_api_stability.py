"""
Test workflow engine public API stability.

This test verifies that original public symbols are importable from both
legacy paths and new modular structure to ensure backward compatibility.
"""

import pytest


def test_workflow_public_api_stability():
    """Test that original public symbols are importable and working."""
    # Test that we can import from the main workflow_engine module
    from aixterm.plugins.devteam.modules.workflow_engine import (
        WorkflowEngine,
        Workflow,
        WorkflowStep,
        WorkflowStepType,
        TaskStep,
        ConditionStep,
        WorkflowStatus,
        WorkflowStepStatus,
    )

    # Verify classes are available and have expected attributes
    assert hasattr(WorkflowEngine, "create_workflow")
    assert hasattr(WorkflowEngine, "start_workflow")
    assert hasattr(WorkflowEngine, "get_workflow")

    assert hasattr(Workflow, "to_dict")
    assert hasattr(Workflow, "from_dict")

    assert hasattr(WorkflowStep, "execute")
    assert hasattr(WorkflowStep, "to_dict")
    assert hasattr(WorkflowStep, "from_dict")

    assert hasattr(TaskStep, "execute")
    assert hasattr(ConditionStep, "execute")

    # Test enums have expected values
    assert WorkflowStepType.TASK.value == "task"
    assert WorkflowStepType.CONDITION.value == "condition"

    assert WorkflowStatus.PENDING.value == "pending"
    assert WorkflowStatus.RUNNING.value == "running"

    assert WorkflowStepStatus.PENDING.value == "pending"
    assert WorkflowStepStatus.IN_PROGRESS.value == "in_progress"


def test_modular_imports_work():
    """Test that modular structure imports work correctly."""
    # Test imports from individual modules
    from aixterm.plugins.devteam.modules.workflow_engine_modules.models import (
        Workflow,
        WorkflowStep,
        WorkflowStepType,
    )
    from aixterm.plugins.devteam.modules.workflow_engine_modules.executor import WorkflowEngine
    from aixterm.plugins.devteam.modules.workflow_engine_modules.step_types import (
        TaskStep,
        ConditionStep,
    )

    # Verify these are the same classes as imported from the facade
    from aixterm.plugins.devteam.modules.workflow_engine import (
        WorkflowEngine as FacadeWorkflowEngine,
        Workflow as FacadeWorkflow,
        WorkflowStep as FacadeWorkflowStep,
        WorkflowStepType as FacadeWorkflowStepType,
        TaskStep as FacadeTaskStep,
        ConditionStep as FacadeConditionStep,
    )

    # These should be the same classes
    assert WorkflowEngine is FacadeWorkflowEngine
    assert Workflow is FacadeWorkflow
    assert WorkflowStep is FacadeWorkflowStep
    assert WorkflowStepType is FacadeWorkflowStepType
    assert TaskStep is FacadeTaskStep
    assert ConditionStep is FacadeConditionStep


def test_api_signatures_preserved():
    """Test that key API signatures are preserved."""
    from aixterm.plugins.devteam.modules.workflow_engine import (
        WorkflowEngine,
        Workflow,
        WorkflowStep,
        WorkflowStepType,
        TaskStep,
    )
    import inspect

    # Check WorkflowEngine.create_workflow signature
    create_workflow_sig = inspect.signature(WorkflowEngine.create_workflow)
    expected_params = {"self", "name", "description", "steps", "metadata", "start_step_id"}
    actual_params = set(create_workflow_sig.parameters.keys())
    assert expected_params == actual_params

    # Check Workflow constructor signature
    workflow_sig = inspect.signature(Workflow.__init__)
    expected_params = {
        "self",
        "name",
        "description",
        "steps",
        "workflow_id",
        "metadata",
        "start_step_id",
    }
    actual_params = set(workflow_sig.parameters.keys())
    assert expected_params == actual_params

    # Check WorkflowStep constructor signature
    step_sig = inspect.signature(WorkflowStep.__init__)
    expected_params = {
        "self",
        "step_id",
        "step_type",
        "name",
        "description",
        "next_steps",
        "metadata",
    }
    actual_params = set(step_sig.parameters.keys())
    assert expected_params == actual_params

    # Check TaskStep constructor doesn't require step_type (automatically set)
    task_step_sig = inspect.signature(TaskStep.__init__)
    assert "step_type" not in task_step_sig.parameters
    assert "task_title" in task_step_sig.parameters
    assert "task_description" in task_step_sig.parameters
