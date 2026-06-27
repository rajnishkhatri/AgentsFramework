"""PhaseLogger: decision + reasoning logs.

Captures why decisions were made with structured Decision records.

Storage layout (split-file contract — Phase 3 schema gate):
  - ``decisions.jsonl``: routing/evaluation decisions only (``export_workflow_log``).
  - ``phases.jsonl``: phase boundary events only (``export_phase_events``).

``phases.jsonl`` row shape (``phase_log_schema_version`` ``"1"``):
  ``{ "event": "phase_start"|"phase_end", "workflow_id", "step_count",
  "phase", "outcome"?, "duration_ms"?, "timestamp" }``
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger("services.governance.phase_logger")

# Wire version for phase boundary events; separate from BlackBox BUNDLE_SCHEMA_VERSION.
PHASE_LOG_SCHEMA_VERSION = "1"


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
    decision_id: str | None = Field(
        default=None,
        description="Cross-pillar join key; assigned by PhaseLogger.ensure_decision_id().",
    )


class PhaseLogger:
    def __init__(
        self,
        storage_dir: Path | str,
        decision_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._storage_dir = Path(storage_dir)
        self._phase_starts: dict[str, datetime] = {}
        self.decision_id_factory: Callable[[], str] = (
            decision_id_factory
            if decision_id_factory is not None
            else lambda: str(uuid.uuid4())
        )

    @staticmethod
    def _phase_key(workflow_id: str, step_count: int, phase: WorkflowPhase) -> str:
        return f"{workflow_id}:{step_count}:{phase.value}"

    def _workflow_dir(self, workflow_id: str) -> Path:
        wf_dir = self._storage_dir / workflow_id
        wf_dir.mkdir(parents=True, exist_ok=True)
        return wf_dir

    def _append_phase_event(self, workflow_id: str, record: dict) -> None:
        log_file = self._workflow_dir(workflow_id) / "phases.jsonl"
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        except OSError as exc:
            logger.warning(
                "Failed to write phases.jsonl for workflow %s: %s",
                workflow_id,
                exc,
            )

    def start_phase(
        self,
        workflow_id: str,
        phase: WorkflowPhase,
        step_count: int = 0,
    ) -> None:
        key = self._phase_key(workflow_id, step_count, phase)
        now = datetime.now(UTC)
        self._phase_starts[key] = now
        self._append_phase_event(
            workflow_id,
            {
                "event": "phase_start",
                "workflow_id": workflow_id,
                "step_count": step_count,
                "phase": phase.value,
                "timestamp": now.isoformat(),
            },
        )
        logger.info(
            "Phase %s started for workflow %s (step %s)",
            phase.value,
            workflow_id,
            step_count,
        )

    def ensure_decision_id(self, decision: Decision) -> Decision:
        """Assign ``decision_id`` from the injectable factory when not already set."""
        if decision.decision_id is not None:
            return decision
        return decision.model_copy(update={"decision_id": self.decision_id_factory()})

    def log_decision(self, workflow_id: str, decision: Decision) -> Decision:
        """Persist a decision row; returns the decision with ``decision_id`` assigned."""
        decision = self.ensure_decision_id(decision)
        wf_dir = self._workflow_dir(workflow_id)
        log_file = wf_dir / "decisions.jsonl"

        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "workflow_id": workflow_id,
            **decision.model_dump(mode="json"),
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(record) + "\n")

        logger.info(
            "Decision [%s]: %s (decision_id=%s)",
            decision.phase.value,
            decision.description,
            decision.decision_id,
        )
        return decision

    def end_phase(
        self,
        workflow_id: str,
        phase: WorkflowPhase,
        outcome: str,
        step_count: int = 0,
        details: dict | None = None,
    ) -> None:
        key = self._phase_key(workflow_id, step_count, phase)
        now = datetime.now(UTC)
        start_time = self._phase_starts.pop(key, None)
        duration_ms: int | None = None
        if start_time is None:
            logger.warning(
                "end_phase for %s without matching start (workflow=%s, step=%s)",
                phase.value,
                workflow_id,
                step_count,
            )
        else:
            duration_ms = int((now - start_time).total_seconds() * 1000)

        record: dict = {
            "event": "phase_end",
            "workflow_id": workflow_id,
            "step_count": step_count,
            "phase": phase.value,
            "outcome": outcome,
            "timestamp": now.isoformat(),
        }
        if duration_ms is not None:
            record["duration_ms"] = duration_ms
        if details is not None:
            record["details"] = details
        self._append_phase_event(workflow_id, record)

        logger.info(
            "Phase %s ended for workflow %s (step %s): %s",
            phase.value,
            workflow_id,
            step_count,
            outcome,
        )

    @asynccontextmanager
    async def phase(
        self,
        workflow_id: str,
        phase: WorkflowPhase,
        step_count: int = 0,
        *,
        outcome: str = "ok",
    ) -> AsyncIterator[None]:
        """Async context manager that balances start/end even on exceptions."""
        self.start_phase(workflow_id, phase, step_count)
        try:
            yield
        except Exception:
            self.end_phase(workflow_id, phase, "error", step_count)
            raise
        else:
            self.end_phase(workflow_id, phase, outcome, step_count)

    def export_workflow_log(self, workflow_id: str) -> list[dict]:
        """Return decision records from ``decisions.jsonl`` only (never phase events)."""
        log_file = self._storage_dir / workflow_id / "decisions.jsonl"
        if not log_file.exists():
            return []
        entries = []
        for line in log_file.read_text().strip().split("\n"):
            if line:
                entries.append(json.loads(line))
        return entries

    def export_phase_events(self, workflow_id: str) -> list[dict]:
        """Return phase boundary records from ``phases.jsonl``."""
        log_file = self._storage_dir / workflow_id / "phases.jsonl"
        if not log_file.exists():
            return []
        entries: list[dict] = []
        for line in log_file.read_text().strip().split("\n"):
            if line:
                entries.append(json.loads(line))
        return entries
