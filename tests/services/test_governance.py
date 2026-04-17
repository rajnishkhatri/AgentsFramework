"""L2 Reproducible: Tests for services/governance/ stubs.

Contract-driven TDD. Tests AgentFactsRegistry (register, verify,
suspend, restore, audit_trail), BlackBoxRecorder (record, integrity
hash chain), and PhaseLogger (log_decision).

Failure paths first per TDD principle.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from trust.enums import IdentityStatus
from trust.models import AgentFacts


def _make_facts(**overrides) -> AgentFacts:
    defaults = {
        "agent_id": "agent-001",
        "agent_name": "TestBot",
        "owner": "team-test",
        "version": "1.0.0",
    }
    defaults.update(overrides)
    return AgentFacts(**defaults)


class TestAgentFactsRegistry:
    def test_requires_secret(self, tmp_path, monkeypatch):
        monkeypatch.delenv("AGENT_FACTS_SECRET", raising=False)
        from services.governance.agent_facts_registry import AgentFactsRegistry

        with pytest.raises(ValueError, match="requires a secret"):
            AgentFactsRegistry(storage_dir=tmp_path)

    def test_reads_secret_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENT_FACTS_SECRET", "env-secret")
        from services.governance.agent_facts_registry import AgentFactsRegistry

        registry = AgentFactsRegistry(storage_dir=tmp_path)
        assert registry._secret == "env-secret"

    def test_register_and_get(self, tmp_path):
        from services.governance.agent_facts_registry import AgentFactsRegistry

        registry = AgentFactsRegistry(storage_dir=tmp_path, secret="test-secret")
        facts = _make_facts()
        registered = registry.register(facts, registered_by="admin")
        assert registered.agent_id == "agent-001"

        retrieved = registry.get("agent-001")
        assert retrieved.agent_id == "agent-001"

    def test_verify_valid_agent(self, tmp_path):
        from services.governance.agent_facts_registry import AgentFactsRegistry

        registry = AgentFactsRegistry(storage_dir=tmp_path, secret="test-secret")
        registry.register(_make_facts(), registered_by="admin")
        assert registry.verify("agent-001") is True

    def test_verify_nonexistent_agent_returns_false(self, tmp_path):
        from services.governance.agent_facts_registry import AgentFactsRegistry

        registry = AgentFactsRegistry(storage_dir=tmp_path, secret="test-secret")
        assert registry.verify("nonexistent") is False

    def test_suspend_changes_status(self, tmp_path):
        from services.governance.agent_facts_registry import AgentFactsRegistry

        registry = AgentFactsRegistry(storage_dir=tmp_path, secret="test-secret")
        registry.register(_make_facts(), registered_by="admin")
        registry.suspend("agent-001", reason="test suspension", suspended_by="admin")
        facts = registry.get("agent-001")
        assert facts.status == IdentityStatus.SUSPENDED

    def test_restore_after_suspend(self, tmp_path):
        from services.governance.agent_facts_registry import AgentFactsRegistry

        registry = AgentFactsRegistry(storage_dir=tmp_path, secret="test-secret")
        registry.register(_make_facts(), registered_by="admin")
        registry.suspend("agent-001", reason="test", suspended_by="admin")
        registry.restore("agent-001", reason="cleared", restored_by="admin")
        facts = registry.get("agent-001")
        assert facts.status == IdentityStatus.ACTIVE

    def test_suspended_agent_fails_verify(self, tmp_path):
        from services.governance.agent_facts_registry import AgentFactsRegistry

        registry = AgentFactsRegistry(storage_dir=tmp_path, secret="test-secret")
        registry.register(_make_facts(), registered_by="admin")
        registry.suspend("agent-001", reason="test", suspended_by="admin")
        assert registry.verify("agent-001") is False

    def test_audit_trail(self, tmp_path):
        from services.governance.agent_facts_registry import AgentFactsRegistry

        registry = AgentFactsRegistry(storage_dir=tmp_path, secret="test-secret")
        registry.register(_make_facts(), registered_by="admin")
        registry.suspend("agent-001", reason="test", suspended_by="admin")
        trail = registry.audit_trail("agent-001")
        assert len(trail) >= 2
        actions = [e.action for e in trail]
        assert "register" in actions
        assert "suspend" in actions


class TestBlackBoxRecorder:
    def test_record_event(self, tmp_path):
        from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent

        recorder = BlackBoxRecorder(storage_dir=tmp_path)
        event = TraceEvent(
            event_id="evt-001",
            workflow_id="wf-001",
            event_type=EventType.TASK_STARTED,
            timestamp=datetime.now(UTC),
            details={"task": "test"},
        )
        recorder.record(event)
        trace_file = tmp_path / "wf-001" / "trace.jsonl"
        assert trace_file.exists()

    def test_integrity_hash_chain(self, tmp_path):
        import json

        from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent

        recorder = BlackBoxRecorder(storage_dir=tmp_path)
        for i in range(3):
            event = TraceEvent(
                event_id=f"evt-{i}",
                workflow_id="wf-chain",
                event_type=EventType.STEP_EXECUTED,
                timestamp=datetime.now(UTC),
                step=i,
                details={"step": i},
            )
            recorder.record(event)

        trace_file = tmp_path / "wf-chain" / "trace.jsonl"
        lines = trace_file.read_text().strip().split("\n")
        assert len(lines) == 3
        hashes = [json.loads(line)["integrity_hash"] for line in lines]
        assert len(set(hashes)) == 3

    def test_export_unknown_workflow_raises_key_error(self, tmp_path):
        from services.governance.black_box import BlackBoxRecorder

        recorder = BlackBoxRecorder(storage_dir=tmp_path)
        with pytest.raises(KeyError, match="No trace found"):
            recorder.export("wf-nonexistent")

    def test_replay_unknown_workflow_raises_key_error(self, tmp_path):
        from services.governance.black_box import BlackBoxRecorder

        recorder = BlackBoxRecorder(storage_dir=tmp_path)
        with pytest.raises(KeyError, match="No trace found"):
            recorder.replay("wf-nonexistent")


class TestPhaseLogger:
    def test_log_decision(self, tmp_path):
        from services.governance.phase_logger import Decision, PhaseLogger, WorkflowPhase

        logger = PhaseLogger(storage_dir=tmp_path)
        decision = Decision(
            phase=WorkflowPhase.ROUTING,
            description="Selected gpt-4o-mini",
            alternatives=["gpt-4o"],
            rationale="Phase 1 trivial routing",
            confidence=1.0,
        )
        logger.log_decision("wf-001", decision)

        log_file = tmp_path / "wf-001" / "decisions.jsonl"
        assert log_file.exists()

    def test_multiple_decisions(self, tmp_path):
        from services.governance.phase_logger import Decision, PhaseLogger, WorkflowPhase

        logger = PhaseLogger(storage_dir=tmp_path)
        for phase in [WorkflowPhase.ROUTING, WorkflowPhase.EVALUATION]:
            decision = Decision(
                phase=phase,
                description=f"Decision for {phase}",
                alternatives=[],
                rationale="test",
                confidence=0.9,
            )
            logger.log_decision("wf-002", decision)

        log_file = tmp_path / "wf-002" / "decisions.jsonl"
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 2


# ─────────────────────────────────────────────────────────────────────
# Workstream F: L4 Binary-outcome — route/evaluate always emit rationale
# ─────────────────────────────────────────────────────────────────────


class TestDecisionRationale:
    """Contract tests for the Decision enrichment from route_node / evaluate_node.

    Instead of invoking the full LangGraph graph (which pulls in heavy
    runtime deps), these tests exercise the Decision-construction pattern
    used in orchestration/react_loop.py end to end through the logger.
    """

    def test_routing_decision_includes_alternatives_and_rationale(self, tmp_path):
        from components.router import select_model
        from components.routing_config import RoutingConfig
        from services.base_config import AgentConfig, ModelProfile
        from services.governance.phase_logger import Decision, PhaseLogger, WorkflowPhase

        cfg = AgentConfig(
            default_model="gpt-4o-mini",
            max_cost_usd=1.0,
            models=[
                ModelProfile(
                    name="gpt-4o-mini",
                    litellm_id="openai/gpt-4o-mini",
                    tier="fast",
                    context_window=128000,
                    cost_per_1k_input=0.00015,
                    cost_per_1k_output=0.0006,
                ),
                ModelProfile(
                    name="gpt-4o",
                    litellm_id="openai/gpt-4o",
                    tier="capable",
                    context_window=128000,
                    cost_per_1k_input=0.005,
                    cost_per_1k_output=0.015,
                ),
            ],
        )
        rcfg = RoutingConfig()

        profile, reason = select_model(
            step_count=0,
            consecutive_errors=0,
            last_error_type="",
            total_cost_usd=0.0,
            model_history=[],
            agent_config=cfg,
            routing_config=rcfg,
        )
        alternatives = [m.name for m in cfg.models if m.name != profile.name]
        decision = Decision(
            phase=WorkflowPhase.ROUTING,
            description=f"Selected {profile.name}",
            alternatives=alternatives,
            rationale=f"{reason} (step=0, errors=0)",
            confidence=0.75,
        )

        plog = PhaseLogger(storage_dir=tmp_path)
        plog.log_decision("wf-rat", decision)
        entries = plog.export_workflow_log("wf-rat")

        routing = [e for e in entries if e["phase"] == "routing"]
        assert len(routing) == 1
        assert routing[0]["alternatives"], "alternatives must be non-empty"
        assert "step=" in routing[0]["rationale"]
        assert 0.0 <= routing[0]["confidence"] <= 1.0

    def test_evaluation_decision_contains_structured_alternatives(self, tmp_path):
        from services.governance.phase_logger import Decision, PhaseLogger, WorkflowPhase

        decision = Decision(
            phase=WorkflowPhase.EVALUATION,
            description="Outcome: failure",
            alternatives=["retry", "escalate", "terminal"],
            rationale="Error type: retryable; rate limited",
            confidence=0.8,
        )
        plog = PhaseLogger(storage_dir=tmp_path)
        plog.log_decision("wf-eval", decision)

        entries = plog.export_workflow_log("wf-eval")
        eval_entries = [e for e in entries if e["phase"] == "evaluation"]
        assert eval_entries
        assert set(eval_entries[0]["alternatives"]) == {"retry", "escalate", "terminal"}
        assert "retryable" in eval_entries[0]["rationale"]


@pytest.mark.simulation
class TestBinaryOutcomeDecisionLog:
    """Binary outcome: every routing decision in decisions.jsonl contains alternatives?"""

    def test_routing_decisions_always_non_empty_alternatives(self, tmp_path):
        from services.governance.phase_logger import Decision, PhaseLogger, WorkflowPhase

        plog = PhaseLogger(storage_dir=tmp_path)
        for i in range(3):
            plog.log_decision(
                "wf-sim",
                Decision(
                    phase=WorkflowPhase.ROUTING,
                    description=f"step {i}",
                    alternatives=["gpt-4o-mini", "gpt-4o"],
                    rationale=f"reason-{i}",
                    confidence=0.7,
                ),
            )
        entries = plog.export_workflow_log("wf-sim")
        routing = [e for e in entries if e["phase"] == "routing"]
        assert routing
        assert all(len(e["alternatives"]) > 0 for e in routing)
