"""Tests for ``middleware.composition`` -- the single profile switch.

Per Sprint 1 story **S1.1.2** acceptance criteria and rules **C1-C5**:

  * ``ARCHITECTURE_PROFILE`` is read ONLY here (architecture test
    ``test_middleware_layer.py::TestF1`` enforces this).
  * Composition exports ``buildAdapters()`` (Python: ``build_adapters``)
    returning a typed bag of port instances (rule **C2**).
  * All env reads happen here -- adapters receive plain strings via
    constructor (rule **C4**).
  * Both ``v3`` (dev-tier) and ``v2`` (paid graduation) profiles wire
    correctly. Tests inject ``env`` so we never read process env or
    hit the network.

Layer: **L2 Reproducible Reality** -- contract test with injected env
mapping. No SDK side effects, no network.
"""

from __future__ import annotations

import pytest


# Minimum env required for v3 wiring.
V3_ENV: dict[str, str] = {
    "ARCHITECTURE_PROFILE": "v3",
    "WORKOS_CLIENT_ID": "client_test_local",
    "WORKOS_API_KEY": "sk_test_dummy",
    "MEM0_API_KEY": "m0-test-dummy",
    "MEM0_BASE_URL": "https://api.mem0.ai",
    "LANGFUSE_PUBLIC_KEY": "pk-lf-test-dummy",
    "LANGFUSE_SECRET_KEY": "sk-lf-test-dummy",
    "LANGFUSE_HOST": "https://us.cloud.langfuse.com",
}


# ─────────────────────────────────────────────────────────────────────
# v3 profile (default dev-tier)
# ─────────────────────────────────────────────────────────────────────


class TestV3ProfileWiring:
    def test_v3_returns_typed_adapter_bag(self) -> None:
        """C2: ``build_adapters`` returns a bag whose attributes
        satisfy each port Protocol (vendor-neutral, no SDK types).
        """
        from middleware.composition import build_adapters
        from middleware.ports.jwt_verifier import JwtVerifier
        from middleware.ports.memory_client import MemoryClient
        from middleware.ports.telemetry_exporter import TelemetryExporter
        from middleware.ports.tool_acl import ToolAclProvider

        adapters = build_adapters(env=V3_ENV)

        assert isinstance(adapters.jwt_verifier, JwtVerifier)
        assert isinstance(adapters.tool_acl, ToolAclProvider)
        assert isinstance(adapters.memory_client, MemoryClient)
        assert isinstance(adapters.telemetry_exporter, TelemetryExporter)

    def test_v3_uses_workos_jwt_verifier(self) -> None:
        from middleware.adapters.auth.workos_jwt_verifier import (
            WorkOSJwtVerifier,
        )
        from middleware.composition import build_adapters

        adapters = build_adapters(env=V3_ENV)
        assert isinstance(adapters.jwt_verifier, WorkOSJwtVerifier)

    def test_v3_uses_workos_role_acl(self) -> None:
        from middleware.adapters.acl.workos_role_acl import WorkOSRoleAcl
        from middleware.composition import build_adapters

        adapters = build_adapters(env=V3_ENV)
        assert isinstance(adapters.tool_acl, WorkOSRoleAcl)

    def test_v3_acl_blocks_shell_for_beta(self) -> None:
        """End-to-end composition smoke: the wired ACL enforces the
        ``shell`` block per the WorkOS role table.
        """
        from datetime import UTC, datetime, timedelta

        from middleware.composition import build_adapters
        from middleware.ports.jwt_verifier import JwtClaims

        adapters = build_adapters(env=V3_ENV)
        claims = JwtClaims(
            subject="beta_user",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            issuer="https://...",
            client_id="client_test_local",
            token_use="access",
            roles=("beta",),
        )
        decision = adapters.tool_acl.decide(claims, tool_name="shell")
        assert decision.allowed is False


# ─────────────────────────────────────────────────────────────────────
# v2 profile (paid graduation)
# ─────────────────────────────────────────────────────────────────────


class TestV2ProfileWiring:
    def test_v2_returns_same_port_shapes(self) -> None:
        """v2 swaps adapter implementations, NOT port contracts.
        Composition must return the same typed bag shape for both
        profiles (rule C2).
        """
        from middleware.composition import build_adapters
        from middleware.ports.jwt_verifier import JwtVerifier
        from middleware.ports.memory_client import MemoryClient
        from middleware.ports.telemetry_exporter import TelemetryExporter
        from middleware.ports.tool_acl import ToolAclProvider

        v2_env = {**V3_ENV, "ARCHITECTURE_PROFILE": "v2"}
        adapters = build_adapters(env=v2_env)

        assert isinstance(adapters.jwt_verifier, JwtVerifier)
        assert isinstance(adapters.tool_acl, ToolAclProvider)
        assert isinstance(adapters.memory_client, MemoryClient)
        assert isinstance(adapters.telemetry_exporter, TelemetryExporter)


# ─────────────────────────────────────────────────────────────────────
# Profile-switch error handling
# ─────────────────────────────────────────────────────────────────────


class TestProfileErrors:
    def test_unknown_profile_raises(self) -> None:
        from middleware.composition import (
            UnknownProfileError,
            build_adapters,
        )

        env = {**V3_ENV, "ARCHITECTURE_PROFILE": "v99"}
        with pytest.raises(UnknownProfileError):
            build_adapters(env=env)

    def test_missing_workos_client_id_raises(self) -> None:
        from middleware.composition import (
            MissingEnvError,
            build_adapters,
        )

        env = {k: v for k, v in V3_ENV.items() if k != "WORKOS_CLIENT_ID"}
        with pytest.raises(MissingEnvError) as excinfo:
            build_adapters(env=env)
        assert "WORKOS_CLIENT_ID" in str(excinfo.value)

    def test_default_profile_is_v3_when_unset(self) -> None:
        """C1: a missing ``ARCHITECTURE_PROFILE`` defaults to ``v3``
        (dev-tier). Documented in pyproject + style guide.
        """
        from middleware.composition import build_adapters

        env_without_profile = {
            k: v for k, v in V3_ENV.items() if k != "ARCHITECTURE_PROFILE"
        }
        adapters = build_adapters(env=env_without_profile)
        assert adapters.profile == "v3"


# ─────────────────────────────────────────────────────────────────────
# Env-read isolation (rule C5)
# ─────────────────────────────────────────────────────────────────────


class TestEnvReadIsolation:
    def test_no_other_middleware_file_reads_architecture_profile(self) -> None:
        """C5 is enforced by ``tests/architecture/test_middleware_layer.py``.
        This test re-asserts the same property at the unit-test layer
        for fast feedback during development.
        """
        from pathlib import Path

        AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
        middleware_dir = AGENT_ROOT / "middleware"
        composition_path = middleware_dir / "composition.py"

        leaks: list[str] = []
        for py in middleware_dir.rglob("*.py"):
            if py == composition_path:
                continue
            text = py.read_text()
            # Code reads (not docstrings).
            if 'env["ARCHITECTURE_PROFILE"]' in text or (
                "ARCHITECTURE_PROFILE" in text
                and ("os.environ" in text or "os.getenv" in text)
            ):
                leaks.append(str(py.relative_to(AGENT_ROOT)))
        assert leaks == [], (
            "C5 violated: ARCHITECTURE_PROFILE read outside composition.py:\n"
            + "\n".join(leaks)
        )
