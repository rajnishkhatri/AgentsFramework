"""FastAPI composition root for the explainability dashboard backend.

Binds to 127.0.0.1:8001. CORS allow-list: http://localhost:3001 only.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from explainability_app.wire.responses import (
    DashboardMetricsResponse,
    DecisionRecordResponse,
    ErrorResponse,
    HealthResponse,
    WorkflowEventsResponse,
    WorkflowSummaryResponse,
)
from services.explainability_service import (
    ExplainabilityService,
    WorkflowNotFoundError,
)

logger = logging.getLogger("explainability_app.server")

ALLOWED_ORIGINS = ["http://localhost:3001"]
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001


def build_app(service: ExplainabilityService | None = None) -> FastAPI:
    if service is None:
        cache_dir = Path(__file__).resolve().parents[1] / "cache"
        service = ExplainabilityService(
            recordings_dir=cache_dir / "black_box_recordings",
            phase_logs_dir=cache_dir / "phase_logs",
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
    async def list_workflows() -> JSONResponse | list[WorkflowSummaryResponse]:
        try:
            summaries = service.list_workflows()
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

    return app
