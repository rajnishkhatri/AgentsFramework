"""L2 Reproducible: Tests for utils/cloud_providers/__init__.py -- provider factory.

Contract tests for get_provider() including failure path for unknown providers.
"""

from __future__ import annotations

import pytest

from trust.exceptions import ConfigurationError
from trust.protocols import CredentialProvider, IdentityProvider, PolicyProvider
from utils.cloud_providers import get_provider
from utils.cloud_providers.config import TrustProviderSettings
from utils.cloud_providers.local_provider import (
    LocalCredentialProvider,
    LocalIdentityProvider,
    LocalPolicyProvider,
)


class TestGetProviderLocal:
    def test_returns_local_by_default(self):
        settings = TrustProviderSettings(
            _env_file=None,  # type: ignore[call-arg]
        )
        identity, policy, credential = get_provider(settings)
        assert isinstance(identity, LocalIdentityProvider)
        assert isinstance(policy, LocalPolicyProvider)
        assert isinstance(credential, LocalCredentialProvider)

    def test_local_returns_correct_protocol_types(self):
        settings = TrustProviderSettings(
            provider="local", _env_file=None,  # type: ignore[call-arg]
        )
        identity, policy, credential = get_provider(settings)
        assert isinstance(identity, IdentityProvider)
        assert isinstance(policy, PolicyProvider)
        assert isinstance(credential, CredentialProvider)

    def test_accepts_settings_override(self):
        settings = TrustProviderSettings(
            provider="local", region="eu-west-1",
            _env_file=None,  # type: ignore[call-arg]
        )
        identity, policy, credential = get_provider(settings)
        assert isinstance(identity, LocalIdentityProvider)


class TestGetProviderAWS:
    def test_aws_returns_correct_protocol_types(self):
        settings = TrustProviderSettings(
            provider="aws", _env_file=None,  # type: ignore[call-arg]
        )
        identity, policy, credential = get_provider(settings)
        assert isinstance(identity, IdentityProvider)
        assert isinstance(policy, PolicyProvider)
        assert isinstance(credential, CredentialProvider)


class TestGetProviderFailure:
    def test_unknown_raises_configuration_error(self):
        settings = TrustProviderSettings.__new__(TrustProviderSettings)
        object.__setattr__(settings, "provider", "oracle")
        with pytest.raises(ConfigurationError) as exc_info:
            get_provider(settings)
        assert "oracle" in str(exc_info.value)
        assert exc_info.value.operation == "get_provider"
