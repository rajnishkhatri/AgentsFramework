"""BlackBoxRecorder: immutable execution recording.

Append-only JSONL with chained SHA-256 integrity hashes.
export() and replay() deferred to Phase 2.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from services.governance.hash_chain import append_chained, tail_hash, verify_chain
from services.governance.path_safety import (
    is_safe_path_component,
    require_safe_path_component,
)

logger = logging.getLogger("services.governance.black_box")

# G4: every export bundle and terminal ``task_completed`` event self-identifies
# with this version so the (currently three) coexisting ``task_completed`` shapes
# in a single dataset are no longer ambiguous. Bump when the bundle/terminal-event
# shape changes; consumers branch on it instead of guessing from present keys.
BUNDLE_SCHEMA_VERSION = "2"

# Phase boundary events use a separate schema version so phase-event evolution does
# not force unrelated bundle consumer bumps (DecisionRecord / phase_decisions unchanged).
PHASE_LOG_SCHEMA_VERSION = "1"

# G6 residual: the terminal outcome signals dashboards care about live inside the
# ``task_completed`` event ``details``. Lifting them into a top-level ``summary``
# block lets a consumer key off the result without walking ``events[]`` (and
# without knowing which of the rich / rejected / budget shapes applies). Fields
# absent from a given shape (e.g. ``goal_met`` on a rejected path) surface as
# ``None`` rather than being omitted, so the summary contract is shape-stable.
SUMMARY_FIELDS = ("outcome", "goal_met", "criteria_met", "termination_reason", "reason")


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
    # Phase 1 memory wiring (docs/plans/memory_layer_wiring.plan.md): the two
    # memory-activity carriers. They ENRICH the Recording pillar — they are NOT
    # added to default_spec() in trust/governance_carrier_spec.py as per-phase
    # requirements. Memory is flag-gated and absent on most runs, so requiring
    # them would false-positive the inline carrier gate on every non-memory run
    # (the GG-4 class the resumed-Identity exemption guards against). Recall runs
    # in route_node → PH_ROUTING (keeps model_selected); store in the completion
    # path → PH_COMPLETION (keeps eval.goal_judge). Being non-required, these
    # members leave ALL_PHASE_VALUES and the requirement tuples untouched, so the
    # drift-guard (tests/trust/test_governance_carrier_spec.py) stays green with
    # no SPEC_VERSION bump. details carry user_id/key/count — never content.
    MEMORY_RECALLED = "memory_recalled"
    MEMORY_STORED = "memory_stored"
    # Phase B (chat-persistence reject): soft-suppress / un-suppress on the CRUD
    # PATCH route. Enrichment only (not a per-phase requirement) — same contract
    # as the other memory carriers. details carry user_id/key/suppressed — never
    # content.
    MEMORY_SUPPRESSED = "memory_suppressed"
    # Hermes / memory-os adoption A1 (docs/research/memory/hermes_adoptions_design.md):
    # the bounded-budget consolidation carrier. Like the two above it is
    # ENRICHMENT, not a per-phase requirement — consolidation is a write-side
    # background decision that DELETES memory, so leaving an honest carrier keeps
    # the Validation pillar truthful (a silent eviction would be a swallowed
    # failure). Non-required → ALL_PHASE_VALUES / requirement tuples untouched →
    # drift-guard stays green with no SPEC_VERSION bump. details carry
    # user_id/type/kept/evicted/deduped — never content.
    MEMORY_CONSOLIDATED = "memory_consolidated"
    # C1 §7 context-compaction dual carrier (docs/plans/c1_message_compaction.design.md):
    # the Recording-pillar event for a message-history fold (RemoveMessage rewrite
    # of state["messages"]). Joined to the Reasoning Decision by ``decision_id``
    # (the MODEL_SELECTED dual-sink idiom). ENRICHMENT — NOT added to
    # default_spec()/requirements tuples in trust/governance_carrier_spec.py;
    # compaction is conditional (most turns don't fold), and a per-phase required
    # rule would false-alarm on every non-compaction turn. details carry counts +
    # constraint_floor_hash + floor_exceeded/context_exhausted flags — NEVER the
    # dropped text or constraint strings (the _CompactionOutcome Protocol in
    # services/governance/context_compaction_carrier.py is what makes this
    # structural, not a convention).
    CONTEXT_COMPACTED = "context_compacted"


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

    def _trace_file(self, workflow_id: str) -> Path:
        """Trace path for a workflow; raises ``ValueError`` on an unsafe id."""
        require_safe_path_component(workflow_id, "workflow_id")
        return self._storage_dir / workflow_id / "trace.jsonl"

    def _existing_trace_file(self, workflow_id: str) -> Path:
        """Trace path for reads; an unsafe or unknown id is ``KeyError``."""
        if not is_safe_path_component(workflow_id):
            raise KeyError(f"No trace found for workflow_id={workflow_id!r}")
        trace_file = self._storage_dir / workflow_id / "trace.jsonl"
        if not trace_file.exists():
            raise KeyError(f"No trace found for workflow_id={workflow_id!r}")
        return trace_file

    def _prev_hash(self, trace_file: Path) -> str:
        """Previous chain hash from the file tail, never a memory cache.

        Multiple recorder instances legitimately interleave on one trace
        (the graph's instance + the middleware edit endpoint appending
        PARAMETER_CHANGED mid-run); a per-instance cache would fork the
        chain at the first cross-instance write.
        """
        return tail_hash(trace_file)

    def record(self, event: TraceEvent) -> None:
        trace_file = self._trace_file(event.workflow_id)
        # Tail read + append + anchor update are one locked critical section
        # (services/governance/hash_chain.py), so interleaved recorder
        # instances and processes extend a single chain.
        append_chained(trace_file, event.model_dump(mode="json"))

        logger.info(
            "Recorded %s for workflow %s",
            event.event_type.value,
            event.workflow_id,
        )

    def export(self, workflow_id: str) -> dict:
        """Export a workflow's trace as a structured JSON bundle with integrity verification.

        Returns a dict containing events, metadata, and a verification status
        indicating whether the trace is intact.  When the chain is broken,
        the dict also exposes the FIRST broken event's id along with the
        expected and actual hashes so explainability surfaces can report the
        break location explicitly without re-hashing.

        ``hash_chain_valid`` is ``False`` when the chain is broken, when a
        line is unparseable (``corrupt_line_count``), or when the trace holds
        fewer events than were recorded (``truncated``).
        """
        trace_file = self._existing_trace_file(workflow_id)
        report = verify_chain(trace_file)
        events = report.rows

        broken_at_event_id: str | None = None
        if report.broken_at_index is not None:
            broken_at_event_id = events[report.broken_at_index].get(
                "event_id", "unknown"
            )
        if not report.intact:
            logger.warning(
                "Trace integrity failed for workflow %s "
                "(broken_at=%s, corrupt_lines=%d, truncated=%s)",
                workflow_id,
                broken_at_event_id,
                report.corrupt_line_count,
                report.truncated,
            )

        return {
            "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
            "workflow_id": workflow_id,
            "event_count": len(events),
            "events": events,
            "hash_chain_valid": report.intact,
            "broken_at_event_id": broken_at_event_id,
            "broken_expected_hash": report.broken_expected_hash,
            "broken_actual_hash": report.broken_actual_hash,
            "corrupt_line_count": report.corrupt_line_count,
            "truncated": report.truncated,
            "exported_at": datetime.now(UTC).isoformat() if events else None,
        }

    def replay(self, workflow_id: str) -> list[TraceEvent]:
        """Reconstruct the event timeline for a workflow in chronological order.

        Unparseable lines (torn writes) are skipped; ``export`` reports them.
        """
        trace_file = self._existing_trace_file(workflow_id)

        events = [
            TraceEvent.model_validate(row) for row in verify_chain(trace_file).rows
        ]
        events.sort(key=lambda e: e.timestamp)
        return events

    @staticmethod
    def _summarize_outcome(events: list[dict]) -> dict:
        """G6 residual: lift the terminal outcome signals into a flat summary.

        Walks the events for the (chronologically last) ``task_completed`` and
        copies the dashboard-relevant fields out of its ``details``. Returns a
        shape-stable dict: every field in ``SUMMARY_FIELDS`` is always present
        (``None`` when the terminal event's shape does not carry it), and
        ``task_completed_present`` reports whether a terminal event existed at
        all — a trace that never completed (broken/aborted) is itself a signal.
        """
        summary: dict[str, Any] = {field: None for field in SUMMARY_FIELDS}
        summary["task_completed_present"] = False

        for event in events:
            if event.get("event_type") != EventType.TASK_COMPLETED.value:
                continue
            details = event.get("details") or {}
            summary["task_completed_present"] = True
            for field in SUMMARY_FIELDS:
                summary[field] = details.get(field)

        return summary

    def export_for_compliance(
        self,
        workflow_id: str,
        agent_facts_registry: Any = None,
        phase_logger: Any = None,
    ) -> dict:
        """Story 6.3: produce a compliance-ready bundle joining all governance artifacts."""
        bundle = self.export(workflow_id)

        # G6 residual: surface the terminal outcome at the top level so
        # dashboards key off ``bundle["summary"]`` instead of scanning events[].
        bundle["summary"] = self._summarize_outcome(bundle.get("events", []))

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
                            identity_cards[aid] = agent_facts_registry.get(
                                aid
                            ).model_dump(mode="json")
                        except KeyError:
                            identity_cards[aid] = None
                        audit_trails[aid] = [
                            entry.model_dump(mode="json")
                            for entry in agent_facts_registry.audit_trail(aid)
                        ]
                bundle["identity_cards"] = identity_cards
                bundle["audit_trails"] = audit_trails
            except Exception as exc:
                logger.warning(
                    "Failed to include AgentFacts in compliance bundle: %s", exc
                )

        bundle["phase_log_schema_version"] = PHASE_LOG_SCHEMA_VERSION

        if phase_logger is not None:
            try:
                bundle["phase_decisions"] = phase_logger.export_workflow_log(
                    workflow_id
                )
            except Exception as exc:
                logger.warning(
                    "Failed to include phase decisions in compliance bundle: %s", exc
                )
            try:
                bundle["phase_decisions_integrity"] = phase_logger.verify_decision_log(
                    workflow_id
                )
            except Exception as exc:
                logger.warning(
                    "Failed to verify phase decisions for compliance bundle: %s", exc
                )
            try:
                bundle["phase_events"] = phase_logger.export_phase_events(workflow_id)
            except Exception as exc:
                logger.warning(
                    "Failed to include phase events in compliance bundle: %s", exc
                )

        bundle["bundle_type"] = "compliance_audit"
        return bundle
