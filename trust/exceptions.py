"""Cloud-agnostic exception hierarchy for trust provider operations.

TrustProviderError is the base; subclasses partition errors by domain
(authentication, authorization, credential, configuration) so that
consumers can catch cloud-agnostic categories without importing
provider-specific SDK exceptions.
"""

from __future__ import annotations


class TrustProviderError(Exception):
    """Base for all cloud provider errors."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        operation: str,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.operation = operation
        self.original_error = original_error

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"provider={self.provider!r}, "
            f"operation={self.operation!r}, "
            f"message={str(self)!r})"
        )


class AuthenticationError(TrustProviderError):
    """Identity resolution or verification failed."""


class AuthorizationError(TrustProviderError):
    """Policy evaluation or access decision failed."""


class CredentialError(TrustProviderError):
    """Credential issuance, refresh, or revocation failed."""


class ConfigurationError(TrustProviderError):
    """Provider misconfigured or unavailable."""
