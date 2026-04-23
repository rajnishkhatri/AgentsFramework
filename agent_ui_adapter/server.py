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
from typing import AsyncIterator, Protocol, runtime_checkable

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

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
    RunCreateRequest,
    RunStateView,
    ThreadCreateRequest,
    ThreadState,
)
from trust.models import AgentFacts

logger = logging.getLogger("agent_ui_adapter.server")

ADAPTER_VERSION = "0.1.0"


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
    def __init__(self) -> None:
        self._threads: dict[str, ThreadState] = {}

    def create(self, user_id: str, metadata: dict) -> ThreadState:
        thread_id = uuid.uuid4().hex
        now = datetime.now(UTC)
        state = ThreadState(
            thread_id=thread_id,
            user_id=user_id,
            messages=[],
            created_at=now,
            updated_at=now,
        )
        self._threads[thread_id] = state
        return state

    def get(self, thread_id: str) -> ThreadState | None:
        return self._threads.get(thread_id)


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
) -> FastAPI:
    """Wire FastAPI app from a runtime + JWT verifier + identity registry.

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
        return identity

    # ── routes ──────────────────────────────────────────────────────

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse(status="ok", adapter_version=ADAPTER_VERSION)

    @app.post("/agent/threads", response_model=ThreadState)
    async def create_thread(
        body: ThreadCreateRequest,
        identity: AgentFacts = Depends(_verify_bearer),
    ) -> ThreadState:
        return threads.create(user_id=body.user_id, metadata=body.metadata)

    @app.get("/agent/threads/{thread_id}", response_model=ThreadState)
    async def get_thread(
        thread_id: str,
        identity: AgentFacts = Depends(_verify_bearer),
    ) -> ThreadState:
        state = threads.get(thread_id)
        if state is None:
            raise HTTPException(status_code=404, detail="thread not found")
        return state

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
        run_id = uuid.uuid4().hex
        run_started_at = time.monotonic()

        async def _generate() -> AsyncIterator[bytes]:
            trace_id_seen: str | None = None
            errored = False
            try:
                runs.started(run_id, body.thread_id)
                logger.info(
                    "stream_started run_id=%s thread_id=%s identity=%s",
                    run_id,
                    body.thread_id,
                    identity.agent_id,
                )
                async for domain_event in runtime.run(
                    thread_id=body.thread_id,
                    input=body.input,
                    identity=identity,
                ):
                    if trace_id_seen is None:
                        trace_id_seen = domain_event.trace_id
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

    return app


__all__ = [
    "ADAPTER_VERSION",
    "InMemoryJwtVerifier",
    "JwtClaims",
    "JwtVerifier",
    "build_app",
]
