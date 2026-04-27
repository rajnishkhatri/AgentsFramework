"""Contract tests for ``middleware.adapters.acl.workos_role_acl``.

Layer: **L2 Reproducible Reality** -- pure decision function, no I/O.

Order per Sprint 1 §S1.3.1 acceptance criteria and TAP-4 (Gap Blindness):
    Rejection paths FIRST:
        R1  beta calling ``shell``         -> deny
        R2  unknown role calling anything  -> deny
        R3  viewer calling anything        -> deny
        R4  unknown tool                   -> deny (default-deny)
        R5  empty roles tuple              -> deny
    THEN acceptance:
        A1  admin calling ``shell``        -> allow
        A2  beta calling ``file_io``       -> allow
        A3  beta calling ``web_search``    -> allow

Rejection-to-acceptance ratio = 5:3 (favors failure-path coverage per
Anti-Pattern 6).

The role -> permission mapping under test mirrors what was set up in
WorkOS via the dashboard CLI:

    admin   -> tool:shell, tool:file_io, tool:web_search
    beta    -> tool:file_io, tool:web_search        (NO shell -- security)
    viewer  -> (no tool permissions)
    member  -> (no tool permissions, default WorkOS role)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from middleware.ports.jwt_verifier import JwtClaims
from middleware.ports.tool_acl import ToolAclDecision, ToolAclProvider


def _claims(
    *,
    subject: str = "user_test",
    roles: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
) -> JwtClaims:
    """Build a wire-only JwtClaims for ACL decision-only tests."""
    return JwtClaims(
        subject=subject,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        issuer="https://api.workos.com/user_management/client_test",
        client_id="client_test",
        token_use="access",
        organization_id="org_test",
        roles=roles,
        permissions=permissions,
    )


@pytest.fixture
def acl() -> ToolAclProvider:
    """v3 default ACL adapter -- WorkOS roles -> tool permissions.

    Uses the role/permission table the WorkOS CLI seeded into the dev
    environment.
    """
    from middleware.adapters.acl.workos_role_acl import WorkOSRoleAcl

    return WorkOSRoleAcl(
        role_to_tools={
            "admin": frozenset({"shell", "file_io", "web_search"}),
            "beta": frozenset({"file_io", "web_search"}),
            "viewer": frozenset(),
            "member": frozenset(),
        },
        known_tools=frozenset({"shell", "file_io", "web_search"}),
    )


# ─────────────────────────────────────────────────────────────────────
# REJECTION PATHS first
# ─────────────────────────────────────────────────────────────────────


class TestRejectionPaths:
    def test_R1_beta_user_denied_shell(self, acl: ToolAclProvider) -> None:
        """**R3** literal: ``shell`` is NEVER exposed to non-admin users."""
        decision = acl.decide(
            _claims(subject="beta_user", roles=("beta",)),
            tool_name="shell",
        )
        assert decision.allowed is False
        assert decision.tool_name == "shell"
        assert decision.subject == "beta_user"
        assert "shell" in decision.reason.lower()

    def test_R2_unknown_role_denied(self, acl: ToolAclProvider) -> None:
        """Default-deny for any role not in the policy table."""
        decision = acl.decide(
            _claims(roles=("hacker",)),
            tool_name="file_io",
        )
        assert decision.allowed is False
        assert "unknown" in decision.reason.lower() or "no role" in decision.reason.lower()

    def test_R3_viewer_denied_all_tools(self, acl: ToolAclProvider) -> None:
        """Viewer role exists but has no tool permissions -> deny."""
        for tool in ("shell", "file_io", "web_search"):
            decision = acl.decide(
                _claims(subject="viewer_user", roles=("viewer",)),
                tool_name=tool,
            )
            assert decision.allowed is False, f"viewer must NOT call {tool}"

    def test_R4_unknown_tool_denied_for_admin(
        self, acl: ToolAclProvider
    ) -> None:
        """Default-deny when the tool isn't in the known-tools set
        (fail-closed, even for admin).
        """
        decision = acl.decide(
            _claims(roles=("admin",)),
            tool_name="exfiltrate_db",
        )
        assert decision.allowed is False
        assert "unknown" in decision.reason.lower()

    def test_R5_empty_roles_denied(self, acl: ToolAclProvider) -> None:
        """Token with no role claim at all -> deny."""
        decision = acl.decide(
            _claims(subject="no_role_user", roles=()),
            tool_name="file_io",
        )
        assert decision.allowed is False


# ─────────────────────────────────────────────────────────────────────
# ACCEPTANCE PATHS second
# ─────────────────────────────────────────────────────────────────────


class TestAcceptancePaths:
    def test_A1_admin_allowed_shell(self, acl: ToolAclProvider) -> None:
        decision = acl.decide(
            _claims(subject="admin_user", roles=("admin",)),
            tool_name="shell",
        )
        assert decision.allowed is True
        assert decision.tool_name == "shell"
        assert "admin" in decision.reason.lower()

    def test_A2_beta_allowed_file_io(self, acl: ToolAclProvider) -> None:
        decision = acl.decide(
            _claims(roles=("beta",)),
            tool_name="file_io",
        )
        assert decision.allowed is True
        assert "beta" in decision.reason.lower()

    def test_A3_beta_allowed_web_search(self, acl: ToolAclProvider) -> None:
        decision = acl.decide(
            _claims(roles=("beta",)),
            tool_name="web_search",
        )
        assert decision.allowed is True


# ─────────────────────────────────────────────────────────────────────
# Behavioral contract
# ─────────────────────────────────────────────────────────────────────


class TestBehavioralContract:
    def test_provider_satisfies_protocol(self, acl: ToolAclProvider) -> None:
        assert isinstance(acl, ToolAclProvider)

    def test_decide_is_idempotent(self, acl: ToolAclProvider) -> None:
        """A6: calling decide() twice with the same input returns equal
        decisions.
        """
        c = _claims(roles=("admin",))
        d1 = acl.decide(c, "shell")
        d2 = acl.decide(c, "shell")
        assert d1 == d2

    def test_decide_never_raises(self, acl: ToolAclProvider) -> None:
        """The contract is fail-closed via boolean return -- never via
        exception.
        """
        # Bad inputs in every dimension.
        weird_claims = _claims(subject="", roles=("",), permissions=("",))
        for tool in ("", "shell", "🦠"):
            decision = acl.decide(weird_claims, tool_name=tool)
            assert isinstance(decision, ToolAclDecision)

    def test_first_role_wins_for_audit_trace(
        self, acl: ToolAclProvider
    ) -> None:
        """When a user has multiple roles, the *highest-privilege* role
        granting the tool wins (so admin+beta is admin for shell).
        """
        decision = acl.decide(
            _claims(roles=("admin", "beta")),
            tool_name="shell",
        )
        assert decision.allowed is True
        assert "admin" in decision.reason.lower()
