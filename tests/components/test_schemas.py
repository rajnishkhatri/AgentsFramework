"""L1 Deterministic: Tests for components/schemas.py.

Pure TDD (Red-Green-Refactor). Tests behavioral properties of
ErrorRecord, StepResult, EvalRecord, TaskResult. Failure paths
first per TDD Anti-Pattern 6 (Gap Blindness).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from components.schemas import ErrorRecord, EvalRecord, StepResult, TaskResult


class TestErrorRecord:
    def test_valid_construction(self):
        rec = ErrorRecord(
            step=1,
            error_type="retryable",
            message="Rate limit exceeded",
            model="gpt-4o-mini",
            timestamp=1713400000.0,
        )
        assert rec.step == 1
        assert rec.error_type == "retryable"

    def test_optional_error_code(self):
        rec = ErrorRecord(
            step=1,
            error_type="retryable",
            error_code=429,
            message="Rate limit",
            model="gpt-4o-mini",
            timestamp=1713400000.0,
        )
        assert rec.error_code == 429

    def test_error_code_defaults_none(self):
        rec = ErrorRecord(
            step=1,
            error_type="retryable",
            message="Timeout",
            model="gpt-4o-mini",
            timestamp=1713400000.0,
        )
        assert rec.error_code is None

    def test_rejects_missing_required_field(self):
        with pytest.raises(ValidationError):
            ErrorRecord(step=1, error_type="retryable")  # type: ignore[call-arg]

    def test_roundtrip_json(self):
        rec = ErrorRecord(
            step=2,
            error_type="model_error",
            message="Bad output",
            model="gpt-4o",
            timestamp=1713400000.0,
        )
        restored = ErrorRecord.model_validate_json(rec.model_dump_json())
        assert restored == rec


class TestStepResult:
    def test_valid_construction(self):
        sr = StepResult(
            step_id=1,
            action="tool_call",
            model_used="gpt-4o-mini",
            routing_reason="phase1-trivial",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
            latency_ms=500.0,
            outcome="success",
            reasoning="Completed successfully",
        )
        assert sr.step_id == 1
        assert sr.tool_name is None
        assert sr.error_type is None

    def test_tool_fields_populated(self):
        sr = StepResult(
            step_id=1,
            action="tool_call",
            model_used="gpt-4o-mini",
            routing_reason="phase1-trivial",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
            latency_ms=500.0,
            tool_name="shell",
            tool_input={"command": "ls"},
            tool_output="file1.txt",
            outcome="success",
            reasoning="Tool executed",
        )
        assert sr.tool_name == "shell"
        assert sr.tool_input == {"command": "ls"}

    def test_rejects_missing_outcome(self):
        with pytest.raises(ValidationError):
            StepResult(
                step_id=1,
                action="tool_call",
                model_used="gpt-4o-mini",
                routing_reason="test",
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                latency_ms=0.0,
                reasoning="x",
            )  # type: ignore[call-arg]

    def test_roundtrip_json(self):
        sr = StepResult(
            step_id=3,
            action="answer",
            model_used="gpt-4o",
            routing_reason="escalation",
            input_tokens=200,
            output_tokens=150,
            cost_usd=0.01,
            latency_ms=1200.0,
            outcome="success",
            reasoning="Final answer produced",
        )
        restored = StepResult.model_validate_json(sr.model_dump_json())
        assert restored == sr


class TestEvalRecord:
    def test_valid_construction(self):
        rec = EvalRecord(
            timestamp=datetime.now(UTC),
            task_id="task-001",
            user_id="user-123",
            step=1,
            target="call_llm",
            ai_input={"messages": [{"role": "user", "content": "hi"}]},
            ai_response={"content": "hello"},
        )
        assert rec.schema_version == 1
        assert rec.target == "call_llm"

    def test_schema_version_defaults_to_one(self):
        rec = EvalRecord(
            timestamp=datetime.now(UTC),
            task_id="t1",
            user_id="u1",
            step=0,
            target="guardrail",
            ai_input={},
            ai_response="ok",
        )
        assert rec.schema_version == 1

    def test_optional_fields_default_none(self):
        rec = EvalRecord(
            timestamp=datetime.now(UTC),
            task_id="t1",
            user_id="u1",
            step=0,
            target="call_llm",
            ai_input={},
            ai_response={},
        )
        assert rec.model is None
        assert rec.tokens_in is None
        assert rec.tokens_out is None
        assert rec.cost_usd is None
        assert rec.latency_ms is None
        assert rec.error_type is None

    def test_rejects_missing_task_id(self):
        with pytest.raises(ValidationError):
            EvalRecord(
                timestamp=datetime.now(UTC),
                user_id="u1",
                step=0,
                target="call_llm",
                ai_input={},
                ai_response={},
            )  # type: ignore[call-arg]

    def test_roundtrip_json(self):
        rec = EvalRecord(
            timestamp=datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC),
            task_id="t1",
            user_id="u1",
            step=1,
            target="call_llm",
            model="gpt-4o-mini",
            ai_input={"prompt": "test"},
            ai_response={"answer": "done"},
            tokens_in=100,
            tokens_out=50,
            cost_usd=0.001,
            latency_ms=500.0,
        )
        restored = EvalRecord.model_validate_json(rec.model_dump_json())
        assert restored == rec


class TestTaskResult:
    def test_valid_construction(self):
        tr = TaskResult(
            task_id="task-001",
            task_input="What is 2+2?",
            steps=[],
            final_answer="4",
            total_cost_usd=0.001,
            total_latency_ms=500.0,
            total_steps=1,
            status="completed",
        )
        assert tr.status == "completed"
        assert tr.final_answer == "4"

    def test_final_answer_optional(self):
        tr = TaskResult(
            task_id="t1",
            task_input="fail",
            steps=[],
            total_cost_usd=0.0,
            total_latency_ms=0.0,
            total_steps=0,
            status="failed",
        )
        assert tr.final_answer is None

    def test_rejects_missing_status(self):
        with pytest.raises(ValidationError):
            TaskResult(
                task_id="t1",
                task_input="x",
                steps=[],
                total_cost_usd=0.0,
                total_latency_ms=0.0,
                total_steps=0,
            )  # type: ignore[call-arg]

    def test_roundtrip_json(self):
        step = StepResult(
            step_id=1,
            action="answer",
            model_used="gpt-4o-mini",
            routing_reason="trivial",
            input_tokens=50,
            output_tokens=20,
            cost_usd=0.0005,
            latency_ms=300.0,
            outcome="success",
            reasoning="Direct answer",
        )
        tr = TaskResult(
            task_id="t1",
            task_input="hi",
            steps=[step],
            final_answer="hello",
            total_cost_usd=0.0005,
            total_latency_ms=300.0,
            total_steps=1,
            status="completed",
        )
        restored = TaskResult.model_validate_json(tr.model_dump_json())
        assert restored == tr
