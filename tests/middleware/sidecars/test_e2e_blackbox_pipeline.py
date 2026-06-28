"""L2 Contract: End-to-end BlackBox → Relay → Publisher → Exporter pipeline.

Sprint G of the BlackBox→Langfuse plan.  Tests follow Protocol B
(Contract-Driven TDD) from research/tdd_agentic_systems_prompt.md.

Layer: middleware/sidecars (Middleware ring)
Pyramid level: L2 — Reproducible.  Deterministic, fast, filesystem-isolated.

These integration tests verify that all Sprint A–F components work together
correctly as a pipeline.  Each test uses real BlackBoxRecorder + real
BlackBoxToTelemetryRelay + real publisher mapping, but fake exporter/compliance
publisher (no live Langfuse).

Test categories:
  A. Failure paths first — DLQ, exporter failure, partial lines
  B. Full pipeline flow — all 9 event types, redaction, observation IDs, levels
  C. Multi-workflow isolation — independent offset tracking, per-workflow compliance
  D. Forward-only startup + incremental processing
  E. Dev relay compliance gap verification
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

import pytest

from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent


# ─────────────────────────────────────────────────────────────────────
# Fixtures — FakeExporter + FakeCompliancePublisher + helpers
# ─────────────────────────────────────────────────────────────────────


class FakeExporter:
    """In-memory TelemetryExporter that records calls."""

    def __init__(self, *, fail_on_names: frozenset[str] | None = None) -> None:
        self.events: list[dict[str, Any]] = []
        self._fail_on_names = fail_on_names or frozenset()

    def export_event(
        self,
        *,
        name: str,
        trace_id: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        if name in self._fail_on_names:
            raise RuntimeError(f"Simulated export failure for {name}")
        self.events.append(
            {
                "name": name,
                "trace_id": trace_id,
                "attributes": dict(attributes) if attributes else {},
            }
        )

    def release_trace(self, trace_id: str) -> None:
        pass

    def shutdown(self) -> None:
        pass


class FakeCompliancePublisher:
    """In-memory CompliancePublisher that records dataset items and scores."""

    def __init__(self) -> None:
        self.dataset_items: list[dict[str, Any]] = []
        self.scores: list[dict[str, Any]] = []

    def create_dataset_item(
        self,
        *,
        dataset_name: str,
        input_data: dict[str, Any],
        item_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.dataset_items.append(
            {
                "dataset_name": dataset_name,
                "input_data": input_data,
                "item_id": item_id,
                "metadata": metadata,
            }
        )

    def score_trace(
        self,
        *,
        trace_id: str,
        name: str,
        value: float,
        comment: str | None = None,
    ) -> None:
        self.scores.append(
            {
                "trace_id": trace_id,
                "name": name,
                "value": value,
                "comment": comment,
            }
        )


def _make_event(
    event_type: EventType,
    *,
    workflow_id: str = "wf-e2e",
    step: int = 0,
    details: dict[str, Any] | None = None,
) -> TraceEvent:
    return TraceEvent(
        event_id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        event_type=event_type,
        timestamp=datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC),
        step=step,
        details=details or {},
    )


ALL_NINE_EVENT_TYPES = [
    (EventType.TASK_STARTED, {"task": "test"}),
    (EventType.STEP_PLANNED, {"plan": "step-1"}),
    (EventType.MODEL_SELECTED, {"model": "gpt-4o-mini", "reason": "steady-state"}),
    (EventType.GUARDRAIL_CHECKED, {"passed": True}),
    (EventType.STEP_EXECUTED, {"action": "search"}),
    (EventType.TOOL_CALLED, {"tool": "web_search", "args": "query"}),
    (
        EventType.PARAMETER_CHANGED,
        {"parameter": "model_tier", "old_value": "fast", "new_value": "capable"},
    ),
    (EventType.ERROR_OCCURRED, {"error": "timeout", "type": "retryable"}),
    (EventType.TASK_COMPLETED, {"outcome": "success"}),
]

EXPECTED_OBSERVATION_TYPES = {
    "task.started": "agent",
    "task.completed": "agent",
    "step.planned": "chain",
    "step.executed": "span",
    "tool.called": "tool",
    "model.selected": "chain",  # E5: routing decision, not an LLM call
    "guardrail.checked": "guardrail",
    "parameter.changed": "span",
    "error.occurred": "span",
}


def _record_all_nine(storage_dir: Path, workflow_id: str = "wf-e2e") -> None:
    """Record all 9 event types for a workflow using the real BlackBoxRecorder."""
    recorder = BlackBoxRecorder(storage_dir=storage_dir)
    for i, (event_type, details) in enumerate(ALL_NINE_EVENT_TYPES):
        recorder.record(
            _make_event(
                event_type,
                workflow_id=workflow_id,
                step=i,
                details=details,
            )
        )


def _build_relay(
    storage: Path,
    exporter: FakeExporter,
    compliance_publisher: FakeCompliancePublisher | None = None,
    **kwargs: Any,
):
    from middleware.sidecars.black_box_to_telemetry import BlackBoxToTelemetryRelay

    # This is the audit-complete (Option-B) pipeline harness — it verifies that
    # ALL nine event types (incl. STEP_EXECUTED / TOOL_CALLED) flow through with
    # correct types, redaction, and idempotency. Default to the dual view so the
    # Phase 4 curated suppression doesn't hide the events under test.
    kwargs.setdefault("curated_view", False)
    return BlackBoxToTelemetryRelay(
        storage_dir=storage,
        exporter=exporter,
        compliance_publisher=compliance_publisher,
        base_delay_s=0.0,
        **kwargs,
    )


@pytest.fixture()
def storage(tmp_path: Path) -> Path:
    return tmp_path / "black_box_recordings"


@pytest.fixture()
def exporter() -> FakeExporter:
    return FakeExporter()


@pytest.fixture()
def compliance_pub() -> FakeCompliancePublisher:
    return FakeCompliancePublisher()


# ─────────────────────────────────────────────────────────────────────
# A. FAILURE PATHS FIRST — DLQ, exporter failure, partial lines
# ─────────────────────────────────────────────────────────────────────


class TestPipelineFailurePaths:
    """Failure paths through the full pipeline."""

    def test_corrupted_json_goes_to_dlq_valid_events_still_publish(
        self,
        storage: Path,
        exporter: FakeExporter,
        compliance_pub: FakeCompliancePublisher,
    ) -> None:
        """A corrupt JSONL line should DLQ; surrounding valid events publish."""
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(_make_event(EventType.TASK_STARTED, details={"task": "t1"}))

        trace_file = storage / "wf-e2e" / "trace.jsonl"
        with open(trace_file, "a") as f:
            f.write("{INVALID JSON\n")

        recorder.record(
            _make_event(EventType.TASK_COMPLETED, details={"outcome": "success"})
        )

        (storage / "wf-e2e" / ".langfuse_offset").write_text("0")
        relay = _build_relay(storage, exporter, compliance_pub, max_retries=0)
        relay.run_once()

        exported_names = [e["name"] for e in exporter.events]
        assert "task.started" in exported_names
        assert "task.completed" in exported_names

        dlq_file = storage / "wf-e2e" / ".langfuse_failures.jsonl"
        assert dlq_file.exists()
        dlq_lines = dlq_file.read_text().strip().split("\n")
        assert len(dlq_lines) == 1

    def test_exporter_failure_on_specific_event_dlqs_only_that_event(
        self, storage: Path, compliance_pub: FakeCompliancePublisher
    ) -> None:
        """When exporter raises on one event type, only that event DLQs."""
        failing_exporter = FakeExporter(fail_on_names=frozenset({"step.executed"}))
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(_make_event(EventType.TASK_STARTED, details={"task": "t1"}))
        recorder.record(
            _make_event(EventType.STEP_EXECUTED, step=1, details={"action": "run"})
        )
        recorder.record(
            _make_event(
                EventType.TASK_COMPLETED, step=2, details={"outcome": "success"}
            )
        )

        (storage / "wf-e2e" / ".langfuse_offset").write_text("0")
        relay = _build_relay(storage, failing_exporter, compliance_pub, max_retries=0)
        relay.run_once()

        exported_names = [e["name"] for e in failing_exporter.events]
        assert "task.started" in exported_names
        assert "task.completed" in exported_names
        assert "step.executed" not in exported_names

        dlq_file = storage / "wf-e2e" / ".langfuse_failures.jsonl"
        assert dlq_file.exists()

    def test_partial_line_deferred_to_next_poll(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """Incomplete JSONL tail is deferred, not processed as corrupt."""
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(_make_event(EventType.TASK_STARTED, details={"task": "t1"}))
        (storage / "wf-e2e" / ".langfuse_offset").write_text("0")

        trace_file = storage / "wf-e2e" / "trace.jsonl"
        with open(trace_file, "a") as f:
            f.write('{"event_id": "partial", "workflow_id": "wf-e2e"')

        relay = _build_relay(storage, exporter)
        relay.run_once()

        assert len(exporter.events) == 1
        assert exporter.events[0]["name"] == "task.started"

        dlq_file = storage / "wf-e2e" / ".langfuse_failures.jsonl"
        assert not dlq_file.exists()


# ─────────────────────────────────────────────────────────────────────
# B. FULL PIPELINE FLOW — all 9 types, redaction, observation IDs
# ─────────────────────────────────────────────────────────────────────


class TestFullPipelineFlow:
    """All 9 event types flow through the pipeline correctly."""

    def test_all_nine_event_types_produce_correct_observation_types(
        self,
        storage: Path,
        exporter: FakeExporter,
        compliance_pub: FakeCompliancePublisher,
    ) -> None:
        _record_all_nine(storage)
        (storage / "wf-e2e" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_pub)
        published = relay.run_once()

        assert published == 9

        exported_names = {e["name"] for e in exporter.events}
        for expected_name in EXPECTED_OBSERVATION_TYPES:
            assert expected_name in exported_names, (
                f"Missing observation: {expected_name}"
            )

        for event in exporter.events:
            name = event["name"]
            expected_type = EXPECTED_OBSERVATION_TYPES[name]
            actual_type = event["attributes"].get("__bb_observation_type")
            assert actual_type == expected_type, (
                f"{name}: expected type={expected_type}, got {actual_type}"
            )

    def test_observation_id_matches_event_id_for_idempotency(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """Each exported event should carry __bb_observation_id == event_id."""
        recorder = BlackBoxRecorder(storage_dir=storage)
        event = _make_event(EventType.STEP_EXECUTED, details={"action": "run"})
        recorder.record(event)
        (storage / "wf-e2e" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()

        assert len(exporter.events) == 1
        attrs = exporter.events[0]["attributes"]
        assert attrs["__bb_observation_id"] == attrs["event_id"]

    def test_error_event_has_error_level(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """ERROR_OCCURRED events should carry __bb_level=ERROR."""
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(
            _make_event(
                EventType.ERROR_OCCURRED,
                details={"error": "timeout", "type": "retryable"},
            )
        )
        (storage / "wf-e2e" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()

        assert len(exporter.events) == 1
        assert exporter.events[0]["attributes"]["__bb_level"] == "ERROR"

    def test_non_error_events_have_default_level(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """Non-error events carry __bb_level=DEFAULT."""
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(_make_event(EventType.TASK_STARTED, details={"task": "t"}))
        (storage / "wf-e2e" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()

        assert exporter.events[0]["attributes"]["__bb_level"] == "DEFAULT"

    def test_pii_redacted_through_pipeline(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """PII in event details is scrubbed by the publisher before export."""
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(
            _make_event(
                EventType.STEP_EXECUTED,
                details={
                    "user_email": "alice@example.com",
                    "query": "normal text",
                },
            )
        )
        (storage / "wf-e2e" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()

        attrs = exporter.events[0]["attributes"]
        details = attrs["details"]
        assert "alice@example.com" not in str(details)
        assert details["query"] == "normal text"
        if "__output" in attrs:
            assert "alice@example.com" not in str(attrs["__output"])

    def test_api_key_redacted_through_pipeline(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """API keys in event details are scrubbed by the publisher."""
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(
            _make_event(
                EventType.STEP_EXECUTED,
                details={"config": "key=sk-abc123def456ghi789jkl012mno345pqrstu678vwx"},
            )
        )
        (storage / "wf-e2e" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()

        details_str = str(exporter.events[0]["attributes"]["details"])
        assert "sk-abc123def456ghi789jkl012mno345pqrstu678vwx" not in details_str

    def test_long_detail_values_truncated_at_200_chars(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """Detail values exceeding 200 characters are truncated."""
        long_val = "x" * 300
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(
            _make_event(
                EventType.STEP_EXECUTED,
                details={"long_field": long_val},
            )
        )
        (storage / "wf-e2e" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()

        details = exporter.events[0]["attributes"]["details"]
        assert len(details["long_field"]) <= 200

    def test_trace_id_equals_workflow_id(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """Exported trace_id must equal the BlackBox workflow_id (§2.2 design)."""
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(
            _make_event(
                EventType.TASK_STARTED,
                workflow_id="wf-trace-match",
                details={"task": "test"},
            )
        )
        (storage / "wf-trace-match" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()

        assert exporter.events[0]["trace_id"] == "wf-trace-match"

    def test_integrity_hash_preserved_in_attributes(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """The integrity_hash from the BlackBox chain is forwarded in attributes."""
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(_make_event(EventType.TASK_STARTED, details={"task": "t"}))
        (storage / "wf-e2e" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()

        attrs = exporter.events[0]["attributes"]
        assert "integrity_hash" in attrs
        assert len(attrs["integrity_hash"]) == 64


# ─────────────────────────────────────────────────────────────────────
# C. MULTI-WORKFLOW ISOLATION — independent processing
# ─────────────────────────────────────────────────────────────────────


class TestMultiWorkflowIsolation:
    """Multiple workflows are processed independently."""

    def test_two_workflows_process_independently(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """Each workflow has its own offset and events are attributed correctly."""
        recorder = BlackBoxRecorder(storage_dir=storage)

        recorder.record(
            _make_event(
                EventType.TASK_STARTED, workflow_id="wf-A", details={"task": "A"}
            )
        )
        recorder.record(
            _make_event(
                EventType.TASK_STARTED, workflow_id="wf-B", details={"task": "B"}
            )
        )
        recorder.record(
            _make_event(
                EventType.STEP_EXECUTED, workflow_id="wf-A", step=1, details={"a": 1}
            )
        )
        recorder.record(
            _make_event(
                EventType.STEP_EXECUTED, workflow_id="wf-B", step=1, details={"b": 1}
            )
        )

        (storage / "wf-A" / ".langfuse_offset").write_text("0")
        (storage / "wf-B" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        published = relay.run_once()

        assert published == 4

        wf_a_events = [e for e in exporter.events if e["trace_id"] == "wf-A"]
        wf_b_events = [e for e in exporter.events if e["trace_id"] == "wf-B"]
        assert len(wf_a_events) == 2
        assert len(wf_b_events) == 2

    def test_compliance_bundle_per_workflow(
        self,
        storage: Path,
        exporter: FakeExporter,
        compliance_pub: FakeCompliancePublisher,
    ) -> None:
        """Each TASK_COMPLETED triggers its own compliance bundle."""
        recorder = BlackBoxRecorder(storage_dir=storage)

        for wf_id in ("wf-X", "wf-Y"):
            recorder.record(
                _make_event(
                    EventType.TASK_STARTED, workflow_id=wf_id, details={"task": wf_id}
                )
            )
            recorder.record(
                _make_event(
                    EventType.TASK_COMPLETED,
                    workflow_id=wf_id,
                    step=1,
                    details={"outcome": "success"},
                )
            )
            (storage / wf_id / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_pub)
        relay.run_once()

        workflow_ids_in_items = {
            item["input_data"]["workflow_id"] for item in compliance_pub.dataset_items
        }
        assert "wf-X" in workflow_ids_in_items
        assert "wf-Y" in workflow_ids_in_items

        workflow_ids_in_scores = {s["trace_id"] for s in compliance_pub.scores}
        assert "wf-X" in workflow_ids_in_scores
        assert "wf-Y" in workflow_ids_in_scores

    def test_one_workflow_failure_does_not_block_other(
        self, storage: Path, compliance_pub: FakeCompliancePublisher
    ) -> None:
        """If exporter fails for one workflow's events, the other still processes."""
        failing_exporter = FakeExporter(fail_on_names=frozenset({"task.started"}))
        recorder = BlackBoxRecorder(storage_dir=storage)

        recorder.record(
            _make_event(
                EventType.TASK_STARTED, workflow_id="wf-fail", details={"task": "x"}
            )
        )
        recorder.record(
            _make_event(
                EventType.STEP_EXECUTED, workflow_id="wf-ok", details={"action": "y"}
            )
        )

        (storage / "wf-fail" / ".langfuse_offset").write_text("0")
        (storage / "wf-ok" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, failing_exporter, compliance_pub, max_retries=0)
        relay.run_once()

        exported_trace_ids = {e["trace_id"] for e in failing_exporter.events}
        assert "wf-ok" in exported_trace_ids


# ─────────────────────────────────────────────────────────────────────
# D. STARTUP-FROM-BEGINNING + INCREMENTAL PROCESSING
#
# Canonical relay semantics (commit 9d06699): an absent ``.langfuse_offset``
# starts from offset 0 so the in-process (Cloud Run) relay never skips events
# written before its first poll. Duplicate exports are dedup-safe via
# ``observation_id``. Mirrors TestStartupFromBeginning in
# test_black_box_to_telemetry.py.
# ─────────────────────────────────────────────────────────────────────


class TestStartupAndIncremental:
    """Startup and incremental processing behavior."""

    def test_absent_offset_processes_existing_events(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """Startup-from-beginning: absent .langfuse_offset → process existing events."""
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(_make_event(EventType.TASK_STARTED, details={"task": "old"}))
        recorder.record(_make_event(EventType.STEP_EXECUTED, details={"old": True}))

        relay = _build_relay(storage, exporter)
        published = relay.run_once()

        assert published == 2
        assert len(exporter.events) == 2

        offset_file = storage / "wf-e2e" / ".langfuse_offset"
        assert offset_file.exists()

    def test_new_events_after_startup_are_processed(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """Events appended after the initial poll get processed incrementally."""
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(_make_event(EventType.TASK_STARTED, details={"task": "old"}))

        relay = _build_relay(storage, exporter)
        relay.run_once()
        assert len(exporter.events) == 1

        recorder.record(
            _make_event(EventType.STEP_EXECUTED, step=1, details={"new": True})
        )
        relay.run_once()

        assert len(exporter.events) == 2
        assert exporter.events[1]["name"] == "step.executed"

    def test_offset_advances_correctly_across_polls(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """Offset advances on each poll, preventing re-processing."""
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(_make_event(EventType.TASK_STARTED, details={"task": "t1"}))
        (storage / "wf-e2e" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()
        assert len(exporter.events) == 1

        recorder.record(_make_event(EventType.STEP_EXECUTED, step=1, details={"a": 1}))
        relay.run_once()
        assert len(exporter.events) == 2

        relay.run_once()
        assert len(exporter.events) == 2


# ─────────────────────────────────────────────────────────────────────
# E. DEV RELAY COMPLIANCE GAP VERIFICATION
# ─────────────────────────────────────────────────────────────────────


class TestDevRelayComplianceGap:
    """Verify _build_dev_relay passes compliance_publisher when exporter
    satisfies the CompliancePublisher protocol."""

    def test_dev_relay_with_compliance_capable_exporter(self) -> None:
        """When exporter satisfies CompliancePublisher, relay gets it."""
        from middleware.ports.compliance_publisher import CompliancePublisher

        class _FakeComplianceExporter:
            """Satisfies both TelemetryExporter and CompliancePublisher."""

            def export_event(self, *, name, trace_id, attributes=None):
                pass

            def release_trace(self, trace_id):
                pass

            def shutdown(self):
                pass

            def create_dataset_item(
                self, *, dataset_name, input_data, item_id=None, metadata=None
            ):
                pass

            def score_trace(self, *, trace_id, name, value, comment=None):
                pass

        exp = _FakeComplianceExporter()
        assert isinstance(exp, CompliancePublisher)

        import os

        old_mode = os.environ.get("BLACKBOX_RELAY_MODE")
        old_storage = os.environ.get("BLACKBOX_STORAGE_DIR")
        try:
            os.environ["BLACKBOX_RELAY_MODE"] = "in_process"
            os.environ.pop("BLACKBOX_STORAGE_DIR", None)

            from middleware.__main__ import _build_dev_relay

            relay = _build_dev_relay(exp, Path("/tmp/test-cache"))
            assert relay is not None
            assert relay._compliance_publisher is not None
        finally:
            if old_mode is not None:
                os.environ["BLACKBOX_RELAY_MODE"] = old_mode
            else:
                os.environ.pop("BLACKBOX_RELAY_MODE", None)
            if old_storage is not None:
                os.environ["BLACKBOX_STORAGE_DIR"] = old_storage

    def test_dev_relay_without_compliance_capable_exporter(self) -> None:
        """When exporter lacks CompliancePublisher methods, relay has None."""
        import os

        old_mode = os.environ.get("BLACKBOX_RELAY_MODE")
        try:
            os.environ["BLACKBOX_RELAY_MODE"] = "in_process"
            os.environ.pop("BLACKBOX_STORAGE_DIR", None)

            from middleware.__main__ import _build_dev_relay

            plain_exporter = FakeExporter()
            relay = _build_dev_relay(plain_exporter, Path("/tmp/test-cache"))
            assert relay is not None
            assert relay._compliance_publisher is None
        finally:
            if old_mode is not None:
                os.environ["BLACKBOX_RELAY_MODE"] = old_mode
            else:
                os.environ.pop("BLACKBOX_RELAY_MODE", None)


# ─────────────────────────────────────────────────────────────────────
# F. COMPLIANCE + PIPELINE INTEGRATION
# ─────────────────────────────────────────────────────────────────────


class TestCompliancePipelineIntegration:
    """Compliance bundle flows end-to-end through the pipeline."""

    def test_full_workflow_produces_audit_dataset_and_score(
        self,
        storage: Path,
        exporter: FakeExporter,
        compliance_pub: FakeCompliancePublisher,
    ) -> None:
        """A complete valid workflow produces audit dataset item + score=1.0."""
        _record_all_nine(storage, workflow_id="wf-full")
        (storage / "wf-full" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_pub)
        relay.run_once()

        audit_items = [
            item
            for item in compliance_pub.dataset_items
            if item["dataset_name"] == "agent-compliance-audit"
        ]
        assert len(audit_items) == 1
        assert audit_items[0]["input_data"]["hash_chain_valid"] is True
        assert audit_items[0]["input_data"]["event_count"] == 9

        scores = [s for s in compliance_pub.scores if s["trace_id"] == "wf-full"]
        assert len(scores) == 1
        assert scores[0]["value"] == 1.0

    def test_tampered_chain_produces_incident_dataset_and_zero_score(
        self,
        storage: Path,
        exporter: FakeExporter,
        compliance_pub: FakeCompliancePublisher,
    ) -> None:
        """A workflow with tampered hash chain → incident dataset + score=0.0."""
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(
            _make_event(
                EventType.TASK_STARTED, workflow_id="wf-tampered", details={"task": "t"}
            )
        )
        recorder.record(
            _make_event(
                EventType.STEP_EXECUTED,
                workflow_id="wf-tampered",
                step=1,
                details={"a": 1},
            )
        )
        recorder.record(
            _make_event(
                EventType.TASK_COMPLETED,
                workflow_id="wf-tampered",
                step=2,
                details={"outcome": "success"},
            )
        )

        trace_file = storage / "wf-tampered" / "trace.jsonl"
        lines = trace_file.read_text().strip().split("\n")
        event_data = json.loads(lines[1])
        event_data["integrity_hash"] = "0" * 64
        lines[1] = json.dumps(event_data, default=str)
        trace_file.write_text("\n".join(lines) + "\n")

        (storage / "wf-tampered" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_pub)
        relay.run_once()

        incident_items = [
            item
            for item in compliance_pub.dataset_items
            if item["dataset_name"] == "agent-incident-replay"
        ]
        assert len(incident_items) == 1
        assert incident_items[0]["input_data"]["hash_chain_valid"] is False

        scores = [s for s in compliance_pub.scores if s["trace_id"] == "wf-tampered"]
        assert len(scores) == 1
        assert scores[0]["value"] == 0.0
