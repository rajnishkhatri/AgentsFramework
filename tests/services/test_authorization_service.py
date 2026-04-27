"""L2 Reproducible: Tests for services/authorization_service.py.

Contract-driven TDD per Protocol B + B2 + Pattern 11 (Failure Mode Matrix).
Failure paths first (TAP-4) — rows 2..7 of the decision matrix precede the
acceptance rows.

Spec: docs/plan/services/AUTHORIZATION_SERVICE_PLAN.md.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from trust.enums import IdentityStatus
from trust.models import (
    AgentFacts,
    Capability,
    Policy,
    PolicyDecision,
    TrustTraceRecord,
)


def _make_facts(
    *,
    capabilities: list[Capability] | None = None,
    policies: list[Policy] | None = None,
    status: IdentityStatus = IdentityStatus.ACTIVE,
    valid_until: datetime | None = None,
) -> AgentFacts:
    return AgentFacts(
        agent_id="agent-A",
        agent_name="TestBot",
        owner="team-test",
        version="1.0.0",
        capabilities=capabilities or [],
        policies=policies or [],
        status=status,
        valid_until=valid_until,
    )


def _cap(name: str) -> Capability:
    return Capability(name=name)


def _policy(action: str, enforcement: str, name: str | None = None) -> Policy:
    return Policy(
        name=name or f"policy-{enforcement}-{action}",
        rules={"action": action, "enforcement": enforcement},
    )


class _StubBackend:
    """Stub `PolicyBackend` returning a fixed `PolicyDecision`."""

    def __init__(self, decision: PolicyDecision) -> None:
        self._decision = decision

    def evaluate(
        self, facts: AgentFacts, action: str, context: dict
    ) -> PolicyDecision:
        return self._decision


def _decision(enforcement: str, *, backend: str = "embedded", reason: str = "stub") -> PolicyDecision:
    return PolicyDecision(
        enforcement=enforcement,
        reason=reason,
        backend=backend,  # type: ignore[arg-type]
        audit_entry={},
    )


# ─────────────────────────────────────────────────────────────────────
# §3 + §4.1 Decision matrix — failure rows FIRST (rows 2-7)
# ─────────────────────────────────────────────────────────────────────


class TestAuthorizationDecisionMatrixFailures:
    """Rows 2-7: every embedded deny scenario."""

    def test_row_2_expired_identity_denied(self):
        """Row 2 of the decision matrix: expired identity (valid_until < now).

        Note: the sub-plan §6 suggests `@freeze_time(...)`, but freezegun
        triggers a lazy-import of keras → pandas → pyarrow when the broader
        suite has already loaded keras transitively. Loading pyarrow into
        the freezegun-patched runtime segfaults the interpreter on this
        platform. A static past `valid_until` exercises the same code path
        deterministically without monkey-patching the global datetime.
        Documented as a S1 deviation in the sub-agent report.
        """
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        facts = _make_facts(
            capabilities=[_cap("read")],
            valid_until=datetime(2000, 1, 1, tzinfo=UTC),
        )
        service = AuthorizationService(embedded_backend=EmbeddedPolicyBackend())
        decision = service.authorize(facts, "read", {})
        assert decision.enforcement == "deny"
        assert "expired" in decision.reason.lower()

    def test_row_3_suspended_identity_denied(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        facts = _make_facts(
            capabilities=[_cap("read")],
            status=IdentityStatus.SUSPENDED,
        )
        service = AuthorizationService(embedded_backend=EmbeddedPolicyBackend())
        decision = service.authorize(facts, "read", {})
        assert decision.enforcement == "deny"
        assert "suspended" in decision.reason.lower()

    def test_row_4_revoked_identity_denied(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        facts = _make_facts(
            capabilities=[_cap("read")],
            status=IdentityStatus.REVOKED,
        )
        service = AuthorizationService(embedded_backend=EmbeddedPolicyBackend())
        decision = service.authorize(facts, "read", {})
        assert decision.enforcement == "deny"
        assert "revoked" in decision.reason.lower()

    def test_row_5_missing_capability_denied(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        facts = _make_facts(capabilities=[_cap("read")])
        service = AuthorizationService(embedded_backend=EmbeddedPolicyBackend())
        decision = service.authorize(facts, "delete", {})
        assert decision.enforcement == "deny"
        assert "capability" in decision.reason.lower()

    def test_row_6_embedded_deny_overrides_external_allow(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        facts = _make_facts(
            capabilities=[_cap("delete")],
            policies=[_policy("delete", "deny")],
        )
        external = _StubBackend(_decision("allow", backend="yaml"))
        service = AuthorizationService(
            embedded_backend=EmbeddedPolicyBackend(),
            external_backend=external,
        )
        decision = service.authorize(facts, "delete", {})
        assert decision.enforcement == "deny"

    def test_row_7_external_deny_overrides_embedded_allow(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        facts = _make_facts(capabilities=[_cap("read")])
        external = _StubBackend(_decision("deny", backend="yaml", reason="external no"))
        service = AuthorizationService(
            embedded_backend=EmbeddedPolicyBackend(),
            external_backend=external,
        )
        decision = service.authorize(facts, "read", {})
        assert decision.enforcement == "deny"


# ─────────────────────────────────────────────────────────────────────
# Acceptance rows (1, 8, 9, 10)
# ─────────────────────────────────────────────────────────────────────


class TestAuthorizationDecisionMatrixAcceptance:
    def test_row_1_active_matching_capability_no_policies_allows(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        facts = _make_facts(
            capabilities=[_cap("read")],
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )
        service = AuthorizationService(embedded_backend=EmbeddedPolicyBackend())
        decision = service.authorize(facts, "read", {})
        assert decision.enforcement == "allow"

    def test_row_8_embedded_allow_external_allow(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        facts = _make_facts(capabilities=[_cap("read")])
        external = _StubBackend(_decision("allow", backend="yaml"))
        service = AuthorizationService(
            embedded_backend=EmbeddedPolicyBackend(),
            external_backend=external,
        )
        decision = service.authorize(facts, "read", {})
        assert decision.enforcement == "allow"

    def test_row_9_embedded_require_approval(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        facts = _make_facts(
            capabilities=[_cap("publish")],
            policies=[_policy("publish", "require_approval")],
        )
        service = AuthorizationService(embedded_backend=EmbeddedPolicyBackend())
        decision = service.authorize(facts, "publish", {})
        assert decision.enforcement == "require_approval"

    def test_row_10_embedded_throttle(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        facts = _make_facts(
            capabilities=[_cap("query")],
            policies=[_policy("query", "throttle")],
        )
        service = AuthorizationService(embedded_backend=EmbeddedPolicyBackend())
        decision = service.authorize(facts, "query", {})
        assert decision.enforcement == "throttle"


# ─────────────────────────────────────────────────────────────────────
# §4.2 Trace emission tests
# ─────────────────────────────────────────────────────────────────────


class _TraceCollector:
    def __init__(self) -> None:
        self.records: list[TrustTraceRecord] = []

    def __call__(self, record: TrustTraceRecord) -> None:
        self.records.append(record)


class TestAuthorizationTraceEmission:
    def test_authorize_emits_trace_on_allow(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        facts = _make_facts(capabilities=[_cap("read")])
        collector = _TraceCollector()
        service = AuthorizationService(
            embedded_backend=EmbeddedPolicyBackend(),
            trace_emit=collector,
        )
        service.authorize(facts, "read", {}, trace_id="tid-allow")
        assert len(collector.records) == 1
        rec = collector.records[0]
        assert rec.outcome == "pass"
        assert rec.event_type == "access_granted"
        assert rec.trace_id == "tid-allow"

    def test_authorize_emits_trace_on_deny(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        facts = _make_facts(capabilities=[_cap("read")])
        collector = _TraceCollector()
        service = AuthorizationService(
            embedded_backend=EmbeddedPolicyBackend(),
            trace_emit=collector,
        )
        service.authorize(facts, "delete", {}, trace_id="tid-deny")
        assert len(collector.records) == 1
        rec = collector.records[0]
        assert rec.outcome == "fail"
        assert rec.event_type == "access_denied"
        assert rec.trace_id == "tid-deny"

    def test_authorize_generates_trace_id_when_not_supplied(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        facts = _make_facts(capabilities=[_cap("read")])
        collector = _TraceCollector()
        service = AuthorizationService(
            embedded_backend=EmbeddedPolicyBackend(),
            trace_emit=collector,
        )
        service.authorize(facts, "read", {})
        assert len(collector.records) == 1
        assert collector.records[0].trace_id  # non-empty auto-generated

    def test_authorize_works_without_trace_emit(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        facts = _make_facts(capabilities=[_cap("read")])
        service = AuthorizationService(
            embedded_backend=EmbeddedPolicyBackend(),
            trace_emit=None,
        )
        decision = service.authorize(facts, "read", {})
        assert decision.enforcement == "allow"


# ─────────────────────────────────────────────────────────────────────
# §4.3 Boundary tests
# ─────────────────────────────────────────────────────────────────────


class _ExplodingRegistry:
    """Mock AgentFactsRegistry. authorize() must NEVER touch it."""

    def get(self, agent_id: str) -> AgentFacts:
        raise AssertionError("authorization_service must not call the registry")

    def verify(self, agent_id: str) -> bool:
        raise AssertionError("authorization_service must not call the registry")


class TestAuthorizationBoundaries:
    def test_authorize_rejects_none_facts(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        service = AuthorizationService(embedded_backend=EmbeddedPolicyBackend())
        with pytest.raises(TypeError):
            service.authorize(None, "read", {})  # type: ignore[arg-type]

    def test_authorize_rejects_empty_action(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        service = AuthorizationService(embedded_backend=EmbeddedPolicyBackend())
        with pytest.raises(ValueError):
            service.authorize(_make_facts(), "", {})

    def test_authorize_does_not_call_registry(self):
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        registry = _ExplodingRegistry()  # noqa: F841 — never passed in
        facts = _make_facts(capabilities=[_cap("read")])
        service = AuthorizationService(embedded_backend=EmbeddedPolicyBackend())
        decision = service.authorize(facts, "read", {})
        assert decision.enforcement == "allow"


# ─────────────────────────────────────────────────────────────────────
# §4.5 Property-based test
# ─────────────────────────────────────────────────────────────────────


_ENFORCEMENTS = ["allow", "deny", "require_approval", "throttle"]


@pytest.mark.property
class TestEmbeddedDenyAlwaysWinsProperty:
    @settings(max_examples=25, deadline=None)
    @given(
        external_enforcement=st.sampled_from(_ENFORCEMENTS),
    )
    def test_embedded_deny_always_wins(self, external_enforcement):
        from services.authorization_service import AuthorizationService

        facts = _make_facts(capabilities=[_cap("delete")])
        embedded = _StubBackend(_decision("deny", reason="hard no"))
        external = _StubBackend(
            _decision(external_enforcement, backend="yaml")
        )
        service = AuthorizationService(
            embedded_backend=embedded,
            external_backend=external,
        )
        decision = service.authorize(facts, "delete", {})
        assert decision.enforcement == "deny"
