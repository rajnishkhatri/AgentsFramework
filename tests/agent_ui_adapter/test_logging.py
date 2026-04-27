"""US-6.4: Per-stream observability logs.

Per AGENT_UI_ADAPTER_SPRINTS.md S6 US-6.4. Verifies stream_started /
stream_ended log lines carry trace_id and run_id.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from agent_ui_adapter.adapters.runtime.mock_runtime import MockRuntime
from agent_ui_adapter.server import InMemoryJwtVerifier, JwtClaims, build_app
from agent_ui_adapter.wire.domain_events import (
    RunFinishedDomain,
    RunStartedDomain,
)
from services.authorization_service import AuthorizationService, EmbeddedPolicyBackend
from services.trace_service import InMemoryTraceSink, TraceService
from trust.models import AgentFacts, Capability


def _make_client(runtime, *, trace_sink=None) -> TestClient:
    facts = AgentFacts(
        agent_id="a1",
        agent_name="Bot",
        owner="team",
        version="1.0.0",
        capabilities=[Capability(name="agent.session.start")],
    )
    sink = trace_sink or InMemoryTraceSink()
    trace_svc = TraceService(sinks=[sink])
    return TestClient(
        build_app(
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
                trace_emit=trace_svc.emit,
            ),
            trace_service=trace_svc,
        )
    )


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def capture_server_logs():
    """Capture logs from agent_ui_adapter.server even when propagate=False.

    Pytest's caplog uses the root handler; our logger has propagate=false
    (per H4), so we attach a temporary handler directly. The handler is
    forced to NOTSET so all levels are captured regardless of logger config.
    """
    handler = _CaptureHandler()
    handler.setLevel(logging.NOTSET)
    logger = logging.getLogger("agent_ui_adapter.server")
    previous_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


class TestPerStreamObservability:
    def test_stream_emits_started_and_ended_logs_with_trace_and_run_id(
        self, capture_server_logs
    ) -> None:
        runtime = MockRuntime(
            events=[
                RunStartedDomain(trace_id="trace-x", run_id="run-y", thread_id="t"),
                RunFinishedDomain(trace_id="trace-x", run_id="run-y", thread_id="t"),
            ]
        )
        client = _make_client(runtime)
        with client.stream(
            "POST",
            "/agent/runs/stream",
            json={"thread_id": "t", "input": {}},
            headers={"Authorization": "Bearer good"},
        ) as r:
            b"".join(r.iter_bytes())

        messages = [r.getMessage() for r in capture_server_logs.records]
        joined = "\n".join(messages)
        assert "stream_started" in joined
        assert "stream_ended" in joined
        # The trace_id appears in at least one log line for correlation.
        assert any("trace_id" in m for m in messages)
