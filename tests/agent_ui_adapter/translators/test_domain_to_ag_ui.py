"""US-4.1 — pure shape mapping from DomainEvent → list[AGUIEvent].

Failure paths first per AGENTS.md TAP-4: rejection tests precede acceptance
tests. One acceptance test per row of the mapping table in the S4 spec.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from agent_ui_adapter.translators.domain_to_ag_ui import to_ag_ui
from agent_ui_adapter.wire.ag_ui_events import (
    EventType,
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


TRACE_ID = "trace-abc-123"


# ── Failure paths first (TAP-4) ───────────────────────────────────────


class _NotADomainEvent(BaseModel):
    """A pydantic model that is *not* a DomainEvent subclass."""

    trace_id: str = "x"


def test_to_ag_ui_rejects_unknown_event_type() -> None:
    """Pure dispatch: any non-DomainEvent input raises TypeError."""
    with pytest.raises(TypeError, match="DomainEvent"):
        to_ag_ui(_NotADomainEvent())  # type: ignore[arg-type]


def test_to_ag_ui_raises_when_trace_id_empty() -> None:
    """Empty trace_id is a contract violation -- never silently omitted."""
    event = RunStartedDomain(trace_id="", run_id="r1", thread_id="t1")
    with pytest.raises(ValueError, match="trace_id"):
        to_ag_ui(event)


def test_to_ag_ui_raises_when_state_mutated_has_no_payload() -> None:
    """StateMutated with neither snapshot nor delta is malformed."""
    event = StateMutated(trace_id=TRACE_ID)
    with pytest.raises(ValueError, match="snapshot.*delta"):
        to_ag_ui(event)


# ── Per-row mapping acceptance tests ──────────────────────────────────


def test_run_started_maps_to_run_started() -> None:
    out = to_ag_ui(
        RunStartedDomain(trace_id=TRACE_ID, run_id="r1", thread_id="t1")
    )
    assert len(out) == 1
    assert isinstance(out[0], RunStarted)
    assert out[0].type == EventType.RUN_STARTED
    assert out[0].run_id == "r1"
    assert out[0].thread_id == "t1"
    assert out[0].raw_event == {"trace_id": TRACE_ID}


def test_run_finished_no_error_maps_to_run_finished() -> None:
    out = to_ag_ui(
        RunFinishedDomain(trace_id=TRACE_ID, run_id="r1", thread_id="t1")
    )
    assert len(out) == 1
    assert isinstance(out[0], RunFinished)
    assert out[0].run_id == "r1"
    assert out[0].thread_id == "t1"


def test_run_finished_with_error_maps_to_run_error() -> None:
    out = to_ag_ui(
        RunFinishedDomain(
            trace_id=TRACE_ID,
            run_id="r1",
            thread_id="t1",
            error="boom",
        )
    )
    assert len(out) == 1
    assert isinstance(out[0], RunError)
    assert out[0].message == "boom"
    assert out[0].code is None
    assert out[0].run_id == "r1"
    assert out[0].thread_id == "t1"


def test_llm_message_started_maps_to_text_message_start() -> None:
    out = to_ag_ui(LLMMessageStarted(trace_id=TRACE_ID, message_id="m1"))
    assert len(out) == 1
    assert isinstance(out[0], TextMessageStart)
    assert out[0].message_id == "m1"
    assert out[0].role == "assistant"


def test_llm_token_emitted_maps_to_text_message_content() -> None:
    out = to_ag_ui(
        LLMTokenEmitted(trace_id=TRACE_ID, message_id="m1", delta="hello")
    )
    assert len(out) == 1
    assert isinstance(out[0], TextMessageContent)
    assert out[0].message_id == "m1"
    assert out[0].delta == "hello"


def test_llm_message_ended_maps_to_text_message_end() -> None:
    out = to_ag_ui(LLMMessageEnded(trace_id=TRACE_ID, message_id="m1"))
    assert len(out) == 1
    assert isinstance(out[0], TextMessageEnd)
    assert out[0].message_id == "m1"


def test_tool_call_started_maps_to_two_events() -> None:
    out = to_ag_ui(
        ToolCallStarted(
            trace_id=TRACE_ID,
            tool_call_id="tc1",
            tool_name="grep",
            args_json='{"pattern":"foo"}',
        )
    )
    assert len(out) == 2
    assert isinstance(out[0], ToolCallStart)
    assert isinstance(out[1], ToolCallArgs)
    assert out[0].tool_call_id == "tc1"
    assert out[0].tool_call_name == "grep"
    assert out[0].parent_message_id is None
    assert out[1].tool_call_id == "tc1"
    assert out[1].delta == '{"pattern":"foo"}'


def test_tool_call_ended_maps_to_tool_call_end() -> None:
    out = to_ag_ui(ToolCallEnded(trace_id=TRACE_ID, tool_call_id="tc1"))
    assert len(out) == 1
    assert isinstance(out[0], ToolCallEnd)
    assert out[0].tool_call_id == "tc1"


def test_tool_result_received_maps_to_tool_result() -> None:
    out = to_ag_ui(
        ToolResultReceived(
            trace_id=TRACE_ID,
            tool_call_id="tc1",
            result="42",
        )
    )
    assert len(out) == 1
    assert isinstance(out[0], ToolResult)
    assert out[0].tool_call_id == "tc1"
    assert out[0].content == "42"
    assert out[0].role == "tool"


def test_state_mutated_with_snapshot_maps_to_state_snapshot() -> None:
    out = to_ag_ui(
        StateMutated(trace_id=TRACE_ID, snapshot={"k": "v"})
    )
    assert len(out) == 1
    assert isinstance(out[0], StateSnapshot)
    assert out[0].snapshot == {"k": "v"}


def test_state_mutated_with_delta_maps_to_state_delta() -> None:
    out = to_ag_ui(
        StateMutated(
            trace_id=TRACE_ID,
            delta=[{"op": "add", "path": "/k", "value": "v"}],
        )
    )
    assert len(out) == 1
    assert isinstance(out[0], StateDelta)
    assert out[0].delta == [{"op": "add", "path": "/k", "value": "v"}]


def test_state_mutated_with_both_prefers_snapshot() -> None:
    """Spec: when both fields set, prefer snapshot and emit only one event."""
    out = to_ag_ui(
        StateMutated(
            trace_id=TRACE_ID,
            snapshot={"k": "v"},
            delta=[{"op": "add", "path": "/k", "value": "v"}],
        )
    )
    assert len(out) == 1
    assert isinstance(out[0], StateSnapshot)
