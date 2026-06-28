"""Soft-gate understanding edit endpoint (task_understanding plan Phase 4).

POST /run/understanding/{thread_id} — the card's edit round-trip:
authenticated user pauses the run (existing stop semantics), corrects the
restated intent / success checklist, and this endpoint writes the
``user_edited`` artifact to the thread checkpoint via the runtime adapter.
The client resumes by re-invoking ``/run/stream`` with the same thread_id;
the terminal judge then scores against the corrected conditions.

Governance (plan §4.7): every accepted edit is recorded as a
``PARAMETER_CHANGED`` TraceEvent in the run's hash-chained trace.jsonl —
old/new content HASHES (compact + tamper-evident), ``reason="user_edit"``,
and the authenticated user_id. The verdict basis must never change
unrecorded. Recording uses its own ``BlackBoxRecorder`` instance; chain
continuity across instances is guaranteed by the recorder's file-tail hash
recovery.

Layering (M1): imports ``agent_ui_adapter/wire`` shapes and ``services`` —
never ``components/`` or ``orchestration/``. The runtime adapter is injected
as a callable so this module stays SDK-free and unit-testable.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Protocol

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import ValidationError

from agent_ui_adapter.wire.agent_protocol import TaskUnderstandingEditRequest
from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent

logger = logging.getLogger("middleware.understanding_edit")

__all__ = ["register_understanding_edit_route"]


class _RuntimeLike(Protocol):
    async def update_task_understanding(
        self,
        *,
        thread_id: str,
        trace_id: str,
        restated_intent: str,
        success_conditions: list[str],
    ) -> tuple[dict, dict]: ...


def _conditions_hash(artifact: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "restated_intent": artifact.get("restated_intent", ""),
            "success_conditions": artifact.get("success_conditions", []),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def register_understanding_edit_route(
    app: FastAPI,
    *,
    verify_bearer: Callable[[str | None], str],
    get_runtime: Callable[[], _RuntimeLike],
    black_box_dir: Path,
) -> None:
    """Mount the edit route on ``app``.

    Args:
        verify_bearer: maps the Authorization header to the authenticated
            subject (WorkOS user id); raises ``HTTPException(401)`` otherwise.
        get_runtime: returns the live runtime adapter (resolved per-request —
            ``app.state.runtime`` is set in the lifespan, after route
            registration).
        black_box_dir: the graph's ``black_box_recordings`` storage dir.
    """

    @app.post("/run/understanding/{thread_id}")
    async def edit_understanding(
        thread_id: str,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        user_id = verify_bearer(authorization)

        body = await request.json()
        try:
            edit = TaskUnderstandingEditRequest.model_validate(body)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422, detail=json.loads(exc.json())
            ) from None

        runtime = get_runtime()
        try:
            old, new = await runtime.update_task_understanding(
                thread_id=thread_id,
                trace_id=edit.trace_id,
                restated_intent=edit.restated_intent,
                success_conditions=list(edit.success_conditions),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

        recorder = BlackBoxRecorder(storage_dir=black_box_dir)
        recorder.record(
            TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=edit.trace_id,
                event_type=EventType.PARAMETER_CHANGED,
                timestamp=datetime.now(UTC),
                details={
                    "parameter": "success_conditions",
                    "old_hash": _conditions_hash(old),
                    "new_hash": _conditions_hash(new),
                    "old_source": str(old.get("source", "")),
                    "new_source": "user_edited",
                    "condition_count": len(new.get("success_conditions", [])),
                    "reason": "user_edit",
                    "user_id": user_id,
                },
            )
        )
        logger.info(
            "task_understanding edited trace=%s thread=%s user=%s",
            edit.trace_id,
            thread_id,
            user_id,
        )
        return {
            "ok": True,
            "trace_id": edit.trace_id,
            "thread_id": thread_id,
            "source": "user_edited",
            "success_conditions": new.get("success_conditions", []),
            "restated_intent": new.get("restated_intent", ""),
        }
