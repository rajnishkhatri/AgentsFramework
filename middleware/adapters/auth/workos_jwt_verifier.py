"""WorkOSJwtVerifier -- ``JwtVerifier`` adapter for WorkOS AuthKit.

Implements ``middleware.ports.jwt_verifier.JwtVerifier`` using PyJWT for
RS256 signature verification against a JWKS document fetched from
WorkOS's user-management endpoint.

**SDK isolation (rule F-R2 / A1):** ``jwt`` (PyJWT) is imported only in
this file. The return value (``JwtClaims``) is a vendor-neutral wire
shape -- no PyJWT internals, no WorkOS SDK objects, ever escape past
this boundary (rule F-R8 / A4).

**Error translation table (rule A5):**

    +-------------------------------+------------------------------+
    | PyJWT exception               | Port exception                |
    +===============================+==============================+
    | ExpiredSignatureError         | ExpiredTokenError             |
    | InvalidIssuerError            | InvalidIssuerError (port)     |
    | InvalidSignatureError         | InvalidTokenError             |
    | DecodeError                   | InvalidTokenError             |
    | PyJWKClientError              | InvalidTokenError             |
    | (anything else)               | InvalidTokenError             |
    +-------------------------------+------------------------------+

**Idempotency (rule A6):** ``verify`` is pure given a fixed token + a
stable JWKS fetcher. Calling twice returns equal claims.

**SDK pin (rule A9):** PyJWT >= 2.8 (declared in ``pyproject.toml``).

**Logger (rule A7 / O3):** ``middleware.adapters.auth`` -- never log raw
tokens (PII). Log only ``subject`` and rejection ``reason``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Callable

import jwt
from jwt import (
    DecodeError,
    ExpiredSignatureError,
    InvalidSignatureError,
    PyJWKClient,
)
from jwt.exceptions import (
    InvalidIssuerError as PyJWTInvalidIssuerError,
)
from jwt.exceptions import PyJWKClientError

from middleware.ports.jwt_verifier import (
    ExpiredTokenError,
    InvalidClientIdError,
    InvalidIssuerError,
    InvalidTokenError,
    InvalidTokenUseError,
    JwtClaims,
    MissingTokenError,
)

logger = logging.getLogger("middleware.adapters.auth")

__all__ = ["WorkOSJwtVerifier", "default_workos_issuer"]


# Type aliases for dependency injection. The composition root passes one of:
#   * a ``PyJWKClient`` instance (production), OR
#   * a fixture-style ``jwks_fetcher`` callable (tests, no network).
JwksFetcher = Callable[[], dict[str, Any]]


def default_workos_issuer(client_id: str) -> str:
    """The canonical WorkOS user-management issuer URL for a client_id.

    Composition root uses this when env var ``WORKOS_ISSUER`` is unset.
    """
    return f"https://api.workos.com/user_management/{client_id}"


class WorkOSJwtVerifier:
    """RS256 verifier wired against a JWKS document.

    Construction:
        Production wiring (composition root)::

            verifier = WorkOSJwtVerifier(
                jwks_client=PyJWKClient(
                    f"https://api.workos.com/sso/jwks/{client_id}"
                ),
                expected_issuer=default_workos_issuer(client_id),
                expected_client_id=client_id,
            )

        Test wiring (no network)::

            verifier = WorkOSJwtVerifier(
                jwks_fetcher=lambda: STATIC_JWKS,
                expected_issuer="https://...",
                expected_client_id="client_test",
            )

    Exactly one of ``jwks_client`` or ``jwks_fetcher`` MUST be supplied.
    """

    def __init__(
        self,
        *,
        jwks_url: str | None = None,
        jwks_client: PyJWKClient | None = None,
        jwks_fetcher: JwksFetcher | None = None,
        expected_issuer: str,
        expected_client_id: str,
        expected_token_use: str = "access",
        algorithms: tuple[str, ...] = ("RS256",),
    ) -> None:
        # Exactly one of the three JWKS sources MUST be supplied.
        sources_given = sum(
            1
            for s in (jwks_url, jwks_client, jwks_fetcher)
            if s is not None
        )
        if sources_given != 1:
            raise ValueError(
                "WorkOSJwtVerifier requires exactly one of "
                "jwks_url (production), jwks_client, or jwks_fetcher (tests)"
            )
        self._jwks_client = jwks_client
        self._jwks_fetcher = jwks_fetcher
        # Lazy-build a PyJWKClient from the URL on first use. This keeps
        # the SDK construction inside the adapter (rule F-R2 / A1) so
        # composition.py never names PyJWKClient directly.
        if jwks_url is not None:
            self._jwks_client = PyJWKClient(jwks_url)
        self._expected_issuer = expected_issuer
        self._expected_client_id = expected_client_id
        self._expected_token_use = expected_token_use
        self._algorithms = list(algorithms)

    # ── port impl ───────────────────────────────────────────────────

    def verify(self, token: str | None) -> JwtClaims:
        if token is None or not token.strip():
            raise MissingTokenError("missing bearer token")

        signing_key = self._signing_key_for(token)

        try:
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=self._algorithms,
                issuer=self._expected_issuer,
                options={
                    "require": ["exp", "iss", "sub"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iss": True,
                },
            )
        except ExpiredSignatureError as exc:
            self._log_rejection(token, "expired")
            raise ExpiredTokenError("token expired") from exc
        except PyJWTInvalidIssuerError as exc:
            self._log_rejection(token, "invalid_issuer")
            raise InvalidIssuerError(
                f"unexpected issuer (expected {self._expected_issuer})"
            ) from exc
        except (InvalidSignatureError, DecodeError) as exc:
            self._log_rejection(token, "invalid_signature_or_decode")
            raise InvalidTokenError(f"invalid token: {exc}") from exc
        except jwt.PyJWTError as exc:
            self._log_rejection(token, "pyjwt_error")
            raise InvalidTokenError(f"invalid token: {exc}") from exc

        # Post-decode invariant checks (PyJWT does not natively verify
        # client_id or token_use).
        actual_client_id = payload.get("client_id")
        if actual_client_id != self._expected_client_id:
            self._log_rejection(token, "invalid_client_id")
            raise InvalidClientIdError(
                f"client_id mismatch (got {actual_client_id!r}, "
                f"expected {self._expected_client_id!r})"
            )

        actual_token_use = payload.get("token_use")
        if actual_token_use != self._expected_token_use:
            self._log_rejection(token, "invalid_token_use")
            raise InvalidTokenUseError(
                f"token_use mismatch (got {actual_token_use!r}, "
                f"expected {self._expected_token_use!r})"
            )

        claims = self._payload_to_claims(payload)
        logger.info(
            "auth_ok subject=%s org=%s roles=%s",
            claims.subject,
            claims.organization_id,
            list(claims.roles),
        )
        return claims

    # ── helpers ─────────────────────────────────────────────────────

    def _signing_key_for(self, token: str) -> Any:
        """Resolve the RSA signing key for ``token``'s ``kid`` header.

        Strategy 1 (prod): delegate to ``PyJWKClient``.
        Strategy 2 (tests): build a key on the fly from the in-memory
        JWKS dict. This keeps the verifier free of network I/O during
        unit tests (anti-pattern AP-5 guard).
        """
        if self._jwks_client is not None:
            try:
                return self._jwks_client.get_signing_key_from_jwt(token).key
            except PyJWKClientError as exc:
                raise InvalidTokenError(f"jwks lookup failed: {exc}") from exc
            except DecodeError as exc:
                raise InvalidTokenError(f"jwt header decode failed: {exc}") from exc

        # jwks_fetcher path -- find matching kid manually.
        try:
            unverified_header = jwt.get_unverified_header(token)
        except DecodeError as exc:
            raise InvalidTokenError(f"jwt header decode failed: {exc}") from exc
        kid = unverified_header.get("kid")
        assert self._jwks_fetcher is not None  # branch invariant
        jwks = self._jwks_fetcher()
        for jwk in jwks.get("keys", []):
            if jwk.get("kid") == kid:
                return jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
        raise InvalidTokenError(f"no JWK found for kid={kid!r}")

    def _payload_to_claims(self, payload: dict[str, Any]) -> JwtClaims:
        """Map decoded JWT payload to the vendor-neutral wire shape."""
        roles = _normalize_string_seq(payload.get("role"))
        if not roles:
            roles = _normalize_string_seq(payload.get("roles"))
        permissions = _normalize_string_seq(payload.get("permissions"))

        return JwtClaims(
            subject=str(payload["sub"]),
            expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=UTC),
            issuer=str(payload["iss"]),
            client_id=str(payload["client_id"]),
            token_use=str(payload["token_use"]),
            organization_id=(
                str(payload["org_id"]) if payload.get("org_id") else None
            ),
            roles=roles,
            permissions=permissions,
        )

    def _log_rejection(self, token: str, reason: str) -> None:
        """Log a rejection without leaking the raw token (rule O2: no PII)."""
        suffix = token[-6:] if isinstance(token, str) and len(token) > 6 else "?"
        logger.warning("auth_reject reason=%s token_tail=%s", reason, suffix)


def _normalize_string_seq(value: Any) -> tuple[str, ...]:
    """Coerce a JWT claim into a tuple of strings.

    Accepts ``None``, ``str``, ``list[str]``, ``tuple[str, ...]``.
    Anything else returns an empty tuple.
    """
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value if v is not None)
    return ()
