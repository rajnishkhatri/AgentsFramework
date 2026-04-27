"""US-9.2: End-to-end smoke test with LangGraphRuntime + InMemoryJwtVerifier.

Exercises the full HTTP→JWT→LangGraphRuntime→translator→SSE stack using a
fake compiled graph (no real LLM). Validates:
  1. Authenticated request through InMemoryJwtVerifier
  2. LangGraphRuntime translates graph events into domain events
  3. Domain events are translated to AG-UI wire events in the SSE stream
  4. Sentinel terminates the stream
  5. Unauthenticated request is rejected before any SSE bytes leak

Phase 1 sign-off note: production deployment requires a real JwtVerifier
(WorkOS / RS256 / OAuth) behind the same Protocol. InMemoryJwtVerifier is
the test double. Real verifier deferred to v1.5.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, AsyncIterator

from fastapi.testclient import TestClient

from agent_ui_adapter.adapters.runtime.langgraph_runtime import LangGraphRuntime
from agent_ui_adapter.server import InMemoryJwtVerifier, JwtClaims, build_app
from services.authorization_service import AuthorizationService, EmbeddedPolicyBackend
from trust.models import AgentFacts, Capability


class _FakeChunk:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeCompiledGraph:
    """Scripted LangGraph compiled app for testing."""

    def __init__(self, scripted: list[dict], state: Any = None) -> None:
        self._scripted = scripted
        self._state = state

    async def astream_events(
        self, input: Any, config: dict | None = None, version: str = "v2"
    ) -> AsyncIterator[dict]:
        for ev in self._scripted:
            yield ev

    async def aget_state(self, config: dict) -> Any:
        return self._state


def _build_stack():
    facts = AgentFacts(
        agent_id="smoke-agent",
        agent_name="SmokeBot",
        owner="ci",
        version="1.0.0",
        capabilities=[Capability(name="agent.session.start")],
    )
    scripted_events = [
        {
            "event": "on_chat_model_start",
            "data": {},
            "name": "ChatModel",
            "run_id": "lc-smoke-1",
        },
        {
            "event": "on_chat_model_stream",
            "data": {"chunk": _FakeChunk("Hello")},
            "name": "ChatModel",
            "run_id": "lc-smoke-1",
        },
        {
            "event": "on_chat_model_stream",
            "data": {"chunk": _FakeChunk(", ")},
            "name": "ChatModel",
            "run_id": "lc-smoke-1",
        },
        {
            "event": "on_chat_model_stream",
            "data": {"chunk": _FakeChunk("world!")},
            "name": "ChatModel",
            "run_id": "lc-smoke-1",
        },
        {
            "event": "on_chat_model_end",
            "data": {},
            "name": "ChatModel",
            "run_id": "lc-smoke-1",
        },
        {
            "event": "on_tool_start",
            "data": {"input": {"query": "test"}},
            "name": "web_search",
            "run_id": "lc-smoke-tool-1",
        },
        {
            "event": "on_tool_end",
            "data": {"output": "search result"},
            "name": "web_search",
            "run_id": "lc-smoke-tool-1",
        },
    ]

    graph = _FakeCompiledGraph(scripted=scripted_events)
    runtime = LangGraphRuntime(graph=graph)

    app = build_app(
        runtime=runtime,
        jwt_verifier=InMemoryJwtVerifier(
            token_to_claims={
                "smoke-token": JwtClaims(
                    subject="smoke-agent",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            }
        ),
        agent_facts={facts.agent_id: facts},
        authorization_service=AuthorizationService(
            embedded_backend=EmbeddedPolicyBackend(),
        ),
    )
    return app


def test_langgraph_runtime_end_to_end_sse() -> None:
    """Full stack: JWT auth → LangGraphRuntime → AG-UI SSE stream."""
    app = _build_stack()
    client = TestClient(app)

    with client.stream(
        "POST",
        "/agent/runs/stream",
        json={"thread_id": "t-smoke", "input": {"task": "hello"}},
        headers={"Authorization": "Bearer smoke-token"},
    ) as r:
        assert r.status_code == 200
        body = b"".join(r.iter_bytes())

    expected_markers = [
        b"event: RUN_STARTED",
        b"event: TEXT_MESSAGE_START",
        b"event: TEXT_MESSAGE_CONTENT",
        b"event: TEXT_MESSAGE_CONTENT",
        b"event: TEXT_MESSAGE_CONTENT",
        b"event: TEXT_MESSAGE_END",
        b"event: TOOL_CALL_START",
        b"event: TOOL_CALL_ARGS",
        b"event: TOOL_RESULT",
        b"event: RUN_FINISHED",
        b"event: done",
    ]
    cursor = 0
    for marker in expected_markers:
        idx = body.find(marker, cursor)
        assert idx >= 0, (
            f"missing or out-of-order: {marker!r} after pos {cursor}\n"
            f"body excerpt: ...{body[max(0, cursor - 50):cursor + 200]!r}..."
        )
        cursor = idx + len(marker)

    assert body.rstrip().endswith(b"[DONE]")


def test_langgraph_runtime_unauthenticated_returns_401() -> None:
    app = _build_stack()
    client = TestClient(app)
    r = client.post(
        "/agent/runs/stream",
        json={"thread_id": "t-smoke", "input": {}},
    )
    assert r.status_code == 401
    assert b"event:" not in r.content
