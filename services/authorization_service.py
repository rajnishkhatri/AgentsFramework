"""AuthorizationService: in-graph runtime trust gate.

Spec: docs/plan/services/AUTHORIZATION_SERVICE_PLAN.md.

Horizontal service per AGENTS.md AP-2: receives `AgentFacts` as a
parameter (never fetches identity), receives a `trace_emit` callable as a
parameter (never imports the trace service), and never imports
`AgentFactsRegistry`.

Decision precedence (docs/FOUR_LAYER_ARCHITECTURE.md):
    1. Embedded backend evaluates first.
    2. Embedded `deny` short-circuits and is returned.
    3. If an external backend is configured, it is consulted next.
    4. Any `deny` denies; otherwise the embedded decision is returned
       so its `allow`/`require_approval`/`throttle` semantics survive.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Callable, Protocol, runtime_checkable

from trust.enums import IdentityStatus
from trust.models import (
    AgentFacts,
    Policy,
    PolicyDecision,
    TrustTraceRecord,
)

logger = logging.getLogger("services.authorization")


class AuthorizationError(Exception):
    """Typed exception base for authorization-service-level failures."""


@runtime_checkable
class PolicyBackend(Protocol):
    """External policy backend Protocol.

    Implementations: `EmbeddedPolicyBackend` (v1), `OpaPolicyBackend`
    (v1.5), `CedarPolicyBackend` (v1.5).
    """

    def evaluate(
        self,
        facts: AgentFacts,
        action: str,
        context: dict,
    ) -> PolicyDecision: ...


def _decision(
    enforcement: str,
    *,
    reason: str,
    backend: str = "embedded",
    audit_entry: dict[str, Any] | None = None,
) -> PolicyDecision:
    return PolicyDecision(
        enforcement=enforcement,  # type: ignore[arg-type]
        reason=reason,
        backend=backend,  # type: ignore[arg-type]
        audit_entry=audit_entry or {},
    )


class EmbeddedPolicyBackend:
    """Evaluates `facts.status`, `facts.valid_until`, `facts.capabilities`,
    and `facts.policies` directly. Pure function; no I/O.

    Policy rule format (v1; per Q-A5 exact match only):

        Policy(name=..., rules={"action": <action>, "enforcement": <enforce>})

    where `<enforce>` is one of `allow`, `deny`, `require_approval`,
    `throttle`. A policy with no `action` key applies to every action.
    """

    def evaluate(
        self,
        facts: AgentFacts,
        action: str,
        context: dict,
    ) -> PolicyDecision:
        if facts.status == IdentityStatus.SUSPENDED:
            return _decision(
                "deny",
                reason="suspended identity",
                audit_entry={"check": "status", "status": facts.status.value},
            )
        if facts.status == IdentityStatus.REVOKED:
            return _decision(
                "deny",
                reason="revoked identity",
                audit_entry={"check": "status", "status": facts.status.value},
            )

        if facts.valid_until is not None:
            now = datetime.now(UTC)
            if facts.valid_until < now:
                return _decision(
                    "deny",
                    reason="expired identity",
                    audit_entry={
                        "check": "valid_until",
                        "valid_until": facts.valid_until.isoformat(),
                    },
                )

        if not any(cap.name == action for cap in facts.capabilities):
            return _decision(
                "deny",
                reason="missing capability",
                audit_entry={"check": "capability", "action": action},
            )

        for policy in facts.policies:
            verdict = _policy_verdict(policy, action)
            if verdict is not None:
                return _decision(
                    verdict,
                    reason=f"policy '{policy.name}' returned {verdict}",
                    audit_entry={
                        "check": "policy",
                        "policy": policy.name,
                        "enforcement": verdict,
                    },
                )

        return _decision(
            "allow",
            reason="all embedded checks passed",
            audit_entry={"check": "embedded_default"},
        )


def _policy_verdict(policy: Policy, action: str) -> str | None:
    """Return the policy's enforcement for `action`, or None if it doesn't apply."""
    rules = policy.rules or {}
    enforcement = rules.get("enforcement")
    if enforcement not in {"allow", "deny", "require_approval", "throttle"}:
        return None
    if "action" in rules and rules["action"] != action:
        return None
    if "actions" in rules:
        actions = rules["actions"]
        if isinstance(actions, (list, tuple, set)) and action not in actions:
            return None
    return enforcement


class AuthorizationService:
    def __init__(
        self,
        embedded_backend: PolicyBackend,
        external_backend: PolicyBackend | None = None,
        trace_emit: Callable[[TrustTraceRecord], None] | None = None,
    ) -> None:
        self._embedded = embedded_backend
        self._external = external_backend
        self._trace_emit = trace_emit

    def authorize(
        self,
        facts: AgentFacts,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        if not isinstance(facts, AgentFacts):
            raise TypeError(
                f"authorize() requires an AgentFacts instance, "
                f"got {type(facts).__name__}"
            )
        if not isinstance(action, str):
            raise TypeError(
                f"action must be a string, got {type(action).__name__}"
            )
        if not action:
            raise ValueError("action must not be empty")
        ctx: dict[str, Any] = dict(context or {})

        embedded = self._embedded.evaluate(facts, action, ctx)

        final: PolicyDecision
        if embedded.enforcement == "deny":
            final = embedded
        elif self._external is not None:
            external = self._external.evaluate(facts, action, ctx)
            if external.enforcement == "deny":
                final = external
            else:
                final = embedded
        else:
            final = embedded

        self._log_decision(facts, action, ctx, final)
        self._emit_trace(facts, action, final)
        return final

    def _log_decision(
        self,
        facts: AgentFacts,
        action: str,
        context: dict[str, Any],
        decision: PolicyDecision,
    ) -> None:
        # Sensitive-data invariant (plan §5): log context KEYS only.
        logger.info(
            "authorize action=%s agent_id=%s outcome=%s reason=%s context_keys=%s",
            action,
            facts.agent_id,
            decision.enforcement,
            decision.reason,
            sorted(context.keys()),
        )

    def _emit_trace(
        self,
        facts: AgentFacts,
        action: str,
        decision: PolicyDecision,
    ) -> None:
        if self._trace_emit is None:
            return
        outcome = "pass" if decision.enforcement == "allow" else "fail"
        event_type = "access_granted" if decision.enforcement == "allow" else "access_denied"
        record = TrustTraceRecord(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            trace_id=str(uuid.uuid4()),
            agent_id=facts.agent_id,
            layer="L4",
            event_type=event_type,
            details={
                "action": action,
                "enforcement": decision.enforcement,
                "reason": decision.reason,
                "backend": decision.backend,
            },
            outcome=outcome,
        )
        try:
            self._trace_emit(record)
        except Exception as exc:
            logger.error(
                "trace_emit failed: %s: %s", type(exc).__name__, exc
            )


__all__ = [
    "PolicyBackend",
    "AuthorizationService",
    "EmbeddedPolicyBackend",
    "AuthorizationError",
]
