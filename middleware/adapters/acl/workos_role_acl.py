"""WorkOSRoleAcl -- ``ToolAclProvider`` adapter backed by WorkOS roles.

Implements ``middleware.ports.tool_acl.ToolAclProvider``.

**No SDK import.** This adapter is a pure decision function over the
already-normalized ``JwtClaims.roles`` tuple. The WorkOS SDK was used
out-of-band (via ``npx workos@latest role/permission ...``) to seed the
role/permission table; at runtime we receive role slugs in the
verified JWT.

**Default-deny:** unknown roles, unknown tools, and the empty-roles
case all return ``allowed=False``. Fail-closed -- the only
trust-critical default (TAP-4 / FE-AP-13).

**Audit trail (rule O3):** ``decide()`` always logs the decision via
the ``middleware.adapters.acl`` logger so external trace pipelines see
every allow and deny.
"""

from __future__ import annotations

import logging
from typing import FrozenSet, Mapping

from middleware.ports.jwt_verifier import JwtClaims
from middleware.ports.tool_acl import ToolAclDecision

logger = logging.getLogger("middleware.adapters.acl")

__all__ = ["WorkOSRoleAcl"]


# Privilege ranking -- higher = more privileged. Used to pick the
# "winning" role when a user has multiple. ``admin > beta > viewer/member``.
# Keeping this explicit (rather than inferring from permission counts)
# makes audit logs deterministic and gives the test
# ``test_first_role_wins_for_audit_trace`` a stable reason string.
_DEFAULT_PRIVILEGE_RANK: dict[str, int] = {
    "admin": 100,
    "beta": 50,
    "viewer": 10,
    "member": 5,
}


class WorkOSRoleAcl:
    """Map WorkOS role slugs to a per-tool allow/deny decision.

    Args:
        role_to_tools: ``{role_slug: frozenset(tool_name, ...)}``. Roles
            not in this map are treated as unknown -> deny.
        known_tools: the closed set of tool names the policy understands.
            Any tool outside this set is denied even for ``admin``
            (default-deny / FE-AP-13).
        privilege_rank: optional override for the default role ranking
            used to pick the most-privileged matching role for the
            audit reason string.
    """

    def __init__(
        self,
        *,
        role_to_tools: Mapping[str, FrozenSet[str]],
        known_tools: FrozenSet[str],
        privilege_rank: Mapping[str, int] | None = None,
    ) -> None:
        self._role_to_tools = dict(role_to_tools)
        self._known_tools = frozenset(known_tools)
        self._privilege_rank = dict(privilege_rank or _DEFAULT_PRIVILEGE_RANK)

    def decide(
        self,
        claims: JwtClaims,
        tool_name: str,
    ) -> ToolAclDecision:
        # Default-deny: unknown tool.
        if tool_name not in self._known_tools:
            return self._deny(
                claims,
                tool_name,
                reason=f"unknown tool {tool_name!r}",
            )

        # Default-deny: no roles on the token.
        if not claims.roles:
            return self._deny(
                claims,
                tool_name,
                reason="no role on token",
            )

        # Find every role granting the tool, then keep the most
        # privileged one for the audit reason string.
        granting_roles = [
            role
            for role in claims.roles
            if role in self._role_to_tools
            and tool_name in self._role_to_tools[role]
        ]
        if not granting_roles:
            unknown_only = all(
                r not in self._role_to_tools for r in claims.roles
            )
            if unknown_only:
                reason = (
                    "unknown role(s): "
                    + ", ".join(sorted(claims.roles))
                )
            else:
                reason = (
                    f"role(s) {sorted(claims.roles)!r} lack permission "
                    f"for tool {tool_name!r}"
                )
            return self._deny(claims, tool_name, reason=reason)

        # Pick highest-privilege granting role for the audit message.
        winning_role = max(
            granting_roles,
            key=lambda r: self._privilege_rank.get(r, 0),
        )
        return self._allow(
            claims,
            tool_name,
            reason=f"role:{winning_role} grants tool:{tool_name}",
        )

    # ── helpers ─────────────────────────────────────────────────────

    def _allow(
        self,
        claims: JwtClaims,
        tool_name: str,
        *,
        reason: str,
    ) -> ToolAclDecision:
        decision = ToolAclDecision(
            allowed=True,
            tool_name=tool_name,
            subject=claims.subject,
            reason=reason,
        )
        logger.info(
            "acl_decision allowed=True subject=%s tool=%s reason=%s",
            claims.subject,
            tool_name,
            reason,
        )
        return decision

    def _deny(
        self,
        claims: JwtClaims,
        tool_name: str,
        *,
        reason: str,
    ) -> ToolAclDecision:
        decision = ToolAclDecision(
            allowed=False,
            tool_name=tool_name,
            subject=claims.subject,
            reason=reason,
        )
        logger.warning(
            "acl_decision allowed=False subject=%s tool=%s reason=%s",
            claims.subject,
            tool_name,
            reason,
        )
        return decision
