"""FastAPI composition root for the explainability dashboard backend.

Binds to 127.0.0.1:8001. CORS allow-list: http://localhost:3001 only.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from explainability_app.wire.responses import (
    AgentAuditEntryResponse,
    AgentCardResponse,
    ComplianceBundleResponse,
    ComplianceSummaryResponse,
    DashboardMetricsResponse,
    DecisionRecordResponse,
    ErrorResponse,
    GuardrailSummaryResponse,
    HealthResponse,
    IntegrityReportResponse,
    LogRowResponse,
    WorkflowEventsResponse,
    WorkflowIntegritySummaryResponse,
    WorkflowSummaryResponse,
)
from services.explainability_service import (
    AgentNotFoundError,
    ExplainabilityService,
    WorkflowNotFoundError,
)
from services.governance.agent_facts_registry import AgentFactsRegistry

logger = logging.getLogger("explainability_app.server")

ALLOWED_ORIGINS = ["http://localhost:3001"]
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001


def build_app(service: ExplainabilityService | None = None) -> FastAPI:
    if service is None:
        agent_root = Path(__file__).resolve().parents[1]
        cache_dir = agent_root / "cache"
        agent_facts_registry = _try_build_agent_facts_registry(
            storage_dir=cache_dir / "agent_facts",
        )
        service = ExplainabilityService(
            recordings_dir=cache_dir / "black_box_recordings",
            phase_logs_dir=cache_dir / "phase_logs",
            agent_facts_registry=agent_facts_registry,
            logs_dir=agent_root / "logs",
        )

    app = FastAPI(title="Explainability Dashboard API", version="0.1.0")
    app.state.host = DEFAULT_HOST
    app.state.port = DEFAULT_PORT

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get(
        "/api/v1/workflows",
        response_model=list[WorkflowSummaryResponse],
        responses={500: {"model": ErrorResponse}},
    )
    async def list_workflows(
        since: datetime | None = Query(None),
        until: datetime | None = Query(None),
    ) -> JSONResponse | list[WorkflowSummaryResponse]:
        try:
            summaries = service.list_workflows(since=since, until=until)
            return [
                WorkflowSummaryResponse(**s.model_dump()) for s in summaries
            ]
        except Exception:
            logger.exception("Failed to list workflows")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

    @app.get(
        "/api/v1/workflows/{wf_id}/events",
        response_model=WorkflowEventsResponse,
        responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    )
    async def get_workflow_events(wf_id: str) -> WorkflowEventsResponse:
        try:
            result = service.get_workflow_events(wf_id)
        except WorkflowNotFoundError:
            raise HTTPException(
                status_code=404, detail=f"Unknown workflow_id: {wf_id}"
            )
        return WorkflowEventsResponse(**result.model_dump())

    @app.get(
        "/api/v1/workflows/{wf_id}/decisions",
        response_model=list[DecisionRecordResponse],
        responses={500: {"model": ErrorResponse}},
    )
    async def get_workflow_decisions(wf_id: str) -> list[DecisionRecordResponse]:
        records = service.get_workflow_decisions(wf_id)
        return [DecisionRecordResponse(**r.model_dump()) for r in records]

    @app.get(
        "/api/v1/dashboard/metrics",
        response_model=DashboardMetricsResponse,
        responses={500: {"model": ErrorResponse}},
    )
    async def get_dashboard_metrics(
        since: datetime | None = Query(None),
        until: datetime | None = Query(None),
    ) -> DashboardMetricsResponse:
        metrics = service.get_dashboard_metrics(since=since, until=until)
        return DashboardMetricsResponse(**metrics.model_dump())

    @app.get(
        "/api/v1/guardrails/summary",
        response_model=GuardrailSummaryResponse,
        responses={500: {"model": ErrorResponse}},
    )
    async def get_guardrail_summary(
        since: datetime | None = Query(None),
        until: datetime | None = Query(None),
    ) -> JSONResponse | GuardrailSummaryResponse:
        try:
            summary = service.get_guardrail_summary(since=since, until=until)
        except Exception:
            logger.exception("Failed to compute guardrail summary")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )
        return GuardrailSummaryResponse(**summary.model_dump())

    @app.get(
        "/api/v1/workflows/{wf_id}/integrity",
        response_model=IntegrityReportResponse,
        responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    )
    async def get_workflow_integrity(wf_id: str) -> IntegrityReportResponse:
        try:
            report = service.get_workflow_integrity(wf_id)
        except WorkflowNotFoundError:
            raise HTTPException(
                status_code=404, detail=f"Unknown workflow_id: {wf_id}"
            )
        return IntegrityReportResponse(**report.model_dump())

    @app.get(
        "/api/v1/workflows/{wf_id}/compliance",
        response_model=ComplianceBundleResponse,
        responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    )
    async def get_workflow_compliance(wf_id: str) -> ComplianceBundleResponse:
        try:
            bundle = service.get_compliance_bundle(wf_id)
        except WorkflowNotFoundError:
            raise HTTPException(
                status_code=404, detail=f"Unknown workflow_id: {wf_id}"
            )
        return ComplianceBundleResponse(**bundle.model_dump())

    @app.get(
        "/api/v1/compliance/summary",
        response_model=ComplianceSummaryResponse,
        responses={500: {"model": ErrorResponse}},
    )
    async def get_compliance_summary(
        since: datetime | None = Query(None),
        until: datetime | None = Query(None),
    ) -> JSONResponse | ComplianceSummaryResponse:
        """Batched workflow + integrity rows for the Compliance home.

        Replaces the per-row N+1 fan-out (Sprint 3 review F3): the page
        used to call `getWorkflowIntegrity` once per workflow.
        """
        try:
            summary = service.list_workflow_integrity(since=since, until=until)
        except Exception:
            logger.exception("Failed to compute compliance summary")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )
        return ComplianceSummaryResponse(**summary.model_dump())

    @app.get(
        "/api/v1/logs",
        response_model=list[LogRowResponse],
        responses={500: {"model": ErrorResponse}},
    )
    async def query_logs(
        concerns: list[str] | None = Query(None),
        level: str | None = Query(None),
        search: str | None = Query(None),
        since: datetime | None = Query(None),
        limit: int = Query(500, ge=1, le=5000),
    ) -> JSONResponse | list[LogRowResponse]:
        try:
            rows = service.query_logs(
                concerns=concerns,
                level=level,
                search=search,
                since=since,
                limit=limit,
            )
        except Exception:
            logger.exception("Failed to query logs")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )
        return [LogRowResponse(**r.model_dump()) for r in rows]

    @app.get(
        "/api/v1/logs/stream",
        responses={500: {"model": ErrorResponse}},
    )
    async def stream_logs(
        request: Request,
        concerns: list[str] | None = Query(None),
        level: str | None = Query(None),
        search: str | None = Query(None),
    ) -> StreamingResponse:
        gen = service.tail_logs(
            concerns=concerns,
            level=level,
            search=search,
        )
        body = _sse_log_stream(gen, request=request)
        return StreamingResponse(
            body,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    app.include_router(_build_agents_router(service), prefix="/api/v1/agents")

    return app


# --- S4.3.2: SSE encoder + heartbeat for /api/v1/logs/stream ---

# Frame the rule X4 mirror server-side: emit a comment-line heartbeat every
# HEARTBEAT_SECONDS so an idle proxy keeps the connection alive.
HEARTBEAT_SECONDS: float = 15.0
# Cap the per-yield wait so a client disconnect is observed within
# DISCONNECT_POLL_SECONDS even when no log row is forthcoming.  Smaller =
# faster shutdown; larger = fewer wakeups on an idle stream.
DISCONNECT_POLL_SECONDS: float = 0.5


async def _sse_log_stream(
    source: AsyncIterator,
    *,
    request: Request,
) -> AsyncIterator[bytes]:
    """Wrap an async iterator of `LogRow` instances as an SSE byte stream.

    * Each row is serialised as `event: log` + `data: {json}` + blank line.
    * A `:heartbeat` comment frame fires every `HEARTBEAT_SECONDS` to keep the
      socket alive through proxies that timeout idle connections.
    * Client disconnect is polled every `DISCONNECT_POLL_SECONDS`; the handler
      aborts as soon as it observes `request.is_disconnected() is True`, then
      `aclose()`s the source via `contextlib.aclosing` so the underlying file
      handles never leak.
    * On any exception in the source, an `event: error` frame is emitted, the
      exception is swallowed, and the stream closes cleanly.
    """
    loop = asyncio.get_event_loop()
    last_heartbeat = loop.time()
    async with contextlib.aclosing(source) as gen:
        next_task: asyncio.Task | None = None
        try:
            while True:
                if await request.is_disconnected():
                    return
                if next_task is None:
                    next_task = asyncio.ensure_future(anext(gen))
                # Wait for either a new row or the disconnect poll interval.
                done, _ = await asyncio.wait(
                    {next_task},
                    timeout=DISCONNECT_POLL_SECONDS,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                now = loop.time()
                if next_task not in done:
                    if now - last_heartbeat >= HEARTBEAT_SECONDS:
                        yield b": heartbeat\n\n"
                        last_heartbeat = now
                    continue
                # next_task completed: extract the row or surface the error.
                try:
                    row = next_task.result()
                except StopAsyncIteration:
                    return
                except Exception as exc:  # noqa: BLE001 -- re-emit as SSE error
                    logger.exception("tail_logs raised: %s", exc)
                    payload = json.dumps(
                        {"message": str(exc) or exc.__class__.__name__},
                        separators=(",", ":"),
                    )
                    yield f"event: error\ndata: {payload}\n\n".encode("utf-8")
                    return
                finally:
                    next_task = None

                payload = row.model_dump_json()
                yield f"event: log\ndata: {payload}\n\n".encode("utf-8")
                if now - last_heartbeat >= HEARTBEAT_SECONDS:
                    yield b": heartbeat\n\n"
                    last_heartbeat = now
        finally:
            if next_task is not None and not next_task.done():
                next_task.cancel()
                with contextlib.suppress(BaseException):
                    await next_task


def _try_build_agent_facts_registry(
    storage_dir: Path,
) -> AgentFactsRegistry | None:
    """Build an `AgentFactsRegistry` for the dashboard's read views.

    Resolution order:
      1. `AGENT_FACTS_SECRET` env var (production / share-with-runtime).
      2. The dev-seed secret (only when the dev_seed-created storage dir
         exists; otherwise we'd be wiring an empty registry with a fake key).
      3. Return None and let `ExplainabilityService.list_agents` return [].

    Failing closed (returning None) is intentional: the dashboard is a
    read-only viewer; without a secret we cannot verify signatures, so the
    Agent Registry section degrades to an empty state instead of asserting
    against unverified facts.
    """
    import os

    secret = os.environ.get("AGENT_FACTS_SECRET")
    if not secret and storage_dir.exists():
        from explainability_app.dev_seed import DEV_SEED_AGENT_FACTS_SECRET

        secret = DEV_SEED_AGENT_FACTS_SECRET
    if not secret:
        return None
    try:
        return AgentFactsRegistry(storage_dir=storage_dir, secret=secret)
    except Exception:
        logger.warning(
            "Unable to wire AgentFactsRegistry at %s; agent registry views "
            "will report an empty list.",
            storage_dir,
            exc_info=True,
        )
        return None


def _build_agents_router(service: ExplainabilityService) -> APIRouter:
    """Build the read-only Agent Registry router (S2.2.1, F-R6).

    F-R6: only GET methods are mounted. POST / PUT / PATCH / DELETE on this
    sub-router are intentionally absent so the framework returns 405. The
    architecture test `tests/architecture/test_agents_router_read_only.py`
    asserts this property by reflecting on `router.routes`.
    """
    router = APIRouter()

    @router.get(
        "",
        response_model=list[AgentCardResponse],
        responses={500: {"model": ErrorResponse}},
    )
    async def list_agents() -> list[AgentCardResponse]:
        cards = service.list_agents()
        return [AgentCardResponse(**c.model_dump()) for c in cards]

    @router.get(
        "/{agent_id}",
        response_model=AgentCardResponse,
        responses={
            404: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
    )
    async def get_agent_card(agent_id: str) -> AgentCardResponse:
        try:
            card = service.get_agent_card(agent_id)
        except AgentNotFoundError:
            raise HTTPException(
                status_code=404, detail=f"Unknown agent_id: {agent_id}"
            )
        return AgentCardResponse(**card.model_dump())

    @router.get(
        "/{agent_id}/audit",
        response_model=list[AgentAuditEntryResponse],
        responses={
            404: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
    )
    async def get_agent_audit(agent_id: str) -> list[AgentAuditEntryResponse]:
        try:
            entries = service.get_agent_audit(agent_id)
        except AgentNotFoundError:
            raise HTTPException(
                status_code=404, detail=f"Unknown agent_id: {agent_id}"
            )
        return [AgentAuditEntryResponse(**e.model_dump()) for e in entries]

    return router
