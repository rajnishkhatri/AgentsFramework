"""Trust Foundation -- shared kernel types for the four-layer grid.

Re-exports all public types so consumers can write::

    from trust import AgentFacts, IdentityProvider, IdentityContext
"""

from trust.cloud_identity import (
    AccessDecision,
    IdentityContext,
    PermissionBoundary,
    PolicyBinding,
    TemporaryCredentials,
    VerificationResult,
)
from trust.enums import IdentityStatus
from trust.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    CredentialError,
    TrustProviderError,
)
from trust.models import (
    AgentFacts,
    AuditEntry,
    Capability,
    CloudBinding,
    Policy,
    PolicyDecision,
    TraceLayer,
    TraceOutcome,
    TrustTraceRecord,
    VerificationReport,
)
from trust.protocols import CredentialProvider, IdentityProvider, PolicyProvider
from trust.review_schema import (
    Certificate,
    DimensionResult,
    DimensionStatus,
    ReviewFinding,
    ReviewReport,
    Severity,
    Verdict,
)
from trust.signature import compute_signature, verify_signature

__all__ = [
    # models
    "AgentFacts",
    "AuditEntry",
    "Capability",
    "CloudBinding",
    "Policy",
    "PolicyDecision",
    "TraceLayer",
    "TraceOutcome",
    "TrustTraceRecord",
    "VerificationReport",
    # cloud identity value objects
    "AccessDecision",
    "IdentityContext",
    "PermissionBoundary",
    "PolicyBinding",
    "TemporaryCredentials",
    "VerificationResult",
    # enums
    "IdentityStatus",
    # protocols
    "CredentialProvider",
    "IdentityProvider",
    "PolicyProvider",
    # review schema
    "Certificate",
    "DimensionResult",
    "DimensionStatus",
    "ReviewFinding",
    "ReviewReport",
    "Severity",
    "Verdict",
    # exceptions
    "AuthenticationError",
    "AuthorizationError",
    "ConfigurationError",
    "CredentialError",
    "TrustProviderError",
    # signature
    "compute_signature",
    "verify_signature",
]
