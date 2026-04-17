"""L2 Reproducible: Tests for utils/cloud_providers/config.py -- provider settings.

Contract tests for TrustProviderSettings with env var injection.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from utils.cloud_providers.config import TrustProviderSettings


class TestDefaults:
    def test_default_provider_is_local(self):
        settings = TrustProviderSettings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.provider == "local"

    def test_default_region_is_us_east_1(self):
        settings = TrustProviderSettings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.region == "us-east-1"

    def test_retry_max_attempts_default(self):
        settings = TrustProviderSettings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.retry_max_attempts == 3

    def test_credential_source_default(self):
        settings = TrustProviderSettings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.credential_source == "environment"

    def test_sts_endpoint_default_none(self):
        settings = TrustProviderSettings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.sts_endpoint is None

    def test_iam_endpoint_default_none(self):
        settings = TrustProviderSettings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.iam_endpoint is None


class TestValidation:
    def test_provider_accepts_aws(self):
        settings = TrustProviderSettings(
            provider="aws", _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.provider == "aws"

    def test_provider_accepts_local(self):
        settings = TrustProviderSettings(
            provider="local", _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.provider == "local"

    def test_provider_literal_rejects_invalid(self):
        with pytest.raises(ValidationError):
            TrustProviderSettings(
                provider="azure", _env_file=None,  # type: ignore[call-arg]
            )


class TestEnvVars:
    def test_settings_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("TRUST_PROVIDER", "aws")
        monkeypatch.setenv("TRUST_REGION", "eu-west-1")
        settings = TrustProviderSettings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.provider == "aws"
        assert settings.region == "eu-west-1"

    def test_retry_from_env(self, monkeypatch):
        monkeypatch.setenv("TRUST_RETRY_MAX_ATTEMPTS", "5")
        settings = TrustProviderSettings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.retry_max_attempts == 5
