"""Pure domain → AG-UI shape mapping.

Per AGENT_UI_ADAPTER_PLAN.md §4.3 Option B and rules R5-R7:
- R5: pure data-shape mapping only
- R6: no I/O, no LLM, no policy decisions, no auth checks
- R7: imports from trust/ + agent_ui_adapter.wire/ only -- NOT from services/

Every emitted AG-UI event carries the originating ``trace_id`` in
``raw_event["trace_id"]`` so cross-layer correlation survives the AG-UI hop.
The translator never invents data not present in the input -- if the input
domain event lacks a trace_id, ``ValueError`` is raised (no silent omission).
"""

from __future__ import annotations

from agent_ui_adapter.wire.ag_ui_events import (
    AGUIEvent,
    Custom,
    RunError,
    RunFinished,
    RunStarted,
    StateDelta,
    StateSnapshot,
    TextMessageContent,
    TextMessageEnd,
    TextMessageStart,
    ToolCallArgs,
    ToolCallEnd,
    ToolCallStart,
    ToolResult,
)
from agent_ui_adapter.wire.domain_events import (
    DomainEventBase,
    LLMMessageEnded,
    LLMMessageStarted,
    ReasoningSummarized,
    LLMTokenEmitted,
    RunFinishedDomain,
    RunStartedDomain,
    StateMutated,
    StepProgressed,
    TaskUnderstood,
    ToolCallEnded,
    ToolCallStarted,
    ToolResultReceived,
)


def _raw(trace_id: str) -> dict:
    """Build the raw_event sidecar carrying the trace_id (plan §4.3)."""
    return {"trace_id": trace_id}


def to_ag_ui(event: DomainEventBase) -> list[AGUIEvent]:
    """Map one canonical domain event to one or more AG-UI events.

    Per plan §4.3 Option B: every emitted event carries the originating
    ``trace_id`` in ``raw_event["trace_id"]``.

    Raises:
        TypeError: ``event`` is not a known ``DomainEvent`` subclass.
        ValueError: ``event.trace_id`` is missing or empty (no silent omission)
            or ``StateMutated`` carries neither ``snapshot`` nor ``delta``.
    """
    if not isinstance(event, DomainEventBase):
        raise TypeError(
            f"to_ag_ui() expects a DomainEvent; got {type(event).__name__}"
        )

    trace_id = event.trace_id
    if not trace_id:
        raise ValueError(
            "Domain event missing trace_id; refusing to emit AG-UI events "
            "without correlation id (plan §4.3 Option B)"
        )

    raw = _raw(trace_id)

    if isinstance(event, RunStartedDomain):
        return [
            RunStarted(
                run_id=event.run_id,
                thread_id=event.thread_id,
                raw_event=raw,
            )
        ]

    if isinstance(event, RunFinishedDomain):
        if event.error:
            return [
                RunError(
                    run_id=event.run_id,
                    thread_id=event.thread_id,
                    message=event.error,
                    code=None,
                    raw_event=raw,
                )
            ]
        return [
            RunFinished(
                run_id=event.run_id,
                thread_id=event.thread_id,
                raw_event=raw,
            )
        ]

    if isinstance(event, LLMMessageStarted):
        return [
            TextMessageStart(
                message_id=event.message_id,
                role="assistant",
                raw_event=raw,
            )
        ]

    if isinstance(event, LLMTokenEmitted):
        return [
            TextMessageContent(
                message_id=event.message_id,
                delta=event.delta,
                raw_event=raw,
            )
        ]

    if isinstance(event, LLMMessageEnded):
        return [
            TextMessageEnd(
                message_id=event.message_id,
                raw_event=raw,
            )
        ]

    if isinstance(event, ToolCallStarted):
        return [
            ToolCallStart(
                tool_call_id=event.tool_call_id,
                tool_call_name=event.tool_name,
                parent_message_id=None,
                raw_event=raw,
            ),
            ToolCallArgs(
                tool_call_id=event.tool_call_id,
                delta=event.args_json,
                raw_event=raw,
            ),
        ]

    if isinstance(event, ToolCallEnded):
        return [
            ToolCallEnd(
                tool_call_id=event.tool_call_id,
                raw_event=raw,
            )
        ]

    if isinstance(event, ToolResultReceived):
        return [
            ToolResult(
                tool_call_id=event.tool_call_id,
                content=event.result,
                role="tool",
                raw_event=raw,
            )
        ]

    if isinstance(event, StateMutated):
        if event.snapshot is not None:
            return [StateSnapshot(snapshot=event.snapshot, raw_event=raw)]
        if event.delta is not None:
            return [StateDelta(delta=event.delta, raw_event=raw)]
        raise ValueError(
            "StateMutated must carry either 'snapshot' or 'delta'"
        )

    if isinstance(event, StepProgressed):
        # Rides the Custom 'step_meter' channel: the frontend translator
        # special-cases it into step_progress with the real count. The wire
        # StepStarted shape carries no count (the frontend renders it as
        # step 0), so it is deliberately not used for the meter.
        return [
            Custom(
                name="step_meter",
                value={"step": event.step_count, "step_name": event.step_name},
                raw_event=raw,
            )
        ]

    if isinstance(event, ReasoningSummarized):
        # F10 Tier-2: rides Custom 'reasoning_summary' (zero wire change);
        # the frontend translator special-cases the name like step_meter.
        return [
            Custom(
                name="reasoning_summary",
                value={"text": event.text},
                raw_event=raw,
            )
        ]

    if isinstance(event, TaskUnderstood):
        # task_understanding plan Phase 3: rides Custom 'task_understanding'
        # (zero wire change); the frontend translator special-cases the name.
        return [
            Custom(
                name="task_understanding",
                value={
                    "restated_intent": event.restated_intent,
                    "success_conditions": list(event.success_conditions),
                    "confidence": event.confidence,
                    "source": event.source,
                },
                raw_event=raw,
            )
        ]

    raise TypeError(
        f"to_ag_ui() has no mapping for DomainEvent subclass "
        f"{type(event).__name__}"
    )


__all__ = ["to_ag_ui"]
