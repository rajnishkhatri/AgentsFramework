"""US-6.6: Phase 1 smoke test.

End-to-end integration: boot the app with MockRuntime, send authenticated
POST /agent/runs/stream, verify a multi-event SSE response in the
expected order. The Phase 1 acceptance gate.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from agent_ui_adapter.adapters.runtime.mock_runtime import MockRuntime
from agent_ui_adapter.server import InMemoryJwtVerifier, JwtClaims, build_app
from agent_ui_adapter.wire.domain_events import (
    LLMMessageEnded,
    LLMMessageStarted,
    LLMTokenEmitted,
    RunFinishedDomain,
    RunStartedDomain,
)
from services.authorization_service import AuthorizationService, EmbeddedPolicyBackend
from trust.models import AgentFacts, Capability


def test_phase_1_end_to_end_smoke() -> None:
    facts = AgentFacts(
        agent_id="a1",
        agent_name="Bot",
        owner="team",
        version="1.0.0",
        capabilities=[Capability(name="agent.session.start")],
    )
    runtime = MockRuntime(
        events=[
            RunStartedDomain(trace_id="trace-1", run_id="r1", thread_id="t1"),
            LLMMessageStarted(trace_id="trace-1", message_id="m1"),
            LLMTokenEmitted(trace_id="trace-1", message_id="m1", delta="Hello"),
            LLMTokenEmitted(trace_id="trace-1", message_id="m1", delta=", "),
            LLMTokenEmitted(trace_id="trace-1", message_id="m1", delta="world"),
            LLMMessageEnded(trace_id="trace-1", message_id="m1"),
            RunFinishedDomain(trace_id="trace-1", run_id="r1", thread_id="t1"),
        ]
    )
    app = build_app(
        runtime=runtime,
        jwt_verifier=InMemoryJwtVerifier(
            token_to_claims={
                "good": JwtClaims(
                    subject="a1",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            }
        ),
        agent_facts={facts.agent_id: facts},
        authorization_service=AuthorizationService(
            embedded_backend=EmbeddedPolicyBackend(),
        ),
    )
    client = TestClient(app)

    # Authenticated request: full multi-event SSE arrives, then sentinel.
    with client.stream(
        "POST",
        "/agent/runs/stream",
        json={"thread_id": "t1", "input": {}},
        headers={"Authorization": "Bearer good"},
    ) as r:
        assert r.status_code == 200
        body = b"".join(r.iter_bytes())

    # Required event types in order.
    expected_events = [
        b"event: RUN_STARTED",
        b"event: TEXT_MESSAGE_START",
        b"event: TEXT_MESSAGE_CONTENT",
        b"event: TEXT_MESSAGE_CONTENT",
        b"event: TEXT_MESSAGE_CONTENT",
        b"event: TEXT_MESSAGE_END",
        b"event: RUN_FINISHED",
        b"event: done",
    ]
    cursor = 0
    for marker in expected_events:
        idx = body.find(marker, cursor)
        assert idx >= 0, f"missing or out-of-order: {marker!r} after pos {cursor}"
        cursor = idx + len(marker)

    # Sentinel terminator
    assert body.rstrip().endswith(b"[DONE]")


def test_phase_1_unauthenticated_request_returns_401_no_sse_leak() -> None:
    app = build_app(
        runtime=MockRuntime(events=[]),
        jwt_verifier=InMemoryJwtVerifier(token_to_claims={}),
        agent_facts={},
    )
    client = TestClient(app)
    r = client.post(
        "/agent/runs/stream", json={"thread_id": "t", "input": {}}
    )
    assert r.status_code == 401
    # No SSE bytes leak in error response
    assert b"event:" not in r.content
    assert b"[DONE]" not in r.content
