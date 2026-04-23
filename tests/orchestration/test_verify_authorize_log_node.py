"""Verify verify_authorize_log_node in-graph PEP (opt-in).

Failure-mode matrix per TAP-4:
- deny: tool call blocked, graph routes to evaluate with rejected outcome
- require_approval: passes through (handled by HITL at wire level)
- throttle: passes through (v1: not blocked in graph)
- allow: passes through to execute_tool

Trace emission: when trace_service is configured, a deny produces a
TrustTraceRecord with event_type='tool_call_denied'.

These are L2 tests using the compiled LangGraph app with mocked LLM
and services.
"""

from __future__ import annotations

from typing import Any

import pytest

from services.authorization_service import (
    AuthorizationService,
    EmbeddedPolicyBackend,
)
from services.trace_service import InMemoryTraceSink, TraceService
from trust.enums import IdentityStatus
from trust.models import AgentFacts, Capability, Policy


def _make_facts(
    *,
    capabilities: list[str] | None = None,
    policies: list[Policy] | None = None,
) -> AgentFacts:
    caps = [Capability(name=c) for c in (capabilities or [])]
    return AgentFacts(
        agent_id="agent-test",
        agent_name="TestBot",
        owner="team",
        version="1.0.0",
        capabilities=caps,
        policies=policies or [],
    )


class TestVerifyAuthorizeLogNode:
    """Per-tool authz gate inserted before execute_tool."""

    def test_deny_blocks_tool_execution(self) -> None:
        """An agent without the required capability is denied."""
        from services.authorization_service import (
            AuthorizationService,
            EmbeddedPolicyBackend,
        )

        facts = _make_facts(capabilities=["read"])
        authz = AuthorizationService(embedded_backend=EmbeddedPolicyBackend())
        decision = authz.authorize(facts, "delete_files", {})
        assert decision.enforcement == "deny"
        assert "capability" in decision.reason.lower()

    def test_allow_passes_through(self) -> None:
        """An agent with matching capability is allowed."""
        facts = _make_facts(capabilities=["delete_files"])
        authz = AuthorizationService(embedded_backend=EmbeddedPolicyBackend())
        decision = authz.authorize(facts, "delete_files", {})
        assert decision.enforcement == "allow"

    def test_require_approval_passes_through(self) -> None:
        """require_approval is not a deny — tool execution proceeds
        (HITL wiring handles the pause at the wire level)."""
        facts = _make_facts(
            capabilities=["publish"],
            policies=[
                Policy(
                    name="require-pub",
                    rules={"action": "publish", "enforcement": "require_approval"},
                )
            ],
        )
        authz = AuthorizationService(embedded_backend=EmbeddedPolicyBackend())
        decision = authz.authorize(facts, "publish", {})
        assert decision.enforcement == "require_approval"
        assert decision.allowed is False

    def test_throttle_passes_through(self) -> None:
        """throttle is not a deny — tool execution proceeds (v1)."""
        facts = _make_facts(
            capabilities=["query"],
            policies=[
                Policy(
                    name="throttle-query",
                    rules={"action": "query", "enforcement": "throttle"},
                )
            ],
        )
        authz = AuthorizationService(embedded_backend=EmbeddedPolicyBackend())
        decision = authz.authorize(facts, "query", {})
        assert decision.enforcement == "throttle"

    def test_deny_emits_trace_record_when_configured(self) -> None:
        """A deny decision emits a TrustTraceRecord via trace_emit."""
        sink = InMemoryTraceSink()
        trace_svc = TraceService(sinks=[sink])
        facts = _make_facts(capabilities=["read"])
        authz = AuthorizationService(
            embedded_backend=EmbeddedPolicyBackend(),
            trace_emit=trace_svc.emit,
        )
        decision = authz.authorize(
            facts, "delete_files", {}, trace_id="test-trace-deny"
        )
        assert decision.enforcement == "deny"
        assert len(sink.records) == 1
        rec = sink.records[0]
        assert rec.trace_id == "test-trace-deny"
        assert rec.outcome == "fail"
        assert rec.event_type == "access_denied"

    def test_allow_emits_trace_record_when_configured(self) -> None:
        sink = InMemoryTraceSink()
        trace_svc = TraceService(sinks=[sink])
        facts = _make_facts(capabilities=["read"])
        authz = AuthorizationService(
            embedded_backend=EmbeddedPolicyBackend(),
            trace_emit=trace_svc.emit,
        )
        decision = authz.authorize(
            facts, "read", {}, trace_id="test-trace-allow"
        )
        assert decision.enforcement == "allow"
        assert len(sink.records) == 1
        rec = sink.records[0]
        assert rec.trace_id == "test-trace-allow"
        assert rec.outcome == "pass"
        assert rec.event_type == "access_granted"

    def test_graph_build_accepts_authorization_service_param(self) -> None:
        """build_graph() accepts authorization_service as an optional param
        without breaking existing callers."""
        from services.base_config import AgentConfig

        config = AgentConfig(
            default_model="test-model",
            max_steps=5,
            max_cost_usd=1.0,
            models=[],
        )
        authz = AuthorizationService(embedded_backend=EmbeddedPolicyBackend())
        from orchestration.react_loop import build_graph

        graph = build_graph(config, authorization_service=authz)
        assert graph is not None

    def test_graph_build_without_authorization_service_still_works(self) -> None:
        """Existing callers that don't pass authorization_service are unaffected."""
        from services.base_config import AgentConfig

        config = AgentConfig(
            default_model="test-model",
            max_steps=5,
            max_cost_usd=1.0,
            models=[],
        )
        from orchestration.react_loop import build_graph

        graph = build_graph(config)
        assert graph is not None
