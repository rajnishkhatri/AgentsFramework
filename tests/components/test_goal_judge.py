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
from services.governance.guardrail_validator import (
    FailAction,
    GuardRailValidator,
    api_key_rules,
    pii_rules,
)
from services.prompt_service import PromptService


def _redact_all_validator() -> GuardRailValidator:
    """Mirror the graph-build judge redactor: all PII/API-key rules as REDACT."""
    return GuardRailValidator([
        rule.model_copy(update={"fail_action": FailAction.REDACT})
        for rule in (pii_rules() + api_key_rules())
    ])


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


def _judge(
    response_content: str, *, redactor: GuardRailValidator | None = None
) -> tuple[GoalJudge, FakeLLMService]:
    llm = FakeLLMService(response_content)
    judge = GoalJudge(
        llm_service=llm,  # type: ignore[arg-type]
        prompt_service=PromptService(),
        judge_profile=_profile(),
        redactor=redactor,
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


# ─────────────────────────────────────────────────────────────────────
# Fix 2 (Option B): graceful_failure + partial_fraction metadata axes.
# Backward compat (missing keys) is tested before the happy path (TAP-4).
# ─────────────────────────────────────────────────────────────────────


class TestNewVerdictAxes:
    @pytest.mark.asyncio
    async def test_graceful_failure_string_false_parses_false(self):
        """JSON string ``\"false\"`` must not coerce to True (F4 regression)."""
        judge, _ = _judge(
            '{"goal_met": false, "criteria_met": 0.0, "per_criterion": [], '
            '"rationale": "stringy false", "graceful_failure": "false"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.graceful_failure is False

    @pytest.mark.asyncio
    async def test_graceful_failure_string_true_parses_true(self):
        judge, _ = _judge(
            '{"goal_met": false, "criteria_met": 0.0, "per_criterion": [], '
            '"rationale": "stringy true", "graceful_failure": "true"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.graceful_failure is True

    @pytest.mark.asyncio
    async def test_missing_new_keys_default_safely(self):
        """A v1 verdict (no graceful_failure/partial_fraction) stays valid."""
        judge, _ = _judge(
            '{"goal_met": true, "criteria_met": 1.0, "per_criterion": [], '
            '"rationale": "ok"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.graceful_failure is False
        assert verdict.partial_fraction == 0.0

    @pytest.mark.asyncio
    async def test_graceful_failure_parsed(self):
        judge, _ = _judge(
            '{"goal_met": false, "criteria_met": 0.0, "per_criterion": [], '
            '"rationale": "task was impossible; agent reported it honestly", '
            '"graceful_failure": true, "partial_fraction": 0.0}'
        )
        verdict = await judge.evaluate(
            task_input="Divide 1 by 0 exactly.",
            final_answer="That is undefined; division by zero is impossible.",
            success_conditions=[],
        )
        assert verdict.goal_met is False
        assert verdict.graceful_failure is True

    @pytest.mark.asyncio
    async def test_partial_fraction_parsed(self):
        judge, _ = _judge(
            '{"goal_met": false, "criteria_met": 0.5, "per_criterion": [], '
            '"rationale": "half done", "partial_fraction": 0.5}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.partial_fraction == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_a2_partial_verdict_end_to_end(self):
        """A2 corrupt-success: canned goal_met=false + partial_fraction=0.67 parses."""
        from tests.fixtures.goaljudge.a2_session_fixtures import (
            GJ_010_SHAPED,
            _CANNED_A2_PARTIAL_VERDICT,
        )

        judge, _ = _judge(_CANNED_A2_PARTIAL_VERDICT)
        verdict = await judge.evaluate(
            task_input=GJ_010_SHAPED["task_input"],
            final_answer=GJ_010_SHAPED["final_answer"],
            success_conditions=GJ_010_SHAPED["success_conditions"],
            evidence=GJ_010_SHAPED["evidence"],
        )
        assert verdict.goal_met is False
        assert verdict.partial_fraction == pytest.approx(0.67)
        assert verdict.graceful_failure is False

    @pytest.mark.asyncio
    async def test_partial_fraction_out_of_range_is_clamped(self):
        """A >1 fraction (e.g. a 0-100 percentage) is rescaled then clamped."""
        judge, _ = _judge(
            '{"goal_met": false, "criteria_met": 0.0, "per_criterion": [], '
            '"rationale": "pct", "partial_fraction": 60}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert 0.0 <= verdict.partial_fraction <= 1.0
        assert verdict.partial_fraction == pytest.approx(0.6)

    @pytest.mark.asyncio
    async def test_negative_partial_fraction_clamped_to_zero(self):
        judge, _ = _judge(
            '{"goal_met": false, "criteria_met": 0.0, "per_criterion": [], '
            '"rationale": "neg", "partial_fraction": -0.5}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.partial_fraction == 0.0

    @pytest.mark.asyncio
    async def test_non_numeric_partial_fraction_defaults_zero(self):
        judge, _ = _judge(
            '{"goal_met": false, "criteria_met": 0.0, "per_criterion": [], '
            '"rationale": "bad", "partial_fraction": "lots"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.partial_fraction == 0.0


# ─────────────────────────────────────────────────────────────────────
# Evidence enrichment + redaction: tool inputs reach the prompt, and an
# injected redactor scrubs secrets/PII before they hit the judge call.
# ─────────────────────────────────────────────────────────────────────


class TestEvidenceEnrichmentAndRedaction:
    @pytest.mark.asyncio
    async def test_digest_includes_tool_input(self):
        judge, llm = _judge(
            '{"goal_met": true, "criteria_met": 1.0, "per_criterion": [], '
            '"rationale": "ok"}'
        )
        await judge.evaluate(
            task_input="Look up Austin weather",
            final_answer="Sunny, 75F.",
            success_conditions=[],
            evidence=[
                {
                    "tool_name": "web_search",
                    "tool_input": {"query": "Austin weather today"},
                    "tool_output": "Austin 75F sunny",
                }
            ],
        )
        rendered = llm.calls[0][1][0]["content"]
        assert "Austin weather today" in rendered  # the tool INPUT is grounded
        assert "Austin 75F sunny" in rendered  # the tool OUTPUT is grounded

    @pytest.mark.asyncio
    async def test_redactor_scrubs_api_key_in_evidence(self):
        judge, llm = _judge(
            '{"goal_met": true, "criteria_met": 1.0, "per_criterion": [], '
            '"rationale": "ok"}',
            redactor=_redact_all_validator(),
        )
        secret = "sk-proj-ABCD1234efgh5678"
        await judge.evaluate(
            task_input="t",
            final_answer="done",
            success_conditions=[],
            evidence=[
                {
                    "tool_name": "shell",
                    "tool_input": {"cmd": f"export OPENAI_API_KEY={secret}"},
                    "tool_output": f"key set to {secret}",
                }
            ],
        )
        rendered = llm.calls[0][1][0]["content"]
        assert secret not in rendered
        assert "[REDACTED]" in rendered

    @pytest.mark.asyncio
    async def test_redactor_scrubs_email_pii_in_evidence(self):
        judge, llm = _judge(
            '{"goal_met": true, "criteria_met": 1.0, "per_criterion": [], '
            '"rationale": "ok"}',
            redactor=_redact_all_validator(),
        )
        await judge.evaluate(
            task_input="t",
            final_answer="done",
            success_conditions=[],
            evidence=[
                {
                    "tool_name": "lookup",
                    "tool_input": {},
                    "tool_output": "contact: jane.doe@example.com",
                }
            ],
        )
        rendered = llm.calls[0][1][0]["content"]
        assert "jane.doe@example.com" not in rendered

    @pytest.mark.asyncio
    async def test_no_redactor_leaves_evidence_intact(self):
        """Without a redactor (CI default) the digest is verbatim."""
        judge, llm = _judge(
            '{"goal_met": true, "criteria_met": 1.0, "per_criterion": [], '
            '"rationale": "ok"}'
        )
        await judge.evaluate(
            task_input="t",
            final_answer="done",
            success_conditions=[],
            evidence=[{"tool_name": "lookup", "tool_output": "plain text result"}],
        )
        rendered = llm.calls[0][1][0]["content"]
        assert "plain text result" in rendered
