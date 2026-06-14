"""L1 Deterministic: Tests for components/router.py.

Phase 2 select_model() — 5 MECE branches. Pure function; no LLM; no langgraph.
Protocol A (Red-Green-Refactor) with failure-mode parametrized matrix.
"""

from __future__ import annotations

import pytest

from components.router import select_model, select_planning_depth
from components.routing_config import RoutingConfig
from services.base_config import AgentConfig, ModelProfile


def _fast_profile():
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _capable_profile():
    return ModelProfile(
        name="gpt-4o",
        litellm_id="openai/gpt-4o",
        tier="capable",
        context_window=128000,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.015,
    )


def _agent_config() -> AgentConfig:
    return AgentConfig(
        default_model="gpt-4o-mini",
        max_cost_usd=1.0,
        models=[_fast_profile(), _capable_profile()],
    )


def _routing_config() -> RoutingConfig:
    return RoutingConfig(
        default_model="gpt-4o-mini",
        escalate_after_failures=2,
        max_escalations=3,
        budget_downgrade_threshold=0.8,
    )


# ─────────────────────────────────────────────────────────────────────
# Branch matrix: (step, errors, err_type, cost_frac, history) ->
# (expected_tier, expected_reason_prefix)
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "step,errors,err_type,cost_frac,history_tiers,expected_tier,expected_reason_prefix",
    [
        # Branch 4: first step -> capable planning
        (0, 0, "", 0.0, [], "capable", "capable-for-planning"),
        # Branch 5: steady state -> fast
        (5, 0, "", 0.1, ["fast"] * 5, "fast", "steady-state-fast"),
        # Branch 1: budget downgrade wins over everything else
        (5, 0, "", 0.85, ["fast"] * 5, "fast", "budget-downgrade"),
        # Branch 2: retryable -> same model (previously fast)
        (5, 1, "retryable", 0.1, ["fast"] * 5, "fast", "retry-after-backoff"),
        (5, 1, "retryable", 0.1, ["capable"] * 5, "capable", "retry-after-backoff"),
        # Branch 3: escalate after N failures
        (5, 2, "model_error", 0.1, ["fast"] * 5, "capable", "escalate-after"),
        # Branch 1 beats Branch 3: budget wins over escalation
        (5, 2, "model_error", 0.85, ["fast"] * 5, "fast", "budget-downgrade"),
        # Branch 1 beats Branch 2: budget wins over retryable
        (5, 1, "retryable", 0.9, ["fast"] * 5, "fast", "budget-downgrade"),
        # Branch 3 bounded by max_escalations (3): 3 capable uses already -> fall through to default
        (5, 5, "model_error", 0.1, ["capable"] * 3, "fast", "steady-state-fast"),
    ],
)
def test_branch_matrix(
    step,
    errors,
    err_type,
    cost_frac,
    history_tiers,
    expected_tier,
    expected_reason_prefix,
):
    cfg = _agent_config()
    rcfg = _routing_config()
    tier_to_name = {"fast": "gpt-4o-mini", "capable": "gpt-4o"}
    history = [
        {
            "step": i,
            "model": tier_to_name.get(tier, "gpt-4o-mini"),
            "tier": tier,
            "reason": "r",
        }
        for i, tier in enumerate(history_tiers)
    ]
    profile, reason = select_model(
        step_count=step,
        consecutive_errors=errors,
        last_error_type=err_type,
        total_cost_usd=cost_frac * cfg.max_cost_usd,
        model_history=history,
        agent_config=cfg,
        routing_config=rcfg,
    )
    assert profile.tier == expected_tier, (
        f"tier mismatch: got {profile.tier}, expected {expected_tier}"
    )
    assert reason.startswith(expected_reason_prefix), (
        f"reason '{reason}' must start with '{expected_reason_prefix}'"
    )


class TestBranchOrdering:
    def test_first_match_wins_budget_over_everything(self):
        """Branch 1 strictly precedes all others (budget>=threshold AND retryable)."""
        cfg = _agent_config()
        rcfg = _routing_config()
        _, reason = select_model(
            step_count=0,
            consecutive_errors=10,
            last_error_type="retryable",
            total_cost_usd=0.95,
            model_history=[{"step": 0, "model": "gpt-4o", "tier": "capable"}],
            agent_config=cfg,
            routing_config=rcfg,
        )
        assert reason == "budget-downgrade"

    def test_every_state_maps_exactly_one_branch(self):
        """Sanity: function always returns; no state tuple is unreachable."""
        cfg = _agent_config()
        rcfg = _routing_config()
        for step in (0, 1, 5):
            for errors in (0, 2, 5):
                for err in ("", "retryable", "model_error", "terminal"):
                    for frac in (0.1, 0.85):
                        profile, reason = select_model(
                            step_count=step,
                            consecutive_errors=errors,
                            last_error_type=err,
                            total_cost_usd=frac * cfg.max_cost_usd,
                            model_history=[],
                            agent_config=cfg,
                            routing_config=rcfg,
                        )
                        assert isinstance(profile, ModelProfile)
                        assert isinstance(reason, str) and reason


class TestFallbacks:
    def test_when_no_capable_tier_available_first_step_falls_to_fast(self):
        cfg = AgentConfig(default_model="gpt-4o-mini", models=[_fast_profile()])
        rcfg = _routing_config()
        profile, reason = select_model(
            step_count=0,
            consecutive_errors=0,
            last_error_type="",
            total_cost_usd=0.0,
            model_history=[],
            agent_config=cfg,
            routing_config=rcfg,
        )
        assert profile.tier == "fast"
        assert reason == "steady-state-fast"

    def test_retryable_with_empty_history_uses_default(self):
        cfg = _agent_config()
        rcfg = _routing_config()
        profile, reason = select_model(
            step_count=2,
            consecutive_errors=1,
            last_error_type="retryable",
            total_cost_usd=0.1,
            model_history=[],
            agent_config=cfg,
            routing_config=rcfg,
        )
        assert profile.name == "gpt-4o-mini"
        assert reason == "retry-after-backoff"


class TestReturnShape:
    def test_returns_tuple_of_profile_and_reason(self):
        cfg = _agent_config()
        rcfg = _routing_config()
        result = select_model(0, 0, "", 0.0, [], cfg, rcfg)
        assert isinstance(result, tuple)
        assert len(result) == 2
        profile, reason = result
        assert isinstance(profile, ModelProfile)
        assert isinstance(reason, str) and reason


class TestPlanningDepth:
    @pytest.mark.parametrize(
        "task_input,task_tool_results_count,expected_depth,expected_reason",
        [
            ("What is 2+2?", 0, "L0", "simple-initial-task"),
            (
                "Compare architecture trade-offs and propose a migration roadmap with constraints.",
                0,
                "L1",
                "moderate-complexity-initial-task",
            ),
            (
                "Compare architecture options and design a migration plan.\n"
                "Also include risks and phased rollout.\n"
                "Then propose test strategy and governance checks?",
                0,
                "L2",
                "high-complexity-initial-task",
            ),
            ("Any follow-up after tools.", 1, "L0", "post-tool-synthesis"),
            # Per-task scoping regression guard: a multi-subtask prompt on a
            # long-lived LangGraph thread (saturation runs, replay batches,
            # multi-turn UIs) must still classify as L1 when *this task* has
            # produced zero tool results — even if the thread overall has
            # many. The bug this guards: prior router took thread-wide
            # ``step_count`` / ``len(state["tool_results"])`` and fell into
            # ``post-tool-synthesis`` (L0), so the planner capped at 1 step,
            # and the agent fabricated subtasks 2-N. The caller is now
            # responsible for filtering tool_results to the current task_id.
            (
                "Create a file /workspace/f3.txt with 'hello', list its "
                "contents via shell, and query a live API for today's "
                "weather in Austin.",
                0,  # task_tool_results_count=0 — this task has not yet acted
                "L1",
                "moderate-complexity-initial-task",
            ),
            # Composite imperative chains — Stage 4 §10.2 GJ-010/011/012
            # regression guard. Without enumeration / comma-then-and
            # detection, these score 1 (just " and ") and fall through to L0,
            # capping the planner at 1 step and causing the agent to fabricate
            # the missing subtasks (root cause of GJ-012 pf=0.33).
            (
                "Do these three things: (1) write 'first' to /tmp/f1.txt; "
                "(2) write 'second' to /tmp/f2.txt; (3) search the web for "
                "the live population of Mars and report it.",
                0,
                "L1",
                "moderate-complexity-initial-task",
            ),
            (
                "Create a file /tmp/f3.txt with 'hello', list its contents "
                "via shell, and query a live API for today's weather.",
                0,
                "L1",
                "moderate-complexity-initial-task",
            ),
            # TAP-4 rejection guard: a single-imperative prompt with one
            # incidental comma must NOT trip the new comma-then-and heuristic
            # (only TWO commas + "and" should fire it). If this flips to L1
            # we're over-flagging trivial tasks and burning planner budget.
            (
                "Write the number 42 to /tmp/answer.txt.",
                0,
                "L0",
                "simple-initial-task",
            ),
            # TAP-4 rejection guard: a single "(1)"-marked enumeration is NOT
            # multi-subtask — needs at least two enumeration markers to fire.
            (
                "Step (1) is the only step.",
                0,
                "L0",
                "simple-initial-task",
            ),
            # TAP-4 over-flag guard (CI regression from this PR): an
            # architecture-style prompt already scoring on multi_part_markers
            # + " and " must NOT *also* pick up the comma-then-and bonus, or
            # the L1-expected synthetic e2e fixtures
            # (``todo_file_progression``, ``large_output_offload``) get
            # pushed into L2. The comma-then-and heuristic is gated on the
            # absence of multi_part_markers for exactly this reason.
            (
                "Compare two architecture approaches, design a migration "
                "roadmap, and then produce a concise implementation summary "
                "with testing notes and explicit constraints.",
                0,
                "L1",
                "moderate-complexity-initial-task",
            ),
            (
                "Design and compare rollout options, then summarize risks, "
                "constraints, and mitigation trade-offs for the migration.",
                0,
                "L1",
                "moderate-complexity-initial-task",
            ),
        ],
    )
    def test_select_planning_depth_levels(
        self,
        task_input: str,
        task_tool_results_count: int,
        expected_depth: str,
        expected_reason: str,
    ) -> None:
        depth, reason = select_planning_depth(
            task_input=task_input,
            task_tool_results_count=task_tool_results_count,
        )
        assert depth == expected_depth
        assert reason == expected_reason


class TestDepthCollapseRegression:
    """Depth-collapse fix (planning-pipeline Phase 0).

    Oracle: ``tests/fixtures/planning_depth/depth_strata_rich.json`` carries
    the *untruncated* prompts plus the intended depth (``want_depth``) per
    stratum. Derived from the offline GoalJudge depth-strata run
    (``cache/goaljudge_eval/depth_strata_rich.jsonl`` when present locally).

    Pre-fix, the additive lexical scorer under-scored short single-intent tasks
    ("Plan the Postgres migration.", "Refactor the auth module.") and long
    no-other-signal tasks down to L0, collapsing the plan to one step. This is
    the **failure-first** regression test: it asserts every rich-corpus row
    reaches its intended depth when scored fresh (``task_tool_results_count=0``).
    L1-discipline: pure, deterministic, no LLM (Protocol A).
    """

    @staticmethod
    def _load_rich_corpus() -> list[tuple[str, str]]:
        import json
        from pathlib import Path

        path = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "planning_depth"
            / "depth_strata_rich.json"
        )
        records = json.loads(path.read_text())
        rows: dict[str, str] = {}
        for record in records:
            rows[record["prompt"]] = record["want_depth"]
        return sorted(rows.items())

    def test_rich_corpus_reaches_intended_depth(self) -> None:
        corpus = self._load_rich_corpus()
        assert corpus, "rich depth-strata corpus is empty or missing"

        mismatches: list[str] = []
        for prompt, want in corpus:
            fired, reason = select_planning_depth(
                task_input=prompt,
                task_tool_results_count=0,
            )
            if fired != want:
                mismatches.append(
                    f"want={want} fired={fired} ({reason}) :: {prompt[:70]!r}"
                )

        assert not mismatches, "depth collapse — rows under intended depth:\n" + "\n".join(
            mismatches
        )

    def test_post_tool_synthesis_still_collapses_to_l0(self) -> None:
        # Do not over-correct: a genuine post-tool-synthesis turn (this task has
        # already produced a tool result) must still route L0, even for a prompt
        # that scores high when fresh. Guards the per-task-scoped count contract.
        depth, reason = select_planning_depth(
            task_input="Plan the Postgres migration and audit the rollout.",
            task_tool_results_count=1,
        )
        assert depth == "L0"
        assert reason == "post-tool-synthesis"
