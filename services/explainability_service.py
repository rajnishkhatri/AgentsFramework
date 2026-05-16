"""ExplainabilityService: read-only aggregator over governance artifacts.

Scans cache/black_box_recordings/, cache/phase_logs/, cache/agent_facts/,
and logs/*.log to provide structured views for the explainability dashboard.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import Counter
from collections.abc import AsyncIterator, Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from services.governance.agent_facts_registry import AgentFactsRegistry
from services.governance.black_box import BlackBoxRecorder
from services.governance.phase_logger import PhaseLogger
from trust.models import AuditEntry, Capability, Policy

logger = logging.getLogger("services.explainability")


class WorkflowSummary(BaseModel):
    workflow_id: str
    started_at: datetime | None = None
    event_count: int = 0
    status: str = "unknown"
    primary_agent_id: str | None = None


def _parse_trace_timestamp(ts_str: str | None) -> datetime | None:
    """Parse ISO timestamps from trace JSONL; always UTC-aware for stable sorting."""
    if not ts_str:
        return None
    s = str(ts_str).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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


class ValidatorStat(BaseModel):
    """Per-validator roll-up for the guardrail monitor.

    `name` mirrors the `details.guardrail` field on a `guardrail_checked` event.
    No knowledge of the validator's internals -- this is a generic counter.
    """

    name: str
    total_checks: int = 0
    pass_count: int = 0
    fail_count: int = 0
    pass_rate: float = 0.0


class GuardrailFailure(BaseModel):
    """Recent guardrail rejection surfaced for the failures table."""

    workflow_id: str
    validator: str
    fail_action: str | None = None
    timestamp: datetime | None = None


class GuardrailSummary(BaseModel):
    """Aggregated guardrail signals for the `[since, until)` window.

    Trend is the single-number delta between this window's `pass_rate` and the
    pass_rate of the immediately preceding window of equal length (per
    S2.1.1 AC: "Trends are a single number (delta vs prior period)").
    """

    total_checks: int = 0
    pass_count: int = 0
    fail_count: int = 0
    pass_rate: float = 0.0
    fail_action_distribution: dict[str, int] = {}
    per_validator: list[ValidatorStat] = []
    recent_failures: list[GuardrailFailure] = []
    trend_pass_rate_delta: float = 0.0


class WorkflowNotFoundError(KeyError):
    """Raised when a workflow has no recorded trace on disk."""

    def __init__(self, workflow_id: str) -> None:
        super().__init__(workflow_id)
        self.workflow_id = workflow_id


class AgentNotFoundError(KeyError):
    """Raised when an agent id is not registered in `AgentFactsRegistry`."""

    def __init__(self, agent_id: str) -> None:
        super().__init__(agent_id)
        self.agent_id = agent_id


SignatureVerificationStatus = Literal["verified", "failed", "unavailable"]


class AgentCard(BaseModel):
    """Read-only projection of `AgentFacts` for the registry views.

    F-R6 (sprint board): a strict subset of `AgentFacts` -- no mutation API,
    no `signature_hash` setter. Verification of the HMAC is computed
    server-side via `AgentFactsRegistry.verify(agent_id)` and exposed both
    as the legacy `signature_verified` boolean (for back-compat) and the
    richer `signature_verification_status` string. The string value
    distinguishes `verified` (HMAC matched), `failed` (HMAC did not match
    or status != active), and `unavailable` (no verification was possible
    -- e.g. registry/secret missing). Collapsing all three into a single
    boolean conflates trust signals; the UI MUST consume the status string
    when rendering a verification badge.
    """

    agent_id: str
    agent_name: str
    owner: str
    version: str
    description: str = ""
    capabilities: list[Capability] = []
    policies: list[Policy] = []
    status: str
    valid_until: datetime | None = None
    parent_agent_id: str | None = None
    signature_truncated: str
    signature_verified: bool
    signature_verification_status: SignatureVerificationStatus = "unavailable"
    created_at: datetime
    updated_at: datetime


class AgentAuditEntry(BaseModel):
    """Read-only mirror of `trust.models.AuditEntry` for the audit timeline."""

    agent_id: str
    action: str
    performed_by: str
    timestamp: datetime
    details: dict[str, Any] = {}


# Sprint 3 -- Compliance Integrity & Bundle


class IntegrityReport(BaseModel):
    """S3.1.1: chain-integrity result for a single workflow.

    `chain_valid=True` -> all break-location fields are None.  When the chain
    is broken, the FIRST mismatch is exposed so the UI can highlight the
    breakage location.  Hash recomputation is delegated to
    `BlackBoxRecorder.export()` -- this layer never re-implements SHA-256
    (TAP-1).
    """

    workflow_id: str
    chain_valid: bool
    broken_at_event_id: str | None = None
    expected_hash: str | None = None
    actual_hash: str | None = None


CORRELATION_KEYS: tuple[str, ...] = (
    "trace_id",
    "user_id",
    "task_id",
    "agent_id",
)


class CorrelationHealth(BaseModel):
    """S3.1.2: explicit per-key correlation status for a workflow.

    Every correlation key is reported as a boolean -- the bundle never
    silently omits a missing key.  `missing_keys` is the convenience list
    consumed by the Compliance UI's "missing keys named explicitly" card.
    """

    has_trace_id: bool
    has_user_id: bool
    has_task_id: bool
    has_agent_id: bool
    missing_keys: list[str] = []


class LogRow(BaseModel):
    """S4.3.1: a single parsed line from one of the per-concern `logs/*.log` files.

    The format mirrors the JSON formatter declared in `logging.json`:
      ``%(asctime)s %(name)s %(levelname)s %(message)s``

    Lines that do not match are surfaced verbatim with `level="UNKNOWN"` so
    the operator never silently loses bytes that hit disk.  H1: this method
    has no knowledge of any specific service's log content -- it only consumes
    the stable formatter shape.
    """

    concern: str
    timestamp: datetime | None = None
    logger: str = ""
    level: str = "UNKNOWN"
    message: str = ""
    raw: str = ""


# Maps the per-concern handler names from `logging.json` (the file names
# under `logs/`) to the concern key surfaced through the API.  Adding a new
# handler in `logging.json` requires a new row here AND a new row in
# `frontend-explainability/lib/wire/responses.ts` LOG_CONCERN_KEYS.
DEFAULT_LOG_CONCERNS: tuple[str, ...] = (
    "prompts",
    "guards",
    "evals",
    "tools",
    "routing",
    "black_box",
    "phases",
    "identity",
    "drift",
    "framework_telemetry",
    "trust_trace",
    "authorization",
    "long_term_memory",
    "agent_ui_adapter_server",
    "agent_ui_adapter_transport",
    "agent_ui_adapter_translators",
    "explainability",
)


_LOG_LINE_RE = re.compile(
    r"^(?P<asctime>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[,.\d]+)?)\s+"
    r"(?P<logger>\S+)\s+"
    r"(?P<level>[A-Z]+)\s+"
    r"(?P<message>.*)$"
)


class ComplianceBundle(BaseModel):
    """S3.1.2: read-only projection of `BlackBoxRecorder.export_for_compliance`.

    Adds the `correlation_health` block derived from the events' `details`
    dicts AND embeds the full `IntegrityReport` so the deep-dive Recording
    quadrant can name the broken event id and show the expected/actual
    hash mismatch (Sprint 3 review F4).  Never mutates the bundle; never
    re-runs the agent.  The wire shape is a strict subset (no setters, no
    signed-field exposure beyond `signature_truncated` on the embedded
    `AgentCard` projections).
    """

    workflow_id: str
    event_count: int
    hash_chain_valid: bool
    bundle_type: str = "compliance_audit"
    exported_at: datetime | None = None
    events: list[BlackBoxEventRecord] = []
    identity_cards: dict[str, AgentCard | None] = {}
    audit_trails: dict[str, list[AgentAuditEntry]] = {}
    phase_decisions: list[DecisionRecord] = []
    correlation_health: CorrelationHealth
    integrity: IntegrityReport


class WorkflowIntegritySummary(BaseModel):
    """Single row in the batched compliance summary view.

    Pairs a `WorkflowSummary` with its `IntegrityReport` (or ``None`` when
    the workflow could not be read).  Computed by
    :meth:`ExplainabilityService.list_workflow_integrity` so the
    Compliance Center home can render with one round-trip instead of one
    integrity call per workflow (Sprint 3 review F3).
    """

    workflow: WorkflowSummary
    integrity: IntegrityReport | None = None


class ComplianceSummary(BaseModel):
    """Batched compliance home payload (Sprint 3 review F3 fix)."""

    rows: list[WorkflowIntegritySummary] = []
    generated_at: datetime
    since: datetime | None = None
    until: datetime | None = None


class ExplainabilityService:
    def __init__(
        self,
        recordings_dir: Path | str,
        phase_logs_dir: Path | str | None = None,
        agent_facts_registry: AgentFactsRegistry | None = None,
        logs_dir: Path | str | None = None,
    ) -> None:
        self._recordings_dir = Path(recordings_dir)
        self._phase_logs_dir = Path(phase_logs_dir) if phase_logs_dir else None
        self._recorder = BlackBoxRecorder(self._recordings_dir)
        self._agent_facts_registry = agent_facts_registry
        self._logs_dir = Path(logs_dir) if logs_dir else None

    def list_workflows(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[WorkflowSummary]:
        """Return workflow summaries newest first, optionally bounded.

        ``since`` is inclusive on ``started_at``; ``until`` is exclusive
        (matches the convention used by ``get_dashboard_metrics`` and
        ``get_guardrail_summary``). Workflows without a parseable
        ``started_at`` are returned unconditionally so they remain visible
        in the UI even when their trace is incomplete.
        """
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
            if summary.started_at is not None:
                if since is not None and summary.started_at < since:
                    continue
                if until is not None and summary.started_at >= until:
                    continue
            summaries.append(summary)

        summaries.sort(
            key=lambda s: s.started_at
            or datetime.min.replace(tzinfo=timezone.utc),
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
                started_at = _parse_trace_timestamp(event.get("timestamp"))
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

        Reads `cache/phase_logs/{wf_id}/decisions.jsonl`. Returns `[]` when
        the workflow has no decision log.

        Contract drift note: this method intentionally returns `[]` for an
        unknown ``workflow_id`` rather than raising
        :class:`WorkflowNotFoundError`. Phase logging is best-effort and a
        decision file may legitimately be absent (e.g. fully cached run);
        the dashboard renders an empty Decision Audit panel instead of a
        404. Use :meth:`get_workflow_events` /
        :meth:`get_workflow_integrity` to assert workflow existence
        explicitly when 404 semantics are required.
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
                    accepted = _guardrail_accepted(details)
                    if accepted is not None:
                        guardrail_total += 1
                        if accepted:
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

    def get_guardrail_summary(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        recent_failures_limit: int = 25,
    ) -> GuardrailSummary:
        """Aggregate `guardrail_checked` events into a per-validator summary.

        S2.1.1 ACs:
          * Read events from `cache/black_box_recordings/*/trace.jsonl`.
          * Roll up totals, fail-action distribution, and per-validator stats.
          * Trends are a single number (delta vs prior period).
          * Zero events in range returns the all-zero structure (not 404).

        H1: this method has no knowledge of `services/governance/guardrail_validator.py`'s
        internals -- it consumes the recorded `details.guardrail`, `details.accepted`,
        and `details.fail_action` keys only.
        """
        current = self._aggregate_guardrails_window(
            since=since,
            until=until,
            recent_failures_limit=recent_failures_limit,
        )
        prior_pass_rate = self._aggregate_prior_pass_rate(since=since, until=until)
        delta = (
            (current.pass_rate - prior_pass_rate)
            if prior_pass_rate is not None
            else 0.0
        )
        return current.model_copy(update={"trend_pass_rate_delta": delta})

    def _aggregate_guardrails_window(
        self,
        since: datetime | None,
        until: datetime | None,
        recent_failures_limit: int,
    ) -> GuardrailSummary:
        if not self._recordings_dir.exists():
            return GuardrailSummary()

        per_validator: dict[str, dict[str, int]] = {}
        fail_action_counter: Counter[str] = Counter()
        failures: list[GuardrailFailure] = []
        total = 0
        passes = 0

        for wf_dir in self._recordings_dir.iterdir():
            if not wf_dir.is_dir():
                continue
            trace_file = wf_dir / "trace.jsonl"
            if not trace_file.exists():
                continue
            for event in _safe_iter_events(trace_file):
                if event.get("event_type") != "guardrail_checked":
                    continue
                ts = _parse_timestamp(event.get("timestamp"))
                if ts is None:
                    continue
                if since is not None and ts < since:
                    continue
                if until is not None and ts >= until:
                    continue

                details = event.get("details") or {}
                accepted = _guardrail_accepted(details)
                if accepted is None:
                    # Event shape did not carry a pass/fail signal; skip the
                    # row rather than mis-attributing it as a fail.  This
                    # keeps `pass_rate + fail_rate == 1` invariant intact.
                    continue
                validator = _guardrail_validator_name(details)

                bucket = per_validator.setdefault(
                    validator, {"total": 0, "pass": 0, "fail": 0}
                )
                bucket["total"] += 1
                total += 1
                if accepted:
                    bucket["pass"] += 1
                    passes += 1
                else:
                    bucket["fail"] += 1
                    fail_action = details.get("fail_action")
                    if fail_action:
                        fail_action_counter[str(fail_action)] += 1
                    failures.append(
                        GuardrailFailure(
                            workflow_id=wf_dir.name,
                            validator=validator,
                            fail_action=(
                                str(fail_action) if fail_action else None
                            ),
                            timestamp=ts,
                        )
                    )

        if total == 0:
            return GuardrailSummary()

        validator_stats = sorted(
            (
                ValidatorStat(
                    name=name,
                    total_checks=stats["total"],
                    pass_count=stats["pass"],
                    fail_count=stats["fail"],
                    pass_rate=(
                        stats["pass"] / stats["total"] if stats["total"] else 0.0
                    ),
                )
                for name, stats in per_validator.items()
            ),
            key=lambda v: v.name,
        )
        failures.sort(
            key=lambda f: f.timestamp or datetime.min,
            reverse=True,
        )
        return GuardrailSummary(
            total_checks=total,
            pass_count=passes,
            fail_count=total - passes,
            pass_rate=passes / total,
            fail_action_distribution=dict(fail_action_counter),
            per_validator=validator_stats,
            recent_failures=failures[:recent_failures_limit],
            trend_pass_rate_delta=0.0,
        )

    # --- S2.2.1: agent registry views (read-only over AgentFactsRegistry) ---

    def list_agents(self) -> list[AgentCard]:
        """Return every registered agent as a read-only `AgentCard`.

        Returns `[]` when no registry was wired in (the dashboard always
        renders structurally on a cold install -- no 404). Uses the
        registry's public :meth:`AgentFactsRegistry.list_agent_ids` API so
        this method does not depend on private storage layout.
        """
        if self._agent_facts_registry is None:
            return []
        try:
            agent_ids = self._agent_facts_registry.list_agent_ids()
        except Exception:
            logger.warning(
                "Failed to enumerate agents from registry; "
                "returning empty list",
                exc_info=True,
            )
            return []
        cards: list[AgentCard] = []
        for agent_id in agent_ids:
            try:
                cards.append(self.get_agent_card(agent_id))
            except AgentNotFoundError:
                continue
            except Exception:
                logger.warning(
                    "Skipping unreadable agent facts for %s",
                    agent_id,
                    exc_info=True,
                )
                continue
        cards.sort(key=lambda c: c.agent_id)
        return cards

    def get_agent_card(self, agent_id: str) -> AgentCard:
        """Return the read-only identity card for `agent_id`.

        Raises:
            AgentNotFoundError: when no registry is wired or the id is unknown.
        """
        if self._agent_facts_registry is None:
            raise AgentNotFoundError(agent_id)
        try:
            facts = self._agent_facts_registry.get(agent_id)
        except KeyError as exc:
            raise AgentNotFoundError(agent_id) from exc

        verification_status: SignatureVerificationStatus
        try:
            verified = bool(self._agent_facts_registry.verify(agent_id))
            verification_status = "verified" if verified else "failed"
        except Exception:
            logger.warning(
                "Signature verification raised for agent %s; "
                "reporting verification_status=unavailable",
                agent_id,
                exc_info=True,
            )
            verified = False
            verification_status = "unavailable"

        sig = facts.signature_hash or ""
        truncated = f"{sig[:8]}…{sig[-8:]}" if len(sig) > 16 else sig
        return AgentCard(
            agent_id=facts.agent_id,
            agent_name=facts.agent_name,
            owner=facts.owner,
            version=facts.version,
            description=facts.description,
            capabilities=list(facts.capabilities),
            policies=list(facts.policies),
            status=facts.status.value,
            valid_until=facts.valid_until,
            parent_agent_id=facts.parent_agent_id,
            signature_truncated=truncated,
            signature_verified=verified,
            signature_verification_status=verification_status,
            created_at=facts.created_at,
            updated_at=facts.updated_at,
        )

    def get_agent_audit(self, agent_id: str) -> list[AgentAuditEntry]:
        """Return the chronological audit trail for `agent_id`.

        Raises:
            AgentNotFoundError: when no registry is wired or the agent itself
            is unknown.  Returns `[]` when the agent exists but has no audit
            entries (e.g. an audit file rotated away).
        """
        if self._agent_facts_registry is None:
            raise AgentNotFoundError(agent_id)
        try:
            self._agent_facts_registry.get(agent_id)
        except KeyError as exc:
            raise AgentNotFoundError(agent_id) from exc

        raw_entries: list[AuditEntry] = self._agent_facts_registry.audit_trail(
            agent_id
        )
        return [
            AgentAuditEntry(
                agent_id=entry.agent_id,
                action=entry.action,
                performed_by=entry.performed_by,
                timestamp=entry.timestamp,
                details=dict(entry.details),
            )
            for entry in raw_entries
        ]

    # --- S3.1.1 / S3.1.2: Compliance integrity & bundle ---

    def get_workflow_integrity(self, workflow_id: str) -> IntegrityReport:
        """Return a chain-integrity report for `workflow_id`.

        Wraps `BlackBoxRecorder.export()` (which already verifies the chain)
        and re-shapes its `broken_at_event_id` / `broken_expected_hash` /
        `broken_actual_hash` extension into the explicit `IntegrityReport`
        wire shape.  Never re-implements SHA-256 (TAP-1).

        Raises:
            WorkflowNotFoundError: when no `trace.jsonl` exists for the id.
        """
        try:
            export = self._recorder.export(workflow_id)
        except KeyError as exc:
            raise WorkflowNotFoundError(workflow_id) from exc
        return IntegrityReport(
            workflow_id=workflow_id,
            chain_valid=bool(export.get("hash_chain_valid", False)),
            broken_at_event_id=export.get("broken_at_event_id"),
            expected_hash=export.get("broken_expected_hash"),
            actual_hash=export.get("broken_actual_hash"),
        )

    def get_compliance_bundle(self, workflow_id: str) -> ComplianceBundle:
        """Return the four-pillar compliance bundle for `workflow_id`.

        Delegates to `BlackBoxRecorder.export_for_compliance(...)` (which is
        the canonical join of recording + identity + reasoning artifacts) and
        adds a `correlation_health` block derived from event `details`.
        Missing correlation keys are NEVER silently omitted -- both the
        boolean per-key flags and the `missing_keys` list are populated.

        Raises:
            WorkflowNotFoundError: when no `trace.jsonl` exists for the id.
        """
        phase_logger = (
            PhaseLogger(self._phase_logs_dir) if self._phase_logs_dir else None
        )
        try:
            raw = self._recorder.export_for_compliance(
                workflow_id,
                agent_facts_registry=self._agent_facts_registry,
                phase_logger=phase_logger,
            )
        except KeyError as exc:
            raise WorkflowNotFoundError(workflow_id) from exc

        if not raw.get("events"):
            # `export_for_compliance` calls `export()` first; an empty/missing
            # workflow is signalled by KeyError above. Belt-and-braces.
            raise WorkflowNotFoundError(workflow_id)

        events = [
            BlackBoxEventRecord.model_validate(raw_event)
            for raw_event in raw.get("events", [])
        ]

        identity_cards: dict[str, AgentCard | None] = {}
        if self._agent_facts_registry is not None:
            for agent_id in raw.get("identity_cards", {}):
                if agent_id is None:
                    continue
                try:
                    identity_cards[agent_id] = self.get_agent_card(agent_id)
                except AgentNotFoundError:
                    identity_cards[agent_id] = None

        audit_trails: dict[str, list[AgentAuditEntry]] = {}
        if self._agent_facts_registry is not None:
            for agent_id in raw.get("audit_trails", {}):
                if agent_id is None:
                    continue
                try:
                    audit_trails[agent_id] = self.get_agent_audit(agent_id)
                except AgentNotFoundError:
                    audit_trails[agent_id] = []

        phase_decisions: list[DecisionRecord] = []
        for raw_decision in raw.get("phase_decisions", []) or []:
            try:
                phase_decisions.append(
                    DecisionRecord.model_validate(raw_decision)
                )
            except Exception:
                logger.warning(
                    "Skipping unparseable phase decision in %s: %r",
                    workflow_id,
                    raw_decision,
                )

        correlation_health = _derive_correlation_health(raw.get("events", []))
        exported_at_raw = raw.get("exported_at")
        exported_at = _parse_timestamp(exported_at_raw)

        # Sprint 3 review F4: include the IntegrityReport so the deep-dive
        # Recording quadrant can show `broken_at_event_id` plus the
        # expected/actual hash mismatch.  We synthesize it directly from
        # the same `raw` payload to avoid re-reading the trace file.
        integrity = IntegrityReport(
            workflow_id=workflow_id,
            chain_valid=bool(raw.get("hash_chain_valid", False)),
            broken_at_event_id=raw.get("broken_at_event_id"),
            expected_hash=raw.get("broken_expected_hash"),
            actual_hash=raw.get("broken_actual_hash"),
        )

        return ComplianceBundle(
            workflow_id=workflow_id,
            event_count=int(raw.get("event_count", len(events))),
            hash_chain_valid=bool(raw.get("hash_chain_valid", False)),
            bundle_type=str(raw.get("bundle_type", "compliance_audit")),
            exported_at=exported_at,
            events=events,
            identity_cards=identity_cards,
            audit_trails=audit_trails,
            phase_decisions=phase_decisions,
            correlation_health=correlation_health,
            integrity=integrity,
        )

    # --- Sprint 3 review F3 fix: batched compliance summary ---

    def list_workflow_integrity(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> ComplianceSummary:
        """Return one summary + integrity row per workflow in ``[since, until)``.

        Replaces the per-row N+1 fan-out on the Compliance home: one call
        gets every workflow's chain status in a single pass, sharing the
        `BlackBoxRecorder.export()` invocation that already verifies the
        chain.  Workflows that fail to read are surfaced with
        ``integrity=None`` rather than dropped, so the operator never
        loses visibility into a corrupted directory.
        """
        summaries = self.list_workflows(since=since, until=until)
        rows: list[WorkflowIntegritySummary] = []
        for summary in summaries:
            try:
                report = self.get_workflow_integrity(summary.workflow_id)
            except WorkflowNotFoundError:
                report = None
            except Exception:
                logger.warning(
                    "Skipping workflow %s during compliance summary: "
                    "integrity read raised",
                    summary.workflow_id,
                    exc_info=True,
                )
                report = None
            rows.append(
                WorkflowIntegritySummary(workflow=summary, integrity=report)
            )
        return ComplianceSummary(
            rows=rows,
            generated_at=datetime.now(timezone.utc),
            since=since,
            until=until,
        )

    # --- S4.3.1 / S4.3.2: Log viewer (read-only file aggregator) ---

    def query_logs(
        self,
        concerns: Sequence[str] | None = None,
        level: str | None = None,
        search: str | None = None,
        since: datetime | None = None,
        limit: int = 500,
    ) -> list[LogRow]:
        """Read newest-first log rows for the given concerns.

        S4.3.1 ACs:
          * Reads `logs/*.log` files matching the per-concern names from
            `logging.json`.
          * Filters: `concerns`, `level`, `search`, `since`, `limit`.
          * Returns newest-first.
          * Missing log file is silently skipped (NEVER raises).
          * Missing logs dir returns [].

        Lines that cannot be parsed against the formatter pattern are returned
        with `level="UNKNOWN"` so the operator never silently loses bytes.
        """
        if self._logs_dir is None or not self._logs_dir.exists():
            return []
        wanted = _normalize_concerns(concerns)
        rows: list[LogRow] = []
        for concern in wanted:
            log_file = self._logs_dir / f"{concern}.log"
            if not log_file.exists():
                continue
            try:
                text = log_file.read_text()
            except OSError:
                logger.warning(
                    "Skipping unreadable log file %s", log_file, exc_info=True
                )
                continue
            for line in text.splitlines():
                if not line.strip():
                    continue
                row = _parse_log_line(line, concern=concern)
                if not _row_matches(row, level=level, search=search, since=since):
                    continue
                rows.append(row)

        rows.sort(
            key=lambda r: r.timestamp or _DT_MIN_UTC,
            reverse=True,
        )
        if limit > 0:
            rows = rows[:limit]
        return rows

    def tail_logs(
        self,
        concerns: Sequence[str] | None = None,
        level: str | None = None,
        search: str | None = None,
        poll_interval: float = 1.0,
    ) -> AsyncIterator[LogRow]:
        """Return an async generator that yields newly-appended log rows.

        S4.3.2: poll-from-position loop (per the sprint board's documented
        limitation: rotation is not detected; see
        `explainability_app/transport/sse.py` docstring).

        The offsets are seeded SYNCHRONOUSLY here -- before the generator's
        first `__anext__` runs -- so the contract "tail starts at file end"
        holds even if the consumer cancels the first `wait_for(anext(gen))`
        before yielding.

        Stop signalling: the consumer calls `aclose()`.  Cancelling a single
        `wait_for(anext(gen))` does close the generator (asyncio's documented
        behavior), so consumers that need to tolerate timeouts should instead
        wrap the entire `async for ... in tail_logs(...)` in a watchdog.
        """
        wanted = _normalize_concerns(concerns)
        offsets: dict[str, int] = {}
        if self._logs_dir is not None and self._logs_dir.exists():
            for concern in wanted:
                file = self._logs_dir / f"{concern}.log"
                if file.exists():
                    try:
                        offsets[concern] = file.stat().st_size
                    except OSError:
                        offsets[concern] = 0
                else:
                    offsets[concern] = 0
        return self._tail_logs_loop(
            wanted=wanted,
            offsets=offsets,
            level=level,
            search=search,
            poll_interval=poll_interval,
        )

    async def _tail_logs_loop(
        self,
        *,
        wanted: list[str],
        offsets: dict[str, int],
        level: str | None,
        search: str | None,
        poll_interval: float,
    ) -> AsyncIterator[LogRow]:
        if self._logs_dir is None or not self._logs_dir.exists():
            return
        while True:
            for concern in wanted:
                file = self._logs_dir / f"{concern}.log"
                if not file.exists():
                    continue
                try:
                    size = file.stat().st_size
                except OSError:
                    continue
                last = offsets.get(concern, 0)
                if size <= last:
                    continue
                try:
                    with open(file, "r") as fh:
                        fh.seek(last)
                        chunk = fh.read()
                        offsets[concern] = fh.tell()
                except OSError:
                    continue
                for line in chunk.splitlines():
                    if not line.strip():
                        continue
                    row = _parse_log_line(line, concern=concern)
                    if not _row_matches(
                        row, level=level, search=search, since=None
                    ):
                        continue
                    yield row
            await asyncio.sleep(poll_interval)

    def _aggregate_prior_pass_rate(
        self,
        since: datetime | None,
        until: datetime | None,
    ) -> float | None:
        """Return the pass_rate of the immediately preceding window, or None.

        When `since` and `until` are both unbounded the prior window is also
        unbounded -- there is no meaningful trend, so we return None and the
        caller emits delta=0.
        """
        if since is None or until is None:
            return None
        window = until - since
        prior_since = since - window
        prior_until = since
        prior = self._aggregate_guardrails_window(
            since=prior_since,
            until=prior_until,
            recent_failures_limit=0,
        )
        if prior.total_checks == 0:
            return None
        return prior.pass_rate


_ALLOWED_LOG_CONCERNS: frozenset[str] = frozenset(DEFAULT_LOG_CONCERNS)

# Used as a sortable fallback when a log row has no parsable timestamp.
# Aware-UTC so it compares cleanly against the aware row timestamps that
# `_parse_log_timestamp` now returns.
_DT_MIN_UTC: datetime = datetime.min.replace(tzinfo=timezone.utc)


def _normalize_concerns(concerns: Sequence[str] | None) -> list[str]:
    """Restrict caller-supplied concern strings to the known allowlist.

    The Log Viewer endpoint exposes concerns as user-controlled query
    params.  Without this allowlist, a crafted value such as ``"../foo"``
    would let the service open ``logs/../foo.log`` and read arbitrary
    ``*.log`` files on disk.  Unknown values are silently dropped so the
    UI never sees a 500 for a typo and an attacker cannot enumerate
    filesystem state via differential responses.
    """
    if not concerns:
        return list(DEFAULT_LOG_CONCERNS)
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in concerns:
        if not isinstance(raw, str):
            continue
        # Reject anything that smells like a path component.
        if "/" in raw or "\\" in raw or raw in {".", ".."}:
            logger.warning(
                "Rejecting log concern %r: contains a path separator", raw
            )
            continue
        if raw not in _ALLOWED_LOG_CONCERNS:
            logger.warning(
                "Rejecting log concern %r: not in the known allowlist", raw
            )
            continue
        if raw in seen:
            continue
        seen.add(raw)
        ordered.append(raw)
    return ordered


def _guardrail_accepted(details: dict) -> bool | None:
    """Return the pass/fail signal for a `guardrail_checked` event, or None.

    Handles the three shapes emitted by `orchestration/react_loop.py`:
      * input prompt-injection: ``{"accepted": <bool>, ...}``
      * agent-facts identity:   ``{"verified": <bool>, "guardrail": "agent_facts"}``
      * output scanner:         ``{"stage": "output", "blocked": <bool>, ...}``

    Returning ``None`` (instead of defaulting to ``False``) keeps the
    pass-rate denominator honest when an unknown shape sneaks in -- the
    aggregator skips the row instead of misclassifying it as a failure.
    """
    if not isinstance(details, dict):
        return None
    if "accepted" in details and isinstance(details["accepted"], bool):
        return details["accepted"]
    if "verified" in details and isinstance(details["verified"], bool):
        return details["verified"]
    if details.get("stage") == "output" and isinstance(
        details.get("blocked"), bool
    ):
        return not details["blocked"]
    return None


def _guardrail_validator_name(details: dict) -> str:
    """Best-effort validator label for a `guardrail_checked` event.

    Falls back through the orchestration-specific shape variants so the
    Guardrail Monitor never groups output-scanner rejections under
    ``"unknown"``.
    """
    name = details.get("guardrail")
    if isinstance(name, str) and name:
        return name
    stage = details.get("stage")
    if isinstance(stage, str) and stage:
        return f"output_scanner:{stage}" if stage != "output" else "output_scanner"
    return "unknown"


def _safe_iter_events(trace_file: Path):
    """Yield parsed events from a JSONL trace file, skipping corrupted lines."""
    for line in trace_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Skipping corrupted line in %s", trace_file)
            continue


def _parse_timestamp(raw: object) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


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


def _parse_log_line(line: str, *, concern: str) -> LogRow:
    """Parse one log line into a `LogRow`.  Unparseable lines come back with
    `level="UNKNOWN"` and the full line in `raw`/`message`."""
    match = _LOG_LINE_RE.match(line)
    if match is None:
        return LogRow(
            concern=concern,
            timestamp=None,
            logger="",
            level="UNKNOWN",
            message=line,
            raw=line,
        )
    asctime = match.group("asctime")
    timestamp = _parse_log_timestamp(asctime)
    return LogRow(
        concern=concern,
        timestamp=timestamp,
        logger=match.group("logger"),
        level=match.group("level"),
        message=match.group("message"),
        raw=line,
    )


def _parse_log_timestamp(asctime: str) -> datetime | None:
    # Python's logging asctime is `YYYY-MM-DD HH:MM:SS,mmm` and is emitted
    # without timezone info.  We attach UTC so comparisons against
    # frontend-supplied ISO bounds (which are timezone-aware via
    # `Date.toISOString()`) do not raise
    # `TypeError: can't compare offset-naive and offset-aware datetimes`.
    parsed: datetime | None = None
    try:
        if "," in asctime:
            base, ms = asctime.rsplit(",", 1)
            base_dt = datetime.strptime(base, "%Y-%m-%d %H:%M:%S")
            parsed = base_dt.replace(microsecond=int(ms) * 1000)
        else:
            parsed = datetime.strptime(asctime, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            parsed = datetime.fromisoformat(asctime)
        except ValueError:
            return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# Python `logging` emits `WARNING`; the frontend exposes `WARN` for brevity.
# Keep both names accepted on input so the Log Viewer never appears to drop
# real warnings.
_LEVEL_ALIASES: dict[str, set[str]] = {
    "WARN": {"WARN", "WARNING"},
    "WARNING": {"WARN", "WARNING"},
}


def _level_matches(row_level: str, requested: str) -> bool:
    requested_upper = requested.upper()
    accepted = _LEVEL_ALIASES.get(requested_upper, {requested_upper})
    return row_level.upper() in accepted


def _normalize_since(since: datetime | None) -> datetime | None:
    if since is None:
        return None
    if since.tzinfo is None:
        return since.replace(tzinfo=timezone.utc)
    return since


def _row_matches(
    row: LogRow,
    *,
    level: str | None,
    search: str | None,
    since: datetime | None,
) -> bool:
    if level is not None and not _level_matches(row.level, level):
        return False
    if search is not None and search.strip():
        if search.lower() not in row.message.lower():
            return False
    normalized_since = _normalize_since(since)
    if normalized_since is not None and row.timestamp is not None:
        row_ts = row.timestamp
        if row_ts.tzinfo is None:
            row_ts = row_ts.replace(tzinfo=timezone.utc)
        if row_ts < normalized_since:
            return False
    return True


def _derive_correlation_health(events: list[dict]) -> CorrelationHealth:
    """Walk every event's `details` dict and report which correlation keys
    are present at least once.  Order of the `missing_keys` list is stable
    (it follows `CORRELATION_KEYS`) so snapshot tests do not flake.
    """
    found: set[str] = set()
    for event in events:
        details = event.get("details") or {}
        if not isinstance(details, dict):
            continue
        for key in CORRELATION_KEYS:
            if key in details and details[key]:
                found.add(key)
    missing = [k for k in CORRELATION_KEYS if k not in found]
    return CorrelationHealth(
        has_trace_id="trace_id" in found,
        has_user_id="user_id" in found,
        has_task_id="task_id" in found,
        has_agent_id="agent_id" in found,
        missing_keys=missing,
    )
