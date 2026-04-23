"""US-7.2 — HITL round-trip integration test.

Failure paths first:
- Inbound non-``ToolResult`` AG-UI events are rejected by ``to_domain``
- Inbound ``ToolResult`` with missing fields is rejected by Pydantic

Acceptance (mock approve + mock deny scenarios):

Outbound leg
    A ``MockRuntime`` scripted to emit a ``request_approval`` tool-call
    streams the expected ``TOOL_CALL_START`` / ``TOOL_CALL_ARGS`` /
    ``TOOL_CALL_END`` AG-UI events through the SSE pipeline, with the
    ``request_approval`` tool name, the supplied args, and the ``trace_id``
    propagated to every ``raw_event``.

Inbound leg
    The frontend's ``TOOL_RESULT`` event (``content="approved"`` and
    ``content="denied"``) is mapped by ``ag_ui_to_domain.to_domain`` into
    a ``ToolResultReceived`` domain event whose ``tool_call_id`` matches
    the originating tool call and whose ``result`` carries the user's
    decision. That domain event is what a runtime would receive to
    resume the run.

Per the S7 ownership convention this story owns NO translator code -- it
only exercises the existing translator pipeline (US-4.1, US-4.2) plus the
virtual ``request_approval`` tool wired in US-7.1.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from agent_ui_adapter.adapters.runtime.mock_runtime import MockRuntime
from agent_ui_adapter.server import InMemoryJwtVerifier, JwtClaims, build_app
from agent_ui_adapter.translators.ag_ui_to_domain import to_domain
from agent_ui_adapter.wire.ag_ui_events import (
    RunStarted as AGUIRunStarted,
    ToolResult,
)
from agent_ui_adapter.wire.domain_events import (
    RunFinishedDomain,
    RunStartedDomain,
    ToolCallEnded,
    ToolCallStarted,
    ToolResultReceived,
)
from services.tools.hitl import (
    APPROVED_RESULT,
    DENIED_RESULT,
    REQUEST_APPROVAL_TOOL_NAME,
)
from trust.models import AgentFacts


TRACE_ID = "hitl-trace-1"
RUN_ID = "hitl-run-1"
THREAD_ID = "hitl-thread-1"
TOOL_CALL_ID = "tc-approval-1"
APPROVAL_ARGS = {"action": "delete-files", "justification": "tmp cleanup"}


# ── Helpers ───────────────────────────────────────────────────────────


def _build_hitl_runtime() -> MockRuntime:
    """A scripted runtime that requests approval then completes.

    The agent has no way to "wait" inside a MockRuntime, so we model the
    round-trip in two halves: the outbound leg streams the tool-call
    events through SSE; the inbound leg is exercised separately by
    feeding the simulated frontend ``ToolResult`` through ``to_domain``.
    """
    return MockRuntime(
        events=[
            RunStartedDomain(
                trace_id=TRACE_ID, run_id=RUN_ID, thread_id=THREAD_ID
            ),
            ToolCallStarted(
                trace_id=TRACE_ID,
                tool_call_id=TOOL_CALL_ID,
                tool_name=REQUEST_APPROVAL_TOOL_NAME,
                args_json=json.dumps(APPROVAL_ARGS),
            ),
            ToolCallEnded(trace_id=TRACE_ID, tool_call_id=TOOL_CALL_ID),
            RunFinishedDomain(
                trace_id=TRACE_ID, run_id=RUN_ID, thread_id=THREAD_ID
            ),
        ]
    )


def _build_authed_client() -> TestClient:
    from services.authorization_service import (
        AuthorizationService,
        EmbeddedPolicyBackend,
    )
    from trust.models import Capability

    facts = AgentFacts(
        agent_id="hitl-agent",
        agent_name="HITLBot",
        owner="team",
        version="1.0.0",
        capabilities=[Capability(name="agent.session.start")],
    )
    app = build_app(
        runtime=_build_hitl_runtime(),
        jwt_verifier=InMemoryJwtVerifier(
            token_to_claims={
                "good": JwtClaims(
                    subject="hitl-agent",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            }
        ),
        agent_facts={facts.agent_id: facts},
        authorization_service=AuthorizationService(
            embedded_backend=EmbeddedPolicyBackend(),
        ),
    )
    return TestClient(app)


# ── Failure paths first ───────────────────────────────────────────────


class TestInboundRejections:
    def test_inbound_non_tool_result_event_is_rejected(self) -> None:
        """A frontend cannot inject a RunStarted to fake the run state."""
        bogus = AGUIRunStarted(run_id="x", thread_id="y")
        with pytest.raises(TypeError, match="ToolResult"):
            to_domain(bogus, trace_id=TRACE_ID)

    def test_inbound_tool_result_missing_required_field_rejected(self) -> None:
        """Pydantic ``extra='forbid'`` + missing field → ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ToolResult(tool_call_id=TOOL_CALL_ID, role="tool")  # type: ignore[call-arg]


# ── Outbound leg: SSE carries the request_approval tool call ──────────


def test_outbound_emits_request_approval_tool_call() -> None:
    """SSE stream contains TOOL_CALL_START/ARGS/END for ``request_approval``."""
    with _build_authed_client().stream(
        "POST",
        "/agent/runs/stream",
        json={"thread_id": THREAD_ID, "input": {}},
        headers={"Authorization": "Bearer good"},
    ) as r:
        assert r.status_code == 200
        body = b"".join(r.iter_bytes())

    expected_in_order = [
        b"event: RUN_STARTED",
        b"event: TOOL_CALL_START",
        b"event: TOOL_CALL_ARGS",
        b"event: TOOL_CALL_END",
        b"event: RUN_FINISHED",
        b"event: done",
    ]
    cursor = 0
    for marker in expected_in_order:
        idx = body.find(marker, cursor)
        assert idx >= 0, f"missing or out-of-order: {marker!r} after pos {cursor}"
        cursor = idx + len(marker)

    body_text = body.decode("utf-8")
    assert REQUEST_APPROVAL_TOOL_NAME in body_text
    assert APPROVAL_ARGS["action"] in body_text
    assert APPROVAL_ARGS["justification"] in body_text
    assert TRACE_ID in body_text


# ── Inbound leg: TOOL_RESULT routes back via translator ───────────────


@pytest.mark.parametrize(
    ("decision", "expected_result"),
    [
        ("approve", APPROVED_RESULT),
        ("deny", DENIED_RESULT),
    ],
)
def test_inbound_tool_result_routes_back_to_runtime(
    decision: str, expected_result: str
) -> None:
    """A frontend ``TOOL_RESULT`` becomes a ``ToolResultReceived`` for the runtime."""
    inbound = ToolResult(
        tool_call_id=TOOL_CALL_ID,
        content=expected_result,
        role="tool",
    )
    domain_event = to_domain(inbound, trace_id=TRACE_ID)

    assert isinstance(domain_event, ToolResultReceived), (
        f"{decision} path must produce a ToolResultReceived"
    )
    assert domain_event.tool_call_id == TOOL_CALL_ID
    assert domain_event.result == expected_result
    assert domain_event.trace_id == TRACE_ID
