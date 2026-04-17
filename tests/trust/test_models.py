"""L1 Deterministic: Tests for trust/models.py -- identity data models.

Schema validation (A1), defaults (A2), immutability, and property-based
roundtrip tests (Pattern 1).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from trust.models import (
    AgentFacts,
    AuditEntry,
    Capability,
    CloudBinding,
    Policy,
    VerificationReport,
)


# ── A1: Schema Validation ─────────────────────────────────────────────


class TestAgentFactsSchema:
    def test_valid(self):
        facts = AgentFacts(
            agent_id="agent-001",
            agent_name="WriterBot",
            owner="team-content",
            version="1.0.0",
        )
        assert facts.agent_id == "agent-001", (
            "AgentFacts.agent_id must round-trip from the constructor"
        )
        assert facts.agent_name == "WriterBot", (
            "AgentFacts.agent_name must round-trip from the constructor"
        )

    def test_rejects_missing_agent_id(self):
        with pytest.raises(ValidationError):
            AgentFacts(agent_name="Bot", owner="team", version="1.0.0")

    def test_rejects_missing_agent_name(self):
        with pytest.raises(ValidationError):
            AgentFacts(agent_id="a1", owner="team", version="1.0.0")

    def test_rejects_missing_owner(self):
        with pytest.raises(ValidationError):
            AgentFacts(agent_id="a1", agent_name="Bot", version="1.0.0")

    def test_rejects_missing_version(self):
        with pytest.raises(ValidationError):
            AgentFacts(agent_id="a1", agent_name="Bot", owner="team")

    def test_frozen(self):
        facts = AgentFacts(
            agent_id="a1", agent_name="Bot", owner="team", version="1.0.0"
        )
        with pytest.raises(ValidationError):
            facts.agent_id = "a2"


class TestCapability:
    def test_valid(self):
        cap = Capability(name="write", description="write articles")
        assert cap.name == "write", "Capability.name must round-trip from the constructor"

    def test_frozen(self):
        cap = Capability(name="write")
        with pytest.raises(ValidationError):
            cap.name = "read"

    def test_defaults(self):
        cap = Capability(name="write")
        assert cap.description == "", (
            "Capability.description must default to empty string"
        )
        assert cap.parameters == {}, (
            "Capability.parameters must default to an empty dict"
        )


class TestPolicy:
    def test_valid(self):
        pol = Policy(name="max_tokens", description="token limit")
        assert pol.name == "max_tokens", "Policy.name must round-trip from constructor"

    def test_frozen(self):
        pol = Policy(name="max_tokens")
        with pytest.raises(ValidationError):
            pol.name = "other"

    def test_defaults(self):
        pol = Policy(name="max_tokens")
        assert pol.description == "", "Policy.description must default to empty string"
        assert pol.rules == {}, "Policy.rules must default to an empty dict"


class TestAuditEntry:
    def test_valid(self):
        entry = AuditEntry(
            agent_id="agent-001",
            action="register",
            performed_by="admin",
        )
        assert entry.agent_id == "agent-001", (
            "AuditEntry.agent_id must round-trip from constructor"
        )
        assert entry.action == "register", (
            "AuditEntry.action must round-trip from constructor"
        )

    def test_frozen(self):
        entry = AuditEntry(
            agent_id="agent-001", action="register", performed_by="admin"
        )
        with pytest.raises(ValidationError):
            entry.action = "suspend"

    def test_auto_timestamp(self):
        entry = AuditEntry(
            agent_id="a1", action="test", performed_by="admin"
        )
        assert isinstance(entry.timestamp, datetime), (
            "AuditEntry.timestamp must be auto-populated with a datetime"
        )


class TestVerificationReport:
    def test_valid(self):
        report = VerificationReport(total=10, passed=8, failed=1, expired=1)
        assert report.total == 10, (
            "VerificationReport.total must round-trip from constructor"
        )

    def test_frozen(self):
        report = VerificationReport()
        with pytest.raises(ValidationError):
            report.total = 99

    def test_defaults(self):
        report = VerificationReport()
        assert report.total == 0, "VerificationReport.total must default to 0"
        assert report.passed == 0, "VerificationReport.passed must default to 0"
        assert report.failed == 0, "VerificationReport.failed must default to 0"
        assert report.expired == 0, "VerificationReport.expired must default to 0"
        assert report.failures == [], (
            "VerificationReport.failures must default to an empty list"
        )


class TestCloudBinding:
    def test_valid_providers(self):
        for provider in ("aws", "gcp", "azure", "local"):
            binding = CloudBinding(
                agent_id="a1", provider=provider
            )
            assert binding.provider == provider, (
                f"CloudBinding.provider must round-trip the constructor value '{provider}'"
            )

    def test_rejects_invalid_provider(self):
        with pytest.raises(ValidationError):
            CloudBinding(agent_id="a1", provider="oracle")

    def test_frozen(self):
        binding = CloudBinding(agent_id="a1", provider="local")
        with pytest.raises(ValidationError):
            binding.agent_id = "a2"


# ── A2: Defaults and Auto-fields ──────────────────────────────────────


class TestAgentFactsDefaults:
    def test_status_default(self):
        facts = AgentFacts(
            agent_id="a1", agent_name="Bot", owner="team", version="1.0.0"
        )
        assert facts.status == "active", (
            "AgentFacts.status must default to IdentityStatus.ACTIVE ('active')"
        )

    def test_timestamps_auto_set(self):
        facts = AgentFacts(
            agent_id="a1", agent_name="Bot", owner="team", version="1.0.0"
        )
        assert isinstance(facts.created_at, datetime), (
            "AgentFacts.created_at must be auto-populated with a datetime"
        )
        assert isinstance(facts.updated_at, datetime), (
            "AgentFacts.updated_at must be auto-populated with a datetime"
        )

    def test_optional_fields_default(self):
        facts = AgentFacts(
            agent_id="a1", agent_name="Bot", owner="team", version="1.0.0"
        )
        assert facts.capabilities == [], "capabilities must default to empty list"
        assert facts.policies == [], "policies must default to empty list"
        assert facts.signed_metadata == {}, "signed_metadata must default to empty dict"
        assert facts.metadata == {}, "metadata must default to empty dict"
        assert facts.valid_until is None, "valid_until must default to None"
        assert facts.parent_agent_id is None, "parent_agent_id must default to None"
        assert facts.signature_hash == "", "signature_hash must default to empty string"


# ── Property-Based: Roundtrip (Pattern 1) ─────────────────────────────


class TestRoundtrip:
    def test_agent_facts_roundtrip(self):
        facts = AgentFacts(
            agent_id="a1",
            agent_name="Bot",
            owner="team",
            version="1.0.0",
            capabilities=[Capability(name="write")],
            policies=[Policy(name="max_tokens")],
        )
        serialized = facts.model_dump_json()
        deserialized = AgentFacts.model_validate_json(serialized)
        assert deserialized.agent_id == facts.agent_id, (
            "agent_id must survive JSON serialization round-trip"
        )
        assert deserialized.agent_name == facts.agent_name, (
            "agent_name must survive JSON serialization round-trip"
        )
        assert len(deserialized.capabilities) == 1, (
            "capabilities list must preserve its single entry after JSON round-trip"
        )

    def test_capability_roundtrip(self):
        cap = Capability(name="write", description="writes articles", parameters={"max": 100})
        serialized = cap.model_dump_json()
        deserialized = Capability.model_validate_json(serialized)
        assert deserialized == cap, (
            "Capability instances must be equal after JSON round-trip"
        )
