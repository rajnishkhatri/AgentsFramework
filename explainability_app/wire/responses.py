"""Pydantic response shapes for the explainability API.

These are the wire-level contracts consumed by the frontend Zod mirrors.
The `__python_schema_baseline__.json` file in the frontend mirrors a
JSON-Schema export of every shape defined here; baseline_drift tests fail
on any unsynchronised change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class WorkflowSummaryResponse(BaseModel):
    workflow_id: str
    started_at: datetime | None = None
    event_count: int = 0
    status: str = "unknown"
    primary_agent_id: str | None = None


class BlackBoxEventResponse(BaseModel):
    event_id: str
    workflow_id: str
    event_type: str
    timestamp: datetime | None = None
    step: int | None = None
    details: dict[str, Any] = {}
    integrity_hash: str = ""


class WorkflowEventsResponse(BaseModel):
    workflow_id: str
    event_count: int = 0
    hash_chain_valid: bool = False
    events: list[BlackBoxEventResponse] = []


class DecisionRecordResponse(BaseModel):
    workflow_id: str
    phase: str
    description: str
    alternatives: list[str] = []
    rationale: str
    confidence: float
    timestamp: datetime | None = None


class TimeSeriesPointResponse(BaseModel):
    bucket: datetime
    value: float


class DashboardMetricsResponse(BaseModel):
    total_runs: int = 0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    guardrail_pass_rate: float = 0.0
    hash_chain_valid_count: int = 0
    hash_chain_invalid_count: int = 0
    time_series_cost: list[TimeSeriesPointResponse] = []
    time_series_latency: list[TimeSeriesPointResponse] = []
    time_series_tokens: list[TimeSeriesPointResponse] = []
    model_distribution: dict[str, int] = {}


class ValidatorStatResponse(BaseModel):
    name: str
    total_checks: int = 0
    pass_count: int = 0
    fail_count: int = 0
    pass_rate: float = 0.0


class GuardrailFailureResponse(BaseModel):
    workflow_id: str
    validator: str
    fail_action: str | None = None
    timestamp: datetime | None = None


class GuardrailSummaryResponse(BaseModel):
    total_checks: int = 0
    pass_count: int = 0
    fail_count: int = 0
    pass_rate: float = 0.0
    fail_action_distribution: dict[str, int] = {}
    per_validator: list[ValidatorStatResponse] = []
    recent_failures: list[GuardrailFailureResponse] = []
    trend_pass_rate_delta: float = 0.0


class CapabilityResponse(BaseModel):
    name: str
    description: str = ""
    parameters: dict[str, Any] = {}


class PolicyResponse(BaseModel):
    name: str
    description: str = ""
    rules: dict[str, Any] = {}


class AgentCardResponse(BaseModel):
    """Wire shape for the read-only Agent Registry card.

    ``signature_verification_status`` distinguishes the three trust signals
    (``verified``, ``failed``, ``unavailable``); ``signature_verified`` is
    retained as a convenience boolean (``True`` only for ``verified``) so
    older clients keep working while the UI migrates to the richer status
    string.
    """

    agent_id: str
    agent_name: str
    owner: str
    version: str
    description: str = ""
    capabilities: list[CapabilityResponse] = []
    policies: list[PolicyResponse] = []
    status: str
    valid_until: datetime | None = None
    parent_agent_id: str | None = None
    signature_truncated: str
    signature_verified: bool
    signature_verification_status: str = "unavailable"
    created_at: datetime
    updated_at: datetime


class AgentAuditEntryResponse(BaseModel):
    agent_id: str
    action: str
    performed_by: str
    timestamp: datetime
    details: dict[str, Any] = {}


class IntegrityReportResponse(BaseModel):
    """S3.1.1 wire shape: chain-integrity result for a single workflow."""

    workflow_id: str
    chain_valid: bool
    broken_at_event_id: str | None = None
    expected_hash: str | None = None
    actual_hash: str | None = None


class CorrelationHealthResponse(BaseModel):
    """S3.1.2 wire shape: explicit per-key correlation status.

    `missing_keys` is the convenience list consumed by the Compliance UI's
    "missing keys named explicitly" card.
    """

    has_trace_id: bool
    has_user_id: bool
    has_task_id: bool
    has_agent_id: bool
    missing_keys: list[str] = []


class ComplianceBundleResponse(BaseModel):
    """S3.1.2 wire shape: four-pillar compliance bundle for a workflow.

    The ``integrity`` field embeds the full `IntegrityReportResponse` so the
    Workflow Deep Dive's Recording quadrant can name the broken event id
    plus the expected/actual hashes (Sprint 3 review F4).
    """

    workflow_id: str
    event_count: int = 0
    hash_chain_valid: bool = False
    bundle_type: str = "compliance_audit"
    exported_at: datetime | None = None
    events: list[BlackBoxEventResponse] = []
    identity_cards: dict[str, AgentCardResponse | None] = {}
    audit_trails: dict[str, list[AgentAuditEntryResponse]] = {}
    phase_decisions: list[DecisionRecordResponse] = []
    correlation_health: CorrelationHealthResponse
    integrity: IntegrityReportResponse


class WorkflowIntegritySummaryResponse(BaseModel):
    """One row in the batched compliance summary.

    Pairs a workflow summary with its integrity report (or ``None`` when
    the workflow could not be read).  See `ComplianceSummaryResponse`.
    """

    workflow: WorkflowSummaryResponse
    integrity: IntegrityReportResponse | None = None


class ComplianceSummaryResponse(BaseModel):
    """Batched compliance home payload (Sprint 3 review F3 fix).

    Replaces the previous per-workflow integrity fan-out: one call returns
    every workflow + integrity row, plus the bounds the server actually
    applied (so the UI can render the audit window verbatim).
    """

    rows: list[WorkflowIntegritySummaryResponse] = []
    generated_at: datetime
    since: datetime | None = None
    until: datetime | None = None


class LogRowResponse(BaseModel):
    """S4.3.1 wire shape: a single parsed log line.

    `level="UNKNOWN"` when the formatter pattern did not match -- the raw line
    is preserved in `raw` and `message` so the operator can still see the
    bytes that hit disk.
    """

    concern: str
    timestamp: datetime | None = None
    logger: str = ""
    level: str = "UNKNOWN"
    message: str = ""
    raw: str = ""


class HealthResponse(BaseModel):
    status: str = "ok"


class ErrorResponse(BaseModel):
    detail: str
