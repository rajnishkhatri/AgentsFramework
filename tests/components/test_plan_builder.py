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


# ---------------------------------------------------------------------------
# Deterministic success-conditions floor (Option A — task_understanding plan
# Phase 1, §4.3). Replaces the constant generic pair the Stage 6 audit §3
# found on 100/100 production spans. Exact-string asserts are allowed here:
# this is a pure regex pipeline, not an LLM (TAP-3 N/A).
# ---------------------------------------------------------------------------

GENERIC_PAIR = (
    "All planned branches are addressed in the final synthesis.",
    "Final answer is concise, actionable, and internally consistent.",
)


def test_floor_empty_task_input_yields_nonempty_generic_fallback() -> None:
    """Rejection case first: even a blank task must produce ≥1 condition —
    ``validate_plan_mece`` fails on empty conditions and would trigger the
    capable-tier escalation side effect."""
    artifact = build_plan_artifact("L1", task_input="")
    assert artifact.success_conditions
    assert all(c.strip() for c in artifact.success_conditions)


def test_floor_duplicate_branches_do_not_yield_duplicate_conditions() -> None:
    task = "Check the logs.\nCheck the logs.\nCheck the logs."
    artifact = build_plan_artifact("L2", task_input=task)
    normalized = [c.strip().lower() for c in artifact.success_conditions]
    assert len(normalized) == len(set(normalized))


def test_floor_output_always_passes_mece_validation() -> None:
    for task in ["", "One task.", "Do A. Do B. Do C. Do D. Do E. Do F. Do G. Do H."]:
        artifact = build_plan_artifact("L0", task_input=task)
        assert validate_plan_mece(artifact).is_valid, task


def test_floor_multiclause_task_yields_per_branch_conditions() -> None:
    task = (
        "Create a file /workspace/f3.txt with 'hello', list its contents "
        "via shell, and query a live API for today's weather in Austin."
    )
    artifact = build_plan_artifact("L1", task_input=task)
    conditions = artifact.success_conditions
    joined = " ".join(conditions)
    assert "/workspace/f3.txt" in joined
    assert "list" in joined.lower()
    assert "weather" in joined.lower()
    # One condition per branch + the generic tail.
    assert len(conditions) == 4


def test_floor_uses_all_branches_not_depth_truncated_slice() -> None:
    """An L0 plan keeps only 1 step, but the judge must still see ALL
    subtasks as conditions — the depth cap bounds execution granularity,
    not the success definition."""
    task = "Compare options. Evaluate risks. Propose migration."
    artifact = build_plan_artifact("L0", task_input=task)
    assert len(artifact.ordered_steps) == 1
    joined = " ".join(artifact.success_conditions).lower()
    assert "compare options" in joined
    assert "evaluate risks" in joined
    assert "propose migration" in joined


def test_floor_generic_tail_always_last() -> None:
    for task in ["", "Single ask.", "Do A. Do B."]:
        artifact = build_plan_artifact("L1", task_input=task)
        tail = artifact.success_conditions[-1]
        assert "internally consistent" in tail


def test_floor_generic_pair_never_returns() -> None:
    """Exit check for Phase 1: the audit §3 boilerplate pair must be gone."""
    for task in ["", "Compare options. Evaluate risks.", "hello"]:
        artifact = build_plan_artifact("L2", task_input=task)
        for generic in GENERIC_PAIR:
            assert generic not in artifact.success_conditions


def test_floor_branch_count_capped_at_six_plus_tail() -> None:
    task = ". ".join(f"Do subtask number {w}" for w in
                     ["one", "two", "three", "four", "five", "six", "seven", "eight"]) + "."
    artifact = build_plan_artifact("L2", task_input=task)
    assert len(artifact.success_conditions) <= 7


def test_floor_property_bounds_dedupe_tail() -> None:
    """Property-based (Pattern 1): arbitrary non-empty task strings give
    1 ≤ n ≤ 7 unique conditions with the generic tail present."""
    from hypothesis import given, settings
    from hypothesis import strategies as st

    @settings(max_examples=200, deadline=None)
    @given(st.text(min_size=1, max_size=400))
    def check(task: str) -> None:
        artifact = build_plan_artifact("L1", task_input=task)
        conditions = artifact.success_conditions
        assert 1 <= len(conditions) <= 7
        normalized = [c.strip().lower() for c in conditions]
        assert len(normalized) == len(set(normalized))
        assert "internally consistent" in conditions[-1]
        assert validate_plan_mece(artifact).is_valid

    check()


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
