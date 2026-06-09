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


def test_build_plan_artifact_decomposes_gj012_composite_prompt() -> None:
    """GJ-012 §10.2 regression guard: the comma-then-and shape must produce 3
    discrete subtasks, one per imperative clause, so the agent attempts all of
    them before the L1 budget is exhausted.

    The prior period-only splitter chopped this into 2 broken pieces (the
    file path lost a chunk on ``f3.txt``), capping the planner at 2 steps and
    forcing the agent to fabricate subtask 3 (live weather query). Result:
    judge correctly returned ``pf=0.33`` for ~1/3 of subtasks grounded.
    """
    task = (
        "Create a file /workspace/f3.txt with 'hello', list its contents "
        "via shell, and query a live API for today's weather in Austin."
    )
    artifact = build_plan_artifact("L1", task_input=task)
    assert len(artifact.ordered_steps) == 3
    goals = [step.goal for step in artifact.ordered_steps]
    # Path must NOT be split: ``/workspace/f3.txt`` belongs in step 1.
    assert "/workspace/f3.txt" in goals[0]
    # Step 2 must mention listing — the verification subtask.
    assert "list" in goals[1].lower()
    # Step 3 must mention the live API / weather — the web_search subtask.
    assert "query" in goals[2].lower() or "weather" in goals[2].lower()


def test_extract_branches_does_not_split_noun_phrase_and() -> None:
    """TAP-4 false-positive guard: ``"Compare trade-offs and risks"`` is a
    single noun-phrase task. Bare ``" and "`` between nouns must NOT trip a
    subtask boundary, or any prompt with conjoined noun phrases would
    over-decompose into wrong subtasks.
    """
    task = "Compare trade-offs and risks in the architecture."
    artifact = build_plan_artifact("L1", task_input=task)
    assert len(artifact.ordered_steps) == 1


def test_extract_branches_does_not_split_file_path_period() -> None:
    """Path-safety guard: a ``.`` inside ``/workspace/f3.txt`` is not a
    sentence boundary. Previously this split into ``["/workspace/f3",
    "txt with 'hello'..."]`` and broke step decomposition.
    """
    task = "Write hello to /workspace/f3.txt."
    artifact = build_plan_artifact("L1", task_input=task)
    assert len(artifact.ordered_steps) == 1
    assert "/workspace/f3.txt" in artifact.ordered_steps[0].goal


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
