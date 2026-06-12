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
    """In-memory LLM stub: replays a canned response, records the call."""

    def __init__(self, response_content: str, *, raises: Exception | None = None) -> None:
        self._response_content = response_content
        self._raises = raises
        self.calls: list[tuple[ModelProfile, list[dict]]] = []

    async def invoke(self, profile, messages, **kwargs):
        self.calls.append((profile, messages))
        if self._raises is not None:
            raise self._raises
        return _FakeResponse(self._response_content)


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
    response_content: str, *, raises: Exception | None = None
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
    def test_count_gate_rejects_zero_one_and_eight(self):
        for conditions in ([], ["only one mentioning task"],
                           [f"task condition {i}" for i in range(8)]):
            issues = validate_conditions(conditions, task_input="task condition text")
            assert any("count" in issue for issue in issues)

    def test_length_gate_rejects_201_char_item(self):
        long_item = "task " + "x" * 200
        issues = validate_conditions(
            ["task is done", long_item], task_input="the task"
        )
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
        # …but count/length bounds still apply.
        issues = validate_conditions(
            ["one"], task_input="Fetch the weather", source="user_edited"
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
            _payload(success_conditions=[
                "The file /workspace/f3.txt exists.",
                "Zorblat frequencies harmonized",
            ])
        )
        with pytest.raises(TaskUnderstandingValidationError):
            await generator.generate(task_input=_TASK)

    @pytest.mark.asyncio
    async def test_count_overflow_raises_validation_error(self):
        generator, _ = _generator(
            _payload(success_conditions=[f"weather condition {i} in Austin" for i in range(9)])
        )
        with pytest.raises(TaskUnderstandingValidationError):
            await generator.generate(task_input="weather conditions in Austin")

    @pytest.mark.asyncio
    async def test_fenced_json_tolerated(self):
        generator, _ = _generator(f"```json\n{_payload()}\n```")
        artifact = await generator.generate(task_input=_TASK)
        assert artifact.source == "generated"

    @pytest.mark.asyncio
    async def test_happy_path_artifact_provenance_and_tail(self):
        generator, llm = _generator(_payload())
        artifact = await generator.generate(task_input=_TASK)
        assert isinstance(artifact, TaskUnderstanding)
        assert artifact.source == "generated"
        assert artifact.model == "gpt-4o-mini"
        assert artifact.confidence == 0.85
        assert artifact.restated_intent
        # Generic consistency tail always appended, last.
        assert artifact.success_conditions[-1] == GENERIC_TAIL_CONDITION
        # The 3 generated conditions + tail.
        assert len(artifact.success_conditions) == 4
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
