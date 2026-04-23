"""Tests for JsonlTraceSink (M-Phase2 second swap proof).

Per AGENT_UI_ADAPTER_SPRINTS.md M-Phase2.3, failure paths first (TAP-4):
  - Missing parent directory → FileNotFoundError at construction
  - Non-TrustTraceRecord → TypeError
  - Sink raises mid-stream → other sinks continue (fan-out invariant via TraceService)
  - Happy path: round-trip emit-then-read returns byte-equivalent records
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from services.trace_service import InMemoryTraceSink, TraceService
from services.trace_sinks.jsonl_sink import JsonlTraceSink
from trust.models import TrustTraceRecord


def _make_record(trace_id: str = "t-1") -> TrustTraceRecord:
    return TrustTraceRecord(
        event_id=str(uuid.uuid4()),
        timestamp=datetime.now(UTC),
        trace_id=trace_id,
        agent_id="test-agent",
        layer="L4",
        event_type="test_event",
        details={"key": "value"},
        outcome="pass",
    )


class TestJsonlTraceSinkFailurePaths:
    def test_missing_parent_directory_raises_at_construction(self, tmp_path: Path) -> None:
        bad_parent = tmp_path / "nonexistent" / "trace.jsonl"
        with pytest.raises(FileNotFoundError, match="Parent directory"):
            JsonlTraceSink(bad_parent)

    def test_non_trust_trace_record_raises_type_error(self, tmp_path: Path) -> None:
        sink = JsonlTraceSink(tmp_path / "trace.jsonl")
        with pytest.raises(TypeError, match="TrustTraceRecord"):
            sink.emit("not a record")  # type: ignore[arg-type]

    def test_sink_failure_does_not_block_other_sinks(self, tmp_path: Path) -> None:
        """Fan-out invariant from US-1.1: one sink error doesn't block others."""

        class _ExplodingSink:
            name = "exploding"

            def emit(self, record: TrustTraceRecord) -> None:
                raise RuntimeError("boom")

        good_sink = InMemoryTraceSink()
        service = TraceService(sinks=[_ExplodingSink(), good_sink])

        record = _make_record()
        service.emit(record)
        assert len(good_sink.records) == 1


class TestJsonlTraceSinkHappyPath:
    def test_round_trip_emit_then_read(self, tmp_path: Path) -> None:
        path = tmp_path / "trace.jsonl"
        sink = JsonlTraceSink(path)

        r1 = _make_record("trace-a")
        r2 = _make_record("trace-b")
        sink.emit(r1)
        sink.emit(r2)

        rehydrated = sink.read_all()
        assert len(rehydrated) == 2
        assert rehydrated[0] == r1
        assert rehydrated[1] == r2

    def test_implements_trace_sink_protocol(self, tmp_path: Path) -> None:
        from services.trace_service import TraceSink

        sink = JsonlTraceSink(tmp_path / "trace.jsonl")
        assert isinstance(sink, TraceSink)

    def test_jsonl_sink_works_with_trace_service(self, tmp_path: Path) -> None:
        """Integration: TraceService fans out to JsonlTraceSink."""
        path = tmp_path / "trace.jsonl"
        jsonl_sink = JsonlTraceSink(path)
        mem_sink = InMemoryTraceSink()
        service = TraceService(sinks=[jsonl_sink, mem_sink])

        record = _make_record()
        service.emit(record)

        assert len(mem_sink.records) == 1
        rehydrated = jsonl_sink.read_all()
        assert len(rehydrated) == 1
        assert rehydrated[0] == record
