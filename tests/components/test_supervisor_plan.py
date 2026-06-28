"""Decline-first tests for components/supervisor_plan.py (T3, Protocol C).

Failure-first ordering (TAP-4 / component spec §5): every *decline* condition
is written and asserted BEFORE the single *fan_out* acceptance. A component that
fans out by default is the dangerous one (the §3.5a GAIA guard), so the headline
test is "a dependent multi-step plan is NOT fanned out."

The dependent-plan fixtures are the real corpus near-miss prompts, run through
the real T1 floor (``build_plan_artifact``) so the detector is tested over
actual T1-segmented steps — not hand-written goals (component spec §3a
"lexical-on-the-plan"). No live LLM anywhere (AP5); the decompose model is a
plain injected callable stub (P6).
"""

from __future__ import annotations

import pytest

from components.plan_builder import PlanArtifact, PlanStep, build_plan_artifact
from components.supervisor_plan import (
    Delegation,
    SupervisorPlan,
    detect_sequential_dependence,
    plan_delegations,
    validate_independence,
)


# ── helpers ───────────────────────────────────────────────────────────────


def _plan(*goals: str) -> dict:
    """A minimal PlanArtifact.model_dump() from explicit step goals."""
    return PlanArtifact(
        ordered_steps=[
            PlanStep(step_id=i + 1, title=f"Step {i + 1}", goal=g)
            for i, g in enumerate(goals)
        ],
        constraints=[],
        success_conditions=["done"],
    ).model_dump()


def _t1_plan(prompt: str) -> dict:
    """The real T1 floor plan for a prompt (what the supervisor actually reads)."""
    return build_plan_artifact("L1", task_input=prompt).model_dump()


def _independent_generate(prompt: str) -> dict:
    """A decompose-LLM stub that proposes 3 independent branches."""
    return {
        "branches": [
            {"objective": "summarize document A", "subagent_type": "general"},
            {"objective": "summarize document B", "subagent_type": "general"},
            {"objective": "summarize document C", "subagent_type": "general"},
        ]
    }


def _dependent_generate(prompt: str) -> dict:
    """A decompose-LLM stub that (optimistically) proposes branches WITH edges."""
    return {
        "branches": [
            {"objective": "benchmark Redis", "subagent_type": "general"},
            {"objective": "benchmark Memcached", "subagent_type": "general"},
            {
                "objective": "recommend one using the numbers",
                "subagent_type": "general",
                "depends_on": [1, 2],
            },
        ]
    }


# The 7 named near-miss decline prompts (component spec §3a crosswalk).
NEAR_MISS_PROMPTS = {
    "trip-dated-01": "Book a trip: first book the flight, then book a hotel "
    "around the flight dates, then book a rental car for the hotel stay.",
    "restaurant-then-route-02": "Pick a highly-rated restaurant with an open "
    "dinner slot, then get directions to that restaurant and make a "
    "reservation under that name.",
    "benchmark-then-tune-03": "Benchmark Redis and Memcached for our cache, "
    "then use those numbers to recommend one and tune its configuration.",
    "fetch-then-transform-04": "Fetch the dataset from /workspace/raw.csv, then "
    "clean it, then compute the summary statistic from the cleaned data.",
    "shared-write-05": "Have three workers each append their section to the same "
    "report file /workspace/report.md: an intro section, a results section, and "
    "a conclusion section.",
    "pick-then-act-06": "Choose the cheapest of the three available flights, "
    "then book that flight and add a seat and a checked bag for that flight.",
    "policy-dependent-10": "Check whether the customer is eligible, and if "
    "eligible then apply the discount, then confirm the new total.",
}


# ═══════════════════════════════════════════════════════════════════════════
# plan_delegations — decline conditions FIRST (component spec §2 / §5)
# ═══════════════════════════════════════════════════════════════════════════


def test_1_L0_declines() -> None:
    """Condition 1: an L0 task is single-step → decline (no LLM)."""
    plan = plan_delegations(
        task_input="echo ok",
        plan_artifact=_plan("echo ok"),
        planning_depth="L0",
        generate=_independent_generate,
    )
    assert plan.decision == "decline"
    assert "single-step" in plan.reason


def test_2_single_step_L1_declines() -> None:
    """Condition 1 boundary: an L1 plan with < 2 steps → decline."""
    plan = plan_delegations(
        task_input="write an essay",
        plan_artifact=_plan("write a 3-paragraph essay"),
        planning_depth="L1",
        generate=_independent_generate,
    )
    assert plan.decision == "decline"
    assert "single-step" in plan.reason


@pytest.mark.parametrize("case", sorted(NEAR_MISS_PROMPTS))
def test_3_dependent_multistep_declines(case: str) -> None:
    """THE HEADLINE (condition 2 / GAIA guard): every near-miss decline prompt,
    run through the real T1 floor, is declined as sequential-dependent."""
    prompt = NEAR_MISS_PROMPTS[case]
    plan = plan_delegations(
        task_input=prompt,
        plan_artifact=_t1_plan(prompt),
        planning_depth="L1",
        # Give it an eager (independent) decompose model: condition 2 must
        # decline BEFORE the model is ever consulted.
        generate=_independent_generate,
    )
    assert plan.decision == "decline", f"{case} should decline (dependent chain)"
    assert "sequential-dependent" in plan.reason, case


def test_4_no_generator_declines() -> None:
    """Condition 3: an independent multi-step plan with no decompose model →
    the deterministic floor declines (never invents parallelism)."""
    plan = plan_delegations(
        task_input="summarize three unrelated docs A, B, C",
        plan_artifact=_plan("summarize doc A", "summarize doc B", "summarize doc C"),
        planning_depth="L1",
        generate=None,
    )
    assert plan.decision == "decline"
    assert "no-generator" in plan.reason


def test_5_llm_depends_on_declines() -> None:
    """Condition 4 (P6 mocked LLM): the model proposes branches WITH depends_on
    edges → validate_independence overrides the model's optimism → decline."""
    plan = plan_delegations(
        task_input="benchmark two caches then recommend",
        plan_artifact=_plan(
            "benchmark Redis", "benchmark Memcached", "recommend the better one"
        ),
        planning_depth="L1",
        generate=_dependent_generate,
    )
    assert plan.decision == "decline"
    assert "not-independent" in plan.reason


def test_5b_llm_parse_failure_declines() -> None:
    """Condition 3 floor: a decompose model that raises / returns junk →
    decline (the safe floor), never a crash."""
    plan = plan_delegations(
        task_input="three unrelated tasks",
        plan_artifact=_plan("task A", "task B", "task C"),
        planning_depth="L1",
        generate=lambda _p: {"not_branches": "garbage"},
    )
    assert plan.decision == "decline"
    assert "no-generator" in plan.reason


# ── the ONE acceptance, written LAST (component spec §5) ────────────────────


def test_6_independent_branches_fan_out() -> None:
    """Condition 5: an independent multi-step plan + a model proposing >= 2
    independent branches → fan_out (the single acceptance)."""
    plan = plan_delegations(
        task_input="summarize three unrelated documents A, B and C independently",
        plan_artifact=_plan("summarize doc A", "summarize doc B", "summarize doc C"),
        planning_depth="L1",
        generate=_independent_generate,
    )
    assert plan.decision == "fan_out"
    assert len(plan.branches) == 3
    assert validate_independence(plan) is True
    assert all(b.depends_on == [] for b in plan.branches)


def test_6b_corpus_independent_rows_fan_out() -> None:
    """The corpus independent rows fan out (true-positive sanity over real T1
    plans). Uses the independent decompose stub (the decision is the model's;
    the gate is independence, which holds)."""
    prompt = (
        "Summarize the key finding of each of three unrelated documents in "
        "/workspace/docs/ independently: a.txt, b.txt, and c.txt."
    )
    plan = plan_delegations(
        task_input=prompt,
        plan_artifact=_t1_plan(prompt),
        planning_depth="L1",
        generate=_independent_generate,
    )
    assert plan.decision == "fan_out"


# ═══════════════════════════════════════════════════════════════════════════
# validate_independence — property test (component spec §5, P1)
# ═══════════════════════════════════════════════════════════════════════════


def _fanout(*branches: Delegation) -> SupervisorPlan:
    return SupervisorPlan(decision="fan_out", branches=list(branches), reason="x")


def _branch(bid: int, obj: str, depends_on: list[int] | None = None) -> Delegation:
    return Delegation(
        branch_id=bid,
        objective=obj,
        subagent_type="general",
        depends_on=depends_on or [],
    )


def test_validate_independence_empty_depends_on_true() -> None:
    """Empty depends_on across a >=2 contiguous set ⇒ True."""
    plan = _fanout(_branch(1, "A"), _branch(2, "B"))
    assert validate_independence(plan) is True


@pytest.mark.parametrize("edges", [[2], [1], [1, 2]])
def test_validate_independence_any_edge_false(edges: list[int]) -> None:
    """Any non-empty depends_on in the fanned set ⇒ False (the crux signal)."""
    plan = _fanout(_branch(1, "A"), _branch(2, "B", depends_on=edges))
    assert validate_independence(plan) is False


def test_validate_independence_single_branch_false() -> None:
    """< 2 branches is not a fan-out ⇒ False."""
    assert validate_independence(_fanout(_branch(1, "A"))) is False


def test_validate_independence_duplicate_objective_false() -> None:
    """Duplicate objectives are not mutually exclusive ⇒ False."""
    plan = _fanout(_branch(1, "same"), _branch(2, "same"))
    assert validate_independence(plan) is False


def test_validate_independence_noncontiguous_ids_false() -> None:
    """Non-contiguous branch_ids fail the MECE numbering check ⇒ False."""
    plan = _fanout(_branch(1, "A"), _branch(3, "B"))
    assert validate_independence(plan) is False


def test_validate_independence_decline_false() -> None:
    """A decline plan is never independent (decision gate) ⇒ False."""
    assert (
        validate_independence(SupervisorPlan(decision="decline", reason="x")) is False
    )


# ═══════════════════════════════════════════════════════════════════════════
# detect_sequential_dependence — signal matrix (component spec §3a, P1)
# ═══════════════════════════════════════════════════════════════════════════


def test_dep_explicit_sequencing() -> None:
    """Signal 1 — explicit sequencing ('then') in a later step ⇒ dependent."""
    assert (
        detect_sequential_dependence(_plan("fetch the data", "then transform the data"))
        is True
    )


def test_dep_result_backref() -> None:
    """Signal 1 — result back-reference ('use those numbers') ⇒ dependent."""
    assert (
        detect_sequential_dependence(
            _plan("benchmark the caches", "use those numbers to recommend one")
        )
        is True
    )


def test_dep_conditional_gating() -> None:
    """Signal 1 — conditional gating ('if eligible, then') ⇒ dependent."""
    assert (
        detect_sequential_dependence(
            _plan("check eligibility", "if eligible then apply the discount")
        )
        is True
    )


def test_dep_anaphora_that_file() -> None:
    """Signal 1 — anaphora ('that file') to a prior artifact ⇒ dependent."""
    assert (
        detect_sequential_dependence(
            _plan("read the seed to get a filename", "read that file and summarize it")
        )
        is True
    )


def test_dep_shared_write_structural() -> None:
    """THE STRUCTURAL HEADLINE (signal 2): two steps WRITE the same path ⇒
    dependent — the case a naive 'scan for then' implementation misses."""
    assert (
        detect_sequential_dependence(
            _plan(
                "write the intro to /workspace/report.md",
                "write the conclusion to /workspace/report.md",
            )
        )
        is True
    )


def test_dep_shared_write_phrase() -> None:
    """Signal 2 backstop: a single step declaring multiple writers against one
    target ('the same report file') ⇒ dependent (survives T1 collapse)."""
    assert (
        detect_sequential_dependence(
            _plan(
                "have three workers append to the same report file",
                "the intro section",
                "the conclusion section",
            )
        )
        is True
    )


def test_dep_three_independent_summaries_not_dependent() -> None:
    """The true negative: three independent imperatives must NOT over-fire."""
    assert (
        detect_sequential_dependence(
            _plan("summarize doc A", "summarize doc B", "summarize doc C")
        )
        is False
    )


def test_dep_join_step_not_dependent() -> None:
    """A terminal aggregation/join step ('then report all three') is the
    EXPECTED fan-out shape, not an inter-branch dependency ⇒ NOT dependent."""
    assert (
        detect_sequential_dependence(
            _plan(
                "summarize doc A",
                "summarize doc B",
                "then report all three results",
            )
        )
        is False
    )


def test_dep_unmarked_semantic_chain_false_negative() -> None:
    """Documented FN (component spec §3a 'honest limit'): an unmarked semantic
    chain reads as independent. Pinned as a RECORDED false-negative, caught
    downstream by validate_independence — not a silent surprise."""
    assert (
        detect_sequential_dependence(
            _plan("compute the project budget", "staff the project")
        )
        is False
    )


def test_dep_single_step_not_dependent() -> None:
    """A < 2-step plan has nothing to be sequential about ⇒ False."""
    assert detect_sequential_dependence(_plan("do one thing")) is False
