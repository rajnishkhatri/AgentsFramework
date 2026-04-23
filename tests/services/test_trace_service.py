"""L2 Reproducible: Tests for services/trace_service.py.

Contract-driven TDD per Protocol B. Failure paths first (TAP-4).

Spec: docs/plan/services/TRACE_SERVICE_PLAN.md.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from trust.models import TrustTraceRecord


def _make_record(**overrides) -> TrustTraceRecord:
    defaults = {
        "event_id": "evt-1",
        "timestamp": datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC),
        "trace_id": "trace-1",
        "agent_id": "agent-1",
        "layer": "L2",
        "event_type": "unit_test",
        "details": {"foo": "bar"},
        "outcome": "pass",
    }
    defaults.update(overrides)
    return TrustTraceRecord(**defaults)


class _RecordingSink:
    name = "recording"

    def __init__(self) -> None:
        self.records: list[TrustTraceRecord] = []

    def emit(self, record: TrustTraceRecord) -> None:
        self.records.append(record)


class _ExplodingSink:
    name = "exploding"

    def emit(self, record: TrustTraceRecord) -> None:
        raise RuntimeError("sink boom")


# ─────────────────────────────────────────────────────────────────────
# 3.1 Failure path tests (FIRST)
# ─────────────────────────────────────────────────────────────────────


class TestTraceServiceFailures:
    def test_emit_rejects_non_trace_record_payload(self):
        from services.trace_service import TraceService

        sink = _RecordingSink()
        service = TraceService(sinks=[sink])
        with pytest.raises(TypeError):
            service.emit({"not": "a record"})  # type: ignore[arg-type]
        assert sink.records == []

    def test_emit_rejects_none(self):
        from services.trace_service import TraceService

        sink = _RecordingSink()
        service = TraceService(sinks=[sink])
        with pytest.raises(TypeError):
            service.emit(None)  # type: ignore[arg-type]
        assert sink.records == []

    def test_emit_isolates_sink_failures(self):
        from services.trace_service import TraceService

        good = _RecordingSink()
        service = TraceService(sinks=[_ExplodingSink(), good])
        record = _make_record()
        service.emit(record)
        assert good.records == [record]

    def test_emit_logs_sink_failures(self):
        from services.trace_service import TraceService

        target = logging.getLogger("trust.trace")
        captured: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(record)

        handler = _Capture(level=logging.ERROR)
        target.addHandler(handler)
        original_level = target.level
        target.setLevel(logging.ERROR)
        try:
            service = TraceService(sinks=[_ExplodingSink()])
            service.emit(_make_record())
        finally:
            target.removeHandler(handler)
            target.setLevel(original_level)

        assert any(rec.levelno == logging.ERROR for rec in captured)
        text = " ".join(rec.getMessage() for rec in captured)
        assert "sink boom" in text or "RuntimeError" in text

    def test_jsonl_sink_handles_unwritable_path(self, tmp_path):
        from services.trace_service import (
            JsonlFileTraceSink,
            TraceService,
        )

        bad = JsonlFileTraceSink(Path("/no/such/dir/xyz.jsonl"))
        good = _RecordingSink()
        service = TraceService(sinks=[bad, good])
        record = _make_record()
        service.emit(record)
        assert good.records == [record]


# ─────────────────────────────────────────────────────────────────────
# 3.2 Acceptance path tests
# ─────────────────────────────────────────────────────────────────────


class TestTraceServiceAcceptance:
    def test_emit_fans_out_to_all_sinks(self):
        from services.trace_service import TraceService

        s1, s2, s3 = _RecordingSink(), _RecordingSink(), _RecordingSink()
        service = TraceService(sinks=[s1, s2, s3])
        record = _make_record()
        service.emit(record)
        for sink in (s1, s2, s3):
            assert len(sink.records) == 1
            assert sink.records[0].model_dump_json() == record.model_dump_json()

    def test_inmemory_sink_records_in_order(self):
        from services.trace_service import InMemoryTraceSink, TraceService

        sink = InMemoryTraceSink()
        service = TraceService(sinks=[sink])
        for i in range(3):
            service.emit(_make_record(event_id=f"evt-{i}"))
        assert [r.event_id for r in sink.records] == ["evt-0", "evt-1", "evt-2"]

    def test_jsonl_sink_writes_one_record_per_line(self, tmp_path):
        from services.trace_service import JsonlFileTraceSink, TraceService

        path = tmp_path / "trace.jsonl"
        service = TraceService(sinks=[JsonlFileTraceSink(path)])
        service.emit(_make_record(event_id="a"))
        service.emit(_make_record(event_id="b"))

        lines = path.read_text().splitlines()
        assert len(lines) == 2
        parsed = [TrustTraceRecord.model_validate_json(line) for line in lines]
        assert [r.event_id for r in parsed] == ["a", "b"]

    def test_jsonl_sink_round_trips_unicode(self, tmp_path):
        from services.trace_service import JsonlFileTraceSink, TraceService

        path = tmp_path / "trace.jsonl"
        service = TraceService(sinks=[JsonlFileTraceSink(path)])
        details = {"msg": "héllo 🌍 ünïcødé", "lang": "日本語"}
        record = _make_record(details=details)
        service.emit(record)

        line = path.read_text().splitlines()[0]
        roundtripped = TrustTraceRecord.model_validate_json(line)
        assert roundtripped.details == details

    def test_no_dedup_at_service_layer(self):
        from services.trace_service import InMemoryTraceSink, TraceService

        sink = InMemoryTraceSink()
        service = TraceService(sinks=[sink])
        record = _make_record()
        service.emit(record)
        service.emit(record)
        assert len(sink.records) == 2

    def test_add_sink_late_binding(self):
        from services.trace_service import TraceService

        service = TraceService(sinks=[])
        service.emit(_make_record(event_id="ignored"))  # no sinks, no error

        sink = _RecordingSink()
        service.add_sink(sink)
        record = _make_record(event_id="latebind")
        service.emit(record)
        assert sink.records == [record]


class TestLoggingSink:
    def test_logging_sink_emits_at_info(self):
        from services.trace_service import LoggingTraceSink, TraceService

        target = logging.getLogger("trust.trace.test")
        captured: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(record)

        handler = _Capture(level=logging.INFO)
        target.addHandler(handler)
        original_level = target.level
        target.setLevel(logging.INFO)
        try:
            sink = LoggingTraceSink(logger_name="trust.trace.test")
            service = TraceService(sinks=[sink])
            service.emit(_make_record(event_id="logged"))
        finally:
            target.removeHandler(handler)
            target.setLevel(original_level)

        assert any("logged" in r.getMessage() for r in captured)


# ─────────────────────────────────────────────────────────────────────
# 3.3 Property-based test
# ─────────────────────────────────────────────────────────────────────


@st.composite
def _trace_records(draw) -> TrustTraceRecord:
    return TrustTraceRecord(
        event_id=draw(st.text(min_size=1, max_size=20)),
        timestamp=datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC),
        trace_id=draw(st.text(min_size=1, max_size=20)),
        agent_id=draw(st.text(min_size=1, max_size=20)),
        layer=draw(st.sampled_from(["L1", "L2", "L3", "L4", "L5", "L6", "L7"])),
        event_type=draw(st.text(min_size=1, max_size=20)),
        details=draw(
            st.dictionaries(
                keys=st.text(min_size=1, max_size=10),
                values=st.one_of(
                    st.text(max_size=50),
                    st.integers(),
                    st.booleans(),
                ),
                max_size=4,
            )
        ),
        outcome=draw(st.sampled_from(["pass", "fail", "alert", None])),
    )


@pytest.mark.property
class TestTraceServiceProperty:
    @settings(max_examples=25, deadline=None)
    @given(record=_trace_records())
    def test_emit_preserves_record_bytewise(self, record):
        from services.trace_service import InMemoryTraceSink, TraceService

        sink = InMemoryTraceSink()
        service = TraceService(sinks=[sink])
        service.emit(record)
        assert len(sink.records) == 1
        assert sink.records[0].model_dump_json() == record.model_dump_json()
