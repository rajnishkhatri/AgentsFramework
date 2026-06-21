"""Shared emitter for the ``CONTEXT_COMPACTED`` Recording-pillar carrier.

C1 (deterministic message-history compaction, see
`docs/plans/c1_message_compaction.design.md` §7) silently rewrites
``state["messages"]`` via ``RemoveMessage(REMOVE_ALL_MESSAGES)`` at the
WRITE seam (`react_loop.evaluate_node` §5.1). Without a carrier, that fold
is an invisible mutation of the model's context — the worst-class
governance defect (a fact with zero carriers, CRITICAL → NON-COMPLIANT
in the four-pillar audit).

This module is the single source of truth for the fold's Recording carrier.
The contract:

* counts + hash + flags ONLY — **never** dropped text or constraint
  strings.  The ``_CompactionOutcome`` Protocol below structurally
  forbids string fields except ``constraint_floor_hash`` (a SHA-256
  digest, not free text);
* joined to the Reasoning Decision (``PhaseLogger.log_decision``) by
  ``decision_id`` (mirrors the ``MODEL_SELECTED`` dual-sink pattern at
  `react_loop.py:1450-1461`);
* enrichment — the new ``EventType.CONTEXT_COMPACTED`` member is NOT
  added to ``trust/governance_carrier_spec.default_spec()`` (most turns
  don't fold; a per-phase required rule would false-alarm on every
  no-compaction turn, the GG-4 class).

Framework-clean (I-4): depends only on the governance recorder and a
duck-typed outcome. Cloned in shape from
``services/governance/memory_consolidation_carrier.py`` — the same
content-free posture the four memory carriers already use.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent


class _CompactionOutcome(Protocol):
    """The slice of a fold's outcome that the Recording carrier reports.

    Every field is a scalar (int / bool) or a hex digest (``str``), so
    passing a content-bearing outcome through this Protocol is a structural
    type error — not just a convention. ``constraint_floor_hash`` is the
    ONLY string field, and it is a SHA-256 digest of the rendered floor
    block (see §7.3): an in-process auditor with the floor strings can
    re-derive it; a reader of the curated trace cannot.
    """

    # cost (the "what happened")
    tokens_before: int
    tokens_after: int
    turns_folded: int
    observations_cleared: int
    keep_last_k: int
    # B2 floor integrity (content-free)
    pinned_kept: int
    must_not_count: int
    constraint_floor_hash: str  # SHA-256 hex digest — the only allowed string
    floor_reinjected: bool
    floor_exceeded: bool  # §5.3 fail-loud (compaction declined)
    context_exhausted: bool  # §5.4 terminal halt at the hard window


def emit_compaction_carrier(
    black_box: BlackBoxRecorder,
    *,
    workflow_id: str,
    step: int,
    decision_id: str | None,
    outcome: _CompactionOutcome,
) -> None:
    """Record one ``CONTEXT_COMPACTED`` carrier — counts + hash + flags only.

    ``workflow_id`` is the trace this fold belongs to (the same id the
    Reasoning ``PhaseLogger.log_decision`` call uses, so the two sinks
    join on it). ``decision_id`` is the per-decision uuid the
    ``PhaseLogger`` returns after stamping the Decision — passing it
    through lets a trace reader answer *both* "what happened" (this
    carrier) and "why" (the joined Decision) without re-derivation.

    The ``outcome`` Protocol structurally forbids dropped-text fields,
    so the ``details`` payload below cannot accidentally smuggle a
    constraint string onto the wire. The accompanying content-free
    tests pin the invariant against future refactors.
    """
    details: dict[str, Any] = {
        "decision_id": decision_id,
        # cost (the "what happened")
        "tokens_before": outcome.tokens_before,
        "tokens_after": outcome.tokens_after,
        "turns_folded": outcome.turns_folded,
        "observations_cleared": outcome.observations_cleared,
        "keep_last_k": outcome.keep_last_k,
        # B2 floor integrity (content-free)
        "pinned_kept": outcome.pinned_kept,
        "must_not_count": outcome.must_not_count,
        "constraint_floor_hash": outcome.constraint_floor_hash,
        "floor_reinjected": outcome.floor_reinjected,
        "floor_exceeded": outcome.floor_exceeded,
        "context_exhausted": outcome.context_exhausted,
    }
    black_box.record(
        TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.CONTEXT_COMPACTED,
            timestamp=datetime.now(UTC),
            step=step,
            details=details,
        )
    )
