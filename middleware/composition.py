"""middleware/composition.py -- the SINGLE wiring point for the
middleware ring.

This is the only file in ``middleware/`` that:

  * Reads ``ARCHITECTURE_PROFILE`` (rule **F1 / C1**).
  * Reads any ``WORKOS_*``, ``MEM0_*``, ``LANGFUSE_*`` env var
    (rule **C4 / C5**).
  * Names concrete adapter classes (rule **C1**).

Downstream consumers (the FastAPI app, route handlers) receive port
instances via the typed bag ``MiddlewareAdapters`` (rule **C2**) and
NEVER import a concrete adapter class themselves.

Architecture-test enforcement: ``tests/architecture/test_middleware_layer.py``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from middleware.adapters.acl.workos_role_acl import WorkOSRoleAcl
from middleware.adapters.auth.workos_jwt_verifier import (
    WorkOSJwtVerifier,
    default_workos_issuer,
)
from middleware.adapters.memory.mem0_cloud_client import Mem0CloudClient
from middleware.adapters.observability.langfuse_cloud_exporter import (
    LangfuseCloudExporter,
)
from middleware.ports.jwt_verifier import JwtVerifier
from middleware.ports.memory_client import MemoryClient
from middleware.ports.telemetry_exporter import TelemetryExporter
from middleware.ports.tool_acl import ToolAclProvider


__all__ = [
    "MiddlewareAdapters",
    "build_adapters",
    "MissingEnvError",
    "UnknownProfileError",
]


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class MissingEnvError(KeyError):
    """A required env var was absent during composition."""

    def __init__(self, var_name: str) -> None:
        super().__init__(var_name)
        self.var_name = var_name

    def __str__(self) -> str:
        return f"missing required env var: {self.var_name}"


class UnknownProfileError(ValueError):
    """``ARCHITECTURE_PROFILE`` is not one of the known values."""


# ─────────────────────────────────────────────────────────────────────
# Default tool-ACL policy table
# ─────────────────────────────────────────────────────────────────────
#
# Mirror of the WorkOS dashboard role/permission seed (created via
# ``npx workos@latest role/permission ...``). Kept here as a fallback
# / canonical source so the ACL works even on first-boot before
# WorkOS roles propagate to the issued JWTs.

_DEFAULT_ROLE_TO_TOOLS: dict[str, frozenset[str]] = {
    "admin": frozenset({"shell", "file_io", "web_search"}),
    "beta": frozenset({"file_io", "web_search"}),
    "viewer": frozenset(),
    "member": frozenset(),
}

_DEFAULT_KNOWN_TOOLS: frozenset[str] = frozenset(
    {"shell", "file_io", "web_search"}
)


# ─────────────────────────────────────────────────────────────────────
# Typed adapter bag
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MiddlewareAdapters:
    """Bag of port-typed adapter instances (rule C2)."""

    profile: str
    jwt_verifier: JwtVerifier
    tool_acl: ToolAclProvider
    memory_client: MemoryClient
    telemetry_exporter: TelemetryExporter


# ─────────────────────────────────────────────────────────────────────
# build_adapters -- THE composition function
# ─────────────────────────────────────────────────────────────────────


def build_adapters(
    *,
    env: Mapping[str, str] | None = None,
) -> MiddlewareAdapters:
    """Wire all middleware adapters from the environment.

    Args:
        env: optional explicit env mapping. Tests inject this so
            composition is deterministic (no real ``os.environ`` reads).
            When ``None``, falls back to ``os.environ``.

    Returns:
        MiddlewareAdapters: typed bag of port instances.

    Raises:
        UnknownProfileError: ``ARCHITECTURE_PROFILE`` is not ``v3`` or ``v2``.
        MissingEnvError: a required env var is absent.
    """
    e = dict(env) if env is not None else dict(os.environ)

    # Profile is the ONLY place this string is read in middleware/.
    profile = e.get("ARCHITECTURE_PROFILE", "v3")
    if profile not in {"v3", "v2"}:
        raise UnknownProfileError(
            f"unknown ARCHITECTURE_PROFILE={profile!r}; "
            "must be 'v3' (dev-tier default) or 'v2' (paid graduation)"
        )

    if profile == "v3":
        return _build_v3(e)
    # profile == "v2"
    return _build_v2(e)


# ─────────────────────────────────────────────────────────────────────
# v3 (dev-tier free substrates)
# ─────────────────────────────────────────────────────────────────────


def _build_v3(e: Mapping[str, str]) -> MiddlewareAdapters:
    workos_client_id = _require(e, "WORKOS_CLIENT_ID")
    _require(e, "WORKOS_API_KEY")  # not used directly here; sanity check
    mem0_api_key = _require(e, "MEM0_API_KEY")
    langfuse_public = _require(e, "LANGFUSE_PUBLIC_KEY")
    langfuse_secret = _require(e, "LANGFUSE_SECRET_KEY")

    workos_issuer = e.get(
        "WORKOS_ISSUER", default_workos_issuer(workos_client_id)
    )
    mem0_base_url = e.get("MEM0_BASE_URL", "https://api.mem0.ai")
    langfuse_host = e.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    jwks_url = e.get(
        "WORKOS_JWKS_URL",
        f"https://api.workos.com/sso/jwks/{workos_client_id}",
    )

    # JWT verifier -- adapter owns SDK construction (rule F-R2 / A1).
    # Real network is only hit on the first verify() call.
    verifier = WorkOSJwtVerifier(
        jwks_url=jwks_url,
        expected_issuer=workos_issuer,
        expected_client_id=workos_client_id,
        expected_token_use="access",
    )

    return MiddlewareAdapters(
        profile="v3",
        jwt_verifier=verifier,
        tool_acl=WorkOSRoleAcl(
            role_to_tools=_DEFAULT_ROLE_TO_TOOLS,
            known_tools=_DEFAULT_KNOWN_TOOLS,
        ),
        memory_client=Mem0CloudClient(
            api_key=mem0_api_key,
            base_url=mem0_base_url,
        ),
        telemetry_exporter=LangfuseCloudExporter(
            public_key=langfuse_public,
            secret_key=langfuse_secret,
            host=langfuse_host,
        ),
    )


# ─────────────────────────────────────────────────────────────────────
# v2 (paid graduation -- self-hosted variants)
# ─────────────────────────────────────────────────────────────────────


def _build_v2(e: Mapping[str, str]) -> MiddlewareAdapters:
    """v2 wiring -- self-hosted Mem0 + self-hosted Langfuse + (same)
    WorkOS verifier + WorkOS role ACL.

    Sprint 1 ships parity by reusing the v3 SDKs but pointed at
    self-hosted hosts. The dedicated self-hosted adapter classes land
    in Sprint 2 along with their conformance tests.
    """
    workos_client_id = _require(e, "WORKOS_CLIENT_ID")
    _require(e, "WORKOS_API_KEY")
    mem0_api_key = _require(e, "MEM0_API_KEY")
    langfuse_public = _require(e, "LANGFUSE_PUBLIC_KEY")
    langfuse_secret = _require(e, "LANGFUSE_SECRET_KEY")

    workos_issuer = e.get(
        "WORKOS_ISSUER", default_workos_issuer(workos_client_id)
    )
    # v2 defaults to self-hosted endpoints.
    mem0_base_url = e.get("MEM0_BASE_URL", "https://mem0.internal")
    langfuse_host = e.get("LANGFUSE_HOST", "https://langfuse.internal")
    jwks_url = e.get(
        "WORKOS_JWKS_URL",
        f"https://api.workos.com/sso/jwks/{workos_client_id}",
    )

    verifier = WorkOSJwtVerifier(
        jwks_url=jwks_url,
        expected_issuer=workos_issuer,
        expected_client_id=workos_client_id,
        expected_token_use="access",
    )

    return MiddlewareAdapters(
        profile="v2",
        jwt_verifier=verifier,
        tool_acl=WorkOSRoleAcl(
            role_to_tools=_DEFAULT_ROLE_TO_TOOLS,
            known_tools=_DEFAULT_KNOWN_TOOLS,
        ),
        memory_client=Mem0CloudClient(
            api_key=mem0_api_key,
            base_url=mem0_base_url,
        ),
        telemetry_exporter=LangfuseCloudExporter(
            public_key=langfuse_public,
            secret_key=langfuse_secret,
            host=langfuse_host,
        ),
    )


# ─────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────


def _require(env: Mapping[str, str], key: str) -> str:
    value = env.get(key)
    if value is None or value == "":
        raise MissingEnvError(key)
    return value
