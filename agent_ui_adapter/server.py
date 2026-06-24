"""FastAPI composition root for the agent-ui adapter.

Per AGENT_UI_ADAPTER_SPRINTS.md S6 (US-6.1 .. US-6.6) and
AGENT_UI_ADAPTER_PLAN.md §4 routes + §5.3 dual-PEP.

Composition: this module is the ONLY place where the adapter wires
horizontal services + the chosen `AgentRuntime` into the HTTP surface.
Per rule R8, route handlers compose service calls and translator calls
only at the boundary; no domain logic lives here.

The `JwtVerifier` Protocol is local to the composition root (NOT a port)
so rule R9 (single port = `AgentRuntime`) holds. Production wires a real
verifier (WorkOS / OAuth / Cognito) by passing it to `build_app`.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, AsyncIterator, Protocol, runtime_checkable

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from agent_ui_adapter.ports.agent_runtime import AgentRuntime
from agent_ui_adapter.translators.domain_to_ag_ui import to_ag_ui
from agent_ui_adapter.transport.sse import (
    PROXY_HEADERS,
    SENTINEL_LINE,
    encode_error,
    encode_event,
)
from agent_ui_adapter.wire.agent_protocol import (
    HealthResponse,
    MemoryCreateRequest,
    MemoryItem,
    MemoryListResponse,
    MemorySuppressRequest,
    ModelInfo,
    ModelsResponse,
    RunCreateRequest,
    RunStateView,
    ThreadCreateRequest,
    ThreadListResponse,
    ThreadRenameRequest,
    ThreadState,
)
from services.authorization_service import AuthorizationService
from services.long_term_memory import LongTermMemoryService
from services.trace_service import TraceService
from services.tools.registry import ToolRegistry
from trust.models import AgentFacts

logger = logging.getLogger("agent_ui_adapter.server")

ADAPTER_VERSION = "0.1.0"

_DEFAULT_THREAD_TITLE = "New chat"
_TITLE_MAX_LEN = 60


def _emit_crud_consolidation(
    recordings_dir: Path | None, owner: str, mem_type: str | None, outcome: Any
) -> None:
    """Emit a MEMORY_CONSOLIDATED carrier when a CRUD write overflowed the budget.

    A1 / P1 #6a: a panel/CRUD ``create_memory`` that evicts memory must leave a
    Validation-pillar carrier (a silent prune is the swallowed-failure the pillar
    forbids). No-op when nothing was pruned OR no recordings dir is wired (the
    lean test composition has no relay). Observability must never fail the request.
    """
    if recordings_dir is None or outcome is None:
        return
    if outcome.evicted == 0 and outcome.deduped == 0:
        return
    try:
        from services.governance.black_box import BlackBoxRecorder
        from services.governance.memory_consolidation_carrier import (
            emit_consolidation_carrier,
        )

        emit_consolidation_carrier(
            BlackBoxRecorder(recordings_dir),
            workflow_id=f"mem-crud-{uuid.uuid4().hex}",
            user_id=owner,
            mem_type=mem_type or "unknown",
            outcome=outcome,
        )
    except Exception:  # pragma: no cover - observability must never break CRUD
        logger.warning("memory.consolidated carrier emit failed", exc_info=True)


def _emit_suppressed_carrier(
    recordings_dir: Path | None,
    owner: str,
    key: str,
    *,
    suppressed: bool,
) -> None:
    """Emit a MEMORY_SUPPRESSED carrier after a soft-suppress PATCH.

    Phase B (chat-persistence reject): the analyzer scores C3/C4 from the trace,
    not the DOM. No-op when no recordings dir is wired (lean test composition).
    Observability must never fail the request.
    """
    if recordings_dir is None:
        return
    try:
        from services.governance.black_box import BlackBoxRecorder
        from services.governance.memory_suppressed_carrier import (
            emit_suppressed_carrier,
        )

        emit_suppressed_carrier(
            BlackBoxRecorder(recordings_dir),
            workflow_id=f"mem-suppress-{uuid.uuid4().hex}",
            user_id=owner,
            key=key,
            suppressed=suppressed,
        )
    except Exception:  # pragma: no cover - observability must never break CRUD
        logger.warning("memory.suppressed carrier emit failed", exc_info=True)


def derive_thread_title(first_message: str | None) -> str:
    """Deterministic sidebar title from the first user message (Phase 3).

    No LLM call — a truncated, whitespace-collapsed slice of the first turn,
    preferring a word boundary and appending an ellipsis when cut. Falls back
    to ``"New chat"`` for empty/blank/non-string input. An LLM auto-title is a
    later upgrade behind this same ``title`` field.
    """
    if not isinstance(first_message, str):
        return _DEFAULT_THREAD_TITLE
    collapsed = " ".join(first_message.split())
    if not collapsed:
        return _DEFAULT_THREAD_TITLE
    if len(collapsed) <= _TITLE_MAX_LEN:
        return collapsed
    # Truncate at a word boundary within the budget, then ellipsize.
    cut = collapsed[: _TITLE_MAX_LEN - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return f"{cut.rstrip()}…"


# ─────────────────────────────────────────────────────────────────────
# JWT verification — local composition-root abstraction (NOT a port).
# Tests use InMemoryJwtVerifier; production swaps in a real implementation.
# ─────────────────────────────────────────────────────────────────────


class JwtClaims(BaseModel):
    """Verified bearer-token claims. ``subject`` is the agent_id."""

    subject: str
    expires_at: datetime
    issuer: str | None = None

    model_config = ConfigDict(frozen=True)


@runtime_checkable
class JwtVerifier(Protocol):
    """Composition-root abstraction. NOT in agent_ui_adapter/ports/ (R9)."""

    def verify(self, token: str) -> JwtClaims:
        """Return claims for a valid token; raise ValueError otherwise."""
        ...


class InMemoryJwtVerifier:
    """Test-friendly verifier with a static token→claims map."""

    def __init__(self, token_to_claims: dict[str, JwtClaims]) -> None:
        self._map = dict(token_to_claims)

    def verify(self, token: str) -> JwtClaims:
        if token not in self._map:
            raise ValueError("invalid token")
        return self._map[token]


# ─────────────────────────────────────────────────────────────────────
# In-memory thread + run stores (placeholder for v1; swap with services)
# ─────────────────────────────────────────────────────────────────────


class _ThreadStore:
    """In-memory thread store (placeholder for the persistent store).

    Phase 3 sidebar surface: user-scoped ``list`` (newest-first, cursor),
    deterministic ``title`` from the first message, ``rename``, and ``archive``
    (soft-delete — ``archived_at`` set; list/get filter it out). The persistent
    Postgres/Drizzle store is a deferred swap behind this same shape.
    """

    def __init__(self) -> None:
        self._threads: dict[str, ThreadState] = {}
        # Insertion order for stable, newest-first pagination.
        self._order: list[str] = []

    def create(
        self, user_id: str, metadata: dict, *, thread_id: str | None = None
    ) -> ThreadState:
        # Honor a client-minted id (== the agent/checkpointer thread_id) so the
        # durable row keys by the id the resume path reads; otherwise mint one.
        thread_id = thread_id or uuid.uuid4().hex
        now = datetime.now(UTC)
        # Deterministic title from the first message if the caller supplied one
        # in metadata; otherwise the renamable default.
        first_message = metadata.get("first_message") if metadata else None
        title = derive_thread_title(first_message)
        state = ThreadState(
            thread_id=thread_id,
            user_id=user_id,
            title=title,
            messages=[],
            created_at=now,
            updated_at=now,
            archived_at=None,
        )
        self._threads[thread_id] = state
        self._order.append(thread_id)
        return state

    def get(self, thread_id: str, *, owner: str | None = None) -> ThreadState | None:
        state = self._threads.get(thread_id)
        if state is None or state.archived_at is not None:
            return None
        # Ownership scoping: not-found and not-owned are indistinguishable
        # (no existence oracle). ``owner=None`` preserves the legacy un-scoped
        # get for the existing get-by-id endpoint contract.
        if owner is not None and state.user_id != owner:
            return None
        return state

    def list(
        self, owner: str, *, cursor: str | None = None, limit: int = 20
    ) -> tuple[list[ThreadState], str | None]:
        """Newest-first page of the owner's non-archived threads."""
        visible = [
            self._threads[tid]
            for tid in reversed(self._order)
            if self._threads[tid].user_id == owner
            and self._threads[tid].archived_at is None
        ]
        start = 0
        if cursor:
            ids = [t.thread_id for t in visible]
            start = ids.index(cursor) + 1 if cursor in ids else len(visible)
        page = visible[start : start + limit]
        next_cursor = (
            page[-1].thread_id if page and start + limit < len(visible) else None
        )
        return page, next_cursor

    def rename(self, thread_id: str, owner: str, title: str) -> ThreadState | None:
        state = self.get(thread_id, owner=owner)
        if state is None:
            return None
        updated = state.model_copy(
            update={"title": title, "updated_at": datetime.now(UTC)}
        )
        self._threads[thread_id] = updated
        return updated

    def archive(self, thread_id: str, owner: str) -> bool:
        state = self.get(thread_id, owner=owner)
        if state is None:
            return False
        self._threads[thread_id] = state.model_copy(
            update={"archived_at": datetime.now(UTC)}
        )
        return True


class _RunRegistry:
    def __init__(self) -> None:
        self._runs: dict[str, RunStateView] = {}

    def started(self, run_id: str, thread_id: str) -> None:
        self._runs[run_id] = RunStateView(
            run_id=run_id,
            thread_id=thread_id,
            status="running",
            started_at=datetime.now(UTC),
            completed_at=None,
        )

    def finished(self, run_id: str, *, errored: bool = False) -> None:
        if run_id in self._runs:
            current = self._runs[run_id]
            self._runs[run_id] = current.model_copy(
                update={
                    "status": "errored" if errored else "completed",
                    "completed_at": datetime.now(UTC),
                }
            )

    def cancelled(self, run_id: str) -> None:
        if run_id in self._runs:
            self._runs[run_id] = self._runs[run_id].model_copy(
                update={"status": "cancelled", "completed_at": datetime.now(UTC)}
            )

    def get(self, run_id: str) -> RunStateView | None:
        return self._runs.get(run_id)


# ─────────────────────────────────────────────────────────────────────
# Composition root
# ─────────────────────────────────────────────────────────────────────


def build_app(
    *,
    runtime: AgentRuntime,
    jwt_verifier: JwtVerifier,
    agent_facts: dict[str, AgentFacts],
    authorization_service: AuthorizationService | None = None,
    trace_service: TraceService | None = None,
    long_term_memory: LongTermMemoryService | None = None,
    tool_registry: ToolRegistry | None = None,
    black_box_recordings_dir: Path | None = None,
) -> FastAPI:
    """Wire FastAPI app from a runtime + JWT verifier + horizontal services.

    Caller is responsible for choosing a runtime (LangGraphRuntime in prod,
    MockRuntime in tests) and a JwtVerifier (real WorkOS in prod, in-memory
    in tests).

    R8: route handlers below contain only orchestration glue — no domain
    logic. They call services + translator + transport at the boundary.
    R9: only one Protocol (AgentRuntime) is consumed from ports/; the
    JwtVerifier Protocol is local to this composition root.
    """
    app = FastAPI(title="Agent UI Adapter", version=ADAPTER_VERSION)
    threads = _ThreadStore()
    runs = _RunRegistry()

    def _verify_bearer(
        authorization: str | None = Header(default=None),
    ) -> AgentFacts:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        token = authorization[len("Bearer ") :].strip()
        try:
            claims = jwt_verifier.verify(token)
        except ValueError as exc:
            raise HTTPException(
                status_code=401, detail=f"invalid token: {exc}"
            ) from None
        if claims.expires_at < datetime.now(UTC):
            raise HTTPException(status_code=401, detail="token expired")
        identity = agent_facts.get(claims.subject)
        if identity is None:
            raise HTTPException(
                status_code=401, detail="unknown identity for subject"
            )
        if authorization_service is not None:
            preflight_trace_id = uuid.uuid4().hex
            decision = authorization_service.authorize(
                identity,
                "agent.session.start",
                {},
                trace_id=preflight_trace_id,
            )
            if not decision.allowed:
                raise HTTPException(
                    status_code=401, detail=decision.reason
                )
        return identity

    # ── routes ──────────────────────────────────────────────────────

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse(status="ok", adapter_version=ADAPTER_VERSION)

    @app.get("/models", response_model=ModelsResponse)
    async def list_models(
        identity: AgentFacts = Depends(_verify_bearer),
    ) -> ModelsResponse:
        """The model picker's catalog — auth-scoped like the other routes.

        Reads the H2-canonical registry (services/llm_config.py) for the active
        MODEL_PROFILE_SET — the same source the runtime wired, so the dropdown
        can never list a model Auto can't route. Exposes name+tier ONLY; the
        cost table / litellm ids stay server-side (ModelInfo enforces this).
        """
        import os

        from services.llm_config import build_model_registry

        models, default_model = build_model_registry(
            os.environ.get("MODEL_PROFILE_SET", "openai")
        )
        return ModelsResponse(
            default=default_model,
            models=[ModelInfo(name=m.name, tier=m.tier) for m in models],
        )

    @app.get("/agent/threads", response_model=ThreadListResponse)
    async def list_threads(
        cursor: str | None = None,
        limit: int = 20,
        identity: AgentFacts = Depends(_verify_bearer),
    ) -> ThreadListResponse:
        # Scoped to identity.owner (caller's own only — B6 / no cross-user
        # leak). Newest-first, cursor-paginated, archived hidden.
        bounded = max(1, min(100, limit))
        page, next_cursor = threads.list(
            identity.owner, cursor=cursor, limit=bounded
        )
        return ThreadListResponse(threads=page, next_cursor=next_cursor)

    @app.post("/agent/threads", response_model=ThreadState)
    async def create_thread(
        body: ThreadCreateRequest,
        identity: AgentFacts = Depends(_verify_bearer),
    ) -> ThreadState:
        return threads.create(
            user_id=body.user_id, metadata=body.metadata, thread_id=body.thread_id
        )

    @app.get("/agent/threads/{thread_id}", response_model=ThreadState)
    async def get_thread(
        thread_id: str,
        identity: AgentFacts = Depends(_verify_bearer),
    ) -> ThreadState:
        state = threads.get(thread_id)
        if state is None:
            raise HTTPException(status_code=404, detail="thread not found")
        return state

    @app.patch("/agent/threads/{thread_id}", response_model=ThreadState)
    async def rename_thread(
        thread_id: str,
        body: ThreadRenameRequest,
        identity: AgentFacts = Depends(_verify_bearer),
    ) -> ThreadState:
        # 404 covers both not-found and not-owned (no existence oracle).
        renamed = threads.rename(thread_id, identity.owner, body.title)
        if renamed is None:
            raise HTTPException(status_code=404, detail="thread not found")
        return renamed

    @app.delete("/agent/threads/{thread_id}")
    async def archive_thread(
        thread_id: str,
        identity: AgentFacts = Depends(_verify_bearer),
    ) -> dict:
        if not threads.archive(thread_id, identity.owner):
            raise HTTPException(status_code=404, detail="thread not found")
        return {"archived": thread_id}

    @app.get("/agent/runs/{run_id}", response_model=RunStateView)
    async def get_run(
        run_id: str,
        identity: AgentFacts = Depends(_verify_bearer),
    ) -> RunStateView:
        view = runs.get(run_id)
        if view is None:
            raise HTTPException(status_code=404, detail="run not found")
        return view

    @app.delete("/agent/runs/{run_id}")
    async def cancel_run(
        run_id: str,
        identity: AgentFacts = Depends(_verify_bearer),
    ) -> dict:
        await runtime.cancel(run_id=run_id)
        runs.cancelled(run_id)
        return {"cancelled": run_id}

    @app.post("/agent/runs/stream")
    async def stream_run(
        body: RunCreateRequest,
        identity: AgentFacts = Depends(_verify_bearer),
    ) -> StreamingResponse:
        run_started_at = time.monotonic()

        async def _generate() -> AsyncIterator[bytes]:
            run_id: str | None = None
            trace_id_seen: str | None = None
            errored = False
            try:
                async for domain_event in runtime.run(
                    thread_id=body.thread_id,
                    input=body.input,
                    identity=identity,
                ):
                    if trace_id_seen is None:
                        trace_id_seen = domain_event.trace_id
                    if run_id is None and hasattr(domain_event, "run_id"):
                        run_id = domain_event.run_id
                        runs.started(run_id, body.thread_id)
                        logger.info(
                            "stream_started run_id=%s thread_id=%s "
                            "trace_id=%s identity=%s",
                            run_id,
                            body.thread_id,
                            trace_id_seen,
                            identity.agent_id,
                        )
                    for ag_ui_event in to_ag_ui(domain_event):
                        yield encode_event(
                            ag_ui_event,
                            event_id=uuid.uuid4().hex,
                        )
                yield SENTINEL_LINE
            except Exception as exc:
                errored = True
                logger.exception(
                    "stream_error run_id=%s thread_id=%s trace_id=%s err=%s",
                    run_id,
                    body.thread_id,
                    trace_id_seen,
                    exc,
                )
                yield encode_error(
                    f"{type(exc).__name__}: {exc}", code="runtime_error"
                )
                yield SENTINEL_LINE
            finally:
                if run_id is not None:
                    runs.finished(run_id, errored=errored)
                duration_ms = int((time.monotonic() - run_started_at) * 1000)
                logger.info(
                    "stream_ended run_id=%s thread_id=%s trace_id=%s "
                    "duration_ms=%d errored=%s",
                    run_id,
                    body.thread_id,
                    trace_id_seen,
                    duration_ms,
                    errored,
                )

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers=PROXY_HEADERS,
        )

    # ── Memory panel (Phase 3) ───────────────────────────────────────
    #
    # Every memory route is scoped to ``identity.owner`` — the verified
    # bearer subject's owner — NEVER a client-supplied user_id. This IS the
    # cross-user-leak guard: a caller can only ever read or mutate their own
    # memory. Returns 503 (not 500) when the long-term-memory service was not
    # wired, so the panel degrades to "unavailable" cleanly.

    def _require_memory() -> LongTermMemoryService:
        if long_term_memory is None:
            raise HTTPException(
                status_code=503, detail="memory service not available"
            )
        return long_term_memory

    @app.get("/agent/memory", response_model=MemoryListResponse)
    async def list_memory(
        identity: AgentFacts = Depends(_verify_bearer),
    ) -> MemoryListResponse:
        memory = _require_memory()
        records = memory.list_all(identity.owner, limit=500)
        items = [
            MemoryItem(
                key=r.key,
                type=r.metadata.get("type"),
                content=str(r.payload.get("text", "")),
                salience=r.metadata.get("salience"),
            )
            for r in records
        ]
        return MemoryListResponse(items=items)

    @app.post("/agent/memory", response_model=MemoryItem)
    async def create_memory(
        body: MemoryCreateRequest,
        identity: AgentFacts = Depends(_verify_bearer),
    ) -> MemoryItem:
        memory = _require_memory()
        key = body.key or uuid.uuid4().hex
        meta = {"type": body.type, "source": "user_added"}
        # Persist salience only when provided (A3): a record with no salience
        # renders unmarked. store() consolidates the type on budget overflow.
        if body.salience is not None:
            meta["salience"] = body.salience
        outcome = memory.store(identity.owner, key, {"text": body.content}, metadata=meta)
        # A1 / P1 #6a: a CRUD write that overflowed the budget pruned memory —
        # leave the MEMORY_CONSOLIDATED carrier so the eviction is not silent
        # (Validation pillar). No-op when nothing was pruned or no recordings dir
        # is wired (the lean test composition). See app_prod._emit_crud_consolidation.
        _emit_crud_consolidation(
            black_box_recordings_dir, identity.owner, body.type, outcome
        )
        return MemoryItem(
            key=key, type=body.type, content=body.content, salience=body.salience
        )

    @app.delete("/agent/memory/{key}")
    async def delete_memory(
        key: str,
        identity: AgentFacts = Depends(_verify_bearer),
    ) -> dict:
        memory = _require_memory()
        removed = memory.forget(identity.owner, key)
        if not removed:
            raise HTTPException(status_code=404, detail="memory not found")
        return {"deleted": key}

    @app.patch("/agent/memory/{key}", status_code=204)
    async def suppress_memory(
        key: str,
        body: MemorySuppressRequest,
        identity: AgentFacts = Depends(_verify_bearer),
    ) -> Response:
        # Phase B (D5): reject = soft-suppress globally. The record stops being
        # recalled/injected but the row is RETAINED (audit); un-suppress
        # restores. Scoped to the verified bearer identity (cross-user guard).
        memory = _require_memory()
        existed = memory.suppress(
            identity.owner, key, suppressed=body.suppressed
        )
        if not existed:
            raise HTTPException(status_code=404, detail="memory not found")
        _emit_suppressed_carrier(
            black_box_recordings_dir,
            identity.owner,
            key,
            suppressed=body.suppressed,
        )
        return Response(status_code=204)

    return app


__all__ = [
    "ADAPTER_VERSION",
    "AuthorizationService",
    "InMemoryJwtVerifier",
    "JwtClaims",
    "JwtVerifier",
    "LongTermMemoryService",
    "ToolRegistry",
    "TraceService",
    "build_app",
]
