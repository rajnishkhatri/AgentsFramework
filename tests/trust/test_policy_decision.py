"""L1 Deterministic: Tests for trust.models.PolicyDecision.

Per AGENT_UI_ADAPTER_SPRINTS.md US-DP-1.1.
TDD Protocol A (Pure TDD), failure paths first per AGENTS.md TAP-4.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from trust.models import PolicyDecision


# ── Failure-path tests (TAP-4) ────────────────────────────────────────


class TestPolicyDecisionRejection:
    def test_rejects_invalid_enforcement(self):
        with pytest.raises(ValidationError):
            PolicyDecision(
                enforcement="maybe",  # Not allow/deny/require_approval/throttle
                reason="...",
                backend="embedded",
                audit_entry={},
            )

    def test_rejects_invalid_backend(self):
        with pytest.raises(ValidationError):
            PolicyDecision(
                enforcement="allow",
                reason="...",
                backend="custom-backend",  # Not embedded/opa/cedar/yaml
                audit_entry={},
            )

    def test_rejects_missing_reason(self):
        with pytest.raises(ValidationError):
            PolicyDecision(
                enforcement="deny",
                backend="embedded",
                audit_entry={},
            )

    def test_rejects_missing_audit_entry(self):
        with pytest.raises(ValidationError):
            PolicyDecision(
                enforcement="allow",
                reason="...",
                backend="embedded",
            )


# ── Acceptance tests ──────────────────────────────────────────────────


class TestPolicyDecisionSchema:
    def test_allow_decision(self):
        d = PolicyDecision(
            enforcement="allow",
            reason="capability matched",
            backend="embedded",
            audit_entry={"matched_capability": "read"},
        )
        assert d.enforcement == "allow"
        assert d.allowed is True

    def test_deny_decision(self):
        d = PolicyDecision(
            enforcement="deny",
            reason="missing capability",
            backend="embedded",
            audit_entry={"required": "write"},
        )
        assert d.allowed is False

    def test_require_approval_is_not_allowed(self):
        d = PolicyDecision(
            enforcement="require_approval",
            reason="HITL gate",
            backend="embedded",
            audit_entry={},
        )
        assert d.allowed is False, (
            "require_approval is NOT allowed; only enforcement='allow' returns True"
        )

    def test_throttle_is_not_allowed(self):
        d = PolicyDecision(
            enforcement="throttle",
            reason="rate limit",
            backend="embedded",
            audit_entry={"limit": 10},
        )
        assert d.allowed is False

    @pytest.mark.parametrize("backend", ["embedded", "opa", "cedar", "yaml"])
    def test_all_backends_accepted(self, backend):
        d = PolicyDecision(
            enforcement="allow",
            reason="...",
            backend=backend,
            audit_entry={},
        )
        assert d.backend == backend


# ── Round-trip ────────────────────────────────────────────────────────


class TestPolicyDecisionRoundTrip:
    def test_json_round_trip(self):
        original = PolicyDecision(
            enforcement="deny",
            reason="suspended identity",
            backend="embedded",
            audit_entry={"checked_at": "2025-01-01T00:00:00Z", "policy": "default"},
        )
        rehydrated = PolicyDecision.model_validate_json(original.model_dump_json())
        assert rehydrated == original
