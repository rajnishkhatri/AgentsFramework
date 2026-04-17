"""Cloud provider factory.

Usage::

    from utils.cloud_providers import get_provider

    identity, policy, credentials = get_provider()
"""

from __future__ import annotations

from trust.exceptions import ConfigurationError
from trust.protocols import CredentialProvider, IdentityProvider, PolicyProvider
from utils.cloud_providers.config import TrustProviderSettings


def get_provider(
    settings: TrustProviderSettings | None = None,
) -> tuple[IdentityProvider, PolicyProvider, CredentialProvider]:
    """Return the (IdentityProvider, PolicyProvider, CredentialProvider) trio
    for the configured cloud provider.
    """
    settings = settings or TrustProviderSettings()

    if settings.provider == "aws":
        from utils.cloud_providers.aws_credentials import AWSCredentialProvider
        from utils.cloud_providers.aws_identity import AWSIdentityProvider
        from utils.cloud_providers.aws_policy import AWSPolicyProvider

        return (
            AWSIdentityProvider(settings),
            AWSPolicyProvider(settings),
            AWSCredentialProvider(settings),
        )

    if settings.provider == "local":
        from utils.cloud_providers.local_provider import (
            LocalCredentialProvider,
            LocalIdentityProvider,
            LocalPolicyProvider,
        )

        return (
            LocalIdentityProvider(),
            LocalPolicyProvider(),
            LocalCredentialProvider(),
        )

    raise ConfigurationError(
        f"Unknown trust provider: {settings.provider!r}. "
        "Supported values: 'aws', 'local'.",
        provider=settings.provider,
        operation="get_provider",
    )
