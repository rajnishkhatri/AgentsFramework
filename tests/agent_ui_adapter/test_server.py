"""US-6.1, US-6.3: FastAPI app + routes + composition root tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from agent_ui_adapter.adapters.runtime.mock_runtime import MockRuntime
from agent_ui_adapter.server import (
    InMemoryJwtVerifier,
    JwtClaims,
    build_app,
)
from agent_ui_adapter.wire.domain_events import (
    LLMTokenEmitted,
    RunFinishedDomain,
    RunStartedDomain,
)
from services.authorization_service import AuthorizationService, EmbeddedPolicyBackend
from services.trace_service import InMemoryTraceSink, TraceService
from trust.models import AgentFacts, Capability


def _good_token(client: TestClient) -> dict:
    return {"Authorization": "Bearer good"}


def _make_app_with_runtime(runtime, agent_id: str = "a1", *, trace_sink=None):
    facts = AgentFacts(
        agent_id=agent_id,
        agent_name="Bot",
        owner="team",
        version="1.0.0",
        capabilities=[Capability(name="agent.session.start")],
    )
    sink = trace_sink or InMemoryTraceSink()
    trace_svc = TraceService(sinks=[sink])
    return build_app(
        runtime=runtime,
        jwt_verifier=InMemoryJwtVerifier(
            token_to_claims={
                "good": JwtClaims(
                    subject=agent_id,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            }
        ),
        agent_facts={facts.agent_id: facts},
        authorization_service=AuthorizationService(
            embedded_backend=EmbeddedPolicyBackend(),
            trace_emit=trace_svc.emit,
        ),
        trace_service=trace_svc,
    )


# ── Routes ────────────────────────────────────────────────────────────


class TestRoutes:
    def test_healthz_returns_ok(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        r = client.get("/healthz")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "adapter_version" in body

    def test_get_unknown_run_returns_404(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        r = client.get(
            "/agent/runs/does-not-exist", headers=_good_token(client)
        )
        assert r.status_code == 404

    def test_post_threads_creates_thread(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        r = client.post(
            "/agent/threads",
            json={"user_id": "u1", "metadata": {}},
            headers=_good_token(client),
        )
        assert r.status_code == 200
        assert r.json()["user_id"] == "u1"
        assert r.json()["thread_id"]

    def test_runs_stream_returns_sse_response(self) -> None:
        runtime = MockRuntime(
            events=[
                RunStartedDomain(trace_id="trace-1", run_id="r1", thread_id="t1"),
                LLMTokenEmitted(trace_id="trace-1", message_id="m1", delta="hi"),
                RunFinishedDomain(trace_id="trace-1", run_id="r1", thread_id="t1"),
            ]
        )
        client = TestClient(_make_app_with_runtime(runtime))
        with client.stream(
            "POST",
            "/agent/runs/stream",
            json={"thread_id": "t1", "input": {}},
            headers=_good_token(client),
        ) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            assert r.headers.get("x-accel-buffering") == "no"
            body = b"".join(r.iter_bytes())
        assert b"event: RUN_STARTED" in body
        assert b"event: TEXT_MESSAGE_CONTENT" in body
        assert b"event: RUN_FINISHED" in body
        assert b"event: done" in body
        assert b"[DONE]" in body


# ── Composition root: DI swappability ─────────────────────────────────


class TestCompositionRoot:
    def test_build_app_uses_supplied_runtime(self) -> None:
        # Two different runtimes produce two different streams.
        rt1 = MockRuntime(
            events=[
                RunStartedDomain(trace_id="t", run_id="r1", thread_id="t1"),
                RunFinishedDomain(trace_id="t", run_id="r1", thread_id="t1"),
            ]
        )
        rt2 = MockRuntime(
            events=[
                RunStartedDomain(trace_id="t", run_id="r2", thread_id="t1"),
                LLMTokenEmitted(trace_id="t", message_id="m", delta="x"),
                RunFinishedDomain(trace_id="t", run_id="r2", thread_id="t1"),
            ]
        )
        c1 = TestClient(_make_app_with_runtime(rt1))
        c2 = TestClient(_make_app_with_runtime(rt2))
        with c1.stream(
            "POST",
            "/agent/runs/stream",
            json={"thread_id": "t1", "input": {}},
            headers=_good_token(c1),
        ) as r:
            b1 = b"".join(r.iter_bytes())
        with c2.stream(
            "POST",
            "/agent/runs/stream",
            json={"thread_id": "t1", "input": {}},
            headers=_good_token(c2),
        ) as r:
            b2 = b"".join(r.iter_bytes())
        # rt1 has 2 events; rt2 has 3. The token output proves they differ.
        assert b"TEXT_MESSAGE_CONTENT" not in b1
        assert b"TEXT_MESSAGE_CONTENT" in b2

    def test_build_app_returns_a_fastapi_app(self) -> None:
        from fastapi import FastAPI

        app = _make_app_with_runtime(MockRuntime(events=[]))
        assert isinstance(app, FastAPI)

    def test_cancel_run_routes_through_runtime(self) -> None:
        runtime = MockRuntime(
            events=[
                RunStartedDomain(trace_id="t", run_id="r1", thread_id="t1"),
                RunFinishedDomain(trace_id="t", run_id="r1", thread_id="t1"),
            ]
        )
        client = TestClient(_make_app_with_runtime(runtime))
        with client.stream(
            "POST",
            "/agent/runs/stream",
            json={"thread_id": "t1", "input": {}},
            headers=_good_token(client),
        ) as r:
            body = b"".join(r.iter_bytes())
        run_id = "r1"
        r2 = client.delete(
            f"/agent/runs/{run_id}", headers=_good_token(client)
        )
        assert r2.status_code == 200
        assert run_id in runtime.cancelled_runs
