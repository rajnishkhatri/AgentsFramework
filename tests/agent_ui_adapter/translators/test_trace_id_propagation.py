"""US-4.3 — trace_id propagation across the AG-UI hop (plan §4.3 Option B).

Owns the real assertions for architecture test T9.
"""

from __future__ import annotations

import pytest

from agent_ui_adapter.translators.domain_to_ag_ui import to_ag_ui
from agent_ui_adapter.wire.domain_events import (
    DomainEventBase,
    LLMMessageEnded,
    LLMMessageStarted,
    LLMTokenEmitted,
    RunFinishedDomain,
    RunStartedDomain,
    StateMutated,
    ToolCallEnded,
    ToolCallStarted,
    ToolResultReceived,
)


TRACE_ID = "trace-propagation-7"


def _all_domain_events() -> list[DomainEventBase]:
    """One representative instance per concrete DomainEvent subclass."""
    return [
        RunStartedDomain(trace_id=TRACE_ID, run_id="r1", thread_id="t1"),
        RunFinishedDomain(trace_id=TRACE_ID, run_id="r1", thread_id="t1"),
        RunFinishedDomain(
            trace_id=TRACE_ID, run_id="r1", thread_id="t1", error="boom"
        ),
        LLMMessageStarted(trace_id=TRACE_ID, message_id="m1"),
        LLMTokenEmitted(trace_id=TRACE_ID, message_id="m1", delta="x"),
        LLMMessageEnded(trace_id=TRACE_ID, message_id="m1"),
        ToolCallStarted(
            trace_id=TRACE_ID,
            tool_call_id="tc1",
            tool_name="grep",
            args_json="{}",
        ),
        ToolCallEnded(trace_id=TRACE_ID, tool_call_id="tc1"),
        ToolResultReceived(
            trace_id=TRACE_ID, tool_call_id="tc1", result="ok"
        ),
        StateMutated(trace_id=TRACE_ID, snapshot={"k": "v"}),
        StateMutated(
            trace_id=TRACE_ID,
            delta=[{"op": "add", "path": "/k", "value": "v"}],
        ),
    ]


def test_every_emitted_ag_ui_event_carries_trace_id() -> None:
    """T9: for every DomainEvent variant, every emitted AG-UI event has
    ``raw_event['trace_id']`` equal to the originating trace_id."""
    for event in _all_domain_events():
        outputs = to_ag_ui(event)
        assert outputs, f"no outputs for {type(event).__name__}"
        for out in outputs:
            assert out.raw_event is not None, (
                f"{type(out).__name__} missing raw_event "
                f"(source={type(event).__name__})"
            )
            assert out.raw_event.get("trace_id") == TRACE_ID, (
                f"{type(out).__name__} carries raw_event["
                f"'trace_id']={out.raw_event.get('trace_id')!r} "
                f"(source={type(event).__name__})"
            )


def test_to_ag_ui_rejects_event_with_empty_trace_id() -> None:
    event = RunStartedDomain(trace_id="", run_id="r1", thread_id="t1")
    with pytest.raises(ValueError, match="trace_id"):
        to_ag_ui(event)
