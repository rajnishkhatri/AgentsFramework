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
