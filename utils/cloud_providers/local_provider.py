"""In-memory implementations of trust protocols for local testing.

Every provider accepts a ``config`` dict in its constructor to control
behaviour -- e.g. set an identity to fail verification so the suspension
cascade can be tested without AWS credentials.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from trust.cloud_identity import (
    AccessDecision,
    IdentityContext,
    PermissionBoundary,
    PolicyBinding,
    TemporaryCredentials,
    VerificationResult,
)
from trust.exceptions import AuthenticationError, AuthorizationError, CredentialError
from trust.models import AgentFacts

_PROVIDER = "local"


class LocalIdentityProvider:
    """Return configurable ``IdentityContext`` values from an in-memory dict."""

    def __init__(self, config: dict[str, dict[str, Any]] | None = None) -> None:
        self._config = config or {}

    def get_caller_identity(self) -> IdentityContext:
        return IdentityContext(
            provider=_PROVIDER,
            principal_id="local-caller",
            display_name="Local Caller",
            account_id="local",
        )

    def resolve_identity(self, identifier: str) -> IdentityContext:
        entry = self._config.get(identifier, {})
        if entry.get("raise_error"):
            raise AuthenticationError(
                f"Simulated authentication failure for {identifier!r}",
                provider=_PROVIDER,
                operation="resolve_identity",
            )
        return IdentityContext(
            provider=_PROVIDER,
            principal_id=identifier,
            display_name=identifier,
            account_id="local",
            roles=entry.get("roles", []),
            tags=entry.get("tags", {}),
        )

    def verify_identity(self, identity: IdentityContext) -> VerificationResult:
        entry = self._config.get(identity.principal_id, {})
        if entry.get("raise_error"):
            raise AuthenticationError(
                f"Simulated verification failure for {identity.principal_id!r}",
                provider=_PROVIDER,
                operation="verify_identity",
            )
        verified = entry.get("verified", True)
        reason = entry.get("reason", "ok" if verified else "failed")
        return VerificationResult(
            verified=verified,
            reason=reason,
            provider=_PROVIDER,
            checked_at=datetime.now(UTC),
        )


class LocalPolicyProvider:
    """Return configurable policy bindings and access decisions."""

    def __init__(self, config: dict[str, dict[str, Any]] | None = None) -> None:
        self._config = config or {}

    def list_policies(self, identity: IdentityContext) -> list[PolicyBinding]:
        entry = self._config.get(identity.principal_id, {})
        if entry.get("raise_error"):
            raise AuthorizationError(
                f"Simulated policy list failure for {identity.principal_id!r}",
                provider=_PROVIDER,
                operation="list_policies",
            )
        raw = entry.get("policies", [])
        return [
            PolicyBinding(
                policy_id=p.get("policy_id", f"local-{i}"),
                policy_name=p.get("policy_name", f"policy-{i}"),
                policy_type=p.get("policy_type", "inline"),
                provider=_PROVIDER,
            )
            for i, p in enumerate(raw)
        ]

    def evaluate_access(
        self, identity: IdentityContext, action: str, resource: str
    ) -> AccessDecision:
        entry = self._config.get(identity.principal_id, {})
        if entry.get("raise_error"):
            raise AuthorizationError(
                f"Simulated access evaluation failure for {identity.principal_id!r}",
                provider=_PROVIDER,
                operation="evaluate_access",
            )
        allowed = entry.get("allowed", True)
        return AccessDecision(
            allowed=allowed,
            reason="local policy" if allowed else "local deny",
            evaluated_policies=[],
            provider=_PROVIDER,
        )

    def get_permission_boundary(
        self, identity: IdentityContext,
    ) -> PermissionBoundary | None:
        entry = self._config.get(identity.principal_id, {})
        boundary = entry.get("boundary")
        if boundary is None:
            return None
        return PermissionBoundary(
            boundary_id=boundary.get("boundary_id", "local-boundary"),
            max_permissions=boundary.get("max_permissions", []),
            provider=_PROVIDER,
        )


class LocalCredentialProvider:
    """Return mock temporary credentials with configurable expiry."""

    def __init__(self, config: dict[str, dict[str, Any]] | None = None) -> None:
        self._config = config or {}

    def issue_credentials(
        self, agent_facts: AgentFacts, scope: list[str],
    ) -> TemporaryCredentials:
        entry = self._config.get(agent_facts.agent_id, {})
        if entry.get("raise_error"):
            raise CredentialError(
                f"Simulated credential issuance failure for {agent_facts.agent_id!r}",
                provider=_PROVIDER,
                operation="issue_credentials",
            )
        ttl = entry.get("ttl_seconds", 900)
        return TemporaryCredentials(
            provider=_PROVIDER,
            access_token=f"local-token-{agent_facts.agent_id}",
            expiry=datetime.now(UTC) + timedelta(seconds=ttl),
            scope=scope or entry.get("scope", []),
            agent_id=agent_facts.agent_id,
        )

    def refresh_credentials(
        self, credentials: TemporaryCredentials,
    ) -> TemporaryCredentials:
        entry = self._config.get(credentials.agent_id, {})
        if entry.get("raise_error"):
            raise CredentialError(
                f"Simulated credential refresh failure for {credentials.agent_id!r}",
                provider=_PROVIDER,
                operation="refresh_credentials",
            )
        ttl = entry.get("ttl_seconds", 900)
        return TemporaryCredentials(
            provider=_PROVIDER,
            access_token=f"local-token-refreshed-{credentials.agent_id}",
            expiry=datetime.now(UTC) + timedelta(seconds=ttl),
            scope=list(credentials.scope),
            agent_id=credentials.agent_id,
        )

    def revoke_credentials(self, credentials: TemporaryCredentials) -> None:
        entry = self._config.get(credentials.agent_id, {})
        if entry.get("raise_error"):
            raise CredentialError(
                f"Simulated credential revocation failure for {credentials.agent_id!r}",
                provider=_PROVIDER,
                operation="revoke_credentials",
            )
