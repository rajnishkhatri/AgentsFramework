"""PhaseLogger: decision + reasoning logs.

Captures why decisions were made with structured Decision records.
Storage: cache/phase_logs/{workflow_id}/decisions.jsonl
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger("services.governance.phase_logger")


class WorkflowPhase(str, Enum):
    INITIALIZATION = "initialization"
    INPUT_VALIDATION = "input_validation"
    ROUTING = "routing"
    MODEL_INVOCATION = "model_invocation"
    TOOL_EXECUTION = "tool_execution"
    EVALUATION = "evaluation"
    CONTINUATION = "continuation"
    OUTPUT_VALIDATION = "output_validation"
    COMPLETION = "completion"


class Decision(BaseModel):
    phase: WorkflowPhase
    description: str
    alternatives: list[str]
    rationale: str
    confidence: float


class PhaseLogger:
    def __init__(self, storage_dir: Path | str) -> None:
        self._storage_dir = Path(storage_dir)

    def start_phase(self, workflow_id: str, phase: WorkflowPhase) -> None:
        logger.info("Phase %s started for workflow %s", phase.value, workflow_id)

    def log_decision(self, workflow_id: str, decision: Decision) -> None:
        wf_dir = self._storage_dir / workflow_id
        wf_dir.mkdir(parents=True, exist_ok=True)
        log_file = wf_dir / "decisions.jsonl"

        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "workflow_id": workflow_id,
            **decision.model_dump(mode="json"),
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(record) + "\n")

        logger.info(
            "Decision [%s]: %s",
            decision.phase.value,
            decision.description,
        )

    def end_phase(
        self,
        workflow_id: str,
        phase: WorkflowPhase,
        outcome: str,
        details: dict,
    ) -> None:
        logger.info(
            "Phase %s ended for workflow %s: %s",
            phase.value,
            workflow_id,
            outcome,
        )

    def export_workflow_log(self, workflow_id: str) -> list[dict]:
        log_file = self._storage_dir / workflow_id / "decisions.jsonl"
        if not log_file.exists():
            return []
        entries = []
        for line in log_file.read_text().strip().split("\n"):
            if line:
                entries.append(json.loads(line))
        return entries
