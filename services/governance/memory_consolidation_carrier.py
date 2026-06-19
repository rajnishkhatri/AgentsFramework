"""Shared emitter for the ``MEMORY_CONSOLIDATED`` Validation-pillar carrier.

A1 (Hermes bounded-budget consolidation) put eviction in
``LongTermMemoryService.store()`` so EVERY writer is bounded, and has it RETURN a
``ConsolidationOutcome``. Whoever owns the write must turn that outcome into a
carrier, or the eviction is silent — exactly the swallowed-failure the Validation
pillar forbids. Two writers exist:

* the autocapture write-back path (``services/memory_autocapture``), and
* the CRUD ``create_memory`` panel route (``middleware/app_prod`` +
  ``agent_ui_adapter/server``).

Both call this single emitter so the carrier shape (counts only — NEVER content)
has one source of truth. Framework-clean (I-4): depends only on the governance
recorder and a duck-typed outcome. See
``docs/research/memory/hermes_adoptions_design.md`` §10.5 (P1 #6a).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent


class _Outcome(Protocol):
    """The slice of ``ConsolidationOutcome`` the carrier reports — counts only."""

    kept: int
    evicted: int
    deduped: int


def emit_consolidation_carrier(
    black_box: BlackBoxRecorder,
    *,
    workflow_id: str,
    user_id: str,
    mem_type: str,
    outcome: _Outcome,
) -> None:
    """Record one ``MEMORY_CONSOLIDATED`` carrier (counts only — never content).

    ``workflow_id`` is the trace this eviction belongs to: the run trace_id for
    the autocapture path, or a freshly-minted per-action id for a CRUD/panel
    write. ``details`` carries ``user_id``/``type``/``kept``/``evicted``/
    ``deduped`` — the same content-free shape the recall/store carriers use.
    """
    details: dict[str, Any] = {
        "user_id": user_id,
        "type": mem_type,
        "kept": outcome.kept,
        "evicted": outcome.evicted,
        "deduped": outcome.deduped,
    }
    black_box.record(
        TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.MEMORY_CONSOLIDATED,
            timestamp=datetime.now(UTC),
            details=details,
        )
    )
