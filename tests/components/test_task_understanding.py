"""L1/L2 tests for components/task_understanding.py (task_understanding plan Phase 2).

Structure mirrors tests/components/test_goal_judge.py: one in-memory LLM stub
plus the REAL PromptService (TAP-2), structural assertions only on generated
content (TAP-3), and every rejection path tested before its acceptance path
(TAP-4).

Contract under test (plan §4.2): the generator RAISES on any failure —
unparseable JSON, LLM error, validation-gate rejection. It never falls back
itself (no peer component imports); the orchestration thin-wrapper owns the
deterministic fallback.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from components.schemas import TaskUnderstanding
from components.task_understanding import (
    GENERIC_TAIL_CONDITION,
    TaskUnderstandingGenerator,
    TaskUnderstandingValidationError,
    validate_conditions,
)
from services.base_config import ModelProfile
from services.prompt_service import PromptService

# ─────────────────────────────────────────────────────────────────────
# Fakes (Pattern 6 — single mock provider)
# ─────────────────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeLLMService:
    """In-memory LLM stub: replays canned response(s), records each call.

    ``response_content`` may be a single string (the original single-shot
    behavior) or a list of strings replayed one-per-``invoke`` so the retry
    path can be exercised (attempt 0 → response[0], attempt 1 → response[1]).
    Once the list is exhausted the last response repeats.
    """

    def __init__(
        self,
        response_content: str | list[str],
        *,
        raises: Exception | None = None,
    ) -> None:
        self._responses = (
            [response_content]
            if isinstance(response_content, str)
            else list(response_content)
        )
        self._raises = raises
        self.calls: list[tuple[ModelProfile, list[dict]]] = []

    async def invoke(self, profile, messages, **kwargs):
        self.calls.append((profile, messages))
        if self._raises is not None:
            raise self._raises
        index = min(len(self.calls) - 1, len(self._responses) - 1)
        return _FakeResponse(self._responses[index])


def _profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _generator(
    response_content: str | list[str], *, raises: Exception | None = None
) -> tuple[TaskUnderstandingGenerator, FakeLLMService]:
    llm = FakeLLMService(response_content, raises=raises)
    generator = TaskUnderstandingGenerator(
        llm_service=llm,  # type: ignore[arg-type]
        prompt_service=PromptService(),
        profile=_profile(),
    )
    return generator, llm


_TASK = (
    "Create a file /workspace/f3.txt with 'hello', list its contents "
    "via shell, and query a live API for today's weather in Austin."
)


def _payload(**overrides) -> str:
    data = {
        "restated_intent": "Create f3.txt, verify its contents, and fetch Austin weather.",
        "success_conditions": [
            "The file /workspace/f3.txt exists and contains 'hello'.",
            "The file contents were listed via a shell command.",
            "Today's weather in Austin was retrieved from a live API.",
        ],
        "confidence": 0.85,
    }
    data.update(overrides)
    return json.dumps(data)


# ─────────────────────────────────────────────────────────────────────
# L1 — schema validation (rejections first)
# ─────────────────────────────────────────────────────────────────────


class TestTaskUnderstandingSchema:
    def test_missing_restated_intent_rejected(self):
        with pytest.raises(ValidationError):
            TaskUnderstanding.model_validate(
                {"success_conditions": ["a", "b"], "confidence": 0.5}
            )

    def test_conditions_not_a_list_rejected(self):
        with pytest.raises(ValidationError):
            TaskUnderstanding.model_validate(
                {
                    "restated_intent": "x",
                    "success_conditions": "not a list",
                    "confidence": 0.5,
                }
            )

    def test_confidence_out_of_range_rejected(self):
        for bad in (-0.1, 1.5):
            with pytest.raises(ValidationError):
                TaskUnderstanding.model_validate(
                    {
                        "restated_intent": "x",
                        "success_conditions": ["a", "b"],
                        "confidence": bad,
                    }
                )

    def test_unknown_source_rejected(self):
        with pytest.raises(ValidationError):
            TaskUnderstanding.model_validate(
                {
                    "restated_intent": "x",
                    "success_conditions": ["a", "b"],
                    "confidence": 0.5,
                    "source": "oracle",
                }
            )

    def test_valid_payload_accepted_with_provenance_defaults(self):
        artifact = TaskUnderstanding.model_validate(
            {
                "restated_intent": "x",
                "success_conditions": ["a", "b"],
            }
        )
        assert artifact.source == "deterministic"
        assert artifact.confidence == 0.0
        assert artifact.model == ""


# ─────────────────────────────────────────────────────────────────────
# L1 — validation gates (pure functions; each rejection before acceptance)
# ─────────────────────────────────────────────────────────────────────


class TestValidationGates:
    def test_count_gate_rejects_zero_and_eight(self):
        # min lowered 2->1 (the generic tail moved to judge-time, so the
        # plan-time list no longer needs padding to reach 2). Zero and 8 still
        # fail the count gate; a single grounded condition is now valid.
        for conditions in ([], [f"task condition {i}" for i in range(8)]):
            issues = validate_conditions(conditions, task_input="task condition text")
            assert any("count" in issue for issue in issues)

    def test_count_gate_accepts_single_condition(self):
        # One well-grounded condition is valid now (was rejected when min==2).
        issues = validate_conditions(
            ["The task condition is satisfied"], task_input="task condition text"
        )
        assert not any("count" in issue for issue in issues)

    def test_length_gate_rejects_201_char_item(self):
        long_item = "task " + "x" * 200
        issues = validate_conditions(["task is done", long_item], task_input="the task")
        assert any("length" in issue for issue in issues)

    def test_grounding_gate_rejects_offtopic_condition(self):
        issues = validate_conditions(
            ["The weather report covers Austin", "Quantum flux capacitors aligned"],
            task_input="Fetch today's weather report for Austin",
        )
        assert any("grounding" in issue for issue in issues)

    def test_dedupe_gate_rejects_normalized_duplicates(self):
        issues = validate_conditions(
            ["The weather is fetched", "  the WEATHER is fetched  "],
            task_input="fetch the weather",
        )
        assert any("duplicate" in issue for issue in issues)

    def test_valid_conditions_pass_all_gates(self):
        issues = validate_conditions(
            [
                "The file /workspace/f3.txt exists with 'hello'.",
                "Austin weather was retrieved from a live API.",
            ],
            task_input=_TASK,
        )
        assert issues == []

    def test_user_edited_skips_grounding_but_keeps_bounds(self):
        # Human is the authority: an off-vocabulary edit is fine…
        issues = validate_conditions(
            ["Quantum flux capacitors aligned", "Another human condition"],
            task_input="Fetch the weather",
            source="user_edited",
        )
        assert issues == []
        # …but count/length bounds still apply (0 and >7 still fail; min is 1).
        issues = validate_conditions(
            [], task_input="Fetch the weather", source="user_edited"
        )
        assert any("count" in issue for issue in issues)


# ─────────────────────────────────────────────────────────────────────
# L2 — generator contract (mock provider; failures first)
# ─────────────────────────────────────────────────────────────────────


class TestTaskUnderstandingGenerator:
    @pytest.mark.asyncio
    async def test_malformed_json_raises(self):
        generator, _ = _generator("this is not json at all")
        with pytest.raises(Exception):
            await generator.generate(task_input=_TASK)

    @pytest.mark.asyncio
    async def test_llm_exception_propagates(self):
        generator, _ = _generator("", raises=RuntimeError("provider down"))
        with pytest.raises(RuntimeError):
            await generator.generate(task_input=_TASK)

    @pytest.mark.asyncio
    async def test_gate_rejection_raises_validation_error(self):
        # One ungrounded condition → grounding gate trips → generator raises.
        generator, _ = _generator(
            _payload(
                success_conditions=[
                    "The file /workspace/f3.txt exists.",
                    "Zorblat frequencies harmonized",
                ]
            )
        )
        with pytest.raises(TaskUnderstandingValidationError):
            await generator.generate(task_input=_TASK)

    @pytest.mark.asyncio
    async def test_count_overflow_raises_validation_error(self):
        generator, _ = _generator(
            _payload(
                success_conditions=[
                    f"weather condition {i} in Austin" for i in range(9)
                ]
            )
        )
        with pytest.raises(TaskUnderstandingValidationError):
            await generator.generate(task_input="weather conditions in Austin")

    @pytest.mark.asyncio
    async def test_fenced_json_tolerated(self):
        generator, _ = _generator(f"```json\n{_payload()}\n```")
        artifact = await generator.generate(task_input=_TASK)
        assert artifact.source == "generated"

    @pytest.mark.asyncio
    async def test_happy_path_artifact_provenance_no_plan_time_tail(self):
        generator, llm = _generator(_payload())
        artifact = await generator.generate(task_input=_TASK)
        assert isinstance(artifact, TaskUnderstanding)
        assert artifact.source == "generated"
        assert artifact.model == "gpt-4o-mini"
        assert artifact.confidence == 0.85
        assert artifact.restated_intent
        # The generic consistency tail is an ANSWER-grading check; it moved to
        # judge-time (goal_judge/evaluator). The plan-time artifact must NOT
        # carry it — the criteria are exactly the synthesized task conditions.
        assert GENERIC_TAIL_CONDITION not in artifact.success_conditions
        # The 3 generated conditions, no tail.
        assert len(artifact.success_conditions) == 3
        assert len(llm.calls) == 1

    @pytest.mark.asyncio
    async def test_prompt_renders_with_task_text(self):
        """H1: the .j2 resolves through the real PromptService and carries
        the task text; the generator never sees the final answer (D1
        pre-registration — there is no final answer at plan time)."""
        generator, llm = _generator(_payload())
        await generator.generate(task_input=_TASK)
        rendered = llm.calls[0][1][0]["content"]
        assert "/workspace/f3.txt" in rendered
        assert "JSON" in rendered


# ─────────────────────────────────────────────────────────────────────
# L2 — bounded retry-with-feedback on gate rejection (Stage 2a round 2)
#
# Round 1 failed at 73% gate-pass: gpt-4o-mini paraphrased 1–2 conditions
# and the all-or-nothing grounding gate discarded the whole artifact. The
# generator now retries ONCE with the rejected conditions + gate issues fed
# back through the prompt. Retry fires ONLY on a validation-gate rejection,
# never on a JSON-parse or LLM-transport error (those keep raising on the
# first attempt — round 1 had zero of them). Failure paths first (TAP-4).
# ─────────────────────────────────────────────────────────────────────


# An ungrounded condition list: "Zorblat …" shares no content token with the
# task, so the grounding gate rejects it on the FIRST attempt.
_UNGROUNDED = _payload(
    success_conditions=[
        "The file /workspace/f3.txt exists.",
        "Zorblat frequencies harmonized completely.",
    ]
)
# A grounded list that clears every gate — the recovered SECOND attempt.
_GROUNDED = _payload(
    success_conditions=[
        "The file /workspace/f3.txt exists and contains 'hello'.",
        "The file contents were listed via a shell command.",
    ]
)


class TestTaskUnderstandingRetry:
    @pytest.mark.asyncio
    async def test_retry_recovers_after_one_gate_rejection(self):
        """Attempt 0 ungrounded → reject → attempt 1 grounded → success.

        The callback carries the rejected condition TEXT (round-2 telemetry
        bug #2): issue strings alone forced round 2's root-cause to be
        inferred blind — and wrong. No diagnosis without the artifact text.
        """
        generator, llm = _generator([_UNGROUNDED, _GROUNDED])
        seen: list[tuple[list[str], int, list[str]]] = []
        artifact = await generator.generate(
            task_input=_TASK,
            on_gate_rejection=lambda issues, attempt, conditions: seen.append(
                (issues, attempt, conditions)
            ),
        )
        assert artifact.source == "generated"
        # The LLM was invoked twice (original + one retry).
        assert len(llm.calls) == 2
        # The callback fired exactly once, for the first (attempt 0) rejection.
        assert len(seen) == 1
        assert seen[0][1] == 0
        assert any("grounding" in issue for issue in seen[0][0])
        # The rejected attempt's conditions arrive verbatim.
        assert any("Zorblat" in c for c in seen[0][2])

    @pytest.mark.asyncio
    async def test_retry_prompt_carries_rejection_feedback(self):
        """The retry render feeds the rejected conditions + gate issues back
        through the .j2 (H1 — never string-concatenated in Python)."""
        generator, llm = _generator([_UNGROUNDED, _GROUNDED])
        await generator.generate(task_input=_TASK)
        assert len(llm.calls) == 2
        first_prompt = llm.calls[0][1][0]["content"]
        retry_prompt = llm.calls[1][1][0]["content"]
        # Only the retry render carries the feedback block + rejected text.
        assert "Zorblat" not in first_prompt
        assert "Zorblat" in retry_prompt
        assert "grounding" in retry_prompt.lower()

    @pytest.mark.asyncio
    async def test_two_rejections_raise_with_both_attempts(self):
        """Both attempts ungrounded → raise; callback fired for attempts 0 AND
        1 with each attempt's rejected text; the error references both
        attempts' issues."""
        generator, llm = _generator([_UNGROUNDED, _UNGROUNDED])
        seen: list[tuple[int, list[str]]] = []
        with pytest.raises(TaskUnderstandingValidationError) as exc_info:
            await generator.generate(
                task_input=_TASK,
                on_gate_rejection=lambda issues, attempt, conditions: seen.append(
                    (attempt, conditions)
                ),
            )
        assert len(llm.calls) == 2
        assert [attempt for attempt, _ in seen] == [0, 1]
        # Every rejected attempt's condition text is captured (bug #2).
        assert all(any("Zorblat" in c for c in conds) for _, conds in seen)
        # The raised error carries issues from both attempts.
        assert len(exc_info.value.issues) >= 2

    @pytest.mark.asyncio
    async def test_no_retry_on_malformed_json(self):
        """A parse failure is not a gate rejection — raise on attempt 0, no
        retry, callback never fires."""
        generator, llm = _generator(["this is not json", _GROUNDED])
        seen: list[int] = []
        with pytest.raises(Exception):
            await generator.generate(
                task_input=_TASK,
                on_gate_rejection=lambda issues, attempt, conditions: seen.append(
                    attempt
                ),
            )
        assert len(llm.calls) == 1
        assert seen == []

    @pytest.mark.asyncio
    async def test_no_retry_on_llm_transport_error(self):
        """An LLM/transport error is not a gate rejection — raise immediately,
        no retry, callback never fires."""
        generator, llm = _generator(
            [_GROUNDED, _GROUNDED], raises=RuntimeError("provider down")
        )
        seen: list[int] = []
        with pytest.raises(RuntimeError):
            await generator.generate(
                task_input=_TASK,
                on_gate_rejection=lambda issues, attempt, conditions: seen.append(
                    attempt
                ),
            )
        assert len(llm.calls) == 1
        assert seen == []

    @pytest.mark.asyncio
    async def test_callback_is_optional(self):
        """Recovery still works with no callback injected (back-compat)."""
        generator, llm = _generator([_UNGROUNDED, _GROUNDED])
        artifact = await generator.generate(task_input=_TASK)
        assert artifact.source == "generated"
        assert len(llm.calls) == 2

    @pytest.mark.asyncio
    async def test_first_attempt_success_does_not_retry(self):
        """Happy path is unchanged: one invoke, no callback, no feedback."""
        generator, llm = _generator(_GROUNDED)
        seen: list[int] = []
        await generator.generate(
            task_input=_TASK,
            on_gate_rejection=lambda issues, attempt, conditions: seen.append(attempt),
        )
        assert len(llm.calls) == 1
        assert seen == []
