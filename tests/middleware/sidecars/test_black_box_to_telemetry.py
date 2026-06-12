"""L2 Contract: BlackBoxToTelemetryRelay — outbox relay from JSONL to Langfuse.

Sprint C of the BlackBox→Langfuse plan.  Tests follow Protocol B
(Contract-Driven TDD) from research/tdd_agentic_systems_prompt.md.

Layer: middleware/sidecars (Middleware ring)
Pyramid level: L2 — Reproducible.  Deterministic, fast, filesystem-isolated.

Test categories:
  A. Failure paths first — DLQ promotion, corrupt lines, exporter failure
  B. Offset bookkeeping — save/resume byte position
  C. Startup-from-beginning — absent offset processes from offset 0 (dedup-safe)
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
    """In-memory TelemetryExporter that records calls and can simulate failures.

    Args:
        fail_until: raise on the first N calls (simulates a *raising* exporter;
            the relay's retry/DLQ loop is exercised).
        swallow_export: when True, ``export_event`` returns ``False`` instead of
            recording — simulates a real swallowed SDK error per rule O1 (the
            S1 bug class), so the relay must dead-letter rather than count it as
            published.
    """

    def __init__(self, *, fail_until: int = 0, swallow_export: bool = False) -> None:
        self.events: list[dict[str, Any]] = []
        self._fail_until = fail_until
        self._swallow_export = swallow_export
        self._call_count = 0

    def export_event(
        self,
        *,
        name: str,
        trace_id: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> bool:
        self._call_count += 1
        if self._call_count <= self._fail_until:
            raise RuntimeError(f"Simulated failure #{self._call_count}")
        if self._swallow_export:
            return False
        self.events.append({
            "name": name,
            "trace_id": trace_id,
            "attributes": dict(attributes) if attributes else {},
        })
        return True

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
    """Lazy import to let RED phase fail on ImportError.

    These export-mechanics tests predate the Phase 4 curated view and assert
    that every event (incl. STEP_EXECUTED / TOOL_CALLED) is exported. Default
    them to the audit-complete dual view (``curated_view=False``) so they keep
    testing offset/idempotency/drain mechanics, not the curated policy. The
    ``TestCuratedViewSuppression`` class passes the flag explicitly to exercise
    the production default.
    """
    from middleware.sidecars.black_box_to_telemetry import BlackBoxToTelemetryRelay

    kwargs.setdefault("curated_view", False)
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


class TestSwallowedExportSignal:
    """A swallowed export (``export_event`` returns False) is dead-lettered.

    Regression guard for the S1 root cause: the exporter swallows SDK errors per
    rule O1 and the relay used to treat that silence as success — advancing the
    offset and logging "published" while dropping every BlackBox observation.
    The relay now treats a ``False`` return as a poison line.
    """

    def test_swallowed_export_goes_to_dlq(self, storage: Path) -> None:
        ev = _make_event(workflow_id="wf-swallow")
        _record_events(storage, "wf-swallow", [ev])
        (storage / "wf-swallow" / ".langfuse_offset").write_text("0")

        swallowing = FakeExporter(swallow_export=True)
        relay = _build_relay(storage, swallowing, max_retries=0)
        published = relay.run_once()

        assert published == 0, "Swallowed export must not count as published"
        assert len(swallowing.events) == 0
        dlq = storage / "wf-swallow" / ".langfuse_failures.jsonl"
        assert dlq.exists()
        dlq_entry = json.loads(dlq.read_text().strip().split("\n")[0])
        assert "swallowed" in dlq_entry["error"]

    def test_none_return_is_treated_as_success(self, storage: Path) -> None:
        """Older exporters that return None (not bool) still count as published."""

        class LegacyExporter(FakeExporter):
            def export_event(self, *, name, trace_id, attributes=None):  # type: ignore[override]
                self.events.append(
                    {"name": name, "trace_id": trace_id, "attributes": dict(attributes or {})}
                )
                return None  # legacy contract

        ev = _make_event(workflow_id="wf-legacy")
        _record_events(storage, "wf-legacy", [ev])
        (storage / "wf-legacy" / ".langfuse_offset").write_text("0")

        legacy = LegacyExporter()
        relay = _build_relay(storage, legacy, max_retries=0)
        published = relay.run_once()

        assert published == 1
        assert len(legacy.events) == 1
        assert not (storage / "wf-legacy" / ".langfuse_failures.jsonl").exists()


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
# C. STARTUP — absent offset processes from beginning (idempotent via observation_id)
# ─────────────────────────────────────────────────────────────────────


class TestStartupFromBeginning:
    """Absent .langfuse_offset → relay processes all existing events from offset 0.

    In the in-process relay mode (Cloud Run), the relay starts alongside the
    recorder. Fast-completing requests write all events before the relay's first
    poll. Starting from 0 ensures nothing is skipped. Duplicate exports are safe
    because Langfuse deduplicates on observation_id.
    """

    def test_absent_offset_processes_existing_events(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(workflow_id="wf-new")
        trace_file = _record_events(storage, "wf-new", [ev])
        expected_size = trace_file.stat().st_size

        relay = _build_relay(storage, exporter)
        published = relay.run_once()

        assert published == 1, "Should process existing events on first encounter"
        assert len(exporter.events) == 1
        offset_file = storage / "wf-new" / ".langfuse_offset"
        assert offset_file.exists()
        assert int(offset_file.read_text().strip()) == expected_size

    def test_new_events_after_startup_are_also_published(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev1 = _make_event(EventType.TASK_STARTED, workflow_id="wf-grow")
        _record_events(storage, "wf-grow", [ev1])

        relay = _build_relay(storage, exporter)
        relay.run_once()
        assert len(exporter.events) == 1

        ev2 = _make_event(EventType.STEP_EXECUTED, workflow_id="wf-grow", step=2)
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(ev2)

        published = relay.run_once()
        assert published == 1
        assert exporter.events[1]["name"] == "step.executed"

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

    def test_mtime_regression(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """Write events, poll, write more within same mtime resolution, poll again.
        Ensures removing the mtime-only early exit correctly picks up new events
        when mtime float64 hasn't changed.
        """
        import os
        ev1 = _make_event(EventType.TASK_STARTED, workflow_id="wf-regress")
        trace_file = _record_events(storage, "wf-regress", [ev1])
        (storage / "wf-regress" / ".langfuse_offset").write_text("0")
        
        # force mtime to a known value
        os.utime(trace_file, (1000.0, 1000.0))

        relay = _build_relay(storage, exporter)
        relay.run_once()
        assert len(exporter.events) == 1

        ev2 = _make_event(EventType.STEP_EXECUTED, workflow_id="wf-regress", step=2)
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(ev2)
        
        # force mtime to exactly the SAME value as before
        os.utime(trace_file, (1000.0, 1000.0))

        published = relay.run_once()
        assert published == 1, "Should publish new events despite identical mtime"
        assert len(exporter.events) == 2


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


# ─────────────────────────────────────────────────────────────────────
# I. DRAIN WORKFLOW — synchronous per-workflow drain
# ─────────────────────────────────────────────────────────────────────


class TestDrainWorkflow:
    def test_drain_workflow_processes_only_target(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev_a = _make_event(workflow_id="wf-a")
        ev_b = _make_event(workflow_id="wf-b")
        _record_events(storage, "wf-a", [ev_a])
        _record_events(storage, "wf-b", [ev_b])

        relay = _build_relay(storage, exporter)
        
        # Drain only wf-a
        processed = relay.drain_workflow("wf-a")
        assert processed == 1
        assert len(exporter.events) == 1
        assert exporter.events[0]["trace_id"] == "wf-a"

        # wf-b is untouched
        offset_b = storage / "wf-b" / ".langfuse_offset"
        assert not offset_b.exists() or int(offset_b.read_text().strip()) == 0


# ─────────────────────────────────────────────────────────────────────
# I8 — single-writer serialization + at-least-once dedup
# ─────────────────────────────────────────────────────────────────────


class _CountingFakeSdkClient:
    """Minimal Langfuse SDK v4 stand-in counting real (deduped) observations."""

    def __init__(self) -> None:
        self.spans: list[dict] = []
        self.flushed = False

    def start_observation(self, *, trace_context=None, name, **kwargs):
        self.spans.append({"name": name, "trace_id": (trace_context or {}).get("trace_id")})

        class _Obs:
            def end(self_inner, **_):
                pass

            def start_observation(self_inner, *, name, **kw):
                return _Obs()

        return _Obs()

    def flush(self) -> None:
        self.flushed = True


class TestSingleWriterIdempotency:
    """Drain after a full poll exports the tail zero extra times; an at-least-once
    re-read (the run_forever + drain race) yields exactly one observation per
    event_id once it reaches the real exporter's dedup guard (I8).
    """

    def test_drain_after_full_poll_publishes_nothing(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(EventType.TASK_COMPLETED, workflow_id="wf-tail")
        _record_events(storage, "wf-tail", [ev])

        relay = _build_relay(storage, exporter)
        assert relay.run_once() == 1
        # The SSE-finally drain races the background poll; with the offset fully
        # advanced it must publish zero extra events.
        assert relay.drain_workflow("wf-tail") == 0
        assert len(exporter.events) == 1

    def test_offset_write_is_atomic_no_temp_left_behind(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(workflow_id="wf-atomic")
        _record_events(storage, "wf-atomic", [ev])

        relay = _build_relay(storage, exporter)
        relay.run_once()

        wf_dir = storage / "wf-atomic"
        assert (wf_dir / ".langfuse_offset").exists()
        assert not (wf_dir / ".langfuse_offset.tmp").exists()

    def test_at_least_once_reread_dedupes_at_exporter(
        self, storage: Path
    ) -> None:
        """A re-read of the same offset window (crash/race) exports once.

        Uses the real ``LangfuseCloudExporter`` so the per-trace ``event_id``
        dedup guard is exercised end to end, not a test re-implementation.
        """
        from middleware.adapters.observability.langfuse_cloud_exporter import (
            LangfuseCloudExporter,
        )

        ev = _make_event(EventType.TASK_COMPLETED, workflow_id="wf-race")
        _record_events(storage, "wf-race", [ev])

        sdk = _CountingFakeSdkClient()
        real_exporter = LangfuseCloudExporter(
            public_key="pk", secret_key="sk", sdk_client=sdk
        )
        relay = _build_relay(storage, real_exporter)

        relay.run_once()
        # Simulate the at-least-once race: the offset was not yet durable, so a
        # concurrent reader re-consumes the same window.
        (storage / "wf-race" / ".langfuse_offset").write_text("0")
        relay.run_once()

        task_spans = [s for s in sdk.spans if s["name"] == "task.completed"]
        assert len(task_spans) == 1, "duplicate event_id must export exactly once"


# ─────────────────────────────────────────────────────────────────────
# Phase 4 — Curated-view flag: relay-side export suppression (E2, E3, E10)
# ─────────────────────────────────────────────────────────────────────


class TestCuratedViewSuppression:
    """The curated flag (default ON) suppresses the EXPORT of governance-
    duplicate events (TOOL_CALLED, STEP_EXECUTED) and unchanged-plan
    STEP_PLANNED re-emissions. Suppression is processed-not-published: the
    offset advances, NO DLQ entry is written, and no export_event fires.

    Rejection paths first.
    """

    def _offset(self, storage: Path, wf: str) -> int:
        return int((storage / wf / ".langfuse_offset").read_text().strip())

    def _dlq(self, storage: Path, wf: str) -> Path:
        return storage / wf / ".langfuse_failures.jsonl"

    # ── ON (default): governance-duplicate events suppressed ──────────

    def test_tool_called_suppressed_when_curated_on(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(EventType.TOOL_CALLED, workflow_id="wf-c1",
                         details={"tool": "shell", "tool_call_id": "1:c"})
        trace_file = _record_events(storage, "wf-c1", [ev])
        (storage / "wf-c1" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, curated_view=True)
        published = relay.run_once()

        assert published == 0
        assert len(exporter.events) == 0
        # offset advanced past the suppressed line; no DLQ.
        assert self._offset(storage, "wf-c1") == trace_file.stat().st_size
        assert not self._dlq(storage, "wf-c1").exists()

    def test_step_executed_suppressed_when_curated_on(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(EventType.STEP_EXECUTED, workflow_id="wf-c2")
        trace_file = _record_events(storage, "wf-c2", [ev])
        (storage / "wf-c2" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, curated_view=True)
        relay.run_once()

        assert len(exporter.events) == 0
        assert self._offset(storage, "wf-c2") == trace_file.stat().st_size
        assert not self._dlq(storage, "wf-c2").exists()

    def test_unchanged_plan_suppressed_when_curated_on(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(EventType.STEP_PLANNED, workflow_id="wf-c3",
                         details={"planning_depth": "L0", "plan_changed": False})
        _record_events(storage, "wf-c3", [ev])
        (storage / "wf-c3" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, curated_view=True)
        relay.run_once()
        assert len(exporter.events) == 0
        assert not self._dlq(storage, "wf-c3").exists()

    # ── ON: real-signal events still exported ─────────────────────────

    def test_changed_plan_exported_when_curated_on(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(EventType.STEP_PLANNED, workflow_id="wf-c4",
                         details={"planning_depth": "L0", "plan_changed": True})
        _record_events(storage, "wf-c4", [ev])
        (storage / "wf-c4" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, curated_view=True)
        published = relay.run_once()
        assert published == 1
        assert exporter.events[0]["name"] == "step.planned"

    def test_plan_changed_absent_exported_back_compat(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """Old JSONL rows have no plan_changed key — they must still export."""
        ev = _make_event(EventType.STEP_PLANNED, workflow_id="wf-c5",
                         details={"planning_depth": "L0"})
        _record_events(storage, "wf-c5", [ev])
        (storage / "wf-c5" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, curated_view=True)
        published = relay.run_once()
        assert published == 1

    def test_task_completed_still_exports_when_curated_on(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(EventType.TASK_COMPLETED, workflow_id="wf-c6",
                         details={"outcome": "success", "goal_met": True})
        _record_events(storage, "wf-c6", [ev])
        (storage / "wf-c6" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, curated_view=True)
        published = relay.run_once()
        assert published == 1
        assert exporter.events[0]["name"] == "task.completed"

    def test_non_suppressed_event_exported_when_curated_on(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(EventType.MODEL_SELECTED, workflow_id="wf-c7",
                         details={"model": "gpt-4o-mini"})
        _record_events(storage, "wf-c7", [ev])
        (storage / "wf-c7" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, curated_view=True)
        assert relay.run_once() == 1

    # ── OFF: Option-B escape hatch — everything exports as before ──────

    def test_tool_called_exported_when_curated_off(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        ev = _make_event(EventType.TOOL_CALLED, workflow_id="wf-c8",
                         details={"tool": "shell", "tool_call_id": "1:c"})
        _record_events(storage, "wf-c8", [ev])
        (storage / "wf-c8" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, curated_view=False)
        published = relay.run_once()
        assert published == 1
        assert exporter.events[0]["name"] == "tool.called"

    def test_step_executed_and_unchanged_plan_exported_when_curated_off(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        evs = [
            _make_event(EventType.STEP_EXECUTED, workflow_id="wf-c9", step=1),
            _make_event(EventType.STEP_PLANNED, workflow_id="wf-c9", step=1,
                       details={"plan_changed": False}),
        ]
        _record_events(storage, "wf-c9", evs)
        (storage / "wf-c9" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, curated_view=False)
        published = relay.run_once()
        assert published == 2

    def test_default_is_curated_on(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """The production constructor default is curated_view=True (built here
        directly, bypassing the test helper's dual-view default)."""
        from middleware.sidecars.black_box_to_telemetry import (
            BlackBoxToTelemetryRelay,
        )

        ev = _make_event(EventType.TOOL_CALLED, workflow_id="wf-c10",
                         details={"tool": "shell"})
        _record_events(storage, "wf-c10", [ev])
        (storage / "wf-c10" / ".langfuse_offset").write_text("0")

        relay = BlackBoxToTelemetryRelay(
            storage_dir=storage, exporter=exporter, base_delay_s=0.0,
        )  # no curated_view kwarg → production default
        assert relay.run_once() == 0
        assert len(exporter.events) == 0
