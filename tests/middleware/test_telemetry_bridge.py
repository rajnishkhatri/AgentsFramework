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
        self.flush_called = False
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

    def flush(self) -> None:
        self.flush_called = True


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
                ToolResultReceived(
                    trace_id="t1",
                    tool_call_id="tc-1",
                    result="file1.txt\nfile2.txt",
                ),
                "tool.unknown",
                {"tool_call_id": "tc-1", "result": "file1.txt\nfile2.txt"},
                id="ToolResultReceived-orphan-names-tool.unknown",
            ),
            pytest.param(
                LLMMessageEnded(trace_id="t1", message_id="msg-1"),
                "llm.call",
                {"message_id": "msg-1"},
                id="LLMMessageEnded-names-llm.call",
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
        """Phase 3: ``*.started`` events buffer (zero export); the terminal
        event emits the single merged observation. A ``ToolResultReceived``
        with no prior ``ToolCallStarted`` is an orphan: it still exports, named
        ``tool.unknown`` (tool_name not yet buffered)."""
        from middleware.telemetry_bridge import emit_domain_event

        emit_domain_event(stub_exporter, domain_event)
        assert len(stub_exporter.events) == 1
        exported = stub_exporter.events[0]
        assert exported["name"] == expected_name
        assert exported["trace_id"] == "t1"
        for key, value in expected_attrs.items():
            assert exported["attributes"][key] == value

    @pytest.mark.parametrize(
        "started_event",
        [
            pytest.param(
                ToolCallStarted(
                    trace_id="t1", tool_call_id="tc-1", tool_name="shell",
                    args_json='{"cmd": "ls"}',
                ),
                id="ToolCallStarted-buffers",
            ),
            pytest.param(
                LLMMessageStarted(
                    trace_id="t1", message_id="msg-1", input_text="hi",
                ),
                id="LLMMessageStarted-buffers",
            ),
        ],
    )
    def test_started_events_buffer_and_produce_no_export(
        self, stub_exporter: StubTelemetryExporter, started_event: DomainEvent
    ) -> None:
        """Phase 3: started events are buffered, not exported on their own."""
        from middleware.telemetry_bridge import emit_domain_event

        emit_domain_event(stub_exporter, started_event)
        assert len(stub_exporter.events) == 0

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
    """StateMutated and ToolCallEnded produce zero export calls."""

    @pytest.mark.parametrize(
        "domain_event",
        [
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


class TestLLMContentExport:
    """Phase 3: input, streamed output, model, usage, cost, and latency are
    folded into ONE merged ``llm.call`` generation on LLMMessageEnded."""

    def test_started_plus_tokens_plus_ended_produce_one_llm_call(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_domain_event

        emit_domain_event(
            stub_exporter,
            LLMMessageStarted(
                trace_id="t1",
                message_id="msg-1",
                input_text="user: What is the capital of France?",
            ),
        )
        emit_domain_event(
            stub_exporter,
            LLMTokenEmitted(trace_id="t1", message_id="msg-1", delta="Paris"),
        )
        emit_domain_event(
            stub_exporter,
            LLMTokenEmitted(trace_id="t1", message_id="msg-1", delta=" is the capital."),
        )
        emit_domain_event(stub_exporter, LLMMessageEnded(trace_id="t1", message_id="msg-1"))

        # ONE merged observation (started buffered, not exported).
        assert len(stub_exporter.events) == 1
        merged = stub_exporter.events[0]
        assert merged["name"] == "llm.call"
        attrs = merged["attributes"]
        assert attrs["input_text"].startswith("user:")  # carried from the buffer
        assert attrs["__output"]["content"] == "Paris is the capital."

    def test_merged_call_carries_model_usage_cost(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_domain_event

        emit_domain_event(
            stub_exporter, LLMMessageStarted(trace_id="t1", message_id="m", input_text="q"),
        )
        emit_domain_event(
            stub_exporter,
            LLMMessageEnded(
                trace_id="t1", message_id="m", output_text="a",
                tokens_in=2144, tokens_out=113, cost_usd=0.00039, model="gpt-4o-mini",
            ),
        )
        attrs = stub_exporter.events[0]["attributes"]
        assert attrs["__bb_model"] == "gpt-4o-mini"
        assert attrs["__bb_usage"] == {"input": 2144, "output": 113, "total": 2257}
        assert attrs["__bb_cost"] == 0.00039

    def test_merged_call_carries_latency_ms(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        """latency_ms = wall time from started to ended."""
        import time

        from middleware.telemetry_bridge import emit_domain_event

        emit_domain_event(
            stub_exporter, LLMMessageStarted(trace_id="t1", message_id="m", input_text="q"),
        )
        time.sleep(0.01)
        emit_domain_event(
            stub_exporter, LLMMessageEnded(trace_id="t1", message_id="m", output_text="a"),
        )
        latency = stub_exporter.events[0]["attributes"]["latency_ms"]
        assert latency >= 10.0

    def test_usage_fields_omitted_when_none(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        """Absent usage/cost/model → no __bb_* keys (Langfuse renders nothing)."""
        from middleware.telemetry_bridge import emit_domain_event

        emit_domain_event(
            stub_exporter, LLMMessageStarted(trace_id="t1", message_id="m", input_text="q"),
        )
        emit_domain_event(
            stub_exporter, LLMMessageEnded(trace_id="t1", message_id="m", output_text="a"),
        )
        attrs = stub_exporter.events[0]["attributes"]
        assert "__bb_model" not in attrs
        assert "__bb_usage" not in attrs
        assert "__bb_cost" not in attrs

    def test_llm_token_emitted_alone_produces_no_export(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_domain_event

        emit_domain_event(
            stub_exporter,
            LLMTokenEmitted(trace_id="t1", message_id="msg-1", delta="hello"),
        )
        assert len(stub_exporter.events) == 0


class TestMergedToolCall:
    """Phase 3: ToolCallStarted buffers args; ToolResultReceived emits ONE
    ``tool.{tool_name}`` observation with args + result + latency."""

    def test_started_plus_result_produce_one_named_tool_obs(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_domain_event

        emit_domain_event(
            stub_exporter,
            ToolCallStarted(
                trace_id="t1", tool_call_id="7:c1", tool_name="file_io",
                args_json='{"path": "/x"}',
            ),
        )
        emit_domain_event(
            stub_exporter,
            ToolResultReceived(trace_id="t1", tool_call_id="7:c1", result="12"),
        )

        assert len(stub_exporter.events) == 1
        obs = stub_exporter.events[0]
        assert obs["name"] == "tool.file_io"  # function-named per D-3a
        attrs = obs["attributes"]
        assert attrs["tool_name"] == "file_io"
        assert attrs["args_json"] == '{"path": "/x"}'  # carried from buffer
        assert attrs["__output"]["result"] == "12"
        assert attrs["step"] == 7  # prefix-derived (Phase 2)

    def test_tool_obs_carries_latency_ms(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        import time

        from middleware.telemetry_bridge import emit_domain_event

        emit_domain_event(
            stub_exporter,
            ToolCallStarted(
                trace_id="t1", tool_call_id="c1", tool_name="shell", args_json="{}",
            ),
        )
        time.sleep(0.01)
        emit_domain_event(
            stub_exporter,
            ToolResultReceived(trace_id="t1", tool_call_id="c1", result="ok"),
        )
        assert stub_exporter.events[0]["attributes"]["latency_ms"] >= 10.0

    def test_orphan_result_without_start_exports_tool_unknown(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        """Failure path: result with no prior start → result-only, tool.unknown,
        no raise."""
        from middleware.telemetry_bridge import emit_domain_event

        emit_domain_event(
            stub_exporter,
            ToolResultReceived(trace_id="t1", tool_call_id="orphan", result="r"),
        )
        assert len(stub_exporter.events) == 1
        obs = stub_exporter.events[0]
        assert obs["name"] == "tool.unknown"
        assert obs["attributes"]["__output"]["result"] == "r"
        assert "args_json" not in obs["attributes"]


class TestOrphanAndCleanup:
    """Failure paths and per-trace buffer hygiene (no cross-run leakage)."""

    def test_orphan_llm_ended_without_started_exports_output_only(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import emit_domain_event

        emit_domain_event(
            stub_exporter,
            LLMMessageEnded(trace_id="t1", message_id="never-started", output_text="a"),
        )
        assert len(stub_exporter.events) == 1
        obs = stub_exporter.events[0]
        assert obs["name"] == "llm.call"
        assert obs["attributes"]["__output"]["content"] == "a"
        assert "input_text" not in obs["attributes"]  # no buffered input

    def test_run_finished_clears_all_per_trace_buffers(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        """Started-but-never-finished calls do not leak after release."""
        from middleware.telemetry_bridge import (
            _llm_start_buffers,
            _tool_start_buffers,
            _llm_token_buffers,
            emit_domain_event,
        )

        emit_domain_event(
            stub_exporter, LLMMessageStarted(trace_id="t-leak", message_id="m", input_text="q"),
        )
        emit_domain_event(
            stub_exporter,
            ToolCallStarted(
                trace_id="t-leak", tool_call_id="c", tool_name="shell", args_json="{}",
            ),
        )
        emit_domain_event(
            stub_exporter, LLMTokenEmitted(trace_id="t-leak", message_id="m", delta="x"),
        )
        # Buffers are populated mid-run.
        assert any(k[0] == "t-leak" for k in _llm_start_buffers)
        assert any(k[0] == "t-leak" for k in _tool_start_buffers)

        emit_domain_event(
            stub_exporter,
            RunFinishedDomain(trace_id="t-leak", run_id="r", thread_id="th", error=None),
        )

        # All per-trace buffers for this trace are gone.
        assert not any(k[0] == "t-leak" for k in _llm_start_buffers)
        assert not any(k[0] == "t-leak" for k in _tool_start_buffers)
        assert not any(k[0] == "t-leak" for k in _llm_token_buffers)

    def test_buffer_cleanup_does_not_touch_other_traces(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        from middleware.telemetry_bridge import (
            _llm_start_buffers,
            emit_domain_event,
        )

        emit_domain_event(
            stub_exporter, LLMMessageStarted(trace_id="keep", message_id="m", input_text="q"),
        )
        emit_domain_event(
            stub_exporter, LLMMessageStarted(trace_id="drop", message_id="m", input_text="q"),
        )
        emit_domain_event(
            stub_exporter,
            RunFinishedDomain(trace_id="drop", run_id="r", thread_id="th", error=None),
        )
        assert any(k[0] == "keep" for k in _llm_start_buffers)
        assert not any(k[0] == "drop" for k in _llm_start_buffers)


# ─────────────────────────────────────────────────────────────────────
# Truncation (4KB limit on args_json and result)
# ─────────────────────────────────────────────────────────────────────


class TestTruncation:
    """args_json and result fields are truncated to 4096 bytes."""

    def test_tool_call_started_truncates_args_json(
        self, stub_exporter: StubTelemetryExporter
    ) -> None:
        """Phase 3: args buffer on start (truncated) and surface on the merged
        tool obs emitted by ToolResultReceived."""
        from middleware.telemetry_bridge import emit_domain_event

        large_args = "x" * 8000
        emit_domain_event(
            stub_exporter,
            ToolCallStarted(
                trace_id="t1", tool_call_id="tc-1", tool_name="shell",
                args_json=large_args,
            ),
        )
        emit_domain_event(
            stub_exporter,
            ToolResultReceived(trace_id="t1", tool_call_id="tc-1", result="ok"),
        )
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
        emit_domain_event(
            stub_exporter,
            ToolCallStarted(
                trace_id="t1", tool_call_id="tc-1", tool_name="shell",
                args_json=small_args,
            ),
        )
        emit_domain_event(
            stub_exporter,
            ToolResultReceived(trace_id="t1", tool_call_id="tc-1", result="ok"),
        )
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
