"""Ids that become storage path segments must not escape the storage root."""

from __future__ import annotations

import pytest

from services.governance.agent_facts_gcs_registry import AgentFactsGcsRegistry
from services.governance.agent_facts_registry import AgentFactsRegistry
from services.governance.phase_logger import Decision, PhaseLogger, WorkflowPhase
from trust.models import AgentFacts

BAD_IDS = ["../escaped", "a/b", "..", "a\\b"]


def _facts(agent_id: str) -> AgentFacts:
    return AgentFacts(agent_id=agent_id, agent_name="n", owner="o", version="1")


@pytest.mark.parametrize("bad_id", BAD_IDS)
def test_should_reject_phase_logger_writes_when_workflow_id_unsafe(tmp_path, bad_id):
    phase_logger = PhaseLogger(tmp_path / "store")
    decision = Decision(
        phase=WorkflowPhase.ROUTING,
        description="d",
        alternatives=[],
        rationale="r",
        confidence=0.5,
    )

    with pytest.raises(ValueError, match="workflow_id"):
        phase_logger.log_decision(bad_id, decision)
    with pytest.raises(ValueError, match="workflow_id"):
        phase_logger.start_phase(bad_id, WorkflowPhase.ROUTING)
    assert phase_logger.export_workflow_log(bad_id) == []
    assert phase_logger.export_phase_events(bad_id) == []
    assert not (tmp_path / "escaped").exists()


@pytest.mark.parametrize("bad_id", BAD_IDS)
def test_should_reject_registry_operations_when_agent_id_unsafe(tmp_path, bad_id):
    registry = AgentFactsRegistry(tmp_path / "store", secret="s")

    with pytest.raises(ValueError, match="agent_id"):
        registry.register(_facts(bad_id), registered_by="admin")
    assert registry.verify(bad_id) is False
    with pytest.raises(KeyError):
        registry.get(bad_id)
    assert registry.audit_trail(bad_id) == []
    assert not (tmp_path / "escaped.json").exists()


@pytest.mark.parametrize("bad_id", BAD_IDS)
def test_should_reject_gcs_registry_operations_when_agent_id_unsafe(bad_id):
    from unittest.mock import MagicMock

    client = MagicMock()
    registry = AgentFactsGcsRegistry("bucket", secret="s", client=client)

    with pytest.raises(ValueError, match="agent_id"):
        registry.register(_facts(bad_id), registered_by="admin")
    assert registry.verify(bad_id) is False
    with pytest.raises(KeyError):
        registry.get(bad_id)
    client.bucket.assert_not_called()
