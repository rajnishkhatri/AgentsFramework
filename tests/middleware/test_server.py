"""Tests for ``middleware.server`` -- the FastAPI app that fronts the
``agent_ui_adapter`` runtime.

Per Sprint 1 §S1.1.1 acceptance criteria:

  * App boots from a typed ``MiddlewareAdapters`` bag (rule C2).
  * ``/healthz`` returns 200 without a token (liveness probe must work
    pre-auth so Cloud Run can boot).
  * Authenticated routes reject:
      - missing bearer       -> 401
      - invalid token        -> 401
      - expired token        -> 401
  * Authenticated routes accept a valid token -> 2xx.
  * Tool ACL middleware blocks the ``shell`` tool for ``beta`` callers.

The tests use ``WorkOSJwtVerifier`` wired with an in-memory JWKS
fixture (no network) and ``WorkOSRoleAcl`` directly. Same L2 contract
test pattern as ``test_workos_jwt_verifier.py``.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient

from middleware.adapters.acl.workos_role_acl import WorkOSRoleAcl
from middleware.adapters.auth.workos_jwt_verifier import WorkOSJwtVerifier
from middleware.adapters.memory.mem0_cloud_client import Mem0CloudClient
from middleware.adapters.observability.langfuse_cloud_exporter import (
    LangfuseCloudExporter,
)
from middleware.composition import MiddlewareAdapters


@pytest.fixture
def adapters_test(
    jwks_provider: Callable[[], dict[str, Any]],
    expected_issuer: str,
    expected_client_id: str,
) -> MiddlewareAdapters:
    """A MiddlewareAdapters bag wired with test-friendly substitutes:

      * JWT verifier uses the in-memory JWKS fixture (no network).
      * Memory + telemetry adapters are real classes but never invoked
        in these tests -- they're constructed with dummy creds.
    """
    return MiddlewareAdapters(
        profile="v3",
        jwt_verifier=WorkOSJwtVerifier(
            jwks_fetcher=jwks_provider,
            expected_issuer=expected_issuer,
            expected_client_id=expected_client_id,
            expected_token_use="access",
        ),
        tool_acl=WorkOSRoleAcl(
            role_to_tools={
                "admin": frozenset({"shell", "file_io", "web_search"}),
                "beta": frozenset({"file_io", "web_search"}),
                "viewer": frozenset(),
            },
            known_tools=frozenset({"shell", "file_io", "web_search"}),
        ),
        memory_client=Mem0CloudClient(api_key="dummy"),
        telemetry_exporter=LangfuseCloudExporter(
            public_key="pk-dummy",
            secret_key="sk-dummy",
        ),
    )


@pytest.fixture
def client(adapters_test: MiddlewareAdapters) -> TestClient:
    from middleware.server import build_middleware_app

    app = build_middleware_app(adapters=adapters_test)
    return TestClient(app)


# ─────────────────────────────────────────────────────────────────────
# Liveness
# ─────────────────────────────────────────────────────────────────────


class TestLiveness:
    def test_healthz_returns_200_without_token(
        self, client: TestClient
    ) -> None:
        """Cloud Run liveness probe must work pre-auth."""
        r = client.get("/healthz")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "profile" in body


# ─────────────────────────────────────────────────────────────────────
# Auth rejection paths (write FIRST per TAP-4)
# ─────────────────────────────────────────────────────────────────────


class TestAuthRejectionPaths:
    def test_missing_bearer_returns_401(self, client: TestClient) -> None:
        r = client.get("/me")
        assert r.status_code == 401

    def test_malformed_authorization_header_returns_401(
        self, client: TestClient
    ) -> None:
        r = client.get("/me", headers={"Authorization": "NotBearer xxx"})
        assert r.status_code == 401

    def test_invalid_token_returns_401(self, client: TestClient) -> None:
        r = client.get(
            "/me", headers={"Authorization": "Bearer not-a-jwt"}
        )
        assert r.status_code == 401

    def test_expired_token_returns_401(
        self,
        client: TestClient,
        make_token: Callable[..., str],
    ) -> None:
        from datetime import UTC, datetime, timedelta

        token = make_token(
            expires_at=datetime.now(UTC) - timedelta(seconds=10),
        )
        r = client.get(
            "/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 401

    def test_wrong_issuer_returns_401(
        self,
        client: TestClient,
        make_token: Callable[..., str],
    ) -> None:
        token = make_token(issuer="https://attacker.example.com")
        r = client.get(
            "/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 401


# ─────────────────────────────────────────────────────────────────────
# Auth happy path
# ─────────────────────────────────────────────────────────────────────


class TestAuthAcceptance:
    def test_valid_token_returns_subject(
        self,
        client: TestClient,
        make_token: Callable[..., str],
    ) -> None:
        token = make_token(subject="user_happy", roles=["beta"])
        r = client.get(
            "/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["subject"] == "user_happy"
        assert body["roles"] == ["beta"]


# ─────────────────────────────────────────────────────────────────────
# Tool-ACL enforcement on the policy-decision endpoint
# ─────────────────────────────────────────────────────────────────────


class TestToolAclEnforcement:
    """Sprint 1 §S1.3.1 acceptance: shell is denied to non-admins."""

    def test_beta_calling_shell_returns_403(
        self,
        client: TestClient,
        make_token: Callable[..., str],
    ) -> None:
        token = make_token(roles=["beta"])
        r = client.post(
            "/acl/decide",
            headers={"Authorization": f"Bearer {token}"},
            json={"tool_name": "shell"},
        )
        assert r.status_code == 403
        assert "shell" in r.json()["detail"].lower()

    def test_admin_calling_shell_returns_200(
        self,
        client: TestClient,
        make_token: Callable[..., str],
    ) -> None:
        token = make_token(roles=["admin"])
        r = client.post(
            "/acl/decide",
            headers={"Authorization": f"Bearer {token}"},
            json={"tool_name": "shell"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["allowed"] is True

    def test_beta_calling_file_io_returns_200(
        self,
        client: TestClient,
        make_token: Callable[..., str],
    ) -> None:
        token = make_token(roles=["beta"])
        r = client.post(
            "/acl/decide",
            headers={"Authorization": f"Bearer {token}"},
            json={"tool_name": "file_io"},
        )
        assert r.status_code == 200
        assert r.json()["allowed"] is True

    def test_unknown_role_calling_anything_returns_403(
        self,
        client: TestClient,
        make_token: Callable[..., str],
    ) -> None:
        token = make_token(roles=["hacker"])
        r = client.post(
            "/acl/decide",
            headers={"Authorization": f"Bearer {token}"},
            json={"tool_name": "file_io"},
        )
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# langgraph.json contract
# ─────────────────────────────────────────────────────────────────────


class TestLangGraphConfig:
    """Sprint 1 §S1.1.1: graph is referenced via langgraph.json string,
    not via Python import.
    """

    def test_langgraph_json_exists(self) -> None:
        from pathlib import Path

        agent_root = Path(__file__).resolve().parent.parent.parent
        cfg = agent_root / "langgraph.json"
        assert cfg.exists(), "langgraph.json must exist at repo root"

    def test_langgraph_json_references_react_loop(self) -> None:
        import json
        from pathlib import Path

        agent_root = Path(__file__).resolve().parent.parent.parent
        cfg = json.loads((agent_root / "langgraph.json").read_text())
        assert "graphs" in cfg
        assert "react_loop" in cfg["graphs"]
        # The value is a *string reference* -- not a Python import. This
        # is what makes loading via langgraph.json compatible with the
        # F4 / M1 architecture rule.
        ref = cfg["graphs"]["react_loop"]
        assert ref == "orchestration.react_loop:build_graph"
