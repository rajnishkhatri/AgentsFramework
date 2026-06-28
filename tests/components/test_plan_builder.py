"""L1/L2 deterministic tests for components/plan_builder.py."""

from __future__ import annotations

import pytest

from components.plan_builder import (
    PlanArtifact,
    PlanStep,
    build_plan_artifact,
    build_plan_artifact_llm,
    build_planning_instructions,
    compute_plan_fingerprint,
    plan_is_stale,
    validate_plan_mece,
)


# ── Phase 4: plan fingerprint (E10 dedup) ─────────────────────────────


def _artifact(goal: str = "a") -> PlanArtifact:
    return PlanArtifact(
        ordered_steps=[PlanStep(step_id=1, title="Step 1", goal=goal)],
        constraints=["c"],
        success_conditions=["s"],
    )


def test_fingerprint_is_deterministic() -> None:
    """Same (depth, artifact) → identical fingerprint across calls."""
    a = _artifact()
    assert compute_plan_fingerprint("L0", a) == compute_plan_fingerprint("L0", a)


def test_fingerprint_changes_with_steps() -> None:
    assert compute_plan_fingerprint("L0", _artifact("a")) != compute_plan_fingerprint(
        "L0", _artifact("b")
    )


def test_fingerprint_changes_with_depth() -> None:
    a = _artifact()
    assert compute_plan_fingerprint("L0", a) != compute_plan_fingerprint("L1", a)


def test_fingerprint_changes_with_constraints() -> None:
    a = PlanArtifact(
        ordered_steps=[PlanStep(step_id=1, title="S", goal="a")],
        constraints=["c1"],
        success_conditions=["s"],
    )
    b = PlanArtifact(
        ordered_steps=[PlanStep(step_id=1, title="S", goal="a")],
        constraints=["c1", "c2"],
        success_conditions=["s"],
    )
    assert compute_plan_fingerprint("L0", a) != compute_plan_fingerprint("L0", b)


def test_fingerprint_changes_with_success_conditions() -> None:
    a = PlanArtifact(
        ordered_steps=[PlanStep(step_id=1, title="S", goal="a")],
        constraints=["c"],
        success_conditions=["s1"],
    )
    b = PlanArtifact(
        ordered_steps=[PlanStep(step_id=1, title="S", goal="a")],
        constraints=["c"],
        success_conditions=["s1", "s2"],
    )
    assert compute_plan_fingerprint("L0", a) != compute_plan_fingerprint("L0", b)


def test_fingerprint_is_order_sensitive_on_steps() -> None:
    """Reordering steps changes the plan → changes the fingerprint."""
    a = PlanArtifact(
        ordered_steps=[
            PlanStep(step_id=1, title="S1", goal="x"),
            PlanStep(step_id=2, title="S2", goal="y"),
        ],
        constraints=[],
        success_conditions=[],
    )
    b = PlanArtifact(
        ordered_steps=[
            PlanStep(step_id=1, title="S1", goal="y"),
            PlanStep(step_id=2, title="S2", goal="x"),
        ],
        constraints=[],
        success_conditions=[],
    )
    assert compute_plan_fingerprint("L0", a) != compute_plan_fingerprint("L0", b)


def test_fingerprint_is_a_hex_string() -> None:
    fp = compute_plan_fingerprint("L0", _artifact())
    assert isinstance(fp, str) and len(fp) == 64  # sha256 hexdigest


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
    # One condition per branch, NO generic tail (the consistency check moved
    # to judge-time). A 3-branch task yields exactly 3 task-specific conditions.
    assert len(conditions) == 3
    assert not any("internally consistent" in c for c in conditions)


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


def test_floor_never_emits_generic_consistency_line() -> None:
    # The generic consistency line is an ANSWER-grading check moved to
    # judge-time. The plan-time floor must NEVER emit it — not even for a blank
    # task (which still yields a non-empty checklist via a task-neutral
    # placeholder branch, so validate_plan_mece's non-empty rule holds).
    for task in ["", "Single ask.", "Do A. Do B."]:
        artifact = build_plan_artifact("L1", task_input=task)
        assert artifact.success_conditions  # non-empty (MECE invariant)
        assert not any(
            "internally consistent" in c for c in artifact.success_conditions
        )


def test_derive_success_conditions_backstop_only_when_branches_empty() -> None:
    # Direct unit on the floor function: empty branch list → the generic
    # backstop is the sole condition (so the list is never empty); a non-empty
    # branch list → only task branches, no backstop.
    from components.plan_builder import derive_success_conditions
    from components.schemas import GENERIC_TAIL_CONDITION

    assert derive_success_conditions([]) == [GENERIC_TAIL_CONDITION]
    assert derive_success_conditions([" ", ""]) == [GENERIC_TAIL_CONDITION]
    branched = derive_success_conditions(["Do A", "Do B"])
    assert GENERIC_TAIL_CONDITION not in branched
    assert branched == ["Do A", "Do B"]


def test_floor_generic_pair_never_returns() -> None:
    """Exit check for Phase 1: the audit §3 boilerplate pair must be gone."""
    for task in ["", "Compare options. Evaluate risks.", "hello"]:
        artifact = build_plan_artifact("L2", task_input=task)
        for generic in GENERIC_PAIR:
            assert generic not in artifact.success_conditions


def test_floor_branch_count_capped_at_six() -> None:
    # 8 branches → capped at _MAX_BRANCH_CONDITIONS (6), and with the generic
    # tail moved to judge-time there is no +1, so exactly 6 task conditions.
    task = (
        ". ".join(
            f"Do subtask number {w}"
            for w in ["one", "two", "three", "four", "five", "six", "seven", "eight"]
        )
        + "."
    )
    artifact = build_plan_artifact("L2", task_input=task)
    assert len(artifact.success_conditions) == 6
    assert not any("internally consistent" in c for c in artifact.success_conditions)


def test_floor_property_bounds_dedupe() -> None:
    """Property-based (Pattern 1): arbitrary non-empty task strings give
    1 ≤ n ≤ 7 unique conditions that always pass MECE validation. The generic
    consistency tail moved to judge-time, so it is no longer asserted here —
    only the non-empty + dedupe + bounds invariants must hold."""
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


# ── Phase 1 (T1): LLM-backed plan with deterministic floor ────────────────
#
# Failure-first (AP6): the floor-fallback tests land BEFORE the success test —
# the contract is "the run ALWAYS has a valid plan", so the failure paths are
# the headline. An LLM plan is a bonus on top of a guaranteed floor.


def test_build_plan_artifact_llm_floors_when_generate_raises() -> None:
    """Generator raises -> deterministic floor, run still has a valid plan."""

    def boom(_task: str) -> dict:
        raise RuntimeError("LLM transport failed")

    artifact = build_plan_artifact_llm(
        "L1", task_input="Plan the Postgres migration.", generate=boom
    )
    floor = build_plan_artifact("L1", task_input="Plan the Postgres migration.")
    assert artifact == floor
    assert validate_plan_mece(artifact).is_valid


def test_build_plan_artifact_llm_floors_on_empty_steps() -> None:
    """A plan with no steps is not a plan -> floor fallback."""
    artifact = build_plan_artifact_llm(
        "L1",
        task_input="Refactor the auth module.",
        generate=lambda _t: {"ordered_steps": [], "success_conditions": ["x"]},
    )
    assert artifact == build_plan_artifact("L1", task_input="Refactor the auth module.")


def test_build_plan_artifact_llm_floors_on_garbage_shape() -> None:
    """Non-dict / wrong-typed response -> floor, never a raise to the caller."""
    artifact = build_plan_artifact_llm(
        "L1", task_input="Audit the pipeline.", generate=lambda _t: ["not", "a", "dict"]
    )
    assert artifact == build_plan_artifact("L1", task_input="Audit the pipeline.")


def test_build_plan_artifact_llm_floors_when_plan_fails_mece() -> None:
    """A structurally invalid LLM plan (overlapping goals) -> floor."""
    artifact = build_plan_artifact_llm(
        "L2",
        task_input="Design the rollout.",
        generate=lambda _t: {
            "ordered_steps": [
                {"title": "a", "goal": "same goal"},
                {"title": "b", "goal": "same goal"},
            ]
        },
    )
    assert artifact == build_plan_artifact("L2", task_input="Design the rollout.")


def test_build_plan_artifact_llm_consumes_valid_plan_structure() -> None:
    """A well-formed LLM plan is consumed — structure asserted, never exact text."""
    artifact = build_plan_artifact_llm(
        "L2",
        task_input="Compare Redis and Memcached.",
        generate=lambda _t: {
            "ordered_steps": [
                {"title": "Survey", "goal": "survey both caches"},
                {"goal": "benchmark latency"},
                {"title": "Recommend", "goal": "recommend one with rationale"},
            ],
            "constraints": ["stay vendor-neutral"],
            "success_conditions": ["a recommendation is made"],
        },
    )
    assert validate_plan_mece(artifact).is_valid
    # Contiguous step_ids re-assigned from 1 regardless of input.
    assert [s.step_id for s in artifact.ordered_steps] == [1, 2, 3]
    # Every step has a non-empty goal (structure, not exact text — AP3).
    assert all(s.goal.strip() for s in artifact.ordered_steps)
    # String-only step coerced to a goal.
    assert artifact.ordered_steps[1].goal == "benchmark latency"
    assert "stay vendor-neutral" in artifact.constraints


def test_build_plan_artifact_llm_accepts_bare_string_steps() -> None:
    """``ordered_steps`` of plain strings (a common model shape) is tolerated."""
    artifact = build_plan_artifact_llm(
        "L1",
        task_input="Build the cache layer.",
        generate=lambda _t: {"ordered_steps": ["design keys", "wire eviction"]},
    )
    assert validate_plan_mece(artifact).is_valid
    assert [s.goal for s in artifact.ordered_steps] == ["design keys", "wire eviction"]


# ── Phase 1 (T1): replan staleness gate (plan_is_stale) ───────────────────


def _plan() -> PlanArtifact:
    return PlanArtifact(
        ordered_steps=[PlanStep(step_id=1, title="Step 1", goal="do it")],
        constraints=["c"],
        success_conditions=["s"],
    )


@pytest.mark.parametrize("outcome", ["error", "failed", "failure", "ERROR"])
def test_plan_is_stale_on_failed_tool_result(outcome: str) -> None:
    """A failed/errored tool result invalidates the plan -> replan."""
    assert plan_is_stale(_plan(), {"outcome": outcome}) is True


def test_plan_is_stale_on_live_tool_failure_schema() -> None:
    """The live execute_tool schema records ok/error, not 'outcome'."""
    assert plan_is_stale(_plan(), {"ok": False, "error": None}) is True
    assert plan_is_stale(_plan(), {"ok": True, "error": "boom"}) is True


def test_plan_is_not_stale_on_live_tool_success_schema() -> None:
    assert plan_is_stale(_plan(), {"ok": True, "error": None}) is False


def test_plan_is_stale_on_explicit_surprising_flag() -> None:
    assert plan_is_stale(_plan(), {"outcome": "success", "surprising": True}) is True
    assert plan_is_stale(_plan(), {"outcome": "success", "replan": True}) is True


def test_plan_is_not_stale_on_expected_success() -> None:
    """The default path: a successful, expected result does NOT replan."""
    assert plan_is_stale(_plan(), {"outcome": "success"}) is False


def test_plan_is_not_stale_with_no_tool_result_or_empty_plan() -> None:
    assert plan_is_stale(_plan(), None) is False
    assert plan_is_stale(_plan(), {}) is False
    empty = PlanArtifact(ordered_steps=[], constraints=[], success_conditions=["s"])
    assert plan_is_stale(empty, {"outcome": "error"}) is False
