"""L1 Deterministic: Tests for trust/cloud_identity.py -- cloud-agnostic value objects.

Schema validation (A1), immutability, defaults (A2), and roundtrip tests.
All 6 models are frozen (immutable).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from trust.cloud_identity import (
    AccessDecision,
    IdentityContext,
    PermissionBoundary,
    PolicyBinding,
    TemporaryCredentials,
    VerificationResult,
)


# ── A1: Schema Validation ─────────────────────────────────────────────


class TestIdentityContext:
    def test_valid(self):
        ctx = IdentityContext(
            provider="aws",
            principal_id="AROA123",
            display_name="AgentRole",
            account_id="123456789012",
        )
        assert ctx.provider == "aws", (
            "IdentityContext.provider must round-trip from constructor"
        )
        assert ctx.principal_id == "AROA123", (
            "IdentityContext.principal_id must round-trip from constructor"
        )

    def test_rejects_missing_provider(self):
        with pytest.raises(ValidationError):
            IdentityContext(
                principal_id="x", display_name="x", account_id="x"
            )

    def test_rejects_missing_principal_id(self):
        with pytest.raises(ValidationError):
            IdentityContext(
                provider="aws", display_name="x", account_id="x"
            )

    def test_frozen(self):
        ctx = IdentityContext(
            provider="aws", principal_id="x",
            display_name="x", account_id="x",
        )
        with pytest.raises(ValidationError):
            ctx.provider = "gcp"


class TestVerificationResult:
    def test_valid(self):
        result = VerificationResult(
            verified=True, reason="ok", provider="aws",
            checked_at=datetime.now(UTC),
        )
        assert result.verified is True, (
            "VerificationResult.verified must round-trip from constructor"
        )

    def test_rejects_missing_verified(self):
        with pytest.raises(ValidationError):
            VerificationResult(
                reason="ok", provider="aws", checked_at=datetime.now(UTC)
            )

    def test_frozen(self):
        result = VerificationResult(
            verified=True, reason="ok", provider="aws",
            checked_at=datetime.now(UTC),
        )
        with pytest.raises(ValidationError):
            result.verified = False


class TestAccessDecision:
    def test_valid(self):
        decision = AccessDecision(
            allowed=True, reason="policy match", provider="aws",
        )
        assert decision.allowed is True, (
            "AccessDecision.allowed must round-trip from constructor"
        )

    def test_rejects_missing_allowed(self):
        with pytest.raises(ValidationError):
            AccessDecision(reason="ok", provider="aws")

    def test_frozen(self):
        decision = AccessDecision(
            allowed=True, reason="ok", provider="aws",
        )
        with pytest.raises(ValidationError):
            decision.allowed = False


class TestTemporaryCredentials:
    def test_valid(self):
        creds = TemporaryCredentials(
            provider="aws",
            access_token="ASIA123",
            expiry=datetime.now(UTC) + timedelta(minutes=15),
            agent_id="agent-001",
        )
        assert creds.access_token == "ASIA123", (
            "TemporaryCredentials.access_token must round-trip from constructor"
        )

    def test_rejects_missing_access_token(self):
        with pytest.raises(ValidationError):
            TemporaryCredentials(
                provider="aws",
                expiry=datetime.now(UTC),
                agent_id="agent-001",
            )

    def test_frozen(self):
        creds = TemporaryCredentials(
            provider="aws", access_token="x",
            expiry=datetime.now(UTC), agent_id="a1",
        )
        with pytest.raises(ValidationError):
            creds.access_token = "y"


class TestPolicyBinding:
    def test_valid(self):
        binding = PolicyBinding(
            policy_id="arn:aws:iam::123:policy/ReadOnly",
            policy_name="ReadOnly",
            policy_type="managed",
            provider="aws",
        )
        assert binding.policy_name == "ReadOnly", (
            "PolicyBinding.policy_name must round-trip from constructor"
        )

    def test_rejects_missing_policy_id(self):
        with pytest.raises(ValidationError):
            PolicyBinding(
                policy_name="x", policy_type="managed", provider="aws"
            )

    def test_frozen(self):
        binding = PolicyBinding(
            policy_id="x", policy_name="x",
            policy_type="managed", provider="aws",
        )
        with pytest.raises(ValidationError):
            binding.policy_name = "y"


class TestPermissionBoundary:
    def test_valid(self):
        boundary = PermissionBoundary(
            boundary_id="arn:aws:iam::123:policy/Boundary",
            provider="aws",
        )
        assert boundary.boundary_id.startswith("arn:"), (
            "PermissionBoundary.boundary_id must be an AWS ARN starting with 'arn:'"
        )

    def test_rejects_missing_boundary_id(self):
        with pytest.raises(ValidationError):
            PermissionBoundary(provider="aws")

    def test_frozen(self):
        boundary = PermissionBoundary(
            boundary_id="x", provider="aws",
        )
        with pytest.raises(ValidationError):
            boundary.boundary_id = "y"


# ── A2: Defaults ──────────────────────────────────────────────────────


class TestDefaults:
    def test_identity_context_default_roles_empty(self):
        ctx = IdentityContext(
            provider="local", principal_id="x",
            display_name="x", account_id="x",
        )
        assert ctx.roles == [], "IdentityContext.roles must default to empty list"

    def test_identity_context_default_tags_empty(self):
        ctx = IdentityContext(
            provider="local", principal_id="x",
            display_name="x", account_id="x",
        )
        assert ctx.tags == {}, "IdentityContext.tags must default to empty dict"

    def test_identity_context_default_session_expiry_none(self):
        ctx = IdentityContext(
            provider="local", principal_id="x",
            display_name="x", account_id="x",
        )
        assert ctx.session_expiry is None, (
            "IdentityContext.session_expiry must default to None"
        )

    def test_temporary_credentials_default_scope_empty(self):
        creds = TemporaryCredentials(
            provider="local", access_token="t",
            expiry=datetime.now(UTC), agent_id="a1",
        )
        assert creds.scope == [], (
            "TemporaryCredentials.scope must default to empty list"
        )

    def test_temporary_credentials_default_raw_empty(self):
        creds = TemporaryCredentials(
            provider="local", access_token="t",
            expiry=datetime.now(UTC), agent_id="a1",
        )
        assert creds.raw_credentials == {}, (
            "TemporaryCredentials.raw_credentials must default to empty dict"
        )

    def test_access_decision_default_policies_empty(self):
        decision = AccessDecision(
            allowed=True, reason="ok", provider="local",
        )
        assert decision.evaluated_policies == [], (
            "AccessDecision.evaluated_policies must default to empty list"
        )

    def test_permission_boundary_default_max_permissions_empty(self):
        boundary = PermissionBoundary(
            boundary_id="x", provider="local",
        )
        assert boundary.max_permissions == [], (
            "PermissionBoundary.max_permissions must default to empty list"
        )

    def test_policy_binding_default_attached_to_empty(self):
        binding = PolicyBinding(
            policy_id="x", policy_name="x",
            policy_type="inline", provider="local",
        )
        assert binding.attached_to == "", (
            "PolicyBinding.attached_to must default to empty string"
        )


# ── Roundtrip ─────────────────────────────────────────────────────────


class TestRoundtrip:
    def test_identity_context_roundtrip(self):
        ctx = IdentityContext(
            provider="aws", principal_id="AROA123",
            display_name="Role", account_id="123",
            roles=["admin"], tags={"env": "prod"},
        )
        serialized = ctx.model_dump_json()
        deserialized = IdentityContext.model_validate_json(serialized)
        assert deserialized == ctx, (
            "IdentityContext must be equal after JSON round-trip"
        )

    def test_temporary_credentials_roundtrip(self):
        creds = TemporaryCredentials(
            provider="aws", access_token="ASIA",
            expiry=datetime(2027, 1, 1),
            agent_id="a1", scope=["s3:GetObject"],
        )
        serialized = creds.model_dump_json()
        deserialized = TemporaryCredentials.model_validate_json(serialized)
        assert deserialized == creds, (
            "TemporaryCredentials must be equal after JSON round-trip"
        )
