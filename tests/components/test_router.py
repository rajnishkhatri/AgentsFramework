"""L1 Deterministic: Tests for components/router.py.

Phase 2 select_model() — 5 MECE branches. Pure function; no LLM; no langgraph.
Protocol A (Red-Green-Refactor) with failure-mode parametrized matrix.
"""

from __future__ import annotations

import pytest

from components.router import select_model
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
