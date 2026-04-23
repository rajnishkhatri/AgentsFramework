"""LangChain Agent Protocol thread/run CRUD wire models.

Per AGENT_UI_ADAPTER_PLAN.md §4 (routes table). These models are the
request/response shapes for the FastAPI server (S6) and feed the OpenAPI
export pipeline (US-2.4 / US-8.1).

Pure Pydantic v2; ``extra='forbid'`` so unknown fields fail closed. Not
``frozen`` because these are wire payloads handled by request/response
machinery, not domain types.

Per rule R4 (plan §8), this module imports only from stdlib + pydantic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ThreadCreateRequest(BaseModel):
    """Body of ``POST /agent/threads``."""

    user_id: str
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ThreadState(BaseModel):
    """Response body of ``GET /agent/threads/{thread_id}``."""

    thread_id: str
    user_id: str
    messages: list[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(extra="forbid")


class RunCreateRequest(BaseModel):
    """Body of ``POST /agent/runs/stream`` and ``POST /agent/runs``."""

    thread_id: str
    input: dict
    agent_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class RunStateView(BaseModel):
    """Response body of ``GET /agent/runs/{run_id}``."""

    run_id: str
    thread_id: str
    status: Literal["running", "completed", "cancelled", "errored"]
    started_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(extra="forbid")


class HealthResponse(BaseModel):
    """Response body of ``GET /healthz``."""

    status: Literal["ok"]
    adapter_version: str

    model_config = ConfigDict(extra="forbid")


__all__ = [
    "HealthResponse",
    "RunCreateRequest",
    "RunStateView",
    "ThreadCreateRequest",
    "ThreadState",
]
