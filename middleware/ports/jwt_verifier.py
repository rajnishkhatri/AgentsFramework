"""JwtVerifier port -- vendor-neutral JWT verification contract.

Per Sprint 1 story **S1.2.1** acceptance criteria:

  * Implements ``JwtVerifier`` Protocol consumed by composition root.
  * No vendor SDK types appear in the return value (rule **F-R8** / **A4**).
  * Verifier raises typed errors so the route layer can map to HTTP status
    codes deterministically (5 rejection paths tested before 1 acceptance
    path per TAP-4 / FD6.ADAPTER).

Concrete adapters live under ``middleware/adapters/auth/`` (e.g.
``WorkOSJwtVerifier``, ``Auth0JwtVerifier``). Tests use
``StubJwtVerifier`` from ``tests/middleware/adapters/auth/`` only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


__all__ = [
    "JwtClaims",
    "JwtVerifier",
    "InvalidTokenError",
    "ExpiredTokenError",
    "InvalidIssuerError",
    "InvalidClientIdError",
    "InvalidTokenUseError",
    "MissingTokenError",
]


# ─────────────────────────────────────────────────────────────────────
# Vendor-neutral wire shape returned by every verifier implementation.
# ─────────────────────────────────────────────────────────────────────


class JwtClaims(BaseModel):
    """Verified bearer-token claims, normalized across providers.

    The composition root maps these fields to whatever the upstream
    Identity Provider calls them (WorkOS uses ``sub``, ``org_id``,
    ``role``, etc.). Downstream consumers (auth middleware, tool ACL)
    see only this normalized shape -- they NEVER touch a WorkOS / Auth0
    SDK object directly. This is the **F-R8 / A4** boundary.

    Fields:
        subject: opaque user identifier (= JWT ``sub`` claim).
        expires_at: token expiry in UTC.
        issuer: token issuer URL (= ``iss`` claim).
        client_id: OAuth client this token was minted for (= ``client_id``).
        token_use: token purpose (e.g. ``"access"``, ``"id"``,
            ``"refresh"``). Used by ACL middleware to reject ID tokens
            on API surfaces.
        organization_id: WorkOS-style multi-tenant org identifier
            (``org_*``). ``None`` for personal accounts.
        roles: vendor-neutral role slugs (e.g. ``["admin"]``,
            ``["beta"]``). The verifier extracts and normalizes this
            from whatever claim the IdP uses (``role``, ``roles``,
            ``cognito:groups``, ...). Empty tuple means "no roles".
        permissions: vendor-neutral permission slugs (e.g.
            ``["tool:shell"]``). Empty tuple means "no permissions".
    """

    subject: str
    expires_at: datetime
    issuer: str
    client_id: str
    token_use: str
    organization_id: str | None = None
    roles: tuple[str, ...] = Field(default_factory=tuple)
    permissions: tuple[str, ...] = Field(default_factory=tuple)

    model_config = ConfigDict(frozen=True)


# ─────────────────────────────────────────────────────────────────────
# Typed errors -- one class per documented rejection reason.
# ─────────────────────────────────────────────────────────────────────


class InvalidTokenError(Exception):
    """Token is malformed, signature invalid, or fails any non-temporal check."""


class ExpiredTokenError(InvalidTokenError):
    """Token's ``exp`` claim is in the past."""


class InvalidIssuerError(InvalidTokenError):
    """Token ``iss`` claim does not match the verifier's expected issuer."""


class InvalidClientIdError(InvalidTokenError):
    """Token ``client_id`` claim does not match the configured client."""


class InvalidTokenUseError(InvalidTokenError):
    """Token ``token_use`` claim is not the expected value (e.g. ID token
    on an API endpoint).
    """


class MissingTokenError(InvalidTokenError):
    """No bearer token was supplied."""


# ─────────────────────────────────────────────────────────────────────
# Port Protocol
# ─────────────────────────────────────────────────────────────────────


@runtime_checkable
class JwtVerifier(Protocol):
    """Application-contract port for JWT bearer-token verification.

    Implementations:
        * ``middleware/adapters/auth/workos_jwt_verifier.py`` -- v3 default.
        * Future: Auth0, Cognito, custom OIDC.

    Behavioral contract (verified by ``tests/middleware/adapters/auth/``):

        * If ``token`` is ``None`` or empty: raise ``MissingTokenError``.
        * If signature does not verify against JWKs: raise ``InvalidTokenError``.
        * If ``exp`` is in the past: raise ``ExpiredTokenError``.
        * If ``iss`` does not match expected: raise ``InvalidIssuerError``.
        * If ``client_id`` does not match expected: raise ``InvalidClientIdError``.
        * If ``token_use`` is not the expected value: raise ``InvalidTokenUseError``.
        * On success: return a fully-populated ``JwtClaims`` instance.

    Implementations MUST be **idempotent** (rule A6): calling ``verify``
    twice with the same token returns the same claims (or raises the
    same error) without side effects.
    """

    def verify(self, token: str | None) -> JwtClaims:
        """Return ``JwtClaims`` for a valid token; raise on any rejection."""
        ...
