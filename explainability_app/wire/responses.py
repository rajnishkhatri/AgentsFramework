"""Pydantic response shapes for the explainability API.

These are the wire-level contracts consumed by the frontend Zod mirrors.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WorkflowSummaryResponse(BaseModel):
    workflow_id: str
    started_at: datetime | None = None
    event_count: int = 0
    status: str = "unknown"
    primary_agent_id: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"


class ErrorResponse(BaseModel):
    detail: str
