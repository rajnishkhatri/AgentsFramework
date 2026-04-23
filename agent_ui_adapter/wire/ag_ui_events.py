"""AG-UI events wire contract -- 17 native event Pydantic models.

Hand-mirrored from the AG-UI spec at https://docs.ag-ui.com/concepts/events.

Pinned AG-UI version: 0.1.18 (latest 0.x line as of S2 authoring; see
``AGUI_PINNED_VERSION`` constant). Tracking the 0.x line per plan §13 R1
mitigation -- upgrade lives on a dedicated branch in v1.5.

Pure Pydantic v2 models. ``extra='forbid'`` and ``frozen=True`` on every
event so schema drift fails closed and instances are immutable wire payloads.
The ``type`` field is the discriminator for the ``AGUIEvent`` union.

Per plan §4.3 Option B, ``trace_id`` rides in ``BaseEvent.raw_event`` on every
emitted event so cross-layer correlation survives the AG-UI hop.

Per plan §15.2 / rule R4, this module imports only from stdlib + pydantic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


AGUI_PINNED_VERSION: str = "0.1.18"


class EventType(str, Enum):
    """The 17 AG-UI event-type discriminator strings."""

    RUN_STARTED = "RUN_STARTED"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_ERROR = "RUN_ERROR"
    STEP_STARTED = "STEP_STARTED"
    STEP_FINISHED = "STEP_FINISHED"
    TEXT_MESSAGE_START = "TEXT_MESSAGE_START"
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    TEXT_MESSAGE_END = "TEXT_MESSAGE_END"
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_ARGS = "TOOL_CALL_ARGS"
    TOOL_CALL_END = "TOOL_CALL_END"
    TOOL_RESULT = "TOOL_RESULT"
    STATE_SNAPSHOT = "STATE_SNAPSHOT"
    STATE_DELTA = "STATE_DELTA"
    MESSAGES_SNAPSHOT = "MESSAGES_SNAPSHOT"
    RAW = "RAW"
    CUSTOM = "CUSTOM"


class BaseEvent(BaseModel):
    """Common header for every AG-UI event."""

    type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_event: dict | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


# ── Lifecycle ─────────────────────────────────────────────────────────


class RunStarted(BaseEvent):
    type: Literal[EventType.RUN_STARTED] = EventType.RUN_STARTED
    run_id: str
    thread_id: str


class RunFinished(BaseEvent):
    type: Literal[EventType.RUN_FINISHED] = EventType.RUN_FINISHED
    run_id: str
    thread_id: str


class RunError(BaseEvent):
    type: Literal[EventType.RUN_ERROR] = EventType.RUN_ERROR
    run_id: str
    thread_id: str
    message: str
    code: str | None = None


class StepStarted(BaseEvent):
    type: Literal[EventType.STEP_STARTED] = EventType.STEP_STARTED
    step_name: str


class StepFinished(BaseEvent):
    type: Literal[EventType.STEP_FINISHED] = EventType.STEP_FINISHED
    step_name: str


# ── Text Message ──────────────────────────────────────────────────────


class TextMessageStart(BaseEvent):
    type: Literal[EventType.TEXT_MESSAGE_START] = EventType.TEXT_MESSAGE_START
    message_id: str
    role: Literal["assistant"]


class TextMessageContent(BaseEvent):
    type: Literal[EventType.TEXT_MESSAGE_CONTENT] = EventType.TEXT_MESSAGE_CONTENT
    message_id: str
    delta: str


class TextMessageEnd(BaseEvent):
    type: Literal[EventType.TEXT_MESSAGE_END] = EventType.TEXT_MESSAGE_END
    message_id: str


# ── Tool Call ─────────────────────────────────────────────────────────


class ToolCallStart(BaseEvent):
    type: Literal[EventType.TOOL_CALL_START] = EventType.TOOL_CALL_START
    tool_call_id: str
    tool_call_name: str
    parent_message_id: str | None = None


class ToolCallArgs(BaseEvent):
    type: Literal[EventType.TOOL_CALL_ARGS] = EventType.TOOL_CALL_ARGS
    tool_call_id: str
    delta: str


class ToolCallEnd(BaseEvent):
    type: Literal[EventType.TOOL_CALL_END] = EventType.TOOL_CALL_END
    tool_call_id: str


class ToolResult(BaseEvent):
    type: Literal[EventType.TOOL_RESULT] = EventType.TOOL_RESULT
    tool_call_id: str
    content: str
    role: Literal["tool"]


# ── State ─────────────────────────────────────────────────────────────


class StateSnapshot(BaseEvent):
    type: Literal[EventType.STATE_SNAPSHOT] = EventType.STATE_SNAPSHOT
    snapshot: dict


class StateDelta(BaseEvent):
    type: Literal[EventType.STATE_DELTA] = EventType.STATE_DELTA
    delta: list[dict]


class MessagesSnapshot(BaseEvent):
    type: Literal[EventType.MESSAGES_SNAPSHOT] = EventType.MESSAGES_SNAPSHOT
    messages: list[dict]


# ── Special ───────────────────────────────────────────────────────────


class Raw(BaseEvent):
    type: Literal[EventType.RAW] = EventType.RAW
    event: str
    source: str | None = None


class Custom(BaseEvent):
    type: Literal[EventType.CUSTOM] = EventType.CUSTOM
    name: str
    value: dict


# ── Discriminated union (plan §4.1) ───────────────────────────────────


AGUIEvent = Annotated[
    RunStarted
    | RunFinished
    | RunError
    | StepStarted
    | StepFinished
    | TextMessageStart
    | TextMessageContent
    | TextMessageEnd
    | ToolCallStart
    | ToolCallArgs
    | ToolCallEnd
    | ToolResult
    | StateSnapshot
    | StateDelta
    | MessagesSnapshot
    | Raw
    | Custom,
    Field(discriminator="type"),
]


__all__ = [
    "AGUI_PINNED_VERSION",
    "AGUIEvent",
    "BaseEvent",
    "Custom",
    "EventType",
    "MessagesSnapshot",
    "Raw",
    "RunError",
    "RunFinished",
    "RunStarted",
    "StateDelta",
    "StateSnapshot",
    "StepFinished",
    "StepStarted",
    "TextMessageContent",
    "TextMessageEnd",
    "TextMessageStart",
    "ToolCallArgs",
    "ToolCallEnd",
    "ToolCallStart",
    "ToolResult",
]
