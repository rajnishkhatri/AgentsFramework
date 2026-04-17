"""L2 Reproducible: Tests for AWS adapters with mocked boto3 clients.

No live AWS calls (Anti-Pattern 5 prevention). All boto3 interactions
are mocked via unittest.mock. Failure paths tested first.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from trust.cloud_identity import (
    AccessDecision,
    IdentityContext,
    PermissionBoundary,
    PolicyBinding,
    TemporaryCredentials,
    VerificationResult,
)
from trust.exceptions import AuthenticationError, AuthorizationError, CredentialError
from trust.models import AgentFacts, Capability
from trust.protocols import CredentialProvider, IdentityProvider, PolicyProvider
from utils.cloud_providers.aws_credentials import AWSCredentialProvider
from utils.cloud_providers.aws_identity import AWSIdentityProvider, _parse_arn
from utils.cloud_providers.aws_policy import AWSPolicyProvider
from utils.cloud_providers.config import TrustProviderSettings


# ── Helpers ───────────────────────────────────────────────────────────


def _settings() -> TrustProviderSettings:
    return TrustProviderSettings(
        provider="aws", _env_file=None,  # type: ignore[call-arg]
    )


def _make_facts(**overrides) -> AgentFacts:
    """AWS-flavored AgentFacts factory with default role_arn metadata.

    Wraps ``tests.conftest.make_valid_facts`` with AWS-specific defaults
    so boto3-mocked tests can call ``sts.assume_role`` without extra
    setup.
    """
    from tests.conftest import make_valid_facts

    defaults = {
        "metadata": {"role_arn": "arn:aws:iam::123456789012:role/agent-001"},
    }
    defaults.update(overrides)
    return make_valid_facts(**defaults)


def _make_identity(**overrides) -> IdentityContext:
    """AWS-flavored IdentityContext factory."""
    from tests.conftest import make_identity_context

    defaults = {
        "provider": "aws",
        "principal_id": "AROA12345",
        "display_name": "AgentRole",
        "account_id": "123456789012",
        "roles": ["AgentRole"],
    }
    defaults.update(overrides)
    return make_identity_context(**defaults)


def _client_error(code: str = "AccessDenied", msg: str = "denied") -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": msg}},
        "TestOperation",
    )


# ── Pure function: _parse_arn ─────────────────────────────────────────


class TestParseArn:
    def test_extracts_all_fields(self):
        arn = "arn:aws:iam::123456789012:role/AgentRole"
        parsed = _parse_arn(arn)
        assert parsed["partition"] == "aws"
        assert parsed["service"] == "iam"
        assert parsed["account_id"] == "123456789012"
        assert parsed["resource"] == "role/AgentRole"

    def test_handles_short_arn(self):
        parsed = _parse_arn("arn:aws")
        assert parsed["partition"] == "aws"
        assert parsed["service"] == ""


# ── AWSIdentityProvider ──────────────────────────────────────────────


class TestAWSIdentityProvider:
    @patch("utils.cloud_providers.aws_identity.boto3")
    def test_satisfies_protocol(self, mock_boto3):
        provider = AWSIdentityProvider(_settings())
        assert isinstance(provider, IdentityProvider)

    @patch("utils.cloud_providers.aws_identity.boto3")
    def test_get_caller_identity_maps_sts_response(self, mock_boto3):
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "UserId": "AROA12345:session",
            "Account": "123456789012",
            "Arn": "arn:aws:sts::123456789012:assumed-role/AgentRole/session",
        }
        mock_boto3.client.side_effect = lambda svc, **kw: mock_sts if svc == "sts" else MagicMock()
        provider = AWSIdentityProvider(_settings())
        ctx = provider.get_caller_identity()
        assert isinstance(ctx, IdentityContext)
        assert ctx.provider == "aws"
        assert ctx.principal_id == "AROA12345:session"
        assert ctx.account_id == "123456789012"

    @patch("utils.cloud_providers.aws_identity.boto3")
    def test_get_caller_identity_raises_on_sts_error(self, mock_boto3):
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = _client_error()
        mock_boto3.client.side_effect = lambda svc, **kw: mock_sts if svc == "sts" else MagicMock()
        provider = AWSIdentityProvider(_settings())
        with pytest.raises(AuthenticationError) as exc_info:
            provider.get_caller_identity()
        assert exc_info.value.provider == "aws"
        assert exc_info.value.operation == "get_caller_identity"

    @patch("utils.cloud_providers.aws_identity.boto3")
    def test_resolve_identity_maps_iam_role(self, mock_boto3):
        mock_sts = MagicMock()
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "ASSUMED_KEY",
                "SecretAccessKey": "ASSUMED_SECRET",
                "SessionToken": "ASSUMED_TOKEN",
            },
        }
        mock_iam = MagicMock()
        mock_iam.get_role.return_value = {
            "Role": {
                "RoleName": "AgentRole",
                "RoleId": "AROA12345",
                "Arn": "arn:aws:iam::123456789012:role/AgentRole",
            },
        }
        mock_iam.list_role_tags.return_value = {
            "Tags": [{"Key": "env", "Value": "prod"}],
        }

        def client_factory(svc, **kw):
            if svc == "sts" and "aws_access_key_id" not in kw:
                return mock_sts
            if svc == "iam":
                return mock_iam
            return MagicMock()

        mock_boto3.client.side_effect = client_factory
        provider = AWSIdentityProvider(_settings())
        ctx = provider.resolve_identity("arn:aws:iam::123456789012:role/AgentRole")
        assert ctx.display_name == "AgentRole"
        assert ctx.tags == {"env": "prod"}
        assert "AgentRole" in ctx.roles
        mock_sts.assume_role.assert_called_once()

    @patch("utils.cloud_providers.aws_identity.boto3")
    def test_resolve_identity_raises_on_assume_role_error(self, mock_boto3):
        mock_sts = MagicMock()
        mock_sts.assume_role.side_effect = _client_error("AccessDenied", "denied")
        mock_boto3.client.side_effect = lambda svc, **kw: mock_sts if svc == "sts" else MagicMock()
        provider = AWSIdentityProvider(_settings())
        with pytest.raises(AuthenticationError) as exc_info:
            provider.resolve_identity("arn:aws:iam::123:role/Missing")
        assert exc_info.value.operation == "resolve_identity"

    @patch("utils.cloud_providers.aws_identity.boto3")
    def test_verify_identity_returns_false_when_expired(self, mock_boto3):
        provider = AWSIdentityProvider(_settings())
        identity = _make_identity(
            session_expiry=datetime.now(UTC) - timedelta(hours=1),
        )
        result = provider.verify_identity(identity)
        assert isinstance(result, VerificationResult)
        assert result.verified is False
        assert "expired" in result.reason.lower()

    @patch("utils.cloud_providers.aws_identity.boto3")
    def test_verify_identity_returns_true_when_valid(self, mock_boto3):
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "UserId": "X", "Account": "X", "Arn": "arn:aws:iam::X:user/X",
        }
        mock_boto3.client.side_effect = lambda svc, **kw: mock_sts if svc == "sts" else MagicMock()
        provider = AWSIdentityProvider(_settings())
        identity = _make_identity()
        result = provider.verify_identity(identity)
        assert result.verified is True

    @patch("utils.cloud_providers.aws_identity.boto3")
    def test_verify_identity_returns_false_on_sts_error(self, mock_boto3):
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = _client_error()
        mock_boto3.client.side_effect = lambda svc, **kw: mock_sts if svc == "sts" else MagicMock()
        provider = AWSIdentityProvider(_settings())
        identity = _make_identity()
        result = provider.verify_identity(identity)
        assert result.verified is False


# ── AWSPolicyProvider ─────────────────────────────────────────────────


class TestAWSPolicyProvider:
    @patch("utils.cloud_providers.aws_policy.boto3")
    def test_satisfies_protocol(self, mock_boto3):
        provider = AWSPolicyProvider(_settings())
        assert isinstance(provider, PolicyProvider)

    @patch("utils.cloud_providers.aws_policy.boto3")
    def test_list_policies_combines_managed_and_inline(self, mock_boto3):
        mock_iam = MagicMock()
        attached_paginator = MagicMock()
        attached_paginator.paginate.return_value = [
            {"AttachedPolicies": [{"PolicyArn": "arn:aws:iam::123:policy/ReadOnly", "PolicyName": "ReadOnly"}]},
        ]
        inline_paginator = MagicMock()
        inline_paginator.paginate.return_value = [
            {"PolicyNames": ["InlineWrite"]},
        ]
        mock_iam.get_paginator.side_effect = lambda name: (
            attached_paginator if name == "list_attached_role_policies" else inline_paginator
        )
        mock_boto3.client.return_value = mock_iam
        provider = AWSPolicyProvider(_settings())
        identity = _make_identity()
        policies = provider.list_policies(identity)
        assert len(policies) == 2
        assert all(isinstance(p, PolicyBinding) for p in policies)
        types = {p.policy_type for p in policies}
        assert "managed" in types
        assert "inline" in types

    @patch("utils.cloud_providers.aws_policy.boto3")
    def test_list_policies_raises_on_iam_error(self, mock_boto3):
        mock_iam = MagicMock()
        mock_iam.get_paginator.side_effect = _client_error()
        mock_boto3.client.return_value = mock_iam
        provider = AWSPolicyProvider(_settings())
        identity = _make_identity()
        with pytest.raises(AuthorizationError) as exc_info:
            provider.list_policies(identity)
        assert exc_info.value.operation == "list_policies"

    @patch("utils.cloud_providers.aws_policy.boto3")
    def test_evaluate_access_maps_simulator_response(self, mock_boto3):
        mock_iam = MagicMock()
        mock_iam.simulate_principal_policy.return_value = {
            "EvaluationResults": [
                {"EvalDecision": "allowed", "EvalDecisionDetails": {}},
            ],
        }
        mock_boto3.client.return_value = mock_iam
        provider = AWSPolicyProvider(_settings())
        identity = _make_identity()
        decision = provider.evaluate_access(identity, "s3:GetObject", "arn:aws:s3:::bucket/*")
        assert isinstance(decision, AccessDecision)
        assert decision.allowed is True

    @patch("utils.cloud_providers.aws_policy.boto3")
    def test_evaluate_access_denied_result(self, mock_boto3):
        mock_iam = MagicMock()
        mock_iam.simulate_principal_policy.return_value = {
            "EvaluationResults": [
                {"EvalDecision": "implicitDeny", "EvalDecisionDetails": {}},
            ],
        }
        mock_boto3.client.return_value = mock_iam
        provider = AWSPolicyProvider(_settings())
        identity = _make_identity()
        decision = provider.evaluate_access(identity, "s3:DeleteBucket", "arn:aws:s3:::bucket")
        assert decision.allowed is False

    @patch("utils.cloud_providers.aws_policy.boto3")
    def test_evaluate_access_raises_on_iam_error(self, mock_boto3):
        mock_iam = MagicMock()
        mock_iam.simulate_principal_policy.side_effect = _client_error()
        mock_boto3.client.return_value = mock_iam
        provider = AWSPolicyProvider(_settings())
        identity = _make_identity()
        with pytest.raises(AuthorizationError):
            provider.evaluate_access(identity, "s3:GetObject", "arn:aws:s3:::bucket/*")

    @patch("utils.cloud_providers.aws_policy.boto3")
    def test_get_permission_boundary_returns_none_when_absent(self, mock_boto3):
        mock_iam = MagicMock()
        mock_iam.get_role.return_value = {"Role": {"RoleName": "AgentRole"}}
        mock_boto3.client.return_value = mock_iam
        provider = AWSPolicyProvider(_settings())
        identity = _make_identity()
        assert provider.get_permission_boundary(identity) is None

    @patch("utils.cloud_providers.aws_policy.boto3")
    def test_get_permission_boundary_returns_boundary_when_present(self, mock_boto3):
        mock_iam = MagicMock()
        mock_iam.get_role.return_value = {
            "Role": {
                "RoleName": "AgentRole",
                "PermissionsBoundary": {
                    "PermissionsBoundaryArn": "arn:aws:iam::123:policy/Boundary",
                },
            },
        }
        mock_iam.get_policy.return_value = {
            "Policy": {"DefaultVersionId": "v1"},
        }
        mock_iam.get_policy_version.return_value = {
            "PolicyVersion": {
                "Document": {
                    "Statement": [
                        {"Effect": "Allow", "Action": ["s3:GetObject"]},
                    ],
                },
            },
        }
        mock_boto3.client.return_value = mock_iam
        provider = AWSPolicyProvider(_settings())
        identity = _make_identity()
        boundary = provider.get_permission_boundary(identity)
        assert isinstance(boundary, PermissionBoundary)
        assert boundary.boundary_id == "arn:aws:iam::123:policy/Boundary"
        assert boundary.max_permissions == ["s3:GetObject"]


# ── AWSCredentialProvider ─────────────────────────────────────────────


class TestAWSCredentialProvider:
    @patch("utils.cloud_providers.aws_credentials.boto3")
    def test_satisfies_protocol(self, mock_boto3):
        provider = AWSCredentialProvider(_settings())
        assert isinstance(provider, CredentialProvider)

    @patch("utils.cloud_providers.aws_credentials.boto3")
    def test_issue_credentials_calls_assume_role(self, mock_boto3):
        mock_sts = MagicMock()
        expiry = datetime.now(UTC) + timedelta(minutes=15)
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "ASIA_TEST",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
                "Expiration": expiry,
            },
        }
        mock_boto3.client.return_value = mock_sts
        provider = AWSCredentialProvider(_settings())
        facts = _make_facts()
        creds = provider.issue_credentials(facts, scope=["s3:GetObject"])
        assert isinstance(creds, TemporaryCredentials)
        assert creds.access_token == "ASIA_TEST"
        assert creds.agent_id == "agent-001"
        mock_sts.assume_role.assert_called_once()

    @patch("utils.cloud_providers.aws_credentials.boto3")
    def test_issue_credentials_sets_session_name_to_agent_id(self, mock_boto3):
        mock_sts = MagicMock()
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "X", "SecretAccessKey": "X",
                "SessionToken": "X", "Expiration": datetime.now(UTC),
            },
        }
        mock_boto3.client.return_value = mock_sts
        provider = AWSCredentialProvider(_settings())
        facts = _make_facts(agent_id="my-agent-42")
        provider.issue_credentials(facts, scope=[])
        call_kwargs = mock_sts.assume_role.call_args[1]
        assert call_kwargs["RoleSessionName"] == "my-agent-42"

    @patch("utils.cloud_providers.aws_credentials.boto3")
    def test_issue_credentials_applies_scope_as_session_policy(self, mock_boto3):
        mock_sts = MagicMock()
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "X", "SecretAccessKey": "X",
                "SessionToken": "X", "Expiration": datetime.now(UTC),
            },
        }
        mock_boto3.client.return_value = mock_sts
        provider = AWSCredentialProvider(_settings())
        facts = _make_facts()
        provider.issue_credentials(facts, scope=["s3:GetObject"])
        call_kwargs = mock_sts.assume_role.call_args[1]
        assert "Policy" in call_kwargs
        assert "s3:GetObject" in call_kwargs["Policy"]

    @patch("utils.cloud_providers.aws_credentials.boto3")
    def test_issue_credentials_no_policy_without_scope(self, mock_boto3):
        mock_sts = MagicMock()
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "X", "SecretAccessKey": "X",
                "SessionToken": "X", "Expiration": datetime.now(UTC),
            },
        }
        mock_boto3.client.return_value = mock_sts
        provider = AWSCredentialProvider(_settings())
        facts = _make_facts()
        provider.issue_credentials(facts, scope=[])
        call_kwargs = mock_sts.assume_role.call_args[1]
        assert "Policy" not in call_kwargs

    @patch("utils.cloud_providers.aws_credentials.boto3")
    def test_issue_credentials_raises_on_sts_error(self, mock_boto3):
        mock_sts = MagicMock()
        mock_sts.assume_role.side_effect = _client_error()
        mock_boto3.client.return_value = mock_sts
        provider = AWSCredentialProvider(_settings())
        facts = _make_facts()
        with pytest.raises(CredentialError) as exc_info:
            provider.issue_credentials(facts, scope=[])
        assert exc_info.value.operation == "issue_credentials"

    @patch("utils.cloud_providers.aws_credentials.boto3")
    def test_refresh_credentials_re_issues(self, mock_boto3):
        mock_sts = MagicMock()
        new_expiry = datetime.now(UTC) + timedelta(minutes=15)
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "ASIA_NEW",
                "SecretAccessKey": "new_secret",
                "SessionToken": "new_token",
                "Expiration": new_expiry,
            },
        }
        mock_boto3.client.return_value = mock_sts
        provider = AWSCredentialProvider(_settings())
        old_creds = TemporaryCredentials(
            provider="aws",
            access_token="ASIA_OLD",
            expiry=datetime.now(UTC) - timedelta(minutes=1),
            agent_id="agent-001",
            raw_credentials={"RoleArn": "arn:aws:iam::123:role/AgentRole"},
        )
        new_creds = provider.refresh_credentials(old_creds)
        assert new_creds.access_token == "ASIA_NEW"
        assert new_creds.agent_id == "agent-001"

    @patch("utils.cloud_providers.aws_credentials.boto3")
    def test_refresh_credentials_raises_when_no_role_arn(self, mock_boto3):
        provider = AWSCredentialProvider(_settings())
        old_creds = TemporaryCredentials(
            provider="aws",
            access_token="ASIA_OLD",
            expiry=datetime.now(UTC),
            agent_id="agent-001",
            raw_credentials={},
        )
        with pytest.raises(CredentialError) as exc_info:
            provider.refresh_credentials(old_creds)
        assert exc_info.value.operation == "refresh_credentials"

    @patch("utils.cloud_providers.aws_credentials.boto3")
    def test_revoke_credentials_raises_not_implemented(self, mock_boto3):
        provider = AWSCredentialProvider(_settings())
        creds = TemporaryCredentials(
            provider="aws",
            access_token="X",
            expiry=datetime.now(UTC),
            agent_id="agent-001",
        )
        with pytest.raises(NotImplementedError):
            provider.revoke_credentials(creds)


# ═══════════════════════════════════════════════════════════════════════
# Plan conformance (migrated from Branch 3 / Branch 5 / CrossBranch
# of the legacy test_plan_hypothesis_validation.py suite).
# Each test maps directly to a falsifiable hypothesis (H3.x).
# ═══════════════════════════════════════════════════════════════════════


class TestAWSPlanConformance:
    """Branch 3 hypotheses (H3.1-H3.7) and Branch 5.5/5.6 plan conformance."""

    @patch("utils.cloud_providers.aws_credentials.boto3")
    def test_h3_1_issue_then_refresh_roundtrip_succeeds(self, mock_boto3):
        """H3.1: issue -> refresh lifecycle works end-to-end (GAP-1 fixed)."""
        mock_sts = MagicMock()
        expiry = datetime.now(UTC) + timedelta(minutes=15)
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "ASIA_TEST",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
                "Expiration": expiry,
            },
        }
        mock_boto3.client.return_value = mock_sts
        provider = AWSCredentialProvider(_settings())
        facts = _make_facts(
            metadata={"role_arn": "arn:aws:iam::123:role/TestRole"},
        )
        issued = provider.issue_credentials(facts, scope=["s3:GetObject"])
        assert "RoleArn" in issued.raw_credentials, (
            "RoleArn must be present in raw_credentials for a later refresh"
        )
        refreshed = provider.refresh_credentials(issued)
        assert refreshed.access_token == "ASIA_TEST"
        assert "RoleArn" in refreshed.raw_credentials

    @patch("utils.cloud_providers.aws_identity.boto3")
    def test_h3_2_resolve_identity_calls_sts_assume_role(self, mock_boto3):
        """H3.2: resolve_identity calls sts.assume_role() (GAP-2 fixed)."""
        mock_sts = MagicMock()
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "ASSUMED_KEY",
                "SecretAccessKey": "ASSUMED_SECRET",
                "SessionToken": "ASSUMED_TOKEN",
            },
        }
        mock_iam = MagicMock()
        mock_iam.get_role.return_value = {
            "Role": {
                "RoleName": "AgentRole",
                "RoleId": "AROA12345",
                "Arn": "arn:aws:iam::123456789012:role/AgentRole",
            },
        }
        mock_iam.list_role_tags.return_value = {"Tags": []}

        def client_factory(svc, **kw):
            if svc == "sts" and "aws_access_key_id" not in kw:
                return mock_sts
            if svc == "iam" and "aws_access_key_id" in kw:
                return mock_iam
            return MagicMock()

        mock_boto3.client.side_effect = client_factory
        provider = AWSIdentityProvider(_settings())
        ctx = provider.resolve_identity(
            "arn:aws:iam::123456789012:role/AgentRole"
        )
        mock_sts.assume_role.assert_called_once()
        assert ctx.display_name == "AgentRole"

    @patch("utils.cloud_providers.aws_identity.boto3")
    def test_h3_3_verify_uses_subject_credentials(self, mock_boto3):
        """H3.3: verify_identity creates a subject-scoped STS client (GAP-3 fixed)."""
        mock_provider_sts = MagicMock()
        mock_subject_sts = MagicMock()
        mock_subject_sts.get_caller_identity.return_value = {
            "UserId": "X", "Account": "X", "Arn": "arn:aws:iam::X:user/X",
        }

        def client_factory(svc, **kw):
            if svc == "sts" and "aws_access_key_id" in kw:
                assert kw["aws_access_key_id"] == "SUBJECT_KEY"
                assert kw["aws_secret_access_key"] == "SUBJECT_SECRET"
                assert kw["aws_session_token"] == "SUBJECT_TOKEN"
                return mock_subject_sts
            if svc == "sts":
                return mock_provider_sts
            return MagicMock()

        mock_boto3.client.side_effect = client_factory
        provider = AWSIdentityProvider(_settings())
        identity = _make_identity(
            raw_attributes={
                "AccessKeyId": "SUBJECT_KEY",
                "SecretAccessKey": "SUBJECT_SECRET",
                "SessionToken": "SUBJECT_TOKEN",
            },
        )
        result = provider.verify_identity(identity)
        assert result.verified is True
        mock_subject_sts.get_caller_identity.assert_called_once()
        mock_provider_sts.get_caller_identity.assert_not_called()

    def test_h3_4_missing_role_arn_raises_credential_error(self):
        """H3.4: _resolve_role_arn requires explicit role_arn (GAP-6 fixed)."""
        from tests.conftest import make_valid_facts

        facts = make_valid_facts()  # no role_arn metadata
        with pytest.raises(CredentialError) as exc_info:
            AWSCredentialProvider._resolve_role_arn(facts)
        assert "role_arn" in str(exc_info.value)

    def test_h3_4_explicit_role_arn_returned(self):
        facts = _make_facts(
            metadata={"role_arn": "arn:aws:iam::123:role/TestRole"},
        )
        arn = AWSCredentialProvider._resolve_role_arn(facts)
        assert arn == "arn:aws:iam::123:role/TestRole"

    def test_h3_5_session_policy_is_valid_iam_json(self):
        """H3.5: _build_session_policy produces valid IAM policy JSON."""
        policy_str = AWSCredentialProvider._build_session_policy(
            ["s3:GetObject"]
        )
        policy = json.loads(policy_str)
        assert policy["Version"] == "2012-10-17"
        assert len(policy["Statement"]) == 1
        assert policy["Statement"][0]["Effect"] == "Allow"
        assert policy["Statement"][0]["Action"] == ["s3:GetObject"]
        assert policy["Statement"][0]["Resource"] == "*"

    def test_h3_5_session_policy_with_multiple_actions(self):
        actions = ["s3:GetObject", "s3:PutObject", "dynamodb:GetItem"]
        policy_str = AWSCredentialProvider._build_session_policy(actions)
        policy = json.loads(policy_str)
        assert policy["Statement"][0]["Action"] == actions

    @patch("utils.cloud_providers.aws_policy.boto3")
    def test_h3_6_empty_evaluation_results_returns_denied(self, mock_boto3):
        """H3.6: evaluate_access handles empty EvaluationResults gracefully."""
        mock_iam = MagicMock()
        mock_iam.simulate_principal_policy.return_value = {
            "EvaluationResults": [],
        }
        mock_boto3.client.return_value = mock_iam
        provider = AWSPolicyProvider(_settings())
        identity = _make_identity()
        decision = provider.evaluate_access(
            identity, "s3:GetObject", "arn:aws:s3:::b/*"
        )
        assert decision.allowed is False
        assert "No evaluation results" in decision.reason

    @patch("utils.cloud_providers.aws_policy.boto3")
    def test_h3_7_max_permissions_populated_from_policy(self, mock_boto3):
        """H3.7: PermissionBoundary.max_permissions is populated (GAP-7 fixed)."""
        mock_iam = MagicMock()
        mock_iam.get_role.return_value = {
            "Role": {
                "RoleName": "AgentRole",
                "PermissionsBoundary": {
                    "PermissionsBoundaryArn": "arn:aws:iam::123:policy/Boundary",
                },
            },
        }
        mock_iam.get_policy.return_value = {
            "Policy": {"DefaultVersionId": "v1"},
        }
        mock_iam.get_policy_version.return_value = {
            "PolicyVersion": {
                "Document": {
                    "Statement": [
                        {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"]},
                        {"Effect": "Allow", "Action": "dynamodb:GetItem"},
                    ],
                },
            },
        }
        mock_boto3.client.return_value = mock_iam
        provider = AWSPolicyProvider(_settings())
        identity = _make_identity()
        boundary = provider.get_permission_boundary(identity)
        assert boundary is not None
        assert boundary.max_permissions == [
            "s3:GetObject", "s3:PutObject", "dynamodb:GetItem",
        ]

    @patch("utils.cloud_providers.aws_credentials.boto3")
    def test_h5_5_revoke_raises_not_implemented_phase1(self, mock_boto3):
        """H5.5: revoke_credentials raises NotImplementedError (Phase 1)."""
        provider = AWSCredentialProvider(_settings())
        creds = TemporaryCredentials(
            provider="aws", access_token="X",
            expiry=datetime.now(UTC), agent_id="a1",
        )
        with pytest.raises(NotImplementedError, match="Phase 1"):
            provider.revoke_credentials(creds)

    def test_h5_6_sts_assumed_role_arn_parses(self):
        """H5.6: _parse_arn handles STS assumed-role ARN format."""
        parsed = _parse_arn(
            "arn:aws:sts::123456789012:assumed-role/AgentRole/session"
        )
        assert parsed["service"] == "sts"
        assert parsed["account_id"] == "123456789012"


class TestAgentFactsToIAMMapping:
    """CrossBranch: AgentFacts-to-AWS-IAM Mapping Strategy.

    Depends on type contracts (Branch 2) and adapter behavior (Branch 3).
    """

    @patch("utils.cloud_providers.aws_credentials.boto3")
    def test_agent_id_maps_to_session_name(self, mock_boto3):
        """Plan: RoleSessionName = agent_id from AgentFacts."""
        mock_sts = MagicMock()
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "X", "SecretAccessKey": "X",
                "SessionToken": "X",
                "Expiration": datetime.now(UTC) + timedelta(minutes=15),
            },
        }
        mock_boto3.client.return_value = mock_sts
        provider = AWSCredentialProvider(_settings())
        facts = _make_facts(
            agent_id="my-writer-agent",
            metadata={"role_arn": "arn:aws:iam::123:role/my-writer-agent"},
        )
        provider.issue_credentials(facts, scope=[])
        call_kwargs = mock_sts.assume_role.call_args[1]
        assert call_kwargs["RoleSessionName"] == "my-writer-agent"

    @patch("utils.cloud_providers.aws_credentials.boto3")
    def test_ttl_maps_to_duration_seconds(self, mock_boto3):
        """Plan: valid_until -> STS DurationSeconds. Implementation uses
        metadata.credential_ttl_seconds to express the same contract."""
        mock_sts = MagicMock()
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "X", "SecretAccessKey": "X",
                "SessionToken": "X",
                "Expiration": datetime.now(UTC) + timedelta(minutes=30),
            },
        }
        mock_boto3.client.return_value = mock_sts
        provider = AWSCredentialProvider(_settings())
        facts = _make_facts(
            metadata={
                "credential_ttl_seconds": 1800,
                "role_arn": "arn:aws:iam::123:role/R",
            },
        )
        provider.issue_credentials(facts, scope=[])
        call_kwargs = mock_sts.assume_role.call_args[1]
        assert call_kwargs["DurationSeconds"] == 1800

    def test_capabilities_attach_to_agent_facts(self):
        """Plan says capabilities map to attached managed policies. No
        automated mapping exists yet; this test documents the gap by
        pinning the AgentFacts-level contract."""
        facts = _make_facts(
            capabilities=[Capability(name="s3_read", description="Read S3")],
        )
        assert len(facts.capabilities) == 1
