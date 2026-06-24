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

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ThreadCreateRequest(BaseModel):
    """Body of ``POST /agent/threads``.

    ``thread_id`` is optional: when the client mints the conversation id (so the
    durable thread row keys by the SAME id the agent/checkpointer uses for
    resume), it supplies it here. Absent → the store mints its own id (the
    legacy path). A provisional title still flows via ``metadata.first_message``
    (see ``derive_thread_title``).
    """

    user_id: str
    thread_id: str | None = None
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ThreadState(BaseModel):
    """Response body of ``GET /agent/threads/{thread_id}`` and items in the
    ``GET /agent/threads`` list.

    ``title`` is the sidebar label (Phase 3) — deterministic from the first
    user message, user-renamable. ``archived_at`` is the soft-delete tombstone
    (set on archive; list/get filter it out).
    """

    thread_id: str
    user_id: str
    title: str = "New chat"
    messages: list[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class ThreadListResponse(BaseModel):
    """Response body of ``GET /agent/threads`` — the caller's own threads,
    cursor-paginated."""

    threads: list[ThreadState] = Field(default_factory=list)
    next_cursor: str | None = None

    model_config = ConfigDict(extra="forbid")


class ThreadRenameRequest(BaseModel):
    """Body of ``PATCH /agent/threads/{thread_id}`` — rename only."""

    title: str = Field(min_length=1, max_length=200)

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


class ModelInfo(BaseModel):
    """One selectable model on the wire — name + tier ONLY.

    Pricing (cost_per_1k_*), ``litellm_id``, and context windows are runtime
    catalog internals and are deliberately NOT exposed to the client (the model
    name is non-secret; the cost table is not a client concern). The dropdown
    needs only the name to pin and the tier to group/label.
    """

    name: str
    tier: str

    model_config = ConfigDict(extra="forbid")


class ModelsResponse(BaseModel):
    """Response body of ``GET /models`` — the model picker's catalog.

    ``default`` is the steady-state fast model name; ``models`` is the registry
    order (the router's first-match-per-tier contract). "Auto" is a UI sentinel,
    not a model — the client prepends it; the backend never lists it.
    """

    default: str
    models: list[ModelInfo]

    model_config = ConfigDict(extra="forbid")


__all__ = [
    "HealthResponse",
    "RunCreateRequest",
    "RunStateView",
    "ThreadCreateRequest",
    "ThreadState",
]


class TaskUnderstandingEditRequest(BaseModel):
    """Edit payload for the soft-gate understanding card (Phase 4).

    Wire shape consumed by the middleware edit endpoint — NEVER the
    components Pydantic type (M1: middleware never imports components/).
    Bounds mirror the components validation gates minus lexical grounding
    (``user_edited`` skips it: the human is the authority). ``trace_id``
    is echoed verbatim from the run (F-R7 — the browser never mints one).
    """

    model_config = ConfigDict(extra="forbid")

    trace_id: str = Field(min_length=1)
    restated_intent: str = Field(min_length=1, max_length=600)
    success_conditions: list[str] = Field(min_length=2, max_length=7)

    @field_validator("success_conditions")
    @classmethod
    def _bound_condition_lengths(cls, value: list[str]) -> list[str]:
        for index, condition in enumerate(value):
            stripped = condition.strip()
            if not stripped:
                raise ValueError(f"condition {index} is empty")
            if len(stripped) > 200:
                raise ValueError(
                    f"condition {index} is {len(stripped)} chars (max 200)"
                )
        return [c.strip() for c in value]


# ── Memory panel (Phase 3) ─────────────────────────────────────────────
#
# The memory PANEL is the one place a user sees their own stored memory
# CONTENT — this is by design (the visible/editable panel is the 2026 trust
# norm). The privacy invariant (no content in LOGS/CARRIERS) is unchanged:
# these wire models cross the authenticated BFF→middleware boundary scoped to
# the caller's own subject, never a log line. Every endpoint keys on
# identity.owner (the cross-user-leak guard), so a user can only ever read or
# mutate their own memory.

MemoryTypeLiteral = Literal["semantic", "episodic", "procedural"]


class MemoryItem(BaseModel):
    """One stored memory item, surfaced to its owner in the panel."""

    key: str
    type: MemoryTypeLiteral | None = None
    content: str
    salience: float | None = None

    model_config = ConfigDict(extra="forbid")


class MemoryListResponse(BaseModel):
    """Response body of ``GET /agent/memory`` — the caller's own items."""

    items: list[MemoryItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class MemoryCreateRequest(BaseModel):
    """Body of ``POST /agent/memory`` — a user-added (manual) memory.

    ``user_id`` is intentionally absent: the subject is the verified bearer
    identity, never client-supplied (cross-user-leak guard).
    """

    content: str = Field(min_length=1, max_length=2000)
    type: MemoryTypeLiteral = "semantic"
    key: str | None = Field(default=None, max_length=200)
    # Optional salience so a panel/manual add can mark importance (and the A3
    # provenance tiers can render). Absent → the record is stored unmarked
    # (the legacy/back-compat path). Bounded [0,1] like TypedMemory.salience.
    salience: float | None = Field(default=None, ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")


class MemorySuppressRequest(BaseModel):
    """Body of ``PATCH /agent/memory/{key}`` — soft-suppress / un-suppress one
    of the caller's own memories (chat-persistence Phase B, D5).

    ``suppressed=True`` (reject) stops the memory being recalled/injected while
    RETAINING the row for audit; ``False`` un-suppresses (reversible). The
    subject is the verified bearer identity, never client-supplied.
    """

    suppressed: bool

    model_config = ConfigDict(extra="forbid")
