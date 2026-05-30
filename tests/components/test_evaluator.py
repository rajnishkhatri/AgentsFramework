"""L1 Deterministic: Tests for components/evaluator.py.

Pure TDD, Protocol A (Red-Green-Refactor). Failure paths first.
Covers parse_llm_response, classify_outcome (parametrized status-code matrix),
build_step_result, check_continuation (backoff property).
"""

from __future__ import annotations

import time

import pytest

from components.evaluator import (
    build_step_result,
    check_continuation,
    classify_outcome,
    parse_llm_response,
)
from components.schemas import ErrorRecord
from services.base_config import AgentConfig


class TestParseLlmResponse:
    def test_detects_tool_call(self):
        msg = type("Msg", (), {
            "tool_calls": [{"name": "shell", "args": {"command": "ls"}}],
            "content": "",
        })()
        assert parse_llm_response(msg) == "tool_call"

    def test_detects_final_answer(self):
        msg = type("Msg", (), {
            "tool_calls": [],
            "content": "FINAL ANSWER: The answer is 42",
        })()
        assert parse_llm_response(msg) == "final_answer"

    def test_detects_text_as_final_answer(self):
        msg = type("Msg", (), {
            "tool_calls": [],
            "content": "The capital of France is Paris.",
        })()
        assert parse_llm_response(msg) == "final_answer"


class _FakeHTTPError(Exception):
    def __init__(self, status_code: int, msg: str = "") -> None:
        super().__init__(msg or f"HTTP {status_code}")
        self.status_code = status_code


class TestClassifyOutcome:
    """Failure paths first (Anti-Pattern 6 prevention)."""

    @pytest.mark.parametrize(
        "status_code,expected_type",
        [
            (429, "retryable"),
            (503, "retryable"),
            (400, "model_error"),
            (401, "model_error"),
            (403, "model_error"),
        ],
    )
    def test_maps_http_status_to_error_type(self, status_code, expected_type):
        err = _FakeHTTPError(status_code=status_code)
        outcome, rec = classify_outcome("", err, model="gpt-4o-mini", step=3)
        assert outcome == "failure"
        assert rec is not None
        assert rec.error_type == expected_type
        assert rec.error_code == status_code
        assert rec.model == "gpt-4o-mini"
        assert rec.step == 3

    def test_terminal_when_no_status_code(self):
        outcome, rec = classify_outcome(
            "", RuntimeError("boom"), model="x"
        )
        assert outcome == "failure"
        assert rec is not None
        assert rec.error_type == "terminal"
        assert rec.error_code is None
        assert "boom" in rec.message

    def test_tool_error_when_message_mentions_tool(self):
        outcome, rec = classify_outcome(
            "", ValueError("tool returned non-zero"), model="m"
        )
        assert outcome == "failure"
        assert rec is not None
        assert rec.error_type == "tool_error"

    def test_success_returns_none_record(self):
        outcome, rec = classify_outcome("Some answer", None, model="m")
        assert outcome == "success"
        assert rec is None

    def test_timestamp_is_populated(self):
        before = time.time()
        outcome, rec = classify_outcome(
            "", _FakeHTTPError(429), model="m"
        )
        after = time.time()
        assert rec is not None
        assert before <= rec.timestamp <= after


class TestBuildStepResult:
    def test_includes_error_type_from_record(self):
        rec = ErrorRecord(
            step=2,
            error_type="retryable",
            error_code=429,
            message="rate limited",
            model="gpt-4o-mini",
            timestamp=123.0,
        )
        sr = build_step_result(
            step_id=2,
            action="call_llm",
            model_used="gpt-4o-mini",
            routing_reason="steady-state-fast",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
            latency_ms=120.0,
            outcome="failure",
            error_record=rec,
            reasoning="rate limit at step 2",
        )
        assert sr.error_type == "retryable"
        assert sr.outcome == "failure"
        assert sr.model_used == "gpt-4o-mini"

    def test_none_record_yields_none_error_type(self):
        sr = build_step_result(
            step_id=0,
            action="answer",
            model_used="gpt-4o-mini",
            routing_reason="steady-state-fast",
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
            latency_ms=10.0,
            outcome="success",
            error_record=None,
            reasoning="ok",
        )
        assert sr.error_type is None


class TestCheckContinuation:
    def test_stops_on_budget_exceeded(self):
        result = check_continuation(
            step_count=5,
            total_cost_usd=1.5,
            last_outcome="success",
            last_error_type=None,
            agent_config=AgentConfig(max_steps=20, max_cost_usd=1.0),
        )
        assert result == "done"

    def test_stops_on_step_limit(self):
        result = check_continuation(
            step_count=20,
            total_cost_usd=0.1,
            last_outcome="success",
            last_error_type=None,
            agent_config=AgentConfig(max_steps=20, max_cost_usd=1.0),
        )
        assert result == "done"

    def test_stops_on_terminal_error(self):
        result = check_continuation(
            step_count=1,
            total_cost_usd=0.01,
            last_outcome="failure",
            last_error_type="terminal",
            agent_config=AgentConfig(max_steps=20, max_cost_usd=1.0),
        )
        assert result == "done"

    def test_stops_on_success_no_pending_tools(self):
        result = check_continuation(
            step_count=1,
            total_cost_usd=0.01,
            last_outcome="success",
            last_error_type=None,
            agent_config=AgentConfig(max_steps=20, max_cost_usd=1.0),
        )
        assert result == "done"

    def test_continues_on_success_with_pending_tools(self):
        result = check_continuation(
            step_count=1,
            total_cost_usd=0.01,
            last_outcome="success",
            last_error_type=None,
            agent_config=AgentConfig(max_steps=20, max_cost_usd=1.0),
            has_pending_tool_result=True,
        )
        assert result == "continue"

    def test_continues_on_retryable_error(self):
        result = check_continuation(
            step_count=1,
            total_cost_usd=0.01,
            last_outcome="failure",
            last_error_type="retryable",
            agent_config=AgentConfig(max_steps=20, max_cost_usd=1.0),
        )
        assert result == "continue"

    def test_backoff_future_keeps_continuation_open(self):
        """Property-ish: a pending backoff_until overrides the 'success -> done'
        early-exit so the retry schedule is respected."""
        now = 1000.0
        result = check_continuation(
            step_count=2,
            total_cost_usd=0.01,
            last_outcome="success",
            last_error_type=None,
            agent_config=AgentConfig(max_steps=20, max_cost_usd=1.0),
            backoff_until=now + 30.0,
            now=now,
        )
        assert result == "continue"

    def test_backoff_past_does_not_prevent_done(self):
        now = 1000.0
        result = check_continuation(
            step_count=2,
            total_cost_usd=0.01,
            last_outcome="success",
            last_error_type=None,
            agent_config=AgentConfig(max_steps=20, max_cost_usd=1.0),
            backoff_until=now - 10.0,
            now=now,
        )
        assert result == "done"

    def test_backoff_does_not_override_budget_cap(self):
        now = 1000.0
        result = check_continuation(
            step_count=5,
            total_cost_usd=5.0,
            last_outcome="success",
            last_error_type=None,
            agent_config=AgentConfig(max_steps=20, max_cost_usd=1.0),
            backoff_until=now + 30.0,
            now=now,
        )
        assert result == "done"


class TestCheckContinuationNoProgress:
    """No-progress graduated backstop: failure paths first (TAP-4 prevention).

    Three tiers:
      1. hard_limit: terminates regardless of directive flag.
      2. threshold + directive_sent: model ignored wrap-up, terminate.
      3. threshold + not directive_sent: allow one synthesis pass (continue).
    """

    # ── Tier 1: hard_limit failsafe (absolute cap) ──

    def test_stops_at_hard_limit_regardless_of_directive_flag(self):
        """Hard limit terminates even when directive was NOT sent."""
        result = check_continuation(
            step_count=5,
            total_cost_usd=0.01,
            last_outcome="failure",
            last_error_type="retryable",
            agent_config=AgentConfig(
                max_steps=20, max_cost_usd=1.0,
                no_progress_repeat_threshold=3, no_progress_hard_limit=5,
            ),
            has_pending_tool_result=True,
            repeated_tool_calls=5,
            no_progress_directive_sent=False,
        )
        assert result == "done"

    def test_stops_above_hard_limit_with_directive_sent(self):
        result = check_continuation(
            step_count=5,
            total_cost_usd=0.01,
            last_outcome="failure",
            last_error_type="retryable",
            agent_config=AgentConfig(
                max_steps=20, max_cost_usd=1.0,
                no_progress_repeat_threshold=3, no_progress_hard_limit=5,
            ),
            has_pending_tool_result=True,
            repeated_tool_calls=6,
            no_progress_directive_sent=True,
        )
        assert result == "done"

    # ── Tier 2: threshold + directive_sent -> done ──

    def test_stops_at_threshold_when_directive_was_sent(self):
        """Model ignored the wrap-up directive: terminate."""
        result = check_continuation(
            step_count=5,
            total_cost_usd=0.01,
            last_outcome="failure",
            last_error_type="retryable",
            agent_config=AgentConfig(
                max_steps=20, max_cost_usd=1.0,
                no_progress_repeat_threshold=3, no_progress_hard_limit=5,
            ),
            has_pending_tool_result=True,
            repeated_tool_calls=3,
            no_progress_directive_sent=True,
        )
        assert result == "done"

    def test_stops_above_threshold_when_directive_was_sent(self):
        result = check_continuation(
            step_count=5,
            total_cost_usd=0.01,
            last_outcome="failure",
            last_error_type=None,
            agent_config=AgentConfig(
                max_steps=20, max_cost_usd=1.0,
                no_progress_repeat_threshold=3, no_progress_hard_limit=5,
            ),
            has_pending_tool_result=True,
            repeated_tool_calls=4,
            no_progress_directive_sent=True,
        )
        assert result == "done"

    # ── Tier 3: threshold + not directive_sent -> continue (synthesis pass) ──

    def test_continues_at_threshold_when_directive_not_sent(self):
        """Allows one synthesis pass before termination."""
        result = check_continuation(
            step_count=5,
            total_cost_usd=0.01,
            last_outcome="failure",
            last_error_type="retryable",
            agent_config=AgentConfig(
                max_steps=20, max_cost_usd=1.0,
                no_progress_repeat_threshold=3, no_progress_hard_limit=5,
            ),
            has_pending_tool_result=True,
            repeated_tool_calls=3,
            no_progress_directive_sent=False,
        )
        assert result == "continue"

    def test_continues_above_threshold_below_hard_limit_when_directive_not_sent(self):
        result = check_continuation(
            step_count=5,
            total_cost_usd=0.01,
            last_outcome="failure",
            last_error_type="retryable",
            agent_config=AgentConfig(
                max_steps=20, max_cost_usd=1.0,
                no_progress_repeat_threshold=3, no_progress_hard_limit=5,
            ),
            has_pending_tool_result=True,
            repeated_tool_calls=4,
            no_progress_directive_sent=False,
        )
        assert result == "continue"

    # ── Below threshold: always continue ──

    def test_continues_when_repeated_below_threshold(self):
        result = check_continuation(
            step_count=5,
            total_cost_usd=0.01,
            last_outcome="failure",
            last_error_type="retryable",
            agent_config=AgentConfig(
                max_steps=20, max_cost_usd=1.0,
                no_progress_repeat_threshold=3, no_progress_hard_limit=5,
            ),
            has_pending_tool_result=True,
            repeated_tool_calls=2,
        )
        assert result == "continue"

    def test_zero_repeats_does_not_trigger(self):
        result = check_continuation(
            step_count=5,
            total_cost_usd=0.01,
            last_outcome="failure",
            last_error_type="retryable",
            agent_config=AgentConfig(
                max_steps=20, max_cost_usd=1.0,
                no_progress_repeat_threshold=3, no_progress_hard_limit=5,
            ),
            has_pending_tool_result=True,
            repeated_tool_calls=0,
        )
        assert result == "continue"

    def test_no_progress_overrides_pending_tool_result(self):
        """Even with a pending tool result, hard limit causes termination."""
        result = check_continuation(
            step_count=5,
            total_cost_usd=0.01,
            last_outcome="failure",
            last_error_type=None,
            agent_config=AgentConfig(
                max_steps=20, max_cost_usd=1.0,
                no_progress_repeat_threshold=3, no_progress_hard_limit=5,
            ),
            has_pending_tool_result=True,
            repeated_tool_calls=5,
        )
        assert result == "done"


class TestEvaluateTaskOutcome:
    """L2 Reproducible: Task outcome evaluation (Protocol B — contract tests).

    Failure paths first per TAP-4. Tests the deterministic process-level
    evaluation: clean termination + substance → outcome classification.
    """

    def test_clean_termination_with_substantive_answer_is_success(self):
        from components.evaluator import evaluate_task_outcome

        result = evaluate_task_outcome(
            final_answer="The capital of France is Paris.",
            success_conditions=[],
            plan_steps=[],
            termination_reason="success",
        )
        assert result.outcome == "success"
        assert result.termination_clean is True
        assert result.score > 0.7

    def test_clean_termination_empty_answer_is_failed(self):
        from components.evaluator import evaluate_task_outcome

        result = evaluate_task_outcome(
            final_answer="",
            success_conditions=[],
            plan_steps=[],
            termination_reason="success",
        )
        assert result.outcome == "failed"
        assert result.termination_clean is True

    def test_unclean_termination_with_answer_is_partial(self):
        from components.evaluator import evaluate_task_outcome

        result = evaluate_task_outcome(
            final_answer="I found some information about the weather.",
            success_conditions=["Provide today's forecast"],
            plan_steps=[{"goal": "Find weather data"}],
            termination_reason="max_steps",
        )
        assert result.outcome == "partial"
        assert result.termination_clean is False

    def test_error_content_is_treated_as_failed(self):
        """Error-formatted content is not a substantive answer."""
        from components.evaluator import evaluate_task_outcome

        result = evaluate_task_outcome(
            final_answer="Error: model returned 401 unauthorized",
            success_conditions=[],
            plan_steps=[],
            termination_reason="failure",
        )
        assert result.outcome == "failed"
        assert result.termination_clean is False

    def test_budget_exceeded_with_answer_is_partial(self):
        from components.evaluator import evaluate_task_outcome

        result = evaluate_task_outcome(
            final_answer="Based on what I found, the answer is approximately 42.",
            success_conditions=["Exact numeric answer required"],
            plan_steps=[],
            termination_reason="budget_exceeded",
        )
        assert result.outcome == "partial"
        assert result.termination_clean is False

    def test_branch_coverage_calculated_from_plan_steps(self):
        from components.evaluator import evaluate_task_outcome

        result = evaluate_task_outcome(
            final_answer="The weather in Austin Texas is sunny and 75 degrees today.",
            success_conditions=[],
            plan_steps=[
                {"goal": "Find current weather in Austin Texas"},
                {"goal": "Report temperature and conditions"},
            ],
            termination_reason="success",
        )
        assert result.outcome == "success"
        assert result.branch_coverage > 0.0

    def test_unmet_conditions_reported(self):
        from components.evaluator import evaluate_task_outcome

        result = evaluate_task_outcome(
            final_answer="Hello world",
            success_conditions=[
                "Provide detailed analysis of quantum computing",
                "Include at least 3 references",
            ],
            plan_steps=[],
            termination_reason="success",
        )
        assert result.outcome == "success"  # Process succeeded
        assert len(result.unmet_conditions) >= 1  # But conditions unmet (informational)

    def test_tool_results_contribute_to_coverage(self):
        from components.evaluator import evaluate_task_outcome

        result = evaluate_task_outcome(
            final_answer="The weather is sunny.",
            success_conditions=[],
            plan_steps=[{"goal": "Search for weather forecast in Austin"}],
            termination_reason="success",
            tool_results=[
                {"tool_output": "Austin Texas weather forecast: sunny, high 75F"},
            ],
        )
        assert result.outcome == "success"
        assert result.branch_coverage > 0.3


class TestI2OutcomeCorrectness:
    """I2: loop-exhaustion (no_progress) must downgrade corrupt-success to partial.

    Failure path first (TAP-4). The Austin symptom: the no-progress wrap-up
    terminates via a clean ``final_answer`` so a naive evaluator scores
    ``success``. Treating ``no_progress`` as unclean fixes the headline bug.
    Goal progress is a separate, NON-gating signal (no determinism theater).
    """

    # ── The corrupt-success fix: no_progress -> partial ──

    def test_no_progress_with_substantive_answer_is_partial(self):
        from components.evaluator import evaluate_task_outcome

        result = evaluate_task_outcome(
            final_answer="Based on the information gathered, the weather looks sunny.",
            success_conditions=[],
            plan_steps=[],
            termination_reason="no_progress",
        )
        assert result.outcome == "partial"
        assert result.termination_clean is False
        assert result.termination_reason == "no_progress"

    def test_no_progress_empty_answer_is_failed(self):
        from components.evaluator import evaluate_task_outcome

        result = evaluate_task_outcome(
            final_answer="",
            success_conditions=[],
            plan_steps=[],
            termination_reason="no_progress",
        )
        assert result.outcome == "failed"
        assert result.termination_clean is False

    def test_clean_success_still_succeeds(self):
        """Sanity: a genuinely clean run is NOT downgraded."""
        from components.evaluator import evaluate_task_outcome

        result = evaluate_task_outcome(
            final_answer="The capital of France is Paris.",
            success_conditions=[],
            plan_steps=[],
            termination_reason="success",
        )
        assert result.outcome == "success"
        assert result.termination_reason == "success"

    # ── goal_met: non-gating goal-progress signal ──

    def test_goal_met_none_when_no_conditions(self):
        from components.evaluator import evaluate_task_outcome

        result = evaluate_task_outcome(
            final_answer="The capital of France is Paris.",
            success_conditions=[],
            plan_steps=[],
            termination_reason="success",
        )
        assert result.goal_met is None

    def test_goal_met_true_when_conditions_satisfied(self):
        from components.evaluator import evaluate_task_outcome

        result = evaluate_task_outcome(
            final_answer="The capital of France is Paris, a major European city.",
            success_conditions=["Identify the capital city of France"],
            plan_steps=[],
            termination_reason="success",
        )
        assert result.goal_met is True

    def test_goal_met_false_when_conditions_unmet(self):
        from components.evaluator import evaluate_task_outcome

        result = evaluate_task_outcome(
            final_answer="Hello world.",
            success_conditions=[
                "Provide a detailed analysis of quantum entanglement experiments",
            ],
            plan_steps=[],
            termination_reason="success",
        )
        assert result.goal_met is False

    def test_goal_met_does_not_change_outcome(self):
        """goal_met=False must NOT downgrade a clean, substantive success."""
        from components.evaluator import evaluate_task_outcome

        result = evaluate_task_outcome(
            final_answer="Here is a thorough and substantive response to the request.",
            success_conditions=[
                "Provide a detailed analysis of quantum entanglement experiments",
            ],
            plan_steps=[],
            termination_reason="success",
        )
        # Process succeeded (clean + substantive) ...
        assert result.outcome == "success"
        # ... even though the keyword-overlap goal signal says the goal is unmet.
        assert result.goal_met is False
