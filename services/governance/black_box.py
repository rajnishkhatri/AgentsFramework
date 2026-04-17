"""BlackBoxRecorder: immutable execution recording.

Append-only JSONL with chained SHA-256 integrity hashes.
export() and replay() deferred to Phase 2.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger("services.governance.black_box")


class EventType(str, Enum):
    TASK_STARTED = "task_started"
    STEP_PLANNED = "step_planned"
    STEP_EXECUTED = "step_executed"
    TOOL_CALLED = "tool_called"
    MODEL_SELECTED = "model_selected"
    ERROR_OCCURRED = "error_occurred"
    GUARDRAIL_CHECKED = "guardrail_checked"
    PARAMETER_CHANGED = "parameter_changed"
    TASK_COMPLETED = "task_completed"


class TraceEvent(BaseModel):
    event_id: str
    workflow_id: str
    event_type: EventType
    timestamp: datetime
    step: int | None = None
    details: dict[str, Any]
    integrity_hash: str = ""


class BlackBoxRecorder:
    def __init__(self, storage_dir: Path | str) -> None:
        self._storage_dir = Path(storage_dir)
        self._last_hash: dict[str, str] = {}

    def record(self, event: TraceEvent) -> None:
        wf_dir = self._storage_dir / event.workflow_id
        wf_dir.mkdir(parents=True, exist_ok=True)
        trace_file = wf_dir / "trace.jsonl"

        prev_hash = self._last_hash.get(event.workflow_id, "0" * 64)
        event_data = event.model_dump(mode="json")
        event_data.pop("integrity_hash", None)
        payload = json.dumps(event_data, sort_keys=True, default=str) + prev_hash
        integrity_hash = hashlib.sha256(payload.encode()).hexdigest()

        event_data["integrity_hash"] = integrity_hash
        self._last_hash[event.workflow_id] = integrity_hash

        with open(trace_file, "a") as f:
            f.write(json.dumps(event_data, default=str) + "\n")

        logger.info(
            "Recorded %s for workflow %s",
            event.event_type.value,
            event.workflow_id,
        )

    def export(self, workflow_id: str) -> dict:
        """Export a workflow's trace as a structured JSON bundle with integrity verification.

        Returns a dict containing events, metadata, and a verification status
        indicating whether the hash chain is intact.
        """
        trace_file = self._storage_dir / workflow_id / "trace.jsonl"
        if not trace_file.exists():
            raise KeyError(f"No trace found for workflow_id={workflow_id!r}")

        events = []
        chain_valid = True
        prev_hash = "0" * 64

        for line in trace_file.read_text().strip().split("\n"):
            if not line:
                continue
            event_data = json.loads(line)
            stored_hash = event_data.get("integrity_hash", "")

            verify_data = dict(event_data)
            verify_data.pop("integrity_hash", None)
            payload = json.dumps(verify_data, sort_keys=True, default=str) + prev_hash
            expected_hash = hashlib.sha256(payload.encode()).hexdigest()

            if stored_hash != expected_hash:
                chain_valid = False
                logger.warning(
                    "Hash chain broken for workflow %s at event %s",
                    workflow_id,
                    event_data.get("event_id", "unknown"),
                )

            prev_hash = stored_hash
            events.append(event_data)

        return {
            "workflow_id": workflow_id,
            "event_count": len(events),
            "events": events,
            "hash_chain_valid": chain_valid,
            "exported_at": datetime.now(UTC).isoformat() if events else None,
        }

    def replay(self, workflow_id: str) -> list[TraceEvent]:
        """Reconstruct the event timeline for a workflow in chronological order."""
        trace_file = self._storage_dir / workflow_id / "trace.jsonl"
        if not trace_file.exists():
            raise KeyError(f"No trace found for workflow_id={workflow_id!r}")

        events: list[TraceEvent] = []
        for line in trace_file.read_text().strip().split("\n"):
            if not line:
                continue
            event_data = json.loads(line)
            events.append(TraceEvent.model_validate(event_data))

        events.sort(key=lambda e: e.timestamp)
        return events

    def export_for_compliance(
        self,
        workflow_id: str,
        agent_facts_registry: Any = None,
        phase_logger: Any = None,
    ) -> dict:
        """Story 6.3: produce a compliance-ready bundle joining all governance artifacts."""
        bundle = self.export(workflow_id)

        if agent_facts_registry is not None:
            try:
                agent_ids = {
                    e.get("details", {}).get("agent_id")
                    for e in bundle.get("events", [])
                    if e.get("details", {}).get("agent_id")
                }
                identity_cards = {}
                audit_trails = {}
                for aid in agent_ids:
                    if aid:
                        try:
                            identity_cards[aid] = agent_facts_registry.get(aid).model_dump(mode="json")
                        except KeyError:
                            identity_cards[aid] = None
                        audit_trails[aid] = [
                            entry.model_dump(mode="json")
                            for entry in agent_facts_registry.audit_trail(aid)
                        ]
                bundle["identity_cards"] = identity_cards
                bundle["audit_trails"] = audit_trails
            except Exception as exc:
                logger.warning("Failed to include AgentFacts in compliance bundle: %s", exc)

        if phase_logger is not None:
            try:
                bundle["phase_decisions"] = phase_logger.export_workflow_log(workflow_id)
            except Exception as exc:
                logger.warning("Failed to include phase decisions in compliance bundle: %s", exc)

        bundle["bundle_type"] = "compliance_audit"
        return bundle
