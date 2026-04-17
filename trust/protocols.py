"""Cloud-agnostic protocol definitions (hexagonal ports).

Each protocol uses ``typing.Protocol`` (PEP 544, structural subtyping)
so that cloud adapter classes satisfy the interface without inheriting
from an ABC. All protocols are ``@runtime_checkable``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from trust.cloud_identity import (
    AccessDecision,
    IdentityContext,
    PermissionBoundary,
    PolicyBinding,
    TemporaryCredentials,
    VerificationResult,
)
from trust.models import AgentFacts


@runtime_checkable
class IdentityProvider(Protocol):
    """Resolve and verify cloud-native identities."""

    def get_caller_identity(self) -> IdentityContext: ...

    def resolve_identity(self, identifier: str) -> IdentityContext: ...

    def verify_identity(self, identity: IdentityContext) -> VerificationResult: ...


@runtime_checkable
class PolicyProvider(Protocol):
    """Query cloud IAM policies."""

    def list_policies(self, identity: IdentityContext) -> list[PolicyBinding]: ...

    def evaluate_access(
        self, identity: IdentityContext, action: str, resource: str
    ) -> AccessDecision: ...

    def get_permission_boundary(
        self, identity: IdentityContext
    ) -> PermissionBoundary | None: ...


@runtime_checkable
class CredentialProvider(Protocol):
    """Issue, refresh, and revoke short-lived credentials."""

    def issue_credentials(
        self, agent_facts: AgentFacts, scope: list[str]
    ) -> TemporaryCredentials: ...

    def refresh_credentials(
        self, credentials: TemporaryCredentials
    ) -> TemporaryCredentials: ...

    def revoke_credentials(self, credentials: TemporaryCredentials) -> None: ...
