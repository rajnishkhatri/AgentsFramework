"""Sealed-envelope helpers for signed trust types (plan §4.4).

The frontend can echo a signed payload back to the server (HITL approvals,
trust-trace forwarding). When that round-trip happens, JSON serialization
may reorder dict keys -- but ``trust.signature.compute_signature`` already
canonicalizes via ``json.dumps(..., sort_keys=True)``, so verification
remains valid as long as we use ``model_dump(mode="json")`` for outbound
serialization and ``model_validate(envelope)`` for inbound rehydration.

These helpers are pure: no I/O, no logging, no service imports. Only
``trust.*`` is consulted (per rule R7 translators may import trust).
"""

from __future__ import annotations

from trust.models import AgentFacts, PolicyDecision, TrustTraceRecord


def to_envelope(facts: AgentFacts) -> dict:
    """Serialize ``AgentFacts`` to a JSON-safe dict that round-trips."""
    return facts.model_dump(mode="json")


def from_envelope(envelope: dict) -> AgentFacts:
    """Inverse of ``to_envelope``: rehydrate ``AgentFacts`` from a dict."""
    return AgentFacts.model_validate(envelope)


def to_trace_envelope(record: TrustTraceRecord) -> dict:
    """Serialize ``TrustTraceRecord`` to a JSON-safe dict."""
    return record.model_dump(mode="json")


def from_trace_envelope(envelope: dict) -> TrustTraceRecord:
    """Inverse of ``to_trace_envelope``."""
    return TrustTraceRecord.model_validate(envelope)


def to_policy_envelope(decision: PolicyDecision) -> dict:
    """Serialize ``PolicyDecision`` to a JSON-safe dict."""
    return decision.model_dump(mode="json")


def from_policy_envelope(envelope: dict) -> PolicyDecision:
    """Inverse of ``to_policy_envelope``."""
    return PolicyDecision.model_validate(envelope)


def signable_dict(envelope: dict) -> dict:
    """Strip the ``signature_hash`` field for signature verification.

    Mirrors ``AgentFactsRegistry._signable_dict`` but lives in the
    translator layer so consumers don't have to import a service.
    """
    d = dict(envelope)
    d.pop("signature_hash", None)
    return d


__all__ = [
    "from_envelope",
    "from_policy_envelope",
    "from_trace_envelope",
    "signable_dict",
    "to_envelope",
    "to_policy_envelope",
    "to_trace_envelope",
]
