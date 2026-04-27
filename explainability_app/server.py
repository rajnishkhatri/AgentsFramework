"""FastAPI composition root for the explainability dashboard backend.

Binds to 127.0.0.1:8001. CORS allow-list: http://localhost:3001 only.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from explainability_app.wire.responses import (
    ErrorResponse,
    HealthResponse,
    WorkflowSummaryResponse,
)
from services.explainability_service import ExplainabilityService

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

    return app
