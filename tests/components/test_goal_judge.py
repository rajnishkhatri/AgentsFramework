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

    @pytest.mark.asyncio
    async def test_malformed_per_criterion_entries_still_raise(self):
        """Non-dict entries must not be silently repaired into a verdict —
        the criteria_met derivation skips them and schema validation raises,
        preserving the heuristic-fallback contract."""
        judge, _ = _judge(
            '{"goal_met": true, "criteria_met": 0.0, "per_criterion": [1, 2], '
            '"rationale": "broken breakdown"}'
        )
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
        assert verdict.criteria_met_derived is False


# ─────────────────────────────────────────────────────────────────────
# criteria_met repair: when the model omits or contradicts its own
# per_criterion breakdown, the met-flag mean is authoritative (production
# trace shipped criteria_met=0.0 alongside 4/4 met=true, corrupting the
# Stage 5/6 calibration slices). ``criteria_met_derived`` marks the repair.
# ─────────────────────────────────────────────────────────────────────

_FOUR_MET = (
    '{"criterion": "a", "met": true, "evidence": "e"},'
    '{"criterion": "b", "met": true, "evidence": "e"},'
    '{"criterion": "c", "met": true, "evidence": "e"},'
    '{"criterion": "d", "met": true, "evidence": "e"}'
)
_THREE_OF_FOUR_MET = (
    '{"criterion": "a", "met": true, "evidence": "e"},'
    '{"criterion": "b", "met": true, "evidence": "e"},'
    '{"criterion": "c", "met": false, "evidence": ""},'
    '{"criterion": "d", "met": true, "evidence": "e"}'
)


class TestCriteriaMetDerivation:
    @pytest.mark.asyncio
    async def test_omitted_criteria_met_derived_from_per_criterion(self):
        judge, _ = _judge(
            '{"goal_met": false, "per_criterion": ['
            + _THREE_OF_FOUR_MET
            + '], "rationale": "no fraction given"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.criteria_met == pytest.approx(0.75)
        assert verdict.criteria_met_derived is True

    @pytest.mark.asyncio
    async def test_contradictory_zero_overridden_by_breakdown(self):
        """The production-trace shape: criteria_met=0.0 with 4/4 met=true."""
        judge, _ = _judge(
            '{"goal_met": true, "criteria_met": 0.0, "per_criterion": ['
            + _FOUR_MET
            + '], "rationale": "contradictory"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.criteria_met == pytest.approx(1.0)
        assert verdict.criteria_met_derived is True

    @pytest.mark.asyncio
    async def test_consistent_criteria_met_kept_and_not_flagged(self):
        """A value within half a criterion's weight of the mean is the model's."""
        judge, _ = _judge(
            '{"goal_met": false, "criteria_met": 0.7, "per_criterion": ['
            + _THREE_OF_FOUR_MET
            + '], "rationale": "close enough"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.criteria_met == pytest.approx(0.7)
        assert verdict.criteria_met_derived is False

    @pytest.mark.asyncio
    async def test_percentage_rescale_consistent_with_breakdown_not_flagged(self):
        """The 0-100 rescale path still applies before the consistency check."""
        judge, _ = _judge(
            '{"goal_met": false, "criteria_met": 75, "per_criterion": ['
            + _THREE_OF_FOUR_MET
            + '], "rationale": "pct"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.criteria_met == pytest.approx(0.75)
        assert verdict.criteria_met_derived is False

    @pytest.mark.asyncio
    async def test_unparseable_criteria_met_derived_when_breakdown_present(self):
        judge, _ = _judge(
            '{"goal_met": true, "criteria_met": "most", "per_criterion": ['
            + _FOUR_MET
            + '], "rationale": "stringy"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.criteria_met == pytest.approx(1.0)
        assert verdict.criteria_met_derived is True

    @pytest.mark.asyncio
    async def test_deviation_of_exactly_half_a_criterion_is_kept(self):
        """The tolerance is strict (>): at exactly 0.5/N the model value wins.

        N=4 -> tolerance 0.125; 0.625 vs mean 0.75 sits on the knife edge
        (all exact binary fractions, so no float fuzz in the comparison).
        """
        judge, _ = _judge(
            '{"goal_met": false, "criteria_met": 0.625, "per_criterion": ['
            + _THREE_OF_FOUR_MET
            + '], "rationale": "boundary"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.criteria_met == pytest.approx(0.625)
        assert verdict.criteria_met_derived is False

    @pytest.mark.asyncio
    async def test_deviation_beyond_half_a_criterion_is_repaired(self):
        """Just past the 0.5/N boundary (0.6 vs mean 0.75) the breakdown wins."""
        judge, _ = _judge(
            '{"goal_met": false, "criteria_met": 0.6, "per_criterion": ['
            + _THREE_OF_FOUR_MET
            + '], "rationale": "past boundary"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.criteria_met == pytest.approx(0.75)
        assert verdict.criteria_met_derived is True

    @pytest.mark.asyncio
    async def test_string_met_flags_are_coerced_not_truthy(self):
        """A ``"false"`` string met-flag counts as not met (bool("false") is
        True — the derivation must mirror pydantic's coercion, not truthiness)."""
        judge, _ = _judge(
            '{"goal_met": false, "per_criterion": ['
            '{"criterion": "a", "met": "true", "evidence": "e"},'
            '{"criterion": "b", "met": "false", "evidence": ""}'
            '], "rationale": "stringly typed"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.criteria_met == pytest.approx(0.5)
        assert verdict.criteria_met_derived is True

    @pytest.mark.asyncio
    async def test_empty_per_criterion_keeps_omitted_default_unflagged(self):
        """No breakdown -> nothing to derive from; the 0.0 default stands."""
        judge, _ = _judge(
            '{"goal_met": false, "per_criterion": [], "rationale": "bare"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.criteria_met == 0.0
        assert verdict.criteria_met_derived is False


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
        """A v1 verdict (no graceful_failure/partial_fraction/failure_mode) stays valid."""
        judge, _ = _judge(
            '{"goal_met": true, "criteria_met": 1.0, "per_criterion": [], '
            '"rationale": "ok"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.graceful_failure is False
        assert verdict.partial_fraction == 0.0
        # Stage 5 ``failure_mode`` axis: absent key ⇒ None (telemetry-only, no
        # behavior change). Back-compat is asserted before the happy path (TAP-4).
        assert verdict.failure_mode is None

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

    # ── Stage 5 ``failure_mode`` axis (telemetry-only; default-None) ──────
    @pytest.mark.asyncio
    async def test_failure_mode_a2_code_parsed(self):
        """An A2 member code in the verdict JSON round-trips onto the axis."""
        judge, _ = _judge(
            '{"goal_met": false, "criteria_met": 0.0, "per_criterion": [], '
            '"rationale": "claimed done, no tool evidence", '
            '"failure_mode": "fabricated-progress"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.failure_mode == "fabricated-progress"

    @pytest.mark.asyncio
    async def test_failure_mode_blank_string_is_none(self):
        """An empty / whitespace ``failure_mode`` normalizes to None (no-op)."""
        judge, _ = _judge(
            '{"goal_met": true, "criteria_met": 1.0, "per_criterion": [], '
            '"rationale": "ok", "failure_mode": "   "}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.failure_mode is None

    @pytest.mark.asyncio
    async def test_failure_mode_literal_none_string_is_none(self):
        """A model emitting the string ``\"none\"`` is treated as unclassified."""
        judge, _ = _judge(
            '{"goal_met": true, "criteria_met": 1.0, "per_criterion": [], '
            '"rationale": "ok", "failure_mode": "none"}'
        )
        verdict = await judge.evaluate(
            task_input="t", final_answer="a", success_conditions=[]
        )
        assert verdict.failure_mode is None

    @pytest.mark.asyncio
    async def test_failure_mode_unknown_code_raises(self):
        """An out-of-vocabulary code is a labelling bug — surface it, don't store it."""
        judge, _ = _judge(
            '{"goal_met": false, "criteria_met": 0.0, "per_criterion": [], '
            '"rationale": "x", "failure_mode": "made-up-code"}'
        )
        with pytest.raises(ValueError, match="unknown failure_mode"):
            await judge.evaluate(
                task_input="t", final_answer="a", success_conditions=[]
            )


# ─────────────────────────────────────────────────────────────────────
# ``failure_mode`` enum integrity: the schema vocabulary must stay in sync
# with the executable registry's Axis-A ``target_code`` values (L1, no I/O).
# ─────────────────────────────────────────────────────────────────────


class TestFailureModeEnumIntegrity:
    def test_enum_matches_registry_axis_a_codes(self):
        """``GOAL_FAILURE_MODES`` == the registry's active Axis-A codes.

        Drift-guard analogous to F7: if a registry ``target_code`` is added or
        retired, this pin fails until the schema enum is reconciled — so the
        Stage 5 ``failure_mode`` vocabulary can never silently diverge from the
        taxonomy the gold set labels against. ``correct-complete`` (the pass
        baseline) and ``tool-stub-limitation`` (retired → Axis-B B5) are
        excluded by construction.
        """
        from components.schemas import GOAL_FAILURE_MODES
        from tests.fixtures.goaljudge.case_registry import LIVE_CASES

        registry_codes = {
            case.target_code
            for case in LIVE_CASES
            if case.target_code
            not in {"correct-complete", "tool-stub-limitation"}
        }
        assert registry_codes <= GOAL_FAILURE_MODES, (
            "registry has Axis-A codes missing from GOAL_FAILURE_MODES: "
            f"{sorted(registry_codes - GOAL_FAILURE_MODES)}"
        )


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


class TestSummarizeToolCalls:
    """L3 pure-function tests for the eval.goal_judge audit-trail helper.

    ``summarize_tool_calls`` is what the orchestration node calls to build
    the ``tool_calls_summary`` field on the Langfuse eval observation. This
    lets us answer queries like "show me every GoalJudge verdict where
    web_search was never invoked" without scrolling through evidence
    digests. Failure paths first (AGENTS.md TAP-4).
    """

    def test_empty_evidence_returns_empty_list(self):
        from components.goal_judge import summarize_tool_calls

        assert summarize_tool_calls([]) == []

    def test_none_evidence_returns_empty_list(self):
        from components.goal_judge import summarize_tool_calls

        assert summarize_tool_calls(None) == []

    def test_missing_tool_name_falls_back_to_question_mark(self):
        from components.goal_judge import summarize_tool_calls

        summary = summarize_tool_calls(
            [{"tool_input": {"q": "x"}}]  # no tool_name
        )
        assert summary == [{"tool_name": "?", "args_keys": ["q"]}]

    def test_missing_tool_input_yields_empty_args_keys(self):
        from components.goal_judge import summarize_tool_calls

        summary = summarize_tool_calls([{"tool_name": "shell"}])
        assert summary == [{"tool_name": "shell", "args_keys": []}]

    def test_args_keys_are_sorted_for_stable_diff(self):
        from components.goal_judge import summarize_tool_calls

        summary = summarize_tool_calls(
            [{"tool_name": "shell", "tool_input": {"cwd": ".", "command": "ls"}}]
        )
        assert summary[0]["args_keys"] == ["command", "cwd"]

    def test_limit_keeps_only_tail(self):
        from components.goal_judge import summarize_tool_calls

        evidence = [
            {"tool_name": f"t{i}", "tool_input": {}} for i in range(12)
        ]
        summary = summarize_tool_calls(evidence, limit=3)
        assert [s["tool_name"] for s in summary] == ["t9", "t10", "t11"]

    def test_default_limit_is_eight(self):
        from components.goal_judge import summarize_tool_calls

        evidence = [
            {"tool_name": f"t{i}", "tool_input": {}} for i in range(20)
        ]
        summary = summarize_tool_calls(evidence)
        assert len(summary) == 8
        assert summary[0]["tool_name"] == "t12"

    def test_three_subtask_trace_surfaces_all_distinct_tools(self):
        """Stage 4 §10.2 GJ-012 — a healthy three-subtask trace should show
        the three distinct tool names so a Langfuse query can flag the case
        where web_search is missing."""
        from components.goal_judge import summarize_tool_calls

        evidence = [
            {"tool_name": "file_io", "tool_input": {"operation": "write", "path": "/x"}},
            {"tool_name": "shell", "tool_input": {"command": "cat /x"}},
            {"tool_name": "web_search", "tool_input": {"query": "Austin weather"}},
        ]
        summary = summarize_tool_calls(evidence)
        assert [s["tool_name"] for s in summary] == ["file_io", "shell", "web_search"]
