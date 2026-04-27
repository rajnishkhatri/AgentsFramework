"""ExplainabilityService: read-only aggregator over governance artifacts.

Scans cache/black_box_recordings/, cache/phase_logs/, cache/agent_facts/,
and logs/*.log to provide structured views for the explainability dashboard.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from services.governance.black_box import BlackBoxRecorder

logger = logging.getLogger("services.explainability")


class WorkflowSummary(BaseModel):
    workflow_id: str
    started_at: datetime | None = None
    event_count: int = 0
    status: str = "unknown"
    primary_agent_id: str | None = None


class BlackBoxEventRecord(BaseModel):
    """Read-only mirror of a recorded `services.governance.black_box.TraceEvent`."""

    event_id: str
    workflow_id: str
    event_type: str
    timestamp: datetime | None = None
    step: int | None = None
    details: dict[str, Any] = {}
    integrity_hash: str = ""


class WorkflowEvents(BaseModel):
    """Result of `get_workflow_events`. Mirrors the API wire shape."""

    workflow_id: str
    event_count: int
    hash_chain_valid: bool
    events: list[BlackBoxEventRecord]


class DecisionRecord(BaseModel):
    """A single phase decision row from `cache/phase_logs/{wf_id}/decisions.jsonl`."""

    workflow_id: str
    phase: str
    description: str
    alternatives: list[str] = []
    rationale: str
    confidence: float
    timestamp: datetime | None = None


class TimeSeriesPoint(BaseModel):
    """A single (bucket, value) pair in a dashboard time series."""

    bucket: datetime
    value: float


class DashboardMetrics(BaseModel):
    """Aggregated KPIs across the workflows in `[since, until)`."""

    total_runs: int = 0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    guardrail_pass_rate: float = 0.0
    hash_chain_valid_count: int = 0
    hash_chain_invalid_count: int = 0
    time_series_cost: list[TimeSeriesPoint] = []
    time_series_latency: list[TimeSeriesPoint] = []
    time_series_tokens: list[TimeSeriesPoint] = []
    model_distribution: dict[str, int] = {}


class WorkflowNotFoundError(KeyError):
    """Raised when a workflow has no recorded trace on disk."""

    def __init__(self, workflow_id: str) -> None:
        super().__init__(workflow_id)
        self.workflow_id = workflow_id


class ExplainabilityService:
    def __init__(
        self,
        recordings_dir: Path | str,
        phase_logs_dir: Path | str | None = None,
    ) -> None:
        self._recordings_dir = Path(recordings_dir)
        self._phase_logs_dir = Path(phase_logs_dir) if phase_logs_dir else None
        self._recorder = BlackBoxRecorder(self._recordings_dir)

    def list_workflows(self, since: datetime | None = None) -> list[WorkflowSummary]:
        if not self._recordings_dir.exists():
            return []

        summaries: list[WorkflowSummary] = []
        for wf_dir in self._recordings_dir.iterdir():
            if not wf_dir.is_dir():
                continue
            trace_file = wf_dir / "trace.jsonl"
            if not trace_file.exists():
                continue
            summary = self._parse_workflow(wf_dir.name, trace_file)
            if summary is None:
                continue
            if since is not None and summary.started_at is not None:
                if summary.started_at < since:
                    continue
            summaries.append(summary)

        summaries.sort(
            key=lambda s: s.started_at or datetime.min,
            reverse=True,
        )
        return summaries

    def _parse_workflow(self, workflow_id: str, trace_file: Path) -> WorkflowSummary | None:
        events: list[dict] = []
        for line in trace_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning(
                    "Skipping corrupted line in %s/%s",
                    workflow_id,
                    trace_file.name,
                )
                continue

        if not events:
            return None

        started_at: datetime | None = None
        status = "in_progress"
        primary_agent_id: str | None = None

        for event in events:
            event_type = event.get("event_type", "")
            if event_type == "task_started" and started_at is None:
                ts_str = event.get("timestamp")
                if ts_str:
                    try:
                        started_at = datetime.fromisoformat(ts_str)
                    except ValueError:
                        pass
            if event_type == "task_completed":
                status = "completed"
            if event_type == "error_occurred":
                status = "error"

            details = event.get("details", {})
            if details.get("agent_id") and primary_agent_id is None:
                primary_agent_id = details["agent_id"]

        return WorkflowSummary(
            workflow_id=workflow_id,
            started_at=started_at,
            event_count=len(events),
            status=status,
            primary_agent_id=primary_agent_id,
        )

    def get_workflow_events(self, workflow_id: str) -> WorkflowEvents:
        """Return the full event timeline for `workflow_id` with hash-chain status.

        Wraps `BlackBoxRecorder.export()`. The integrity check is delegated to
        the recorder — this method never re-implements SHA-256.

        Raises:
            WorkflowNotFoundError: when no `trace.jsonl` exists for the id.
        """
        try:
            export = self._recorder.export(workflow_id)
        except KeyError as exc:
            raise WorkflowNotFoundError(workflow_id) from exc

        events = [
            BlackBoxEventRecord.model_validate(raw) for raw in export.get("events", [])
        ]
        return WorkflowEvents(
            workflow_id=workflow_id,
            event_count=int(export.get("event_count", len(events))),
            hash_chain_valid=bool(export.get("hash_chain_valid", False)),
            events=events,
        )

    def get_workflow_decisions(self, workflow_id: str) -> list[DecisionRecord]:
        """Return the decision log for `workflow_id`, ordered chronologically.

        Reads `cache/phase_logs/{wf_id}/decisions.jsonl`. Returns `[]` when the
        workflow has no decision log (this is intentional — empty is not 404 per
        S1.2.1 AC; an absent decisions file simply means the workflow logged no
        decisions).
        """
        if self._phase_logs_dir is None:
            return []
        log_file = self._phase_logs_dir / workflow_id / "decisions.jsonl"
        if not log_file.exists():
            return []

        records: list[DecisionRecord] = []
        for line in log_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(
                    "Skipping corrupted decision in %s/%s",
                    workflow_id,
                    log_file.name,
                )
                continue
            try:
                records.append(DecisionRecord.model_validate(raw))
            except Exception:
                logger.warning(
                    "Skipping unparseable decision in %s: %r",
                    workflow_id,
                    raw,
                )

        records.sort(key=lambda d: d.timestamp or datetime.min)
        return records

    def get_dashboard_metrics(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> DashboardMetrics:
        """Aggregate KPIs across every workflow whose `started_at` falls in
        `[since, until)` (open intervals when the bound is None).

        Returns the all-zero structure when no workflows are in range — never
        raises (per S1.3.1 AC: "zero workflows in range returns the all-zero
        structure (not 404)").
        """
        if not self._recordings_dir.exists():
            return DashboardMetrics()

        latencies: list[float] = []
        costs: list[float] = []
        tokens: list[int] = []
        cost_buckets: dict[datetime, float] = {}
        latency_buckets: dict[datetime, list[float]] = {}
        tokens_buckets: dict[datetime, int] = {}
        model_counter: Counter[str] = Counter()
        guardrail_pass = 0
        guardrail_total = 0
        hash_chain_valid_count = 0
        hash_chain_invalid_count = 0
        run_count = 0

        for wf_dir in self._recordings_dir.iterdir():
            if not wf_dir.is_dir():
                continue
            trace_file = wf_dir / "trace.jsonl"
            if not trace_file.exists():
                continue

            workflow_id = wf_dir.name
            try:
                export = self._recorder.export(workflow_id)
            except Exception:
                logger.warning(
                    "Skipping unreadable workflow %s during metrics aggregation",
                    workflow_id,
                )
                continue

            events = export.get("events", [])
            started_at = _first_event_timestamp(events)
            if started_at is None:
                continue
            if since is not None and started_at < since:
                continue
            if until is not None and started_at >= until:
                continue

            run_count += 1
            if export.get("hash_chain_valid"):
                hash_chain_valid_count += 1
            else:
                hash_chain_invalid_count += 1

            bucket = _hour_bucket(started_at)
            for event in events:
                event_type = event.get("event_type", "")
                details = event.get("details", {}) or {}
                if event_type == "guardrail_checked":
                    guardrail_total += 1
                    if details.get("accepted"):
                        guardrail_pass += 1
                if event_type == "model_selected":
                    model = details.get("model")
                    if model:
                        model_counter[model] += 1
                if event_type == "step_executed":
                    latency = details.get("latency_ms")
                    cost = details.get("cost_usd")
                    tin = details.get("tokens_in") or 0
                    tout = details.get("tokens_out") or 0
                    if isinstance(latency, (int, float)):
                        latencies.append(float(latency))
                        latency_buckets.setdefault(bucket, []).append(float(latency))
                    if isinstance(cost, (int, float)):
                        costs.append(float(cost))
                        cost_buckets[bucket] = cost_buckets.get(bucket, 0.0) + float(cost)
                    step_tokens = int(tin) + int(tout)
                    if step_tokens:
                        tokens.append(step_tokens)
                        tokens_buckets[bucket] = (
                            tokens_buckets.get(bucket, 0) + step_tokens
                        )

        if run_count == 0:
            return DashboardMetrics()

        return DashboardMetrics(
            total_runs=run_count,
            p50_latency_ms=_percentile(latencies, 50.0),
            p95_latency_ms=_percentile(latencies, 95.0),
            total_cost_usd=round(sum(costs), 6),
            guardrail_pass_rate=(
                guardrail_pass / guardrail_total if guardrail_total else 0.0
            ),
            hash_chain_valid_count=hash_chain_valid_count,
            hash_chain_invalid_count=hash_chain_invalid_count,
            time_series_cost=[
                TimeSeriesPoint(bucket=b, value=round(v, 6))
                for b, v in sorted(cost_buckets.items())
            ],
            time_series_latency=[
                TimeSeriesPoint(bucket=b, value=_percentile(v, 95.0))
                for b, v in sorted(latency_buckets.items())
            ],
            time_series_tokens=[
                TimeSeriesPoint(bucket=b, value=float(v))
                for b, v in sorted(tokens_buckets.items())
            ],
            model_distribution=dict(model_counter),
        )


def _first_event_timestamp(events: list[dict]) -> datetime | None:
    for event in events:
        ts = event.get("timestamp")
        if not ts:
            continue
        try:
            return datetime.fromisoformat(ts)
        except (TypeError, ValueError):
            continue
    return None


def _hour_bucket(ts: datetime) -> datetime:
    return ts.replace(minute=0, second=0, microsecond=0)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (percentile / 100.0) * (len(sorted_values) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return float(
        sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
    )
