"""Internal canonical domain events emitted by ``AgentRuntime.run()``.

Per AGENT_UI_ADAPTER_PLAN.md §5.1 and SPRINTS US-2.3. Translators
(``agent_ui_adapter.translators.domain_to_ag_ui``) map these canonical
shapes to the public AG-UI events without leaking framework specifics
(LangGraph state types) into the wire ring.

Every event carries a required ``trace_id`` per plan §4.3 Option B so
downstream translation can populate ``BaseEvent.raw_event.trace_id`` on
every emitted AG-UI event.

Pure Pydantic v2 with ``extra='forbid'`` and ``frozen=True``. No
discriminated union here -- the translator dispatches on type via pattern
matching. ``DomainEvent`` is exported as a type-alias union so consumers
can spell the type and architecture tests can assert completeness.

Per rule R4, this module imports only from stdlib + pydantic.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class DomainEventBase(BaseModel):
    """Common header for every internal domain event."""

    trace_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(extra="forbid", frozen=True)


# ── LLM token / message lifecycle ─────────────────────────────────────


class LLMTokenEmitted(DomainEventBase):
    message_id: str
    delta: str


class LLMMessageStarted(DomainEventBase):
    message_id: str
    input_text: str | None = None


class LLMMessageEnded(DomainEventBase):
    message_id: str
    output_text: str | None = None
    # Phase 3 (W rule, additive): optional token usage + model carried from the
    # runtime adapter so the merged ``llm.call`` generation renders native token
    # analytics in Langfuse. Absent on legacy payloads → None.
    #
    # ``cost_usd`` is deliberately NOT a wire field: cost requires the model
    # pricing table (``cost_per_1k_*``), which belongs to the service/config
    # layer, not the framework-neutral wire adapter (four-layer boundary). Cost
    # stays single-sourced on the canonical ``STEP_EXECUTED`` record
    # (``react_loop.py``); the trace surfaces token counts instead.
    tokens_in: int | None = None
    tokens_out: int | None = None
    model: str | None = None


# ── Tool call lifecycle ───────────────────────────────────────────────


class ToolCallStarted(DomainEventBase):
    tool_call_id: str
    tool_name: str
    args_json: str


class ToolCallEnded(DomainEventBase):
    tool_call_id: str


class ToolResultReceived(DomainEventBase):
    tool_call_id: str
    result: str


# ── Run lifecycle ─────────────────────────────────────────────────────


class RunStartedDomain(DomainEventBase):
    run_id: str
    thread_id: str


class RunFinishedDomain(DomainEventBase):
    run_id: str
    thread_id: str
    error: str | None = None


# ── State mutations (snapshot or JSON Patch delta) ────────────────────


class StateMutated(DomainEventBase):
    snapshot: dict | None = None
    delta: list[dict] | None = None


# ── Step progress (one ReAct lap; rides the Custom 'step_meter' wire) ─


class StepProgressed(DomainEventBase):
    step_count: int
    step_name: str


class ReasoningSummarized(DomainEventBase):
    """F10 Tier-2: one cheap-tier "why/how" recap per run (wire: Custom
    ``reasoning_summary``)."""

    text: str


class TaskUnderstood(DomainEventBase):
    """task_understanding plan Phase 3: plan-time intent restatement +
    success checklist for the soft-gate card (wire: Custom
    ``task_understanding``). ``source`` is the provenance tier
    (deterministic | generated | user_edited)."""

    restated_intent: str
    success_conditions: list[str]
    confidence: float
    source: str


# ── Union type alias (US-2.3 acceptance, +TaskUnderstood: 12 members) ─


DomainEvent = (
    LLMTokenEmitted
    | LLMMessageStarted
    | LLMMessageEnded
    | ToolCallStarted
    | ToolCallEnded
    | ToolResultReceived
    | RunStartedDomain
    | RunFinishedDomain
    | StateMutated
    | StepProgressed
    | ReasoningSummarized
    | TaskUnderstood
)


__all__ = [
    "DomainEvent",
    "DomainEventBase",
    "LLMMessageEnded",
    "LLMMessageStarted",
    "LLMTokenEmitted",
    "ReasoningSummarized",
    "RunFinishedDomain",
    "RunStartedDomain",
    "StateMutated",
    "StepProgressed",
    "TaskUnderstood",
    "ToolCallEnded",
    "ToolCallStarted",
    "ToolResultReceived",
]
