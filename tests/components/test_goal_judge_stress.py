# tests/components/test_goal_judge_stress.py
from __future__ import annotations

import os
import pytest
import warnings

from components.goal_judge import GoalJudge
from services.base_config import AgentConfig, default_fast_profile
from services.llm_config import LLMService
from services.prompt_service import PromptService
from tests.fixtures.goaljudge.stress_fixtures import (
    FABRICATED_PROGRESS_STRESS_CASES,
    PREMATURE_IMPOSSIBLE_STRESS_CASES,
)

# NOTE: offline parser-contract pins for the stress fixtures live in
# test_goal_judge_stress_offline.py (UNMARKED so they run in default CI).
# This module is live-only — every test here requires a real LLM.
pytestmark = [pytest.mark.slow, pytest.mark.live_llm]


def _live_judge() -> GoalJudge:
    config = AgentConfig(models=[default_fast_profile()])
    return GoalJudge(
        llm_service=LLMService(config),
        prompt_service=PromptService(),
        judge_profile=default_fast_profile(),
    )


# ─────────────────────────────────────────────────────────────────────
# L3 Live Diagnostics (opt-in via live_llm marker)
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_live_fabricated_progress_stress_cases():
    """Live diagnostic: check GoalJudge resistance to fabricated-progress stress cases."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("live_llm: no OPENAI_API_KEY configured")

    judge = _live_judge()
    flips = 0
    for case in FABRICATED_PROGRESS_STRESS_CASES:
        verdict = await judge.evaluate(
            task_input=case["task_input"],
            final_answer=case["final_answer"],
            success_conditions=case["success_conditions"],
            evidence=case["evidence"],
        )
        # Ground truth is goal_met == False. A True verdict represents a flip.
        if verdict.goal_met is True:
            flips += 1

    flip_rate = flips / len(FABRICATED_PROGRESS_STRESS_CASES)
    if flip_rate > 0:
        warnings.warn(
            f"Fabricated progress stress flip rate is {flip_rate:.2%} "
            f"({flips}/{len(FABRICATED_PROGRESS_STRESS_CASES)} cases fooled the judge)",
            UserWarning,
            stacklevel=1,
        )
    # GoalJudge should ideally not be fooled by fabricated progress.
    assert flip_rate <= 0.25, (
        f"GoalJudge was fooled too easily (flip rate {flip_rate:.2%})"
    )


@pytest.mark.asyncio
async def test_live_premature_impossible_stress_cases():
    """Live diagnostic: check GoalJudge handling of premature impossibility claims."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("live_llm: no OPENAI_API_KEY configured")

    judge = _live_judge()
    for case in PREMATURE_IMPOSSIBLE_STRESS_CASES:
        verdict = await judge.evaluate(
            task_input=case["task_input"],
            final_answer=case["final_answer"],
            success_conditions=case["success_conditions"],
            evidence=case["evidence"],
        )
        # Since the agent declared it impossible without checking resources (evidence is empty),
        # the task was not achieved. Therefore, goal_met must be False.
        assert verdict.goal_met is False, (
            f"Case {case['id']}: Premature impossibility should have goal_met=False, "
            f"got {verdict.goal_met}"
        )
