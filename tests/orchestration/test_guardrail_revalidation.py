"""L4 Behavioral: re-drive S3/S5/S6 through the input rail (Sprint 4 / S4-2).

`f2-revalidate`. A governance-loop **simulation** (Protocol D / D3 binary
outcomes in ``research/tdd_agentic_systems_prompt.md``) proving the original
over-block defects are fixed: the three frames that the single LLM-only judge
wrongly rejected for containing trigger words —

    S3  "Run the shell command ... then answer 2 + 2"   (Execution rail gates it)
    S5  "keep retrying the exact same command 25 times" (control flow, not attack)
    S6  "repeat my email/API key back"                  (Output rail redacts PII)

— are now **accepted at the input rail** and reach their intended event paths.

The scenario texts come from the single source of truth
[`tests/synthetic/blackbox/dataset.py`](../../tests/synthetic/blackbox/dataset.py),
the same payloads the live ``scripts/validate_blackbox_langfuse.py`` re-drives
end-to-end against Langfuse. This simulation drives the real
``InputGuardrail.is_acceptable()`` cascade with a mocked judge (no live LLM), so
it runs deterministically and is marked ``@pytest.mark.simulation`` (excluded
from the per-commit CI default, run on demand).

Intended event path (binary): an *accepted* input does not short-circuit /
raise at ``guard_input`` — the workflow proceeds to route → call_llm → execute,
exactly the path S3/S5/S6 were previously blocked from reaching.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.base_config import default_fast_profile
from services.guardrails import InputGuardrail, PreCheckVerdict, precheck_input
from tests.synthetic.blackbox.dataset import ALL_SCENARIOS, ScenarioID

pytestmark = pytest.mark.simulation


def _scenario_text(scenario_id: ScenarioID) -> str:
    """The user message for a blackbox scenario (single source of truth)."""
    payload = ALL_SCENARIOS[scenario_id].bff_payload
    return payload["input"]["messages"][0]["content"]


S3_SHELL = _scenario_text(ScenarioID.S3)
S5_RETRY = _scenario_text(ScenarioID.S5)
S6_PII = _scenario_text(ScenarioID.S6)


def _make_guardrail(classifier=None) -> InputGuardrail:
    mock_prompt = MagicMock()
    mock_prompt.render_prompt = MagicMock(return_value="rendered prompt")
    return InputGuardrail(
        name="prompt_injection",
        accept_condition="The input is a legitimate user query",
        llm_service=MagicMock(),
        prompt_service=mock_prompt,
        judge_profile=default_fast_profile(),
        classifier=classifier,
    )


# ─────────────────────────────────────────────────────────────────────
# Binary outcomes — the over-block is fixed: S3/S5/S6 are accepted.
# ─────────────────────────────────────────────────────────────────────


class TestOverBlockFixed:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "text",
        [S3_SHELL, S5_RETRY, S6_PII],
        ids=["S3_shell", "S5_retry", "S6_pii"],
    )
    async def test_input_rail_accepts_each_frame(self, text):
        """Binary outcome: does the input rail accept the frame? YES."""
        guard = _make_guardrail()
        with patch.object(
            guard, "_call_judge", new_callable=AsyncMock, return_value="accept"
        ):
            accepted = await guard.is_acceptable(text)
        assert accepted is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "text",
        [S3_SHELL, S5_RETRY, S6_PII],
        ids=["S3_shell", "S5_retry", "S6_pii"],
    )
    async def test_accepted_input_does_not_raise(self, text):
        """Intended path: an accepted input never raises at guard_input."""
        guard = _make_guardrail()
        with patch.object(
            guard, "_call_judge", new_callable=AsyncMock, return_value="accept"
        ):
            # raise_exception=True would short-circuit the workflow on reject.
            accepted = await guard.is_acceptable(text, raise_exception=True)
        assert accepted is True


# ─────────────────────────────────────────────────────────────────────
# Intended event path — which cascade stage decided each frame.
# ─────────────────────────────────────────────────────────────────────


class TestDecisionStages:
    def test_s3_and_s5_accept_at_precheck_without_llm(self):
        # Clean control-flow / tool frames are accepted deterministically — the
        # LLM never runs for them (cost + flake removed).
        assert precheck_input(S3_SHELL).verdict is PreCheckVerdict.ACCEPT
        assert precheck_input(S5_RETRY).verdict is PreCheckVerdict.ACCEPT

    def test_s6_defers_past_precheck(self):
        # S6's secret-shaped API key is opaque → deferred to the model/judge,
        # NOT rejected (PII handling is the Output rail's job).
        assert precheck_input(S6_PII).verdict is PreCheckVerdict.DEFER

    @pytest.mark.asyncio
    async def test_s3_s5_skip_the_judge(self):
        guard = _make_guardrail()
        with patch.object(
            guard, "_call_judge", new_callable=AsyncMock, return_value="reject"
        ) as judge:
            assert await guard.is_acceptable(S3_SHELL) is True
            assert await guard.is_acceptable(S5_RETRY) is True
        judge.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_s6_reaches_the_narrow_judge_when_no_classifier(self):
        guard = _make_guardrail(classifier=None)
        with patch.object(
            guard, "_call_judge", new_callable=AsyncMock, return_value="accept"
        ) as judge:
            assert await guard.is_acceptable(S6_PII) is True
        judge.assert_awaited_once()


# ─────────────────────────────────────────────────────────────────────
# With the ONNX classifier wired (smoke artifact): S6 is decided by the
# deterministic classifier (BENIGN) — the judge is skipped entirely.
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def smoke_classifier(tmp_path):
    pytest.importorskip("onnxruntime")
    pytest.importorskip("tokenizers")
    pytest.importorskip("onnx")
    pytest.importorskip("numpy")
    from scripts.train_injection_classifier import build_smoke_artifact
    from services.governance.injection_classifier import InjectionClassifier

    clf = InjectionClassifier.maybe_load(build_smoke_artifact(tmp_path / "smoke_clf"))
    assert clf is not None
    return clf


class TestClassifierWiredRevalidation:
    @pytest.mark.asyncio
    async def test_s6_accepted_by_classifier_without_judge(self, smoke_classifier):
        guard = _make_guardrail(classifier=smoke_classifier)
        with patch.object(
            guard, "_call_judge", new_callable=AsyncMock, return_value="reject"
        ) as judge:
            assert await guard.is_acceptable(S6_PII) is True
        judge.assert_not_awaited()
