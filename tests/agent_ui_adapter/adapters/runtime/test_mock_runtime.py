"""Tests for MockRuntime adapter.

Per AGENT_UI_ADAPTER_SPRINTS.md US-3.2. TDD Protocol B (mock provider, Pattern 6).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agent_ui_adapter.adapters.runtime.mock_runtime import MockRuntime
from agent_ui_adapter.ports.agent_runtime import AgentRuntime
from agent_ui_adapter.wire.agent_protocol import ThreadState
from agent_ui_adapter.wire.domain_events import (
    LLMTokenEmitted,
    RunFinishedDomain,
    RunStartedDomain,
)
from trust.models import AgentFacts


def _facts() -> AgentFacts:
    return AgentFacts(
        agent_id="a1", agent_name="Bot", owner="team", version="1.0.0"
    )


def _scripted_events() -> list:
    trace = "trace-1"
    return [
        RunStartedDomain(trace_id=trace, run_id="r1", thread_id="t1"),
        LLMTokenEmitted(trace_id=trace, message_id="m1", delta="Hello"),
        LLMTokenEmitted(trace_id=trace, message_id="m1", delta=" world"),
        RunFinishedDomain(trace_id=trace, run_id="r1", thread_id="t1"),
    ]


# ── Conformance ───────────────────────────────────────────────────────


class TestMockRuntimeConformance:
    def test_satisfies_agent_runtime_protocol(self) -> None:
        assert isinstance(MockRuntime(events=[]), AgentRuntime)


# ── Acceptance: scripted yield ────────────────────────────────────────


class TestMockRuntimeYield:
    @pytest.mark.asyncio
    async def test_yields_scripted_events_in_order(self) -> None:
        events = _scripted_events()
        rt = MockRuntime(events=events)
        out = []
        async for ev in rt.run(thread_id="t1", input={}, identity=_facts()):
            out.append(ev)
        assert out == events

    @pytest.mark.asyncio
    async def test_yields_empty_when_no_events_configured(self) -> None:
        rt = MockRuntime(events=[])
        out = [ev async for ev in rt.run(thread_id="t1", input={}, identity=_facts())]
        assert out == []


# ── Failure path: scripted error ──────────────────────────────────────


class TestMockRuntimeError:
    @pytest.mark.asyncio
    async def test_error_after_n_raises_after_yielding_n_events(self) -> None:
        events = _scripted_events()
        rt = MockRuntime(events=events, error_after=2)
        out = []
        with pytest.raises(RuntimeError, match="MockRuntime scripted error"):
            async for ev in rt.run(thread_id="t1", input={}, identity=_facts()):
                out.append(ev)
        assert len(out) == 2

    @pytest.mark.asyncio
    async def test_error_after_zero_raises_immediately(self) -> None:
        rt = MockRuntime(events=_scripted_events(), error_after=0)
        out = []
        with pytest.raises(RuntimeError):
            async for ev in rt.run(thread_id="t1", input={}, identity=_facts()):
                out.append(ev)
        assert out == []


# ── cancel + get_state ────────────────────────────────────────────────


class TestMockRuntimeCancel:
    @pytest.mark.asyncio
    async def test_cancel_records_run_id(self) -> None:
        rt = MockRuntime(events=[])
        await rt.cancel(run_id="r1")
        assert "r1" in rt.cancelled_runs


class TestMockRuntimeGetState:
    @pytest.mark.asyncio
    async def test_get_state_returns_default_thread_state(self) -> None:
        rt = MockRuntime(events=[])
        state = await rt.get_state(thread_id="t1")
        assert isinstance(state, ThreadState)
        assert state.thread_id == "t1"

    @pytest.mark.asyncio
    async def test_get_state_uses_seeded_state_when_provided(self) -> None:
        seeded = ThreadState(
            thread_id="t1",
            user_id="u1",
            messages=[{"role": "user", "content": "hi"}],
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        rt = MockRuntime(events=[], states={"t1": seeded})
        state = await rt.get_state(thread_id="t1")
        assert state == seeded

    @pytest.mark.asyncio
    async def test_get_state_unknown_thread_raises_keyerror_when_strict(self) -> None:
        rt = MockRuntime(events=[], states={}, strict_state=True)
        with pytest.raises(KeyError):
            await rt.get_state(thread_id="unknown")
