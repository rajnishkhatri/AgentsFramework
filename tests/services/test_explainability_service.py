"""Tests for ExplainabilityService -- Protocol B (contract-driven, tmp_path isolation).

Test order follows failure-paths-first per AGENTS.md TAP-4.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from services.explainability_service import (
    AgentNotFoundError,
    ExplainabilityService,
    WorkflowNotFoundError,
)
from services.governance.agent_facts_registry import AgentFactsRegistry
from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent
from services.governance.phase_logger import Decision, PhaseLogger, WorkflowPhase
from trust.enums import IdentityStatus
from trust.models import AgentFacts, Capability, Policy


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
    _evt_counter = iter(range(10_000))

    def _evt_id() -> str:
        return f"evt-{workflow_id}-{abs(hash(rng_seed + (next(_evt_counter),)))}"

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


def test_get_workflow_events_returns_chain_invalid_when_tampered(
    tmp_path: Path,
) -> None:
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


# --- S2.1.1: get_guardrail_summary --- failure first


def test_get_guardrail_summary_zero_events_returns_all_zero(tmp_path: Path) -> None:
    """Failure-first AC: zero guardrail events in range returns all-zero with empty per_validator.

    Empty range NEVER 404 -- the dashboard always renders structurally even on a
    cold install.
    """
    svc = ExplainabilityService(recordings_dir=tmp_path / "recordings")
    summary = svc.get_guardrail_summary()
    assert summary.total_checks == 0
    assert summary.pass_count == 0
    assert summary.fail_count == 0
    assert summary.pass_rate == 0.0
    assert summary.fail_action_distribution == {}
    assert summary.per_validator == []
    assert summary.recent_failures == []
    assert summary.trend_pass_rate_delta == 0.0


def test_get_guardrail_summary_skips_unreadable_workflow(tmp_path: Path) -> None:
    """Failure-first: corrupted JSONL is skipped, not fatal."""
    recordings = tmp_path / "recordings"
    wf_dir = recordings / "wf-broken"
    wf_dir.mkdir(parents=True)
    (wf_dir / "trace.jsonl").write_text("NOT VALID JSON\n")

    svc = ExplainabilityService(recordings_dir=recordings)
    summary = svc.get_guardrail_summary()
    assert summary.total_checks == 0
    assert summary.per_validator == []


def test_get_guardrail_summary_excludes_workflows_outside_range(tmp_path: Path) -> None:
    """Failure-first: since/until window excludes out-of-range workflows."""
    recordings = tmp_path / "recordings"
    _seed_recorded_workflow(
        recordings, "wf-old", base_time=datetime(2026, 1, 1, tzinfo=UTC)
    )
    _seed_recorded_workflow(
        recordings, "wf-new", base_time=datetime(2026, 4, 26, tzinfo=UTC)
    )

    svc = ExplainabilityService(recordings_dir=recordings)
    summary = svc.get_guardrail_summary(
        since=datetime(2026, 4, 1, tzinfo=UTC),
        until=datetime(2026, 5, 1, tzinfo=UTC),
    )
    assert summary.total_checks == 1
    assert summary.per_validator[0].name == "prompt_injection"


# --- S2.1.1 acceptance ---


def _seed_guardrail_event(
    recordings: Path,
    workflow_id: str,
    *,
    base_time: datetime,
    validator: str,
    accepted: bool,
    fail_action: str | None = None,
) -> None:
    """Seed one workflow that consists of a single guardrail_checked event.

    Uses the real recorder so the hash chain is valid, then the aggregator can
    assert it against `hash_chain_valid_count`.
    """
    recorder = BlackBoxRecorder(recordings)
    details: dict = {"guardrail": validator, "accepted": accepted}
    if fail_action is not None:
        details["fail_action"] = fail_action
    recorder.record(
        TraceEvent(
            event_id=f"evt-start-{workflow_id}",
            workflow_id=workflow_id,
            event_type=EventType.TASK_STARTED,
            timestamp=base_time,
            details={"agent_id": "cli-agent"},
        )
    )
    recorder.record(
        TraceEvent(
            event_id=f"evt-guard-{workflow_id}",
            workflow_id=workflow_id,
            event_type=EventType.GUARDRAIL_CHECKED,
            timestamp=base_time + timedelta(milliseconds=10),
            details=details,
        )
    )


def test_get_guardrail_summary_pass_plus_fail_equals_total(tmp_path: Path) -> None:
    """Property test (Hypothesis-spirit): pass_rate + fail_rate == 1 for any non-empty input.

    We don't pull in Hypothesis here (the existing suite has no plugin); a
    table-driven enumeration of mixed pass/fail mixes is equivalent.
    """
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, tzinfo=UTC)
    for i, accepted in enumerate([True, True, False, True, False, False, True]):
        _seed_guardrail_event(
            recordings,
            f"wf-{i}",
            base_time=base + timedelta(minutes=i),
            validator="prompt_injection",
            accepted=accepted,
            fail_action=None if accepted else "reject",
        )

    svc = ExplainabilityService(recordings_dir=recordings)
    summary = svc.get_guardrail_summary()
    assert summary.total_checks == 7
    assert summary.pass_count == 4
    assert summary.fail_count == 3
    assert summary.pass_rate + (
        summary.fail_count / summary.total_checks
    ) == pytest.approx(1.0)


def test_get_guardrail_summary_per_validator_breakdown(tmp_path: Path) -> None:
    """Acceptance: per-validator stats roll up correctly across multiple validators."""
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, tzinfo=UTC)
    _seed_guardrail_event(
        recordings,
        "wf-a",
        base_time=base,
        validator="prompt_injection",
        accepted=True,
    )
    _seed_guardrail_event(
        recordings,
        "wf-b",
        base_time=base + timedelta(minutes=1),
        validator="prompt_injection",
        accepted=False,
        fail_action="reject",
    )
    _seed_guardrail_event(
        recordings,
        "wf-c",
        base_time=base + timedelta(minutes=2),
        validator="output_pii_scan",
        accepted=False,
        fail_action="redact",
    )

    svc = ExplainabilityService(recordings_dir=recordings)
    summary = svc.get_guardrail_summary()
    by_name = {v.name: v for v in summary.per_validator}

    assert set(by_name) == {"prompt_injection", "output_pii_scan"}
    assert by_name["prompt_injection"].total_checks == 2
    assert by_name["prompt_injection"].pass_count == 1
    assert by_name["prompt_injection"].fail_count == 1
    assert by_name["prompt_injection"].pass_rate == 0.5

    assert by_name["output_pii_scan"].total_checks == 1
    assert by_name["output_pii_scan"].pass_count == 0
    assert by_name["output_pii_scan"].fail_count == 1
    assert by_name["output_pii_scan"].pass_rate == 0.0

    assert summary.fail_action_distribution == {"reject": 1, "redact": 1}
    failure_validators = {f.validator for f in summary.recent_failures}
    assert failure_validators == {"prompt_injection", "output_pii_scan"}


def test_get_guardrail_summary_trend_delta_compares_prior_window(
    tmp_path: Path,
) -> None:
    """Acceptance: trend is a single number (delta vs prior period) per S2.1.1 AC."""
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, 12, 0, tzinfo=UTC)
    # Prior window [base - 1h, base): 2 checks, 1 pass -> pass_rate 0.5
    for i, accepted in enumerate([True, False]):
        _seed_guardrail_event(
            recordings,
            f"wf-prior-{i}",
            base_time=base - timedelta(minutes=30) + timedelta(minutes=i),
            validator="prompt_injection",
            accepted=accepted,
            fail_action=None if accepted else "reject",
        )
    # Current window [base, base + 1h): 2 checks, 2 passes -> pass_rate 1.0
    for i in range(2):
        _seed_guardrail_event(
            recordings,
            f"wf-curr-{i}",
            base_time=base + timedelta(minutes=i),
            validator="prompt_injection",
            accepted=True,
        )

    svc = ExplainabilityService(recordings_dir=recordings)
    current = svc.get_guardrail_summary(since=base, until=base + timedelta(hours=1))
    assert current.pass_rate == 1.0
    assert current.trend_pass_rate_delta == pytest.approx(0.5)


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


# --- S2.2.1: Agent Registry views --- failure first


def _seed_agent(
    registry: AgentFactsRegistry,
    *,
    agent_id: str,
    agent_name: str = "Test Agent",
    owner: str = "owner",
    version: str = "1.0",
    capabilities: list[Capability] | None = None,
    policies: list[Policy] | None = None,
) -> AgentFacts:
    facts = AgentFacts(
        agent_id=agent_id,
        agent_name=agent_name,
        owner=owner,
        version=version,
        capabilities=capabilities or [],
        policies=policies or [],
    )
    return registry.register(facts, registered_by="test")


def _make_registry(tmp_path: Path) -> AgentFactsRegistry:
    return AgentFactsRegistry(
        storage_dir=tmp_path / "agent_facts",
        secret="test-secret-do-not-use-in-prod",
    )


def test_list_agents_returns_empty_when_no_registry(tmp_path: Path) -> None:
    """Failure-first: a service constructed with no registry returns []."""
    svc = ExplainabilityService(recordings_dir=tmp_path / "recordings")
    assert svc.list_agents() == []


def test_list_agents_returns_empty_when_registry_dir_missing(tmp_path: Path) -> None:
    """Failure-first: empty registry returns [] (not 404)."""
    registry = _make_registry(tmp_path)
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        agent_facts_registry=registry,
    )
    assert svc.list_agents() == []


def test_get_agent_card_raises_for_unknown_agent(tmp_path: Path) -> None:
    """Failure-first: unknown agent raises AgentNotFoundError (404-equivalent)."""
    registry = _make_registry(tmp_path)
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        agent_facts_registry=registry,
    )
    with pytest.raises(AgentNotFoundError) as exc_info:
        svc.get_agent_card("does-not-exist")
    assert exc_info.value.agent_id == "does-not-exist"


def test_get_agent_audit_returns_empty_when_no_audit(tmp_path: Path) -> None:
    """Failure-first: an agent that exists but has no audit trail returns []."""
    registry = _make_registry(tmp_path)
    _seed_agent(registry, agent_id="empty-audit")
    # Manually delete the audit file to simulate the empty case
    audit_file = tmp_path / "agent_facts" / "empty-audit_audit.jsonl"
    audit_file.unlink()
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        agent_facts_registry=registry,
    )
    assert svc.get_agent_audit("empty-audit") == []


def test_get_agent_audit_raises_for_unknown_agent(tmp_path: Path) -> None:
    """Failure-first: AgentNotFoundError when the agent itself is missing."""
    registry = _make_registry(tmp_path)
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        agent_facts_registry=registry,
    )
    with pytest.raises(AgentNotFoundError):
        svc.get_agent_audit("nope")


# --- S2.2.1 acceptance ---


def test_list_agents_returns_seeded_cards(tmp_path: Path) -> None:
    """Acceptance: every registered agent appears in list_agents."""
    registry = _make_registry(tmp_path)
    _seed_agent(registry, agent_id="cli-agent", agent_name="CLI Agent")
    _seed_agent(registry, agent_id="dev-agent", agent_name="Dev Agent")
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        agent_facts_registry=registry,
    )
    cards = svc.list_agents()
    ids = {c.agent_id for c in cards}
    assert ids == {"cli-agent", "dev-agent"}


def test_get_agent_card_contains_no_setter_fields(tmp_path: Path) -> None:
    """F-R6: AgentCard must expose `signature_verified` (boolean) but no setter
    fields like `signature_hash`. The card is a strict subset of `AgentFacts`.
    """
    registry = _make_registry(tmp_path)
    _seed_agent(
        registry,
        agent_id="cli-agent",
        capabilities=[Capability(name="shell.run")],
        policies=[Policy(name="never-run-rm-rf")],
    )
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        agent_facts_registry=registry,
    )
    card = svc.get_agent_card("cli-agent")
    assert card.agent_id == "cli-agent"
    assert card.signature_verified is True
    from services.explainability_service import AgentCard

    # Field set must not include signature_hash, ensuring no setter leak.
    assert "signature_hash" not in AgentCard.model_fields
    # Capabilities and policies pass through.
    assert [c.name for c in card.capabilities] == ["shell.run"]
    assert [p.name for p in card.policies] == ["never-run-rm-rf"]


def test_get_agent_card_signature_verified_false_when_suspended(tmp_path: Path) -> None:
    """A suspended agent must report signature_verified=False because the
    registry's `verify()` short-circuits on non-ACTIVE status.
    """
    registry = _make_registry(tmp_path)
    _seed_agent(registry, agent_id="suspended-agent")
    registry.suspend("suspended-agent", reason="for test", suspended_by="tester")
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        agent_facts_registry=registry,
    )
    card = svc.get_agent_card("suspended-agent")
    assert card.status == IdentityStatus.SUSPENDED.value
    assert card.signature_verified is False


def test_get_agent_audit_returns_chronological_register_then_suspend(
    tmp_path: Path,
) -> None:
    """Acceptance: register and suspend produce two audit entries."""
    registry = _make_registry(tmp_path)
    _seed_agent(registry, agent_id="cli-agent")
    registry.suspend("cli-agent", reason="rotate", suspended_by="ops")
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        agent_facts_registry=registry,
    )
    audit = svc.get_agent_audit("cli-agent")
    assert [a.action for a in audit] == ["register", "suspend"]
    assert audit[1].details == {"reason": "rotate"}


# --- S3.1.1: get_workflow_integrity --- failure first


def test_get_workflow_integrity_raises_for_unknown_workflow(tmp_path: Path) -> None:
    """Failure-first: unknown workflow raises WorkflowNotFoundError (404-equivalent)."""
    from services.explainability_service import IntegrityReport  # noqa: F401

    svc = ExplainabilityService(recordings_dir=tmp_path / "recordings")
    with pytest.raises(WorkflowNotFoundError) as exc_info:
        svc.get_workflow_integrity("wf-missing")
    assert exc_info.value.workflow_id == "wf-missing"


def test_get_workflow_integrity_reports_break_location_when_tampered(
    tmp_path: Path,
) -> None:
    """Failure-first: tampered fixture (mutate one byte) returns chain_valid=False
    with non-null broken_at_event_id and non-null expected/actual hashes.

    Tampered fixture in -> chain_valid=False with concrete break location out.
    Never re-implement SHA256.
    """
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    _seed_recorded_workflow(recordings, "wf-tamper", base_time=base, extra_steps=2)

    trace_file = recordings / "wf-tamper" / "trace.jsonl"
    lines = trace_file.read_text().strip().split("\n")
    target_idx = 2
    tampered = json.loads(lines[target_idx])
    tampered_event_id = tampered["event_id"]
    tampered["details"]["TAMPERED"] = True
    lines[target_idx] = json.dumps(tampered)
    trace_file.write_text("\n".join(lines) + "\n")

    svc = ExplainabilityService(recordings_dir=recordings)
    report = svc.get_workflow_integrity("wf-tamper")

    assert report.workflow_id == "wf-tamper"
    assert report.chain_valid is False
    assert report.broken_at_event_id == tampered_event_id
    assert report.expected_hash is not None
    assert report.actual_hash is not None
    assert report.expected_hash != report.actual_hash


# --- S3.1.1 acceptance ---


def test_get_workflow_integrity_returns_chain_valid_for_untampered(
    tmp_path: Path,
) -> None:
    """Property test (Hypothesis-spirit): a valid chain ALWAYS returns
    chain_valid=True with all break-location fields null.

    Table-driven enumeration over a few workflow shapes is equivalent to a
    Hypothesis property test for this branch.
    """
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    for i, steps in enumerate([1, 2, 4]):
        _seed_recorded_workflow(
            recordings,
            f"wf-clean-{i}",
            base_time=base + timedelta(hours=i),
            extra_steps=steps,
        )

    svc = ExplainabilityService(recordings_dir=recordings)
    for i in range(3):
        report = svc.get_workflow_integrity(f"wf-clean-{i}")
        assert report.chain_valid is True, f"wf-clean-{i} should be valid"
        assert report.broken_at_event_id is None
        assert report.expected_hash is None
        assert report.actual_hash is None


# --- S3.1.2: get_compliance_bundle --- failure first


def _seed_correlated_workflow(
    recordings: Path,
    workflow_id: str,
    *,
    base_time: datetime,
    include_user_id: bool = True,
    include_task_id: bool = True,
    include_trace_id: bool = True,
    include_agent_id: bool = True,
) -> None:
    """Seed a workflow whose `task_started.details` includes the four correlation
    keys. Toggling a flag deletes the corresponding key — used by the
    `missing_keys` failure-first tests.
    """
    recorder = BlackBoxRecorder(recordings)
    details: dict = {}
    if include_user_id:
        details["user_id"] = "user-42"
    if include_task_id:
        details["task_id"] = "task-7"
    if include_trace_id:
        details["trace_id"] = "trace-abc"
    if include_agent_id:
        details["agent_id"] = "cli-agent"
    recorder.record(
        TraceEvent(
            event_id=f"evt-start-{workflow_id}",
            workflow_id=workflow_id,
            event_type=EventType.TASK_STARTED,
            timestamp=base_time,
            details=details,
        )
    )
    recorder.record(
        TraceEvent(
            event_id=f"evt-done-{workflow_id}",
            workflow_id=workflow_id,
            event_type=EventType.TASK_COMPLETED,
            timestamp=base_time + timedelta(milliseconds=100),
            details={"status": "success"},
        )
    )


def test_get_compliance_bundle_raises_for_unknown_workflow(tmp_path: Path) -> None:
    """Failure-first: unknown workflow raises WorkflowNotFoundError."""
    svc = ExplainabilityService(recordings_dir=tmp_path / "recordings")
    with pytest.raises(WorkflowNotFoundError) as exc_info:
        svc.get_compliance_bundle("wf-nope")
    assert exc_info.value.workflow_id == "wf-nope"


def test_get_compliance_bundle_reports_missing_user_id(tmp_path: Path) -> None:
    """Failure-first: a workflow missing `user_id` reports
    has_user_id=False and missing_keys=["user_id"].
    """
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    _seed_correlated_workflow(
        recordings,
        "wf-no-user",
        base_time=base,
        include_user_id=False,
    )

    svc = ExplainabilityService(recordings_dir=recordings)
    bundle = svc.get_compliance_bundle("wf-no-user")

    assert bundle.workflow_id == "wf-no-user"
    assert bundle.correlation_health.has_user_id is False
    assert bundle.correlation_health.has_task_id is True
    assert bundle.correlation_health.has_trace_id is True
    assert bundle.correlation_health.has_agent_id is True
    assert bundle.correlation_health.missing_keys == ["user_id"]


def test_get_compliance_bundle_reports_all_missing_keys_explicitly(
    tmp_path: Path,
) -> None:
    """Failure-first: a workflow with no correlation keys reports every key as
    missing — the bundle never silently omits a missing key.
    """
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    _seed_correlated_workflow(
        recordings,
        "wf-bare",
        base_time=base,
        include_user_id=False,
        include_task_id=False,
        include_trace_id=False,
        include_agent_id=False,
    )

    svc = ExplainabilityService(recordings_dir=recordings)
    bundle = svc.get_compliance_bundle("wf-bare")

    health = bundle.correlation_health
    assert health.has_user_id is False
    assert health.has_task_id is False
    assert health.has_trace_id is False
    assert health.has_agent_id is False
    assert set(health.missing_keys) == {
        "user_id",
        "task_id",
        "trace_id",
        "agent_id",
    }


# --- S3.1.2 acceptance ---


def test_get_compliance_bundle_full_correlation_has_no_missing_keys(
    tmp_path: Path,
) -> None:
    """Acceptance: a fully-correlated workflow has empty missing_keys."""
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    _seed_correlated_workflow(recordings, "wf-full", base_time=base)

    svc = ExplainabilityService(recordings_dir=recordings)
    bundle = svc.get_compliance_bundle("wf-full")

    assert bundle.workflow_id == "wf-full"
    assert bundle.correlation_health.has_user_id is True
    assert bundle.correlation_health.has_task_id is True
    assert bundle.correlation_health.has_trace_id is True
    assert bundle.correlation_health.has_agent_id is True
    assert bundle.correlation_health.missing_keys == []
    assert bundle.event_count == 2
    assert bundle.hash_chain_valid is True
    assert bundle.bundle_type == "compliance_audit"


def test_get_compliance_bundle_includes_identity_cards_when_registry_wired(
    tmp_path: Path,
) -> None:
    """Acceptance: identity cards for every agent referenced in the workflow."""
    registry = _make_registry(tmp_path)
    _seed_agent(registry, agent_id="cli-agent", agent_name="CLI Agent")

    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    _seed_correlated_workflow(recordings, "wf-id", base_time=base)

    svc = ExplainabilityService(
        recordings_dir=recordings,
        agent_facts_registry=registry,
    )
    bundle = svc.get_compliance_bundle("wf-id")
    assert "cli-agent" in bundle.identity_cards
    cli_card = bundle.identity_cards["cli-agent"]
    assert cli_card is not None
    assert cli_card.agent_id == "cli-agent"
    assert cli_card.signature_verified is True


def test_get_compliance_bundle_embeds_integrity_clean(tmp_path: Path) -> None:
    """Sprint 3 review F4: ComplianceBundle exposes the IntegrityReport
    embed so the deep-dive Recording quadrant can show evidence."""
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    _seed_correlated_workflow(recordings, "wf-clean", base_time=base)
    svc = ExplainabilityService(recordings_dir=recordings)
    bundle = svc.get_compliance_bundle("wf-clean")
    assert bundle.integrity.workflow_id == "wf-clean"
    assert bundle.integrity.chain_valid is True
    assert bundle.integrity.broken_at_event_id is None
    assert bundle.integrity.expected_hash is None
    assert bundle.integrity.actual_hash is None


def test_get_compliance_bundle_embeds_integrity_break_location(
    tmp_path: Path,
) -> None:
    """Sprint 3 review F4: tampered chain surfaces broken_at_event_id +
    expected/actual hashes through the bundle, not only through
    /workflows/{id}/integrity."""
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    _seed_correlated_workflow(recordings, "wf-tampered-bundle", base_time=base)

    trace_file = recordings / "wf-tampered-bundle" / "trace.jsonl"
    lines = trace_file.read_text().strip().split("\n")
    tampered = json.loads(lines[1])
    tampered["details"] = dict(tampered.get("details") or {})
    tampered["details"]["TAMPERED"] = True
    lines[1] = json.dumps(tampered)
    trace_file.write_text("\n".join(lines) + "\n")

    svc = ExplainabilityService(recordings_dir=recordings)
    bundle = svc.get_compliance_bundle("wf-tampered-bundle")
    assert bundle.integrity.chain_valid is False
    # The break-location fields MUST be populated so the UI can name the
    # broken event explicitly rather than only saying "tampered".
    assert bundle.integrity.broken_at_event_id is not None
    assert bundle.integrity.expected_hash is not None
    assert bundle.integrity.actual_hash is not None
    assert bundle.integrity.expected_hash != bundle.integrity.actual_hash


def test_list_workflow_integrity_returns_one_row_per_workflow(
    tmp_path: Path,
) -> None:
    """Sprint 3 review F3 fix: a single batched call returns every
    workflow's integrity in one pass."""
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    _seed_recorded_workflow(recordings, "wf-a", base_time=base)
    _seed_recorded_workflow(recordings, "wf-b", base_time=base + timedelta(hours=1))

    svc = ExplainabilityService(recordings_dir=recordings)
    summary = svc.list_workflow_integrity()
    ids = {row.workflow.workflow_id for row in summary.rows}
    assert ids == {"wf-a", "wf-b"}
    for row in summary.rows:
        assert row.integrity is not None
        assert row.integrity.chain_valid is True


def test_list_workflow_integrity_matches_per_row_calls(tmp_path: Path) -> None:
    """Sprint 3 review F3: the batched summary MUST agree with the
    per-row N+1 path it replaces.  This is the correctness sentry that
    keeps the new endpoint a true drop-in fix rather than a behaviour
    change."""
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    _seed_recorded_workflow(recordings, "wf-a", base_time=base)
    _seed_recorded_workflow(recordings, "wf-b", base_time=base + timedelta(hours=1))
    _seed_recorded_workflow(recordings, "wf-c", base_time=base + timedelta(hours=2))
    # Tamper one workflow so we exercise the chain_valid=False path.
    trace_file = recordings / "wf-b" / "trace.jsonl"
    lines = trace_file.read_text().strip().split("\n")
    tampered = json.loads(lines[1])
    tampered["details"] = dict(tampered.get("details") or {})
    tampered["details"]["TAMPERED"] = True
    lines[1] = json.dumps(tampered)
    trace_file.write_text("\n".join(lines) + "\n")

    svc = ExplainabilityService(recordings_dir=recordings)
    batched = svc.list_workflow_integrity()

    summaries = svc.list_workflows()
    expected = []
    for summary in summaries:
        report = svc.get_workflow_integrity(summary.workflow_id)
        expected.append((summary, report))

    assert len(batched.rows) == len(expected)
    for row, (summary, report) in zip(batched.rows, expected):
        assert row.workflow.workflow_id == summary.workflow_id
        assert row.workflow.event_count == summary.event_count
        assert row.integrity is not None
        assert row.integrity.chain_valid == report.chain_valid
        assert row.integrity.broken_at_event_id == report.broken_at_event_id


def test_list_workflow_integrity_honours_since_until(tmp_path: Path) -> None:
    """The batched summary respects the same since/until contract as
    `list_workflows` so the Compliance home audit window is honest."""
    recordings = tmp_path / "recordings"
    _seed_recorded_workflow(
        recordings, "wf-old", base_time=datetime(2026, 1, 1, tzinfo=UTC)
    )
    _seed_recorded_workflow(
        recordings, "wf-new", base_time=datetime(2026, 4, 26, tzinfo=UTC)
    )

    svc = ExplainabilityService(recordings_dir=recordings)
    summary = svc.list_workflow_integrity(
        since=datetime(2026, 4, 1, tzinfo=UTC),
        until=datetime(2026, 5, 1, tzinfo=UTC),
    )
    assert {row.workflow.workflow_id for row in summary.rows} == {"wf-new"}
    assert summary.since == datetime(2026, 4, 1, tzinfo=UTC)
    assert summary.until == datetime(2026, 5, 1, tzinfo=UTC)


def test_get_compliance_bundle_includes_phase_decisions_when_logger_wired(
    tmp_path: Path,
) -> None:
    """Acceptance: phase decisions are included when phase_logs_dir is wired."""
    recordings = tmp_path / "recordings"
    phase_logs = tmp_path / "phase_logs"
    base = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    _seed_correlated_workflow(recordings, "wf-phases", base_time=base)
    PhaseLogger(phase_logs).log_decision(
        "wf-phases",
        Decision(
            phase=WorkflowPhase.ROUTING,
            description="picked gpt-4o",
            alternatives=["gpt-4o-mini"],
            rationale="capable",
            confidence=0.85,
        ),
    )

    svc = ExplainabilityService(
        recordings_dir=recordings,
        phase_logs_dir=phase_logs,
    )
    bundle = svc.get_compliance_bundle("wf-phases")
    assert len(bundle.phase_decisions) == 1
    assert bundle.phase_decisions[0].description == "picked gpt-4o"


# --- S4.3.1: query_logs --- failure first


def _write_log(
    log_dir: Path,
    name: str,
    lines: list[str],
) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    file = log_dir / f"{name}.log"
    file.write_text("\n".join(lines) + ("\n" if lines else ""))
    return file


def _log_line(
    *,
    asctime: str = "2026-04-26 08:00:00,000",
    logger: str = "services.guardrails",
    level: str = "INFO",
    message: str = "ok",
) -> str:
    return f"{asctime} {logger} {level} {message}"


def test_query_logs_returns_empty_when_logs_dir_missing(tmp_path: Path) -> None:
    """Failure-first: missing logs dir returns [] (not an error)."""
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        logs_dir=tmp_path / "missing-logs",
    )
    assert svc.query_logs() == []


def test_query_logs_silently_skips_missing_concern_file(tmp_path: Path) -> None:
    """Failure-first: a concern whose log file is missing is silently skipped
    (S4.3.1 AC: 'missing log file is silently skipped, not a 500')."""
    logs_dir = tmp_path / "logs"
    _write_log(
        logs_dir,
        "guards",
        [_log_line(logger="services.guardrails", level="INFO", message="hi")],
    )
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        logs_dir=logs_dir,
    )
    result = svc.query_logs(concerns=["guards", "does_not_exist"])
    # No exception raised, only the existing concern returns rows.
    assert all(row.concern == "guards" for row in result)
    assert len(result) == 1


def test_query_logs_skips_corrupt_lines(tmp_path: Path) -> None:
    """Failure-first: lines that do not match the formatter's pattern are
    surfaced as best-effort rows with level=UNKNOWN, never raise."""
    logs_dir = tmp_path / "logs"
    _write_log(
        logs_dir,
        "guards",
        [
            "this is not a valid log line",
            _log_line(message="real one"),
        ],
    )
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        logs_dir=logs_dir,
    )
    rows = svc.query_logs(concerns=["guards"])
    levels = {r.level for r in rows}
    # The corrupt row is preserved (operators care about every byte that hit
    # the file) but tagged so filters can drop it.
    assert "UNKNOWN" in levels


def test_query_logs_filters_by_level(tmp_path: Path) -> None:
    """Acceptance: level filter excludes other levels."""
    logs_dir = tmp_path / "logs"
    _write_log(
        logs_dir,
        "guards",
        [
            _log_line(level="INFO", message="info"),
            _log_line(level="ERROR", message="boom"),
            _log_line(level="WARN", message="warn"),
        ],
    )
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        logs_dir=logs_dir,
    )
    only_error = svc.query_logs(concerns=["guards"], level="ERROR")
    assert {r.level for r in only_error} == {"ERROR"}


def test_query_logs_filters_by_search_substring(tmp_path: Path) -> None:
    """Acceptance: search filter is a case-insensitive substring match."""
    logs_dir = tmp_path / "logs"
    _write_log(
        logs_dir,
        "guards",
        [
            _log_line(message="prompt-injection blocked"),
            _log_line(message="other"),
        ],
    )
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        logs_dir=logs_dir,
    )
    matched = svc.query_logs(concerns=["guards"], search="injection")
    assert len(matched) == 1
    assert "injection" in matched[0].message


def test_query_logs_filters_by_since(tmp_path: Path) -> None:
    """Acceptance: since filter excludes lines whose timestamp is before
    the cutoff."""
    logs_dir = tmp_path / "logs"
    _write_log(
        logs_dir,
        "guards",
        [
            _log_line(asctime="2026-04-26 07:00:00,000", message="old"),
            _log_line(asctime="2026-04-26 09:00:00,000", message="new"),
        ],
    )
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        logs_dir=logs_dir,
    )
    cutoff = datetime(2026, 4, 26, 8, 0, 0)
    rows = svc.query_logs(concerns=["guards"], since=cutoff)
    assert len(rows) == 1
    assert rows[0].message == "new"


def test_query_logs_default_concerns_includes_explainability(tmp_path: Path) -> None:
    """Acceptance: when no concerns supplied, every known concern (incl.
    'explainability') is searched."""
    logs_dir = tmp_path / "logs"
    _write_log(
        logs_dir,
        "explainability",
        [_log_line(logger="explainability_app.server", message="started")],
    )
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        logs_dir=logs_dir,
    )
    rows = svc.query_logs()
    assert any(r.concern == "explainability" for r in rows)


def test_query_logs_returns_newest_first(tmp_path: Path) -> None:
    """Acceptance: results are sorted newest first regardless of file order."""
    logs_dir = tmp_path / "logs"
    _write_log(
        logs_dir,
        "guards",
        [
            _log_line(asctime="2026-04-26 07:00:00,000", message="old"),
            _log_line(asctime="2026-04-26 09:00:00,000", message="new"),
            _log_line(asctime="2026-04-26 08:00:00,000", message="mid"),
        ],
    )
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        logs_dir=logs_dir,
    )
    rows = svc.query_logs(concerns=["guards"])
    messages = [r.message for r in rows]
    assert messages == ["new", "mid", "old"]


def test_query_logs_respects_limit(tmp_path: Path) -> None:
    """Acceptance: the limit caps the returned rows."""
    logs_dir = tmp_path / "logs"
    _write_log(
        logs_dir,
        "guards",
        [
            _log_line(
                asctime=f"2026-04-26 08:00:{n:02d},000",
                message=f"m{n}",
            )
            for n in range(10)
        ],
    )
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        logs_dir=logs_dir,
    )
    rows = svc.query_logs(concerns=["guards"], limit=3)
    assert len(rows) == 3


# --- S4.3.2: tail_logs (async generator) --- failure first


import asyncio


async def test_tail_logs_silently_skips_when_logs_dir_missing(
    tmp_path: Path,
) -> None:
    """Failure-first: tailing a missing logs directory yields nothing and
    never raises."""
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        logs_dir=tmp_path / "missing-logs",
    )
    gen = svc.tail_logs(concerns=["guards"], poll_interval=0.01)
    try:
        results: list = []
        try:
            results.append(await asyncio.wait_for(anext(gen), timeout=0.05))
        except (asyncio.TimeoutError, StopAsyncIteration):
            pass
        # Either zero rows (timed out before any data) or only legitimate log
        # rows; never an exception.
        assert results == []
    finally:
        await gen.aclose()


async def test_tail_logs_emits_appended_lines(tmp_path: Path) -> None:
    """Acceptance: lines appended after the tail starts are emitted.

    The generator seeds offsets synchronously in `tail_logs(...)` itself, so
    appending after construction is enough to exercise the tail-from-position
    path.
    """
    logs_dir = tmp_path / "logs"
    file = _write_log(
        logs_dir,
        "guards",
        [_log_line(asctime="2026-04-26 08:00:00,000", message="historic")],
    )
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        logs_dir=logs_dir,
    )
    gen = svc.tail_logs(concerns=["guards"], poll_interval=0.01)
    try:
        with open(file, "a") as fh:
            fh.write(_log_line(message="appended"))
            fh.write("\n")
            fh.flush()
        try:
            row = await asyncio.wait_for(anext(gen), timeout=1.0)
        except (StopAsyncIteration, asyncio.TimeoutError):
            row = None
        assert row is not None and row.message == "appended"
    finally:
        await gen.aclose()


async def test_tail_logs_close_does_not_raise(tmp_path: Path) -> None:
    """Failure-first: a client cancelling mid-tail does not raise on the server
    (S4.3.2 AC: 'cancels cleanly when the client disconnects')."""
    logs_dir = tmp_path / "logs"
    _write_log(
        logs_dir,
        "guards",
        [_log_line(message="x")],
    )
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        logs_dir=logs_dir,
    )
    gen = svc.tail_logs(concerns=["guards"], poll_interval=0.01)
    try:
        await asyncio.wait_for(anext(gen), timeout=0.5)
    except (StopAsyncIteration, asyncio.TimeoutError):
        pass
    await gen.aclose()
    # Closing a second time must also be safe.
    await gen.aclose()


# --- Phase 1 hardening: list_workflows until filter & decisions contract ---


def test_list_workflows_until_filter_excludes_newer(tmp_path: Path) -> None:
    """`until` is exclusive on `started_at` and excludes newer workflows."""
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
    result = svc.list_workflows(until=cutoff)
    assert [s.workflow_id for s in result] == ["wf-old"]


def test_list_workflows_since_and_until_combined(tmp_path: Path) -> None:
    """Combining `since` and `until` filters returns only the in-range row."""
    recordings = tmp_path / "recordings"
    for wf, ts in [
        ("wf-too-old", "2026-04-20T00:00:00Z"),
        ("wf-mid", "2026-04-25T00:00:00Z"),
        ("wf-too-new", "2026-05-01T00:00:00Z"),
    ]:
        _write_trace(
            recordings,
            wf,
            [_make_event("task_started", wf, ts)],
        )

    svc = ExplainabilityService(recordings_dir=recordings)
    result = svc.list_workflows(
        since=datetime(2026, 4, 24, tzinfo=UTC),
        until=datetime(2026, 4, 27, tzinfo=UTC),
    )
    assert [s.workflow_id for s in result] == ["wf-mid"]


def test_get_workflow_decisions_returns_empty_for_unknown_workflow_id(
    tmp_path: Path,
) -> None:
    """Documented contract drift: decisions returns `[]` (NOT 404) for an
    unknown workflow id, unlike events/integrity/compliance.

    Phase logging is best-effort and a missing decisions file is a normal
    state for fully cached or short runs.  The dashboard renders an empty
    Decision Audit panel instead of erroring out.
    """
    phase_logs = tmp_path / "phase_logs"
    phase_logs.mkdir()
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        phase_logs_dir=phase_logs,
    )
    assert svc.get_workflow_decisions("wf-never-recorded") == []


# --- Phase 1 hardening: signature_verification_status semantics ---


def test_get_agent_card_verified_when_active_and_signed(tmp_path: Path) -> None:
    """Active agent with a matching signature reports status='verified'."""
    registry = _make_registry(tmp_path)
    _seed_agent(registry, agent_id="cli-agent")
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        agent_facts_registry=registry,
    )
    card = svc.get_agent_card("cli-agent")
    assert card.signature_verified is True
    assert card.signature_verification_status == "verified"


def test_get_agent_card_failed_when_suspended(tmp_path: Path) -> None:
    """Suspended agent reports status='failed' (registry.verify shorts-out)."""
    registry = _make_registry(tmp_path)
    _seed_agent(registry, agent_id="suspended-agent")
    registry.suspend("suspended-agent", reason="for test", suspended_by="tester")
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        agent_facts_registry=registry,
    )
    card = svc.get_agent_card("suspended-agent")
    assert card.signature_verified is False
    assert card.signature_verification_status == "failed"


def test_get_agent_card_unavailable_when_verify_raises(tmp_path: Path) -> None:
    """If `registry.verify(...)` raises (e.g. wrong-key crypto failure), the
    card reports status='unavailable' rather than collapsing to a misleading
    `False` boolean."""

    class _RaisingRegistry:
        def __init__(self, real: AgentFactsRegistry) -> None:
            self._real = real

        def list_agent_ids(self):
            return self._real.list_agent_ids()

        def get(self, agent_id: str):
            return self._real.get(agent_id)

        def audit_trail(self, agent_id: str):
            return self._real.audit_trail(agent_id)

        def verify(self, agent_id: str) -> bool:
            raise RuntimeError("simulated crypto failure")

    real = _make_registry(tmp_path)
    _seed_agent(real, agent_id="cli-agent")
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        agent_facts_registry=_RaisingRegistry(real),  # type: ignore[arg-type]
    )
    card = svc.get_agent_card("cli-agent")
    assert card.signature_verified is False
    assert card.signature_verification_status == "unavailable"


def test_list_agents_uses_public_registry_listing(tmp_path: Path) -> None:
    """Failure-first: a registry that omits `_storage_dir` (public-only API)
    must still yield the registered agents through `list_agent_ids()`."""

    class _PublicOnlyRegistry:
        """Wrapper that proxies only the public read API; trying to access
        `_storage_dir` would AttributeError."""

        def __init__(self, real: AgentFactsRegistry) -> None:
            self._real = real

        def list_agent_ids(self) -> list[str]:
            return self._real.list_agent_ids()

        def get(self, agent_id: str):
            return self._real.get(agent_id)

        def verify(self, agent_id: str) -> bool:
            return self._real.verify(agent_id)

        def audit_trail(self, agent_id: str):
            return self._real.audit_trail(agent_id)

    real = _make_registry(tmp_path)
    _seed_agent(real, agent_id="cli-agent")
    _seed_agent(real, agent_id="dev-agent")
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        agent_facts_registry=_PublicOnlyRegistry(real),  # type: ignore[arg-type]
    )
    cards = svc.list_agents()
    assert {c.agent_id for c in cards} == {"cli-agent", "dev-agent"}


# --- Phase 1 hardening: guardrail aggregation handles real react_loop shapes ---


def _seed_workflow_with_guardrail_shapes(
    recordings_dir: Path,
    workflow_id: str,
    *,
    base_time: datetime,
) -> None:
    """Seed a workflow whose `guardrail_checked` events match what
    `orchestration/react_loop.py` actually emits at runtime: agent_facts
    (`verified`), prompt_injection (`accepted`), output scanner (`stage` +
    `blocked`)."""
    recorder = BlackBoxRecorder(recordings_dir)
    t = base_time

    def _evt() -> str:
        return f"evt-{workflow_id}-{abs(hash((workflow_id, t.isoformat())))}"

    recorder.record(
        TraceEvent(
            event_id=_evt(),
            workflow_id=workflow_id,
            event_type=EventType.TASK_STARTED,
            timestamp=t,
            details={"task_input": "hi", "agent_id": "cli-agent"},
        )
    )
    t += timedelta(milliseconds=10)
    recorder.record(
        TraceEvent(
            event_id=_evt(),
            workflow_id=workflow_id,
            event_type=EventType.GUARDRAIL_CHECKED,
            timestamp=t,
            details={
                "guardrail": "agent_facts",
                "agent_id": "cli-agent",
                "verified": True,
            },
        )
    )
    t += timedelta(milliseconds=10)
    recorder.record(
        TraceEvent(
            event_id=_evt(),
            workflow_id=workflow_id,
            event_type=EventType.GUARDRAIL_CHECKED,
            timestamp=t,
            details={"accepted": True, "guardrail": "prompt_injection"},
        )
    )
    t += timedelta(milliseconds=10)
    recorder.record(
        TraceEvent(
            event_id=_evt(),
            workflow_id=workflow_id,
            event_type=EventType.GUARDRAIL_CHECKED,
            timestamp=t,
            details={
                "stage": "output",
                "blocked": True,
                "failed_rules": ["pii_email"],
            },
        )
    )


def test_guardrail_aggregation_recognises_agent_facts_and_output_shapes(
    tmp_path: Path,
) -> None:
    """The aggregator must classify the three runtime guardrail event
    shapes (`accepted`, `verified`, `stage=output`+`blocked`) instead of
    grouping output rejections under `"unknown"` and miscounting agent_facts
    as failures."""
    recordings = tmp_path / "recordings"
    _seed_workflow_with_guardrail_shapes(
        recordings,
        "wf-shapes",
        base_time=datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC),
    )

    svc = ExplainabilityService(recordings_dir=recordings)
    summary = svc.get_guardrail_summary()
    by_name = {v.name: v for v in summary.per_validator}

    # All three shapes must contribute exactly one event with a known label.
    assert summary.total_checks == 3
    assert summary.pass_count == 2  # agent_facts + prompt_injection
    assert summary.fail_count == 1  # output scanner blocked

    assert "agent_facts" in by_name and by_name["agent_facts"].pass_count == 1
    assert "prompt_injection" in by_name and by_name["prompt_injection"].pass_count == 1
    # Output scanner must not be labelled "unknown".
    assert "output_scanner" in by_name and by_name["output_scanner"].fail_count == 1
    assert "unknown" not in by_name


def test_guardrail_aggregation_skips_unrecognised_shape(tmp_path: Path) -> None:
    """A `guardrail_checked` event with no `accepted`/`verified`/`stage`
    signal is dropped from the denominator rather than being counted as a
    failure (this keeps `pass_rate + fail_rate == 1`)."""
    recordings = tmp_path / "recordings"
    base = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    _write_trace(
        recordings,
        "wf-malformed",
        [
            _make_event("task_started", "wf-malformed", "2026-04-26T08:00:00Z"),
            _make_event(
                "guardrail_checked",
                "wf-malformed",
                "2026-04-26T08:00:01Z",
                details={"some_other_field": "noise"},
            ),
        ],
    )

    svc = ExplainabilityService(recordings_dir=recordings)
    summary = svc.get_guardrail_summary()
    assert summary.total_checks == 0
    assert summary.pass_count == 0
    assert summary.fail_count == 0


# --- Phase 1 / 3 hardening: log timestamp and concern allowlist semantics ---


def test_query_logs_with_aware_since_does_not_raise(tmp_path: Path) -> None:
    """Failure-first: a frontend-supplied aware ISO `since` no longer
    triggers `TypeError: can't compare offset-naive and offset-aware
    datetimes` (regression for the Sprint 4 review F1)."""
    logs_dir = tmp_path / "logs"
    _write_log(
        logs_dir,
        "guards",
        [
            _log_line(asctime="2026-04-26 08:00:00,000", message="historic"),
            _log_line(asctime="2026-04-26 09:00:00,000", message="recent"),
        ],
    )
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        logs_dir=logs_dir,
    )
    cutoff = datetime(2026, 4, 26, 8, 30, 0, tzinfo=UTC)
    rows = svc.query_logs(concerns=["guards"], since=cutoff)
    assert [r.message for r in rows] == ["recent"]


def test_query_logs_warning_alias_matches_python_logging(tmp_path: Path) -> None:
    """Python's logging emits `WARNING`; the UI exposes `WARN`. Both must
    match real warning rows so the operator never sees an empty filter."""
    logs_dir = tmp_path / "logs"
    _write_log(
        logs_dir,
        "guards",
        [
            _log_line(level="WARNING", message="real-python-warning"),
            _log_line(level="INFO", message="ignore"),
        ],
    )
    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        logs_dir=logs_dir,
    )
    rows = svc.query_logs(concerns=["guards"], level="WARN")
    assert [r.message for r in rows] == ["real-python-warning"]


def test_query_logs_rejects_path_traversal_concerns(tmp_path: Path) -> None:
    """Caller-supplied concerns containing `..` or path separators must be
    silently dropped so the service cannot be coerced into reading
    arbitrary files outside `logs/`."""
    logs_dir = tmp_path / "logs"
    _write_log(
        logs_dir,
        "guards",
        [_log_line(message="legit")],
    )
    # Plant a sibling file the service must NOT read.
    sibling = tmp_path / "secret.log"
    sibling.write_text(_log_line(message="secret"))

    svc = ExplainabilityService(
        recordings_dir=tmp_path / "recordings",
        logs_dir=logs_dir,
    )
    rows = svc.query_logs(concerns=["../secret", "guards/../../secret"])
    # Both crafted concerns are dropped; with no remaining concerns we
    # return [] rather than scanning the default allowlist (the caller
    # asked for specific names).
    assert rows == []

    rows = svc.query_logs(concerns=["guards", "../secret"])
    # The legitimate concern still works; the traversal one is dropped.
    assert [r.message for r in rows] == ["legit"]
