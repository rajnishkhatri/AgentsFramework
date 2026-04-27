"""Tests for ExplainabilityService -- Protocol B (contract-driven, tmp_path isolation).

Test order follows failure-paths-first per AGENTS.md TAP-4.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from services.explainability_service import (
    ExplainabilityService,
    WorkflowNotFoundError,
    WorkflowSummary,
)
from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent
from services.governance.phase_logger import Decision, PhaseLogger, WorkflowPhase


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


def _seed_recorded_workflow(
    recordings_dir: Path,
    workflow_id: str,
    *,
    base_time: datetime,
    include_completion: bool = True,
    extra_steps: int = 1,
    model: str = "gpt-4o",
    guardrail_accepted: bool = True,
    cost_usd: float = 0.001,
    latency_ms: float = 1000.0,
    tokens_in: int = 100,
    tokens_out: int = 50,
    agent_id: str = "cli-agent",
) -> None:
    """Use the real BlackBoxRecorder so the hash chain is valid."""
    recorder = BlackBoxRecorder(recordings_dir)
    rng_seed = (workflow_id, base_time.isoformat())

    def _evt_id() -> str:
        return f"evt-{workflow_id}-{abs(hash(rng_seed + (recorder._last_hash.get(workflow_id, ''),)))}"

    t = base_time
    recorder.record(
        TraceEvent(
            event_id=_evt_id(),
            workflow_id=workflow_id,
            event_type=EventType.TASK_STARTED,
            timestamp=t,
            details={"task_input": "test", "agent_id": agent_id},
        )
    )
    t += timedelta(milliseconds=10)
    recorder.record(
        TraceEvent(
            event_id=_evt_id(),
            workflow_id=workflow_id,
            event_type=EventType.GUARDRAIL_CHECKED,
            timestamp=t,
            details={"guardrail": "prompt_injection", "accepted": guardrail_accepted},
        )
    )
    t += timedelta(milliseconds=10)
    recorder.record(
        TraceEvent(
            event_id=_evt_id(),
            workflow_id=workflow_id,
            event_type=EventType.MODEL_SELECTED,
            timestamp=t,
            details={"model": model, "reason": "test"},
        )
    )
    t += timedelta(milliseconds=10)
    for step in range(extra_steps):
        recorder.record(
            TraceEvent(
                event_id=_evt_id(),
                workflow_id=workflow_id,
                event_type=EventType.STEP_EXECUTED,
                timestamp=t,
                step=step,
                details={
                    "model": model,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "cost_usd": cost_usd,
                    "latency_ms": latency_ms,
                },
            )
        )
        t += timedelta(milliseconds=int(latency_ms))
    if include_completion:
        recorder.record(
            TraceEvent(
                event_id=_evt_id(),
                workflow_id=workflow_id,
                event_type=EventType.TASK_COMPLETED,
                timestamp=t,
                details={"status": "success"},
            )
        )


# --- S1.1.1: get_workflow_events --- failure first


def test_get_workflow_events_raises_for_unknown_workflow(tmp_path: Path) -> None:
    """AC: 404-equivalent — unknown wf_id raises WorkflowNotFoundError."""
    svc = ExplainabilityService(recordings_dir=tmp_path / "recordings")
    with pytest.raises(WorkflowNotFoundError) as exc_info:
        svc.get_workflow_events("wf-does-not-exist")
    assert exc_info.value.workflow_id == "wf-does-not-exist"


def test_get_workflow_events_returns_chain_invalid_when_tampered(tmp_path: Path) -> None:
    """Failure-first: tamper one byte then assert hash_chain_valid is False.

    Tampered fixture in -> hash_chain_valid = False out.  Never re-implement SHA256.
    """
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    _seed_recorded_workflow(recordings, "wf-tampered", base_time=base)

    trace_file = recordings / "wf-tampered" / "trace.jsonl"
    lines = trace_file.read_text().strip().split("\n")
    tampered = json.loads(lines[1])
    tampered["details"]["TAMPERED"] = True
    lines[1] = json.dumps(tampered)
    trace_file.write_text("\n".join(lines) + "\n")

    svc = ExplainabilityService(recordings_dir=recordings)
    result = svc.get_workflow_events("wf-tampered")
    assert result.hash_chain_valid is False
    assert result.event_count == len(lines)


def test_get_workflow_events_happy_path(tmp_path: Path) -> None:
    """Acceptance: untampered workflow has hash_chain_valid=True and full events."""
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    _seed_recorded_workflow(recordings, "wf-happy", base_time=base, extra_steps=2)

    svc = ExplainabilityService(recordings_dir=recordings)
    result = svc.get_workflow_events("wf-happy")

    assert result.workflow_id == "wf-happy"
    assert result.hash_chain_valid is True
    # task_started + guardrail_checked + model_selected + 2x step_executed + task_completed
    assert result.event_count == 6
    assert result.events[0].event_type == "task_started"
    assert result.events[-1].event_type == "task_completed"
    for event in result.events:
        assert event.workflow_id == "wf-happy"
        assert event.event_id
        assert event.integrity_hash


# --- S1.2.1: get_workflow_decisions --- failure first


def test_get_workflow_decisions_returns_empty_when_no_log(tmp_path: Path) -> None:
    """Failure-first AC: empty workflow returns [], NOT 404."""
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        phase_logs_dir=tmp_path / "phase_logs",
    )
    assert svc.get_workflow_decisions("wf-no-decisions") == []


def test_get_workflow_decisions_returns_empty_when_phase_logs_dir_unset(
    tmp_path: Path,
) -> None:
    """Failure-first: service constructed without phase_logs_dir returns []."""
    svc = ExplainabilityService(recordings_dir=tmp_path / "recordings")
    assert svc.get_workflow_decisions("any-id") == []


def test_get_workflow_decisions_skips_corrupted_lines(tmp_path: Path) -> None:
    """Failure-first: corrupted JSONL lines are logged and skipped, not fatal."""
    phase_logs = tmp_path / "phase_logs"
    wf_dir = phase_logs / "wf-corrupt"
    wf_dir.mkdir(parents=True)
    log_file = wf_dir / "decisions.jsonl"
    log_file.write_text(
        '{"timestamp":"2026-04-26T10:00:00+00:00","workflow_id":"wf-corrupt",'
        '"phase":"routing","description":"first","alternatives":["a","b"],'
        '"rationale":"because","confidence":0.9}\n'
        "NOT JSON\n"
        '{"timestamp":"2026-04-26T10:00:01+00:00","workflow_id":"wf-corrupt",'
        '"phase":"evaluation","description":"second","alternatives":[],'
        '"rationale":"r","confidence":1.0}\n'
    )

    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        phase_logs_dir=phase_logs,
    )
    result = svc.get_workflow_decisions("wf-corrupt")
    assert len(result) == 2
    assert result[0].description == "first"
    assert result[1].description == "second"


def test_get_workflow_decisions_orders_chronologically(tmp_path: Path) -> None:
    """Acceptance AC: decisions are ordered by timestamp ascending."""
    phase_logs = tmp_path / "phase_logs"
    pl = PhaseLogger(phase_logs)
    pl.log_decision(
        "wf-ord",
        Decision(
            phase=WorkflowPhase.ROUTING,
            description="first",
            alternatives=[],
            rationale="r",
            confidence=0.8,
        ),
    )
    pl.log_decision(
        "wf-ord",
        Decision(
            phase=WorkflowPhase.EVALUATION,
            description="second",
            alternatives=[],
            rationale="r",
            confidence=0.9,
        ),
    )

    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        phase_logs_dir=phase_logs,
    )
    result = svc.get_workflow_decisions("wf-ord")
    assert [d.description for d in result] == ["first", "second"]
    assert result[0].timestamp is not None
    assert result[1].timestamp is not None
    assert result[0].timestamp <= result[1].timestamp


def test_get_workflow_decisions_returns_decision_record_fields(tmp_path: Path) -> None:
    """Acceptance: every required field is populated."""
    phase_logs = tmp_path / "phase_logs"
    pl = PhaseLogger(phase_logs)
    pl.log_decision(
        "wf-fields",
        Decision(
            phase=WorkflowPhase.ROUTING,
            description="picked gpt-4o",
            alternatives=["gpt-4o-mini", "claude-3-opus"],
            rationale="capable-for-planning",
            confidence=0.85,
        ),
    )

    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        phase_logs_dir=phase_logs,
    )
    result = svc.get_workflow_decisions("wf-fields")
    assert len(result) == 1
    d = result[0]
    assert d.workflow_id == "wf-fields"
    assert d.phase == "routing"
    assert d.description == "picked gpt-4o"
    assert d.alternatives == ["gpt-4o-mini", "claude-3-opus"]
    assert d.rationale == "capable-for-planning"
    assert d.confidence == 0.85
    assert d.timestamp is not None


# --- S1.3.1: get_dashboard_metrics --- failure first


def test_get_dashboard_metrics_zero_workflows_returns_all_zero(tmp_path: Path) -> None:
    """Failure-first AC: zero workflows in range returns all-zero, NOT 404."""
    svc = ExplainabilityService(recordings_dir=tmp_path / "recordings")
    metrics = svc.get_dashboard_metrics()
    assert metrics.total_runs == 0
    assert metrics.p50_latency_ms == 0.0
    assert metrics.p95_latency_ms == 0.0
    assert metrics.total_cost_usd == 0.0
    assert metrics.guardrail_pass_rate == 0.0
    assert metrics.hash_chain_valid_count == 0
    assert metrics.hash_chain_invalid_count == 0
    assert metrics.time_series_cost == []
    assert metrics.time_series_latency == []
    assert metrics.time_series_tokens == []
    assert metrics.model_distribution == {}


def test_get_dashboard_metrics_excludes_workflows_outside_range(tmp_path: Path) -> None:
    """Failure-first: since/until exclude out-of-range workflows."""
    recordings = tmp_path / "recordings"
    _seed_recorded_workflow(
        recordings, "wf-old", base_time=datetime(2026, 1, 1, tzinfo=UTC)
    )
    _seed_recorded_workflow(
        recordings, "wf-new", base_time=datetime(2026, 4, 26, tzinfo=UTC)
    )

    svc = ExplainabilityService(recordings_dir=recordings)
    metrics = svc.get_dashboard_metrics(
        since=datetime(2026, 4, 1, tzinfo=UTC),
        until=datetime(2026, 5, 1, tzinfo=UTC),
    )
    assert metrics.total_runs == 1


def test_get_dashboard_metrics_three_workflow_aggregates(tmp_path: Path) -> None:
    """Acceptance: golden fixture with 3 workflows produces expected aggregates."""
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    _seed_recorded_workflow(
        recordings,
        "wf-a",
        base_time=base,
        model="gpt-4o",
        latency_ms=1000.0,
        cost_usd=0.001,
        tokens_in=100,
        tokens_out=50,
    )
    _seed_recorded_workflow(
        recordings,
        "wf-b",
        base_time=base + timedelta(hours=1),
        model="gpt-4o",
        latency_ms=2000.0,
        cost_usd=0.002,
        tokens_in=200,
        tokens_out=100,
    )
    _seed_recorded_workflow(
        recordings,
        "wf-c",
        base_time=base + timedelta(hours=2),
        model="claude-3-opus",
        latency_ms=3000.0,
        cost_usd=0.003,
        tokens_in=300,
        tokens_out=150,
    )

    svc = ExplainabilityService(recordings_dir=recordings)
    metrics = svc.get_dashboard_metrics()
    assert metrics.total_runs == 3
    assert metrics.hash_chain_valid_count == 3
    assert metrics.hash_chain_invalid_count == 0
    assert metrics.guardrail_pass_rate == 1.0
    assert metrics.total_cost_usd == pytest.approx(0.006)
    assert metrics.p50_latency_ms == pytest.approx(2000.0)
    assert metrics.p95_latency_ms == pytest.approx(2900.0)
    assert metrics.model_distribution == {"gpt-4o": 2, "claude-3-opus": 1}
    assert len(metrics.time_series_cost) == 3
    assert len(metrics.time_series_latency) == 3
    assert len(metrics.time_series_tokens) == 3


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
