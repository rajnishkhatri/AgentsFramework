"""L2 tests for Phase 4 dev telemetry parity in middleware/__main__.py.

Verifies:
  * _NoopTelemetryExporter satisfies TelemetryExporter protocol (all no-ops)
  * _build_dev_telemetry_exporter fallback logic (kill switch, missing keys)
  * Dev _generate() forwards domain events to telemetry bridge
  * O1: SSE survives exporter failure
  * No double run.finished emission
  * Safety-net run.finished on stream error

Layer: L2 (Reproducible Reality)
Strategy: Contract-driven TDD with in-memory exporter stub (Pattern 6)
Anti-patterns avoided:
  - Tautological: tests assert observable stub state, not algorithms
  - Mock Addiction: real in-memory stub; infra mocks only for graph/checkpointer
  - Gap Blindness: failure paths tested before success paths (Principle 4)
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch


from agent_ui_adapter.wire.domain_events import (
    LLMMessageEnded,
    LLMMessageStarted,
    RunFinishedDomain,
    RunStartedDomain,
    ToolCallStarted,
    ToolResultReceived,
)
from middleware.ports.telemetry_exporter import TelemetryExporter
from trust.enums import IdentityStatus
from trust.models import AgentFacts, Capability


# ─────────────────────────────────────────────────────────────────────
# In-Memory Exporter Stub (same contract as test_app_prod.py)
# ─────────────────────────────────────────────────────────────────────


class _StubTelemetryExporter:
    """In-memory exporter recording calls for assertion.

    Satisfies TelemetryExporter protocol without SDK dependency.
    """

    def __init__(self, *, raise_on_export: bool = False) -> None:
        self.events: list[dict] = []
        self.released_traces: list[str] = []
        self.shutdown_called = False
        self._raise_on_export = raise_on_export

    def export_event(
        self, *, name: str, trace_id: str, attributes: dict | None = None
    ) -> None:
        if self._raise_on_export:
            raise RuntimeError("simulated exporter failure")
        self.events.append(
            {"name": name, "trace_id": trace_id, "attributes": attributes}
        )

    def release_trace(self, trace_id: str) -> None:
        self.released_traces.append(trace_id)

    def shutdown(self) -> None:
        self.shutdown_called = True


# ─────────────────────────────────────────────────────────────────────
# _NoopTelemetryExporter — Protocol Compliance (Unit)
# ─────────────────────────────────────────────────────────────────────


class TestNoopTelemetryExporter:
    """_NoopTelemetryExporter is a port-shaped stub: all methods are silent no-ops."""

    def _make_noop(self):
        from middleware.__main__ import _NoopTelemetryExporter

        return _NoopTelemetryExporter()

    def test_satisfies_telemetry_exporter_protocol(self) -> None:
        noop = self._make_noop()
        assert isinstance(noop, TelemetryExporter)

    def test_export_event_is_noop(self) -> None:
        """export_event does not raise, returns None."""
        noop = self._make_noop()
        result = noop.export_event(
            name="run.started", trace_id="t1", attributes={"key": "val"}
        )
        assert result is None

    def test_release_trace_is_noop(self) -> None:
        noop = self._make_noop()
        result = noop.release_trace("t1")
        assert result is None

    def test_shutdown_is_noop(self) -> None:
        noop = self._make_noop()
        result = noop.shutdown()
        assert result is None


# ─────────────────────────────────────────────────────────────────────
# _build_dev_telemetry_exporter — Fallback Logic
# ─────────────────────────────────────────────────────────────────────


class TestBuildDevTelemetryExporter:
    """_build_dev_telemetry_exporter returns Langfuse when keys exist,
    noop otherwise.

    Failure paths tested first (Principle 4):
      - kill switch → noop
      - missing keys → noop
    Then success path:
      - keys present → LangfuseCloudExporter
    """

    def test_returns_noop_when_langfuse_disabled(self) -> None:
        """LANGFUSE_ENABLED=false → noop exporter."""
        from middleware.__main__ import (
            _NoopTelemetryExporter,
            _build_dev_telemetry_exporter,
        )

        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}, clear=False):
            exporter = _build_dev_telemetry_exporter()
        assert isinstance(exporter, _NoopTelemetryExporter)

    def test_returns_noop_when_public_key_missing(self) -> None:
        """No LANGFUSE_PUBLIC_KEY → noop exporter."""
        from middleware.__main__ import (
            _NoopTelemetryExporter,
            _build_dev_telemetry_exporter,
        )

        env = {"LANGFUSE_ENABLED": "true", "LANGFUSE_SECRET_KEY": "sk_test"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            exporter = _build_dev_telemetry_exporter()
        assert isinstance(exporter, _NoopTelemetryExporter)

    def test_returns_noop_when_secret_key_missing(self) -> None:
        """No LANGFUSE_SECRET_KEY → noop exporter."""
        from middleware.__main__ import (
            _NoopTelemetryExporter,
            _build_dev_telemetry_exporter,
        )

        env = {"LANGFUSE_ENABLED": "true", "LANGFUSE_PUBLIC_KEY": "pk_test"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("LANGFUSE_SECRET_KEY", None)
            exporter = _build_dev_telemetry_exporter()
        assert isinstance(exporter, _NoopTelemetryExporter)

    def test_returns_noop_when_langfuse_enabled_unset_and_keys_missing(self) -> None:
        """Default LANGFUSE_ENABLED (unset = true) but no keys → noop."""
        from middleware.__main__ import (
            _NoopTelemetryExporter,
            _build_dev_telemetry_exporter,
        )

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LANGFUSE_ENABLED", None)
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)
            exporter = _build_dev_telemetry_exporter()
        assert isinstance(exporter, _NoopTelemetryExporter)

    def test_returns_langfuse_exporter_when_keys_present(self) -> None:
        """Both keys present + enabled → LangfuseCloudExporter."""
        from middleware.__main__ import _build_dev_telemetry_exporter

        env = {
            "LANGFUSE_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "pk_test",
            "LANGFUSE_SECRET_KEY": "sk_test",
        }
        with patch.dict(os.environ, env, clear=False):
            exporter = _build_dev_telemetry_exporter()

        from middleware.adapters.observability.langfuse_cloud_exporter import (
            LangfuseCloudExporter,
        )

        assert isinstance(exporter, LangfuseCloudExporter)
        assert isinstance(exporter, TelemetryExporter)

    def test_returns_noop_on_exporter_construction_failure(self) -> None:
        """If LangfuseCloudExporter.__init__ raises, fall back to noop."""
        from middleware.__main__ import (
            _NoopTelemetryExporter,
            _build_dev_telemetry_exporter,
        )

        env = {
            "LANGFUSE_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "pk_test",
            "LANGFUSE_SECRET_KEY": "sk_test",
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch(
                "middleware.__main__.LangfuseCloudExporter",
                side_effect=RuntimeError("boom"),
            ),
        ):
            exporter = _build_dev_telemetry_exporter()
        assert isinstance(exporter, _NoopTelemetryExporter)


# ─────────────────────────────────────────────────────────────────────
# Dev _generate() Telemetry Wiring — Integration
#
# These tests mirror TestTelemetryWiring in test_app_prod.py but for
# the dev server. We mock the graph/checkpointer infra and inject a
# stub exporter to verify the telemetry_bridge wiring.
# ─────────────────────────────────────────────────────────────────────


def _build_dev_telemetry_client(
    domain_events,
    *,
    stub_exporter: _StubTelemetryExporter | None = None,
    runtime_error: Exception | None = None,
):
    """Build a dev FastAPI TestClient wired with a StubTelemetryExporter.

    Returns ``(TestClient, StubTelemetryExporter)``.
    Infrastructure mocks (graph, checkpointer, identity) isolate external I/O;
    the exporter is a real in-memory implementation.
    """
    from importlib import reload

    if stub_exporter is None:
        stub_exporter = _StubTelemetryExporter()

    async def _mock_run(*args, **kwargs):
        for ev in domain_events:
            yield ev
        if runtime_error:
            raise runtime_error

    mock_runtime = MagicMock()
    mock_runtime.run = _mock_run

    dev_identity = AgentFacts(
        agent_id="dev-agent",
        agent_name="Dev Agent",
        owner="dev-user",
        version="1.0.0",
        description="Local development agent",
        capabilities=[Capability(name="delegate.subagent.*")],
        status=IdentityStatus.ACTIVE,
    )

    mock_registry = MagicMock()
    mock_registry.get.return_value = dev_identity

    mock_trace_service = MagicMock()
    cache_dir = Path("/tmp/agent-dev-test-cache")

    # build_dev_app now consumes the FULL AgentComponents (so the memory recall
    # service + Phase-2 autocapture reach LangGraphRuntime). Mirror that shape.
    from middleware.composition import AgentComponents

    build_components_return = AgentComponents(
        agent_config=MagicMock(),
        tool_registry=MagicMock(),
        agent_facts_registry=mock_registry,
        cache_dir=cache_dir,
        goal_judge_config_reader=MagicMock(),
        settings=MagicMock(),
        memory_service=MagicMock(),
        memory_autocapture=MagicMock(),
    )

    env = {
        "LANGFUSE_ENABLED": "true",
        "LANGFUSE_PUBLIC_KEY": "pk_test",
        "LANGFUSE_SECRET_KEY": "sk_test",
    }

    # Remove GCP env to force the local dev path
    with (
        patch.dict(os.environ, env, clear=False),
        patch("middleware.__main__._GCP_EXECUTION_ENV", None),
        patch(
            "middleware.__main__._build_dev_telemetry_exporter",
            return_value=stub_exporter,
        ),
        patch(
            "middleware.__main__._load_graph_factory",
            return_value=MagicMock(),
        ),
        patch(
            "middleware.__main__._build_agent_components",
            return_value=build_components_return,
        ),
        patch(
            "middleware.__main__.LangGraphRuntime",
            return_value=mock_runtime,
        ),
        patch(
            "middleware.__main__.TraceService",
            return_value=mock_trace_service,
        ),
        patch(
            "middleware.__main__.JsonlFileTraceSink",
            return_value=MagicMock(),
        ),
    ):
        import middleware.__main__ as mod

        reload(mod)

        # Bypass the async lifespan by building the app and injecting state
        with (
            patch.object(
                mod,
                "_build_agent_components",
                return_value=build_components_return,
            ),
            patch(
                "middleware.__main__._build_dev_telemetry_exporter",
                return_value=stub_exporter,
            ),
        ):
            app = mod.build_dev_app()
            app.state.runtime = mock_runtime
            app.state.dev_identity = dev_identity

    from fastapi.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=False)
    return client, stub_exporter


def _dev_post_stream(client):
    """POST /run/stream with valid dev bearer token."""
    return client.post(
        "/run/stream",
        json={"input": {"messages": [{"content": "hello"}]}},
        headers={"Authorization": "Bearer dev-token"},
    )


class TestDevTelemetryWiring:
    """Phase 4: dev _generate() wires domain events to telemetry bridge.

    Tests ordered failure-path-first per TDD Operating Principle 4.
    """

    # ── Failure paths (tested first) ─────────────────────────────────

    def test_sse_survives_exporter_failure(self) -> None:
        """O1: broken exporter never breaks SSE stream."""
        events = [
            RunStartedDomain(trace_id="t-1", run_id="r-1", thread_id="th-1"),
            RunFinishedDomain(
                trace_id="t-1", run_id="r-1", thread_id="th-1", error=None
            ),
        ]
        stub = _StubTelemetryExporter(raise_on_export=True)
        client, _ = _build_dev_telemetry_client(events, stub_exporter=stub)
        r = _dev_post_stream(client)
        assert r.status_code == 200

    def test_safety_net_emits_run_finished_on_stream_error(self) -> None:
        """Finally block emits run.finished when stream errors before
        RunFinishedDomain."""
        events = [
            RunStartedDomain(trace_id="t-1", run_id="r-1", thread_id="th-1"),
        ]
        client, stub = _build_dev_telemetry_client(
            events, runtime_error=RuntimeError("boom")
        )
        r = _dev_post_stream(client)
        assert r.status_code == 200

        run_finished = [e for e in stub.events if e["name"] == "run.finished"]
        assert len(run_finished) == 1, (
            f"Expected 1 run.finished, got {len(run_finished)}"
        )
        assert run_finished[0]["attributes"]["errored"] is True

    def test_no_double_run_finished(self) -> None:
        """Bridge handles RunFinishedDomain; finally block does not duplicate."""
        events = [
            RunStartedDomain(trace_id="t-1", run_id="r-1", thread_id="th-1"),
            RunFinishedDomain(
                trace_id="t-1", run_id="r-1", thread_id="th-1", error=None
            ),
        ]
        client, stub = _build_dev_telemetry_client(events)
        r = _dev_post_stream(client)
        assert r.status_code == 200

        run_finished = [e for e in stub.events if e["name"] == "run.finished"]
        assert len(run_finished) == 1, (
            f"Expected exactly 1 run.finished, got {len(run_finished)}"
        )

    def test_safety_net_skipped_when_no_events(self) -> None:
        """No run.finished emitted when stream yields zero events."""
        client, stub = _build_dev_telemetry_client([])
        r = _dev_post_stream(client)
        assert r.status_code == 200
        assert len(stub.events) == 0

    # ── Contract: exactly-once semantics ─────────────────────────────

    def test_run_started_exactly_once(self) -> None:
        """run.started exported exactly once per request."""
        events = [
            RunStartedDomain(trace_id="t-1", run_id="r-1", thread_id="th-1"),
            ToolCallStarted(
                trace_id="t-1",
                tool_call_id="tc-1",
                tool_name="shell",
                args_json='{"cmd":"ls"}',
            ),
            ToolResultReceived(trace_id="t-1", tool_call_id="tc-1", result="file.txt"),
            RunFinishedDomain(
                trace_id="t-1", run_id="r-1", thread_id="th-1", error=None
            ),
        ]
        client, stub = _build_dev_telemetry_client(events)
        r = _dev_post_stream(client)
        assert r.status_code == 200

        run_started = [e for e in stub.events if e["name"] == "run.started"]
        assert len(run_started) == 1

    def test_run_finished_exactly_once(self) -> None:
        """run.finished exported exactly once per request."""
        events = [
            RunStartedDomain(trace_id="t-1", run_id="r-1", thread_id="th-1"),
            RunFinishedDomain(
                trace_id="t-1", run_id="r-1", thread_id="th-1", error=None
            ),
        ]
        client, stub = _build_dev_telemetry_client(events)
        r = _dev_post_stream(client)
        assert r.status_code == 200

        run_finished = [e for e in stub.events if e["name"] == "run.finished"]
        assert len(run_finished) == 1

    # ── Happy path: full event forwarding ────────────────────────────

    def test_forwards_all_domain_events_to_exporter(self) -> None:
        """All non-skipped domain events forwarded to telemetry exporter."""
        events = [
            RunStartedDomain(trace_id="t-1", run_id="r-1", thread_id="th-1"),
            LLMMessageStarted(trace_id="t-1", message_id="msg-1"),
            LLMMessageEnded(trace_id="t-1", message_id="msg-1"),
            ToolCallStarted(
                trace_id="t-1",
                tool_call_id="tc-1",
                tool_name="shell",
                args_json='{"cmd":"ls"}',
            ),
            ToolResultReceived(trace_id="t-1", tool_call_id="tc-1", result="file.txt"),
            RunFinishedDomain(
                trace_id="t-1", run_id="r-1", thread_id="th-1", error=None
            ),
        ]
        client, stub = _build_dev_telemetry_client(events)
        r = _dev_post_stream(client)
        assert r.status_code == 200

        # Phase 3: started events buffer; one merged obs per LLM/tool call.
        exported_names = [e["name"] for e in stub.events]
        assert exported_names == [
            "run.started",
            "llm.call",
            "tool.shell",
            "run.finished",
        ]

    def test_subject_passed_as_dev_user_id(self) -> None:
        """DEV_USER_ID forwarded as subject in telemetry events."""
        events = [
            RunStartedDomain(trace_id="t-1", run_id="r-1", thread_id="th-1"),
            RunFinishedDomain(
                trace_id="t-1", run_id="r-1", thread_id="th-1", error=None
            ),
        ]
        client, stub = _build_dev_telemetry_client(events)
        r = _dev_post_stream(client)
        assert r.status_code == 200

        for event in stub.events:
            assert event["attributes"].get("subject") == "dev-user"
