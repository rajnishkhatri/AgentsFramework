"""ToolAclProvider port -- vendor-neutral tool-level access control.

Per Sprint 1 story **S1.3.1**: enforce per-WorkOS-role tool allowlists
so the security-sensitive ``shell`` tool is **NEVER** exposed to
non-admin users (rule **R3**).

This port lives in ``middleware/`` (rule §3.2: tool ACL is a middleware
concern, not a component or service concern). Concrete adapters under
``middleware/adapters/acl/`` translate from whatever role/permission
shape the upstream IdP exposes (WorkOS roles, Cognito groups, ...) into
the vendor-neutral ``ToolAclDecision`` returned by ``decide()``.

Behavioral contract (verified by ``tests/middleware/adapters/acl/``):

    decide(claims, tool_name) -> ToolAclDecision

      * If the tool is unknown to the policy: deny (default-deny, fail-closed).
      * If the user's role lacks the matching permission: deny.
      * On allow: ``allowed=True``, ``reason="role:<slug> grants tool:<name>"``.
      * On deny: ``allowed=False``, ``reason="..."`` -- never raise.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from middleware.ports.jwt_verifier import JwtClaims


__all__ = ["ToolAclDecision", "ToolAclProvider"]


class ToolAclDecision(BaseModel):
    """Vendor-neutral tool-call authorization decision.

    Fields:
        allowed: ``True`` only if the caller is permitted to invoke the
            tool. Every other path is ``False`` (fail-closed default).
        tool_name: the tool the decision is for.
        subject: the principal (= ``JwtClaims.subject``) the decision
            applies to. Echoed for audit logging.
        reason: free-form, audit-quality message. Stable enough to be
            string-matched in tests (e.g. ``"role:admin grants ..."``,
            ``"unknown role"``, ``"missing permission tool:shell"``).
    """

    allowed: bool
    tool_name: str
    subject: str
    reason: str

    model_config = ConfigDict(frozen=True)


@runtime_checkable
class ToolAclProvider(Protocol):
    """Application-contract port for tool-call authorization.

    Implementations:
        * ``middleware/adapters/acl/workos_role_acl.py`` -- v3 default,
          maps WorkOS role slugs (``admin``, ``beta``, ``viewer``) to
          tool permissions.
        * Future: dynamic / DB-backed policy.

    Behavioral contract:

        * MUST be **pure** (no I/O at decision time -- all policy data
          loaded at construction).
        * MUST be **idempotent** (rule A6).
        * MUST **never raise** -- the only way to express failure is
          ``allowed=False`` with a reason.
        * Unknown tools and unknown roles MUST return ``allowed=False``
          (default-deny / fail-closed -- TAP-4 / FE-AP-13).
    """

    def decide(
        self,
        claims: JwtClaims,
        tool_name: str,
    ) -> ToolAclDecision:
        """Return an allow/deny decision for ``claims`` calling ``tool_name``."""
        ...
