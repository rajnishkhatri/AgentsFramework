"""L2 tests for middleware/telemetry_bridge.py — contract-driven TDD.

Tests the domain-event telemetry bridge (Phase 2 of Langfuse GCP Integration plan):
  - Table-driven mapping: each DomainEvent type maps to expected Langfuse event name
  - Skipped events: LLMTokenEmitted, StateMutated, ToolCallEnded produce zero export calls
  - Truncation: args_json and result fields are truncated to 4KB
  - release_trace(): called after run.finished emission
  - Failure path: exporter.export_event() raising does NOT propagate

Layer: L2 (Reproducible Reality)
Strategy: Contract-driven TDD with in-memory exporter stub
Anti-patterns avoided:
  - Tautological (tests assert observable behavior via stub, not algorithm)
  - Mock Addiction (single in-memory stub, not mock framework)
  - Gap Blindness (skip + failure paths tested explicitly)
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agent_ui_adapter.wire.domain_events import (
    DomainEvent,
    LLMMessageEnded,
    LLMMessageStarted,
    LLMTokenEmitted,
    RunFinishedDomain,
    RunStartedDomain,
    StateMutated,
    ToolCallEnded,
    ToolCallStarted,
    ToolResultReceived,
)
from middleware.ports.telemetry_exporter import TelemetryExporter


# ─────────────────────────────────────────────────────────────────────
# In-Memory Exporter Stub
# ─────────────────────────────────────────────────────────────────────


class StubTelemetryExporter:
    """In-memory exporter recording all calls for assertion.

    Satisfies TelemetryExporter protocol without any SDK dependency.
    """

    def __init__(self, *, raise_on_export: bool = False) -> None:
        self.events: list[dict] = []
        self.released_traces: list[str] = []
        self.shutdown_called = False
        self._raise_on_export = raise_on_export

    def export_event(
        self,
        *,
        name: str,
        trace_id: str,
        attributes: dict | None = None,
    ) -> None:
        if self._raise_on_export:
            raise RuntimeError("simulated exporter failure")
        self.events.append(
            {"name": name, "trace_id": trace_id, "attributes": attributes}
        )

    def release_trace(self, trace_id: str) -> None:
        self.released_traces.append(trace_id)

    def shutdown(self) -> None:
        self.shutdown_called = True


@pytest.fixture
def stub_exporter() -> StubTelemetryExporter:
    return StubTelemetryExporter()


# ─────────────────────────────────────────────────────────────────────
# Table-Driven Domain Event Mapping
# ─────────────────────────────────────────────────────────────────────


class TestEmitDomainEvent:
    """emit_domain_event() maps each DomainEvent type to the correct Langfuse name."""

    @pytest.mark.parametrize(
        "domain_event,expected_name,expected_attrs",
        [
            pytest.param(
                RunStartedDomain(
                    trace_id="t1", run_id="run-1", thread_id="thread-1"
                ),
                "run.started",
                {"run_id": "run-1", "thread_id": "thread-1"},
                id="RunStartedDomain",
            ),
            pytest.param(
                RunFinishedDomain(
                    trace_id="t1",
                    run_id="run-1",
                    thread_id="thread-1",
                    error=None,
                ),
                "run.finished",
                {"run_id": "run-1", "thread_id": "thread-1", "error": None},
                id="RunFinishedDomain-no-error",
            ),
            pytest.param(
                RunFinishedDomain(
                    trace_id="t1",
                    run_id="run-1",
                    thread_id="thread-1",
                    error="timeout",
                ),
                "run.finished",
                {"run_id": "run-1", "thread_id": "thread-1", "error": "timeout"},
                id="RunFinishedDomain-with-error",
            ),
            pytest.param(
                ToolCallStarted(
                    trace_id="t1",
                    tool_call_id="tc-1",
                    tool_name="shell",
                    args_json='{"cmd": "ls"}',
                ),
                "tool.started",
                {
                    "tool_name": "shell",
                    "tool_call_id": "tc-1",
                    "args_json": '{"cmd": "ls"}',
                },
                id="ToolCallStarted",
            ),
            pytest.param(
                ToolResultReceived(
                    trace_id="t1",
                    tool_call_id="tc-1",
                    result="file1.txt\nfile2.txt",
                ),
                "tool.finished",
                {"tool_call_id": "tc-1", "result": "file1.txt\nfile2.txt"},
                id="ToolResultReceived",
            ),
            pytest.param(
                LLMMessageStarted(trace_id="t1", message_id="msg-1"),
                "llm.started",
                {"message_id": "msg-1"},
                id="LLMMessageStarted",
            ),
            pytest.param(
                LLMMessageEnded(trace_id="t1", message_id="msg-1"),
                "llm.finished",
                {"message_id": "msg-1"},
                id="LLMMessageEnded",
            ),
        ],
    )
    def test_maps_domain_event_to_langfuse_name(
        self,
        stub_exporter: StubTelemetryExporter,
        domain_event: DomainEvent,
        expected_name: str,
        expected_attrs: dict,
    ) -> None:
        from middleware.telemetry_bridge import emit_domain_event

        emit_domain_event(stub_exporter, domain_event)
        assert len(stub_exporter.events) == 1
        exported = stub_exporter.events[0]
        assert exported["name"] == expected_name
        assert exported["trace_id"] == "t1"
        for key, value in expected_attrs.items():
            assert exported["attributes"][key] == value

    def test_subject_included_in_attributes_when_provided(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_domain_event

        event = RunStartedDomain(
            trace_id="t1", run_id="run-1", thread_id="thread-1"
        )
        emit_domain_event(stub_exporter, event, subject="user@example.com")
        assert stub_exporter.events[0]["attributes"]["subject"] == "user@example.com"

    def test_subject_not_in_attributes_when_none(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_domain_event

        event = RunStartedDomain(
            trace_id="t1", run_id="run-1", thread_id="thread-1"
        )
        emit_domain_event(stub_exporter, event, subject=None)
        assert "subject" not in stub_exporter.events[0]["attributes"]


# ─────────────────────────────────────────────────────────────────────
# Skipped Events (Failure Path: zero export calls)
# ─────────────────────────────────────────────────────────────────────


class TestSkippedEvents:
    """LLMTokenEmitted, StateMutated, ToolCallEnded produce zero export calls."""

    @pytest.mark.parametrize(
        "domain_event",
        [
            pytest.param(
                LLMTokenEmitted(trace_id="t1", message_id="msg-1", delta="hello"),
                id="LLMTokenEmitted-skipped",
            ),
            pytest.param(
                StateMutated(trace_id="t1", snapshot={"key": "value"}),
                id="StateMutated-skipped",
            ),
            pytest.param(
                ToolCallEnded(trace_id="t1", tool_call_id="tc-1"),
                id="ToolCallEnded-skipped",
            ),
        ],
    )
    def test_skipped_event_produces_no_export(
        self,
        stub_exporter: StubTelemetryExporter,
        domain_event: DomainEvent,
    ) -> None:
        from middleware.telemetry_bridge import emit_domain_event

        emit_domain_event(stub_exporter, domain_event)
        assert len(stub_exporter.events) == 0


# ─────────────────────────────────────────────────────────────────────
# Truncation (4KB limit on args_json and result)
# ─────────────────────────────────────────────────────────────────────


class TestTruncation:
    """args_json and result fields are truncated to 4096 bytes."""

    def test_tool_call_started_truncates_args_json(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_domain_event

        large_args = "x" * 8000
        event = ToolCallStarted(
            trace_id="t1",
            tool_call_id="tc-1",
            tool_name="shell",
            args_json=large_args,
        )
        emit_domain_event(stub_exporter, event)
        exported_args = stub_exporter.events[0]["attributes"]["args_json"]
        assert len(exported_args) <= 4096

    def test_tool_result_truncates_result(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_domain_event

        large_result = "y" * 8000
        event = ToolResultReceived(
            trace_id="t1",
            tool_call_id="tc-1",
            result=large_result,
        )
        emit_domain_event(stub_exporter, event)
        exported_result = stub_exporter.events[0]["attributes"]["result"]
        assert len(exported_result) <= 4096

    def test_small_args_not_truncated(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_domain_event

        small_args = '{"cmd": "ls"}'
        event = ToolCallStarted(
            trace_id="t1",
            tool_call_id="tc-1",
            tool_name="shell",
            args_json=small_args,
        )
        emit_domain_event(stub_exporter, event)
        assert stub_exporter.events[0]["attributes"]["args_json"] == small_args


# ─────────────────────────────────────────────────────────────────────
# release_trace() on RunFinishedDomain
# ─────────────────────────────────────────────────────────────────────


class TestReleaseTraceOnFinish:
    """Bridge calls exporter.release_trace(trace_id) after emitting run.finished."""

    def test_release_trace_called_on_run_finished(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_domain_event

        event = RunFinishedDomain(
            trace_id="t1", run_id="run-1", thread_id="thread-1", error=None
        )
        emit_domain_event(stub_exporter, event)
        assert "t1" in stub_exporter.released_traces

    def test_release_trace_not_called_on_other_events(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_domain_event

        event = RunStartedDomain(
            trace_id="t1", run_id="run-1", thread_id="thread-1"
        )
        emit_domain_event(stub_exporter, event)
        assert len(stub_exporter.released_traces) == 0


# ─────────────────────────────────────────────────────────────────────
# emit_run_finished() standalone function
# ─────────────────────────────────────────────────────────────────────


class TestEmitRunFinished:
    """emit_run_finished() emits run.finished event with correct attributes."""

    def test_emits_run_finished_event(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_run_finished

        emit_run_finished(
            stub_exporter,
            trace_id="t1",
            run_id="run-1",
            thread_id="thread-1",
            duration_ms=1500,
            errored=False,
        )
        assert len(stub_exporter.events) == 1
        exported = stub_exporter.events[0]
        assert exported["name"] == "run.finished"
        assert exported["trace_id"] == "t1"
        assert exported["attributes"]["run_id"] == "run-1"
        assert exported["attributes"]["thread_id"] == "thread-1"
        assert exported["attributes"]["duration_ms"] == 1500
        assert exported["attributes"]["errored"] is False

    def test_emits_with_error_flag(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_run_finished

        emit_run_finished(
            stub_exporter,
            trace_id="t1",
            run_id="run-1",
            thread_id="thread-1",
            duration_ms=500,
            errored=True,
        )
        assert stub_exporter.events[0]["attributes"]["errored"] is True

    def test_includes_subject_when_provided(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_run_finished

        emit_run_finished(
            stub_exporter,
            trace_id="t1",
            run_id=None,
            thread_id="thread-1",
            duration_ms=100,
            errored=False,
            subject="user@example.com",
        )
        assert stub_exporter.events[0]["attributes"]["subject"] == "user@example.com"

    def test_releases_trace_after_emit(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_run_finished

        emit_run_finished(
            stub_exporter,
            trace_id="t1",
            run_id="run-1",
            thread_id="thread-1",
            duration_ms=100,
            errored=False,
        )
        assert "t1" in stub_exporter.released_traces

    def test_run_id_none_still_emits(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_run_finished

        emit_run_finished(
            stub_exporter,
            trace_id="t1",
            run_id=None,
            thread_id="thread-1",
            duration_ms=100,
            errored=False,
        )
        assert stub_exporter.events[0]["attributes"]["run_id"] is None


# ─────────────────────────────────────────────────────────────────────
# O1: Telemetry Never Blocks — failure path
# ─────────────────────────────────────────────────────────────────────


class TestTelemetryNeverBlocks:
    """Exporter raising on export_event() does not propagate from bridge."""

    def test_emit_domain_event_swallows_exporter_exception(self) -> None:
        from middleware.telemetry_bridge import emit_domain_event

        broken_exporter = StubTelemetryExporter(raise_on_export=True)
        event = RunStartedDomain(
            trace_id="t1", run_id="run-1", thread_id="thread-1"
        )
        # Must not raise
        emit_domain_event(broken_exporter, event)

    def test_emit_run_finished_swallows_exporter_exception(self) -> None:
        from middleware.telemetry_bridge import emit_run_finished

        broken_exporter = StubTelemetryExporter(raise_on_export=True)
        # Must not raise
        emit_run_finished(
            broken_exporter,
            trace_id="t1",
            run_id="run-1",
            thread_id="thread-1",
            duration_ms=100,
            errored=False,
        )


# ─────────────────────────────────────────────────────────────────────
# Port Protocol Compliance
# ─────────────────────────────────────────────────────────────────────


class TestStubSatisfiesProtocol:
    """StubTelemetryExporter satisfies TelemetryExporter protocol."""

    def test_stub_is_telemetry_exporter(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        assert isinstance(stub_exporter, TelemetryExporter)
