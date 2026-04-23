"""middleware/server.py -- the FastAPI app that fronts the
``agent_ui_adapter`` runtime with WorkOS JWT auth and tool ACL.

Per Sprint 1 §S1.1.1 acceptance criteria:

  * Composes from a typed ``MiddlewareAdapters`` bag (rule **C2**) --
    no ``import``s of concrete adapters in this file. The composition
    root (``middleware/composition.py``) is the only place adapters are
    named.
  * Loads the ``react_loop`` graph via ``langgraph.json`` config string
    -- never via Python import of ``orchestration/`` (rule **F4**).
    The architecture test ``test_middleware_layer.py`` enforces this.
  * Every authenticated route runs the JWT bearer verification middleware
    via the injected ``JwtVerifier`` port.
  * Tool calls are gated by the injected ``ToolAclProvider`` port --
    ``shell`` is denied to non-admin users (rule **R3**).

This module contains no domain logic. Route handlers are thin wrappers
around port calls -- they map success to 2xx and exceptions to HTTP
status codes only.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from middleware.composition import MiddlewareAdapters
from middleware.ports.jwt_verifier import (
    ExpiredTokenError,
    InvalidClientIdError,
    InvalidIssuerError,
    InvalidTokenError,
    InvalidTokenUseError,
    JwtClaims,
    MissingTokenError,
)


logger = logging.getLogger("middleware.server")


__all__ = ["build_middleware_app"]


# ─────────────────────────────────────────────────────────────────────
# Wire shapes for the auth + ACL endpoints
# ─────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    profile: str


class WhoAmIResponse(BaseModel):
    subject: str
    organization_id: str | None
    roles: list[str]
    permissions: list[str]


class AclDecideRequest(BaseModel):
    tool_name: str


class AclDecideResponse(BaseModel):
    allowed: bool
    tool_name: str
    subject: str
    reason: str


# ─────────────────────────────────────────────────────────────────────
# Composition root
# ─────────────────────────────────────────────────────────────────────


def build_middleware_app(
    *,
    adapters: MiddlewareAdapters,
) -> FastAPI:
    """Build the middleware FastAPI app from a wired adapter bag.

    Args:
        adapters: typed bag of port instances from
            ``middleware.composition.build_adapters()``.

    Returns:
        FastAPI: ready to mount additional routers (e.g. the
        ``agent_ui_adapter`` SSE surface).
    """
    app = FastAPI(
        title="Agent Middleware",
        description=(
            "WorkOS auth + tool ACL + LangGraph runtime gateway. "
            "Sprint 1 surface."
        ),
        version="0.1.0",
    )

    # ── auth dependency (port-driven) ───────────────────────────────

    def _verify_bearer(
        authorization: str | None = Header(default=None),
    ) -> JwtClaims:
        """Extract the bearer token, delegate to the injected verifier,
        and translate typed port errors into HTTP 401.

        Rule **F-R8 / A4**: the only thing returned to route handlers
        is a vendor-neutral ``JwtClaims`` -- no PyJWT or WorkOS SDK
        types ever escape past this seam.
        """
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401, detail="missing or malformed bearer token"
            )
        token = authorization[len("Bearer ") :].strip()
        try:
            return adapters.jwt_verifier.verify(token)
        except MissingTokenError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from None
        except ExpiredTokenError as exc:
            raise HTTPException(
                status_code=401, detail=f"token expired: {exc}"
            ) from None
        except InvalidIssuerError as exc:
            raise HTTPException(
                status_code=401, detail=f"invalid issuer: {exc}"
            ) from None
        except InvalidClientIdError as exc:
            raise HTTPException(
                status_code=401, detail=f"invalid client_id: {exc}"
            ) from None
        except InvalidTokenUseError as exc:
            raise HTTPException(
                status_code=401, detail=f"invalid token_use: {exc}"
            ) from None
        except InvalidTokenError as exc:
            raise HTTPException(
                status_code=401, detail=f"invalid token: {exc}"
            ) from None

    # ── routes ──────────────────────────────────────────────────────

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        """Cloud Run liveness probe -- intentionally pre-auth."""
        return HealthResponse(status="ok", profile=adapters.profile)

    @app.get("/me", response_model=WhoAmIResponse)
    async def me(
        claims: JwtClaims = Depends(_verify_bearer),
    ) -> WhoAmIResponse:
        return WhoAmIResponse(
            subject=claims.subject,
            organization_id=claims.organization_id,
            roles=list(claims.roles),
            permissions=list(claims.permissions),
        )

    @app.post("/acl/decide", response_model=AclDecideResponse)
    async def acl_decide(
        body: AclDecideRequest,
        claims: JwtClaims = Depends(_verify_bearer),
    ) -> AclDecideResponse:
        """Authorize a tool call. Returns the ACL decision; on deny
        responds with HTTP 403 carrying the audit-quality reason.

        Sprint 1 §S1.3.1: ``shell`` is denied to ``beta`` and
        ``viewer`` callers.
        """
        decision = adapters.tool_acl.decide(claims, body.tool_name)
        if not decision.allowed:
            raise HTTPException(status_code=403, detail=decision.reason)
        return AclDecideResponse(
            allowed=True,
            tool_name=decision.tool_name,
            subject=decision.subject,
            reason=decision.reason,
        )

    # Place to mount the agent_ui_adapter app at /agent in production
    # composition (see docs/Architectures/FRONTEND_ARCHITECTURE.md
    # data-flow steps 6-9). Keeping the mount in the prod-only entry
    # script (e.g. middleware/__main__.py) keeps test boot fast.

    logger.info(
        "middleware app built profile=%s acl_provider=%s",
        adapters.profile,
        type(adapters.tool_acl).__name__,
    )
    return app


# ─────────────────────────────────────────────────────────────────────
# Optional helper -- used by ``python -m middleware`` for local dev.
# Kept ``Any`` typed to keep this module SDK-import-free.
# ─────────────────────────────────────────────────────────────────────


def build_default_app() -> Any:
    """Build the app with adapters wired from real env vars.

    Used by the ``python -m middleware`` entry point. Tests use
    ``build_middleware_app(adapters=...)`` directly with injected
    fixtures.
    """
    from middleware.composition import build_adapters

    return build_middleware_app(adapters=build_adapters())
