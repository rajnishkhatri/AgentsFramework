"""Tests for ExplainabilityService -- Protocol B (contract-driven, tmp_path isolation).

Test order follows failure-paths-first per AGENTS.md TAP-4.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from services.explainability_service import ExplainabilityService, WorkflowSummary


def _write_trace(recordings_dir: Path, workflow_id: str, events: list[dict]) -> None:
    wf_dir = recordings_dir / workflow_id
    wf_dir.mkdir(parents=True, exist_ok=True)
    trace_file = wf_dir / "trace.jsonl"
    with open(trace_file, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")


def _make_event(
    event_type: str,
    workflow_id: str = "wf-test",
    timestamp: str | None = None,
    details: dict | None = None,
) -> dict:
    return {
        "event_id": f"evt-{event_type}",
        "workflow_id": workflow_id,
        "event_type": event_type,
        "timestamp": timestamp or datetime.now(UTC).isoformat(),
        "step": None,
        "details": details or {},
        "integrity_hash": "0" * 64,
    }


# --- Failure paths first ---


def test_list_workflows_empty_when_dir_missing(tmp_path: Path) -> None:
    """AC2: returns [] when the recordings directory does not exist."""
    svc = ExplainabilityService(recordings_dir=tmp_path / "nonexistent")
    result = svc.list_workflows()
    assert result == []


def test_list_workflows_skips_corrupted_jsonl(tmp_path: Path) -> None:
    """Corrupted JSONL lines are logged and skipped, not fatal."""
    recordings = tmp_path / "recordings"
    wf_dir = recordings / "wf-corrupt"
    wf_dir.mkdir(parents=True)
    trace_file = wf_dir / "trace.jsonl"
    trace_file.write_text(
        '{"event_id":"e1","workflow_id":"wf-corrupt","event_type":"task_started",'
        '"timestamp":"2026-04-26T10:00:00Z","step":null,"details":{},"integrity_hash":"0"}\n'
        "NOT VALID JSON\n"
        '{"event_id":"e2","workflow_id":"wf-corrupt","event_type":"task_completed",'
        '"timestamp":"2026-04-26T10:01:00Z","step":null,"details":{},"integrity_hash":"0"}\n'
    )

    svc = ExplainabilityService(recordings_dir=recordings)
    result = svc.list_workflows()
    assert len(result) == 1
    assert result[0].event_count == 2
    assert result[0].status == "completed"


def test_list_workflows_handles_partial_workflow(tmp_path: Path) -> None:
    """A workflow without task_completed has status='in_progress'."""
    recordings = tmp_path / "recordings"
    _write_trace(
        recordings,
        "wf-partial",
        [
            _make_event("task_started", "wf-partial", "2026-04-26T10:00:00Z"),
            _make_event("step_executed", "wf-partial", "2026-04-26T10:00:01Z"),
        ],
    )

    svc = ExplainabilityService(recordings_dir=recordings)
    result = svc.list_workflows()
    assert len(result) == 1
    assert result[0].status == "in_progress"


# --- Acceptance paths ---


def test_list_workflows_orders_newest_first(tmp_path: Path) -> None:
    """AC3: newest workflows first by started_at."""
    recordings = tmp_path / "recordings"
    _write_trace(
        recordings,
        "wf-old",
        [_make_event("task_started", "wf-old", "2026-04-25T08:00:00Z")],
    )
    _write_trace(
        recordings,
        "wf-new",
        [_make_event("task_started", "wf-new", "2026-04-26T12:00:00Z")],
    )
    _write_trace(
        recordings,
        "wf-mid",
        [_make_event("task_started", "wf-mid", "2026-04-26T09:00:00Z")],
    )

    svc = ExplainabilityService(recordings_dir=recordings)
    result = svc.list_workflows()
    assert [s.workflow_id for s in result] == ["wf-new", "wf-mid", "wf-old"]


def test_list_workflows_since_filter(tmp_path: Path) -> None:
    """AC4: since filter excludes older workflows."""
    recordings = tmp_path / "recordings"
    _write_trace(
        recordings,
        "wf-old",
        [_make_event("task_started", "wf-old", "2026-04-24T08:00:00Z")],
    )
    _write_trace(
        recordings,
        "wf-new",
        [_make_event("task_started", "wf-new", "2026-04-26T12:00:00Z")],
    )

    svc = ExplainabilityService(recordings_dir=recordings)
    cutoff = datetime(2026, 4, 25, tzinfo=UTC)
    result = svc.list_workflows(since=cutoff)
    assert len(result) == 1
    assert result[0].workflow_id == "wf-new"


def test_list_workflows_returns_workflow_summary_fields(tmp_path: Path) -> None:
    """AC1: returns WorkflowSummary with correct fields."""
    recordings = tmp_path / "recordings"
    _write_trace(
        recordings,
        "wf-full",
        [
            _make_event(
                "task_started",
                "wf-full",
                "2026-04-26T10:00:00Z",
                {"task_input": "test"},
            ),
            _make_event(
                "guardrail_checked",
                "wf-full",
                "2026-04-26T10:00:01Z",
                {"agent_id": "cli-agent", "verified": True},
            ),
            _make_event(
                "model_selected",
                "wf-full",
                "2026-04-26T10:00:02Z",
                {"model": "gpt-4o"},
            ),
            _make_event(
                "step_executed",
                "wf-full",
                "2026-04-26T10:00:03Z",
            ),
            _make_event(
                "task_completed",
                "wf-full",
                "2026-04-26T10:00:04Z",
            ),
        ],
    )

    svc = ExplainabilityService(recordings_dir=recordings)
    result = svc.list_workflows()
    assert len(result) == 1
    s = result[0]
    assert s.workflow_id == "wf-full"
    assert s.event_count == 5
    assert s.status == "completed"
    assert s.primary_agent_id == "cli-agent"
    assert s.started_at is not None
