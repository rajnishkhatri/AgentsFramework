"""Tests for explainability_app/server.py -- failure-paths-first.

Uses httpx.AsyncClient(app=build_app(service=stub)).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from explainability_app.server import DEFAULT_HOST, build_app
from services.explainability_service import (
    AgentAuditEntry,
    AgentCard,
    AgentNotFoundError,
    BlackBoxEventRecord,
    ComplianceBundle,
    CorrelationHealth,
    DashboardMetrics,
    DecisionRecord,
    ExplainabilityService,
    GuardrailFailure,
    GuardrailSummary,
    IntegrityReport,
    LogRow,
    TimeSeriesPoint,
    ValidatorStat,
    WorkflowEvents,
    WorkflowNotFoundError,
    WorkflowSummary,
)
from trust.models import Capability, Policy


class _ErrorStub:
    """Stub that raises RuntimeError on every call."""

    def list_workflows(self, since=None, until=None):
        raise RuntimeError("Simulated service failure")


class _EmptyStub:
    """Stub that returns empty results."""

    def list_workflows(self, since=None, until=None):
        return []


class _SeededStub:
    """Stub that returns pre-defined workflow summaries."""

    def __init__(self) -> None:
        self.last_kwargs: dict | None = None

    def list_workflows(self, since=None, until=None):
        self.last_kwargs = {"since": since, "until": until}
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


@pytest.mark.asyncio
async def test_workflows_forwards_since_and_until_to_service() -> None:
    """Phase 1 contract correction: /api/v1/workflows MUST accept
    `since` and `until` query params and pass them to the service.

    Frontend `HttpExplainabilityClient.listWorkflows(since, until)` already
    sends both; without backend forwarding the audit window is silently
    ignored.
    """
    stub = _SeededStub()
    app = build_app(service=stub)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/workflows",
            params={
                "since": "2026-04-01T00:00:00+00:00",
                "until": "2026-05-01T00:00:00+00:00",
            },
        )
        assert resp.status_code == 200

    assert stub.last_kwargs is not None
    assert stub.last_kwargs["since"] == datetime(2026, 4, 1, tzinfo=UTC)
    assert stub.last_kwargs["until"] == datetime(2026, 5, 1, tzinfo=UTC)


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


# --- S2.1.1: GET /api/v1/guardrails/summary --- failure first


class _GuardrailStub:
    def get_guardrail_summary(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        recent_failures_limit: int = 25,
    ) -> GuardrailSummary:
        if since is not None and until is not None and since == until:
            return GuardrailSummary()
        return GuardrailSummary(
            total_checks=4,
            pass_count=3,
            fail_count=1,
            pass_rate=0.75,
            fail_action_distribution={"reject": 1},
            per_validator=[
                ValidatorStat(
                    name="prompt_injection",
                    total_checks=3,
                    pass_count=3,
                    fail_count=0,
                    pass_rate=1.0,
                ),
                ValidatorStat(
                    name="output_pii_scan",
                    total_checks=1,
                    pass_count=0,
                    fail_count=1,
                    pass_rate=0.0,
                ),
            ],
            recent_failures=[
                GuardrailFailure(
                    workflow_id="wf-bad",
                    validator="output_pii_scan",
                    fail_action="reject",
                    timestamp=datetime(2026, 4, 26, 9, 0, 0, tzinfo=UTC),
                ),
            ],
            trend_pass_rate_delta=0.05,
        )


@pytest.mark.asyncio
async def test_guardrail_summary_empty_range_returns_200_all_zero() -> None:
    """Failure-first: an empty range yields all-zero, NOT 404."""
    app = build_app(service=_GuardrailStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        ts = "2026-04-26T00:00:00+00:00"
        resp = await client.get(
            "/api/v1/guardrails/summary",
            params={"since": ts, "until": ts},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_checks"] == 0
        assert body["per_validator"] == []
        assert body["recent_failures"] == []


@pytest.mark.asyncio
async def test_guardrail_summary_returns_500_on_service_error() -> None:
    """Failure-first: stub raising an exception surfaces a structured 500 with no traceback."""

    class _ErrGuardStub:
        def get_guardrail_summary(self, **_kwargs):
            raise RuntimeError("boom guardrail")

    app = build_app(service=_ErrGuardStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/guardrails/summary")
        assert resp.status_code == 500
        assert resp.json() == {"detail": "Internal server error"}
        assert "boom guardrail" not in resp.text
        assert "Traceback" not in resp.text


@pytest.mark.asyncio
async def test_guardrail_summary_happy_path() -> None:
    app = build_app(service=_GuardrailStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/guardrails/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_checks"] == 4
        assert body["pass_rate"] == 0.75
        assert body["fail_action_distribution"] == {"reject": 1}
        assert {v["name"] for v in body["per_validator"]} == {
            "prompt_injection",
            "output_pii_scan",
        }
        assert body["recent_failures"][0]["workflow_id"] == "wf-bad"
        assert body["trend_pass_rate_delta"] == 0.05


# --- S2.2.1: Agent Registry endpoints --- failure first


def _make_agent_card(
    agent_id: str,
    *,
    status: str = "active",
    signature_verified: bool = True,
    signature_verification_status: str | None = None,
) -> AgentCard:
    if signature_verification_status is None:
        signature_verification_status = (
            "verified" if signature_verified else "failed"
        )
    return AgentCard(
        agent_id=agent_id,
        agent_name=f"{agent_id}-name",
        owner="ops",
        version="1.0",
        description="seed",
        capabilities=[Capability(name="shell.run")],
        policies=[Policy(name="never-rm-rf")],
        status=status,
        signature_truncated="aaaaaaaa…bbbbbbbb",
        signature_verified=signature_verified,
        signature_verification_status=signature_verification_status,
        created_at=datetime(2026, 4, 1, tzinfo=UTC),
        updated_at=datetime(2026, 4, 1, tzinfo=UTC),
    )


class _AgentStub:
    def list_agents(self) -> list[AgentCard]:
        return [
            _make_agent_card("cli-agent"),
            _make_agent_card(
                "suspended-agent", status="suspended", signature_verified=False
            ),
        ]

    def get_agent_card(self, agent_id: str) -> AgentCard:
        if agent_id == "missing":
            raise AgentNotFoundError(agent_id)
        return _make_agent_card(agent_id)

    def get_agent_audit(self, agent_id: str) -> list[AgentAuditEntry]:
        if agent_id == "missing":
            raise AgentNotFoundError(agent_id)
        return [
            AgentAuditEntry(
                agent_id=agent_id,
                action="register",
                performed_by="bootstrap",
                timestamp=datetime(2026, 4, 1, 8, 0, 0, tzinfo=UTC),
                details={"status": "active"},
            ),
        ]


@pytest.mark.asyncio
async def test_get_agent_card_returns_404_for_unknown_agent() -> None:
    """Failure-first: unknown agent returns a structured 404."""
    app = build_app(service=_AgentStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/agents/missing")
        assert resp.status_code == 404
        assert "missing" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_agent_audit_returns_404_for_unknown_agent() -> None:
    app = build_app(service=_AgentStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/agents/missing/audit")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_agents_router_rejects_post_put_patch_delete() -> None:
    """F-R6 (read-only): every mutation verb on the agents router returns 405."""
    app = build_app(service=_AgentStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for method, path in [
            ("POST", "/api/v1/agents"),
            ("POST", "/api/v1/agents/cli-agent"),
            ("PUT", "/api/v1/agents/cli-agent"),
            ("PATCH", "/api/v1/agents/cli-agent"),
            ("DELETE", "/api/v1/agents/cli-agent"),
        ]:
            resp = await client.request(method, path)
            assert resp.status_code == 405, (
                f"{method} {path} should be Method Not Allowed (got "
                f"{resp.status_code})"
            )


@pytest.mark.asyncio
async def test_list_agents_returns_seeded_cards() -> None:
    app = build_app(service=_AgentStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 200
        body = resp.json()
        ids = {c["agent_id"] for c in body}
        assert ids == {"cli-agent", "suspended-agent"}
        suspended = next(c for c in body if c["agent_id"] == "suspended-agent")
        assert suspended["status"] == "suspended"
        assert suspended["signature_verified"] is False
        # F-R6: response shape MUST NOT leak the full signature_hash.
        assert "signature_hash" not in suspended


@pytest.mark.asyncio
async def test_get_agent_card_happy_path() -> None:
    app = build_app(service=_AgentStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/agents/cli-agent")
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent_id"] == "cli-agent"
        assert body["signature_verified"] is True
        assert body["signature_verification_status"] == "verified"
        assert body["capabilities"][0]["name"] == "shell.run"
        assert body["policies"][0]["name"] == "never-rm-rf"


@pytest.mark.asyncio
async def test_list_agents_includes_signature_verification_status() -> None:
    """Phase 1 trust correction: AgentCardResponse must surface the richer
    `signature_verification_status` (verified | failed | unavailable) in
    addition to the legacy boolean."""
    app = build_app(service=_AgentStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 200
        body = resp.json()
        cli = next(c for c in body if c["agent_id"] == "cli-agent")
        suspended = next(c for c in body if c["agent_id"] == "suspended-agent")
        assert cli["signature_verification_status"] == "verified"
        assert suspended["signature_verification_status"] == "failed"


@pytest.mark.asyncio
async def test_get_agent_audit_happy_path() -> None:
    app = build_app(service=_AgentStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/agents/cli-agent/audit")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["action"] == "register"
        assert body[0]["agent_id"] == "cli-agent"


# --- S3.1.1: GET /api/v1/workflows/{wf_id}/integrity --- failure first


class _IntegrityStub:
    def get_workflow_integrity(self, workflow_id: str) -> IntegrityReport:
        if workflow_id == "wf-missing":
            raise WorkflowNotFoundError(workflow_id)
        if workflow_id == "wf-tampered":
            return IntegrityReport(
                workflow_id=workflow_id,
                chain_valid=False,
                broken_at_event_id="evt-2",
                expected_hash="a" * 64,
                actual_hash="b" * 64,
            )
        return IntegrityReport(workflow_id=workflow_id, chain_valid=True)


@pytest.mark.asyncio
async def test_get_integrity_returns_404_for_unknown_workflow() -> None:
    """Failure-first: unknown workflow returns a structured 404."""
    app = build_app(service=_IntegrityStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/workflows/wf-missing/integrity")
        assert resp.status_code == 404
        assert "wf-missing" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_integrity_reports_break_location_when_tampered() -> None:
    """Failure-first: tampered chain returns chain_valid=false with the break
    location explicitly named in the body.
    """
    app = build_app(service=_IntegrityStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/workflows/wf-tampered/integrity")
        assert resp.status_code == 200
        body = resp.json()
        assert body["chain_valid"] is False
        assert body["broken_at_event_id"] == "evt-2"
        assert body["expected_hash"] == "a" * 64
        assert body["actual_hash"] == "b" * 64


@pytest.mark.asyncio
async def test_get_integrity_happy_path_clean_chain() -> None:
    """Acceptance: clean chain returns chain_valid=true with all break-fields null."""
    app = build_app(service=_IntegrityStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/workflows/wf-good/integrity")
        assert resp.status_code == 200
        body = resp.json()
        assert body["workflow_id"] == "wf-good"
        assert body["chain_valid"] is True
        assert body["broken_at_event_id"] is None
        assert body["expected_hash"] is None
        assert body["actual_hash"] is None


# --- S3.1.2: GET /api/v1/workflows/{wf_id}/compliance --- failure first


def _make_bundle(
    workflow_id: str,
    *,
    missing_keys: list[str] | None = None,
    chain_valid: bool = True,
    broken_at_event_id: str | None = None,
    expected_hash: str | None = None,
    actual_hash: str | None = None,
) -> ComplianceBundle:
    missing = missing_keys or []
    return ComplianceBundle(
        workflow_id=workflow_id,
        event_count=2,
        hash_chain_valid=chain_valid,
        bundle_type="compliance_audit",
        events=[],
        identity_cards={},
        audit_trails={},
        phase_decisions=[],
        correlation_health=CorrelationHealth(
            has_trace_id="trace_id" not in missing,
            has_user_id="user_id" not in missing,
            has_task_id="task_id" not in missing,
            has_agent_id="agent_id" not in missing,
            missing_keys=missing,
        ),
        integrity=IntegrityReport(
            workflow_id=workflow_id,
            chain_valid=chain_valid,
            broken_at_event_id=broken_at_event_id,
            expected_hash=expected_hash,
            actual_hash=actual_hash,
        ),
    )


class _ComplianceStub:
    def get_compliance_bundle(self, workflow_id: str) -> ComplianceBundle:
        if workflow_id == "wf-missing":
            raise WorkflowNotFoundError(workflow_id)
        if workflow_id == "wf-no-user":
            return _make_bundle(workflow_id, missing_keys=["user_id"])
        return _make_bundle(workflow_id)


@pytest.mark.asyncio
async def test_get_compliance_returns_404_for_unknown_workflow() -> None:
    """Failure-first: unknown workflow returns a structured 404."""
    app = build_app(service=_ComplianceStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/workflows/wf-missing/compliance")
        assert resp.status_code == 404
        assert "wf-missing" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_compliance_reports_missing_user_id_explicitly() -> None:
    """Failure-first: a workflow missing user_id surfaces has_user_id=false
    AND lists "user_id" in missing_keys.  Missing keys are NEVER silently
    omitted (the dashboard must name them so SREs can fix the upstream gap).
    """
    app = build_app(service=_ComplianceStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/workflows/wf-no-user/compliance")
        assert resp.status_code == 200
        body = resp.json()
        assert body["correlation_health"]["has_user_id"] is False
        assert body["correlation_health"]["missing_keys"] == ["user_id"]


@pytest.mark.asyncio
async def test_get_compliance_includes_integrity_break_location() -> None:
    """Sprint 3 review F4: the Workflow Deep Dive bundle now embeds the
    full integrity report, including `broken_at_event_id` and the
    expected/actual hashes for tampered chains."""

    class _TamperedBundleStub:
        def get_compliance_bundle(self, workflow_id: str) -> ComplianceBundle:
            return _make_bundle(
                workflow_id,
                chain_valid=False,
                broken_at_event_id="evt-2",
                expected_hash="a" * 64,
                actual_hash="b" * 64,
            )

    app = build_app(service=_TamperedBundleStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/workflows/wf-tampered/compliance")
        assert resp.status_code == 200
        body = resp.json()
        assert body["integrity"]["chain_valid"] is False
        assert body["integrity"]["broken_at_event_id"] == "evt-2"
        assert body["integrity"]["expected_hash"] == "a" * 64
        assert body["integrity"]["actual_hash"] == "b" * 64


@pytest.mark.asyncio
async def test_get_compliance_full_correlation_happy_path() -> None:
    """Acceptance: a fully-correlated workflow has empty missing_keys."""
    app = build_app(service=_ComplianceStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/workflows/wf-full/compliance")
        assert resp.status_code == 200
        body = resp.json()
        assert body["workflow_id"] == "wf-full"
        assert body["bundle_type"] == "compliance_audit"
        assert body["correlation_health"]["missing_keys"] == []
        assert all(
            body["correlation_health"][f"has_{k}"]
            for k in ("trace_id", "user_id", "task_id", "agent_id")
        )


# --- S4.3.1: GET /api/v1/logs --- failure first


class _LogStub:
    """Captures the kwargs passed to query_logs / tail_logs and returns
    pre-canned rows + a controllable async generator."""

    def __init__(
        self,
        rows: list[LogRow] | None = None,
        tail_rows: list[LogRow] | None = None,
        raise_on_query: BaseException | None = None,
        tail_finite: bool = True,
    ) -> None:
        self._rows = rows or []
        self._tail_rows = tail_rows or []
        self._raise = raise_on_query
        self._tail_finite = tail_finite
        self.last_query_kwargs: dict | None = None
        self.last_tail_kwargs: dict | None = None

    def query_logs(self, **kwargs):  # noqa: D401
        self.last_query_kwargs = kwargs
        if self._raise is not None:
            raise self._raise
        return list(self._rows)

    def tail_logs(self, **kwargs):  # noqa: D401
        self.last_tail_kwargs = kwargs
        rows = list(self._tail_rows)
        finite = self._tail_finite

        async def _gen():
            for row in rows:
                yield row
            if not finite:
                while True:
                    await asyncio.sleep(0.01)
            # `finite=True`: the generator simply ends, signalling
            # StopAsyncIteration so the SSE handler closes cleanly.

        return _gen()


@pytest.mark.asyncio
async def test_query_logs_returns_500_on_service_error() -> None:
    """Failure-first: a stub service raising surfaces a structured 500."""
    app = build_app(service=_LogStub(raise_on_query=RuntimeError("boom logs")))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/logs")
        assert resp.status_code == 500
        assert resp.json() == {"detail": "Internal server error"}
        assert "boom logs" not in resp.text
        assert "Traceback" not in resp.text


@pytest.mark.asyncio
async def test_query_logs_empty_returns_200_empty_list() -> None:
    app = build_app(service=_LogStub(rows=[]))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/logs")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
async def test_query_logs_forwards_filter_params() -> None:
    stub = _LogStub(
        rows=[
            LogRow(
                concern="guards",
                timestamp=datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC),
                logger="services.guardrails",
                level="ERROR",
                message="rejected",
            ),
        ],
    )
    app = build_app(service=stub)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/logs",
            params=[
                ("concerns", "guards"),
                ("concerns", "tools"),
                ("level", "ERROR"),
                ("search", "rej"),
                ("since", "2026-04-26T00:00:00+00:00"),
                ("limit", "10"),
            ],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["level"] == "ERROR"
        assert body[0]["concern"] == "guards"

    assert stub.last_query_kwargs is not None
    assert stub.last_query_kwargs["concerns"] == ["guards", "tools"]
    assert stub.last_query_kwargs["level"] == "ERROR"
    assert stub.last_query_kwargs["search"] == "rej"
    assert stub.last_query_kwargs["limit"] == 10


@pytest.mark.asyncio
async def test_query_logs_rejects_negative_limit() -> None:
    """Failure-first: limit must be a positive integer; FastAPI returns 422."""
    app = build_app(service=_LogStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/logs", params={"limit": "-1"})
        assert resp.status_code == 422


# --- S4.3.2: GET /api/v1/logs/stream (SSE) --- failure first


@pytest.mark.asyncio
async def test_logs_stream_emits_log_event_for_each_row() -> None:
    """Acceptance: each tail_logs row is emitted as `event: log` + json data."""
    stub = _LogStub(
        tail_rows=[
            LogRow(
                concern="guards",
                timestamp=datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC),
                logger="services.guardrails",
                level="INFO",
                message="row-one",
            ),
            LogRow(
                concern="guards",
                timestamp=datetime(2026, 4, 26, 8, 0, 1, tzinfo=UTC),
                logger="services.guardrails",
                level="INFO",
                message="row-two",
            ),
        ],
    )
    app = build_app(service=stub)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        timeout=5.0,
    ) as client:
        async with client.stream("GET", "/api/v1/logs/stream") as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            collected: list[str] = []
            async for line in resp.aiter_lines():
                collected.append(line)
                joined = "\n".join(collected)
                if "row-one" in joined and "row-two" in joined:
                    break

    joined = "\n".join(collected)
    assert "event: log" in joined
    assert "row-one" in joined
    assert "row-two" in joined


@pytest.mark.asyncio
async def test_logs_stream_forwards_filter_params() -> None:
    stub = _LogStub(tail_rows=[])
    app = build_app(service=stub)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        timeout=2.0,
    ) as client:
        async with client.stream(
            "GET",
            "/api/v1/logs/stream",
            params=[
                ("concerns", "guards"),
                ("level", "ERROR"),
                ("search", "boom"),
            ],
        ) as resp:
            # Read enough to ensure the handler started; immediately drop.
            await asyncio.sleep(0.05)
            await resp.aclose()

    assert stub.last_tail_kwargs is not None
    assert stub.last_tail_kwargs["concerns"] == ["guards"]
    assert stub.last_tail_kwargs["level"] == "ERROR"
    assert stub.last_tail_kwargs["search"] == "boom"


# --- Sprint 3 review F3 fix: GET /api/v1/compliance/summary ---


from services.explainability_service import (  # noqa: E402
    ComplianceSummary,
    WorkflowIntegritySummary,
)


class _ComplianceSummaryStub:
    def __init__(self) -> None:
        self.last_kwargs: dict | None = None

    def list_workflow_integrity(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> ComplianceSummary:
        self.last_kwargs = {"since": since, "until": until}
        return ComplianceSummary(
            rows=[
                WorkflowIntegritySummary(
                    workflow=WorkflowSummary(
                        workflow_id="wf-clean",
                        started_at=datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC),
                        event_count=4,
                        status="completed",
                        primary_agent_id="cli-agent",
                    ),
                    integrity=IntegrityReport(
                        workflow_id="wf-clean", chain_valid=True
                    ),
                ),
                WorkflowIntegritySummary(
                    workflow=WorkflowSummary(
                        workflow_id="wf-bad",
                        started_at=datetime(2026, 4, 26, 13, 0, 0, tzinfo=UTC),
                        event_count=3,
                        status="completed",
                        primary_agent_id=None,
                    ),
                    integrity=IntegrityReport(
                        workflow_id="wf-bad",
                        chain_valid=False,
                        broken_at_event_id="evt-2",
                        expected_hash="a" * 64,
                        actual_hash="b" * 64,
                    ),
                ),
            ],
            generated_at=datetime(2026, 4, 26, 14, 0, 0, tzinfo=UTC),
            since=since,
            until=until,
        )


@pytest.mark.asyncio
async def test_compliance_summary_returns_500_on_service_error() -> None:
    """Failure-first: a stub raising surfaces a structured 500."""

    class _ErrSummaryStub:
        def list_workflow_integrity(self, **_kwargs):
            raise RuntimeError("boom summary")

    app = build_app(service=_ErrSummaryStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/compliance/summary")
        assert resp.status_code == 500
        assert resp.json() == {"detail": "Internal server error"}
        assert "boom summary" not in resp.text


@pytest.mark.asyncio
async def test_compliance_summary_forwards_since_until() -> None:
    """Phase 2 contract: /api/v1/compliance/summary forwards both bounds."""
    stub = _ComplianceSummaryStub()
    app = build_app(service=stub)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/compliance/summary",
            params={
                "since": "2026-04-01T00:00:00+00:00",
                "until": "2026-05-01T00:00:00+00:00",
            },
        )
        assert resp.status_code == 200

    assert stub.last_kwargs is not None
    assert stub.last_kwargs["since"] == datetime(2026, 4, 1, tzinfo=UTC)
    assert stub.last_kwargs["until"] == datetime(2026, 5, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_compliance_summary_returns_seeded_rows() -> None:
    app = build_app(service=_ComplianceSummaryStub())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/compliance/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["rows"]) == 2
        ids = {row["workflow"]["workflow_id"] for row in body["rows"]}
        assert ids == {"wf-clean", "wf-bad"}
        bad = next(row for row in body["rows"] if row["workflow"]["workflow_id"] == "wf-bad")
        assert bad["integrity"]["chain_valid"] is False
        assert bad["integrity"]["broken_at_event_id"] == "evt-2"
