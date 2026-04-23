"""Shared fixtures for JWT verifier adapter tests.

Anti-Pattern guard (AP-5 / "Live LLM in CI" generalised to any external
service): we **never** hit a real JWKS endpoint in CI. Instead we generate
an in-process RSA keypair, expose its public half via an in-memory
``PyJWKClient`` substitute, and sign tokens locally. This keeps the L2
"Reproducible Reality" guarantee from ``research/tdd_agentic_systems_prompt.md``:
contract verification with mock providers, every commit, <30s.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

import jwt
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


# ─────────────────────────────────────────────────────────────────────
# Keypair + JWKS fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def rsa_keypair() -> dict[str, Any]:
    """Session-scoped 2048-bit RSA keypair. Holds the private PEM (used to
    sign tokens), public PEM (used by the verifier), and a JWKS dict
    suitable for ``PyJWKClient``-style consumption.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Build a JWKS document with one key.
    public_numbers = public_key.public_numbers()

    def _b64url_uint(value: int) -> str:
        import base64

        byte_length = (value.bit_length() + 7) // 8
        return (
            base64.urlsafe_b64encode(value.to_bytes(byte_length, "big"))
            .rstrip(b"=")
            .decode("ascii")
        )

    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "kid": "test-key-1",
                "use": "sig",
                "alg": "RS256",
                "n": _b64url_uint(public_numbers.n),
                "e": _b64url_uint(public_numbers.e),
            }
        ]
    }
    return {
        "private_pem": private_pem,
        "public_pem": public_pem,
        "private_key": private_key,
        "public_key": public_key,
        "kid": "test-key-1",
        "jwks": jwks,
        "jwks_json": json.dumps(jwks).encode("utf-8"),
    }


@pytest.fixture
def expected_issuer() -> str:
    return "https://api.workos.com/user_management/client_test_local"


@pytest.fixture
def expected_client_id() -> str:
    return "client_test_local"


# ─────────────────────────────────────────────────────────────────────
# Token factory
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def make_token(
    rsa_keypair: dict[str, Any],
    expected_issuer: str,
    expected_client_id: str,
) -> Callable[..., str]:
    """Returns a callable that mints signed JWTs with overridable claims.

    Defaults produce a *valid* token; tests override individual fields
    to construct each rejection scenario.
    """

    def _make(
        *,
        subject: str = "user_01HX",
        issuer: str | None = None,
        client_id: str | None = None,
        token_use: str = "access",
        expires_at: datetime | None = None,
        algorithm: str = "RS256",
        kid: str | None = None,
        organization_id: str | None = "org_01HX",
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "sub": subject,
            "iss": issuer if issuer is not None else expected_issuer,
            "client_id": client_id if client_id is not None else expected_client_id,
            "token_use": token_use,
            "iat": int(now.timestamp()),
            "exp": int(
                (expires_at or (now + timedelta(minutes=15))).timestamp()
            ),
        }
        if organization_id is not None:
            payload["org_id"] = organization_id
        if roles is not None:
            payload["role"] = roles[0] if len(roles) == 1 else roles
        if permissions is not None:
            payload["permissions"] = permissions
        if extra_claims:
            payload.update(extra_claims)

        headers = {"kid": kid if kid is not None else rsa_keypair["kid"]}
        return jwt.encode(
            payload,
            rsa_keypair["private_pem"],
            algorithm=algorithm,
            headers=headers,
        )

    return _make


# ─────────────────────────────────────────────────────────────────────
# In-memory JWKS source -- avoids any network call
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def jwks_provider(rsa_keypair: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    """Returns the same JWKS dict every call. Mimics a healthy
    PyJWKClient.fetch_data() surface.
    """

    def _provider() -> dict[str, Any]:
        return rsa_keypair["jwks"]

    return _provider
