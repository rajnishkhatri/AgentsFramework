"""Tests for middleware.app_prod — production combined backend.

Verifies:
  * build_combined_app() factory boots cleanly with mocked GCP deps
  * /healthz responds 200 pre-auth (Cloud Run liveness)
  * /run/stream rejects missing bearer (401)
  * Dockerfile.backend and Dockerfile.frontend exist with expected content
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


AGENT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestDockerfiles:
    """Verify Docker assets exist and contain expected markers."""

    def test_dockerfile_backend_exists(self) -> None:
        path = AGENT_ROOT / "Dockerfile.backend"
        assert path.exists(), "Dockerfile.backend must exist at repo root"

    def test_dockerfile_backend_uses_python_311(self) -> None:
        content = (AGENT_ROOT / "Dockerfile.backend").read_text()
        assert "python:3.11" in content

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

        with patch.dict(os.environ, env, clear=False), \
             patch(
                 "middleware.app_prod.AgentFactsGcsRegistry",
                 return_value=mock_gcs_registry,
             ), \
             patch(
                 "middleware.app_prod.GcsTraceSink",
                 return_value=mock_gcs_sink,
             ), \
             patch(
                 "middleware.app_prod._load_graph_factory",
                 return_value=MagicMock(),
             ):
            from importlib import reload
            import middleware.app_prod as mod
            reload(mod)
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
