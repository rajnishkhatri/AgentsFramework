"""Offline CI pins for the GoalJudge synthetic stress fixtures.

UNMARKED on purpose: these run in default CI (no ``slow`` / ``live_llm``).
They pin the *parse contract* for the deterministic judge-stress set, not
model robustness (the aggregate live diagnostics live in
``test_goal_judge_stress.py``).
"""

from __future__ import annotations

import pytest

from components.goal_judge import GoalJudge
from services.prompt_service import PromptService
from tests.components.test_goal_judge import FakeLLMService, _profile
from tests.fixtures.goaljudge.stress_fixtures import ALL_STRESS_CASES

_CANNED_FALSE_VERDICT = (
    '{"goal_met": false, "criteria_met": 0.0, "per_criterion": [], '
    '"rationale": "stress test", "graceful_failure": true}'
)


def _fake_judge(canned_response: str) -> GoalJudge:
    llm = FakeLLMService(canned_response)
    return GoalJudge(
        llm_service=llm,  # type: ignore[arg-type]
        prompt_service=PromptService(),
        judge_profile=_profile(),
    )


@pytest.mark.asyncio
async def test_stress_cases_offline_parser_contract():
    """Canned fabricated/premature verdicts parse to goal_met=False."""
    for case in ALL_STRESS_CASES:
        judge = _fake_judge(_CANNED_FALSE_VERDICT)
        verdict = await judge.evaluate(
            task_input=case["task_input"],
            final_answer=case["final_answer"],
            success_conditions=case["success_conditions"],
            evidence=case["evidence"],
        )
        assert verdict.goal_met is False
        assert verdict.graceful_failure is True


def test_stress_fixtures_are_tagged_synthetic_and_excluded():
    """Firewall pin: every stress case is provenance=synthetic (never live)."""
    assert ALL_STRESS_CASES, "stress set must be non-empty"
    for case in ALL_STRESS_CASES:
        assert case["provenance"] == "synthetic"
        assert case["target_code"] in {"fabricated-progress", "premature-impossible"}
