"""L2 Contract: Feasibility gate tests (STORY-413).

Tests the LangGraph keep-or-replace decision logic.
"""

from __future__ import annotations

import pytest

from meta.feasibility import FeasibilityGate, FeasibilityReport
from services.observability import FrameworkTelemetry


@pytest.fixture
def gate():
    return FeasibilityGate()


class TestFeasibilityGate:
    def test_all_criteria_met_keep(self, gate):
        telemetry = FrameworkTelemetry(
            checkpoint_invocations=20,  # 20% > 10%
            rollback_invocations=10,
            rollback_time_saved_ms=600_000.0,  # 10 min total, 10 per 100 tasks > 5
            auto_trace_insights=5,  # > 3
        )
        report = gate.evaluate(telemetry, total_tasks=100)
        assert report.keep_langgraph is True
        assert all(report.criteria_met.values())
        assert "KEEP" in report.recommendation

    def test_one_criterion_fails_replace(self, gate):
        telemetry = FrameworkTelemetry(
            checkpoint_invocations=20,
            rollback_invocations=10,
            rollback_time_saved_ms=600_000.0,
            auto_trace_insights=1,  # <= 3, fails
        )
        report = gate.evaluate(telemetry, total_tasks=100)
        assert report.keep_langgraph is False
        assert report.criteria_met["auto_trace_insights"] is False
        assert "REPLACE" in report.recommendation

    def test_all_criteria_fail_replace(self, gate):
        telemetry = FrameworkTelemetry(
            checkpoint_invocations=1,  # 1% <= 10%
            rollback_invocations=0,
            rollback_time_saved_ms=0.0,
            auto_trace_insights=0,
        )
        report = gate.evaluate(telemetry, total_tasks=100)
        assert report.keep_langgraph is False
        assert not any(report.criteria_met.values())

    def test_zero_total_tasks_raises(self, gate):
        telemetry = FrameworkTelemetry()
        with pytest.raises(ValueError, match="total_tasks must be positive"):
            gate.evaluate(telemetry, total_tasks=0)

    def test_boundary_checkpoint_rate(self, gate):
        """Exactly 10% should NOT meet threshold (must be >10%)."""
        telemetry = FrameworkTelemetry(
            checkpoint_invocations=10,  # exactly 10%
            rollback_invocations=10,
            rollback_time_saved_ms=600_000.0,
            auto_trace_insights=5,
        )
        report = gate.evaluate(telemetry, total_tasks=100)
        assert report.criteria_met["checkpoint_usage_rate"] is False

    def test_boundary_rollback_time(self, gate):
        """Exactly 5 min per 100 tasks should NOT meet threshold (must be >5)."""
        telemetry = FrameworkTelemetry(
            checkpoint_invocations=20,
            rollback_invocations=5,
            rollback_time_saved_ms=300_000.0,  # 5 min total = 5 per 100 tasks
            auto_trace_insights=5,
        )
        report = gate.evaluate(telemetry, total_tasks=100)
        assert report.criteria_met["rollback_time_saved"] is False

    def test_boundary_auto_trace_insights(self, gate):
        """Exactly 3 insights should NOT meet threshold (must be >3)."""
        telemetry = FrameworkTelemetry(
            checkpoint_invocations=20,
            rollback_invocations=10,
            rollback_time_saved_ms=600_000.0,
            auto_trace_insights=3,
        )
        report = gate.evaluate(telemetry, total_tasks=100)
        assert report.criteria_met["auto_trace_insights"] is False

    def test_report_serialization_roundtrip(self, gate):
        telemetry = FrameworkTelemetry(
            checkpoint_invocations=20,
            rollback_invocations=10,
            rollback_time_saved_ms=600_000.0,
            auto_trace_insights=5,
        )
        report = gate.evaluate(telemetry, total_tasks=100)
        serialized = report.model_dump_json()
        deserialized = FeasibilityReport.model_validate_json(serialized)
        assert deserialized.keep_langgraph == report.keep_langgraph
