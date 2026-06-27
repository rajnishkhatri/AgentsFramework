"""L1 Deterministic: Tests for components/router.py.

Phase 2 select_model() — 5 MECE branches. Pure function; no LLM; no langgraph.
Protocol A (Red-Green-Refactor) with failure-mode parametrized matrix.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from components.router import decide_escalation, select_model, select_planning_depth
from components.routing_config import RoutingConfig
from services.base_config import AgentConfig, ModelProfile

_DEPTH_STRATA_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "planning_depth"
    / "depth_strata_rich.json"
)
_DEPTH_STRATA_CORPUS: list[tuple[str, str]] = sorted(
    (record["prompt"], record["want_depth"])
    for record in json.loads(_DEPTH_STRATA_FIXTURE.read_text())
)


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


def _reasoning_profile():
    return ModelProfile(
        name="claude-opus-4-8",
        litellm_id="anthropic/claude-opus-4-8",
        tier="reasoning",
        context_window=1000000,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.025,
    )


def _three_tier_config() -> AgentConfig:
    """Anthropic-shaped registry: fast/capable/reasoning all present."""
    return AgentConfig(
        default_model="gpt-4o-mini",
        max_cost_usd=1.0,
        models=[_fast_profile(), _capable_profile(), _reasoning_profile()],
    )


class TestUserPinBranch:
    """Branch 1.5 — the per-run user pin. Honesty over silent fallback."""

    def test_pin_resolves_to_named_model(self):
        cfg = _agent_config()
        # would be steady-state-fast without a pin; pin forces gpt-4o (capable)
        profile, reason = select_model(
            5, 0, "", 0.1, ["fast"] * 5, cfg, _routing_config(), pinned_model="gpt-4o"
        )
        assert profile.name == "gpt-4o"
        assert reason == "user-pinned:gpt-4o"

    def test_empty_pin_is_byte_identical_auto(self):
        cfg = _agent_config()
        a = select_model(0, 0, "", 0.0, [], cfg, _routing_config())
        b = select_model(0, 0, "", 0.0, [], cfg, _routing_config(), pinned_model="")
        assert a[0].name == b[0].name
        assert a[1] == b[1] == "capable-for-planning"

    def test_budget_downgrade_still_wins_over_pin(self):
        """A pin must not blow the cost cap — budget (Branch 1) is higher."""
        cfg = _agent_config()
        profile, reason = select_model(
            5, 0, "", 0.95, ["fast"] * 5, cfg, _routing_config(), pinned_model="gpt-4o"
        )
        assert reason == "budget-downgrade"
        assert profile.tier == "fast"

    def test_pin_miss_falls_to_auto_but_records_the_miss(self):
        """An unregistered pin name must NOT masquerade as an Auto decision."""
        cfg = _agent_config()
        profile, reason = select_model(
            0, 0, "", 0.0, [], cfg, _routing_config(), pinned_model="ghost-model"
        )
        # fell through to Branch 4 (first step), but the miss is auditable
        assert "pin-miss:ghost-model->auto" in reason
        assert "capable-for-planning" in reason
        assert profile.tier == "capable"


class TestReasoningTierEscalation:
    """Branch 3 escalates to the reasoning tier (Opus), falling back to capable."""

    def test_escalation_reaches_reasoning_when_present(self):
        cfg = _three_tier_config()
        profile, reason = select_model(
            5, 2, "model_error", 0.1, ["fast"] * 5, cfg, _routing_config()
        )
        assert profile.tier == "reasoning"
        assert reason.startswith("escalate-after")

    def test_escalation_falls_back_to_capable_without_reasoning(self):
        """The openai 2-tier set has no reasoning tier — escalate to capable."""
        cfg = _agent_config()  # fast + capable only
        profile, reason = select_model(
            5, 2, "model_error", 0.1, ["fast"] * 5, cfg, _routing_config()
        )
        assert profile.tier == "capable"
        assert reason.startswith("escalate-after")

    def test_escalation_count_includes_reasoning_history(self):
        """Once escalated to reasoning, prior reasoning picks count against the
        escalation budget (else escalations run unbounded)."""
        cfg = _three_tier_config()
        rcfg = _routing_config()  # max_escalations=3
        # model_history entries are dicts carrying a "tier" key
        history = [{"step": i, "tier": "reasoning"} for i in range(3)]
        # 3 reasoning picks already used -> budget exhausted -> fall through
        profile, reason = select_model(5, 5, "model_error", 0.1, history, cfg, rcfg)
        assert reason == "steady-state-fast"
        assert profile.tier == "fast"


class TestDeepSeekSetRoutesThroughTiers:
    """Drive the REAL deepseek registry through select_model: the router is
    name-agnostic, so this proves the tier->name mapping end-to-end (Flash fills
    fast+capable, Pro is the reasoning escalation target, pin resolves)."""

    def _deepseek_config(self) -> AgentConfig:
        from services.llm_config import build_model_registry

        models, default_model = build_model_registry("deepseek")
        return AgentConfig(default_model=default_model, max_cost_usd=1.0, models=models)

    def test_first_step_planning_picks_flash_capable(self):
        cfg = self._deepseek_config()
        profile, reason = select_model(0, 0, "", 0.0, [], cfg, _routing_config())
        assert reason == "capable-for-planning"
        assert profile.tier == "capable"
        assert profile.name == "deepseek-v4-flash-capable"

    def test_failure_escalation_picks_pro_reasoning(self):
        cfg = self._deepseek_config()
        profile, reason = select_model(
            5, 2, "model_error", 0.1, ["fast"] * 5, cfg, _routing_config()
        )
        assert profile.tier == "reasoning"
        assert profile.name == "deepseek-v4-pro"
        assert reason.startswith("escalate-after")

    def test_steady_state_picks_flash_fast(self):
        cfg = self._deepseek_config()
        profile, reason = select_model(
            5, 0, "", 0.1, ["fast"] * 5, cfg, _routing_config()
        )
        assert reason == "steady-state-fast"
        assert profile.name == "deepseek-v4-flash"

    def test_pin_resolves_to_deepseek_pro(self):
        cfg = self._deepseek_config()
        profile, reason = select_model(
            5,
            0,
            "",
            0.1,
            ["fast"] * 5,
            cfg,
            _routing_config(),
            pinned_model="deepseek-v4-pro",
        )
        assert profile.name == "deepseek-v4-pro"
        assert reason == "user-pinned:deepseek-v4-pro"


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

    def test_rich_corpus_reaches_intended_depth(self) -> None:
        assert _DEPTH_STRATA_CORPUS, "rich depth-strata corpus is empty or missing"

        mismatches: list[str] = []
        for prompt, want in _DEPTH_STRATA_CORPUS:
            fired, reason = select_planning_depth(
                task_input=prompt,
                task_tool_results_count=0,
            )
            if fired != want:
                mismatches.append(
                    f"want={want} fired={fired} ({reason}) :: {prompt[:70]!r}"
                )

        assert not mismatches, (
            "depth collapse — rows under intended depth:\n" + "\n".join(mismatches)
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


class TestDecideEscalation:
    """Phase 3 hybrid-escalation predicate (``decide_escalation``).

    The §5 trigger matrix as one pure scalar predicate (OBP-2, no LLM — D2).
    Failure-first (AP6): the **not-fired** ``hold`` rows — budget exhausted, a
    clean verdict, a non-prose no-progress kind — land BEFORE the ``escalate``
    rows, because the headline contract is that escalation is *bounded* and only
    fires on real evidence (it must never thrash, and a clean run must not loop).
    L1-discipline: pure, deterministic, zero flake (Protocol A/C).
    """

    # ── hold (failure-first) ──────────────────────────────────────────────

    @pytest.mark.parametrize("verdict", ["failed", "partial", "success"])
    def test_holds_at_budget_ceiling_even_on_failure(self, verdict: str) -> None:
        """At/above the ceiling, ALWAYS hold — no signal overrides the budget."""
        assert (
            decide_escalation(
                goal_verdict=verdict,
                unmet_conditions=["x is reversible"],
                prose_kind="prose_repeat",
                attempt=2,
                max_attempts=2,
            )
            == "hold"
        )
        assert (
            decide_escalation(
                goal_verdict=verdict,
                unmet_conditions=[],
                prose_kind="prose_repeat",
                attempt=3,
                max_attempts=2,
            )
            == "hold"
        )

    def test_zero_budget_never_escalates(self) -> None:
        assert (
            decide_escalation(
                goal_verdict="failed",
                unmet_conditions=["x"],
                prose_kind="prose_repeat",
                attempt=0,
                max_attempts=0,
            )
            == "hold"
        )

    @pytest.mark.parametrize("verdict", ["success", "", "unknown"])
    def test_clean_verdict_no_thrash_holds(self, verdict: str) -> None:
        """A clean/unrecognized verdict with no prose thrash never escalates."""
        assert (
            decide_escalation(
                goal_verdict=verdict,
                unmet_conditions=[],
                prose_kind="none",
                attempt=0,
                max_attempts=2,
            )
            == "hold"
        )

    def test_tool_repeat_alone_does_not_escalate(self) -> None:
        """tool_repeat is check_continuation's job, not a reflexion trigger."""
        assert (
            decide_escalation(
                goal_verdict="success",
                unmet_conditions=[],
                prose_kind="tool_repeat",
                attempt=0,
                max_attempts=2,
            )
            == "hold"
        )

    # ── escalate (the fired cases) ────────────────────────────────────────

    @pytest.mark.parametrize("verdict", ["failed", "partial"])
    def test_bad_verdict_under_budget_escalates(self, verdict: str) -> None:
        """Primary §5: a failed/partial verdict escalates while budget remains."""
        assert (
            decide_escalation(
                goal_verdict=verdict,
                unmet_conditions=["the migration is reversible"],
                prose_kind="none",
                attempt=0,
                max_attempts=2,
            )
            == "escalate"
        )
        assert (
            decide_escalation(
                goal_verdict=verdict,
                unmet_conditions=[],
                prose_kind="none",
                attempt=1,
                max_attempts=2,
            )
            == "escalate"
        )

    def test_prose_thrash_on_clean_verdict_escalates(self) -> None:
        """Tertiary §5 / D3: a no-tool prose thrash escalates even when the
        verdict is clean — catches the OpenManus is_stuck failure."""
        assert (
            decide_escalation(
                goal_verdict="success",
                unmet_conditions=[],
                prose_kind="prose_repeat",
                attempt=0,
                max_attempts=2,
            )
            == "escalate"
        )

    def test_verdict_takes_priority_over_prose(self) -> None:
        """Both signals firing still escalates (priority is moot — same action)."""
        assert (
            decide_escalation(
                goal_verdict="failed",
                unmet_conditions=["x"],
                prose_kind="prose_repeat",
                attempt=0,
                max_attempts=2,
            )
            == "escalate"
        )
