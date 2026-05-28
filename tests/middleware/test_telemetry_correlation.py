"""Phase 7 — Trace Correlation Health & Event Completeness Verification.

L2 tests (Reproducible Reality) that fill the gap between Phase 5 unit
tests and the Phase 6 manual human verification checklist.

Test categories (mapped to ``research/tdd_agentic_systems_prompt.md``):

  A3  Event Completeness Guard — every ``DomainEvent`` subclass is either
      mapped to a Langfuse event name OR explicitly marked as skipped. A
      10th event type added to ``domain_events.py`` breaks these tests
      until ``telemetry_bridge.py`` is updated.

  B1  Concurrent Trace Isolation — interleaved runs with different
      ``trace_id`` values never cross-contaminate exporter trace handles
      or child spans.

  Pattern 11  Trace Handle Lifecycle Failure Mode Matrix — edge-case
              scenarios for ``release_trace`` and handle re-creation.

  Pattern 4  Full Vertical Integration — domain events piped through the
             bridge into the exporter with a mock SDK client, verifying
             end-to-end data shapes (consumer-driven contract).

Layer: L2 (Reproducible Reality)
Strategy: Contract-driven TDD with in-memory stubs / fake SDK
CI/CD: Every commit, <30s
Anti-patterns avoided:
  - Gap Blindness (completeness + concurrency + lifecycle exhaustively covered)
  - Mock Addiction (real in-memory FakeLangfuseClient, not MagicMock)
  - Tautological (tests assert observable output, not algorithm)
"""

from __future__ import annotations

from typing import Any, get_args

import pytest

from agent_ui_adapter.wire.domain_events import (
    DomainEvent,
    DomainEventBase,
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
from middleware.adapters.observability.langfuse_cloud_exporter import (
    LangfuseCloudExporter,
)
from middleware.ports.telemetry_exporter import TelemetryExporter
from middleware.telemetry_bridge import (
    _SKIPPED_TYPES,
    _build_attributes,
    emit_domain_event,
    emit_run_finished,
)


# ─────────────────────────────────────────────────────────────────────
# Shared Stubs
# ─────────────────────────────────────────────────────────────────────


class StubTelemetryExporter:
    """In-memory exporter recording all calls for assertion."""

    def __init__(self, *, raise_on_export: bool = False) -> None:
        self.events: list[dict] = []
        self.released_traces: list[str] = []
        self.shutdown_called = False
        self._raise_on_export = raise_on_export

    def export_event(
        self, *, name: str, trace_id: str, attributes: dict | None = None
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


class FakeObservation:
    def __init__(self, data: dict) -> None:
        self.data = data

    def end(self) -> None:
        pass


class FakeLangfuseClient:
    """In-memory stand-in for the Langfuse SDK v4 client."""

    def __init__(self) -> None:
        self.traces: dict[str, dict] = {}
        self.spans: list[dict] = []
        self.flushed = False

    def start_observation(
        self,
        *,
        trace_context: dict | None = None,
        name: str,
        as_type: str = "span",
        input: dict | None = None,
        metadata: dict | None = None,
        **kw,
    ) -> FakeObservation:
        trace_id = (trace_context or {}).get("trace_id", "unknown")
        if trace_id not in self.traces:
            self.traces[trace_id] = {"id": trace_id}
        data = {
            "trace_id": trace_id,
            "name": name,
            "input": input,
            "as_type": as_type,
            "metadata": metadata,
            **kw,
        }
        self.spans.append(data)
        return FakeObservation(data)

    def flush(self) -> None:
        self.flushed = True


@pytest.fixture
def stub() -> StubTelemetryExporter:
    return StubTelemetryExporter()


@pytest.fixture
def fake_client() -> FakeLangfuseClient:
    return FakeLangfuseClient()


@pytest.fixture
def exporter(fake_client: FakeLangfuseClient) -> LangfuseCloudExporter:
    return LangfuseCloudExporter(
        public_key="pk-test",
        secret_key="sk-test",
        host="https://cloud.langfuse.com",
        sdk_client=fake_client,
    )


# ═════════════════════════════════════════════════════════════════════
# A3: Event Completeness Guard
# ═════════════════════════════════════════════════════════════════════


class TestEventCompleteness:
    """Every DomainEvent subclass is accounted for in the bridge.

    If a developer adds a 10th DomainEvent type to domain_events.py,
    this test suite breaks until telemetry_bridge.py is updated.
    Prevents silent event loss (Gap Blindness anti-pattern).
    """

    # The union type lists all 9 concrete event types.
    ALL_EVENT_TYPES: set[type] = set(get_args(DomainEvent))

    MAPPED_TYPES: set[type] = {
        RunStartedDomain,
        RunFinishedDomain,
        ToolCallStarted,
        ToolResultReceived,
        LLMMessageStarted,
        LLMMessageEnded,
    }

    SKIPPED_TYPES: set[type] = {
        LLMTokenEmitted,
        StateMutated,
        ToolCallEnded,
    }

    def test_mapped_plus_skipped_equals_all(self) -> None:
        """Union of mapped + skipped must equal all DomainEvent types."""
        covered = self.MAPPED_TYPES | self.SKIPPED_TYPES
        assert covered == self.ALL_EVENT_TYPES, (
            f"Uncovered types: {self.ALL_EVENT_TYPES - covered}; "
            f"Extra types: {covered - self.ALL_EVENT_TYPES}"
        )

    def test_mapped_and_skipped_are_disjoint(self) -> None:
        """No type appears in both mapped and skipped."""
        overlap = self.MAPPED_TYPES & self.SKIPPED_TYPES
        assert overlap == set(), f"Overlapping types: {overlap}"

    def test_skipped_types_constant_matches_bridge(self) -> None:
        """The bridge's internal _SKIPPED_TYPES matches our expectation."""
        bridge_skipped = set(_SKIPPED_TYPES)
        assert bridge_skipped == self.SKIPPED_TYPES

    @pytest.mark.parametrize("event_type", sorted(MAPPED_TYPES, key=lambda t: t.__name__))
    def test_mapped_type_produces_export_call(
        self, stub: StubTelemetryExporter, event_type: type
    ) -> None:
        """Every mapped type produces exactly one export call."""
        event = _make_event(event_type)
        emit_domain_event(stub, event)
        assert len(stub.events) == 1, (
            f"{event_type.__name__} should produce 1 export call"
        )

    @pytest.mark.parametrize("event_type", sorted(SKIPPED_TYPES, key=lambda t: t.__name__))
    def test_skipped_type_produces_zero_calls(
        self, stub: StubTelemetryExporter, event_type: type
    ) -> None:
        """Every skipped type produces zero export calls."""
        event = _make_event(event_type)
        emit_domain_event(stub, event)
        assert len(stub.events) == 0, (
            f"{event_type.__name__} should produce 0 export calls"
        )

    def test_unknown_event_type_returns_none_from_build_attributes(self) -> None:
        """An unrecognized event type returns None (safe default)."""

        class UnknownDomainEvent(DomainEventBase):
            custom_field: str = "test"

            model_config = DomainEventBase.model_config

        event = UnknownDomainEvent(trace_id="t-unknown")
        result = _build_attributes(event, subject=None)
        assert result is None, "Unknown event type must return None, not raise"

    def test_event_count_matches_union(self) -> None:
        """Guard: domain_events.DomainEvent union has exactly 9 members."""
        assert len(self.ALL_EVENT_TYPES) == 9, (
            f"Expected 9 DomainEvent types, got {len(self.ALL_EVENT_TYPES)}. "
            "Update telemetry_bridge.py and this test."
        )


# ═════════════════════════════════════════════════════════════════════
# B1: Cross-Plane Trace ID Correlation
# ═════════════════════════════════════════════════════════════════════


class TestTraceidCorrelation:
    """All export calls for one run share the same trace_id.

    Verifies the contract that downstream consumers (GCS sink, Cloud
    Logging) can join on trace_id.
    """

    def test_all_events_same_run_share_trace_id(
        self, stub: StubTelemetryExporter
    ) -> None:
        """Every export call for a single run carries the same trace_id."""
        trace_id = "corr-trace-001"
        events = _make_full_run(trace_id, run_id="r-1", thread_id="th-1")
        for ev in events:
            emit_domain_event(stub, ev)
        for exported in stub.events:
            assert exported["trace_id"] == trace_id

    def test_run_finished_safety_net_uses_same_trace_id(
        self, stub: StubTelemetryExporter
    ) -> None:
        """emit_run_finished() (safety-net path) uses the given trace_id."""
        emit_run_finished(
            stub,
            trace_id="corr-trace-002",
            run_id="r-2",
            thread_id="th-2",
            duration_ms=500,
            errored=True,
        )
        assert stub.events[0]["trace_id"] == "corr-trace-002"

    def test_release_trace_uses_same_trace_id(
        self, stub: StubTelemetryExporter
    ) -> None:
        """release_trace is called with the correct trace_id on run.finished."""
        event = RunFinishedDomain(
            trace_id="corr-trace-003", run_id="r-3", thread_id="th-3", error=None
        )
        emit_domain_event(stub, event)
        assert "corr-trace-003" in stub.released_traces


# ═════════════════════════════════════════════════════════════════════
# Concurrent Trace Isolation
# ═════════════════════════════════════════════════════════════════════


class TestConcurrentTraceIsolation:
    """Interleaved runs with different trace_ids must not cross-contaminate."""

    def test_interleaved_traces_stay_isolated_in_bridge(
        self, stub: StubTelemetryExporter
    ) -> None:
        """Two interleaved runs produce events tagged with their own trace_id."""
        emit_domain_event(
            stub,
            RunStartedDomain(trace_id="t-A", run_id="rA", thread_id="thA"),
        )
        emit_domain_event(
            stub,
            RunStartedDomain(trace_id="t-B", run_id="rB", thread_id="thB"),
        )
        emit_domain_event(
            stub,
            ToolCallStarted(
                trace_id="t-A", tool_call_id="tc-A1", tool_name="shell",
                args_json="{}",
            ),
        )
        emit_domain_event(
            stub,
            ToolCallStarted(
                trace_id="t-B", tool_call_id="tc-B1", tool_name="file",
                args_json="{}",
            ),
        )

        a_events = [e for e in stub.events if e["trace_id"] == "t-A"]
        b_events = [e for e in stub.events if e["trace_id"] == "t-B"]
        assert len(a_events) == 2
        assert len(b_events) == 2

    def test_interleaved_traces_produce_separate_sdk_traces(
        self,
        exporter: LangfuseCloudExporter,
        fake_client: FakeLangfuseClient,
    ) -> None:
        """Two trace_ids create two separate Langfuse traces in the SDK."""
        exporter.export_event(name="run.started", trace_id="t-X")
        exporter.export_event(name="run.started", trace_id="t-Y")
        exporter.export_event(
            name="tool.started", trace_id="t-X",
            attributes={"tool_name": "shell"},
        )
        exporter.export_event(
            name="tool.started", trace_id="t-Y",
            attributes={"tool_name": "file"},
        )
        assert len(fake_client.traces) == 2
        assert "t-X" in fake_client.traces
        assert "t-Y" in fake_client.traces

    def test_interleaved_spans_belong_to_correct_trace(
        self,
        exporter: LangfuseCloudExporter,
        fake_client: FakeLangfuseClient,
    ) -> None:
        """Child spans are attached to the correct parent trace."""
        exporter.export_event(name="run.started", trace_id="t-X")
        exporter.export_event(name="run.started", trace_id="t-Y")
        exporter.export_event(
            name="tool.started", trace_id="t-X",
            attributes={"tool_name": "shell"},
        )
        exporter.export_event(
            name="llm.started", trace_id="t-Y",
            attributes={"message_id": "m-1"},
        )

        x_spans = [s for s in fake_client.spans if s["trace_id"] == "t-X"]
        y_spans = [s for s in fake_client.spans if s["trace_id"] == "t-Y"]
        assert len(x_spans) == 2  # run.started + tool.started
        assert len(y_spans) == 2  # run.started + llm.started
        assert x_spans[1]["name"] == "tool.started"
        assert y_spans[1]["name"] == "llm.started"

    def test_release_one_trace_does_not_affect_other(
        self,
        exporter: LangfuseCloudExporter,
        fake_client: FakeLangfuseClient,
    ) -> None:
        """Releasing trace A does not drop trace B's handle."""
        exporter.export_event(name="run.started", trace_id="t-A")
        exporter.export_event(name="run.started", trace_id="t-B")
        exporter.release_trace("t-A")
        assert exporter.active_trace_count == 1
        exporter.export_event(
            name="tool.started", trace_id="t-B",
            attributes={"tool_name": "shell"},
        )
        b_spans = [s for s in fake_client.spans if s["trace_id"] == "t-B"]
        assert len(b_spans) == 2  # run.started + tool.started


# ═════════════════════════════════════════════════════════════════════
# Trace Handle Lifecycle — Failure Mode Matrix (Pattern 11)
# ═════════════════════════════════════════════════════════════════════


class TestTraceHandleLifecycle:
    """Failure mode matrix for the exporter's in-memory trace handle dict.

    Ordered failure-path-first per TDD §Operating Principle 4.
    """

    # ── Failure paths ────────────────────────────────────────────────

    def test_release_before_any_export_is_noop(
        self, exporter: LangfuseCloudExporter
    ) -> None:
        exporter.release_trace("never-seen")
        assert exporter.active_trace_count == 0

    def test_double_release_is_noop(
        self, exporter: LangfuseCloudExporter
    ) -> None:
        exporter.export_event(name="run.started", trace_id="t-1")
        exporter.release_trace("t-1")
        exporter.release_trace("t-1")  # second release must not raise
        assert exporter.active_trace_count == 0

    def test_export_after_release_creates_new_handle(
        self,
        exporter: LangfuseCloudExporter,
        fake_client: FakeLangfuseClient,
    ) -> None:
        """After releasing, a new export opens a fresh trace handle."""
        exporter.export_event(name="run.started", trace_id="t-1")
        exporter.release_trace("t-1")
        assert exporter.active_trace_count == 0
        exporter.export_event(name="run.started", trace_id="t-1")
        assert exporter.active_trace_count == 1
        # The SDK trace() was called twice (once per open)
        assert len(fake_client.spans) == 2

    # ── Happy paths ──────────────────────────────────────────────────

    def test_active_trace_count_tracks_open_handles(
        self, exporter: LangfuseCloudExporter
    ) -> None:
        assert exporter.active_trace_count == 0
        exporter.export_event(name="run.started", trace_id="t-1")
        assert exporter.active_trace_count == 1
        exporter.export_event(name="run.started", trace_id="t-2")
        assert exporter.active_trace_count == 2
        exporter.release_trace("t-1")
        assert exporter.active_trace_count == 1
        exporter.release_trace("t-2")
        assert exporter.active_trace_count == 0

    def test_shutdown_flushes_with_open_handles(
        self,
        exporter: LangfuseCloudExporter,
        fake_client: FakeLangfuseClient,
    ) -> None:
        """shutdown() calls flush even when trace handles are still open."""
        exporter.export_event(name="run.started", trace_id="t-1")
        exporter.shutdown()
        assert fake_client.flushed is True

    def test_many_traces_all_releasable(
        self, exporter: LangfuseCloudExporter
    ) -> None:
        """Stress: 100 concurrent traces can all be opened and released."""
        for i in range(100):
            exporter.export_event(name="run.started", trace_id=f"t-{i}")
        assert exporter.active_trace_count == 100
        for i in range(100):
            exporter.release_trace(f"t-{i}")
        assert exporter.active_trace_count == 0


# ═════════════════════════════════════════════════════════════════════
# Full Vertical Integration (Pattern 4: Consumer-Driven Contract)
# Domain Events → Bridge → Exporter → Mock SDK
# ═════════════════════════════════════════════════════════════════════


class TestVerticalIntegration:
    """End-to-end data flow: domain events piped through the bridge into
    the exporter with a mock SDK client.

    Verifies the consumer contract: the SDK receives correctly-structured
    traces and child spans with the expected names and attributes.
    """

    def test_full_run_produces_one_trace_with_child_spans(
        self,
        exporter: LangfuseCloudExporter,
        fake_client: FakeLangfuseClient,
    ) -> None:
        """A complete run lifecycle produces 1 SDK trace with N child spans."""
        trace_id = "vert-001"
        events = _make_full_run(trace_id, run_id="r-1", thread_id="th-1")
        for ev in events:
            emit_domain_event(exporter, ev)

        assert len(fake_client.traces) == 1
        assert trace_id in fake_client.traces

        span_names = [s["name"] for s in fake_client.spans]
        assert span_names == [
            "run.started",
            "llm.started",
            "llm.finished",
            "tool.started",
            "tool.finished",
            "run.finished",
        ]

    def test_span_attributes_carry_tool_details(
        self,
        exporter: LangfuseCloudExporter,
        fake_client: FakeLangfuseClient,
    ) -> None:
        """tool.started span carries tool_name and tool_call_id."""
        event = ToolCallStarted(
            trace_id="vert-002",
            tool_call_id="tc-99",
            tool_name="file_write",
            args_json='{"path": "/tmp/x"}',
        )
        emit_domain_event(exporter, event)

        assert len(fake_client.spans) == 1
        span_input = fake_client.spans[0]["input"]
        assert span_input["tool_name"] == "file_write"
        assert span_input["tool_call_id"] == "tc-99"
        assert span_input["args_json"] == '{"path": "/tmp/x"}'

    def test_span_attributes_carry_llm_message_id(
        self,
        exporter: LangfuseCloudExporter,
        fake_client: FakeLangfuseClient,
    ) -> None:
        """llm.started span carries message_id."""
        event = LLMMessageStarted(trace_id="vert-003", message_id="msg-42")
        emit_domain_event(exporter, event)

        assert fake_client.spans[0]["input"]["message_id"] == "msg-42"

    def test_run_finished_with_error_carries_error_detail(
        self,
        exporter: LangfuseCloudExporter,
        fake_client: FakeLangfuseClient,
    ) -> None:
        """run.finished span carries error field when stream errored."""
        event = RunFinishedDomain(
            trace_id="vert-004",
            run_id="r-err",
            thread_id="th-err",
            error="context_window_exceeded",
        )
        emit_domain_event(exporter, event)

        span = fake_client.spans[0]
        assert span["name"] == "run.finished"
        assert span["input"]["error"] == "context_window_exceeded"

    def test_skipped_events_produce_no_sdk_calls(
        self,
        exporter: LangfuseCloudExporter,
        fake_client: FakeLangfuseClient,
    ) -> None:
        """Skipped events (token, state, tool_ended) produce zero SDK calls."""
        skipped_events = [
            LLMTokenEmitted(trace_id="vert-005", message_id="m-1", delta="hi"),
            StateMutated(trace_id="vert-005", snapshot={"k": "v"}),
            ToolCallEnded(trace_id="vert-005", tool_call_id="tc-1"),
        ]
        for ev in skipped_events:
            emit_domain_event(exporter, ev)
        assert len(fake_client.traces) == 0
        assert len(fake_client.spans) == 0

    def test_release_trace_clears_handle_after_full_run(
        self,
        exporter: LangfuseCloudExporter,
        fake_client: FakeLangfuseClient,
    ) -> None:
        """Bridge's RunFinishedDomain handler calls release_trace, clearing
        the in-memory handle so no trace leak occurs."""
        events = _make_full_run("vert-006", run_id="r-6", thread_id="th-6")
        for ev in events:
            emit_domain_event(exporter, ev)
        assert exporter.active_trace_count == 0

    def test_subject_flows_through_entire_pipeline(
        self,
        exporter: LangfuseCloudExporter,
        fake_client: FakeLangfuseClient,
    ) -> None:
        """Subject attribute flows from bridge caller through to SDK span."""
        event = RunStartedDomain(
            trace_id="vert-007", run_id="r-7", thread_id="th-7"
        )
        emit_domain_event(exporter, event, subject="user@corp.com")
        span_input = fake_client.spans[0]["input"]
        assert span_input["subject"] == "user@corp.com"

    def test_truncation_honored_through_full_pipeline(
        self,
        exporter: LangfuseCloudExporter,
        fake_client: FakeLangfuseClient,
    ) -> None:
        """4KB truncation from bridge is preserved in SDK span input."""
        large_args = "A" * 8000
        event = ToolCallStarted(
            trace_id="vert-008",
            tool_call_id="tc-big",
            tool_name="shell",
            args_json=large_args,
        )
        emit_domain_event(exporter, event)
        sdk_args = fake_client.spans[0]["input"]["args_json"]
        assert len(sdk_args) <= 4096


# ═════════════════════════════════════════════════════════════════════
# Port Protocol Compliance
# ═════════════════════════════════════════════════════════════════════


class TestPortProtocolCompliance:
    """Verify stubs satisfy TelemetryExporter Protocol."""

    def test_stub_satisfies_protocol(self, stub: StubTelemetryExporter) -> None:
        assert isinstance(stub, TelemetryExporter)


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════


def _make_event(event_type: type, trace_id: str = "t-test") -> Any:
    """Construct a minimal valid instance of the given DomainEvent type."""
    if event_type is RunStartedDomain:
        return RunStartedDomain(trace_id=trace_id, run_id="r-1", thread_id="th-1")
    if event_type is RunFinishedDomain:
        return RunFinishedDomain(
            trace_id=trace_id, run_id="r-1", thread_id="th-1", error=None
        )
    if event_type is ToolCallStarted:
        return ToolCallStarted(
            trace_id=trace_id, tool_call_id="tc-1", tool_name="shell",
            args_json='{"cmd":"ls"}',
        )
    if event_type is ToolResultReceived:
        return ToolResultReceived(
            trace_id=trace_id, tool_call_id="tc-1", result="output"
        )
    if event_type is ToolCallEnded:
        return ToolCallEnded(trace_id=trace_id, tool_call_id="tc-1")
    if event_type is LLMMessageStarted:
        return LLMMessageStarted(trace_id=trace_id, message_id="msg-1")
    if event_type is LLMMessageEnded:
        return LLMMessageEnded(trace_id=trace_id, message_id="msg-1")
    if event_type is LLMTokenEmitted:
        return LLMTokenEmitted(trace_id=trace_id, message_id="msg-1", delta="hi")
    if event_type is StateMutated:
        return StateMutated(trace_id=trace_id, snapshot={"k": "v"})
    raise ValueError(f"Unknown event type: {event_type}")


def _make_full_run(
    trace_id: str, *, run_id: str, thread_id: str
) -> list[DomainEvent]:
    """Construct a realistic full-run event sequence (6 exported events)."""
    return [
        RunStartedDomain(trace_id=trace_id, run_id=run_id, thread_id=thread_id),
        LLMMessageStarted(trace_id=trace_id, message_id="msg-1"),
        LLMMessageEnded(trace_id=trace_id, message_id="msg-1"),
        ToolCallStarted(
            trace_id=trace_id, tool_call_id="tc-1", tool_name="shell",
            args_json='{"cmd":"ls"}',
        ),
        ToolResultReceived(
            trace_id=trace_id, tool_call_id="tc-1", result="file.txt"
        ),
        RunFinishedDomain(
            trace_id=trace_id, run_id=run_id, thread_id=thread_id, error=None
        ),
    ]
