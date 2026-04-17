"""L2 Contract: BlackBox export/replay with hash chain verification (Story 6.2).

Tests that export produces valid JSON with intact hash chains,
replay reconstructs chronological timeline, and tamper detection works.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent


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
