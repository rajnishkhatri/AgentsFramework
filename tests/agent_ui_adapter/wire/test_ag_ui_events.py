"""L1 Deterministic: Tests for agent_ui_adapter.wire.ag_ui_events.

Per AGENT_UI_ADAPTER_SPRINTS.md US-2.1.
TDD Protocol A. For each of the 17 AG-UI events:
- valid construction (acceptance)
- extra-field rejection (extra='forbid')
- missing-required-field rejection
Plus enum completeness, discriminated-union round-trip, raw_event trace_id, and
a Hypothesis property-based round-trip for TextMessageContent.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import TypeAdapter, ValidationError

from agent_ui_adapter.wire.ag_ui_events import (
    AGUIEvent,
    BaseEvent,
    Custom,
    EventType,
    MessagesSnapshot,
    Raw,
    RunError,
    RunFinished,
    RunStarted,
    StateDelta,
    StateSnapshot,
    StepFinished,
    StepStarted,
    TextMessageContent,
    TextMessageEnd,
    TextMessageStart,
    ToolCallArgs,
    ToolCallEnd,
    ToolCallStart,
    ToolResult,
)


# ─────────────────────────────────────────────────────────────────────
# Lifecycle events
# ─────────────────────────────────────────────────────────────────────


class TestRunStarted:
    def test_run_started_valid(self):
        ev = RunStarted(
            type=EventType.RUN_STARTED,
            run_id="r1",
            thread_id="t1",
            timestamp=datetime.now(UTC),
        )
        assert ev.run_id == "r1"
        assert ev.thread_id == "t1"
        assert ev.type == EventType.RUN_STARTED

    def test_run_started_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            RunStarted(
                type=EventType.RUN_STARTED,
                run_id="r1",
                thread_id="t1",
                timestamp=datetime.now(UTC),
                surprise="forbidden",  # type: ignore[call-arg]
            )

    def test_run_started_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            RunStarted(  # type: ignore[call-arg]
                type=EventType.RUN_STARTED,
                thread_id="t1",
                timestamp=datetime.now(UTC),
            )


class TestRunFinished:
    def test_run_finished_valid(self):
        ev = RunFinished(
            type=EventType.RUN_FINISHED,
            run_id="r1",
            thread_id="t1",
            timestamp=datetime.now(UTC),
        )
        assert ev.run_id == "r1"

    def test_run_finished_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            RunFinished(
                type=EventType.RUN_FINISHED,
                run_id="r1",
                thread_id="t1",
                timestamp=datetime.now(UTC),
                bogus=1,  # type: ignore[call-arg]
            )

    def test_run_finished_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            RunFinished(  # type: ignore[call-arg]
                type=EventType.RUN_FINISHED,
                run_id="r1",
                timestamp=datetime.now(UTC),
            )


class TestRunError:
    def test_run_error_valid(self):
        ev = RunError(
            type=EventType.RUN_ERROR,
            run_id="r1",
            thread_id="t1",
            message="boom",
            code="E_FAIL",
        )
        assert ev.message == "boom"
        assert ev.code == "E_FAIL"

    def test_run_error_optional_code(self):
        ev = RunError(
            type=EventType.RUN_ERROR,
            run_id="r1",
            thread_id="t1",
            message="boom",
        )
        assert ev.code is None

    def test_run_error_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            RunError(
                type=EventType.RUN_ERROR,
                run_id="r1",
                thread_id="t1",
                message="boom",
                extra="x",  # type: ignore[call-arg]
            )

    def test_run_error_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            RunError(  # type: ignore[call-arg]
                type=EventType.RUN_ERROR,
                run_id="r1",
                thread_id="t1",
            )


class TestStepStarted:
    def test_step_started_valid(self):
        ev = StepStarted(type=EventType.STEP_STARTED, step_name="reason")
        assert ev.step_name == "reason"

    def test_step_started_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            StepStarted(
                type=EventType.STEP_STARTED,
                step_name="reason",
                extra="nope",  # type: ignore[call-arg]
            )

    def test_step_started_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            StepStarted(type=EventType.STEP_STARTED)  # type: ignore[call-arg]


class TestStepFinished:
    def test_step_finished_valid(self):
        ev = StepFinished(type=EventType.STEP_FINISHED, step_name="reason")
        assert ev.step_name == "reason"

    def test_step_finished_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            StepFinished(
                type=EventType.STEP_FINISHED,
                step_name="reason",
                bogus=1,  # type: ignore[call-arg]
            )

    def test_step_finished_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            StepFinished(type=EventType.STEP_FINISHED)  # type: ignore[call-arg]


# ─────────────────────────────────────────────────────────────────────
# Text Message events
# ─────────────────────────────────────────────────────────────────────


class TestTextMessageStart:
    def test_text_message_start_valid(self):
        ev = TextMessageStart(
            type=EventType.TEXT_MESSAGE_START,
            message_id="m1",
            role="assistant",
        )
        assert ev.message_id == "m1"
        assert ev.role == "assistant"

    def test_text_message_start_rejects_wrong_role(self):
        with pytest.raises(ValidationError):
            TextMessageStart(
                type=EventType.TEXT_MESSAGE_START,
                message_id="m1",
                role="user",  # type: ignore[arg-type]
            )

    def test_text_message_start_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            TextMessageStart(
                type=EventType.TEXT_MESSAGE_START,
                message_id="m1",
                role="assistant",
                bogus=1,  # type: ignore[call-arg]
            )

    def test_text_message_start_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            TextMessageStart(  # type: ignore[call-arg]
                type=EventType.TEXT_MESSAGE_START,
                role="assistant",
            )


class TestTextMessageContent:
    def test_text_message_content_valid(self):
        ev = TextMessageContent(
            type=EventType.TEXT_MESSAGE_CONTENT,
            message_id="m1",
            delta="hello",
        )
        assert ev.delta == "hello"

    def test_text_message_content_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            TextMessageContent(
                type=EventType.TEXT_MESSAGE_CONTENT,
                message_id="m1",
                delta="hello",
                extra="x",  # type: ignore[call-arg]
            )

    def test_text_message_content_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            TextMessageContent(  # type: ignore[call-arg]
                type=EventType.TEXT_MESSAGE_CONTENT,
                delta="hello",
            )


class TestTextMessageEnd:
    def test_text_message_end_valid(self):
        ev = TextMessageEnd(type=EventType.TEXT_MESSAGE_END, message_id="m1")
        assert ev.message_id == "m1"

    def test_text_message_end_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            TextMessageEnd(
                type=EventType.TEXT_MESSAGE_END,
                message_id="m1",
                bogus=1,  # type: ignore[call-arg]
            )

    def test_text_message_end_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            TextMessageEnd(type=EventType.TEXT_MESSAGE_END)  # type: ignore[call-arg]


# ─────────────────────────────────────────────────────────────────────
# Tool Call events
# ─────────────────────────────────────────────────────────────────────


class TestToolCallStart:
    def test_tool_call_start_valid(self):
        ev = ToolCallStart(
            type=EventType.TOOL_CALL_START,
            tool_call_id="tc1",
            tool_call_name="search",
            parent_message_id="m1",
        )
        assert ev.tool_call_name == "search"
        assert ev.parent_message_id == "m1"

    def test_tool_call_start_optional_parent(self):
        ev = ToolCallStart(
            type=EventType.TOOL_CALL_START,
            tool_call_id="tc1",
            tool_call_name="search",
        )
        assert ev.parent_message_id is None

    def test_tool_call_start_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            ToolCallStart(
                type=EventType.TOOL_CALL_START,
                tool_call_id="tc1",
                tool_call_name="search",
                bogus="x",  # type: ignore[call-arg]
            )

    def test_tool_call_start_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            ToolCallStart(  # type: ignore[call-arg]
                type=EventType.TOOL_CALL_START,
                tool_call_id="tc1",
            )


class TestToolCallArgs:
    def test_tool_call_args_valid(self):
        ev = ToolCallArgs(
            type=EventType.TOOL_CALL_ARGS,
            tool_call_id="tc1",
            delta='{"q": "x"}',
        )
        assert ev.delta == '{"q": "x"}'

    def test_tool_call_args_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            ToolCallArgs(
                type=EventType.TOOL_CALL_ARGS,
                tool_call_id="tc1",
                delta="{}",
                extra=1,  # type: ignore[call-arg]
            )

    def test_tool_call_args_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            ToolCallArgs(  # type: ignore[call-arg]
                type=EventType.TOOL_CALL_ARGS,
                tool_call_id="tc1",
            )


class TestToolCallEnd:
    def test_tool_call_end_valid(self):
        ev = ToolCallEnd(type=EventType.TOOL_CALL_END, tool_call_id="tc1")
        assert ev.tool_call_id == "tc1"

    def test_tool_call_end_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            ToolCallEnd(
                type=EventType.TOOL_CALL_END,
                tool_call_id="tc1",
                bogus="y",  # type: ignore[call-arg]
            )

    def test_tool_call_end_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            ToolCallEnd(type=EventType.TOOL_CALL_END)  # type: ignore[call-arg]


class TestToolResult:
    def test_tool_result_valid(self):
        ev = ToolResult(
            type=EventType.TOOL_RESULT,
            tool_call_id="tc1",
            content="ok",
            role="tool",
        )
        assert ev.content == "ok"
        assert ev.role == "tool"

    def test_tool_result_rejects_wrong_role(self):
        with pytest.raises(ValidationError):
            ToolResult(
                type=EventType.TOOL_RESULT,
                tool_call_id="tc1",
                content="ok",
                role="assistant",  # type: ignore[arg-type]
            )

    def test_tool_result_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            ToolResult(
                type=EventType.TOOL_RESULT,
                tool_call_id="tc1",
                content="ok",
                role="tool",
                surprise=1,  # type: ignore[call-arg]
            )

    def test_tool_result_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            ToolResult(  # type: ignore[call-arg]
                type=EventType.TOOL_RESULT,
                tool_call_id="tc1",
                role="tool",
            )


# ─────────────────────────────────────────────────────────────────────
# State events
# ─────────────────────────────────────────────────────────────────────


class TestStateSnapshot:
    def test_state_snapshot_valid(self):
        ev = StateSnapshot(type=EventType.STATE_SNAPSHOT, snapshot={"k": 1})
        assert ev.snapshot == {"k": 1}

    def test_state_snapshot_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            StateSnapshot(
                type=EventType.STATE_SNAPSHOT,
                snapshot={},
                bogus=1,  # type: ignore[call-arg]
            )

    def test_state_snapshot_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            StateSnapshot(type=EventType.STATE_SNAPSHOT)  # type: ignore[call-arg]


class TestStateDelta:
    def test_state_delta_valid(self):
        ev = StateDelta(
            type=EventType.STATE_DELTA,
            delta=[{"op": "add", "path": "/x", "value": 1}],
        )
        assert ev.delta[0]["op"] == "add"

    def test_state_delta_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            StateDelta(
                type=EventType.STATE_DELTA,
                delta=[],
                bogus=1,  # type: ignore[call-arg]
            )

    def test_state_delta_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            StateDelta(type=EventType.STATE_DELTA)  # type: ignore[call-arg]


class TestMessagesSnapshot:
    def test_messages_snapshot_valid(self):
        ev = MessagesSnapshot(
            type=EventType.MESSAGES_SNAPSHOT,
            messages=[{"role": "user", "content": "hi"}],
        )
        assert ev.messages[0]["role"] == "user"

    def test_messages_snapshot_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            MessagesSnapshot(
                type=EventType.MESSAGES_SNAPSHOT,
                messages=[],
                bogus=1,  # type: ignore[call-arg]
            )

    def test_messages_snapshot_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            MessagesSnapshot(type=EventType.MESSAGES_SNAPSHOT)  # type: ignore[call-arg]


# ─────────────────────────────────────────────────────────────────────
# Special events
# ─────────────────────────────────────────────────────────────────────


class TestRaw:
    def test_raw_valid(self):
        ev = Raw(type=EventType.RAW, event="custom_thing", source="provider_x")
        assert ev.event == "custom_thing"
        assert ev.source == "provider_x"

    def test_raw_optional_source(self):
        ev = Raw(type=EventType.RAW, event="custom_thing")
        assert ev.source is None

    def test_raw_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            Raw(type=EventType.RAW, event="x", bogus=1)  # type: ignore[call-arg]

    def test_raw_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            Raw(type=EventType.RAW)  # type: ignore[call-arg]


class TestCustom:
    def test_custom_valid(self):
        ev = Custom(type=EventType.CUSTOM, name="x", value={"a": 1})
        assert ev.name == "x"
        assert ev.value == {"a": 1}

    def test_custom_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            Custom(
                type=EventType.CUSTOM,
                name="x",
                value={},
                bogus=1,  # type: ignore[call-arg]
            )

    def test_custom_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            Custom(type=EventType.CUSTOM, name="x")  # type: ignore[call-arg]


# ─────────────────────────────────────────────────────────────────────
# Cross-cutting
# ─────────────────────────────────────────────────────────────────────


EXPECTED_EVENT_TYPE_VALUES = {
    "RUN_STARTED",
    "RUN_FINISHED",
    "RUN_ERROR",
    "STEP_STARTED",
    "STEP_FINISHED",
    "TEXT_MESSAGE_START",
    "TEXT_MESSAGE_CONTENT",
    "TEXT_MESSAGE_END",
    "TOOL_CALL_START",
    "TOOL_CALL_ARGS",
    "TOOL_CALL_END",
    "TOOL_RESULT",
    "STATE_SNAPSHOT",
    "STATE_DELTA",
    "MESSAGES_SNAPSHOT",
    "RAW",
    "CUSTOM",
}


def test_event_type_enum_has_all_17_values():
    values = {e.value for e in EventType}
    assert values == EXPECTED_EVENT_TYPE_VALUES
    assert len(values) == 17


def test_discriminated_union_dispatches_correctly():
    """Round-trip via the discriminated-union TypeAdapter resolves the right concrete type."""
    adapter: TypeAdapter[AGUIEvent] = TypeAdapter(AGUIEvent)
    cases: list[tuple[BaseEvent, type]] = [
        (
            RunStarted(
                type=EventType.RUN_STARTED,
                run_id="r1",
                thread_id="t1",
                timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            ),
            RunStarted,
        ),
        (
            TextMessageContent(
                type=EventType.TEXT_MESSAGE_CONTENT, message_id="m1", delta="x"
            ),
            TextMessageContent,
        ),
        (
            ToolResult(
                type=EventType.TOOL_RESULT,
                tool_call_id="tc1",
                content="ok",
                role="tool",
            ),
            ToolResult,
        ),
        (StateSnapshot(type=EventType.STATE_SNAPSHOT, snapshot={"k": 1}), StateSnapshot),
        (Custom(type=EventType.CUSTOM, name="n", value={}), Custom),
    ]
    for original, expected_cls in cases:
        payload = original.model_dump(mode="json")
        rebuilt = adapter.validate_python(payload)
        assert isinstance(rebuilt, expected_cls)
        assert rebuilt == original


def test_base_event_raw_event_carries_trace_id():
    """Plan §4.3 Option B: trace_id rides in BaseEvent.raw_event."""
    ev = RunStarted(
        type=EventType.RUN_STARTED,
        run_id="r1",
        thread_id="t1",
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        raw_event={"trace_id": "abc"},
    )
    assert ev.raw_event == {"trace_id": "abc"}
    rehydrated = RunStarted.model_validate_json(ev.model_dump_json())
    assert rehydrated.raw_event == {"trace_id": "abc"}


# ─────────────────────────────────────────────────────────────────────
# Property-based round-trip (Pattern 1 from TDD §Pattern Catalog)
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.property
@given(message_id=st.text(min_size=1, max_size=64), delta=st.text(max_size=512))
def test_text_message_content_round_trip(message_id: str, delta: str):
    original = TextMessageContent(
        type=EventType.TEXT_MESSAGE_CONTENT,
        message_id=message_id,
        delta=delta,
    )
    rehydrated = TextMessageContent.model_validate_json(original.model_dump_json())
    assert rehydrated == original
