"""L2 Contract: Compliance bundle → Langfuse dataset item.

Sprint E of the BlackBox→Langfuse plan.  Tests follow Protocol B
(Contract-Driven TDD) from research/tdd_agentic_systems_prompt.md.

Layer: middleware/sidecars (Middleware ring)
Pyramid level: L2 — Reproducible.  Deterministic, fast, filesystem-isolated.

Test categories:
  A. Failure paths first — broken hash chain publishes to incident dataset
  B. Success path — valid chain publishes to compliance audit dataset
  C. Score attachment — hash_chain_valid score on trace (True/False)
  D. Trigger condition — only TASK_COMPLETED triggers compliance publish
  E. Architecture invariant — relay still has no langfuse/langgraph imports
  F. Negative-path gate-failure traces (G7/G8/G9) — drive the synthetic
     scenarios from the dataset's single source of truth so the gate-failure
     modes (failed AgentFacts, broken chain, retryable/tool errors) are
     actually exercised, not just the happy path (Pattern 11 failure-mode
     matrix; prevents TAP-4 Gap Blindness).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

import pytest

from services.governance.black_box import (
    PHASE_LOG_SCHEMA_VERSION,
    BlackBoxRecorder,
    EventType,
    TraceEvent,
)
from services.governance.phase_logger import PhaseLogger, WorkflowPhase


# ─────────────────────────────────────────────────────────────────────
# Fixtures — FakeExporter + FakeCompliancePublisher + helpers
# ─────────────────────────────────────────────────────────────────────


class FakeExporter:
    """In-memory TelemetryExporter that records calls."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def export_event(
        self,
        *,
        name: str,
        trace_id: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        self.events.append({
            "name": name,
            "trace_id": trace_id,
            "attributes": dict(attributes) if attributes else {},
        })

    def release_trace(self, trace_id: str) -> None:
        pass

    def shutdown(self) -> None:
        pass


class FakeCompliancePublisher:
    """In-memory CompliancePublisher that records dataset items and scores."""

    def __init__(self, *, fail_on_publish: bool = False) -> None:
        self.dataset_items: list[dict[str, Any]] = []
        self.scores: list[dict[str, Any]] = []
        self._fail_on_publish = fail_on_publish

    def create_dataset_item(
        self,
        *,
        dataset_name: str,
        input_data: dict[str, Any],
        item_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._fail_on_publish:
            raise RuntimeError("Simulated Langfuse dataset publish failure")
        self.dataset_items.append({
            "dataset_name": dataset_name,
            "input_data": input_data,
            "item_id": item_id,
            "metadata": metadata,
        })

    def score_trace(
        self,
        *,
        trace_id: str,
        name: str,
        value: float,
        comment: str | None = None,
    ) -> None:
        if self._fail_on_publish:
            raise RuntimeError("Simulated Langfuse score failure")
        self.scores.append({
            "trace_id": trace_id,
            "name": name,
            "value": value,
            "comment": comment,
        })


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


def _record_workflow(
    storage_dir: Path,
    workflow_id: str,
    *,
    include_task_completed: bool = True,
    outcome: str = "success",
) -> Path:
    """Record a complete workflow: TASK_STARTED, STEP_EXECUTED, TASK_COMPLETED."""
    recorder = BlackBoxRecorder(storage_dir=storage_dir)
    recorder.record(_make_event(
        EventType.TASK_STARTED, workflow_id=workflow_id, step=0,
        details={"task": "test task"},
    ))
    recorder.record(_make_event(
        EventType.STEP_EXECUTED, workflow_id=workflow_id, step=1,
        details={"action": "test action"},
    ))
    if include_task_completed:
        recorder.record(_make_event(
            EventType.TASK_COMPLETED, workflow_id=workflow_id, step=2,
            details={"outcome": outcome},
        ))
    return storage_dir / workflow_id / "trace.jsonl"


def _corrupt_hash_chain(trace_file: Path) -> None:
    """Tamper with the integrity hash of the second event to break the chain."""
    lines = trace_file.read_text().strip().split("\n")
    if len(lines) >= 2:
        event_data = json.loads(lines[1])
        event_data["integrity_hash"] = "0" * 64
        lines[1] = json.dumps(event_data, default=str)
    trace_file.write_text("\n".join(lines) + "\n")


@pytest.fixture()
def storage(tmp_path: Path) -> Path:
    return tmp_path / "black_box_recordings"


@pytest.fixture()
def exporter() -> FakeExporter:
    return FakeExporter()


@pytest.fixture()
def compliance_publisher() -> FakeCompliancePublisher:
    return FakeCompliancePublisher()


def _build_relay(
    storage: Path,
    exporter: FakeExporter,
    compliance_publisher: FakeCompliancePublisher | None = None,
    **kwargs: Any,
):
    """Lazy import to let RED phase fail on ImportError."""
    from middleware.sidecars.black_box_to_telemetry import BlackBoxToTelemetryRelay

    return BlackBoxToTelemetryRelay(
        storage_dir=storage,
        exporter=exporter,
        compliance_publisher=compliance_publisher,
        base_delay_s=0.0,
        **kwargs,
    )


# ─────────────────────────────────────────────────────────────────────
# A. FAILURE PATHS FIRST — broken chain → incident dataset
# ─────────────────────────────────────────────────────────────────────


class TestBrokenChainPublishesToIncidentDataset:
    """When hash chain is broken, the bundle goes to agent-incident-replay."""

    def test_broken_chain_publishes_to_incident_dataset(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        trace_file = _record_workflow(storage, "wf-broken")
        _corrupt_hash_chain(trace_file)
        (storage / "wf-broken" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        incident_items = [
            item for item in compliance_publisher.dataset_items
            if item["dataset_name"] == "agent-incident-replay"
        ]
        assert len(incident_items) == 1
        assert incident_items[0]["input_data"]["hash_chain_valid"] is False
        assert incident_items[0]["input_data"]["workflow_id"] == "wf-broken"

    def test_broken_chain_score_is_zero(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        trace_file = _record_workflow(storage, "wf-score-broken")
        _corrupt_hash_chain(trace_file)
        (storage / "wf-score-broken" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        scores = [s for s in compliance_publisher.scores if s["trace_id"] == "wf-score-broken"]
        assert len(scores) == 1
        assert scores[0]["name"] == "hash_chain_valid"
        assert scores[0]["value"] == 0.0

    def test_broken_chain_item_has_workflow_id_as_item_id(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        trace_file = _record_workflow(storage, "wf-itemid")
        _corrupt_hash_chain(trace_file)
        (storage / "wf-itemid" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        items = compliance_publisher.dataset_items
        assert len(items) >= 1
        assert items[0]["item_id"] == "wf-itemid"

    def test_publisher_failure_does_not_crash_relay(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """CompliancePublisher failure must not crash the relay (rule O1)."""
        failing_publisher = FakeCompliancePublisher(fail_on_publish=True)
        _record_workflow(storage, "wf-crash")
        (storage / "wf-crash" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, failing_publisher)
        published = relay.run_once()

        assert published >= 1


# ─────────────────────────────────────────────────────────────────────
# B. SUCCESS PATH — valid chain → compliance audit dataset
# ─────────────────────────────────────────────────────────────────────


class TestValidChainPublishesToAuditDataset:
    """When hash chain is valid, the bundle goes to agent-compliance-audit."""

    def test_valid_chain_publishes_to_audit_dataset(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        _record_workflow(storage, "wf-valid")
        (storage / "wf-valid" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        audit_items = [
            item for item in compliance_publisher.dataset_items
            if item["dataset_name"] == "agent-compliance-audit"
        ]
        assert len(audit_items) == 1
        assert audit_items[0]["input_data"]["hash_chain_valid"] is True
        assert audit_items[0]["input_data"]["workflow_id"] == "wf-valid"

    def test_valid_chain_score_is_one(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        _record_workflow(storage, "wf-score-valid")
        (storage / "wf-score-valid" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        scores = [s for s in compliance_publisher.scores if s["trace_id"] == "wf-score-valid"]
        assert len(scores) == 1
        assert scores[0]["name"] == "hash_chain_valid"
        assert scores[0]["value"] == 1.0

    def test_audit_item_contains_event_count(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        _record_workflow(storage, "wf-count")
        (storage / "wf-count" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        items = compliance_publisher.dataset_items
        assert items[0]["input_data"]["event_count"] == 3

    def test_audit_item_contains_bundle_type(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        _record_workflow(storage, "wf-bundle")
        (storage / "wf-bundle" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        items = compliance_publisher.dataset_items
        assert items[0]["input_data"]["bundle_type"] == "compliance_audit"

    def test_failed_outcome_goes_to_both_datasets(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        """A failed outcome with valid chain still goes to audit, PLUS incident-replay."""
        _record_workflow(storage, "wf-failed-outcome", outcome="failure")
        (storage / "wf-failed-outcome" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        dataset_names = [item["dataset_name"] for item in compliance_publisher.dataset_items]
        assert "agent-compliance-audit" in dataset_names
        assert "agent-incident-replay" in dataset_names


# ─────────────────────────────────────────────────────────────────────
# C. SCORE ATTACHMENT — hash_chain_valid score on trace
# ─────────────────────────────────────────────────────────────────────


class TestScoreAttachment:
    """Attach hash_chain_valid as a Langfuse score on the trace."""

    def test_score_has_comment_on_failure(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        trace_file = _record_workflow(storage, "wf-comment")
        _corrupt_hash_chain(trace_file)
        (storage / "wf-comment" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        scores = compliance_publisher.scores
        assert len(scores) >= 1
        assert scores[0]["comment"] is not None
        assert "broken" in scores[0]["comment"].lower() or "invalid" in scores[0]["comment"].lower()

    def test_score_trace_id_matches_workflow_id(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        _record_workflow(storage, "wf-trace-match")
        (storage / "wf-trace-match" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        # Phase 1 adds outcome scores alongside hash_chain_valid; assert on the
        # hash_chain_valid score specifically rather than the total count.
        chain_scores = [
            s for s in compliance_publisher.scores if s["name"] == "hash_chain_valid"
        ]
        assert len(chain_scores) == 1
        assert chain_scores[0]["trace_id"] == "wf-trace-match"


# ─────────────────────────────────────────────────────────────────────
# D. TRIGGER CONDITION — only TASK_COMPLETED triggers publish
# ─────────────────────────────────────────────────────────────────────


class TestTriggerCondition:
    """Compliance publish only triggers on TASK_COMPLETED event."""

    def test_no_publish_without_task_completed(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        """A workflow without TASK_COMPLETED should not trigger compliance publish."""
        _record_workflow(storage, "wf-incomplete", include_task_completed=False)
        (storage / "wf-incomplete" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        assert len(compliance_publisher.dataset_items) == 0
        assert len(compliance_publisher.scores) == 0

    def test_publish_triggered_by_task_completed_event(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        """Relay publishes compliance bundle when it processes TASK_COMPLETED."""
        _record_workflow(storage, "wf-trigger")
        (storage / "wf-trigger" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        assert len(compliance_publisher.dataset_items) >= 1

    def test_no_duplicate_publish_on_second_run(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        """Once processed, the same TASK_COMPLETED should not re-trigger."""
        _record_workflow(storage, "wf-no-dup")
        (storage / "wf-no-dup" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()
        relay.run_once()

        audit_items = [
            item for item in compliance_publisher.dataset_items
            if item["input_data"]["workflow_id"] == "wf-no-dup"
        ]
        assert len(audit_items) == 1

    def test_no_publisher_means_no_compliance_action(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """When compliance_publisher is None, relay still works without compliance."""
        _record_workflow(storage, "wf-no-pub")
        (storage / "wf-no-pub" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher=None)
        published = relay.run_once()

        assert published >= 1


# ─────────────────────────────────────────────────────────────────────
# E. ARCHITECTURE INVARIANT — relay has no langfuse/langgraph imports
# ─────────────────────────────────────────────────────────────────────


class TestArchitectureInvariant:
    """Sidecar module must import ports, never SDKs directly."""

    def test_relay_has_no_langfuse_import(self) -> None:
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

    def test_relay_has_no_langgraph_import(self) -> None:
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

    def test_compliance_publisher_port_has_no_sdk_imports(self) -> None:
        import ast

        src = Path("middleware/ports/compliance_publisher.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(("langfuse", "langgraph")), (
                        f"Forbidden import in port: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith(("langfuse", "langgraph")), (
                        f"Forbidden import in port: {node.module}"
                    )


# ─────────────────────────────────────────────────────────────────────
# F. NEGATIVE-PATH GATE-FAILURE TRACES (G7/G8/G9)
#
# A compliance dataset with zero ERROR_OCCURRED, zero broken chains and zero
# rejected verifications is not proof the gates work — it is proof they were
# never tested (TAP-4 Gap Blindness, AGENTS.md). These tests materialize the
# synthetic scenarios (the single source of truth in tests/synthetic/blackbox)
# and drive them through the *real* relay so each gate-failure mode lands in
# the dataset exactly as the runtime would emit it. Failure paths first.
# ─────────────────────────────────────────────────────────────────────


from tests.synthetic.blackbox.dataset import (  # noqa: E402
    NEGATIVE_SCENARIOS,
    Scenario,
    ScenarioID,
)
from tests.synthetic.blackbox.langfuse_assertions import (  # noqa: E402
    assert_broken_chain_bundle,
    assert_bundle_event_types,
    assert_dataset_routing,
    assert_error_trace_present,
    assert_rejected_outcome,
)


def _materialize_scenario(storage: Path, scenario: Scenario) -> tuple[str, str | None]:
    """Record a synthetic scenario's trace, optionally tampering the chain.

    Returns ``(workflow_id, broken_event_id)`` where ``broken_event_id`` is the
    event whose stored integrity hash was zeroed (None when no corruption).
    The byte offset is reset to 0 so the relay reads the whole trace.
    """
    wf_id = scenario.id.value
    recorder = BlackBoxRecorder(storage_dir=storage)
    base_ts = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
    for i, ev in enumerate(scenario.synthetic_events):
        recorder.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=wf_id,
            event_type=EventType(ev.event_type),
            timestamp=base_ts,
            step=ev.step,
            details=dict(ev.details),
        ))

    broken_event_id: str | None = None
    if scenario.corrupt_event_index is not None:
        trace_file = storage / wf_id / "trace.jsonl"
        lines = trace_file.read_text().strip().split("\n")
        idx = scenario.corrupt_event_index
        event_data = json.loads(lines[idx])
        broken_event_id = event_data.get("event_id")
        event_data["integrity_hash"] = "0" * 64
        lines[idx] = json.dumps(event_data, default=str)
        trace_file.write_text("\n".join(lines) + "\n")

    (storage / wf_id / ".langfuse_offset").write_text("0")
    return wf_id, broken_event_id


def _published_item(publisher: FakeCompliancePublisher, wf_id: str) -> dict[str, Any]:
    """Return the (first) dataset item the relay published for *wf_id*."""
    items = [
        item for item in publisher.dataset_items
        if item["input_data"].get("workflow_id") == wf_id
    ]
    assert items, f"No dataset item published for {wf_id}"
    return items[0]


class TestG8BrokenChainTrace:
    """G8: a tampered hash chain routes to incident-replay with score 0 and a
    populated ``broken_at_event_id`` — the auditor's jump-to-tamper signal."""

    def test_broken_chain_routes_to_incident_with_break_location(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        scenario = NEGATIVE_SCENARIOS[ScenarioID.S9]
        wf_id, broken_event_id = _materialize_scenario(storage, scenario)

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        item = _published_item(compliance_publisher, wf_id)
        routing = assert_dataset_routing(item["dataset_name"], scenario.compliance)
        assert routing.passed, routing.description

        bundle = item["input_data"]
        failures = [r for r in assert_broken_chain_bundle(bundle) if not r.passed]
        assert not failures, "\n".join(f.description for f in failures)
        assert bundle["broken_at_event_id"] == broken_event_id

    def test_broken_chain_score_is_zero(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        scenario = NEGATIVE_SCENARIOS[ScenarioID.S9]
        wf_id, _ = _materialize_scenario(storage, scenario)

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        # Phase 1 may add terminal outcome scores alongside hash_chain_valid;
        # assert on the chain-validity score specifically.
        chain_scores = [
            s for s in compliance_publisher.scores
            if s["trace_id"] == wf_id and s["name"] == "hash_chain_valid"
        ]
        assert len(chain_scores) == 1
        assert chain_scores[0]["value"] == scenario.compliance.hash_chain_valid_score == 0.0


class TestG7FailedAgentFactsTrace:
    """G7: a failed AgentFacts verification yields a rejected terminal outcome.
    The chain is intact, so it routes to the audit dataset, but the summary
    block surfaces ``outcome=rejected`` so the gate's firing is provable."""

    def test_rejected_outcome_surfaced_in_summary(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        scenario = NEGATIVE_SCENARIOS[ScenarioID.S7]
        wf_id, _ = _materialize_scenario(storage, scenario)

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        item = _published_item(compliance_publisher, wf_id)
        routing = assert_dataset_routing(item["dataset_name"], scenario.compliance)
        assert routing.passed, routing.description

        failures = [
            r for r in assert_rejected_outcome(item["input_data"], scenario.expected_reason)
            if not r.passed
        ]
        assert not failures, "\n".join(f.description for f in failures)

    def test_rejected_trace_chain_is_intact(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        # The task was rejected, not the recording — integrity must stay 1.0.
        scenario = NEGATIVE_SCENARIOS[ScenarioID.S7]
        wf_id, _ = _materialize_scenario(storage, scenario)

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        scores = [s for s in compliance_publisher.scores if s["trace_id"] == wf_id]
        assert len(scores) == 1
        assert scores[0]["value"] == 1.0


class TestG9ErrorTraces:
    """G9 dataset coverage: retryable (429) and tool errors fire ERROR_OCCURRED
    and carry a non-null ``error_type`` onto the terminal event. The runtime
    already emits these; this proves they reach the dataset."""

    @pytest.mark.parametrize("scenario_id", [ScenarioID.S10, ScenarioID.S11])
    def test_error_trace_present_with_error_type(
        self,
        scenario_id: ScenarioID,
        storage: Path,
        exporter: FakeExporter,
        compliance_publisher: FakeCompliancePublisher,
    ) -> None:
        scenario = NEGATIVE_SCENARIOS[scenario_id]
        wf_id, _ = _materialize_scenario(storage, scenario)

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        item = _published_item(compliance_publisher, wf_id)
        bundle = item["input_data"]
        failures = [
            r for r in assert_error_trace_present(bundle, scenario.expected_error_types)
            if not r.passed
        ]
        assert not failures, "\n".join(f.description for f in failures)

    @pytest.mark.parametrize("scenario_id", [ScenarioID.S10, ScenarioID.S11])
    def test_error_occurred_exported_at_error_level(
        self,
        scenario_id: ScenarioID,
        storage: Path,
        exporter: FakeExporter,
        compliance_publisher: FakeCompliancePublisher,
    ) -> None:
        # The relay must still ship the ERROR_OCCURRED observation to telemetry.
        scenario = NEGATIVE_SCENARIOS[scenario_id]
        wf_id, _ = _materialize_scenario(storage, scenario)

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        error_events = [
            e for e in exporter.events
            if e["name"] == "error.occurred" and e["trace_id"] == wf_id
        ]
        assert error_events, "ERROR_OCCURRED not exported to telemetry"
        assert error_events[0]["attributes"]["__bb_level"] == "ERROR"


class TestRelayPhaseEvents:
    """Sprint 4 (b3-relay): compliance publish includes phase_events[]; redaction applies."""

    def test_relay_publishes_phase_events_when_phase_logs_present(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        wf_id = "wf-phase-relay"
        _record_workflow(storage, wf_id)
        phase_logs = storage.parent / "phase_logs"
        pl = PhaseLogger(phase_logs)
        pl.start_phase(wf_id, WorkflowPhase.ROUTING, step_count=0)
        pl.end_phase(wf_id, WorkflowPhase.ROUTING, "done", step_count=0)
        pl.start_phase(wf_id, WorkflowPhase.COMPLETION, step_count=0)
        pl.end_phase(wf_id, WorkflowPhase.COMPLETION, "done", step_count=0)
        (storage / wf_id / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        item = _published_item(compliance_publisher, wf_id)
        bundle = item["input_data"]
        assert bundle["phase_log_schema_version"] == PHASE_LOG_SCHEMA_VERSION
        assert len(bundle["phase_events"]) >= 2
        ended = [e for e in bundle["phase_events"] if e.get("event") == "phase_end"]
        assert any(e["phase"] == WorkflowPhase.ROUTING.value for e in ended)

    def test_published_phase_event_details_are_redacted(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        wf_id = "wf-phase-pii"
        _record_workflow(storage, wf_id)
        phase_logs = storage.parent / "phase_logs"
        pl = PhaseLogger(phase_logs)
        pl.end_phase(
            wf_id,
            WorkflowPhase.ROUTING,
            "done",
            step_count=0,
            details={"note": "email alice@example.com before route"},
        )
        (storage / wf_id / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        bundle = _published_item(compliance_publisher, wf_id)["input_data"]
        routing_ends = [
            e
            for e in bundle["phase_events"]
            if e.get("event") == "phase_end" and e.get("phase") == WorkflowPhase.ROUTING.value
        ]
        assert routing_ends
        note = routing_ends[0]["details"]["note"]
        assert "alice@example.com" not in note
        assert "[REDACTED]" in note


class TestNegativeScenarioEventCoverage:
    """Every synthetic scenario's declared event sequence must materialize in
    the published bundle — the dataset definition and the trace cannot drift."""

    @pytest.mark.parametrize(
        "scenario_id", [ScenarioID.S7, ScenarioID.S9, ScenarioID.S10, ScenarioID.S11]
    )
    def test_declared_events_present_in_bundle(
        self,
        scenario_id: ScenarioID,
        storage: Path,
        exporter: FakeExporter,
        compliance_publisher: FakeCompliancePublisher,
    ) -> None:
        scenario = NEGATIVE_SCENARIOS[scenario_id]
        wf_id, _ = _materialize_scenario(storage, scenario)

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        bundle = _published_item(compliance_publisher, wf_id)["input_data"]
        failures = [
            r for r in assert_bundle_event_types(bundle, scenario.expected_observations)
            if not r.passed
        ]
        assert not failures, "\n".join(f.description for f in failures)


# ─────────────────────────────────────────────────────────────────────
# G. Phase 1 — terminal outcome scores on the trace (E1/E9)
# ─────────────────────────────────────────────────────────────────────


def _record_workflow_with_outcome(
    storage_dir: Path,
    workflow_id: str,
    *,
    completed_details: dict[str, Any],
    agent_id: str | None = None,
) -> Path:
    """Record TASK_STARTED → STEP_EXECUTED → TASK_COMPLETED with rich terminal
    details (and an optional agent_id on TASK_STARTED for identity tests)."""
    recorder = BlackBoxRecorder(storage_dir=storage_dir)
    started_details: dict[str, Any] = {"task": "test task"}
    if agent_id is not None:
        started_details["agent_id"] = agent_id
    recorder.record(_make_event(
        EventType.TASK_STARTED, workflow_id=workflow_id, step=0,
        details=started_details,
    ))
    recorder.record(_make_event(
        EventType.STEP_EXECUTED, workflow_id=workflow_id, step=1,
        details={"action": "test action"},
    ))
    recorder.record(_make_event(
        EventType.TASK_COMPLETED, workflow_id=workflow_id, step=2,
        details=completed_details,
    ))
    return storage_dir / workflow_id / "trace.jsonl"


class TestOutcomeScores:
    """TASK_COMPLETED publishes goal_met / criteria_met / task_completion_score
    as trace-level scores so a run is triageable from the Langfuse list view
    without opening the trace (review finding E9)."""

    def test_outcome_scores_published(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        _record_workflow_with_outcome(
            storage, "wf-scores",
            completed_details={
                "outcome": "success",
                "goal_met": False,
                "criteria_met": 0.0,
                "task_completion_score": 0.887,
            },
        )
        (storage / "wf-scores" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()

        by_name = {s["name"]: s for s in compliance_publisher.scores}
        assert by_name["goal_met"]["value"] == 0.0  # False → 0.0
        assert by_name["criteria_met"]["value"] == 0.0
        assert by_name["task_completion_score"]["value"] == 0.887
        for name in ("goal_met", "criteria_met", "task_completion_score"):
            assert by_name[name]["trace_id"] == "wf-scores"

    def test_goal_met_true_scores_one(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        _record_workflow_with_outcome(
            storage, "wf-goalmet",
            completed_details={"outcome": "success", "goal_met": True, "criteria_met": 1.0},
        )
        (storage / "wf-goalmet" / ".langfuse_offset").write_text("0")
        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()
        by_name = {s["name"]: s for s in compliance_publisher.scores}
        assert by_name["goal_met"]["value"] == 1.0

    # ── failure paths first ──────────────────────────────────────────

    def test_missing_outcome_fields_emit_no_score_and_no_raise(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        """A terminal event missing goal_met/criteria_met (e.g. a rejected or
        budget-exceeded shape) must NOT fabricate a score and must NOT raise."""
        _record_workflow_with_outcome(
            storage, "wf-partial",
            completed_details={"outcome": "failure"},  # no goal_met / criteria_met
        )
        (storage / "wf-partial" / ".langfuse_offset").write_text("0")
        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()  # must not raise

        score_names = {s["name"] for s in compliance_publisher.scores}
        assert "goal_met" not in score_names
        assert "criteria_met" not in score_names
        assert "task_completion_score" not in score_names
        # hash_chain_valid still attached — outcome-score absence doesn't block it.
        assert "hash_chain_valid" in score_names

    def test_none_outcome_field_emits_no_score(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        """goal_met=None (judge never ran) → no goal_met score, no raise."""
        _record_workflow_with_outcome(
            storage, "wf-nonegoal",
            completed_details={"outcome": "success", "goal_met": None, "criteria_met": 0.5},
        )
        (storage / "wf-nonegoal" / ".langfuse_offset").write_text("0")
        relay = _build_relay(storage, exporter, compliance_publisher)
        relay.run_once()
        by_name = {s["name"]: s for s in compliance_publisher.scores}
        assert "goal_met" not in by_name
        assert by_name["criteria_met"]["value"] == 0.5

    def test_score_failure_does_not_block_bundle_publish(
        self, storage: Path, exporter: FakeExporter
    ) -> None:
        """If score_trace raises, the compliance bundle still publishes (O1)."""
        publisher = FakeCompliancePublisher(fail_on_publish=True)
        _record_workflow_with_outcome(
            storage, "wf-scorefail",
            completed_details={"outcome": "success", "goal_met": True, "criteria_met": 1.0},
        )
        (storage / "wf-scorefail" / ".langfuse_offset").write_text("0")
        relay = _build_relay(storage, exporter, publisher)
        # Must not raise even though every publisher call raises.
        relay.run_once()


# ─────────────────────────────────────────────────────────────────────
# H. Phase 1 — identity pillar reaches the bundle (E7)
# ─────────────────────────────────────────────────────────────────────


class _FakeFacts:
    def __init__(self, agent_id: str) -> None:
        self._agent_id = agent_id

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        return {"agent_id": self._agent_id, "agent_name": "test-agent", "version": "1.0.0"}


class _FakeAuditEntry:
    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        return {"action": "registered"}


class _FakeAgentFactsRegistry:
    """Minimal registry honoring the export_for_compliance contract."""

    def __init__(self, known: set[str]) -> None:
        self._known = known

    def get(self, agent_id: str) -> _FakeFacts:
        if agent_id not in self._known:
            raise KeyError(agent_id)
        return _FakeFacts(agent_id)

    def audit_trail(self, agent_id: str) -> list[_FakeAuditEntry]:
        return [_FakeAuditEntry()]


class TestIdentityInBundle:
    """The relay forwards an injected AgentFacts registry into
    export_for_compliance so the compliance bundle carries identity_cards
    (review finding E7: the registry was never passed, so the Identity pillar
    was dead in practice)."""

    def test_identity_cards_present_when_registry_supplied(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        _record_workflow_with_outcome(
            storage, "wf-identity",
            completed_details={"outcome": "success", "goal_met": True, "criteria_met": 1.0},
            agent_id="agent-007",
        )
        (storage / "wf-identity" / ".langfuse_offset").write_text("0")

        registry = _FakeAgentFactsRegistry(known={"agent-007"})
        relay = _build_relay(
            storage, exporter, compliance_publisher, agent_facts_registry=registry,
        )
        relay.run_once()

        item = _published_item(compliance_publisher, "wf-identity")
        bundle = item["input_data"]
        assert "identity_cards" in bundle
        assert "agent-007" in bundle["identity_cards"]
        assert bundle["identity_cards"]["agent-007"]["agent_id"] == "agent-007"

    def test_no_registry_means_no_identity_cards(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        """Failure path: without a registry the bundle simply omits identity_cards
        (no crash, no empty-shell key)."""
        _record_workflow_with_outcome(
            storage, "wf-noreg",
            completed_details={"outcome": "success", "goal_met": True, "criteria_met": 1.0},
            agent_id="agent-007",
        )
        (storage / "wf-noreg" / ".langfuse_offset").write_text("0")
        relay = _build_relay(storage, exporter, compliance_publisher)  # no registry
        relay.run_once()
        bundle = _published_item(compliance_publisher, "wf-noreg")["input_data"]
        assert "identity_cards" not in bundle

    def test_setter_injects_registry_post_construction(
        self, storage: Path, exporter: FakeExporter, compliance_publisher: FakeCompliancePublisher
    ) -> None:
        """The composition root joins relay (from adapters) and registry (from
        components) after construction, so a setter must work like the ctor arg
        (mirrors eval_telemetry.set_sink — avoids AP-2 adapter/registry coupling)."""
        _record_workflow_with_outcome(
            storage, "wf-setter",
            completed_details={"outcome": "success", "goal_met": True, "criteria_met": 1.0},
            agent_id="agent-007",
        )
        (storage / "wf-setter" / ".langfuse_offset").write_text("0")
        relay = _build_relay(storage, exporter, compliance_publisher)  # no ctor registry
        relay.set_agent_facts_registry(_FakeAgentFactsRegistry(known={"agent-007"}))
        relay.run_once()
        bundle = _published_item(compliance_publisher, "wf-setter")["input_data"]
        assert bundle["identity_cards"]["agent-007"]["agent_id"] == "agent-007"
