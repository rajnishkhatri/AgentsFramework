"""L2 Contract: subject-coach-english AgentFacts instance (FR-1/FR-2).

ADR-0007 / agent spec §3.1: the coach is an identity-bound *instance* of the
existing pipeline — a new AgentFacts record, NOT a new trust/ type (no kernel
re-sign). These tests pin the declared contract (capabilities + policies) and
prove rejection before acceptance (failure paths first, TAP-6): a tampered
identity card must fail verification before the clean roundtrip passes.

Real in-memory/tmp-path registry, no mocks (TAP-2).
Test import rule: trust/ + services/ only.
"""

from __future__ import annotations

import json

import pytest

from services.governance.agent_facts_registry import AgentFactsRegistry
from services.governance.subject_coach_identity import (
    SUBJECT_COACH_AGENT_ID,
    SUBJECT_COACH_CAPABILITIES,
    SUBJECT_COACH_POLICIES,
    register_subject_coach,
    subject_coach_english_facts,
)


@pytest.fixture
def registry(tmp_path):
    return AgentFactsRegistry(
        storage_dir=tmp_path / "agent_facts",
        secret="test-secret",
    )


class TestTamperRejection:
    """FR-2 failure path FIRST: a tampered card must fail verification."""

    def test_tampered_policy_fails_verification(self, registry, tmp_path):
        register_subject_coach(registry, registered_by="test")
        # Tamper the stored card on disk: weaken the anti-leakage policy.
        path = tmp_path / "agent_facts" / f"{SUBJECT_COACH_AGENT_ID}.json"
        stored = json.loads(path.read_text())
        stored["policies"] = [
            p for p in stored["policies"] if p["name"] != "answer-leakage-prohibited"
        ]
        path.write_text(json.dumps(stored))

        assert registry.verify(SUBJECT_COACH_AGENT_ID) is False

    def test_tampered_capability_fails_verification(self, registry, tmp_path):
        register_subject_coach(registry, registered_by="test")
        # Tamper: grant the coach a shell capability it never declared.
        path = tmp_path / "agent_facts" / f"{SUBJECT_COACH_AGENT_ID}.json"
        stored = json.loads(path.read_text())
        stored["capabilities"].append(
            {"name": "shell", "description": "", "parameters": {}}
        )
        path.write_text(json.dumps(stored))

        assert registry.verify(SUBJECT_COACH_AGENT_ID) is False

    def test_unregistered_coach_fails_verification(self, registry):
        assert registry.verify(SUBJECT_COACH_AGENT_ID) is False


class TestRegisterVerifyRoundtrip:
    """FR-1 acceptance path: HMAC-signed registration verifies clean."""

    def test_register_then_verify(self, registry):
        registered = register_subject_coach(registry, registered_by="test")
        assert registered.signature_hash, "registration must HMAC-sign the card"
        assert registry.verify(SUBJECT_COACH_AGENT_ID) is True

    def test_register_is_idempotent(self, registry):
        first = register_subject_coach(registry, registered_by="test")
        second = register_subject_coach(registry, registered_by="test")
        assert second.agent_id == first.agent_id
        assert registry.verify(SUBJECT_COACH_AGENT_ID) is True


class TestIdempotencyIsNotMasking:
    """Review finding I1: 'already registered' is the ONLY silent path.

    The original helper caught bare ValueError and returned whatever card was
    stored — masking pydantic ValidationError (a ValueError subclass) and
    serving a stale/drifted contract as if freshly ratified.
    """

    def test_stale_stored_card_raises_instead_of_being_served(self, registry):
        # A legitimately-signed OLD card (weaker contract: no anti-leakage
        # policy, older version) is already on disk.
        stale = subject_coach_english_facts().model_copy(
            update={
                "version": "0.9.0",
                "policies": [
                    p
                    for p in subject_coach_english_facts().policies
                    if p.name != "answer-leakage-prohibited"
                ],
            }
        )
        registry.register(stale, registered_by="old-deploy")

        with pytest.raises(ValueError, match="drift"):
            register_subject_coach(registry, registered_by="test")

    def test_registration_failure_propagates_not_masked(self):
        # A registry whose register() raises a ValidationError-shaped error
        # (ValueError subclass) for a NOT-yet-registered agent: the old code
        # swallowed it and re-raised a confusing KeyError from get().
        class BrokenValidation(ValueError):
            pass

        class StubRegistry:
            def get(self, agent_id):
                raise KeyError(agent_id)

            def register(self, facts, registered_by):
                raise BrokenValidation("signed dict failed model_validate")

        with pytest.raises(BrokenValidation):
            register_subject_coach(StubRegistry(), registered_by="test")


class TestDeclaredContract:
    """FR-1: the declared contract is exactly what the ADRs ratified."""

    def test_agent_id(self):
        assert SUBJECT_COACH_AGENT_ID == "subject-coach-english"
        assert subject_coach_english_facts().agent_id == SUBJECT_COACH_AGENT_ID

    def test_capabilities_are_exactly_think_and_file_io(self):
        facts = subject_coach_english_facts()
        assert [c.name for c in facts.capabilities] == ["think", "file_io"]
        assert SUBJECT_COACH_CAPABILITIES == ["think", "file_io"]

    def test_policies_declare_the_four_ratified_constraints(self):
        facts = subject_coach_english_facts()
        assert [p.name for p in facts.policies] == list(SUBJECT_COACH_POLICIES)
        assert set(SUBJECT_COACH_POLICIES) == {
            "domain-english-teaching",
            "no-code-execution",
            "answer-leakage-prohibited",
            "coach-rate-limit",
        }

    def test_every_policy_names_its_enforcement_plane(self):
        """Declared = enforced: each policy rule names where it is enforced
        (runtime / guardrail / judge / trace) — no prose-only assertions."""
        facts = subject_coach_english_facts()
        for policy in facts.policies:
            assert policy.rules.get("enforced_by"), (
                f"policy '{policy.name}' must name its enforcement plane"
            )
