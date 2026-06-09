"""Offline shadow-validation harness for the Stage 4 A2 confirmation gate (§8.3).

Scaffolds the spec §10.2 shadow run **without a live model**: drive
:class:`~components.goal_judge.GoalJudge` over each registry anchor's recorded
trace and assert the parsed verdict matches the registry ``target_axes``.

Determinism boundary (AGENTS.md H1: no live LLM in CI). The verdicts here are
*recorded* (canned) — replaying them through :class:`MultiTraceFakeLLM` pins the
harness wiring (digest → prompt → parse → verdict) and the registry alignment,
**not** live-judge robustness. When G3 remediation + the G1/G2 batch land, swap
each ``ShadowTrace.recorded_verdict`` for the Langfuse-replayed verdict and these
same assertions become the real §10.2 behavioral gate.

What this pins today:
  - every §10.2 anchor renders, parses, and yields the registry-target verdict;
  - ``partial_fraction`` survives the parse/clamp path at the target value;
  - the negative control (GJ-001B) is NOT flagged corrupt-success;
  - GJ-019 stays A3 (`raw-error-propagation`), distinct from the A2 fails.
"""

from __future__ import annotations

import pytest

from components.goal_judge import GoalJudge
from services.prompt_service import PromptService
from tests.components.test_goal_judge import FakeLLMService, _profile
from tests.fixtures.goaljudge.shadow_traces import (
    SHADOW_TRACES,
    ShadowTrace,
)

# A2 member codes (spec §4) — the corrupt-success family the rubric targets.
_A2_CODES = {"fabricated-progress", "partial-counted-as-full", "subtask-dropped"}


class MultiTraceFakeLLM(FakeLLMService):
    """Replay the right recorded verdict per trace, keyed on its ``task_input``.

    One judge instance can shadow-run every anchor: each rendered prompt embeds
    the trace's ``task_input`` (``{{ task_input }}`` in the ``.j2``), so we route
    the call to the matching ``recorded_verdict``. Falls back to a hard error on
    an unrecognised prompt rather than silently replaying a stale verdict.
    """

    def __init__(self, traces: list[ShadowTrace]) -> None:
        super().__init__("")  # base records calls; we override the response
        self._by_task_input = {t.task_input: t.recorded_verdict_json for t in traces}

    async def invoke(self, profile, messages, **kwargs):
        self.calls.append((profile, messages))
        prompt = messages[0]["content"]
        for task_input, verdict_json in self._by_task_input.items():
            if task_input in prompt:
                from tests.components.test_goal_judge import _FakeResponse

                return _FakeResponse(verdict_json)
        raise AssertionError("no recorded verdict matched the rendered prompt")


def _shadow_judge() -> tuple[GoalJudge, MultiTraceFakeLLM]:
    llm = MultiTraceFakeLLM(SHADOW_TRACES)
    judge = GoalJudge(
        llm_service=llm,  # type: ignore[arg-type]
        prompt_service=PromptService(),
        judge_profile=_profile(),
    )
    return judge, llm


async def _run(judge: GoalJudge, trace: ShadowTrace):
    return await judge.evaluate(
        task_input=trace.task_input,
        final_answer=trace.final_answer,
        success_conditions=[],
        evidence=trace.evidence,
    )


class TestShadowValidationHarness:
    """Spec §10.2 shadow table, offline against recorded verdicts."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("trace", SHADOW_TRACES, ids=lambda t: t.registry_id)
    async def test_verdict_matches_registry_target(self, trace: ShadowTrace):
        """goal_met + partial_fraction match the registry target_axes (§10.2)."""
        judge, _ = _shadow_judge()
        verdict = await _run(judge, trace)
        assert verdict.goal_met is trace.expected_goal_met
        assert verdict.partial_fraction == pytest.approx(
            trace.expected_partial_fraction
        )

    @pytest.mark.asyncio
    async def test_negative_control_not_flagged_corrupt_success(self):
        """GJ-001B (correct-complete) must pass — the harness must not over-flag."""
        trace = next(t for t in SHADOW_TRACES if t.registry_id == "GJ-001B")
        judge, _ = _shadow_judge()
        verdict = await _run(judge, trace)
        assert verdict.goal_met is True
        assert verdict.partial_fraction == pytest.approx(1.0)
        assert trace.target_code not in _A2_CODES

    @pytest.mark.asyncio
    async def test_gj019_is_a3_not_a2(self):
        """GJ-019 fails like A2 (goal_met=false) but must stay A3, not corrupt-success."""
        trace = next(t for t in SHADOW_TRACES if t.registry_id == "GJ-019")
        judge, _ = _shadow_judge()
        verdict = await _run(judge, trace)
        assert verdict.goal_met is False
        assert trace.target_code == "raw-error-propagation"
        assert trace.target_code not in _A2_CODES

    @pytest.mark.asyncio
    async def test_fabricated_progress_anchor_has_no_tool_evidence(self):
        """GJ-008's digest must show the no-tools placeholder the rubric keys on."""
        from components.goal_judge import _summarize_evidence

        trace = next(t for t in SHADOW_TRACES if t.registry_id == "GJ-008")
        assert _summarize_evidence(trace.evidence) == "(no tool calls were made)"
        judge, _ = _shadow_judge()
        verdict = await _run(judge, trace)
        assert verdict.goal_met is False
        assert verdict.partial_fraction == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_all_a2_anchors_fail_goal_met(self):
        """Every A2-coded anchor in the table shadow-runs to goal_met=false."""
        judge, _ = _shadow_judge()
        a2_traces = [t for t in SHADOW_TRACES if t.target_code in _A2_CODES]
        assert a2_traces, "expected at least one A2 anchor in the shadow set"
        for trace in a2_traces:
            verdict = await _run(judge, trace)
            assert verdict.goal_met is False, f"{trace.registry_id} should fail"

    def test_unmatched_prompt_raises(self):
        """Guard: the replay stub must error (not replay stale) on an unknown prompt."""
        import asyncio

        llm = MultiTraceFakeLLM(SHADOW_TRACES)
        with pytest.raises(AssertionError, match="no recorded verdict matched"):
            asyncio.run(llm.invoke(_profile(), [{"role": "user", "content": "unknown task"}]))
