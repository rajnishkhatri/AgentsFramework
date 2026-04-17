"""L1 Deterministic: Tests for trust/exceptions.py -- exception hierarchy.

Failure paths first: every exception subclass must preserve base fields
and be catchable as TrustProviderError.
"""

from __future__ import annotations

import pytest

from trust.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    CredentialError,
    TrustProviderError,
)


class TestTrustProviderErrorBase:
    def test_stores_provider_and_operation(self):
        exc = TrustProviderError(
            "something broke",
            provider="aws",
            operation="get_caller_identity",
        )
        assert exc.provider == "aws"
        assert exc.operation == "get_caller_identity"
        assert str(exc) == "something broke"

    def test_stores_original_error(self):
        original = RuntimeError("boto3 exploded")
        exc = TrustProviderError(
            "wrapped",
            provider="aws",
            operation="resolve_identity",
            original_error=original,
        )
        assert exc.original_error is original

    def test_original_error_defaults_to_none(self):
        exc = TrustProviderError(
            "no original", provider="local", operation="test"
        )
        assert exc.original_error is None

    def test_repr_contains_provider_and_operation(self):
        exc = TrustProviderError(
            "msg", provider="aws", operation="op"
        )
        r = repr(exc)
        assert "aws" in r
        assert "op" in r
        assert "TrustProviderError" in r

    def test_is_exception(self):
        exc = TrustProviderError(
            "test", provider="local", operation="test"
        )
        assert isinstance(exc, Exception)


SUBCLASSES = [
    AuthenticationError,
    AuthorizationError,
    CredentialError,
    ConfigurationError,
]


class TestSubclassHierarchy:
    @pytest.mark.parametrize("cls", SUBCLASSES, ids=lambda c: c.__name__)
    def test_is_trust_provider_error(self, cls):
        exc = cls("test error", provider="aws", operation="test_op")
        assert isinstance(exc, TrustProviderError)

    @pytest.mark.parametrize("cls", SUBCLASSES, ids=lambda c: c.__name__)
    def test_preserves_base_fields(self, cls):
        original = ValueError("root cause")
        exc = cls(
            "error msg",
            provider="gcp",
            operation="some_op",
            original_error=original,
        )
        assert exc.provider == "gcp"
        assert exc.operation == "some_op"
        assert exc.original_error is original
        assert str(exc) == "error msg"

    @pytest.mark.parametrize("cls", SUBCLASSES, ids=lambda c: c.__name__)
    def test_catchable_as_base(self, cls):
        with pytest.raises(TrustProviderError):
            raise cls("catch me", provider="local", operation="test")

    def test_authentication_error_identity(self):
        assert issubclass(AuthenticationError, TrustProviderError)

    def test_authorization_error_identity(self):
        assert issubclass(AuthorizationError, TrustProviderError)

    def test_credential_error_identity(self):
        assert issubclass(CredentialError, TrustProviderError)

    def test_configuration_error_identity(self):
        assert issubclass(ConfigurationError, TrustProviderError)
