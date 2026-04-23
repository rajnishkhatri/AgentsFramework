"""US-6.2: Pre-flight JWT verification dependency.

Per AGENT_UI_ADAPTER_SPRINTS.md S6 US-6.2. Failure paths first per TAP-4.

Uses an InMemoryJwtVerifier so tests are deterministic and require no
external SDK. Production wires a real verifier (WorkOS / Cognito / OAuth)
behind the same JwtVerifier Protocol via the composition root.
"""

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
from trust.models import AgentFacts


def _facts(agent_id: str = "a1") -> AgentFacts:
    return AgentFacts(
        agent_id=agent_id, agent_name="Bot", owner="team", version="1.0.0"
    )


def _verifier(claims: JwtClaims, agent_id: str = "a1") -> InMemoryJwtVerifier:
    """Verifier that maps token 'good' → claims; everything else → invalid."""
    return InMemoryJwtVerifier(token_to_claims={"good": claims})


def _client(verifier=None, identities=None) -> TestClient:
    return TestClient(
        build_app(
            runtime=MockRuntime(events=[]),
            jwt_verifier=verifier or InMemoryJwtVerifier(token_to_claims={}),
            agent_facts={f.agent_id: f for f in (identities or [])},
        )
    )


# ── Failure paths first ───────────────────────────────────────────────


class TestJwtPreflight:
    def test_missing_authorization_header_returns_401(self) -> None:
        client = _client()
        r = client.post("/agent/runs/stream", json={"thread_id": "t", "input": {}})
        assert r.status_code == 401
        assert r.json()["detail"]

    def test_malformed_bearer_returns_401(self) -> None:
        client = _client()
        r = client.post(
            "/agent/runs/stream",
            json={"thread_id": "t", "input": {}},
            headers={"Authorization": "NotBearer xyz"},
        )
        assert r.status_code == 401

    def test_invalid_token_returns_401(self) -> None:
        client = _client()
        r = client.post(
            "/agent/runs/stream",
            json={"thread_id": "t", "input": {}},
            headers={"Authorization": "Bearer wrong"},
        )
        assert r.status_code == 401

    def test_expired_token_returns_401_with_reason(self) -> None:
        claims = JwtClaims(
            subject="a1",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        client = _client(_verifier(claims), [_facts()])
        r = client.post(
            "/agent/runs/stream",
            json={"thread_id": "t", "input": {}},
            headers={"Authorization": "Bearer good"},
        )
        assert r.status_code == 401
        assert "expired" in r.json()["detail"].lower()

    def test_unknown_identity_returns_401(self) -> None:
        claims = JwtClaims(
            subject="a-unknown",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        client = _client(_verifier(claims), [_facts()])
        r = client.post(
            "/agent/runs/stream",
            json={"thread_id": "t", "input": {}},
            headers={"Authorization": "Bearer good"},
        )
        assert r.status_code == 401
        assert "identity" in r.json()["detail"].lower()


# ── Acceptance: valid token + active identity ─────────────────────────


class TestJwtAcceptance:
    def test_valid_token_admits_request(self) -> None:
        claims = JwtClaims(
            subject="a1",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        client = _client(_verifier(claims), [_facts()])
        r = client.post(
            "/agent/runs/stream",
            json={"thread_id": "t", "input": {}},
            headers={"Authorization": "Bearer good"},
        )
        # MockRuntime yields no events; sentinel comes; status 200.
        assert r.status_code == 200
