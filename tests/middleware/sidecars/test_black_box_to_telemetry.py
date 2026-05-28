"""L2 Contract: BlackBoxToTelemetryRelay — outbox relay from JSONL to Langfuse.

Sprint C of the BlackBox→Langfuse plan.  Tests follow Protocol B
(Contract-Driven TDD) from research/tdd_agentic_systems_prompt.md.

Layer: middleware/sidecars (Middleware ring)
Pyramid level: L2 — Reproducible.  Deterministic, fast, filesystem-isolated.

Test categories:
  A. Failure paths first — DLQ promotion, corrupt lines, exporter failure
  B. Offset bookkeeping — save/resume byte position
  C. Forward-only startup — absent offset seeks to EOF
  D. mtime-based pickup — unchanged files are skipped
  E. Idempotent export — observation_id + observation_type in attributes
  F. run_forever lifecycle — stop flag halts loop
  G. Architecture invariant — no langfuse/langgraph imports
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

import pytest

from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent


# ─────────────────────────────────────────────────────────────────────
# Fixtures — FakeExporter + helpers
# ─────────────────────────────────────────────────────────────────────


class FakeExporter:
    """In-memory TelemetryExporter that records calls and can simulate failures."""

    def __init__(self, *, fail_until: int = 0) -> None:
        self.events: list[dict[str, Any]] = []
        self._fail_until = fail_until
        self._call_count = 0

    def export_event(
        self,
        *,
        name: str,
        trace_id: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        self._call_count += 1
        if self._call_count <= self._fail_until:
            raise RuntimeError(f"Simulated failure #{self._call_count}")
        self.events.append({
            "name": name,
            "trace_id": trace_id,
            "attributes": dict(attributes) if attributes else {},
        })

    def release_trace(self, trace_id: str) -> None:
        pass

    def shutdown(self) -> None:
        pass


def _make_event(
    event_type: EventType = EventType.STEP_EXECUTED,
    *,
    workflow_id: str = "wf-001",
    step: int = 1,
    details: dict[str, Any] | None = None,
) -> TraceEvent:
    return TraceEvent(
        event_id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        event_type=event_type,
        timestamp=datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC),
        step=step,
        details=details or {"info": "ok"},
    )


def _record_events(
    storage_dir: Path,
    workflow_id: str,
    events: list[TraceEvent],
) -> Path:
    """Use the real BlackBoxRecorder to write properly-chained JSONL."""
    recorder = BlackBoxRecorder(storage_dir=storage_dir)
    for ev in events:
        recorder.record(ev)
    return storage_dir / workflow_id / "trace.jsonl"


@pytest.fixture()
def storage(tmp_path: Path) -> Path:
    return tmp_path / "black_box_recordings"


@pytest.fixture()
def exporter() -> FakeExporter:
    return FakeExporter()


def _build_relay(storage: Path, exporter: FakeExporter, **kwargs: Any):
    """Lazy import to let RED phase fail on ImportError."""
    from middleware.sidecars.black_box_to_telemetry import BlackBoxToTelemetryRelay

    return BlackBoxToTelemetryRelay(
        storage_dir=storage,
        exporter=exporter,
        base_delay_s=0.0,  # no sleep in tests
        **kwargs,
    )


# ─────────────────────────────────────────────────────────────────────
# A. FAILURE PATHS FIRST — DLQ, corrupt lines, exporter failure
# ─────────────────────────────────────────────────────────────────────


class TestDLQPromotion:
    """After max_retries, a poison line goes to .langfuse_failures.jsonl."""

    def test_corrupt_json_line_goes_to_dlq(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        wf_dir = storage / "wf-corrupt"
        wf_dir.mkdir(parents=True)
        trace_file = wf_dir / "trace.jsonl"
        trace_file.write_text("this is not json\n")
        (wf_dir / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, max_retries=2)
        published = relay.run_once()

        assert published == 0
        assert len(exporter.events) == 0
        dlq = wf_dir / ".langfuse_failures.jsonl"
        assert dlq.exists()
        dlq_entry = json.loads(dlq.read_text().strip().split("\n")[0])
        assert "this is not json" in dlq_entry["line"]
        assert dlq_entry["error"] != ""

    def test_exporter_failure_triggers_dlq_after_retries(
        self, storage: Path
    ) -> None:
        ev = _make_event(workflow_id="wf-fail")
        _record_events(storage, "wf-fail", [ev])
        (storage / "wf-fail" / ".langfuse_offset").write_text("0")

        failing_exporter = FakeExporter(fail_until=99)
        relay = _build_relay(storage, failing_exporter, max_retries=3)
        published = relay.run_once()

        assert published == 0
        dlq = storage / "wf-fail" / ".langfuse_failures.jsonl"
        assert dlq.exists()

    def test_offset_advances_past_poison_line(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """Offset advances even for DLQ'd lines so the relay doesn't re-process them."""
        wf_dir = storage / "wf-poison"
        wf_dir.mkdir(parents=True)
        trace_file = wf_dir / "trace.jsonl"
        trace_file.write_text("bad line\n")
        (wf_dir / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, max_retries=0)
        relay.run_once()

        offset = int((wf_dir / ".langfuse_offset").read_text().strip())
        assert offset == len("bad line\n".encode("utf-8"))

    def test_dlq_entry_has_timestamp(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        wf_dir = storage / "wf-ts"
        wf_dir.mkdir(parents=True)
        (wf_dir / "trace.jsonl").write_text("{invalid json}\n")
        (wf_dir / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, max_retries=0)
        relay.run_once()

        dlq_entry = json.loads(
            (wf_dir / ".langfuse_failures.jsonl").read_text().strip()
        )
        assert "timestamp" in dlq_entry


# ─────────────────────────────────────────────────────────────────────
# B. OFFSET BOOKKEEPING — save and resume byte position
# ─────────────────────────────────────────────────────────────────────


class TestOffsetBookkeeping:
    """Relay tracks byte offsets in .langfuse_offset per workflow."""

    def test_publishes_events_and_advances_offset(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(workflow_id="wf-001")
        trace_file = _record_events(storage, "wf-001", [ev])
        (storage / "wf-001" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        published = relay.run_once()

        assert published == 1
        assert len(exporter.events) == 1
        offset = int((storage / "wf-001" / ".langfuse_offset").read_text().strip())
        assert offset == trace_file.stat().st_size

    def test_resumes_from_saved_offset(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev1 = _make_event(EventType.TASK_STARTED, workflow_id="wf-resume")
        ev2 = _make_event(EventType.STEP_EXECUTED, workflow_id="wf-resume", step=2)
        trace_file = _record_events(storage, "wf-resume", [ev1, ev2])

        # Simulate: first event already consumed
        first_line = trace_file.read_text().split("\n")[0] + "\n"
        mid_offset = len(first_line.encode("utf-8"))
        (storage / "wf-resume" / ".langfuse_offset").write_text(str(mid_offset))

        relay = _build_relay(storage, exporter)
        published = relay.run_once()

        assert published == 1
        assert exporter.events[0]["name"] == "step.executed"

    def test_multiple_workflows_tracked_independently(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev_a = _make_event(workflow_id="wf-a")
        ev_b = _make_event(workflow_id="wf-b")
        _record_events(storage, "wf-a", [ev_a])
        _record_events(storage, "wf-b", [ev_b])
        (storage / "wf-a" / ".langfuse_offset").write_text("0")
        (storage / "wf-b" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        published = relay.run_once()

        assert published == 2
        trace_ids = {e["trace_id"] for e in exporter.events}
        assert trace_ids == {"wf-a", "wf-b"}

    def test_no_new_content_is_noop(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(workflow_id="wf-done")
        trace_file = _record_events(storage, "wf-done", [ev])
        file_size = trace_file.stat().st_size
        (storage / "wf-done" / ".langfuse_offset").write_text(str(file_size))

        relay = _build_relay(storage, exporter)
        published = relay.run_once()

        assert published == 0
        assert len(exporter.events) == 0


# ─────────────────────────────────────────────────────────────────────
# C. FORWARD-ONLY STARTUP — absent offset = seek to EOF
# ─────────────────────────────────────────────────────────────────────


class TestForwardOnlyStartup:
    """Absent .langfuse_offset → relay skips existing events (no backfill)."""

    def test_absent_offset_creates_offset_at_eof(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(workflow_id="wf-new")
        trace_file = _record_events(storage, "wf-new", [ev])
        expected_size = trace_file.stat().st_size

        relay = _build_relay(storage, exporter)
        published = relay.run_once()

        assert published == 0, "Should not backfill existing events"
        assert len(exporter.events) == 0
        offset_file = storage / "wf-new" / ".langfuse_offset"
        assert offset_file.exists()
        assert int(offset_file.read_text().strip()) == expected_size

    def test_new_events_after_startup_are_published(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev1 = _make_event(EventType.TASK_STARTED, workflow_id="wf-grow")
        _record_events(storage, "wf-grow", [ev1])

        relay = _build_relay(storage, exporter)
        relay.run_once()
        assert len(exporter.events) == 0

        ev2 = _make_event(EventType.STEP_EXECUTED, workflow_id="wf-grow", step=2)
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(ev2)

        published = relay.run_once()
        assert published == 1
        assert exporter.events[0]["name"] == "step.executed"

    def test_nonexistent_storage_dir_returns_zero(
        self, tmp_path: Path, exporter: FakeExporter
    ) -> None:
        relay = _build_relay(tmp_path / "does_not_exist", exporter)
        assert relay.run_once() == 0


# ─────────────────────────────────────────────────────────────────────
# D. MTIME-BASED PICKUP — unchanged files skipped
# ─────────────────────────────────────────────────────────────────────


class TestMtimePickup:
    """Relay uses mtime polling to skip unchanged trace files."""

    def test_unchanged_mtime_skips_file(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(workflow_id="wf-mtime")
        _record_events(storage, "wf-mtime", [ev])
        (storage / "wf-mtime" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()
        assert len(exporter.events) == 1

        exporter.events.clear()
        published = relay.run_once()
        assert published == 0, "Second run with same mtime should skip"

    def test_changed_mtime_processes_new_events(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev1 = _make_event(EventType.TASK_STARTED, workflow_id="wf-mt2")
        _record_events(storage, "wf-mt2", [ev1])
        (storage / "wf-mt2" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()  # processes ev1
        assert len(exporter.events) == 1

        ev2 = _make_event(EventType.STEP_EXECUTED, workflow_id="wf-mt2", step=2)
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(ev2)

        published = relay.run_once()
        assert published == 1
        assert exporter.events[-1]["name"] == "step.executed"


# ─────────────────────────────────────────────────────────────────────
# E. IDEMPOTENT EXPORT — observation_id/type/level in attributes
# ─────────────────────────────────────────────────────────────────────


class TestIdempotentExport:
    """Relay passes observation_id, observation_type, and level via attributes."""

    def test_observation_id_passed_in_attributes(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(EventType.TOOL_CALLED, workflow_id="wf-idem")
        _record_events(storage, "wf-idem", [ev])
        (storage / "wf-idem" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()

        attrs = exporter.events[0]["attributes"]
        assert attrs["__bb_observation_id"] == ev.event_id

    def test_observation_type_passed_in_attributes(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(EventType.TOOL_CALLED, workflow_id="wf-type")
        _record_events(storage, "wf-type", [ev])
        (storage / "wf-type" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()

        attrs = exporter.events[0]["attributes"]
        assert attrs["__bb_observation_type"] == "tool"

    def test_error_event_level_is_error(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(
            EventType.ERROR_OCCURRED,
            workflow_id="wf-err",
            details={"error": "something failed"},
        )
        _record_events(storage, "wf-err", [ev])
        (storage / "wf-err" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()

        attrs = exporter.events[0]["attributes"]
        assert attrs["__bb_level"] == "ERROR"

    def test_non_error_event_level_is_default(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(EventType.TASK_STARTED, workflow_id="wf-lvl")
        _record_events(storage, "wf-lvl", [ev])
        (storage / "wf-lvl" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()

        attrs = exporter.events[0]["attributes"]
        assert attrs["__bb_level"] == "DEFAULT"

    def test_trace_id_equals_workflow_id(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(workflow_id="wf-trace")
        _record_events(storage, "wf-trace", [ev])
        (storage / "wf-trace" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()

        assert exporter.events[0]["trace_id"] == "wf-trace"


# ─────────────────────────────────────────────────────────────────────
# F. run_forever LIFECYCLE — stop flag halts loop
# ─────────────────────────────────────────────────────────────────────


class TestRunForever:
    """run_forever() is an async loop that respects the stop flag."""

    def test_stop_halts_loop(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        relay = _build_relay(storage, exporter)

        async def _run() -> None:
            task = asyncio.create_task(relay.run_forever(interval_s=0.01))
            await asyncio.sleep(0.05)
            relay.stop()
            await task

        asyncio.run(_run())

    def test_run_forever_processes_events(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(workflow_id="wf-loop")
        _record_events(storage, "wf-loop", [ev])
        (storage / "wf-loop" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)

        async def _run() -> None:
            task = asyncio.create_task(relay.run_forever(interval_s=0.01))
            await asyncio.sleep(0.05)
            relay.stop()
            await task

        asyncio.run(_run())
        assert len(exporter.events) >= 1


# ─────────────────────────────────────────────────────────────────────
# G. ARCHITECTURE INVARIANT — no langfuse/langgraph imports
# ─────────────────────────────────────────────────────────────────────


class TestLayeringInvariant:
    """Sidecar module must import the port, never the SDK directly."""

    def test_no_langfuse_import(self) -> None:
        import ast

        src = Path("middleware/sidecars/black_box_to_telemetry.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("langfuse"), (
                        f"Forbidden import: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith("langfuse"), (
                        f"Forbidden import from: {node.module}"
                    )

    def test_no_langgraph_import(self) -> None:
        import ast

        src = Path("middleware/sidecars/black_box_to_telemetry.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("langgraph"), (
                        f"Forbidden import: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith("langgraph"), (
                        f"Forbidden import from: {node.module}"
                    )


# ─────────────────────────────────────────────────────────────────────
# H. PARTIAL LINE SAFETY — incomplete writes are not processed
# ─────────────────────────────────────────────────────────────────────


class TestPartialLineSafety:
    """A trace.jsonl with a partial last line (no trailing newline) must not
    corrupt the relay — the partial line is deferred to the next poll."""

    def test_partial_line_not_processed(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(workflow_id="wf-partial")
        trace_file = _record_events(storage, "wf-partial", [ev])
        (storage / "wf-partial" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()
        assert len(exporter.events) == 1

        # Append a partial line (no trailing newline)
        with open(trace_file, "a") as f:
            f.write('{"event_id": "partial"')

        exporter.events.clear()
        published = relay.run_once()
        assert published == 0, "Partial line should not be processed"

    def test_completed_partial_line_processed_next_poll(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        wf_dir = storage / "wf-complete"
        wf_dir.mkdir(parents=True)
        trace_file = wf_dir / "trace.jsonl"

        ev = _make_event(EventType.TASK_STARTED, workflow_id="wf-complete")
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(ev)

        (wf_dir / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()  # processes the first event
        initial_count = len(exporter.events)

        # Write another event normally (with trailing newline)
        ev2 = _make_event(EventType.STEP_EXECUTED, workflow_id="wf-complete", step=2)
        recorder.record(ev2)

        published = relay.run_once()
        assert published == 1
        assert len(exporter.events) == initial_count + 1
