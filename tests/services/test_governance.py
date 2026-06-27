"""L2 Reproducible: Tests for services/governance/ stubs.

Contract-driven TDD. Tests AgentFactsRegistry (register, verify,
suspend, restore, audit_trail), BlackBoxRecorder (record, integrity
hash chain), and PhaseLogger (log_decision).

Failure paths first per TDD principle.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

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
        from services.governance.black_box import (
            BlackBoxRecorder,
            EventType,
            TraceEvent,
        )

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

        from services.governance.black_box import (
            BlackBoxRecorder,
            EventType,
            TraceEvent,
        )

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
        from services.governance.phase_logger import (
            Decision,
            PhaseLogger,
            WorkflowPhase,
        )

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
        from services.governance.phase_logger import (
            Decision,
            PhaseLogger,
            WorkflowPhase,
        )

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


class TestPhaseLoggerFailurePaths:
    """C0 (Sprint 0 red): failure-path tests for PhaseLogger persistence (B1).

    These assert behaviors that the log-only implementation does not provide yet.
    Remove the class ``xfail`` marker when Sprint 1 turns them green. Failure paths
    first (TDD prompt §4, TAP-4).
    """

    @staticmethod
    def _phases_path(tmp_path, workflow_id: str):
        return tmp_path / workflow_id / "phases.jsonl"

    def test_end_phase_without_start_writes_end_and_warns(self, tmp_path, caplog):
        from services.governance.phase_logger import PhaseLogger, WorkflowPhase

        pl = PhaseLogger(storage_dir=tmp_path)
        with caplog.at_level(
            logging.WARNING, logger="services.governance.phase_logger"
        ):
            pl.end_phase("wf-unbalanced", WorkflowPhase.ROUTING, "done", step_count=0)

        phases_file = self._phases_path(tmp_path, "wf-unbalanced")
        assert phases_file.exists(), (
            "end_phase must persist a phase_end row even without start"
        )
        rows = [
            json.loads(line)
            for line in phases_file.read_text().strip().split("\n")
            if line
        ]
        assert any(r.get("event") == "phase_end" for r in rows)
        assert any("without matching start" in r.getMessage() for r in caplog.records)

    def test_per_step_key_isolation(self, tmp_path):
        from tests.conftest import freeze_time

        from services.governance.phase_logger import PhaseLogger, WorkflowPhase

        pl = PhaseLogger(storage_dir=tmp_path)
        with freeze_time("2026-06-01T10:00:00Z"):
            pl.start_phase("wf-steps", WorkflowPhase.ROUTING, step_count=0)
        with freeze_time("2026-06-01T10:00:01Z"):
            pl.end_phase("wf-steps", WorkflowPhase.ROUTING, "done", step_count=0)
        with freeze_time("2026-06-01T10:00:02Z"):
            pl.start_phase("wf-steps", WorkflowPhase.ROUTING, step_count=1)
        with freeze_time("2026-06-01T10:00:03Z"):
            pl.end_phase("wf-steps", WorkflowPhase.ROUTING, "done", step_count=1)

        events = pl.export_phase_events("wf-steps")
        ends = [e for e in events if e.get("event") == "phase_end"]
        assert len(ends) == 2
        assert {e["step_count"] for e in ends} == {0, 1}
        assert all(e.get("duration_ms", -1) >= 0 for e in ends)

    def test_jsonl_write_io_error_does_not_crash(self, tmp_path, monkeypatch, caplog):
        from services.governance.phase_logger import PhaseLogger, WorkflowPhase

        pl = PhaseLogger(storage_dir=tmp_path)
        real_open = open

        def failing_open(file, mode="r", *args, **kwargs):
            path = str(file)
            if "phases.jsonl" in path and "a" in mode:
                raise OSError("simulated disk full")
            return real_open(file, mode, *args, **kwargs)

        monkeypatch.setattr("builtins.open", failing_open)
        with caplog.at_level(
            logging.WARNING, logger="services.governance.phase_logger"
        ):
            pl.start_phase("wf-io", WorkflowPhase.INPUT_VALIDATION, step_count=0)

        assert any(
            "phases.jsonl" in r.getMessage() or "phase" in r.getMessage().lower()
            for r in caplog.records
        )

    def test_completion_without_start_warns_no_crash(self, tmp_path, caplog):
        from services.governance.phase_logger import PhaseLogger, WorkflowPhase

        pl = PhaseLogger(storage_dir=tmp_path)
        with caplog.at_level(
            logging.WARNING, logger="services.governance.phase_logger"
        ):
            pl.end_phase(
                "wf-completion", WorkflowPhase.COMPLETION, "done", step_count=0
            )

        phases_file = self._phases_path(tmp_path, "wf-completion")
        assert phases_file.exists()
        exported = pl.export_phase_events("wf-completion")
        assert any(
            ev.get("event") == "phase_end" and ev.get("phase") == "completion"
            for ev in exported
        )
        assert any("without matching start" in r.getMessage() for r in caplog.records)

    def test_mixed_export_ordering_keeps_decisions_separate(self, tmp_path):
        from services.governance.phase_logger import (
            Decision,
            PhaseLogger,
            WorkflowPhase,
        )

        pl = PhaseLogger(storage_dir=tmp_path)
        pl.start_phase("wf-mixed", WorkflowPhase.INITIALIZATION, step_count=0)
        pl.log_decision(
            "wf-mixed",
            Decision(
                phase=WorkflowPhase.ROUTING,
                description="route",
                alternatives=[],
                rationale="r",
                confidence=1.0,
            ),
        )
        pl.end_phase("wf-mixed", WorkflowPhase.INITIALIZATION, "ok", step_count=0)

        decisions = pl.export_workflow_log("wf-mixed")
        phase_events = pl.export_phase_events("wf-mixed")

        assert len(decisions) == 1
        assert decisions[0].get("description") == "route"
        assert not any(
            d.get("event") in ("phase_start", "phase_end") for d in decisions
        )
        assert len(phase_events) >= 2
        assert not any(e.get("description") == "route" for e in phase_events)

    def test_phase_duration_tracked_with_freezegun(self, tmp_path):
        from datetime import datetime

        from tests.conftest import freeze_time

        from services.governance.phase_logger import PhaseLogger, WorkflowPhase

        pl = PhaseLogger(storage_dir=tmp_path)
        t0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        t1 = datetime(2026, 6, 1, 12, 0, 0, 500000, tzinfo=UTC)
        with freeze_time(t0):
            pl.start_phase("wf-dur", WorkflowPhase.MODEL_INVOCATION, step_count=2)
        with freeze_time(t1):
            pl.end_phase("wf-dur", WorkflowPhase.MODEL_INVOCATION, "ok", step_count=2)

        ends = [
            e for e in pl.export_phase_events("wf-dur") if e.get("event") == "phase_end"
        ]
        assert len(ends) == 1
        assert ends[0]["duration_ms"] >= 500


class TestPhaseLoggerImplementation:
    """C1 (Sprint 1 green): acceptance tests for PhaseLogger persistence (B1)."""

    def test_start_end_writes_phases_jsonl_schema(self, tmp_path):
        from tests.conftest import freeze_time

        from services.governance.phase_logger import PhaseLogger, WorkflowPhase

        pl = PhaseLogger(storage_dir=tmp_path)
        with freeze_time("2026-06-01T11:00:00Z"):
            pl.start_phase("wf-schema", WorkflowPhase.INITIALIZATION, step_count=0)
        with freeze_time("2026-06-01T11:00:01Z"):
            pl.end_phase("wf-schema", WorkflowPhase.INITIALIZATION, "ok", step_count=0)

        events = pl.export_phase_events("wf-schema")
        assert len(events) == 2

        start_row = next(e for e in events if e["event"] == "phase_start")
        end_row = next(e for e in events if e["event"] == "phase_end")
        assert start_row["workflow_id"] == "wf-schema"
        assert start_row["step_count"] == 0
        assert start_row["phase"] == "initialization"
        assert "timestamp" in start_row
        assert "outcome" not in start_row

        assert end_row["outcome"] == "ok"
        assert end_row["duration_ms"] >= 0

    def test_phase_tracker_records_error_on_exception_and_reraises(self, tmp_path):
        import asyncio

        from services.governance.phase_logger import PhaseLogger, WorkflowPhase

        pl = PhaseLogger(storage_dir=tmp_path)

        async def _run() -> None:
            async with pl.phase("wf-err", WorkflowPhase.MODEL_INVOCATION, step_count=1):
                raise RuntimeError("simulated llm failure")

        with pytest.raises(RuntimeError, match="simulated llm failure"):
            asyncio.run(_run())

        events = pl.export_phase_events("wf-err")
        ends = [e for e in events if e["event"] == "phase_end"]
        assert len(ends) == 1
        assert ends[0]["outcome"] == "error"
        assert ends[0]["step_count"] == 1
        # Start key must be popped so a subsequent phase at same key can start fresh.
        pl.start_phase("wf-err", WorkflowPhase.MODEL_INVOCATION, step_count=1)
        pl.end_phase("wf-err", WorkflowPhase.MODEL_INVOCATION, "ok", step_count=1)
        assert (
            len(
                [
                    e
                    for e in pl.export_phase_events("wf-err")
                    if e["event"] == "phase_end"
                ]
            )
            == 2
        )

    def test_phase_tracker_success_outcome(self, tmp_path):
        import asyncio

        from services.governance.phase_logger import PhaseLogger, WorkflowPhase

        pl = PhaseLogger(storage_dir=tmp_path)

        async def _run() -> None:
            async with pl.phase(
                "wf-ok",
                WorkflowPhase.ROUTING,
                step_count=0,
                outcome="routed",
            ):
                pass

        asyncio.run(_run())
        ends = [e for e in pl.export_phase_events("wf-ok") if e["event"] == "phase_end"]
        assert len(ends) == 1
        assert ends[0]["outcome"] == "routed"

    def test_injected_decision_id_factory_yields_deterministic_ids(self, tmp_path):
        from services.governance.phase_logger import (
            Decision,
            PhaseLogger,
            WorkflowPhase,
        )

        counter = {"n": 0}

        def factory() -> str:
            counter["n"] += 1
            return f"decision-{counter['n']}"

        pl = PhaseLogger(storage_dir=tmp_path, decision_id_factory=factory)
        decision = Decision(
            phase=WorkflowPhase.ROUTING,
            description="first",
            alternatives=[],
            rationale="r",
            confidence=1.0,
        )
        decision = pl.log_decision("wf-ids", decision)
        assert decision.decision_id == "decision-1"
        pl.log_decision(
            "wf-ids",
            Decision(
                phase=WorkflowPhase.EVALUATION,
                description="second",
                alternatives=[],
                rationale="r",
                confidence=1.0,
            ),
        )

        entries = pl.export_workflow_log("wf-ids")
        assert [e["decision_id"] for e in entries] == ["decision-1", "decision-2"]


class TestDecisionIdJoin:
    """S2 (Sprint 2): decision_id on Decision model + MODEL_SELECTED cross-pillar join."""

    def test_ensure_decision_id_is_idempotent(self, tmp_path):
        from services.governance.phase_logger import (
            Decision,
            PhaseLogger,
            WorkflowPhase,
        )

        pl = PhaseLogger(storage_dir=tmp_path, decision_id_factory=lambda: "stable-id")
        base = Decision(
            phase=WorkflowPhase.ROUTING,
            description="route",
            alternatives=[],
            rationale="r",
            confidence=1.0,
        )
        first = pl.ensure_decision_id(base)
        second = pl.ensure_decision_id(first)
        assert first.decision_id == "stable-id"
        assert second.decision_id == "stable-id"

    def test_log_decision_assigns_id_on_model_and_jsonl(self, tmp_path):
        from services.governance.phase_logger import (
            Decision,
            PhaseLogger,
            WorkflowPhase,
        )

        pl = PhaseLogger(storage_dir=tmp_path, decision_id_factory=lambda: "join-id")
        decision = pl.log_decision(
            "wf-model",
            Decision(
                phase=WorkflowPhase.ROUTING,
                description="Selected gpt-4o-mini",
                alternatives=["gpt-4o"],
                rationale="steady-state",
                confidence=0.75,
            ),
        )
        assert decision.decision_id == "join-id"
        row = pl.export_workflow_log("wf-model")[0]
        assert row["decision_id"] == decision.decision_id

    def test_model_selected_details_share_decision_id(self, tmp_path):
        """Route-node pattern: same id in decisions.jsonl and BlackBox MODEL_SELECTED."""
        from datetime import UTC, datetime

        from services.governance.black_box import (
            BlackBoxRecorder,
            EventType,
            TraceEvent,
        )
        from services.governance.phase_logger import (
            Decision,
            PhaseLogger,
            WorkflowPhase,
        )

        wf_id = "wf-cross-pillar"
        pl = PhaseLogger(
            storage_dir=tmp_path, decision_id_factory=lambda: "route-decision-42"
        )
        bb = BlackBoxRecorder(storage_dir=tmp_path / "black_box")

        decision = pl.log_decision(
            wf_id,
            Decision(
                phase=WorkflowPhase.ROUTING,
                description="Selected gpt-4o-mini",
                alternatives=["gpt-4o"],
                rationale="capable-for-planning",
                confidence=0.75,
            ),
        )
        bb.record(
            TraceEvent(
                event_id="ev-model-selected",
                workflow_id=wf_id,
                event_type=EventType.MODEL_SELECTED,
                timestamp=datetime.now(UTC),
                step=0,
                details={
                    "model": "gpt-4o-mini",
                    "reason": "capable-for-planning",
                    "decision_id": decision.decision_id,
                },
            )
        )

        decision_row = pl.export_workflow_log(wf_id)[0]
        model_selected = [
            e
            for e in bb.export(wf_id)["events"]
            if e["event_type"] == EventType.MODEL_SELECTED.value
        ]
        assert len(model_selected) == 1
        assert decision_row["decision_id"] == "route-decision-42"
        assert (
            model_selected[0]["details"]["decision_id"] == decision_row["decision_id"]
        )


try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    _HAS_HYPOTHESIS = True
except ImportError:
    _HAS_HYPOTHESIS = False


@pytest.mark.property
@pytest.mark.skipif(not _HAS_HYPOTHESIS, reason="hypothesis not installed")
class TestDecisionIdUniqueness:
    """C3 (Sprint 2): decision_id uniqueness within a workflow."""

    @settings(max_examples=25, deadline=None)
    @given(n=st.integers(min_value=2, max_value=50))
    def test_decision_ids_unique_in_workflow(self, n: int):
        import tempfile

        from services.governance.phase_logger import (
            Decision,
            PhaseLogger,
            WorkflowPhase,
        )

        with tempfile.TemporaryDirectory() as storage_dir:
            pl = PhaseLogger(storage_dir=storage_dir)
            wf_id = "wf-uniqueness"
            for i in range(n):
                pl.log_decision(
                    wf_id,
                    Decision(
                        phase=WorkflowPhase.ROUTING,
                        description=f"decision-{i}",
                        alternatives=[],
                        rationale="property test",
                        confidence=1.0,
                    ),
                )

            ids = [row["decision_id"] for row in pl.export_workflow_log(wf_id)]
            assert len(ids) == n
            assert len(set(ids)) == n


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
        from services.governance.phase_logger import (
            Decision,
            PhaseLogger,
            WorkflowPhase,
        )

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
        from services.governance.phase_logger import (
            Decision,
            PhaseLogger,
            WorkflowPhase,
        )

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
        from services.governance.phase_logger import (
            Decision,
            PhaseLogger,
            WorkflowPhase,
        )

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
