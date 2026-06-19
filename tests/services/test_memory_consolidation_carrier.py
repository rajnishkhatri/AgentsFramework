"""L1 contract tests for the shared MEMORY_CONSOLIDATED carrier emitter.

Failure-paths-first: the privacy invariant (the carrier carries counts only —
NEVER memory content) is asserted before the happy-path shape. This emitter is
the single source of truth for the carrier used by BOTH the autocapture path and
the CRUD ``create_memory`` path (P1 #6a — a panel/CRUD eviction must not be a
silent Validation-pillar failure). See
``docs/research/memory/hermes_adoptions_design.md`` §10.5.
"""

from __future__ import annotations

from services.governance.black_box import BlackBoxRecorder, EventType
from services.governance.memory_consolidation_carrier import (
    emit_consolidation_carrier,
)
from services.long_term_memory import ConsolidationOutcome


class _CapturingRecorder(BlackBoxRecorder):
    """A recorder that captures TraceEvents in memory instead of on disk
    (Pattern 6 mock — keeps the test free of filesystem + integrity-chain
    concerns; we assert the event shape, not the storage)."""

    def __init__(self) -> None:  # noqa: D107 - test double
        self.events: list = []

    def record(self, event) -> None:  # type: ignore[override]
        self.events.append(event)


class TestPrivacyInvariant:
    def test_carrier_contains_only_counts_never_content(self) -> None:
        rec = _CapturingRecorder()
        outcome = ConsolidationOutcome(kept=5, evicted=2, deduped=1)
        emit_consolidation_carrier(
            rec,
            workflow_id="wf-1",
            user_id="user-1",
            mem_type="semantic",
            outcome=outcome,
        )
        assert len(rec.events) == 1
        details = rec.events[0].details
        # ONLY these keys — no payload/text/content of any kind.
        assert set(details) == {"user_id", "type", "kept", "evicted", "deduped"}
        # Belt-and-suspenders: no value smuggles free text.
        assert details["user_id"] == "user-1"
        assert details["type"] == "semantic"
        assert details["kept"] == 5
        assert details["evicted"] == 2
        assert details["deduped"] == 1


class TestCarrierShape:
    def test_event_type_is_memory_consolidated(self) -> None:
        rec = _CapturingRecorder()
        emit_consolidation_carrier(
            rec,
            workflow_id="wf-2",
            user_id="u",
            mem_type="episodic",
            outcome=ConsolidationOutcome(kept=1, evicted=0, deduped=0),
        )
        assert rec.events[0].event_type is EventType.MEMORY_CONSOLIDATED
        assert rec.events[0].workflow_id == "wf-2"

    def test_each_call_emits_one_event_with_unique_id(self) -> None:
        rec = _CapturingRecorder()
        for t in ("semantic", "episodic"):
            emit_consolidation_carrier(
                rec,
                workflow_id="wf-3",
                user_id="u",
                mem_type=t,
                outcome=ConsolidationOutcome(kept=1, evicted=1, deduped=0),
            )
        assert len(rec.events) == 2
        assert rec.events[0].event_id != rec.events[1].event_id
