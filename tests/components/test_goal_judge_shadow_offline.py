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

import json

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
    """Replay the right verdict per trace, keyed on its ``task_input``.

    One judge instance can shadow-run every anchor: each rendered prompt embeds
    the trace's ``task_input`` (``{{ task_input }}`` in the ``.j2``), so we route
    the call to the matching verdict. Falls back to a hard error on an
    unrecognised prompt rather than silently replaying a stale verdict.

    **Verdict source — the §8.3 swap seam.** By default each trace replays its
    inline ``recorded_verdict`` (canned; pins wiring only). Pass ``replay`` — a
    ``registry_id -> verdict_json`` map from
    :func:`tests.fixtures.goaljudge.langfuse_replay.replay_source` — to override
    those anchors with **Langfuse-replayed** verdicts from a real batch re-run.
    Anchors absent from ``replay`` keep their recorded verdict, so a partial
    export still runs. When ``replay`` covers every anchor, the shadow run is
    the real §10.2 behavioral gate with no other code change.
    """

    def __init__(
        self,
        traces: list[ShadowTrace],
        replay: dict[str, str] | None = None,
    ) -> None:
        super().__init__("")  # base records calls; we override the response
        replay = replay or {}
        # Route by task_input (that is what lands in the prompt); pick the
        # replayed verdict when present, else the trace's recorded verdict.
        self._by_task_input = {
            t.task_input: replay.get(t.registry_id, t.recorded_verdict_json)
            for t in traces
        }

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
        # spec §10.2: partial_fraction ≈ target (±0.05) — Langfuse stores ⅔ as 0.6666…
        assert verdict.partial_fraction == pytest.approx(
            trace.expected_partial_fraction, abs=0.05
        )

    @pytest.mark.asyncio
    async def test_negative_control_not_flagged_corrupt_success(self):
        """GJ-001B (correct-complete) must pass — the harness must not over-flag."""
        trace = next(t for t in SHADOW_TRACES if t.registry_id == "GJ-001B")
        judge, _ = _shadow_judge()
        verdict = await _run(judge, trace)
        assert verdict.goal_met is True
        assert verdict.partial_fraction == pytest.approx(1.0, abs=0.05)
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
        assert verdict.partial_fraction == pytest.approx(0.0, abs=0.05)

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


class TestLangfuseReplaySwapSeam:
    """The §8.3 verdict-swap path (`langfuse_replay.py`) — load + route + parse.

    Proves the recorded→replayed switch is invisible to the §10.2 assertions:
    feeding the harness Langfuse-shaped verdicts (here, the committed *sample*
    export) drives the same judge to the same registry-target verdicts. When the
    real export replaces the sample post-G3 batch, these assertions become the
    behavioral gate with no further code change.
    """

    def test_trace_id_map_covers_every_shadow_anchor(self):
        """Every §10.2 anchor has a trace_id join (no silently-unmapped anchor)."""
        from tests.fixtures.goaljudge.langfuse_replay import TRACE_ID_TO_REGISTRY_ID

        mapped = set(TRACE_ID_TO_REGISTRY_ID.values())
        for trace in SHADOW_TRACES:
            assert trace.registry_id in mapped, f"{trace.registry_id} has no trace_id"

    def test_sample_export_loads_all_anchors(self):
        """The committed sample resolves to registry IDs via the trace_id map."""
        from tests.fixtures.goaljudge.langfuse_replay import (
            SAMPLE_EXPORT_PATH,
            load_replayed_verdicts,
        )

        verdicts = load_replayed_verdicts(SAMPLE_EXPORT_PATH)
        # Sample carries the 5 §10.2 anchors (both Form A and Form B rows).
        assert set(verdicts) == {"GJ-008", "GJ-010", "GJ-012", "GJ-001B", "GJ-019"}
        for v in verdicts.values():
            assert "goal_met" in v and "partial_fraction" in v

    @pytest.mark.asyncio
    async def test_replayed_verdicts_match_registry_targets(self):
        """Swap recorded→replayed: same judge, same registry-target verdicts (§10.2)."""
        from tests.fixtures.goaljudge.langfuse_replay import (
            SAMPLE_EXPORT_PATH,
            replay_source,
        )

        replay = replay_source(SAMPLE_EXPORT_PATH)
        await _assert_replay_matches_registry(replay)

    @pytest.mark.asyncio
    async def test_live_export_matches_registry_when_env_set(self):
        """§8.3 behavioral gate: real batch export via GOALJUDGE_LANGFUSE_EXPORT."""
        import os

        from tests.fixtures.goaljudge.langfuse_replay import EXPORT_ENV_VAR, replay_source

        if not os.environ.get(EXPORT_ENV_VAR):
            pytest.skip(f"{EXPORT_ENV_VAR} not set — run batch + export first")
        replay = replay_source()
        if not replay:
            pytest.skip(f"{EXPORT_ENV_VAR} resolved to an empty replay map")
        await _assert_replay_matches_registry(replay)

    def test_no_export_falls_back_to_empty_source(self, monkeypatch):
        """Resolution order: no path + no env var → {} (harness keeps recorded)."""
        from tests.fixtures.goaljudge import langfuse_replay

        monkeypatch.delenv(langfuse_replay.EXPORT_ENV_VAR, raising=False)
        assert langfuse_replay.replay_source() == {}

    def test_env_var_resolves_export(self, monkeypatch):
        """The env var is honoured when no explicit path is passed."""
        from tests.fixtures.goaljudge import langfuse_replay

        monkeypatch.setenv(
            langfuse_replay.EXPORT_ENV_VAR, str(langfuse_replay.SAMPLE_EXPORT_PATH)
        )
        src = langfuse_replay.replay_source()
        assert set(src) == {"GJ-008", "GJ-010", "GJ-012", "GJ-001B", "GJ-019"}

    def test_unknown_trace_ids_are_skipped(self, tmp_path):
        """An export carrying the full batch ignores non-anchor rows."""
        from tests.fixtures.goaljudge.langfuse_replay import load_replayed_verdicts

        export = tmp_path / "full_batch.json"
        export.write_text(
            json.dumps(
                [
                    {"trace_id": "deadbeef-not-an-anchor", "verdict": {"goal_met": True}},
                    {
                        "trace_id": "cbfe84539b675824a1eb08b331204b8d",
                        "verdict": {"goal_met": False, "partial_fraction": 0.0},
                    },
                ]
            )
        )
        verdicts = load_replayed_verdicts(export)
        assert set(verdicts) == {"GJ-008"}

    def test_malformed_row_without_trace_id_raises(self, tmp_path):
        """A row missing trace_id is a hard error (can't silently drop an anchor)."""
        from tests.fixtures.goaljudge.langfuse_replay import (
            ReplayExportError,
            load_replayed_verdicts,
        )

        export = tmp_path / "bad.json"
        export.write_text(json.dumps([{"verdict": {"goal_met": False}}]))
        with pytest.raises(ReplayExportError, match="needs a trace_id"):
            load_replayed_verdicts(export)

    def test_non_verdict_object_raises(self, tmp_path):
        """A mapped row whose payload isn't a verdict is rejected, not replayed."""
        from tests.fixtures.goaljudge.langfuse_replay import (
            ReplayExportError,
            load_replayed_verdicts,
        )

        export = tmp_path / "notaverdict.json"
        export.write_text(
            json.dumps(
                [{"trace_id": "cbfe84539b675824a1eb08b331204b8d", "verdict": {"foo": 1}}]
            )
        )
        with pytest.raises(ReplayExportError, match="not a verdict"):
            load_replayed_verdicts(export)


async def _assert_replay_matches_registry(replay: dict[str, str]) -> None:
    """Shared §10.2 assertions for sample or live Langfuse replay exports."""
    llm = MultiTraceFakeLLM(SHADOW_TRACES, replay=replay)
    judge = GoalJudge(
        llm_service=llm,  # type: ignore[arg-type]
        prompt_service=PromptService(),
        judge_profile=_profile(),
    )
    for trace in SHADOW_TRACES:
        if trace.registry_id not in replay:
            continue
        verdict = await _run(judge, trace)
        assert verdict.goal_met is trace.expected_goal_met, trace.registry_id
        # spec §10.2: ±0.05 tolerance on partial_fraction
        assert verdict.partial_fraction == pytest.approx(
            trace.expected_partial_fraction, abs=0.05
        ), trace.registry_id
