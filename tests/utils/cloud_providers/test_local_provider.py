"""L2 Reproducible: Tests for utils/cloud_providers/local_provider.py.

Contract tests (B4 pattern) + failure path coverage. Each Local*
provider must satisfy its protocol and handle configured error states.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

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
from trust.protocols import CredentialProvider, IdentityProvider, PolicyProvider
from utils.cloud_providers.local_provider import (
    LocalCredentialProvider,
    LocalIdentityProvider,
    LocalPolicyProvider,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _make_facts(**overrides) -> AgentFacts:
    """Factory wrapping ``tests.conftest.make_valid_facts`` for local tests."""
    from tests.conftest import make_valid_facts

    return make_valid_facts(**overrides)


def _make_identity(**overrides) -> IdentityContext:
    """Factory wrapping ``tests.conftest.make_identity_context``.

    Overrides principal/display to match how ``LocalIdentityProvider``
    maps an agent id to an ``IdentityContext`` so tests stay realistic.
    """
    from tests.conftest import make_identity_context

    defaults = {
        "provider": "local",
        "principal_id": "agent-001",
        "display_name": "agent-001",
        "account_id": "local",
    }
    defaults.update(overrides)
    return make_identity_context(**defaults)


# ── Protocol conformance (B4) ────────────────────────────────────────


class TestProtocolConformance:
    def test_local_identity_provider_satisfies_protocol(self):
        assert isinstance(LocalIdentityProvider(), IdentityProvider)

    def test_local_policy_provider_satisfies_protocol(self):
        assert isinstance(LocalPolicyProvider(), PolicyProvider)

    def test_local_credential_provider_satisfies_protocol(self):
        assert isinstance(LocalCredentialProvider(), CredentialProvider)


# ── LocalIdentityProvider ─────────────────────────────────────────────


class TestLocalIdentityProvider:
    def test_get_caller_identity_returns_local_context(self):
        provider = LocalIdentityProvider()
        ctx = provider.get_caller_identity()
        assert isinstance(ctx, IdentityContext)
        assert ctx.provider == "local"
        assert ctx.account_id == "local"

    def test_resolve_identity_returns_configured_context(self):
        config = {
            "agent-001": {"roles": ["writer", "reviewer"], "tags": {"env": "test"}},
        }
        provider = LocalIdentityProvider(config=config)
        ctx = provider.resolve_identity("agent-001")
        assert ctx.principal_id == "agent-001"
        assert ctx.roles == ["writer", "reviewer"]
        assert ctx.tags == {"env": "test"}

    def test_resolve_identity_default_config(self):
        provider = LocalIdentityProvider()
        ctx = provider.resolve_identity("unknown-agent")
        assert ctx.principal_id == "unknown-agent"
        assert ctx.roles == []

    def test_resolve_identity_raises_on_configured_error(self):
        config = {"agent-bad": {"raise_error": True}}
        provider = LocalIdentityProvider(config=config)
        with pytest.raises(AuthenticationError) as exc_info:
            provider.resolve_identity("agent-bad")
        assert exc_info.value.provider == "local"
        assert exc_info.value.operation == "resolve_identity"

    def test_verify_identity_returns_verified_true_by_default(self):
        provider = LocalIdentityProvider()
        identity = _make_identity()
        result = provider.verify_identity(identity)
        assert isinstance(result, VerificationResult)
        assert result.verified is True

    def test_verify_identity_returns_false_when_configured(self):
        config = {"agent-001": {"verified": False, "reason": "expired"}}
        provider = LocalIdentityProvider(config=config)
        identity = _make_identity()
        result = provider.verify_identity(identity)
        assert result.verified is False
        assert result.reason == "expired"

    def test_verify_identity_raises_on_configured_error(self):
        config = {"agent-001": {"raise_error": True}}
        provider = LocalIdentityProvider(config=config)
        identity = _make_identity()
        with pytest.raises(AuthenticationError):
            provider.verify_identity(identity)


# ── LocalPolicyProvider ───────────────────────────────────────────────


class TestLocalPolicyProvider:
    def test_list_policies_returns_configured_bindings(self):
        config = {
            "agent-001": {
                "policies": [
                    {"policy_id": "p1", "policy_name": "ReadOnly", "policy_type": "managed"},
                ],
            },
        }
        provider = LocalPolicyProvider(config=config)
        identity = _make_identity()
        policies = provider.list_policies(identity)
        assert len(policies) == 1
        assert isinstance(policies[0], PolicyBinding)
        assert policies[0].policy_name == "ReadOnly"

    def test_list_policies_empty_default(self):
        provider = LocalPolicyProvider()
        identity = _make_identity()
        policies = provider.list_policies(identity)
        assert policies == []

    def test_list_policies_raises_on_configured_error(self):
        config = {"agent-001": {"raise_error": True}}
        provider = LocalPolicyProvider(config=config)
        identity = _make_identity()
        with pytest.raises(AuthorizationError):
            provider.list_policies(identity)

    def test_evaluate_access_allows_by_default(self):
        provider = LocalPolicyProvider()
        identity = _make_identity()
        decision = provider.evaluate_access(identity, "read", "document")
        assert isinstance(decision, AccessDecision)
        assert decision.allowed is True

    def test_evaluate_access_denies_when_configured(self):
        config = {"agent-001": {"allowed": False}}
        provider = LocalPolicyProvider(config=config)
        identity = _make_identity()
        decision = provider.evaluate_access(identity, "delete", "document")
        assert decision.allowed is False

    def test_evaluate_access_raises_on_configured_error(self):
        config = {"agent-001": {"raise_error": True}}
        provider = LocalPolicyProvider(config=config)
        identity = _make_identity()
        with pytest.raises(AuthorizationError):
            provider.evaluate_access(identity, "read", "doc")

    def test_get_permission_boundary_returns_none_by_default(self):
        provider = LocalPolicyProvider()
        identity = _make_identity()
        assert provider.get_permission_boundary(identity) is None

    def test_get_permission_boundary_returns_configured(self):
        config = {
            "agent-001": {
                "boundary": {
                    "boundary_id": "b1",
                    "max_permissions": ["s3:GetObject"],
                },
            },
        }
        provider = LocalPolicyProvider(config=config)
        identity = _make_identity()
        boundary = provider.get_permission_boundary(identity)
        assert isinstance(boundary, PermissionBoundary)
        assert boundary.boundary_id == "b1"
        assert "s3:GetObject" in boundary.max_permissions


# ── LocalCredentialProvider ───────────────────────────────────────────


class TestLocalCredentialProvider:
    def test_issue_credentials_returns_valid_temporary_credentials(self):
        provider = LocalCredentialProvider()
        facts = _make_facts()
        creds = provider.issue_credentials(facts, scope=["s3:GetObject"])
        assert isinstance(creds, TemporaryCredentials)
        assert creds.provider == "local"
        assert creds.agent_id == "agent-001"
        assert creds.scope == ["s3:GetObject"]
        assert creds.expiry > datetime.now(UTC)

    def test_issue_credentials_uses_configured_ttl(self):
        config = {"agent-001": {"ttl_seconds": 60}}
        provider = LocalCredentialProvider(config=config)
        facts = _make_facts()
        creds = provider.issue_credentials(facts, scope=[])
        expected_max = datetime.now(UTC) + timedelta(seconds=65)
        expected_min = datetime.now(UTC) + timedelta(seconds=55)
        assert expected_min < creds.expiry < expected_max

    def test_issue_credentials_raises_on_configured_error(self):
        config = {"agent-001": {"raise_error": True}}
        provider = LocalCredentialProvider(config=config)
        facts = _make_facts()
        with pytest.raises(CredentialError):
            provider.issue_credentials(facts, scope=[])

    def test_refresh_credentials_returns_new_token(self):
        provider = LocalCredentialProvider()
        facts = _make_facts()
        original = provider.issue_credentials(facts, scope=[])
        refreshed = provider.refresh_credentials(original)
        assert isinstance(refreshed, TemporaryCredentials)
        assert refreshed.access_token != original.access_token
        assert refreshed.agent_id == original.agent_id

    def test_refresh_credentials_raises_on_configured_error(self):
        config = {"agent-001": {"raise_error": True}}
        provider = LocalCredentialProvider(config=config)
        facts = _make_facts(agent_id="agent-002")
        creds = provider.issue_credentials(facts, scope=[])
        creds_with_bad_id = TemporaryCredentials(
            provider="local", access_token="x",
            expiry=datetime.now(UTC) + timedelta(minutes=15),
            agent_id="agent-001",
        )
        with pytest.raises(CredentialError):
            provider.refresh_credentials(creds_with_bad_id)

    def test_revoke_credentials_succeeds_silently(self):
        provider = LocalCredentialProvider()
        facts = _make_facts()
        creds = provider.issue_credentials(facts, scope=[])
        provider.revoke_credentials(creds)

    def test_revoke_credentials_raises_on_configured_error(self):
        config = {"agent-001": {"raise_error": True}}
        provider = LocalCredentialProvider(config=config)
        creds = TemporaryCredentials(
            provider="local", access_token="x",
            expiry=datetime.now(UTC) + timedelta(minutes=15),
            agent_id="agent-001",
        )
        with pytest.raises(CredentialError):
            provider.revoke_credentials(creds)


# ═══════════════════════════════════════════════════════════════════════
# Branch 5.4: full identity -> policy -> credential lifecycle
# Migrated from the legacy test_plan_hypothesis_validation.py suite.
# ═══════════════════════════════════════════════════════════════════════


class TestLocalFullLifecycle:
    """H5.4: Local provider supports the complete identity -> policy ->
    credential lifecycle without errors."""

    def test_full_lifecycle(self):
        config = {
            "agent-001": {
                "roles": ["writer"],
                "tags": {"env": "test"},
                "verified": True,
                "allowed": True,
                "policies": [
                    {
                        "policy_id": "p1",
                        "policy_name": "WriterPolicy",
                        "policy_type": "managed",
                    },
                ],
            },
        }
        identity_prov = LocalIdentityProvider(config=config)
        policy_prov = LocalPolicyProvider(config=config)
        cred_prov = LocalCredentialProvider(config=config)

        ctx = identity_prov.resolve_identity("agent-001")
        assert ctx.principal_id == "agent-001", (
            "resolve_identity must round-trip the requested agent id"
        )

        verification = identity_prov.verify_identity(ctx)
        assert verification.verified is True, (
            "verify_identity must honor the configured verified=True flag"
        )

        policies = policy_prov.list_policies(ctx)
        assert len(policies) == 1, (
            "list_policies must surface the configured WriterPolicy binding"
        )

        decision = policy_prov.evaluate_access(ctx, "write", "document")
        assert decision.allowed is True, (
            "evaluate_access must allow when config.allowed=True"
        )

        facts = _make_facts()
        creds = cred_prov.issue_credentials(facts, scope=["write"])
        assert creds.agent_id == "agent-001", (
            "issue_credentials must stamp the agent_id from AgentFacts"
        )

        refreshed = cred_prov.refresh_credentials(creds)
        assert refreshed.access_token != creds.access_token, (
            "refresh_credentials must mint a new access_token"
        )

        # Should succeed silently -- any raise indicates lifecycle failure.
        cred_prov.revoke_credentials(refreshed)
