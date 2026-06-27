"""L3 offline CI pins for CoT-gaming mitigation (Fix 2 F1).

These tests run in default CI (no ``slow`` / ``live_llm`` markers). They pin the
*structural* mitigation surface — evidence-grounding rule in the rendered prompt
and contradicting/absent tool evidence in the digest — not model robustness.

Aggregate flip-rate quality assessment remains in ``test_goal_judge_redteam.py``
(live ``live_llm`` opt-in only).
"""

from __future__ import annotations

import pytest

from components.goal_judge import GoalJudge, _summarize_evidence
from services.prompt_service import PromptService
from tests.components.test_goal_judge import FakeLLMService, _profile
from tests.components.test_goal_judge_redteam import FABRICATED_PROGRESS_CASES
from tests.fixtures.goaljudge.a2_session_fixtures import (
    A2_SESSION_FIXTURES,
    _CANNED_A2_PARTIAL_VERDICT,
)
from tests.fixtures.goaljudge.case_registry import CASE_BY_ID

# Stable substrings from prompts/goal_judge_system_prompt.j2 (EVIDENCE-GROUNDING).
# NB: keep each marker a *literal* substring — the prose wraps "Treat the agent's
# own\n   narration of progress", so the full phrase is not contiguous; pin the
# two contiguous halves instead.
_GROUNDING_RULE_MARKERS = (
    "EVIDENCE-GROUNDING",
    "Treat the agent's own",
    "narration of progress",
)

# Stage 4 A2 section — keep in sync with goal_judge_system_prompt.j2 step 3.
_A2_CORRUPT_SUCCESS_MARKERS = (
    "CORRUPT-SUCCESS",
    "partial_fraction",
    "claims done",
)

# Per-fixture digest must expose the contradicting tool output or no-tools placeholder.
_DIGEST_EXPECTATIONS: list[str] = [
    "weather",  # web_search returned weather, not BTC price
    "(no tool calls were made)",
    "Error: file not found",
    "noted",  # think tool only — no hash computed
    "permission denied",
    "(no tool calls were made)",
]

_CANNED_FALSE_VERDICT = (
    '{"goal_met": false, "criteria_met": 0.0, "per_criterion": [], '
    '"rationale": "fabricated progress", "graceful_failure": false}'
)


def _judge(response_content: str) -> tuple[GoalJudge, FakeLLMService]:
    llm = FakeLLMService(response_content)
    judge = GoalJudge(
        llm_service=llm,  # type: ignore[arg-type]
        prompt_service=PromptService(),
        judge_profile=_profile(),
    )
    return judge, llm


async def _rendered_prompt(case: dict) -> str:
    judge, llm = _judge(_CANNED_FALSE_VERDICT)
    await judge.evaluate(
        task_input=case["task_input"],
        final_answer=case["final_answer"],
        success_conditions=case["success_conditions"],
        evidence=case["evidence"],
    )
    _, messages = llm.calls[0]
    return messages[0]["content"]


# ─────────────────────────────────────────────────────────────────────
# Rejection / invariant pins (failure-path-first)
# ─────────────────────────────────────────────────────────────────────


class TestOfflineCoTGamingMitigation:
    @pytest.mark.asyncio
    async def test_canned_false_verdicts_parse_to_goal_met_false(self):
        """Parse-contract regression: canned fabricated-progress verdicts."""
        for case in FABRICATED_PROGRESS_CASES:
            judge, _ = _judge(_CANNED_FALSE_VERDICT)
            verdict = await judge.evaluate(
                task_input=case["task_input"],
                final_answer=case["final_answer"],
                success_conditions=case["success_conditions"],
                evidence=case["evidence"],
            )
            assert verdict.goal_met is False
            assert verdict.graceful_failure is False

    @pytest.mark.asyncio
    async def test_prompt_exposes_grounding_rule_for_each_fabricated_case(self):
        for case in FABRICATED_PROGRESS_CASES:
            rendered = await _rendered_prompt(case)
            assert any(marker in rendered for marker in _GROUNDING_RULE_MARKERS), (
                "evidence-grounding rule missing from rendered prompt"
            )

    @pytest.mark.asyncio
    async def test_digest_exposes_contradicting_evidence_for_each_fabricated_case(
        self,
    ):
        for case, expected in zip(
            FABRICATED_PROGRESS_CASES, _DIGEST_EXPECTATIONS, strict=True
        ):
            digest = _summarize_evidence(case["evidence"])
            assert expected in digest, (
                f"digest did not surface expected evidence token {expected!r}"
            )


class TestOfflineA2CorruptSuccessMitigation:
    @pytest.mark.asyncio
    async def test_prompt_exposes_a2_corrupt_success_markers(self):
        case = FABRICATED_PROGRESS_CASES[0]
        rendered = await _rendered_prompt(case)
        missing = [m for m in _A2_CORRUPT_SUCCESS_MARKERS if m not in rendered]
        assert not missing, f"A2 markers missing from rendered prompt: {missing}"

    @pytest.mark.parametrize("fixture", A2_SESSION_FIXTURES, ids=lambda f: f["id"])
    def test_a2_fixture_target_axes_match_registry(self, fixture: dict):
        """F7: fixtures echo registry target_axes, not hand-copied values."""
        reg = CASE_BY_ID[fixture["registry_id"]]
        assert fixture["target_code"] == reg.target_code
        assert fixture["target_axes"] == reg.target_axes

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fixture", A2_SESSION_FIXTURES, ids=lambda f: f["id"])
    async def test_a2_shaped_fixtures_digest_surfaces_tool_evidence(
        self, fixture: dict
    ):
        digest = _summarize_evidence(fixture["evidence"])
        assert "file_io" in digest or "shell" in digest or "web_search" in digest

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fixture", A2_SESSION_FIXTURES, ids=lambda f: f["id"])
    async def test_canned_a2_partial_verdict_parses_for_session_fixtures(
        self, fixture: dict
    ):
        judge, _ = _judge(_CANNED_A2_PARTIAL_VERDICT)
        verdict = await judge.evaluate(
            task_input=fixture["task_input"],
            final_answer=fixture["final_answer"],
            success_conditions=fixture["success_conditions"],
            evidence=fixture["evidence"],
        )
        assert verdict.goal_met is False
        assert verdict.partial_fraction == pytest.approx(0.67)
        assert verdict.graceful_failure is False
