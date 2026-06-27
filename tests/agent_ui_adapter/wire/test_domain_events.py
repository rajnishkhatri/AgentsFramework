"""L1 Deterministic: Tests for agent_ui_adapter.wire.domain_events.

Per AGENT_UI_ADAPTER_SPRINTS.md US-2.3.
TDD Protocol A. Failure paths first.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import get_args

import pytest
from pydantic import ValidationError

from agent_ui_adapter.wire.domain_events import (
    DomainEvent,
    DomainEventBase,
    LLMMessageEnded,
    LLMMessageStarted,
    LLMTokenEmitted,
    RunFinishedDomain,
    RunStartedDomain,
    StateMutated,
    StepProgressed,
    ToolCallEnded,
    ToolCallStarted,
    ToolResultReceived,
)


# Each domain event must require trace_id (failure path first per TAP-4),
# accept a minimal valid construction, and round-trip via JSON.


def _now() -> datetime:
    return datetime(2025, 1, 1, 12, 0, tzinfo=UTC)


# ── LLMTokenEmitted ───────────────────────────────────────────────────


class TestLLMTokenEmitted:
    def test_rejects_missing_trace_id(self):
        with pytest.raises(ValidationError):
            LLMTokenEmitted(message_id="m1", delta="x")  # type: ignore[call-arg]

    def test_valid(self):
        ev = LLMTokenEmitted(trace_id="tr1", message_id="m1", delta="x")
        assert ev.trace_id == "tr1"

    def test_round_trip(self):
        original = LLMTokenEmitted(
            trace_id="tr1", timestamp=_now(), message_id="m1", delta="x"
        )
        assert (
            LLMTokenEmitted.model_validate_json(original.model_dump_json()) == original
        )


# ── LLMMessageStarted ─────────────────────────────────────────────────


class TestLLMMessageStarted:
    def test_rejects_missing_trace_id(self):
        with pytest.raises(ValidationError):
            LLMMessageStarted(message_id="m1")  # type: ignore[call-arg]

    def test_valid(self):
        ev = LLMMessageStarted(trace_id="tr1", message_id="m1")
        assert ev.message_id == "m1"

    def test_round_trip(self):
        original = LLMMessageStarted(trace_id="tr1", timestamp=_now(), message_id="m1")
        assert (
            LLMMessageStarted.model_validate_json(original.model_dump_json())
            == original
        )


# ── LLMMessageEnded ───────────────────────────────────────────────────


class TestLLMMessageEnded:
    def test_rejects_missing_trace_id(self):
        with pytest.raises(ValidationError):
            LLMMessageEnded(message_id="m1")  # type: ignore[call-arg]

    def test_valid(self):
        ev = LLMMessageEnded(trace_id="tr1", message_id="m1")
        assert ev.message_id == "m1"

    def test_round_trip(self):
        original = LLMMessageEnded(trace_id="tr1", timestamp=_now(), message_id="m1")
        assert (
            LLMMessageEnded.model_validate_json(original.model_dump_json()) == original
        )

    # ── Phase 3: optional usage/cost/model fields (additive, W rule) ──

    def test_usage_fields_default_none(self):
        """Back-compat: a payload without the new fields still validates and the
        fields default to None (the wire ring evolves additively — W rule)."""
        ev = LLMMessageEnded(trace_id="tr1", message_id="m1")
        assert ev.tokens_in is None
        assert ev.tokens_out is None
        assert ev.model is None

    def test_cost_usd_is_not_a_wire_field(self):
        """Cost requires the model pricing table (service/config layer); it must
        NOT leak onto the framework-neutral wire event (four-layer boundary).
        Cost stays single-sourced on STEP_EXECUTED."""
        with pytest.raises(ValidationError):
            LLMMessageEnded(trace_id="tr1", message_id="m1", cost_usd=0.1)  # type: ignore[call-arg]

    def test_legacy_json_without_usage_fields_validates(self):
        """A pre-existing serialized event (no usage keys) still deserializes."""
        legacy = '{"trace_id":"tr1","message_id":"m1","output_text":"hi"}'
        ev = LLMMessageEnded.model_validate_json(legacy)
        assert ev.message_id == "m1"
        assert ev.tokens_in is None

    def test_usage_fields_populated(self):
        ev = LLMMessageEnded(
            trace_id="tr1",
            message_id="m1",
            output_text="hi",
            tokens_in=2144,
            tokens_out=113,
            model="gpt-4o-mini",
        )
        assert ev.tokens_in == 2144
        assert ev.tokens_out == 113
        assert ev.model == "gpt-4o-mini"

    def test_usage_round_trip(self):
        original = LLMMessageEnded(
            trace_id="tr1",
            message_id="m1",
            tokens_in=10,
            tokens_out=5,
            model="gpt-4o",
        )
        assert (
            LLMMessageEnded.model_validate_json(original.model_dump_json()) == original
        )


# ── ToolCallStarted ───────────────────────────────────────────────────


class TestToolCallStarted:
    def test_rejects_missing_trace_id(self):
        with pytest.raises(ValidationError):
            ToolCallStarted(  # type: ignore[call-arg]
                tool_call_id="tc1", tool_name="search", args_json="{}"
            )

    def test_valid(self):
        ev = ToolCallStarted(
            trace_id="tr1",
            tool_call_id="tc1",
            tool_name="search",
            args_json='{"q":"x"}',
        )
        assert ev.tool_name == "search"

    def test_round_trip(self):
        original = ToolCallStarted(
            trace_id="tr1",
            timestamp=_now(),
            tool_call_id="tc1",
            tool_name="search",
            args_json='{"q":"x"}',
        )
        assert (
            ToolCallStarted.model_validate_json(original.model_dump_json()) == original
        )


# ── ToolCallEnded ─────────────────────────────────────────────────────


class TestToolCallEnded:
    def test_rejects_missing_trace_id(self):
        with pytest.raises(ValidationError):
            ToolCallEnded(tool_call_id="tc1")  # type: ignore[call-arg]

    def test_valid(self):
        ev = ToolCallEnded(trace_id="tr1", tool_call_id="tc1")
        assert ev.tool_call_id == "tc1"

    def test_round_trip(self):
        original = ToolCallEnded(trace_id="tr1", timestamp=_now(), tool_call_id="tc1")
        assert ToolCallEnded.model_validate_json(original.model_dump_json()) == original


# ── ToolResultReceived ────────────────────────────────────────────────


class TestToolResultReceived:
    def test_rejects_missing_trace_id(self):
        with pytest.raises(ValidationError):
            ToolResultReceived(tool_call_id="tc1", result="ok")  # type: ignore[call-arg]

    def test_valid(self):
        ev = ToolResultReceived(trace_id="tr1", tool_call_id="tc1", result="ok")
        assert ev.result == "ok"

    def test_round_trip(self):
        original = ToolResultReceived(
            trace_id="tr1", timestamp=_now(), tool_call_id="tc1", result="ok"
        )
        assert (
            ToolResultReceived.model_validate_json(original.model_dump_json())
            == original
        )


# ── RunStartedDomain ──────────────────────────────────────────────────


class TestRunStartedDomain:
    def test_rejects_missing_trace_id(self):
        with pytest.raises(ValidationError):
            RunStartedDomain(run_id="r1", thread_id="t1")  # type: ignore[call-arg]

    def test_valid(self):
        ev = RunStartedDomain(trace_id="tr1", run_id="r1", thread_id="t1")
        assert ev.run_id == "r1"

    def test_round_trip(self):
        original = RunStartedDomain(
            trace_id="tr1", timestamp=_now(), run_id="r1", thread_id="t1"
        )
        assert (
            RunStartedDomain.model_validate_json(original.model_dump_json()) == original
        )


# ── RunFinishedDomain ─────────────────────────────────────────────────


class TestRunFinishedDomain:
    def test_rejects_missing_trace_id(self):
        with pytest.raises(ValidationError):
            RunFinishedDomain(run_id="r1", thread_id="t1")  # type: ignore[call-arg]

    def test_valid_no_error(self):
        ev = RunFinishedDomain(trace_id="tr1", run_id="r1", thread_id="t1")
        assert ev.error is None

    def test_valid_with_error(self):
        ev = RunFinishedDomain(
            trace_id="tr1", run_id="r1", thread_id="t1", error="boom"
        )
        assert ev.error == "boom"

    def test_round_trip(self):
        original = RunFinishedDomain(
            trace_id="tr1",
            timestamp=_now(),
            run_id="r1",
            thread_id="t1",
            error="boom",
        )
        assert (
            RunFinishedDomain.model_validate_json(original.model_dump_json())
            == original
        )


# ── StateMutated ──────────────────────────────────────────────────────


class TestStateMutated:
    def test_rejects_missing_trace_id(self):
        with pytest.raises(ValidationError):
            StateMutated(snapshot={"k": 1})  # type: ignore[call-arg]

    def test_valid_snapshot(self):
        ev = StateMutated(trace_id="tr1", snapshot={"k": 1})
        assert ev.snapshot == {"k": 1}

    def test_valid_delta(self):
        ev = StateMutated(
            trace_id="tr1", delta=[{"op": "add", "path": "/x", "value": 1}]
        )
        assert ev.delta is not None and ev.delta[0]["op"] == "add"

    def test_round_trip(self):
        original = StateMutated(
            trace_id="tr1",
            timestamp=_now(),
            snapshot={"k": 1},
            delta=[{"op": "add", "path": "/x", "value": 1}],
        )
        assert StateMutated.model_validate_json(original.model_dump_json()) == original


# ── StepProgressed ────────────────────────────────────────────────────


class TestStepProgressed:
    def test_rejects_missing_trace_id(self):
        with pytest.raises(ValidationError):
            StepProgressed(step_count=1, step_name="evaluation")  # type: ignore[call-arg]

    def test_rejects_missing_step_count(self):
        with pytest.raises(ValidationError):
            StepProgressed(trace_id="tr1", step_name="evaluation")  # type: ignore[call-arg]

    def test_valid(self):
        ev = StepProgressed(trace_id="tr1", step_count=3, step_name="evaluation")
        assert ev.step_count == 3
        assert ev.step_name == "evaluation"

    def test_round_trip(self):
        original = StepProgressed(
            trace_id="tr1",
            timestamp=_now(),
            step_count=2,
            step_name="tool_execution",
        )
        assert (
            StepProgressed.model_validate_json(original.model_dump_json()) == original
        )


# ── Cross-cutting: union completeness ─────────────────────────────────


def test_domain_event_base_is_frozen_and_strict():
    """All domain events inherit ConfigDict(extra='forbid', frozen=True)."""
    ev = LLMTokenEmitted(trace_id="tr1", message_id="m1", delta="x")
    with pytest.raises(ValidationError):
        type(ev).model_validate({**ev.model_dump(), "bogus": 1})


def test_domain_event_union_covers_all_types():
    """US-2.3 acceptance (extended by eval-UI Phase 0 + F10-T2 +
    task_understanding Phase 3 + memory_layer Phase 3 +
    shell_severity_approval_hitl): 14 members."""
    from agent_ui_adapter.wire.domain_events import (
        ApprovalRequested,
        MemoryRecalled,
        ReasoningSummarized,
        TaskUnderstood,
    )

    args = get_args(DomainEvent)
    assert len(args) == 14
    assert set(args) == {
        LLMTokenEmitted,
        LLMMessageStarted,
        LLMMessageEnded,
        ToolCallStarted,
        ToolCallEnded,
        ToolResultReceived,
        RunStartedDomain,
        RunFinishedDomain,
        StateMutated,
        StepProgressed,
        ReasoningSummarized,
        TaskUnderstood,
        MemoryRecalled,
        ApprovalRequested,
    }


def test_domain_event_base_is_abstract_in_practice():
    """DomainEventBase is a base class, not constructable as a meaningful event."""
    base = DomainEventBase(trace_id="tr1")
    assert base.trace_id == "tr1"


def test_task_understood_rejects_extra_fields():
    """Failure path first: the wire shape is strict (extra='forbid')."""
    from agent_ui_adapter.wire.domain_events import TaskUnderstood

    with pytest.raises(ValidationError):
        TaskUnderstood.model_validate(
            {
                "trace_id": "tr1",
                "restated_intent": "x",
                "success_conditions": ["a"],
                "confidence": 0.5,
                "source": "generated",
                "bogus": 1,
            }
        )


def test_task_understood_carries_artifact_fields():
    from agent_ui_adapter.wire.domain_events import TaskUnderstood

    ev = TaskUnderstood(
        trace_id="tr1",
        restated_intent="Create the file and verify it.",
        success_conditions=["file exists", "contents verified"],
        confidence=0.8,
        source="generated",
    )
    assert ev.trace_id == "tr1"
    assert ev.success_conditions == ["file exists", "contents verified"]


def test_memory_recalled_carries_count_and_keys():
    """memory_layer Phase 3 + B: count plus the injected records' KEYS
    (identifiers, never content). keys defaults to [] (backward compatible)."""
    from agent_ui_adapter.wire.domain_events import MemoryRecalled

    ev = MemoryRecalled(trace_id="tr1", count=2, keys=["k1", "k2"])
    assert ev.count == 2
    assert ev.keys == ["k1", "k2"]
    assert set(ev.model_dump()) == {"trace_id", "timestamp", "count", "keys"}


def test_memory_recalled_keys_default_empty():
    """Phase B backward compatibility: a count-only producer is still valid;
    keys defaults to []."""
    from agent_ui_adapter.wire.domain_events import MemoryRecalled

    ev = MemoryRecalled(trace_id="tr1", count=3)
    assert ev.keys == []


def test_memory_recalled_rejects_content_field():
    """Failure path first: strict wire shape — a 'content' field is rejected
    (the privacy invariant is structurally enforced; keys are identifiers, not
    content, and are the ONLY new field allowed)."""
    from agent_ui_adapter.wire.domain_events import MemoryRecalled

    with pytest.raises(ValidationError):
        MemoryRecalled.model_validate(
            {"trace_id": "tr1", "count": 1, "content": "leaked!"}
        )


def test_domain_event_union_includes_task_understood():
    """+TaskUnderstood (task_understanding plan Phase 3) +MemoryRecalled
    (memory_layer Phase 3) +ApprovalRequested (shell_severity_approval_hitl
    plan): 14 members."""
    from agent_ui_adapter.wire.domain_events import (
        ApprovalRequested,
        MemoryRecalled,
        TaskUnderstood,
    )

    args = get_args(DomainEvent)
    assert len(args) == 14
    assert TaskUnderstood in set(args)
    assert MemoryRecalled in set(args)
    assert ApprovalRequested in set(args)


def test_approval_requested_requires_trace_id():
    """Failure path first: ApprovalRequested without trace_id is rejected."""
    from agent_ui_adapter.wire.domain_events import ApprovalRequested

    with pytest.raises(ValidationError):
        ApprovalRequested(
            approval_id="ap1",
            tool="shell",
            command="mkdir x",
            severity="medium",
            band="ask",
            timeout_seconds=120,
        )  # type: ignore[call-arg]


def test_approval_requested_valid():
    from agent_ui_adapter.wire.domain_events import ApprovalRequested

    ev = ApprovalRequested(
        trace_id="tr1",
        approval_id="ap1",
        tool="shell",
        command="rm foo",
        severity="high",
        band="ask",
        timeout_seconds=90,
    )
    assert ev.approval_id == "ap1"
    assert ev.command == "rm foo"
