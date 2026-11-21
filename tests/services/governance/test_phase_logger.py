"""PhaseLogger: balanced phases, tamper-evident decisions, non-fatal writes."""

from __future__ import annotations

import asyncio
import json

import pytest

from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent
from services.governance.phase_logger import Decision, PhaseLogger, WorkflowPhase


def _decision(rationale: str = "because") -> Decision:
    return Decision(
        phase=WorkflowPhase.ROUTING,
        description="pick model",
        alternatives=["fast", "capable"],
        rationale=rationale,
        confidence=0.8,
    )


@pytest.mark.asyncio
async def test_should_close_phase_as_cancelled_when_task_is_cancelled(tmp_path):
    phase_logger = PhaseLogger(tmp_path)

    async def _job() -> None:
        async with phase_logger.phase("wf", WorkflowPhase.MODEL_INVOCATION, 1):
            await asyncio.sleep(10)

    task = asyncio.create_task(_job())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    events = phase_logger.export_phase_events("wf")
    assert [e["event"] for e in events] == ["phase_start", "phase_end"]
    assert events[1]["outcome"] == "cancelled"
    assert phase_logger._phase_starts == {}


def test_should_report_intact_decision_log_when_untouched(tmp_path):
    phase_logger = PhaseLogger(tmp_path)
    phase_logger.log_decision("wf", _decision("one"))
    phase_logger.log_decision("wf", _decision("two"))

    report = phase_logger.verify_decision_log("wf")

    assert report["chain_valid"] is True
    assert report["truncated"] is False
    assert report["corrupt_line_count"] == 0
    assert [r["rationale"] for r in phase_logger.export_workflow_log("wf")] == [
        "one",
        "two",
    ]


def test_should_detect_tampering_when_decision_rationale_is_edited(tmp_path):
    phase_logger = PhaseLogger(tmp_path)
    phase_logger.log_decision("wf", _decision("original"))
    phase_logger.log_decision("wf", _decision("second"))
    log_file = tmp_path / "wf" / "decisions.jsonl"
    log_file.write_text(log_file.read_text().replace("original", "rewritten"))

    assert phase_logger.verify_decision_log("wf")["chain_valid"] is False


def test_should_surface_decision_integrity_in_compliance_bundle(tmp_path):
    from datetime import UTC, datetime

    recorder = BlackBoxRecorder(tmp_path / "bb")
    recorder.record(
        TraceEvent(
            event_id="e0",
            workflow_id="wf",
            event_type=EventType.TASK_STARTED,
            timestamp=datetime.now(UTC),
            details={},
        )
    )
    phase_logger = PhaseLogger(tmp_path / "pl")
    phase_logger.log_decision("wf", _decision())

    bundle = recorder.export_for_compliance("wf", phase_logger=phase_logger)

    assert bundle["phase_decisions_integrity"]["chain_valid"] is True


def test_should_return_decision_when_log_write_fails(tmp_path, caplog):
    phase_logger = PhaseLogger(tmp_path)
    # A regular file where the workflow directory should be makes the write fail.
    (tmp_path / "wf").write_text("not a directory")

    decision = phase_logger.log_decision("wf", _decision())

    assert decision.decision_id is not None
    assert any("decisions.jsonl" in r.getMessage() for r in caplog.records)


def test_should_skip_corrupt_line_when_exporting_decisions(tmp_path):
    phase_logger = PhaseLogger(tmp_path)
    phase_logger.log_decision("wf", _decision("kept"))
    log_file = tmp_path / "wf" / "decisions.jsonl"
    log_file.write_text(log_file.read_text() + '{"torn')

    rows = phase_logger.export_workflow_log("wf")

    assert [r["rationale"] for r in rows] == ["kept"]
    assert json.loads(log_file.read_text().splitlines()[0])["integrity_hash"]
