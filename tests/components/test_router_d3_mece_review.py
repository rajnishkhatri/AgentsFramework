"""L3 router regression — D3 MECE review cases from ``d3_routing_review_cases``."""

from __future__ import annotations

import pytest

from components.router import select_model
from tests.components.test_router import (
    _agent_config,
    _routing_config,
)
from tests.fixtures.goaljudge.d3_routing_review_cases import D3_ROUTING_REVIEW_CASES


@pytest.mark.parametrize("case", D3_ROUTING_REVIEW_CASES, ids=lambda c: c.id)
def test_d3_mece_review_case_matches_select_model(case) -> None:
    """Each fixture row maps to exactly one MECE branch of ``select_model``."""
    cfg = _agent_config()
    rcfg = _routing_config()
    tier_to_name = {"fast": "gpt-4o-mini", "capable": "gpt-4o"}
    history = [
        {
            "step": i,
            "model": tier_to_name.get(tier, "gpt-4o-mini"),
            "tier": tier,
            "reason": "fixture",
        }
        for i, tier in enumerate(case.history_tiers)
    ]
    profile, reason = select_model(
        step_count=case.step_count,
        consecutive_errors=case.consecutive_errors,
        last_error_type=case.last_error_type,
        total_cost_usd=case.cost_fraction * cfg.max_cost_usd,
        model_history=history,
        agent_config=cfg,
        routing_config=rcfg,
    )
    assert profile.tier == case.expected_tier, (
        f"{case.id} ({case.branch_label}): tier {profile.tier!r} != "
        f"{case.expected_tier!r}"
    )
    assert reason.startswith(case.expected_reason_prefix), (
        f"{case.id} ({case.branch_label}): reason {reason!r} must start with "
        f"{case.expected_reason_prefix!r}"
    )


def test_d3_mece_review_fixture_covers_five_distinct_branches() -> None:
    branches = {case.branch_label for case in D3_ROUTING_REVIEW_CASES}
    assert len(D3_ROUTING_REVIEW_CASES) == 5
    assert branches == {
        "capable-for-planning",
        "steady-state-fast",
        "budget-downgrade",
        "retry-after-backoff",
        "escalate-after-N-failures",
    }
