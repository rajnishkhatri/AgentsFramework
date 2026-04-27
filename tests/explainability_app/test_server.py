"""Tests for explainability_app/server.py -- failure-paths-first.

Uses httpx.AsyncClient(app=build_app(service=stub)).
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from explainability_app.server import DEFAULT_HOST, build_app
from services.explainability_service import ExplainabilityService, WorkflowSummary


class _ErrorStub:
    """Stub that raises RuntimeError on every call."""

    def list_workflows(self, since=None):
        raise RuntimeError("Simulated service failure")


class _EmptyStub:
    """Stub that returns empty results."""

    def list_workflows(self, since=None):
        return []


class _SeededStub:
    """Stub that returns pre-defined workflow summaries."""

    def list_workflows(self, since=None):
        return [
            WorkflowSummary(
                workflow_id="wf-abc",
                started_at=datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC),
                event_count=5,
                status="completed",
                primary_agent_id="cli-agent",
            ),
            WorkflowSummary(
                workflow_id="wf-def",
                started_at=datetime(2026, 4, 25, 8, 0, 0, tzinfo=UTC),
                event_count=3,
                status="in_progress",
                primary_agent_id=None,
            ),
        ]


# --- Failure paths first ---


@pytest.mark.asyncio
async def test_workflows_returns_500_on_service_error() -> None:
    app = build_app(service=_ErrorStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/workflows")
        assert resp.status_code == 500


@pytest.mark.asyncio
async def test_cors_blocks_other_origins() -> None:
    app = build_app(service=_EmptyStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.options(
            "/api/v1/workflows",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        acl_origin = resp.headers.get("access-control-allow-origin")
        assert acl_origin != "http://localhost:3000", (
            "CORS should reject http://localhost:3000"
        )


@pytest.mark.asyncio
async def test_cors_allows_explainability_origin() -> None:
    app = build_app(service=_EmptyStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/workflows",
            headers={"Origin": "http://localhost:3001"},
        )
        acl_origin = resp.headers.get("access-control-allow-origin")
        assert acl_origin == "http://localhost:3001"


def test_server_binds_loopback_only() -> None:
    app = build_app(service=_EmptyStub())
    assert app.state.host == "127.0.0.1"


# --- Acceptance paths ---


@pytest.mark.asyncio
async def test_healthz_returns_ok() -> None:
    app = build_app(service=_EmptyStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_workflows_returns_seeded_summaries() -> None:
    app = build_app(service=_SeededStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["workflow_id"] == "wf-abc"
        assert data[0]["event_count"] == 5
        assert data[0]["status"] == "completed"
        assert data[0]["primary_agent_id"] == "cli-agent"
        assert data[1]["workflow_id"] == "wf-def"


@pytest.mark.asyncio
async def test_workflows_empty_returns_empty_list() -> None:
    app = build_app(service=_EmptyStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/workflows")
        assert resp.status_code == 200
        assert resp.json() == []
