"""L1 Deterministic: Tests for trust/__init__.py -- re-exports.

Verifies that all public types are importable from the top-level
``trust`` package and listed in ``__all__``.

Uses a self-maintaining round-trip strategy: iterate ``trust.__all__``
and verify each symbol resolves, then assert that each expected family
of symbols is fully represented. This catches drift in ``__all__`` as
well as broken module-level imports.
"""

from __future__ import annotations

import trust


# Expected symbol families. When a new module/type is added to the trust
# package, extend the matching family below rather than maintaining a
# flat literal list.
EXPECTED_FAMILIES = {
    "models": {
        "AgentFacts",
        "AuditEntry",
        "Capability",
        "CloudBinding",
        "Policy",
        "VerificationReport",
    },
    "cloud_identity": {
        "AccessDecision",
        "IdentityContext",
        "PermissionBoundary",
        "PolicyBinding",
        "TemporaryCredentials",
        "VerificationResult",
    },
    "protocols": {
        "CredentialProvider",
        "IdentityProvider",
        "PolicyProvider",
    },
    "exceptions": {
        "AuthenticationError",
        "AuthorizationError",
        "ConfigurationError",
        "CredentialError",
        "TrustProviderError",
    },
    "enums": {"IdentityStatus"},
    "review_schema": {
        "Certificate",
        "DimensionResult",
        "DimensionStatus",
        "ReviewFinding",
        "ReviewReport",
        "Severity",
        "Verdict",
    },
    "signature": {"compute_signature", "verify_signature"},
}


class TestDunderAllRoundTrip:
    """Verify __all__ is consistent with module-level accessibility."""

    def test_trust_has_dunder_all(self):
        assert hasattr(trust, "__all__"), "trust package must define __all__"

    def test_all_symbols_in_dunder_all_are_accessible(self):
        """Every name in __all__ must resolve on the trust module."""
        missing = [name for name in trust.__all__ if not hasattr(trust, name)]
        assert missing == [], (
            f"Names listed in trust.__all__ but not accessible on trust: {missing}"
        )

    def test_dunder_all_has_no_duplicates(self):
        names = list(trust.__all__)
        assert len(names) == len(set(names)), (
            f"trust.__all__ contains duplicates: {names}"
        )


class TestExpectedFamilies:
    """Verify __all__ fully covers each expected family of symbols."""

    def test_all_families_present(self):
        all_set = set(trust.__all__)
        for family, names in EXPECTED_FAMILIES.items():
            missing = names - all_set
            assert not missing, (
                f"Family '{family}' is missing from trust.__all__: {missing}"
            )

    def test_all_family_symbols_are_truthy(self):
        """Each symbol should be importable and not None."""
        for family, names in EXPECTED_FAMILIES.items():
            for name in names:
                obj = getattr(trust, name, None)
                assert obj is not None, (
                    f"trust.{name} (family '{family}') resolved to None"
                )


class TestDirectImports:
    """Smoke test that classic from-imports still work."""

    def test_can_import_models_from_trust(self):
        from trust import AgentFacts, Capability, Policy

        assert AgentFacts is not None
        assert Capability is not None
        assert Policy is not None

    def test_can_import_protocols_from_trust(self):
        from trust import CredentialProvider, IdentityProvider, PolicyProvider

        assert IdentityProvider is not None
        assert PolicyProvider is not None
        assert CredentialProvider is not None

    def test_can_import_cloud_identity_from_trust(self):
        from trust import AccessDecision, IdentityContext, TemporaryCredentials

        assert IdentityContext is not None
        assert AccessDecision is not None
        assert TemporaryCredentials is not None

    def test_can_import_exceptions_from_trust(self):
        from trust import AuthenticationError, TrustProviderError

        assert TrustProviderError is not None
        assert AuthenticationError is not None
