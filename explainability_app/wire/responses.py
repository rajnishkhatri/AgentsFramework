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


class HealthResponse(BaseModel):
    status: str = "ok"


class ErrorResponse(BaseModel):
    detail: str
