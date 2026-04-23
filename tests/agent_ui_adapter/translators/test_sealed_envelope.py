"""US-4.4 — sealed-envelope round-trip helpers (plan §4.4).

Pattern 3: signature-roundtrip. After a signed trust type is shipped to
the frontend and echoed back, the signature must still verify. Owns the
real assertions for architecture test T6.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_ui_adapter.translators.sealed_envelope import (
    from_envelope,
    from_policy_envelope,
    from_trace_envelope,
    signable_dict,
    to_envelope,
    to_policy_envelope,
    to_trace_envelope,
)
from trust.enums import IdentityStatus
from trust.models import (
    AgentFacts,
    Capability,
    Policy,
    PolicyDecision,
    TrustTraceRecord,
)
from trust.signature import compute_signature, verify_signature


SECRET = "test-secret-S4"


def _signed_facts() -> AgentFacts:
    """Build a signed AgentFacts using the same protocol as the registry."""
    base = AgentFacts(
        agent_id="agent-001",
        agent_name="Researcher",
        owner="alice",
        version="1.0.0",
        description="signs and verifies",
        capabilities=[Capability(name="read", description="read fs")],
        policies=[Policy(name="no-net", description="no network")],
        signed_metadata={"region": "us-east-1"},
        status=IdentityStatus.ACTIVE,
    )
    base_dict = base.model_dump(mode="json")
    sig = compute_signature(signable_dict(base_dict), SECRET)
    base_dict["signature_hash"] = sig
    return AgentFacts.model_validate(base_dict)


# ── AgentFacts envelope ───────────────────────────────────────────────


def test_agent_facts_envelope_round_trip_preserves_signature() -> None:
    """T6: sign → to_envelope → JSON → from_envelope → verify_signature is True."""
    facts = _signed_facts()
    envelope = to_envelope(facts)

    wire = json.loads(json.dumps(envelope))
    rehydrated = from_envelope(wire)

    rehydrated_dict = rehydrated.model_dump(mode="json")
    assert verify_signature(
        signable_dict(rehydrated_dict),
        SECRET,
        rehydrated_dict["signature_hash"],
    )


def test_agent_facts_envelope_identity_round_trip() -> None:
    """from_envelope(to_envelope(x)) == x for AgentFacts."""
    facts = _signed_facts()
    assert from_envelope(to_envelope(facts)) == facts


def test_agent_facts_envelope_rejects_tamper() -> None:
    """Tamper detection: changing a signed field invalidates the signature."""
    facts = _signed_facts()
    envelope = to_envelope(facts)
    envelope["agent_name"] = "Tampered"
    assert not verify_signature(
        signable_dict(envelope),
        SECRET,
        envelope["signature_hash"],
    )


@pytest.mark.property
@given(seed=st.integers(min_value=0, max_value=10_000))
def test_agent_facts_envelope_survives_key_shuffle(seed: int) -> None:
    """Property: any key reordering still verifies (canonical sort is stable)."""
    import random

    facts = _signed_facts()
    envelope = to_envelope(facts)

    keys = list(envelope.keys())
    random.Random(seed).shuffle(keys)
    shuffled = {k: envelope[k] for k in keys}

    rehydrated = from_envelope(shuffled)
    rehydrated_dict = rehydrated.model_dump(mode="json")
    assert verify_signature(
        signable_dict(rehydrated_dict),
        SECRET,
        rehydrated_dict["signature_hash"],
    )


# ── TrustTraceRecord envelope ─────────────────────────────────────────


def test_trust_trace_record_round_trip() -> None:
    record = TrustTraceRecord(
        event_id="evt-1",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        trace_id="trace-1",
        agent_id="agent-001",
        layer="L4",
        event_type="run_started",
        details={"foo": "bar"},
        outcome="pass",
    )
    envelope = to_trace_envelope(record)
    wire = json.loads(json.dumps(envelope))
    assert from_trace_envelope(wire) == record


# ── PolicyDecision envelope ───────────────────────────────────────────


def test_policy_decision_round_trip() -> None:
    decision = PolicyDecision(
        enforcement="allow",
        reason="caller in allowlist",
        backend="embedded",
        audit_entry={"caller": "alice", "resource": "tool:grep"},
    )
    envelope = to_policy_envelope(decision)
    wire = json.loads(json.dumps(envelope))
    assert from_policy_envelope(wire) == decision
