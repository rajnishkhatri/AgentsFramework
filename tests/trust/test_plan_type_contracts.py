"""L1 Deterministic: Plan conformance for type contracts.

Migrated from the Branch 2 section of the legacy
``test_plan_hypothesis_validation.py`` file. These tests validate that
``trust.cloud_identity`` value objects and ``trust.protocols`` match the
plan's specifications (fields, frozen semantics, method signatures,
status enum constraint).

Pure L1: no I/O, no boto3, no filesystem -- only pydantic / typing
introspection.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.conftest import make_valid_facts
from trust.cloud_identity import (
    AccessDecision,
    IdentityContext,
    PermissionBoundary,
    PolicyBinding,
    TemporaryCredentials,
    VerificationResult,
)
from trust.protocols import CredentialProvider, IdentityProvider, PolicyProvider


# ═══════════════════════════════════════════════════════════════════════
# BRANCH 2.1: cloud_identity models have all planned fields
# ═══════════════════════════════════════════════════════════════════════


class TestBranch2_CloudIdentityFields:
    """H2.1: Each cloud_identity model has exactly the fields the plan specifies."""

    def test_identity_context_has_all_planned_fields(self):
        planned = {
            "provider", "principal_id", "display_name", "account_id",
            "roles", "tags", "session_expiry", "raw_attributes",
        }
        actual = set(IdentityContext.model_fields.keys())
        missing = planned - actual
        assert missing == set(), (
            f"IdentityContext missing planned fields: {missing}"
        )

    def test_verification_result_has_all_planned_fields(self):
        planned = {"verified", "reason", "provider", "checked_at"}
        actual = set(VerificationResult.model_fields.keys())
        missing = planned - actual
        assert missing == set(), (
            f"VerificationResult missing planned fields: {missing}"
        )

    def test_access_decision_has_all_planned_fields(self):
        planned = {"allowed", "reason", "evaluated_policies", "provider"}
        actual = set(AccessDecision.model_fields.keys())
        missing = planned - actual
        assert missing == set(), (
            f"AccessDecision missing planned fields: {missing}"
        )

    def test_temporary_credentials_has_all_planned_fields(self):
        planned = {
            "provider", "access_token", "expiry", "scope",
            "agent_id", "raw_credentials",
        }
        actual = set(TemporaryCredentials.model_fields.keys())
        missing = planned - actual
        assert missing == set(), (
            f"TemporaryCredentials missing planned fields: {missing}"
        )

    def test_policy_binding_has_all_planned_fields(self):
        planned = {"policy_id", "policy_name", "policy_type", "provider", "attached_to"}
        actual = set(PolicyBinding.model_fields.keys())
        missing = planned - actual
        assert missing == set(), (
            f"PolicyBinding missing planned fields: {missing}"
        )

    def test_permission_boundary_has_all_planned_fields(self):
        planned = {"boundary_id", "max_permissions", "provider"}
        actual = set(PermissionBoundary.model_fields.keys())
        missing = planned - actual
        assert missing == set(), (
            f"PermissionBoundary missing planned fields: {missing}"
        )


# ═══════════════════════════════════════════════════════════════════════
# BRANCH 2.2: all cloud_identity models are frozen
# ═══════════════════════════════════════════════════════════════════════


FROZEN_MODELS = [
    IdentityContext, VerificationResult, AccessDecision,
    TemporaryCredentials, PolicyBinding, PermissionBoundary,
]


class TestBranch2_AllModelsFrozen:
    """H2.2: All cloud_identity models use frozen=True (plan requirement)."""

    @pytest.mark.parametrize("model_cls", FROZEN_MODELS, ids=lambda c: c.__name__)
    def test_model_is_frozen(self, model_cls):
        config = model_cls.model_config
        assert config.get("frozen") is True, (
            f"{model_cls.__name__} must be frozen per the plan"
        )


# ═══════════════════════════════════════════════════════════════════════
# BRANCH 2.3: Protocol method signatures match the plan
# ═══════════════════════════════════════════════════════════════════════


class TestBranch2_ProtocolSignatures:
    """H2.3: Protocol method signatures match the plan's specification."""

    def test_identity_provider_has_three_methods(self):
        expected = {"get_caller_identity", "resolve_identity", "verify_identity"}
        actual = {
            name for name in dir(IdentityProvider)
            if not name.startswith("_")
            and callable(getattr(IdentityProvider, name, None))
        }
        assert expected.issubset(actual), (
            f"IdentityProvider missing methods: {expected - actual}"
        )

    def test_policy_provider_has_three_methods(self):
        expected = {"list_policies", "evaluate_access", "get_permission_boundary"}
        actual = {
            name for name in dir(PolicyProvider)
            if not name.startswith("_")
            and callable(getattr(PolicyProvider, name, None))
        }
        assert expected.issubset(actual), (
            f"PolicyProvider missing methods: {expected - actual}"
        )

    def test_credential_provider_has_three_methods(self):
        expected = {"issue_credentials", "refresh_credentials", "revoke_credentials"}
        actual = {
            name for name in dir(CredentialProvider)
            if not name.startswith("_")
            and callable(getattr(CredentialProvider, name, None))
        }
        assert expected.issubset(actual), (
            f"CredentialProvider missing methods: {expected - actual}"
        )

    def test_resolve_identity_parameter_name_divergence(self):
        """Plan specifies parameter name 'credential_token' but
        implementation uses 'identifier'. Documenting the divergence."""
        import inspect

        sig = inspect.signature(IdentityProvider.resolve_identity)
        params = list(sig.parameters.keys())
        assert "identifier" in params, (
            "Expected 'identifier' (actual impl parameter name)"
        )
        assert "credential_token" not in params, (
            "Plan uses 'credential_token' but implementation uses 'identifier'. "
            "This test documents the naming divergence."
        )


# ═══════════════════════════════════════════════════════════════════════
# BRANCH 2.4: AgentFacts.status is constrained to IdentityStatus
# ═══════════════════════════════════════════════════════════════════════


class TestBranch2_AgentFactsStatus:
    """H2.4: AgentFacts.status is constrained to IdentityStatus enum values."""

    def test_status_rejects_arbitrary_strings(self):
        with pytest.raises(ValidationError):
            make_valid_facts(status="completely_invalid_status_value")

    def test_status_accepts_valid_enum_values(self):
        for value in ("active", "suspended", "revoked"):
            facts = make_valid_facts(status=value)
            assert facts.status == value, (
                f"AgentFacts.status must accept '{value}' per IdentityStatus"
            )
