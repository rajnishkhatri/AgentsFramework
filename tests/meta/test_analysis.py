"""L2 Contract: Analytics engine tests (Story 4.1).

Tests metric computation from known JSONL fixtures.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from components.schemas import EvalRecord
from meta.analysis import (
    AgentMetrics,
    OptimizerInput,
    build_optimizer_input,
    compute_metrics,
    compute_sensitivity,
    load_eval_records,
)


def _make_record(**overrides) -> EvalRecord:
    defaults = {
        "task_id": "task-001",
        "user_id": "user-001",
        "step": 0,
        "target": "call_llm",
        "model": "gpt-4o-mini",
        "ai_input": {"task_input": "test"},
        "ai_response": "output",
        "tokens_in": 100,
        "tokens_out": 50,
        "cost_usd": 0.001,
        "latency_ms": 500.0,
        "timestamp": datetime.now(UTC),
    }
    defaults.update(overrides)
    return EvalRecord(**defaults)


class TestComputeMetrics:
    def test_known_fixture_produces_expected_metrics(self):
        records = [
            _make_record(task_id="t1", step=0, cost_usd=0.01),
            _make_record(task_id="t1", step=1, cost_usd=0.02),
            _make_record(task_id="t2", step=0, cost_usd=0.01, error_type="retryable"),
            _make_record(task_id="t3", step=0, cost_usd=0.005),
        ]
        metrics = compute_metrics(records)

        assert metrics.total_tasks == 3
        assert metrics.successful_tasks == 2
        assert metrics.failed_tasks == 1
        assert 0.6 <= metrics.success_rate <= 0.7
        assert metrics.total_cost_usd == pytest.approx(0.045)

    def test_empty_records_produce_zero_metrics(self):
        metrics = compute_metrics([])
        assert metrics.total_tasks == 0
        assert metrics.success_rate == 0.0
        assert metrics.total_cost_usd == 0.0

    def test_model_usage_counts(self):
        records = [
            _make_record(model="gpt-4o-mini", task_id="t1"),
            _make_record(model="gpt-4o-mini", task_id="t2"),
            _make_record(model="gpt-4o", task_id="t3"),
        ]
        metrics = compute_metrics(records)
        assert metrics.model_usage_counts["gpt-4o-mini"] == 2
        assert metrics.model_usage_counts["gpt-4o"] == 1

    def test_error_type_counts(self):
        records = [
            _make_record(task_id="t1", error_type="retryable"),
            _make_record(task_id="t2", error_type="retryable"),
            _make_record(task_id="t3", error_type="terminal"),
            _make_record(task_id="t4"),
        ]
        metrics = compute_metrics(records)
        assert metrics.error_type_counts["retryable"] == 2
        assert metrics.error_type_counts["terminal"] == 1

    def test_rollback_frequency_by_tier(self):
        records = [
            _make_record(model="gpt-4o-mini", task_id="t1"),
            _make_record(model="gpt-4o", task_id="t2"),
        ]
        rollback_data = [
            {"model_tier": "fast", "step": 1},
        ]
        metrics = compute_metrics(records, rollback_data=rollback_data)
        assert "fast" in metrics.rollback_frequency_by_tier

    def test_avg_latency_computation(self):
        records = [
            _make_record(latency_ms=100.0, task_id="t1"),
            _make_record(latency_ms=200.0, task_id="t2"),
            _make_record(latency_ms=300.0, task_id="t3"),
        ]
        metrics = compute_metrics(records)
        assert metrics.avg_latency_ms == pytest.approx(200.0)


class TestLoadEvalRecords:
    def test_load_from_jsonl_file(self, tmp_path):
        jsonl_path = tmp_path / "eval.jsonl"
        records = [_make_record(task_id=f"t{i}") for i in range(3)]
        jsonl_path.write_text(
            "\n".join(r.model_dump_json() for r in records) + "\n"
        )

        loaded = load_eval_records(jsonl_path)
        assert len(loaded) == 3

    def test_load_nonexistent_file_returns_empty(self, tmp_path):
        loaded = load_eval_records(tmp_path / "nonexistent.jsonl")
        assert loaded == []

    def test_load_corrupted_lines_skipped(self, tmp_path):
        jsonl_path = tmp_path / "eval.jsonl"
        good_record = _make_record(task_id="t1")
        jsonl_path.write_text(
            good_record.model_dump_json() + "\n"
            + "THIS IS NOT JSON\n"
            + good_record.model_dump_json() + "\n"
        )
        loaded = load_eval_records(jsonl_path)
        assert len(loaded) == 2


class TestOptimizerInput:
    def test_serialization_roundtrip(self):
        oi = OptimizerInput(
            metrics=AgentMetrics(total_tasks=5, success_rate=0.8),
            config_snapshot={"escalate_after_failures": 2},
            golden_set_scores=[4.0, 3.5, 5.0],
            sensitivity={"escalate_after_failures": 0.1},
        )
        serialized = oi.model_dump_json()
        deserialized = OptimizerInput.model_validate_json(serialized)
        assert deserialized.metrics.total_tasks == 5
        assert deserialized.config_snapshot == {"escalate_after_failures": 2}
        assert deserialized.golden_set_scores == [4.0, 3.5, 5.0]

    def test_default_zero_value(self):
        oi = OptimizerInput()
        assert oi.metrics.total_tasks == 0
        assert oi.config_snapshot == {}
        assert oi.golden_set_scores == []
        assert oi.sensitivity == {}


class TestFailureRateBeforeEscalation:
    def test_fast_failure_then_capable_escalation(self):
        records = [
            _make_record(task_id="t1", model="gpt-4o-mini", error_type="retryable", step=0),
            _make_record(task_id="t1", model="gpt-4o", step=1),
            _make_record(task_id="t2", model="gpt-4o-mini", step=0),
        ]
        metrics = compute_metrics(records)
        assert metrics.failure_rate_before_escalation == pytest.approx(0.5)

    def test_no_escalations_zero_rate(self):
        records = [
            _make_record(task_id="t1", model="gpt-4o-mini", step=0),
            _make_record(task_id="t2", model="gpt-4o-mini", step=0),
        ]
        metrics = compute_metrics(records)
        assert metrics.failure_rate_before_escalation == 0.0

    def test_empty_records_zero_rate(self):
        metrics = compute_metrics([])
        assert metrics.failure_rate_before_escalation == 0.0


class TestComputeSensitivity:
    def test_returns_keys_matching_config(self):
        config = {"escalate_after_failures": 2, "budget_downgrade_threshold": 0.8}
        records = [_make_record(task_id="t1")]
        result = compute_sensitivity(records, config)
        assert "escalate_after_failures" in result
        assert "budget_downgrade_threshold" in result

    def test_empty_records_zero_sensitivity(self):
        config = {"escalate_after_failures": 2}
        result = compute_sensitivity([], config)
        assert result == {"escalate_after_failures": 0.0}

    def test_non_numeric_fields_zero(self):
        config = {"default_model": "gpt-4o-mini", "escalate_after_failures": 2}
        records = [_make_record(task_id="t1")]
        result = compute_sensitivity(records, config)
        assert result["default_model"] == 0.0


class TestBuildOptimizerInput:
    def test_builds_from_records(self):
        records = [
            _make_record(task_id="t1", cost_usd=0.01),
            _make_record(task_id="t2", cost_usd=0.02),
        ]
        config = {"escalate_after_failures": 2}
        oi = build_optimizer_input(records, config_snapshot=config, golden_set_scores=[4.0])
        assert oi.metrics.total_tasks == 2
        assert oi.config_snapshot == config
        assert oi.golden_set_scores == [4.0]
        assert "escalate_after_failures" in oi.sensitivity

    def test_empty_records_zero_optimizer_input(self):
        oi = build_optimizer_input([])
        assert oi.metrics.total_tasks == 0
        assert oi.sensitivity == {}
