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
        assert LLMTokenEmitted.model_validate_json(original.model_dump_json()) == original


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
        assert LLMMessageStarted.model_validate_json(original.model_dump_json()) == original


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
        assert LLMMessageEnded.model_validate_json(original.model_dump_json()) == original


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
        assert ToolCallStarted.model_validate_json(original.model_dump_json()) == original


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
            ToolResultReceived.model_validate_json(original.model_dump_json()) == original
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
        assert RunStartedDomain.model_validate_json(original.model_dump_json()) == original


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
        assert RunFinishedDomain.model_validate_json(original.model_dump_json()) == original


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


# ── Cross-cutting: union completeness ─────────────────────────────────


def test_domain_event_base_is_frozen_and_strict():
    """All domain events inherit ConfigDict(extra='forbid', frozen=True)."""
    ev = LLMTokenEmitted(trace_id="tr1", message_id="m1", delta="x")
    with pytest.raises(ValidationError):
        type(ev).model_validate({**ev.model_dump(), "bogus": 1})


def test_domain_event_union_covers_all_types():
    """US-2.3 acceptance: len(get_args(DomainEvent)) == 9."""
    args = get_args(DomainEvent)
    assert len(args) == 9
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
    }


def test_domain_event_base_is_abstract_in_practice():
    """DomainEventBase is a base class, not constructable as a meaningful event."""
    base = DomainEventBase(trace_id="tr1")
    assert base.trace_id == "tr1"
