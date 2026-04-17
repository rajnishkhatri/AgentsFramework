"""Provider configuration loaded from environment variables.

All settings are prefixed with ``TRUST_`` so they coexist cleanly with
other env-based configuration.
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class TrustProviderSettings(BaseSettings):
    """Configuration for the active cloud trust provider."""

    provider: Literal["aws", "local"] = "local"
    region: str = "us-east-1"
    sts_endpoint: str | None = None
    iam_endpoint: str | None = None
    retry_max_attempts: int = 3
    credential_source: Literal["environment", "profile", "instance"] = "environment"

    model_config = SettingsConfigDict(env_prefix="TRUST_")
