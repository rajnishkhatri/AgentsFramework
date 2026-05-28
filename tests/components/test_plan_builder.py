"""L1/L2 deterministic tests for components/plan_builder.py."""

from __future__ import annotations

import pytest

from components.plan_builder import (
    PlanArtifact,
    PlanStep,
    build_plan_artifact,
    build_planning_instructions,
    validate_plan_mece,
)


@pytest.mark.parametrize(
    "depth,needle",
    [
        ("L0", "Planning depth L0"),
        ("L1", "Planning depth L1"),
        ("L2", "Planning depth L2"),
    ],
)
def test_build_planning_instructions_by_depth(depth: str, needle: str) -> None:
    rendered = build_planning_instructions(depth, task_input="demo task")
    assert needle in rendered


def test_build_plan_artifact_respects_depth_limit() -> None:
    task = "Compare options. Evaluate risks. Propose migration. Define tests."
    artifact = build_plan_artifact("L1", task_input=task)
    assert len(artifact.ordered_steps) == 3
    assert artifact.ordered_steps[0].step_id == 1
    assert artifact.success_conditions


def test_validate_plan_mece_rejects_overlapping_goals() -> None:
    artifact = PlanArtifact(
        ordered_steps=[
            PlanStep(step_id=1, title="Step 1", goal="Analyze architecture"),
            PlanStep(step_id=2, title="Step 2", goal="Analyze architecture"),
        ],
        constraints=["Keep scope bounded"],
        success_conditions=["Cover all branches"],
    )
    result = validate_plan_mece(artifact)
    assert result.is_valid is False
    assert any("not MECE" in issue for issue in result.issues)
