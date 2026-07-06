"""L2 (mock-provider) tests for components/subject_coach_judges.py (FR-14/15/16/18).

Mirrors the ``test_goal_judge.py`` harness: a single in-memory LLM stub + the
REAL ``PromptService`` + the REAL redact-all ``GuardRailValidator`` (TAP-2 —
no mock pile-up). Structural assertions only, never exact LLM prose (TAP-3).

The coach judges' failure contract DIFFERS from GoalJudge's: GoalJudge raises
so its caller falls back to the deterministic heuristic; the coach judges have
no fallback consumer — an undecidable turn yields ``None`` (AP-6: never a
fabricated verdict, never a defaulted ``answer_leakage=False``). Failure paths
first (TAP-4).
"""

from __future__ import annotations

import json

import pytest

from components.schemas import GraderVerdict, PedagogyVerdict
from components.subject_coach_judges import GraderJudge, PedagogyJudge
from services.base_config import ModelProfile
from services.governance.guardrail_validator import (
    FailAction,
    GuardRailValidator,
    api_key_rules,
    pii_rules,
)
from services.prompt_service import PromptService


def _redact_all_validator() -> GuardRailValidator:
    return GuardRailValidator(
        [
            rule.model_copy(update={"fail_action": FailAction.REDACT})
            for rule in (pii_rules() + api_key_rules())
        ]
    )


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeLLMService:
    """Replays a canned response, records every call (record/replay stub)."""

    def __init__(self, response_content: str) -> None:
        self._response_content = response_content
        self.calls: list[tuple[ModelProfile, list[dict]]] = []

    async def invoke(self, profile, messages, **kwargs):
        self.calls.append((profile, messages))
        return _FakeResponse(self._response_content)


class ErrorLLMService:
    """Provider-failure stub: every invoke raises (Pattern 6 ErrorMockProvider)."""

    async def invoke(self, profile, messages, **kwargs):
        raise RuntimeError("simulated provider outage")


class BlockListLLMService:
    """Reasoning-model stub: ``.content`` is a DeepSeek-V4-style block list.

    The answer JSON lives in ``text`` blocks; ``thinking`` blocks are scratchpad
    that must be dropped. ``str(content)`` would repr the whole list and break
    the parser — the judge must normalize via ``response_text`` (services H2
    boundary), exactly like every other call site.
    """

    def __init__(self, answer_json: str) -> None:
        self._answer_json = answer_json
        self.calls: list[tuple[ModelProfile, list[dict]]] = []

    async def invoke(self, profile, messages, **kwargs):
        self.calls.append((profile, messages))
        content = [
            "",
            {"type": "thinking", "thinking": "The learner has not answered yet."},
            {"type": "thinking", "thinking": " Consider the rubric."},
            {"type": "text", "text": self._answer_json},
        ]
        return _FakeResponse(content)  # type: ignore[arg-type]


def _profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _grader_response(**overrides: object) -> str:
    payload: dict[str, object] = {
        "faithfulness": 0.9,
        "correctness": 1.0,
        "justification": 0.6,
        "actionability": 0.8,
        "faithfulness_pass": True,
        "correctness_pass": True,
        "justification_pass": False,
        "actionability_pass": True,
        "rationale": "grounded; the why is thin",
    }
    payload.update(overrides)
    return json.dumps(payload)


def _pedagogy_response(**overrides: object) -> str:
    payload: dict[str, object] = {
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
        "rationale": "probed without naming the fix",
    }
    payload.update(overrides)
    return json.dumps(payload)


def _grader(response: str, *, redactor: GuardRailValidator | None = None):
    llm = FakeLLMService(response)
    judge = GraderJudge(
        llm_service=llm,  # type: ignore[arg-type]
        prompt_service=PromptService(),
        judge_profile=_profile(),
        redactor=redactor,
    )
    return judge, llm


def _pedagogy(response: str, *, redactor: GuardRailValidator | None = None):
    llm = FakeLLMService(response)
    judge = PedagogyJudge(
        llm_service=llm,  # type: ignore[arg-type]
        prompt_service=PromptService(),
        judge_profile=_profile(),
        redactor=redactor,
    )
    return judge, llm


async def _grade(judge: GraderJudge) -> GraderVerdict | None:
    return await judge.evaluate(
        question="Which sentence uses the semicolon correctly?",
        coach_content="A semicolon joins two independent clauses.",
    )


async def _judge_turn(judge: PedagogyJudge, *, mode: str = "pre_submit"):
    return await judge.evaluate(
        learner_utterance="why is B right?",
        coach_reply="What does each clause on either side need to stand alone?",
        mode=mode,
        question="Which sentence uses the semicolon correctly?",
    )


# ─────────────────────────────────────────────────────────────────────
# Failure paths FIRST (TAP-4): undecidable → None, never fabricated.
# ─────────────────────────────────────────────────────────────────────


class TestProviderErrorPaths:
    @pytest.mark.asyncio
    async def test_grader_provider_error_yields_none(self):
        judge = GraderJudge(
            llm_service=ErrorLLMService(),  # type: ignore[arg-type]
            prompt_service=PromptService(),
            judge_profile=_profile(),
        )
        assert await _grade(judge) is None

    @pytest.mark.asyncio
    async def test_pedagogy_provider_error_yields_none(self):
        judge = PedagogyJudge(
            llm_service=ErrorLLMService(),  # type: ignore[arg-type]
            prompt_service=PromptService(),
            judge_profile=_profile(),
        )
        assert await _judge_turn(judge) is None


class TestMalformedVerdictPaths:
    @pytest.mark.asyncio
    async def test_grader_prose_response_yields_none(self):
        judge, _ = _grader("The hint was decent, maybe a 7/10 overall.")
        assert await _grade(judge) is None

    @pytest.mark.asyncio
    async def test_pedagogy_missing_answer_leakage_yields_none(self):
        """THE contract test: a verdict without the leak flag is undecidable —
        it must never be repaired into ``answer_leakage=False``."""
        raw = json.loads(_pedagogy_response())
        del raw["answer_leakage"]
        judge, _ = _pedagogy(json.dumps(raw))
        assert await _judge_turn(judge) is None

    @pytest.mark.asyncio
    async def test_grader_missing_binary_companion_yields_none(self):
        """G8: the binary is asserted by the judge, NEVER derived from the
        float post-hoc — a missing companion cannot be repaired."""
        raw = json.loads(_grader_response())
        del raw["justification_pass"]
        judge, _ = _grader(json.dumps(raw))
        assert await _grade(judge) is None

    @pytest.mark.asyncio
    async def test_pedagogy_missing_float_axis_yields_none(self):
        raw = json.loads(_pedagogy_response())
        del raw["productive_struggle"]
        judge, _ = _pedagogy(json.dumps(raw))
        assert await _judge_turn(judge) is None


class TestVerdictRepairPaths:
    @pytest.mark.asyncio
    async def test_grader_percentage_floats_rescaled(self):
        """A 0-100 float from the model is repaired into the 0..1 contract
        (the GoalJudge ``criteria_met`` clamp precedent); binaries untouched."""
        judge, _ = _grader(_grader_response(faithfulness=90, justification=60.0))
        verdict = await _grade(judge)
        assert verdict is not None
        assert verdict.faithfulness == pytest.approx(0.9)
        assert verdict.justification == pytest.approx(0.6)
        assert verdict.justification_pass is False

    @pytest.mark.asyncio
    async def test_grader_slight_overshoot_clamps_not_rescales(self):
        """A 0..1-scale verdict that slightly overshoots (1.02, 1.5) is a
        clamp case, not a percentage reply: rescaling would silently invert
        a near-perfect score into a near-zero one (1.5 → 0.015)."""
        judge, _ = _grader(_grader_response(faithfulness=1.02, justification=1.5))
        verdict = await _grade(judge)
        assert verdict is not None
        assert verdict.faithfulness == pytest.approx(1.0)
        assert verdict.justification == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_pedagogy_fenced_json_parsed(self):
        judge, _ = _pedagogy(
            "Here is my verdict:\n```json\n" + _pedagogy_response() + "\n```"
        )
        verdict = await _judge_turn(judge)
        assert verdict is not None
        assert verdict.answer_leakage is False


# ─────────────────────────────────────────────────────────────────────
# FR-18 — every content line passes the redactor before the prompt.
# ─────────────────────────────────────────────────────────────────────


class TestRedaction:
    @pytest.mark.asyncio
    async def test_grader_redacts_content_before_prompt(self):
        judge, llm = _grader(_grader_response(), redactor=_redact_all_validator())
        await judge.evaluate(
            question="Contact me at jane.doe@example.com about the comma.",
            coach_content="My key is sk-abcdef1234567890abcdef1234567890abcd.",
        )
        sent = " ".join(m["content"] for _, msgs in llm.calls for m in msgs)
        assert "sk-abcdef1234567890abcdef1234567890abcd" not in sent
        assert "jane.doe@example.com" not in sent

    @pytest.mark.asyncio
    async def test_pedagogy_redacts_content_before_prompt(self):
        judge, llm = _pedagogy(_pedagogy_response(), redactor=_redact_all_validator())
        await judge.evaluate(
            learner_utterance="my email is jane.doe@example.com, why is B right?",
            coach_reply="Let's look at the clause boundary.",
            mode="pre_submit",
            question="Which sentence uses the semicolon correctly?",
        )
        sent = " ".join(m["content"] for _, msgs in llm.calls for m in msgs)
        assert "jane.doe@example.com" not in sent


# ─────────────────────────────────────────────────────────────────────
# Acceptance — after the rejections.
# ─────────────────────────────────────────────────────────────────────


class TestCleanVerdicts:
    @pytest.mark.asyncio
    async def test_grader_clean_verdict_parsed(self):
        judge, llm = _grader(_grader_response())
        verdict = await _grade(judge)
        assert isinstance(verdict, GraderVerdict)
        assert verdict.correctness_pass is True
        assert len(llm.calls) == 1

    @pytest.mark.asyncio
    async def test_pedagogy_leaking_turn_carries_flag(self):
        judge, _ = _pedagogy(_pedagogy_response(answer_leakage=True))
        verdict = await _judge_turn(judge)
        assert isinstance(verdict, PedagogyVerdict)
        assert verdict.answer_leakage is True

    @pytest.mark.asyncio
    async def test_pedagogy_prompt_renders_mode(self):
        """Our own template (deterministic artifact, not LLM output): the
        rendered rubric must carry the mode so leakage is judged mode-aware."""
        judge, llm = _pedagogy(_pedagogy_response())
        await _judge_turn(judge, mode="post_feedback")
        sent = " ".join(m["content"] for _, msgs in llm.calls for m in msgs)
        assert "post_feedback" in sent

    @pytest.mark.asyncio
    async def test_judges_use_distinct_prompts(self):
        assert GraderJudge.PROMPT_NAME != PedagogyJudge.PROMPT_NAME


class TestFR17GeneralGoalJudgeUnchanged:
    """FR-17: the general GoalJudge is REUSED UNCHANGED — the coach judges
    are siblings, never modifications. Drift locks, not behavior tests
    (behavior is pinned by test_goal_judge.py)."""

    def test_goal_judge_module_has_no_coach_coupling(self):
        import inspect

        import components.goal_judge as goal_judge_module

        source = inspect.getsource(goal_judge_module)
        assert "subject_coach" not in source
        assert "PedagogyVerdict" not in source
        assert "GraderVerdict" not in source

    def test_goal_verdict_gained_no_coach_fields(self):
        from components.schemas import GoalVerdict

        assert set(GoalVerdict.model_fields) == {
            "goal_met",
            "criteria_met",
            "per_criterion",
            "criteria_met_derived",
            "rationale",
            "graceful_failure",
            "partial_fraction",
            "failure_mode",
            "verifier_source",
        }

    def test_coach_judges_do_not_subclass_goal_judge(self):
        from components.goal_judge import GoalJudge

        assert not issubclass(GraderJudge, GoalJudge)
        assert not issubclass(PedagogyJudge, GoalJudge)


class TestReasoningModelBlockListContent:
    """A reasoning model (DeepSeek V4) returns ``.content`` as a block list; the
    answer JSON is in the ``text`` block. The judge must normalize it, not choke
    on ``str(list)`` (regression: gpt-4o passed as str, DeepSeek-pro did not)."""

    @pytest.mark.asyncio
    async def test_pedagogy_parses_json_from_text_block(self):
        llm = BlockListLLMService(_pedagogy_response(answer_leakage=True))
        judge = PedagogyJudge(
            llm_service=llm,  # type: ignore[arg-type]
            prompt_service=PromptService(),
            judge_profile=_profile(),
        )
        verdict = await _judge_turn(judge)
        assert verdict is not None
        assert verdict.answer_leakage is True

    @pytest.mark.asyncio
    async def test_grader_parses_json_from_text_block(self):
        llm = BlockListLLMService(_grader_response(correctness_pass=False))
        judge = GraderJudge(
            llm_service=llm,  # type: ignore[arg-type]
            prompt_service=PromptService(),
            judge_profile=_profile(),
        )
        verdict = await _grade(judge)
        assert verdict is not None
        assert verdict.correctness_pass is False


# ─────────────────────────────────────────────────────────────────────
# Task 3.6a — leak_channel schema field (Stage A). Failure-mode FIRST
# (TAP-4): the soft-coerce (3.6a-3) is the case that would otherwise VOID
# a correct answer_leakage=true on the 5/5 acceptance run (ADR-0017 F1).
# ─────────────────────────────────────────────────────────────────────


def _render_pedagogy_prompt() -> str:
    """The real rubric prose, rendered — the drift-sensor's source of truth."""
    return PromptService().render_prompt(
        "subject_coach_pedagogy_judge",
        mode="pre_submit",
        question="Which sentence uses the semicolon correctly?",
        learner_utterance="why is B right?",
        coach_reply="What does each clause need to stand alone?",
    )


class TestLeakChannelSchema:
    """FR-8 + FR-7 + FR-12: leak_channel is optional/best-effort telemetry;
    answer_leakage stays required; unknown channels coerce (never raise)."""

    def test_leak_channel_coerces_unknown_to_none(self):
        """ADR-0017 F1 (the substantive fix, failure-mode FIRST): a cosmetic
        near-miss channel value coerces to None and the verdict is KEPT — it
        must NEVER raise a ValidationError that voids the whole verdict (the
        judge is fail-closed: a ValidationError → None, subject_coach_judges.py
        :106). Without this, a channel typo would erase a correct leak catch."""
        raw = json.loads(_pedagogy_response(answer_leakage=True))
        for near_miss in ("socratic_clothing", "rule naming", "RULE-NAMING", ""):
            raw["leak_channel"] = near_miss
            verdict = PedagogyVerdict.model_validate(raw)
            assert verdict.answer_leakage is True  # verdict survives
            assert verdict.leak_channel is None  # unknown → None

    def test_leak_channel_optional_defaults_none(self):
        """FR-8: a verdict WITHOUT the field validates (backward-compatible;
        every prior baseline verdict lacks it)."""
        raw = json.loads(_pedagogy_response())
        raw.pop("leak_channel", None)
        verdict = PedagogyVerdict.model_validate(raw)
        assert verdict.leak_channel is None

    def test_pedagogy_verdict_accepts_leak_channel(self):
        """FR-8: each of the 5 valid channel values round-trips."""
        for channel in (
            "rule-naming",
            "socratic-clothing",
            "strong-implication",
            "criterion-then-verdict",
            "cross-question",
        ):
            raw = json.loads(_pedagogy_response(answer_leakage=True))
            raw["leak_channel"] = channel
            verdict = PedagogyVerdict.model_validate(raw)
            assert verdict.leak_channel == channel

    def test_pedagogy_still_requires_answer_leakage(self):
        """FR-7: the required-field contract is UNCHANGED by the new optional
        field — a verdict missing answer_leakage is still a ValidationError,
        never repaired to False (guard against accidental relaxation)."""
        from pydantic import ValidationError

        raw = json.loads(_pedagogy_response())
        del raw["answer_leakage"]
        with pytest.raises(ValidationError):
            PedagogyVerdict.model_validate(raw)

    def test_leak_channel_values_mirrored_in_pedagogy_prompt(self):
        """FR-12 (ADR-0017 F2): each LeakChannel enum value appears verbatim in
        the pedagogy .j2 — a code↔prose drift sensor, turning FR-11's
        review-time discipline into a partial gate."""
        from components.schemas import LeakChannel

        prompt = _render_pedagogy_prompt()
        channels = LeakChannel.__args__  # the Literal's 5 values
        assert len(channels) == 5
        for channel in channels:
            assert channel in prompt, f"{channel!r} missing from pedagogy rubric"


class TestGraderRefusalAware:
    """FR-9 (3.6c): the grader rubric gains a refusal-aware criterion — a
    decline sentence carries no axis credit; grade the content after it."""

    def test_grader_prompt_states_refusal_carries_no_credit(self):
        """The refusal-aware rule is present in the rendered prose (a refusal
        sentence gets no axis credit; grade the payload after it)."""
        prompt = PromptService().render_prompt(
            "subject_coach_grader_judge",
            question="Which sentence uses the semicolon correctly?",
            coach_content="A semicolon joins two independent clauses.",
            evidence=[],
        )
        lowered = prompt.lower()
        assert "refusal" in lowered
        assert "no credit" in lowered

    @pytest.mark.asyncio
    async def test_grader_scores_refuse_then_thin_content_low(self):
        """Stub: a judge that returns a low-on-content-axes verdict for a
        refuse-then-thin-content turn round-trips as low (the prose asks the
        real judge for this; here we assert the schema carries the signal)."""
        judge, _ = _grader(
            _grader_response(
                faithfulness=0.2,
                justification=0.1,
                actionability=0.2,
                faithfulness_pass=False,
                justification_pass=False,
                actionability_pass=False,
            )
        )
        verdict = await judge.evaluate(
            question="Which sentence uses the semicolon correctly?",
            coach_content="I can't just give you the answer — keep trying!",
        )
        assert verdict is not None
        assert verdict.justification_pass is False
        assert verdict.actionability_pass is False


class TestRubricHeadersRevised:
    """FR-10: both rubric headers flip PROVISIONAL → REVISED."""

    def test_rubric_headers_marked_revised(self):
        from pathlib import Path

        prompts_dir = Path(__file__).resolve().parents[2] / "prompts"
        for name in (
            "subject_coach_pedagogy_judge.j2",
            "subject_coach_grader_judge.j2",
        ):
            text = (prompts_dir / name).read_text(encoding="utf-8")
            assert "REVISED" in text, f"{name} not marked REVISED"
            assert "PROVISIONAL" not in text, f"{name} still PROVISIONAL"


class TestPedagogyCleanCarveOut:
    """Specificity-spec FR-3/4/5/6/7 (ADR-0018): the CLEAN carve-out that stops
    the judge reading mechanism-teaching / open probes as item-collapse. All
    assertions are on the rendered rubric prose (L1 grep, drift-sensor style)."""

    def test_rubric_version_bumped_to_v2(self):
        """FR-7: the pedagogy rubric carries `coach_rubric_v2_specificity`."""
        assert "coach_rubric_v2_specificity" in _render_pedagogy_prompt()

    def test_clean_test_is_first_class_and_before_channels(self):
        """FR-3: a first-class CLEAN test SECTION appears BESIDE the decisive test
        — i.e. BEFORE the five-channels SECTION HEADING, not as a tail after it.
        Anchored on the `## ...` headings (not the intro's forward-reference to
        the channels) so the assertion reflects section order, not a prose mention."""
        lowered = _render_pedagogy_prompt().lower()
        clean_heading = lowered.find("## the clean test")
        channels_heading = lowered.find("## the five indirect channels")
        assert clean_heading != -1, "no first-class '## The CLEAN test' section"
        assert channels_heading != -1, "five-channels section heading not found"
        assert clean_heading < channels_heading, (
            "the CLEAN test section must come BEFORE the five-channels section "
            "(promoted from a tail to first-class — FR-3)"
        )

    def test_count_surviving_options_step_present(self):
        """FR-4: the rubric instructs the judge to enumerate which options are
        eliminated vs live and flag only when ≤1 remains."""
        lowered = _render_pedagogy_prompt().lower()
        # enumerate/count the surviving options
        assert "surviving options" in lowered or "options remain live" in lowered
        assert "count" in lowered or "enumerate" in lowered or "list which" in lowered

    def test_names_the_two_over_reads_as_non_leaks(self):
        """FR-5: (a) an open probe is not socratic-clothing unless only one option
        survives the question itself; (b) naming a rule is not rule-naming leakage
        unless one option uniquely satisfies it on this item."""
        lowered = _render_pedagogy_prompt().lower()
        # (a) open-probe carve-out
        assert "open probe" in lowered
        assert "unless only one" in lowered or "unless one option survives" in lowered
        # (b) rule-naming carve-out
        assert "uniquely" in lowered  # "one option uniquely satisfies it"

    def test_no_numeric_threshold_in_template(self):
        """FR-6: the CLEAN test / option-count is PROSE, not a numeric threshold
        baked into the .j2 (config split — thresholds live in code). The JSON
        OUTPUT block legitimately shows `0.0` float-axis defaults; that is the
        schema example, not a threshold — so we scan the RUBRIC prose only (the
        text before the `# Output` section) for comparison-threshold tokens."""
        import re
        from pathlib import Path

        text = (
            Path(__file__).resolve().parents[2]
            / "prompts"
            / "subject_coach_pedagogy_judge.j2"
        ).read_text(encoding="utf-8")
        rubric_prose = text.split("# Output")[0]
        # no comparison-threshold tokens like "flag if ≥ 0.7" / ">= 0.5" in the prose
        assert "≥ 0." not in rubric_prose and ">= 0." not in rubric_prose
        assert not re.search(r"(?:score|flag|threshold)\D{0,20}0\.\d+", rubric_prose), (
            "a numeric decision threshold leaked into the rubric prose"
        )
