"""L2 Contract: BlackBox export/replay with hash chain verification (Story 6.2).

Tests that export produces valid JSON with intact hash chains,
replay reconstructs chronological timeline, and tamper detection works.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

from services.governance.black_box import (
    BUNDLE_SCHEMA_VERSION,
    PHASE_LOG_SCHEMA_VERSION,
    BlackBoxRecorder,
    EventType,
    TraceEvent,
)
from services.governance.phase_logger import Decision, PhaseLogger, WorkflowPhase


def _make_event(workflow_id: str, event_type: EventType, step: int = 0) -> TraceEvent:
    return TraceEvent(
        event_id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        event_type=event_type,
        timestamp=datetime.now(UTC),
        step=step,
        details={"test": True, "step": step},
    )


class TestBlackBoxExport:
    def test_export_produces_valid_structure(self, tmp_path):
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        wf = "wf-export-test"

        for i, et in enumerate([
            EventType.TASK_STARTED,
            EventType.MODEL_SELECTED,
            EventType.STEP_EXECUTED,
            EventType.TOOL_CALLED,
            EventType.TASK_COMPLETED,
        ]):
            bb.record(_make_event(wf, et, step=i))

        export = bb.export(wf)
        assert export["workflow_id"] == wf
        assert export["event_count"] == 5
        assert len(export["events"]) == 5
        assert export["hash_chain_valid"] is True

    def test_export_hash_chain_intact(self, tmp_path):
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        wf = "wf-chain-test"

        for i in range(5):
            bb.record(_make_event(wf, EventType.STEP_EXECUTED, step=i))

        export = bb.export(wf)
        assert export["hash_chain_valid"] is True

        hashes = [e["integrity_hash"] for e in export["events"]]
        assert len(set(hashes)) == 5, "Each event should have a unique hash"

    def test_export_detects_tampered_hash_chain(self, tmp_path):
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        wf = "wf-tamper-test"

        for i in range(3):
            bb.record(_make_event(wf, EventType.STEP_EXECUTED, step=i))

        trace_file = tmp_path / "bb" / wf / "trace.jsonl"
        lines = trace_file.read_text().strip().split("\n")
        events = [json.loads(line) for line in lines]
        events[1]["details"]["tampered"] = True
        trace_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")

        export = bb.export(wf)
        assert export["hash_chain_valid"] is False

    def test_export_unknown_workflow_raises_error(self, tmp_path):
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")

        with pytest.raises(KeyError, match="No trace found"):
            bb.export("nonexistent-workflow")


class TestBundleSchemaVersion:
    """G4: every export bundle self-identifies with a stable schema version so
    the coexisting ``task_completed`` shapes are no longer ambiguous."""

    def test_export_stamps_bundle_schema_version(self, tmp_path):
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        wf = "wf-schema-version"
        bb.record(_make_event(wf, EventType.TASK_STARTED, step=0))
        bb.record(_make_event(wf, EventType.TASK_COMPLETED, step=1))

        export = bb.export(wf)
        assert "bundle_schema_version" in export
        assert export["bundle_schema_version"] == BUNDLE_SCHEMA_VERSION

    def test_bundle_schema_version_is_stable(self):
        # Locks the wire contract: a silent bump would break consumers that
        # branch on this field, so the constant must change deliberately.
        assert BUNDLE_SCHEMA_VERSION == "2"

    def test_phase_log_schema_version_is_stable(self):
        assert PHASE_LOG_SCHEMA_VERSION == "1"

    def test_export_for_compliance_inherits_schema_version(self, tmp_path):
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        wf = "wf-compliance-schema-version"
        bb.record(_make_event(wf, EventType.TASK_STARTED, step=0))
        bb.record(_make_event(wf, EventType.TASK_COMPLETED, step=1))

        bundle = bb.export_for_compliance(wf)
        assert bundle["bundle_schema_version"] == BUNDLE_SCHEMA_VERSION
        assert bundle["bundle_type"] == "compliance_audit"

    def test_export_for_compliance_stamps_phase_log_schema_version(self, tmp_path):
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        wf = "wf-phase-log-schema"
        bb.record(_make_event(wf, EventType.TASK_STARTED, step=0))
        bb.record(_make_event(wf, EventType.TASK_COMPLETED, step=1))

        bundle = bb.export_for_compliance(wf)
        assert bundle["phase_log_schema_version"] == PHASE_LOG_SCHEMA_VERSION
        assert bundle["bundle_schema_version"] == BUNDLE_SCHEMA_VERSION

    def test_phase_events_separate_from_phase_decisions(self, tmp_path):
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        phase_logs = tmp_path / "phase_logs"
        wf = "wf-phase-split"
        bb.record(_make_event(wf, EventType.TASK_STARTED, step=0))
        bb.record(_make_event(wf, EventType.TASK_COMPLETED, step=1))

        pl = PhaseLogger(phase_logs)
        pl.log_decision(
            wf,
            Decision(
                phase=WorkflowPhase.ROUTING,
                description="picked model",
                alternatives=[],
                rationale="test",
                confidence=1.0,
            ),
        )
        phases_file = phase_logs / wf / "phases.jsonl"
        phases_file.parent.mkdir(parents=True, exist_ok=True)
        phases_file.write_text(
            json.dumps(
                {
                    "event": "phase_end",
                    "workflow_id": wf,
                    "step_count": 0,
                    "phase": "routing",
                    "outcome": "done",
                    "duration_ms": 1,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            + "\n"
        )

        bundle = bb.export_for_compliance(wf, phase_logger=pl)
        assert bundle["phase_log_schema_version"] == "1"
        assert len(bundle["phase_decisions"]) == 1
        assert bundle["phase_decisions"][0]["description"] == "picked model"
        assert len(bundle["phase_events"]) == 1
        assert bundle["phase_events"][0]["event"] == "phase_end"
        assert "description" not in bundle["phase_events"][0]


def _make_terminal_event(workflow_id: str, details: dict, step: int = 1) -> TraceEvent:
    return TraceEvent(
        event_id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        event_type=EventType.TASK_COMPLETED,
        timestamp=datetime.now(UTC),
        step=step,
        details=details,
    )


class TestComplianceSummaryBlock:
    """G6 residual: ``export_for_compliance`` lifts the terminal outcome signals
    into a flat top-level ``summary`` block so dashboards can key off the result
    without walking ``events[]`` or knowing which task_completed shape applies.

    Failure paths first (TDD prompt §4 + TAP-4): a trace that never completes,
    and the rejected/budget shapes that lack the goal fields, are proven before
    the happy rich-path lift.
    """

    def test_summary_present_when_no_task_completed(self, tmp_path):
        # Failure path: an aborted/incomplete trace still gets a shape-stable
        # summary — its absence of completion is itself the signal.
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        wf = "wf-summary-no-terminal"
        bb.record(_make_event(wf, EventType.TASK_STARTED, step=0))
        bb.record(_make_event(wf, EventType.STEP_EXECUTED, step=1))

        bundle = bb.export_for_compliance(wf)
        summary = bundle["summary"]
        assert summary["task_completed_present"] is False
        assert summary["outcome"] is None
        assert summary["goal_met"] is None
        assert summary["criteria_met"] is None
        assert summary["termination_reason"] is None
        assert summary["reason"] is None

    def test_summary_for_rejected_path_lacks_goal_fields(self, tmp_path):
        # Failure path (G7): a guardrail/agent-facts rejection carries an
        # ``outcome`` + ``reason`` but no goal_met/criteria_met. The summary must
        # surface what exists and leave the rest as None rather than omitting keys.
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        wf = "wf-summary-rejected"
        bb.record(_make_event(wf, EventType.TASK_STARTED, step=0))
        bb.record(_make_terminal_event(wf, {
            "outcome": "rejected",
            "reason": "agent_facts_verification_failed",
            "step_count": 0,
            "total_cost_usd": 0.0,
        }))

        summary = bb.export_for_compliance(wf)["summary"]
        assert summary["task_completed_present"] is True
        assert summary["outcome"] == "rejected"
        assert summary["reason"] == "agent_facts_verification_failed"
        assert summary["goal_met"] is None
        assert summary["criteria_met"] is None
        assert summary["termination_reason"] is None

    def test_summary_for_budget_exceeded_path(self, tmp_path):
        # Failure path: budget-exceeded terminal shape (no goal fields, no reason).
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        wf = "wf-summary-budget"
        bb.record(_make_terminal_event(wf, {
            "outcome": "budget_exceeded",
            "step_count": 3,
            "total_cost_usd": 5.0,
            "budget_limit": 5.0,
        }))

        summary = bb.export_for_compliance(wf)["summary"]
        assert summary["outcome"] == "budget_exceeded"
        assert summary["goal_met"] is None
        assert summary["reason"] is None

    def test_summary_lifts_goal_fields_from_rich_task_completed(self, tmp_path):
        # Happy path: the rich terminal event's goal signals are lifted verbatim.
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        wf = "wf-summary-rich"
        bb.record(_make_event(wf, EventType.TASK_STARTED, step=0))
        bb.record(_make_terminal_event(wf, {
            "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
            "outcome": "partial",
            "goal_met": False,
            "criteria_met": 0.667,
            "termination_reason": "no_progress",
            "unmet_conditions": ["coverage"],
        }, step=4))

        summary = bb.export_for_compliance(wf)["summary"]
        assert summary["task_completed_present"] is True
        assert summary["outcome"] == "partial"
        assert summary["goal_met"] is False
        assert summary["criteria_met"] == 0.667
        assert summary["termination_reason"] == "no_progress"
        assert summary["reason"] is None

    def test_summary_uses_last_task_completed(self, tmp_path):
        # Edge: if more than one terminal event exists, the chronologically last
        # one wins so the summary reflects the true final state.
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        wf = "wf-summary-last-wins"
        bb.record(_make_terminal_event(wf, {"outcome": "partial", "goal_met": False}, step=1))
        bb.record(_make_terminal_event(wf, {"outcome": "success", "goal_met": True}, step=2))

        summary = bb.export_for_compliance(wf)["summary"]
        assert summary["outcome"] == "success"
        assert summary["goal_met"] is True

    def test_base_export_has_no_summary_block(self, tmp_path):
        # Contract boundary: the summary is a compliance-bundle concern only;
        # the base export() wire shape stays unchanged (its tests stay green).
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        wf = "wf-summary-base-export"
        bb.record(_make_event(wf, EventType.TASK_STARTED, step=0))
        bb.record(_make_terminal_event(wf, {"outcome": "success", "goal_met": True}))

        assert "summary" not in bb.export(wf)
        assert "summary" in bb.export_for_compliance(wf)


class TestBlackBoxReplay:
    def test_replay_returns_events_in_chronological_order(self, tmp_path):
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        wf = "wf-replay-test"

        events_in = [
            EventType.TASK_STARTED,
            EventType.MODEL_SELECTED,
            EventType.STEP_EXECUTED,
            EventType.TOOL_CALLED,
            EventType.TASK_COMPLETED,
        ]
        for i, et in enumerate(events_in):
            bb.record(_make_event(wf, et, step=i))

        replayed = bb.replay(wf)

        assert len(replayed) == 5
        for i in range(len(replayed) - 1):
            assert replayed[i].timestamp <= replayed[i + 1].timestamp

    def test_replay_unknown_workflow_raises_error(self, tmp_path):
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")

        with pytest.raises(KeyError, match="No trace found"):
            bb.replay("nonexistent-workflow")

    def test_replay_preserves_event_correlation(self, tmp_path):
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        wf = "wf-correlation"

        bb.record(_make_event(wf, EventType.TASK_STARTED, step=0))
        bb.record(_make_event(wf, EventType.STEP_EXECUTED, step=1))

        replayed = bb.replay(wf)
        assert all(e.workflow_id == wf for e in replayed)
        assert replayed[0].event_type == EventType.TASK_STARTED
        assert replayed[1].event_type == EventType.STEP_EXECUTED
