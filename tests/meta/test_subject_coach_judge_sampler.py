"""L2 tests for meta/subject_coach_judge_sampler.py (design §7.3, ADR-0009).

The sampler is a post-hoc ``meta/`` job: EvalRecords ``target="subject_coach"``
→ deterministic task_id-hash sampling → the two coach judges (paired, same
turn) → verdict records ``target="coach_judges"``. Nothing runs inline.

Harness: REAL judges + REAL PromptService + one in-memory LLM stub + a
list-capturing recorder (TAP-2 — no mock pile-up). Failure paths first
(TAP-4): below-rate exclusion and flags-off no-op are asserted BEFORE any
inclusion path; an undecidable verdict is never recorded (AP-6).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from components.schemas import EvalRecord
from components.subject_coach_judges import GraderJudge, PedagogyJudge
from meta.subject_coach_judge_sampler import (
    run_coach_judge_sampling,
    should_sample,
)
from services.base_config import ModelProfile
from services.prompt_service import PromptService
from services.subject_coach_judge_runtime_config import (
    InMemorySubjectCoachJudgeConfigReader,
)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeLLMService:
    def __init__(self, response_content: str) -> None:
        self._response_content = response_content
        self.calls: list[tuple[ModelProfile, list[dict]]] = []

    async def invoke(self, profile, messages, **kwargs):
        self.calls.append((profile, messages))
        return _FakeResponse(self._response_content)


class ErrorLLMService:
    async def invoke(self, profile, messages, **kwargs):
        raise RuntimeError("simulated provider outage")


def _profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


_GRADER_JSON = json.dumps(
    {
        "faithfulness": 0.9,
        "correctness": 1.0,
        "justification": 0.6,
        "actionability": 0.8,
        "faithfulness_pass": True,
        "correctness_pass": True,
        "justification_pass": False,
        "actionability_pass": True,
        "rationale": "grounded",
    }
)

_PEDAGOGY_JSON = json.dumps(
    {
        "mistake_identification": 0.8,
        "mistake_location": 0.7,
        "actionability": 0.9,
        "coherence": 1.0,
        "productive_struggle": 0.6,
        "illusion_of_competence": 0.5,
        "mistake_identification_pass": True,
        "mistake_location_pass": True,
        "actionability_pass": True,
        "coherence_pass": True,
        "productive_struggle_pass": False,
        "illusion_of_competence_pass": False,
        "answer_leakage": False,
        "rationale": "probed",
    }
)


def _judges(
    *, grader_llm=None, pedagogy_llm=None
) -> tuple[GraderJudge, PedagogyJudge, FakeLLMService, FakeLLMService]:
    g_llm = grader_llm if grader_llm is not None else FakeLLMService(_GRADER_JSON)
    p_llm = pedagogy_llm if pedagogy_llm is not None else FakeLLMService(_PEDAGOGY_JSON)
    grader = GraderJudge(
        llm_service=g_llm,  # type: ignore[arg-type]
        prompt_service=PromptService(),
        judge_profile=_profile(),
    )
    pedagogy = PedagogyJudge(
        llm_service=p_llm,  # type: ignore[arg-type]
        prompt_service=PromptService(),
        judge_profile=_profile(),
    )
    return grader, pedagogy, g_llm, p_llm


def _record(
    task_id: str,
    *,
    target: str = "subject_coach",
    step: int = 1,
    task_input: str = "why is B right?",
    response: str = "What does each clause need to stand alone?",
) -> EvalRecord:
    return EvalRecord(
        timestamp=datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
        task_id=task_id,
        user_id="user-1",
        step=step,
        target=target,
        model="gpt-4o-mini",
        ai_input={"task_input": task_input},
        ai_response=response,
    )


def _reader(**kwargs) -> InMemorySubjectCoachJudgeConfigReader:
    defaults = {
        "coach_grader_judge_enabled": True,
        "coach_pedagogy_judge_enabled": True,
        "coach_judge_sample_rate": 1.0,
    }
    defaults.update(kwargs)
    return InMemorySubjectCoachJudgeConfigReader(**defaults)


class _CapturingRecorder:
    def __init__(self) -> None:
        self.records: list[dict] = []

    async def __call__(self, target, ai_input, ai_response, config, **kwargs):
        self.records.append(
            {
                "target": target,
                "ai_input": ai_input,
                "ai_response": ai_response,
                "config": config,
                **kwargs,
            }
        )


# ─────────────────────────────────────────────────────────────────────
# Failure paths FIRST
# ─────────────────────────────────────────────────────────────────────


class TestExclusionPaths:
    @pytest.mark.asyncio
    async def test_rate_zero_samples_nothing(self):
        grader, pedagogy, g_llm, p_llm = _judges()
        recorder = _CapturingRecorder()
        report = await run_coach_judge_sampling(
            [_record("t1"), _record("t2")],
            grader_judge=grader,
            pedagogy_judge=pedagogy,
            config_reader=_reader(coach_judge_sample_rate=0.0),
            recorder=recorder,
        )
        assert report.sampled_tasks == 0
        assert recorder.records == []
        assert g_llm.calls == [] and p_llm.calls == []

    @pytest.mark.asyncio
    async def test_both_flags_off_is_a_noop_even_at_full_rate(self):
        """Defaults-OFF discipline: flags own the on-switch, not the rate."""
        grader, pedagogy, g_llm, p_llm = _judges()
        recorder = _CapturingRecorder()
        report = await run_coach_judge_sampling(
            [_record("t1")],
            grader_judge=grader,
            pedagogy_judge=pedagogy,
            config_reader=_reader(
                coach_grader_judge_enabled=False,
                coach_pedagogy_judge_enabled=False,
            ),
            recorder=recorder,
        )
        assert report.judged == 0
        assert recorder.records == []
        assert g_llm.calls == [] and p_llm.calls == []

    @pytest.mark.asyncio
    async def test_non_coach_targets_are_excluded(self):
        grader, pedagogy, g_llm, p_llm = _judges()
        recorder = _CapturingRecorder()
        report = await run_coach_judge_sampling(
            [_record("t1", target="call_llm"), _record("t2", target="guardrail")],
            grader_judge=grader,
            pedagogy_judge=pedagogy,
            config_reader=_reader(),
            recorder=recorder,
        )
        assert report.coach_records == 0
        assert recorder.records == []

    @pytest.mark.asyncio
    async def test_undecidable_verdict_is_never_recorded(self):
        """AP-6: a provider outage yields NO coach_judges record for that
        judge — never a fabricated verdict. The healthy judge still records."""
        grader, pedagogy, _, p_llm = _judges(grader_llm=ErrorLLMService())
        recorder = _CapturingRecorder()
        report = await run_coach_judge_sampling(
            [_record("t1")],
            grader_judge=grader,
            pedagogy_judge=pedagogy,
            config_reader=_reader(),
            recorder=recorder,
        )
        assert report.undecidable == 1
        judges_recorded = [r["ai_input"]["judge"] for r in recorder.records]
        assert judges_recorded == ["pedagogy"]


# ─────────────────────────────────────────────────────────────────────
# Determinism (Check 7)
# ─────────────────────────────────────────────────────────────────────


class TestShouldSampleDeterminism:
    def test_stable_across_ten_repeats(self):
        for task_id in ("t1", "t2", "abc", "0d6f2f0a"):
            first = should_sample(task_id, 0.10)
            assert all(should_sample(task_id, 0.10) == first for _ in range(10))

    def test_rate_bounds(self):
        assert should_sample("anything", 1.0) is True
        assert should_sample("anything", 0.0) is False

    def test_monotonic_in_rate(self):
        """A task sampled at rate r stays sampled at every higher rate —
        raising the dial never drops previously-judged tasks."""
        for task_id in (f"task-{i}" for i in range(50)):
            if should_sample(task_id, 0.10):
                assert should_sample(task_id, 0.50)
                assert should_sample(task_id, 0.99)

    def test_rate_selects_a_strict_subset(self):
        ids = [f"task-{i}" for i in range(400)]
        low = {t for t in ids if should_sample(t, 0.10)}
        high = {t for t in ids if should_sample(t, 0.90)}
        assert low < high  # strict subset: both non-degenerate


# ─────────────────────────────────────────────────────────────────────
# Acceptance
# ─────────────────────────────────────────────────────────────────────


class TestPairedVerdictRecording:
    @pytest.mark.asyncio
    async def test_sampled_task_gets_paired_verdicts(self):
        grader, pedagogy, _, _ = _judges()
        recorder = _CapturingRecorder()
        report = await run_coach_judge_sampling(
            [_record("t1")],
            grader_judge=grader,
            pedagogy_judge=pedagogy,
            config_reader=_reader(),
            recorder=recorder,
        )
        assert report.sampled_tasks == 1
        assert report.judged == 2
        assert {r["ai_input"]["judge"] for r in recorder.records} == {
            "grader",
            "pedagogy",
        }
        for rec in recorder.records:
            assert rec["target"] == "coach_judges"
            configurable = rec["config"]["configurable"]
            assert configurable["task_id"] == "t1"
            assert configurable["user_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_pedagogy_verdict_payload_carries_leakage_flag(self):
        grader, pedagogy, _, _ = _judges()
        recorder = _CapturingRecorder()
        await run_coach_judge_sampling(
            [_record("t1")],
            grader_judge=grader,
            pedagogy_judge=pedagogy,
            config_reader=_reader(),
            recorder=recorder,
        )
        pedagogy_rec = next(
            r for r in recorder.records if r["ai_input"]["judge"] == "pedagogy"
        )
        assert pedagogy_rec["ai_response"]["answer_leakage"] is False

    @pytest.mark.asyncio
    async def test_single_flag_runs_only_that_judge(self):
        grader, pedagogy, g_llm, _ = _judges()
        recorder = _CapturingRecorder()
        await run_coach_judge_sampling(
            [_record("t1")],
            grader_judge=grader,
            pedagogy_judge=pedagogy,
            config_reader=_reader(coach_grader_judge_enabled=False),
            recorder=recorder,
        )
        assert g_llm.calls == []
        assert [r["ai_input"]["judge"] for r in recorder.records] == ["pedagogy"]

    @pytest.mark.asyncio
    async def test_one_turn_judged_per_task_the_last_step(self):
        """Multiple coach LLM calls in one task collapse to the final turn —
        paired judges see the same (latest) reply, not one per record."""
        grader, pedagogy, _, p_llm = _judges()
        recorder = _CapturingRecorder()
        report = await run_coach_judge_sampling(
            [
                _record("t1", step=1, response="early draft"),
                _record("t1", step=3, response="final coaching reply"),
            ],
            grader_judge=grader,
            pedagogy_judge=pedagogy,
            config_reader=_reader(),
            recorder=recorder,
        )
        assert report.sampled_tasks == 1
        assert report.judged == 2
        sent = " ".join(m["content"] for _, msgs in p_llm.calls for m in msgs)
        assert "final coaching reply" in sent
        assert "early draft" not in sent

    @pytest.mark.asyncio
    async def test_mode_defaults_to_pre_submit_and_reads_post_feedback(self):
        """Fail-closed mode: unknown → pre_submit (the stricter leakage
        rubric); an input carrying the post_feedback marker flips it."""
        grader, pedagogy, _, p_llm = _judges()
        recorder = _CapturingRecorder()
        await run_coach_judge_sampling(
            [
                _record("t1", task_input="why is B right?"),
                _record(
                    "t2",
                    task_input='coach_context: {"mode": "post_feedback"} — explain',
                ),
            ],
            grader_judge=grader,
            pedagogy_judge=pedagogy,
            config_reader=_reader(),
            recorder=recorder,
        )
        modes = {
            r["config"]["configurable"]["task_id"]: r["ai_input"]["mode"]
            for r in recorder.records
            if r["ai_input"]["judge"] == "pedagogy"
        }
        assert modes == {"t1": "pre_submit", "t2": "post_feedback"}

    @pytest.mark.asyncio
    async def test_learner_saying_post_feedback_does_not_flip_the_mode(self):
        """Spoof lock: only the coach_context JSON marker flips the rubric —
        a learner merely TYPING the word must stay on the stricter
        pre_submit leakage rubric (flipping would be fail-open)."""
        grader, pedagogy, _, _ = _judges()
        recorder = _CapturingRecorder()
        await run_coach_judge_sampling(
            [_record("t1", task_input="my teacher said post_feedback helps?")],
            grader_judge=grader,
            pedagogy_judge=pedagogy,
            config_reader=_reader(),
            recorder=recorder,
        )
        assert all(r["ai_input"]["mode"] == "pre_submit" for r in recorder.records)
