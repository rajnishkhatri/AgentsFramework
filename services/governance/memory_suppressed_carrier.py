"""Shared emitter for the ``MEMORY_SUPPRESSED`` Recording-pillar carrier.

Phase B (chat-persistence reject = soft-suppress): the PATCH handler must leave
an honest carrier so offline trace analysis can score C3/C4 without relying on
DOM-only evidence. Mirrors ``memory_consolidation_carrier`` — one source of
truth for the carrier shape (user_id/key/suppressed flag — NEVER content).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent


def emit_suppressed_carrier(
    black_box: BlackBoxRecorder,
    *,
    workflow_id: str,
    user_id: str,
    key: str,
    suppressed: bool,
) -> None:
    """Record one ``MEMORY_SUPPRESSED`` carrier (metadata only — never content).

    ``workflow_id`` is a per-action trace id (fresh uuid for CRUD/panel writes).
    ``details`` carries ``user_id``/``key``/``suppressed`` — the same
    content-free shape the recall/store carriers use.
    """
    black_box.record(
        TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.MEMORY_SUPPRESSED,
            timestamp=datetime.now(UTC),
            details={
                "user_id": user_id,
                "key": key,
                "suppressed": suppressed,
            },
        )
    )
