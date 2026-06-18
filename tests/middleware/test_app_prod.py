"""Tests for middleware.app_prod — production combined backend.

Verifies:
  * build_combined_app() factory boots cleanly with mocked GCP deps
  * /healthz responds 200 pre-auth (Cloud Run liveness)
  * /run/stream rejects missing bearer (401)
  * Dockerfile.backend and Dockerfile.frontend exist with expected content
  * Phase 3: _generate() wires domain events to telemetry bridge (TDD §Protocol B)
"""

from __future__ import annotations

import asyncio
import os
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_ui_adapter.wire.domain_events import (
    LLMMessageEnded,
    LLMMessageStarted,
    RunFinishedDomain,
    RunStartedDomain,
    ToolCallStarted,
    ToolResultReceived,
)
from trust.enums import IdentityStatus
from trust.models import AgentFacts, Capability


AGENT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestDockerfiles:
    """Verify Docker assets exist and contain expected markers."""

    def test_dockerfile_backend_exists(self) -> None:
        path = AGENT_ROOT / "Dockerfile.backend"
        assert path.exists(), "Dockerfile.backend must exist at repo root"

    def test_dockerfile_backend_uses_python_313(self) -> None:
        content = (AGENT_ROOT / "Dockerfile.backend").read_text()
        assert "python:3.13" in content

    def test_dockerfile_backend_installs_gcp_extra(self) -> None:
        content = (AGENT_ROOT / "Dockerfile.backend").read_text()
        assert "[gcp]" in content

    def test_dockerfile_backend_exposes_8080(self) -> None:
        content = (AGENT_ROOT / "Dockerfile.backend").read_text()
        assert "EXPOSE 8080" in content

    def test_dockerfile_backend_cmd_is_uvicorn_factory(self) -> None:
        content = (AGENT_ROOT / "Dockerfile.backend").read_text()
        assert "middleware.app_prod:build_combined_app" in content
        assert "--factory" in content

    def test_dockerfile_backend_has_healthcheck(self) -> None:
        content = (AGENT_ROOT / "Dockerfile.backend").read_text()
        assert "HEALTHCHECK" in content
        assert "/healthz" in content

    def test_dockerfile_frontend_exists(self) -> None:
        path = AGENT_ROOT / "frontend" / "Dockerfile.frontend"
        assert path.exists(), "Dockerfile.frontend must exist in frontend/"

    def test_dockerfile_frontend_uses_standalone(self) -> None:
        content = (AGENT_ROOT / "frontend" / "Dockerfile.frontend").read_text()
        assert "standalone" in content

    def test_dockerfile_frontend_exposes_3000(self) -> None:
        content = (AGENT_ROOT / "frontend" / "Dockerfile.frontend").read_text()
        assert "EXPOSE 3000" in content

    def test_dockerfile_frontend_runs_server_js(self) -> None:
        content = (AGENT_ROOT / "frontend" / "Dockerfile.frontend").read_text()
        assert "server.js" in content


class TestNextConfig:
    """Verify next.config.ts has output: standalone."""

    def test_standalone_output_configured(self) -> None:
        content = (AGENT_ROOT / "frontend" / "next.config.ts").read_text()
        assert 'output: "standalone"' in content or "output: 'standalone'" in content


class TestAppProdModule:
    """Verify app_prod module structure and imports."""

    def test_module_importable(self) -> None:
        """app_prod module can be imported (top-level only)."""
        import middleware.app_prod as mod

        assert hasattr(mod, "build_combined_app")

    def test_build_combined_app_requires_gcs_facts_bucket(self) -> None:
        """Factory raises RuntimeError if GCS_FACTS_BUCKET is not set."""
        env = {
            "GCP_EXECUTION_ENV": "cloudrun",
            "ARCHITECTURE_PROFILE": "v3",
            "GCS_TRACES_BUCKET": "test-traces",
            "WORKOS_CLIENT_ID": "client_test",
            "WORKOS_API_KEY": "sk_test",
            "MEM0_API_KEY": "mem0_test",
            "LANGFUSE_PUBLIC_KEY": "pk_test",
            "LANGFUSE_SECRET_KEY": "sk_test",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("GCS_FACTS_BUCKET", None)
            with pytest.raises(RuntimeError, match="GCS_FACTS_BUCKET"):
                from middleware.app_prod import build_combined_app
                build_combined_app()

    def test_build_combined_app_requires_gcs_traces_bucket(self) -> None:
        """Factory raises RuntimeError if GCS_TRACES_BUCKET is not set."""
        env = {
            "GCP_EXECUTION_ENV": "cloudrun",
            "ARCHITECTURE_PROFILE": "v3",
            "GCS_FACTS_BUCKET": "test-facts",
            "WORKOS_CLIENT_ID": "client_test",
            "WORKOS_API_KEY": "sk_test",
            "MEM0_API_KEY": "mem0_test",
            "LANGFUSE_PUBLIC_KEY": "pk_test",
            "LANGFUSE_SECRET_KEY": "sk_test",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("GCS_TRACES_BUCKET", None)
            with pytest.raises(RuntimeError, match="GCS_TRACES_BUCKET"):
                from middleware.app_prod import build_combined_app
                build_combined_app()


class TestAppProdHealthz:
    """Integration test: build_combined_app healthz works pre-auth."""

    @pytest.fixture
    def prod_client(self):
        """Build the app with all GCP services mocked."""
        env = {
            "GCP_EXECUTION_ENV": "cloudrun",
            "ARCHITECTURE_PROFILE": "v3",
            "GCS_FACTS_BUCKET": "test-facts",
            "GCS_TRACES_BUCKET": "test-traces",
            "AGENT_FACTS_SECRET": "test-secret",
            "WORKOS_CLIENT_ID": "client_test",
            "WORKOS_API_KEY": "sk_test",
            "MEM0_API_KEY": "mem0_test",
            "LANGFUSE_PUBLIC_KEY": "pk_test",
            "LANGFUSE_SECRET_KEY": "sk_test",
            "DATABASE_URL": "postgresql://test:test@localhost/test",
        }

        mock_gcs_registry = MagicMock()
        mock_gcs_sink = MagicMock()
        mock_reader = MagicMock()
        mock_reader.health_posture.return_value = {
            "enabled": False,
            "downgrade_enabled": False,
            "source": "default",
        }

        build_components_return = (
            MagicMock(),
            MagicMock(),
            mock_gcs_registry,
            Path("/tmp/agent-cache"),
            mock_reader,
        )

        with patch.dict(os.environ, env, clear=False), \
             patch(
                 "middleware.app_prod.GcsTraceSink",
                 return_value=mock_gcs_sink,
             ), \
             patch(
                 "middleware.app_prod._load_graph_factory",
                 return_value=MagicMock(),
             ), \
             patch(
                 "middleware.composition.build_adapters",
                 return_value=MagicMock(profile="v3"),
             ):
            from importlib import reload
            import middleware.app_prod as mod
            reload(mod)
            with patch.object(
                mod, "_build_components", return_value=build_components_return
            ):
                app = mod.build_combined_app()

        from fastapi.testclient import TestClient
        return TestClient(app, raise_server_exceptions=False)

    def test_healthz_returns_200(self, prod_client) -> None:
        r = prod_client.get("/healthz")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["mode"] == "combined"

    def test_run_stream_rejects_missing_bearer(self, prod_client) -> None:
        r = prod_client.post("/run/stream", json={"input": {}})
        assert r.status_code == 401


def _build_crud_client(
    *,
    memory_service: object | None = "default",
    subject: str = "user_01CRUDSUBJECT",
):
    """Build a combined-app TestClient wired for the thread/memory CRUD surface.

    Infra (JWT/GCS/Postgres/runtime) is mocked; the thread store is the real
    in-memory ``_ThreadStore`` and ``memory_service`` is a real
    ``LongTermMemoryService(InMemoryMemoryBackend())`` by default so the routes
    exercise genuine owner-scoping. Pass ``memory_service=None`` to assert the
    503 "memory unavailable" degradation path.

    Returns ``(TestClient, subject)``.
    """
    from importlib import reload

    from services.long_term_memory import (
        InMemoryMemoryBackend,
        LongTermMemoryService,
    )

    if memory_service == "default":
        memory_service = LongTermMemoryService(InMemoryMemoryBackend())

    claims = MagicMock(subject=subject)
    mock_jwt = MagicMock()
    mock_jwt.verify.return_value = claims

    mock_adapters = MagicMock()
    mock_adapters.profile = "v3"
    mock_adapters.jwt_verifier = mock_jwt

    identity = AgentFacts(
        agent_id=subject,
        agent_name=subject,
        owner=subject,
        version="1.0.0",
        description="CRUD test identity",
        capabilities=[Capability(name="delegate.subagent.*")],
        status=IdentityStatus.ACTIVE,
    )
    mock_registry = MagicMock()
    mock_registry.get.return_value = identity

    # Full typed component bag so memory_service reaches the route wiring.
    mock_components = MagicMock()
    mock_components.agent_facts_registry = mock_registry
    mock_components.memory_service = memory_service

    env = {
        "GCP_EXECUTION_ENV": "cloudrun",
        "ARCHITECTURE_PROFILE": "v3",
        "GCS_FACTS_BUCKET": "test-facts",
        "GCS_TRACES_BUCKET": "test-traces",
        "AGENT_FACTS_SECRET": "test-secret",
        "WORKOS_CLIENT_ID": "client_test",
        "WORKOS_API_KEY": "sk_test",
        "MEM0_API_KEY": "mem0_test",
        "LANGFUSE_PUBLIC_KEY": "pk_test",
        "LANGFUSE_SECRET_KEY": "sk_test",
        "DATABASE_URL": "postgresql://test:test@localhost/test",
    }

    build_components_return = (
        MagicMock(),  # agent_config
        MagicMock(),  # tool_registry
        mock_registry,
        Path("/tmp/agent-cache"),
        MagicMock(),  # goal_judge_config_reader
    )

    with patch.dict(os.environ, env, clear=False), \
         patch("middleware.app_prod.GcsTraceSink", return_value=MagicMock()), \
         patch(
             "middleware.app_prod._load_graph_factory",
             return_value=MagicMock(),
         ), \
         patch(
             "middleware.composition.build_adapters",
             return_value=mock_adapters,
         ), \
         patch(
             "middleware.app_prod.LangGraphRuntime",
             return_value=MagicMock(),
         ):
        import middleware.app_prod as mod

        reload(mod)
        with patch.object(
            mod, "_build_components", return_value=build_components_return
        ), patch.object(
            mod, "_build_agent_components", return_value=mock_components
        ):
            app = mod.build_combined_app()

    from fastapi.testclient import TestClient

    return TestClient(app, raise_server_exceptions=False), subject


_AUTH = {"Authorization": "Bearer test-token"}


class TestAppProdThreadCrud:
    """Piece A: the combined prod app serves the /agent/threads surface.

    Failure paths first (missing bearer 401; cross-user 404) per TDD §OP-4.
    """

    def test_list_threads_rejects_missing_bearer(self) -> None:
        client, _ = _build_crud_client()
        r = client.get("/agent/threads")
        assert r.status_code == 401

    def test_create_then_list_roundtrip(self) -> None:
        client, subject = _build_crud_client()
        created = client.post(
            "/agent/threads",
            json={"user_id": subject, "metadata": {"first_message": "hi there"}},
            headers=_AUTH,
        )
        assert created.status_code == 200
        tid = created.json()["thread_id"]
        assert created.json()["title"] == "hi there"

        listed = client.get("/agent/threads", headers=_AUTH)
        assert listed.status_code == 200
        ids = [t["thread_id"] for t in listed.json()["threads"]]
        assert tid in ids

    def test_get_rename_archive_lifecycle(self) -> None:
        client, subject = _build_crud_client()
        tid = client.post(
            "/agent/threads",
            json={"user_id": subject, "metadata": {}},
            headers=_AUTH,
        ).json()["thread_id"]

        got = client.get(f"/agent/threads/{tid}", headers=_AUTH)
        assert got.status_code == 200

        renamed = client.patch(
            f"/agent/threads/{tid}",
            json={"title": "Renamed"},
            headers=_AUTH,
        )
        assert renamed.status_code == 200
        assert renamed.json()["title"] == "Renamed"

        archived = client.delete(f"/agent/threads/{tid}", headers=_AUTH)
        assert archived.status_code == 200
        # Archived threads drop out of list and get.
        assert client.get(f"/agent/threads/{tid}", headers=_AUTH).status_code == 404
        listed = client.get("/agent/threads", headers=_AUTH).json()
        assert tid not in [t["thread_id"] for t in listed["threads"]]


class TestAppProdMemoryCrud:
    """Piece A: the combined prod app serves the /agent/memory surface,
    owner-scoped, with a 503 degrade when the service is unwired."""

    def test_list_memory_rejects_missing_bearer(self) -> None:
        client, _ = _build_crud_client()
        r = client.get("/agent/memory")
        assert r.status_code == 401

    def test_memory_unavailable_returns_503(self) -> None:
        client, _ = _build_crud_client(memory_service=None)
        r = client.get("/agent/memory", headers=_AUTH)
        assert r.status_code == 503

    def test_create_list_delete_roundtrip(self) -> None:
        client, _ = _build_crud_client()
        created = client.post(
            "/agent/memory",
            json={"content": "prefers metric units", "type": "semantic"},
            headers=_AUTH,
        )
        assert created.status_code == 200
        key = created.json()["key"]

        listed = client.get("/agent/memory", headers=_AUTH)
        assert listed.status_code == 200
        contents = [i["content"] for i in listed.json()["items"]]
        assert "prefers metric units" in contents

        deleted = client.delete(f"/agent/memory/{key}", headers=_AUTH)
        assert deleted.status_code == 200
        after = client.get("/agent/memory", headers=_AUTH).json()
        assert key not in [i["key"] for i in after["items"]]

    def test_memory_is_owner_scoped_not_client_supplied(self) -> None:
        """The route writes under identity.owner — content for one subject is
        invisible to a different subject (cross-user-leak guard)."""
        shared_mem = None
        from services.long_term_memory import (
            InMemoryMemoryBackend,
            LongTermMemoryService,
        )

        shared_mem = LongTermMemoryService(InMemoryMemoryBackend())
        alice, _ = _build_crud_client(
            memory_service=shared_mem, subject="user_ALICE"
        )
        bob, _ = _build_crud_client(
            memory_service=shared_mem, subject="user_BOB"
        )
        alice.post(
            "/agent/memory",
            json={"content": "alice secret", "type": "semantic"},
            headers=_AUTH,
        )
        bob_items = bob.get("/agent/memory", headers=_AUTH).json()["items"]
        assert "alice secret" not in [i["content"] for i in bob_items]


class TestAppProdAutoProvision:
    """Verify missing AgentFacts triggers auto-registration instead of 500."""

    @pytest.fixture
    def auto_provision_client(self):
        env = {
            "GCP_EXECUTION_ENV": "cloudrun",
            "ARCHITECTURE_PROFILE": "v3",
            "GCS_FACTS_BUCKET": "test-facts",
            "GCS_TRACES_BUCKET": "test-traces",
            "AGENT_FACTS_SECRET": "test-secret",
            "WORKOS_CLIENT_ID": "client_test",
            "WORKOS_API_KEY": "sk_test",
            "MEM0_API_KEY": "mem0_test",
            "LANGFUSE_PUBLIC_KEY": "pk_test",
            "LANGFUSE_SECRET_KEY": "sk_test",
            "DATABASE_URL": "postgresql://test:test@localhost/test",
        }

        subject = "user_01TESTSUBJECT"
        claims = MagicMock(subject=subject)
        mock_jwt_verifier = MagicMock()
        mock_jwt_verifier.verify.return_value = claims

        mock_adapters = MagicMock()
        mock_adapters.profile = "v3"
        mock_adapters.jwt_verifier = mock_jwt_verifier

        provisioned = AgentFacts(
            agent_id=subject,
            agent_name=subject,
            owner=subject,
            version="1.0.0",
            description="Auto-provisioned on first authenticated request",
            capabilities=[Capability(name="delegate.subagent.*")],
            status=IdentityStatus.ACTIVE,
        )
        mock_registry = MagicMock()
        mock_registry.get.side_effect = KeyError(subject)
        mock_registry.register.return_value = provisioned

        async def _empty_run(*_args, **_kwargs):
            return
            yield  # pragma: no cover — makes this an async generator

        mock_runtime = MagicMock()
        mock_runtime.run = _empty_run

        mock_pg = MagicMock()
        mock_pg.saver = MagicMock()
        mock_pg_cm = AsyncMock()
        mock_pg_cm.__aenter__.return_value = mock_pg
        mock_pg_cm.__aexit__.return_value = None

        build_components_return = (
            MagicMock(),
            MagicMock(),
            mock_registry,
            Path("/tmp/agent-cache"),
            MagicMock(),
        )

        with patch.dict(os.environ, env, clear=False), \
             patch(
                 "middleware.app_prod.GcsTraceSink",
                 return_value=MagicMock(),
             ), \
             patch(
                 "middleware.app_prod._load_graph_factory",
                 return_value=MagicMock(),
             ), \
             patch(
                 "middleware.composition.build_adapters",
                 return_value=mock_adapters,
             ), \
             patch(
                 "agent_ui_adapter.adapters.runtime.postgres_saver.PostgresCheckpointer.from_env",
                 return_value=mock_pg_cm,
             ), \
             patch(
                 "middleware.app_prod.LangGraphRuntime",
                 return_value=mock_runtime,
             ):
            from importlib import reload
            import middleware.app_prod as mod
            reload(mod)
            with patch.object(
                mod,
                "_build_components",
                return_value=build_components_return,
            ):
                app = mod.build_combined_app()
            app.state.runtime = mock_runtime

        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)
        return client, mock_registry, subject

    def test_run_stream_auto_provisions_missing_identity(
        self, auto_provision_client
    ) -> None:
        client, mock_registry, subject = auto_provision_client
        r = client.post(
            "/run/stream",
            json={"input": {}},
            headers={"Authorization": "Bearer test-token"},
        )
        assert r.status_code == 200
        mock_registry.get.assert_called_once_with(subject)
        mock_registry.register.assert_called_once()
        registered_facts = mock_registry.register.call_args[0][0]
        assert registered_facts.agent_id == subject
        assert mock_registry.register.call_args[1]["registered_by"] == (
            "app_prod:auto_provision"
        )


# ─────────────────────────────────────────────────────────────────────
# Phase 3 — Telemetry Wiring in _generate()
#
# Layer: L2 (Reproducible Reality)
# Strategy: Contract-driven TDD with in-memory exporter stub
# Acceptance criteria (langfuse_gcp_integration.plan.md §Phase 3):
#   - Mock exporter receives run.started exactly once per request
#   - Mock exporter receives run.finished exactly once
#   - Exporter raising on export_event() does not break SSE
# Anti-patterns avoided:
#   - Mock Addiction: real in-memory StubTelemetryExporter; infra mocks only
#   - Gap Blindness: failure paths tested before acceptance paths
#   - Tautological: observable exporter state, not algorithm reimplementation
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


def _build_telemetry_client(
    domain_events,
    *,
    stub_exporter: _StubTelemetryExporter | None = None,
    runtime_error: Exception | None = None,
):
    """Build a FastAPI TestClient wired with a StubTelemetryExporter.

    Returns ``(TestClient, StubTelemetryExporter, subject_string)``.
    Infrastructure mocks (JWT, GCS, Postgres) isolate external I/O;
    the exporter is a real in-memory implementation.
    """
    from importlib import reload

    if stub_exporter is None:
        stub_exporter = _StubTelemetryExporter()

    subject = "user-test-telemetry"
    claims = MagicMock(subject=subject)
    mock_jwt = MagicMock()
    mock_jwt.verify.return_value = claims

    mock_adapters = MagicMock()
    mock_adapters.profile = "v3"
    mock_adapters.jwt_verifier = mock_jwt
    mock_adapters.telemetry_exporter = stub_exporter

    async def _mock_run(*args, **kwargs):
        for ev in domain_events:
            yield ev
        if runtime_error:
            raise runtime_error

    mock_runtime = MagicMock()
    mock_runtime.run = _mock_run

    mock_registry = MagicMock()
    mock_registry.get.return_value = AgentFacts(
        agent_id=subject,
        agent_name=subject,
        owner=subject,
        version="1.0.0",
        description="Test identity",
        capabilities=[Capability(name="delegate.subagent.*")],
        status=IdentityStatus.ACTIVE,
    )

    env = {
        "GCP_EXECUTION_ENV": "cloudrun",
        "ARCHITECTURE_PROFILE": "v3",
        "GCS_FACTS_BUCKET": "test-facts",
        "GCS_TRACES_BUCKET": "test-traces",
        "AGENT_FACTS_SECRET": "test-secret",
        "WORKOS_CLIENT_ID": "client_test",
        "WORKOS_API_KEY": "sk_test",
        "MEM0_API_KEY": "mem0_test",
        "LANGFUSE_PUBLIC_KEY": "pk_test",
        "LANGFUSE_SECRET_KEY": "sk_test",
        "DATABASE_URL": "postgresql://test:test@localhost/test",
    }

    build_components_return = (
        MagicMock(),  # agent_config
        MagicMock(),  # tool_registry
        mock_registry,
        Path("/tmp/agent-cache"),
        MagicMock(),  # goal_judge_config_reader
    )

    with patch.dict(os.environ, env, clear=False), \
         patch("middleware.app_prod.GcsTraceSink", return_value=MagicMock()), \
         patch(
             "middleware.app_prod._load_graph_factory",
             return_value=MagicMock(),
         ), \
         patch(
             "middleware.composition.build_adapters",
             return_value=mock_adapters,
         ), \
         patch(
             "middleware.app_prod.LangGraphRuntime",
             return_value=mock_runtime,
         ):
        import middleware.app_prod as mod

        reload(mod)
        with patch.object(
            mod, "_build_components", return_value=build_components_return
        ):
            app = mod.build_combined_app()
        app.state.runtime = mock_runtime

    from fastapi.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=False)
    return client, stub_exporter, subject


def _post_stream(client):
    """POST /run/stream with valid auth header."""
    return client.post(
        "/run/stream",
        json={"input": {"messages": [{"content": "hello"}]}},
        headers={"Authorization": "Bearer test-token"},
    )


class TestTelemetryWiring:
    """Phase 3: _generate() wires domain events to telemetry bridge.

    Tests ordered failure-path-first per TDD §Operating Principle 4.
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
        client, _, _ = _build_telemetry_client(events, stub_exporter=stub)
        r = _post_stream(client)
        assert r.status_code == 200

    def test_safety_net_emits_run_finished_on_stream_error(self) -> None:
        """Finally block emits run.finished when stream errors before
        RunFinishedDomain."""
        events = [
            RunStartedDomain(trace_id="t-1", run_id="r-1", thread_id="th-1"),
        ]
        client, stub, _ = _build_telemetry_client(
            events, runtime_error=RuntimeError("boom")
        )
        r = _post_stream(client)
        assert r.status_code == 200

        run_finished = [e for e in stub.events if e["name"] == "run.finished"]
        assert len(run_finished) == 1, (
            f"Expected 1 run.finished, got {len(run_finished)}"
        )
        assert run_finished[0]["attributes"]["errored"] is True

    def test_no_double_run_finished(self) -> None:
        """Bridge handles RunFinishedDomain; finally block does not
        duplicate."""
        events = [
            RunStartedDomain(trace_id="t-1", run_id="r-1", thread_id="th-1"),
            RunFinishedDomain(
                trace_id="t-1", run_id="r-1", thread_id="th-1", error=None
            ),
        ]
        client, stub, _ = _build_telemetry_client(events)
        r = _post_stream(client)
        assert r.status_code == 200

        run_finished = [e for e in stub.events if e["name"] == "run.finished"]
        assert len(run_finished) == 1, (
            f"Expected exactly 1 run.finished, got {len(run_finished)}"
        )

    def test_safety_net_skipped_when_no_events(self) -> None:
        """No run.finished emitted when stream yields zero events."""
        client, stub, _ = _build_telemetry_client([])
        r = _post_stream(client)
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
            ToolResultReceived(
                trace_id="t-1", tool_call_id="tc-1", result="file.txt"
            ),
            RunFinishedDomain(
                trace_id="t-1", run_id="r-1", thread_id="th-1", error=None
            ),
        ]
        client, stub, _ = _build_telemetry_client(events)
        r = _post_stream(client)
        assert r.status_code == 200

        run_started = [e for e in stub.events if e["name"] == "run.started"]
        assert len(run_started) == 1

    def test_run_finished_exactly_once(self) -> None:
        """run.finished exported exactly once per request."""
        events = [
            RunStartedDomain(trace_id="t-1", run_id="r-1", thread_id="th-1"),
            ToolCallStarted(
                trace_id="t-1",
                tool_call_id="tc-1",
                tool_name="shell",
                args_json='{"cmd":"ls"}',
            ),
            ToolResultReceived(
                trace_id="t-1", tool_call_id="tc-1", result="file.txt"
            ),
            RunFinishedDomain(
                trace_id="t-1", run_id="r-1", thread_id="th-1", error=None
            ),
        ]
        client, stub, _ = _build_telemetry_client(events)
        r = _post_stream(client)
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
            ToolResultReceived(
                trace_id="t-1", tool_call_id="tc-1", result="file.txt"
            ),
            RunFinishedDomain(
                trace_id="t-1", run_id="r-1", thread_id="th-1", error=None
            ),
        ]
        client, stub, _ = _build_telemetry_client(events)
        r = _post_stream(client)
        assert r.status_code == 200

        # Phase 3: started events buffer; one merged obs per LLM/tool call.
        exported_names = [e["name"] for e in stub.events]
        assert exported_names == [
            "run.started",
            "llm.call",
            "tool.shell",
            "run.finished",
        ]

    def test_subject_passed_to_bridge(self) -> None:
        """claims.subject forwarded to telemetry bridge events."""
        events = [
            RunStartedDomain(trace_id="t-1", run_id="r-1", thread_id="th-1"),
            RunFinishedDomain(
                trace_id="t-1", run_id="r-1", thread_id="th-1", error=None
            ),
        ]
        client, stub, subject = _build_telemetry_client(events)
        r = _post_stream(client)
        assert r.status_code == 200

        for event in stub.events:
            assert event["attributes"].get("subject") == subject


# ─────────────────────────────────────────────────────────────────────
# BlackBox→Langfuse relay lifecycle (Blocker 1)
#
# Layer: L2 — production lifespan must start the in-process relay (matching
#   dev parity in middleware/__main__.py) and tear it down on shutdown.
# Acceptance (blackbox_langfuse_gcp_deploy.plan.md §Blocker 1):
#   - lifespan starts relay.run_forever as an asyncio task when relay present
#   - finally block calls relay.stop() and cancels the task on shutdown
#   - no relay started / no crash when adapters.black_box_relay is None (off)
# Anti-patterns avoided:
#   - Mock Addiction: real in-memory _StubRelay observed by behavior, not config
#   - Gap Blindness: off/None failure path covered alongside happy path
# ─────────────────────────────────────────────────────────────────────


class _StubRelay:
    """In-memory relay recording start/stop for lifecycle assertions.

    Shape-compatible with BlackBoxToTelemetryRelay's lifespan usage:
    ``run_forever(interval_s=...)`` coroutine + ``stop()``.
    """

    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self._stop = False
        self.injected_registry: object = None

    def set_agent_facts_registry(self, registry: object) -> None:
        # E7: composition root injects the AgentFacts registry before start.
        self.injected_registry = registry

    async def run_forever(self, interval_s: float = 1.0) -> None:
        self.started = True
        while not self._stop:
            await asyncio.sleep(0.005)

    def stop(self) -> None:
        self.stopped = True
        self._stop = True


@contextmanager
def _prod_app_with_relay(relay):
    """Build the prod app with a controllable ``black_box_relay`` on adapters.

    Yields ``(app, mock_telemetry)`` while infra patches (JWT/GCS/Postgres/
    runtime) stay active, so the FastAPI lifespan can run under the mocks.
    The relay is a real in-memory stub so we assert observable lifecycle.
    """
    from importlib import reload

    mock_telemetry = MagicMock()
    mock_adapters = MagicMock()
    mock_adapters.profile = "v3"
    mock_adapters.black_box_relay = relay
    mock_adapters.telemetry_exporter = mock_telemetry

    mock_pg = MagicMock()
    mock_pg.saver = MagicMock()
    mock_pg_cm = AsyncMock()
    mock_pg_cm.__aenter__.return_value = mock_pg
    mock_pg_cm.__aexit__.return_value = None

    build_components_return = (
        MagicMock(),  # agent_config
        MagicMock(),  # tool_registry
        MagicMock(),  # agent_facts_registry
        Path("/tmp/agent-cache"),
        MagicMock(),  # goal_judge_config_reader
    )

    env = {
        "GCP_EXECUTION_ENV": "cloudrun",
        "ARCHITECTURE_PROFILE": "v3",
        "GCS_FACTS_BUCKET": "test-facts",
        "GCS_TRACES_BUCKET": "test-traces",
        "AGENT_FACTS_SECRET": "test-secret",
        "WORKOS_CLIENT_ID": "client_test",
        "WORKOS_API_KEY": "sk_test",
        "MEM0_API_KEY": "mem0_test",
        "LANGFUSE_PUBLIC_KEY": "pk_test",
        "LANGFUSE_SECRET_KEY": "sk_test",
        "DATABASE_URL": "postgresql://test:test@localhost/test",
    }

    with patch.dict(os.environ, env, clear=False), \
         patch(
             "middleware.composition.build_adapters",
             return_value=mock_adapters,
         ), \
         patch(
             "agent_ui_adapter.adapters.runtime.postgres_saver."
             "PostgresCheckpointer.from_env",
             return_value=mock_pg_cm,
         ):
        import middleware.app_prod as mod

        # Reload first, then patch module attributes: reload() re-binds the
        # module's imported names to the real implementations, so patches must
        # be applied to the reloaded module (and stay active through lifespan).
        reload(mod)
        with patch.object(mod, "GcsTraceSink", return_value=MagicMock()), \
             patch.object(mod, "_load_graph_factory", return_value=MagicMock()), \
             patch.object(mod, "LangGraphRuntime", return_value=MagicMock()), \
             patch.object(
                 mod, "_build_components", return_value=build_components_return
             ):
            app = mod.build_combined_app()
            # Keep patches active while the caller drives the lifespan.
            yield app, mock_telemetry


class TestAppProdRelayLifecycle:
    """Blocker 1: production lifespan runs the in-process relay."""

    def test_relay_started_and_stopped_in_lifespan(self) -> None:
        """ACCEPT: relay.run_forever runs during lifespan; stop() on shutdown."""
        from fastapi.testclient import TestClient

        relay = _StubRelay()
        with _prod_app_with_relay(relay) as (app, mock_telemetry):
            with TestClient(app, raise_server_exceptions=False) as client:
                # A request pumps the loop so run_forever's body executes.
                assert client.get("/healthz").status_code == 200

            assert relay.started is True, (
                "relay.run_forever should have been scheduled"
            )
            assert relay.stopped is True, "relay.stop() should run on shutdown"
            mock_telemetry.shutdown.assert_called_once()

    def test_no_relay_when_mode_off(self) -> None:
        """ACCEPT: adapters.black_box_relay=None (mode=off) boots with no relay."""
        from fastapi.testclient import TestClient

        with _prod_app_with_relay(None) as (app, mock_telemetry):
            with TestClient(app, raise_server_exceptions=False) as client:
                assert client.get("/healthz").status_code == 200

            # Telemetry exporter still shuts down even when no relay is wired.
            mock_telemetry.shutdown.assert_called_once()
