"""L3 (mock-provider) tests for components/goal_judge.py.

The goal judge is an LLM-as-judge, so production behaviour sits above the
determinism boundary. These tests pin the *deterministic* parts — prompt
rendering, JSON-verdict parsing, the overlay contract, and failure handling —
using a mock LLM provider (record/replay), never a live model. We assert
STRUCTURAL properties (verdict shape, derived ``unmet_conditions``, clamping),
never exact LLM strings (avoids TAP-3 determinism theater).

Anti-patterns avoided:
  - Mock Addiction: a single in-memory LLM stub, plus the REAL PromptService.
  - Determinism Theater: no assertion on model-generated prose.
  - Gap Blindness: malformed-response failure path tested before happy path.
"""

from __future__ import annotations

import pytest

from components.goal_judge import GoalJudge
from components.schemas import GoalVerdict
from services.base_config import ModelProfile
from services.prompt_service import PromptService


# ─────────────────────────────────────────────────────────────────────
# Fakes
# ─────────────────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeLLMService:
    """In-memory LLM stub: replays a canned response, records the call."""

    def __init__(self, response_content: str) -> None:
        self._response_content = response_content
        self.calls: list[tuple[ModelProfile, list[dict]]] = []

    async def invoke(self, profile, messages, **kwargs):
        self.calls.append((profile, messages))
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


def _judge(response_content: str) -> tuple[GoalJudge, FakeLLMService]:
    llm = FakeLLMService(response_content)
    judge = GoalJudge(
        llm_service=llm,  # type: ignore[arg-type]
        prompt_service=PromptService(),
        judge_profile=_profile(),
    )
    return judge, llm


# ─────────────────────────────────────────────────────────────────────
# Failure path first (TAP-4): a malformed verdict must raise so the caller
# falls back to the deterministic heuristic.
# ─────────────────────────────────────────────────────────────────────


class TestVerdictParsingFailures:
    @pytest.mark.asyncio
    async def test_non_json_response_raises(self):
        judge, _ = _judge("I think the agent did a great job, honestly.")
        with pytest.raises(Exception):
            await judge.evaluate(
                task_input="What is the weather in Austin?",
                final_answer="It is sunny and 75F.",
                success_conditions=[],
            )

    @pytest.mark.asyncio
    async def test_json_array_not_object_raises(self):
        judge, _ = _judge('["not", "an", "object"]')
        with pytest.raises(Exception):
            await judge.evaluate(
                task_input="task",
                final_answer="answer",
                success_conditions=[],
            )


# ─────────────────────────────────────────────────────────────────────
# Happy path + structural contract
# ─────────────────────────────────────────────────────────────────────


class TestVerdictParsing:
    @pytest.mark.asyncio
    async def test_parses_goal_met_true(self):
        judge, _ = _judge(
            '{"goal_met": true, "criteria_met": 1.0, '
            '"per_criterion": [], "rationale": "ok"}'
        )
        verdict = await judge.evaluate(
            task_input="What is 2+2?",
            final_answer="4",
            success_conditions=[],
        )
        assert isinstance(verdict, GoalVerdict)
        assert verdict.goal_met is True
        assert verdict.criteria_met == 1.0

    @pytest.mark.asyncio
    async def test_unmet_conditions_derived_from_per_criterion(self):
        judge, _ = _judge(
            '{"goal_met": false, "criteria_met": 0.5, "per_criterion": ['
            '{"criterion": "Cites a source", "met": true, "evidence": "link"},'
            '{"criterion": "Gives a number", "met": false, "evidence": "vague"}'
            '], "rationale": "partial"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=["x", "y"]
        )
        assert verdict.goal_met is False
        assert verdict.unmet_conditions == ["Gives a number"]

    @pytest.mark.asyncio
    async def test_fenced_json_block_is_parsed(self):
        judge, _ = _judge(
            "Here is my verdict:\n```json\n"
            '{"goal_met": true, "criteria_met": 0.8, "per_criterion": [], '
            '"rationale": "good"}\n```\n'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.goal_met is True
        assert verdict.criteria_met == pytest.approx(0.8)

    @pytest.mark.asyncio
    async def test_percentage_criteria_met_is_clamped_to_unit_interval(self):
        judge, _ = _judge(
            '{"goal_met": true, "criteria_met": 80, "per_criterion": [], '
            '"rationale": "pct"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert 0.0 <= verdict.criteria_met <= 1.0
        assert verdict.criteria_met == pytest.approx(0.8)


# ─────────────────────────────────────────────────────────────────────
# Prompt rendering: the real template must receive task-adaptive context.
# ─────────────────────────────────────────────────────────────────────


class TestPromptRendering:
    @pytest.mark.asyncio
    async def test_prompt_includes_task_and_evidence(self):
        judge, llm = _judge(
            '{"goal_met": true, "criteria_met": 1.0, "per_criterion": [], '
            '"rationale": "ok"}'
        )
        await judge.evaluate(
            task_input="Weather in Austin?",
            final_answer="Sunny, 75F.",
            success_conditions=["Reports a temperature"],
            evidence=[{"tool_name": "web_search", "tool_output": "Austin 75F sunny"}],
        )
        assert len(llm.calls) == 1
        _, messages = llm.calls[0]
        rendered = messages[0]["content"]
        assert "Weather in Austin?" in rendered
        assert "Reports a temperature" in rendered
        assert "web_search" in rendered

    @pytest.mark.asyncio
    async def test_empty_evidence_renders_placeholder(self):
        judge, llm = _judge(
            '{"goal_met": false, "criteria_met": 0.0, "per_criterion": [], '
            '"rationale": "no tools"}'
        )
        await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[], evidence=[]
        )
        rendered = llm.calls[0][1][0]["content"]
        assert "no tool calls" in rendered.lower()

    def test_model_name_exposed_for_eval_capture(self):
        judge, _ = _judge("{}")
        assert judge.model_name == "gpt-4o-mini"
