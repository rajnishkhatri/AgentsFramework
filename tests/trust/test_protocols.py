"""L1 Deterministic: Tests for trust/protocols.py -- protocol definitions.

Validates runtime_checkable behavior, structural subtyping conformance,
and non-conformance detection.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from trust.cloud_identity import (
    AccessDecision,
    IdentityContext,
    PermissionBoundary,
    PolicyBinding,
    TemporaryCredentials,
    VerificationResult,
)
from trust.models import AgentFacts
from trust.protocols import CredentialProvider, IdentityProvider, PolicyProvider


# ── Stub classes for structural subtyping tests ───────────────────────


class ConformingIdentityProvider:
    def get_caller_identity(self) -> IdentityContext:
        return IdentityContext(
            provider="stub", principal_id="x",
            display_name="x", account_id="x",
        )

    def resolve_identity(self, identifier: str) -> IdentityContext:
        return self.get_caller_identity()

    def verify_identity(self, identity: IdentityContext) -> VerificationResult:
        return VerificationResult(
            verified=True, reason="ok",
            provider="stub", checked_at=datetime.now(UTC),
        )


class ConformingPolicyProvider:
    def list_policies(self, identity: IdentityContext) -> list[PolicyBinding]:
        return []

    def evaluate_access(
        self, identity: IdentityContext, action: str, resource: str
    ) -> AccessDecision:
        return AccessDecision(
            allowed=True, reason="ok", provider="stub",
        )

    def get_permission_boundary(
        self, identity: IdentityContext
    ) -> PermissionBoundary | None:
        return None


class ConformingCredentialProvider:
    def issue_credentials(
        self, agent_facts: AgentFacts, scope: list[str]
    ) -> TemporaryCredentials:
        return TemporaryCredentials(
            provider="stub", access_token="t",
            expiry=datetime.now(UTC) + timedelta(minutes=15),
            agent_id=agent_facts.agent_id,
        )

    def refresh_credentials(
        self, credentials: TemporaryCredentials
    ) -> TemporaryCredentials:
        return credentials

    def revoke_credentials(self, credentials: TemporaryCredentials) -> None:
        pass


class NonConformingEmpty:
    """Has no protocol methods at all."""
    pass


class NonConformingPartialIdentity:
    """Has get_caller_identity but missing others."""
    def get_caller_identity(self) -> IdentityContext:
        return IdentityContext(
            provider="x", principal_id="x",
            display_name="x", account_id="x",
        )


# ── Tests ─────────────────────────────────────────────────────────────


class TestRuntimeCheckable:
    def test_identity_provider_is_runtime_checkable(self):
        assert isinstance(ConformingIdentityProvider(), IdentityProvider), (
            "IdentityProvider must be @runtime_checkable so isinstance works"
        )

    def test_policy_provider_is_runtime_checkable(self):
        assert isinstance(ConformingPolicyProvider(), PolicyProvider), (
            "PolicyProvider must be @runtime_checkable so isinstance works"
        )

    def test_credential_provider_is_runtime_checkable(self):
        assert isinstance(ConformingCredentialProvider(), CredentialProvider), (
            "CredentialProvider must be @runtime_checkable so isinstance works"
        )

    def test_all_protocols_marked_runtime_checkable(self):
        """Directly verify the @runtime_checkable marker attribute.

        Fails if the decorator is removed from any protocol, even if
        isinstance still works for some reason.
        """
        for proto in (IdentityProvider, PolicyProvider, CredentialProvider):
            assert getattr(proto, "_is_runtime_protocol", False) is True, (
                f"{proto.__name__} must be decorated with @runtime_checkable"
            )

    def test_all_protocols_use_typing_protocol(self):
        """H4.1: All three protocols use typing.Protocol, not abc.ABC."""
        from typing import Protocol

        for proto in (IdentityProvider, PolicyProvider, CredentialProvider):
            assert issubclass(type(proto), type(Protocol)), (
                f"{proto.__name__} must be a typing.Protocol subclass"
            )


class TestConformingClasses:
    def test_conforming_class_satisfies_identity_provider(self):
        provider = ConformingIdentityProvider()
        assert isinstance(provider, IdentityProvider)
        ctx = provider.get_caller_identity()
        assert ctx.provider == "stub"

    def test_conforming_class_satisfies_policy_provider(self):
        provider = ConformingPolicyProvider()
        assert isinstance(provider, PolicyProvider)

    def test_conforming_class_satisfies_credential_provider(self):
        provider = ConformingCredentialProvider()
        assert isinstance(provider, CredentialProvider)


class TestNonConformingClasses:
    def test_non_conforming_class_fails_identity_provider(self):
        assert not isinstance(NonConformingEmpty(), IdentityProvider)

    def test_non_conforming_class_fails_policy_provider(self):
        assert not isinstance(NonConformingEmpty(), PolicyProvider)

    def test_non_conforming_class_fails_credential_provider(self):
        assert not isinstance(NonConformingEmpty(), CredentialProvider)

    def test_partial_identity_fails(self):
        assert not isinstance(
            NonConformingPartialIdentity(), IdentityProvider
        )
