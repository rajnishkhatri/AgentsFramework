"""Contract tests for ``middleware.adapters.auth.workos_jwt_verifier``.

Layer: **L2 Reproducible Reality** (research/tdd_agentic_systems_prompt.md).
Strategy: **Contract-driven TDD** with mock JWKS provider -- never hits
the real WorkOS JWKS endpoint in CI.

Order per Sprint 1 §S1.2.1 acceptance criteria and TAP-4 / FD6.ADAPTER:
    Rejection paths FIRST (5):
        R1  missing token  -> MissingTokenError
        R2  expired token  -> ExpiredTokenError
        R3  wrong issuer   -> InvalidIssuerError
        R4  wrong client_id -> InvalidClientIdError
        R5  wrong token_use -> InvalidTokenUseError
    THEN acceptance (1):
        A1  valid token    -> JwtClaims with normalized fields

A 5:1 rejection-to-acceptance ratio per **Anti-Pattern 6 (Gap Blindness)**.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Callable

import pytest

from middleware.ports.jwt_verifier import (
    ExpiredTokenError,
    InvalidClientIdError,
    InvalidIssuerError,
    InvalidTokenError,
    InvalidTokenUseError,
    JwtClaims,
    JwtVerifier,
    MissingTokenError,
)


# Note: the verifier under test is constructed from a JWKS-dict provider
# (no network) -- this keeps the L2 contract test deterministic and fast.


@pytest.fixture
def verifier(
    jwks_provider: Callable[[], dict[str, Any]],
    expected_issuer: str,
    expected_client_id: str,
):
    """The system under test -- WorkOSJwtVerifier wired with a JWKS dict
    fetcher (no httpx, no network).
    """
    from middleware.adapters.auth.workos_jwt_verifier import (
        WorkOSJwtVerifier,
    )

    return WorkOSJwtVerifier(
        jwks_fetcher=jwks_provider,
        expected_issuer=expected_issuer,
        expected_client_id=expected_client_id,
        expected_token_use="access",
    )


# ─────────────────────────────────────────────────────────────────────
# REJECTION PATHS — write these FIRST. Per TAP-4 / FD6.ADAPTER.
# ─────────────────────────────────────────────────────────────────────


class TestRejectionPaths:
    """5 rejection scenarios. All MUST fail closed, with typed errors."""

    def test_R1_missing_token_raises_missing_token_error(
        self, verifier: JwtVerifier
    ) -> None:
        """R1: empty / None token must raise ``MissingTokenError``."""
        with pytest.raises(MissingTokenError):
            verifier.verify(None)
        with pytest.raises(MissingTokenError):
            verifier.verify("")
        with pytest.raises(MissingTokenError):
            verifier.verify("   ")

    def test_R2_expired_token_raises_expired_token_error(
        self,
        verifier: JwtVerifier,
        make_token: Callable[..., str],
    ) -> None:
        """R2: ``exp`` in the past must raise ``ExpiredTokenError``."""
        past = datetime.now(UTC) - timedelta(seconds=10)
        token = make_token(expires_at=past)
        with pytest.raises(ExpiredTokenError):
            verifier.verify(token)

    def test_R3_wrong_issuer_raises_invalid_issuer_error(
        self,
        verifier: JwtVerifier,
        make_token: Callable[..., str],
    ) -> None:
        """R3: ``iss`` must match expected_issuer exactly."""
        token = make_token(issuer="https://attacker.example.com")
        with pytest.raises(InvalidIssuerError):
            verifier.verify(token)

    def test_R4_wrong_client_id_raises_invalid_client_id_error(
        self,
        verifier: JwtVerifier,
        make_token: Callable[..., str],
    ) -> None:
        """R4: ``client_id`` must match expected_client_id exactly."""
        token = make_token(client_id="client_attacker")
        with pytest.raises(InvalidClientIdError):
            verifier.verify(token)

    def test_R5_wrong_token_use_raises_invalid_token_use_error(
        self,
        verifier: JwtVerifier,
        make_token: Callable[..., str],
    ) -> None:
        """R5: ``token_use`` must equal "access" -- ID/refresh tokens are
        rejected on API surfaces.
        """
        token = make_token(token_use="id")
        with pytest.raises(InvalidTokenUseError):
            verifier.verify(token)

    # Bonus rejections that are documented behavior of the port contract.

    def test_signature_tampering_raises_invalid_token_error(
        self,
        verifier: JwtVerifier,
        make_token: Callable[..., str],
    ) -> None:
        """Tampered tail bytes must fail signature verification."""
        token = make_token()
        tampered = token[:-10] + ("A" * 10)
        with pytest.raises(InvalidTokenError):
            verifier.verify(tampered)

    def test_unknown_kid_raises_invalid_token_error(
        self,
        verifier: JwtVerifier,
        make_token: Callable[..., str],
    ) -> None:
        """Header ``kid`` not present in the JWKS document -> reject."""
        token = make_token(kid="unknown-key-99")
        with pytest.raises(InvalidTokenError):
            verifier.verify(token)

    def test_malformed_token_raises_invalid_token_error(
        self,
        verifier: JwtVerifier,
    ) -> None:
        """Garbage bytes -- not three dot-separated base64 parts."""
        with pytest.raises(InvalidTokenError):
            verifier.verify("not-a-real-jwt")


# ─────────────────────────────────────────────────────────────────────
# ACCEPTANCE PATH — only one. Wrote AFTER all rejections.
# ─────────────────────────────────────────────────────────────────────


class TestAcceptancePath:
    def test_A1_valid_token_returns_normalized_claims(
        self,
        verifier: JwtVerifier,
        make_token: Callable[..., str],
        expected_issuer: str,
        expected_client_id: str,
    ) -> None:
        """A1: valid token -> ``JwtClaims`` with subject + roles
        normalized to the vendor-neutral wire shape.
        """
        token = make_token(
            subject="user_01HX",
            organization_id="org_01HX",
            roles=["beta"],
            permissions=["tool:file_io", "tool:web_search"],
        )
        claims = verifier.verify(token)

        assert isinstance(claims, JwtClaims)
        assert claims.subject == "user_01HX"
        assert claims.issuer == expected_issuer
        assert claims.client_id == expected_client_id
        assert claims.token_use == "access"
        assert claims.organization_id == "org_01HX"
        assert claims.roles == ("beta",)
        assert claims.permissions == ("tool:file_io", "tool:web_search")
        assert claims.expires_at > datetime.now(UTC)


# ─────────────────────────────────────────────────────────────────────
# Behavioral contract tests
# ─────────────────────────────────────────────────────────────────────


class TestBehavioralContract:
    def test_verifier_satisfies_jwt_verifier_protocol(
        self, verifier: JwtVerifier
    ) -> None:
        """Port-conformance check: WorkOSJwtVerifier IS a JwtVerifier."""
        assert isinstance(verifier, JwtVerifier)

    def test_verify_is_idempotent(
        self,
        verifier: JwtVerifier,
        make_token: Callable[..., str],
    ) -> None:
        """A6: calling verify twice with the same token returns equal claims."""
        token = make_token(subject="user_idem")
        c1 = verifier.verify(token)
        c2 = verifier.verify(token)
        assert c1 == c2

    def test_verifier_returns_no_sdk_types(
        self,
        verifier: JwtVerifier,
        make_token: Callable[..., str],
    ) -> None:
        """A4 / F-R8: return value is the wire-only ``JwtClaims`` type --
        never a PyJWT internal object or dict.
        """
        token = make_token()
        claims = verifier.verify(token)
        assert type(claims).__name__ == "JwtClaims"
        assert type(claims).__module__ == "middleware.ports.jwt_verifier"
