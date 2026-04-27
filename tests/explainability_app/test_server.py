"""Tests for explainability_app/server.py -- failure-paths-first.

Uses httpx.AsyncClient(app=build_app(service=stub)).
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from explainability_app.server import DEFAULT_HOST, build_app
from services.explainability_service import (
    BlackBoxEventRecord,
    DashboardMetrics,
    DecisionRecord,
    ExplainabilityService,
    TimeSeriesPoint,
    WorkflowEvents,
    WorkflowNotFoundError,
    WorkflowSummary,
)


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
        assert resp.json() == {"detail": "Internal server error"}
        assert "Traceback" not in resp.text
        assert "Simulated service failure" not in resp.text


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


# --- S1.1.1: GET /api/v1/workflows/{wf_id}/events --- failure first


class _EventsStub:
    """Stub that returns a workflow with a tampered chain."""

    def get_workflow_events(self, workflow_id: str) -> WorkflowEvents:
        if workflow_id == "wf-missing":
            raise WorkflowNotFoundError(workflow_id)
        return WorkflowEvents(
            workflow_id=workflow_id,
            event_count=2,
            hash_chain_valid=workflow_id != "wf-tampered",
            events=[
                BlackBoxEventRecord(
                    event_id="e1",
                    workflow_id=workflow_id,
                    event_type="task_started",
                    timestamp=datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC),
                    integrity_hash="h1",
                ),
                BlackBoxEventRecord(
                    event_id="e2",
                    workflow_id=workflow_id,
                    event_type="task_completed",
                    timestamp=datetime(2026, 4, 26, 8, 0, 1, tzinfo=UTC),
                    integrity_hash="h2",
                ),
            ],
        )


@pytest.mark.asyncio
async def test_get_events_returns_404_for_unknown_workflow() -> None:
    app = build_app(service=_EventsStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/workflows/wf-missing/events")
        assert resp.status_code == 404
        assert "wf-missing" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_events_reports_chain_invalid_when_tampered() -> None:
    app = build_app(service=_EventsStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/workflows/wf-tampered/events")
        assert resp.status_code == 200
        body = resp.json()
        assert body["hash_chain_valid"] is False
        assert body["event_count"] == 2


@pytest.mark.asyncio
async def test_get_events_happy_path() -> None:
    app = build_app(service=_EventsStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/workflows/wf-good/events")
        assert resp.status_code == 200
        body = resp.json()
        assert body["workflow_id"] == "wf-good"
        assert body["hash_chain_valid"] is True
        assert body["event_count"] == 2
        assert len(body["events"]) == 2
        assert body["events"][0]["event_type"] == "task_started"
        assert body["events"][-1]["event_type"] == "task_completed"


# --- S1.2.1: GET /api/v1/workflows/{wf_id}/decisions --- failure first


class _DecisionsStub:
    def get_workflow_decisions(self, workflow_id: str) -> list[DecisionRecord]:
        if workflow_id == "wf-empty":
            return []
        return [
            DecisionRecord(
                workflow_id=workflow_id,
                phase="routing",
                description="picked gpt-4o",
                alternatives=["gpt-4o-mini"],
                rationale="capable",
                confidence=0.85,
                timestamp=datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC),
            ),
            DecisionRecord(
                workflow_id=workflow_id,
                phase="evaluation",
                description="continue",
                alternatives=["retry", "escalate"],
                rationale="no errors",
                confidence=0.95,
                timestamp=datetime(2026, 4, 26, 8, 0, 5, tzinfo=UTC),
            ),
        ]


@pytest.mark.asyncio
async def test_get_decisions_empty_workflow_returns_200_empty_list() -> None:
    """Failure-first: empty decisions returns 200 [], NOT 404."""
    app = build_app(service=_DecisionsStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/workflows/wf-empty/decisions")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
async def test_get_decisions_happy_path_returns_chronological() -> None:
    app = build_app(service=_DecisionsStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/workflows/wf-x/decisions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["phase"] == "routing"
        assert body[0]["confidence"] == 0.85
        assert body[1]["phase"] == "evaluation"
        assert body[1]["timestamp"] > body[0]["timestamp"]


# --- S1.3.1: GET /api/v1/dashboard/metrics --- failure first


class _DashboardStub:
    def get_dashboard_metrics(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> DashboardMetrics:
        if since is not None and until is not None and since == until:
            return DashboardMetrics()
        return DashboardMetrics(
            total_runs=3,
            p50_latency_ms=2000.0,
            p95_latency_ms=2900.0,
            total_cost_usd=0.006,
            guardrail_pass_rate=1.0,
            hash_chain_valid_count=3,
            hash_chain_invalid_count=0,
            time_series_cost=[
                TimeSeriesPoint(
                    bucket=datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC), value=0.001
                ),
                TimeSeriesPoint(
                    bucket=datetime(2026, 4, 26, 9, 0, 0, tzinfo=UTC), value=0.002
                ),
            ],
            time_series_latency=[],
            time_series_tokens=[],
            model_distribution={"gpt-4o": 2, "claude-3-opus": 1},
        )


@pytest.mark.asyncio
async def test_dashboard_metrics_empty_range_returns_200_all_zero() -> None:
    """Failure-first: an empty range yields the all-zero structure, NOT 404."""
    app = build_app(service=_DashboardStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        ts = "2026-04-26T00:00:00+00:00"
        resp = await client.get(
            "/api/v1/dashboard/metrics",
            params={"since": ts, "until": ts},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_runs"] == 0
        assert body["total_cost_usd"] == 0.0
        assert body["model_distribution"] == {}


@pytest.mark.asyncio
async def test_dashboard_metrics_happy_path() -> None:
    app = build_app(service=_DashboardStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/dashboard/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_runs"] == 3
        assert body["p95_latency_ms"] == 2900.0
        assert body["model_distribution"] == {"gpt-4o": 2, "claude-3-opus": 1}
        assert len(body["time_series_cost"]) == 2
