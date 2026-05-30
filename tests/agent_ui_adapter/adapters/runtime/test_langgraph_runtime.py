"""Tests for LangGraphRuntime adapter.

Per AGENT_UI_ADAPTER_SPRINTS.md US-3.3. TDD Protocol B (mock provider for
LangGraph compiled graph; no real LLM calls).

The adapter wraps `orchestration.react_loop:build_graph`. For unit tests
we substitute a fake compiled graph that yields a scripted async stream
of `astream_events`-shaped dicts so the runtime's translation logic is
exercised in isolation.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from agent_ui_adapter.adapters.runtime.langgraph_runtime import LangGraphRuntime
from agent_ui_adapter.ports.agent_runtime import AgentRuntime
from agent_ui_adapter.wire.domain_events import (
    DomainEventBase,
    LLMMessageStarted,
    LLMTokenEmitted,
    RunFinishedDomain,
    RunStartedDomain,
    ToolCallStarted,
    ToolResultReceived,
)
from trust.models import AgentFacts


# ── Fake compiled graph helpers ───────────────────────────────────────


class _FakeCompiledGraph:
    """Stand-in for a LangGraph compiled app.

    Implements the minimum surface LangGraphRuntime depends on:
    `astream_events(input, config, version)` returning an async iterator
    of dicts, plus `aget_state(config)` for get_state lookups.
    """

    def __init__(self, scripted: list[dict], state: Any = None) -> None:
        self._scripted = scripted
        self._state = state

    async def astream_events(self, input, config=None, version="v2"):
        for ev in self._scripted:
            yield ev

    async def aget_state(self, config):
        return self._state


def _facts() -> AgentFacts:
    return AgentFacts(
        agent_id="a1", agent_name="Bot", owner="team", version="1.0.0"
    )


# ── Conformance ───────────────────────────────────────────────────────


class TestLangGraphRuntimeConformance:
    def test_satisfies_agent_runtime_protocol(self) -> None:
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=[]))
        assert isinstance(rt, AgentRuntime)


# ── Translation: stream events → DomainEvent ──────────────────────────


class TestLangGraphRuntimeStream:
    @pytest.mark.asyncio
    async def test_emits_run_started_first_and_run_finished_last(self) -> None:
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=[]))
        out = []
        async for ev in rt.run(thread_id="t1", input={"task": "x"}, identity=_facts()):
            out.append(ev)
        assert isinstance(out[0], RunStartedDomain)
        assert isinstance(out[-1], RunFinishedDomain)
        assert out[-1].error is None

    @pytest.mark.asyncio
    async def test_translates_chat_model_stream_events_to_llm_tokens(self) -> None:
        scripted = [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": _FakeChunk(content="Hel")},
                "name": "ChatModel",
                "run_id": "lc-1",
            },
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": _FakeChunk(content="lo")},
                "name": "ChatModel",
                "run_id": "lc-1",
            },
        ]
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=scripted))
        out = []
        async for ev in rt.run(thread_id="t1", input={}, identity=_facts()):
            out.append(ev)
        token_events = [e for e in out if isinstance(e, LLMTokenEmitted)]
        assert len(token_events) == 2
        assert token_events[0].delta == "Hel"
        assert token_events[1].delta == "lo"

    @pytest.mark.asyncio
    async def test_filters_guard_input_when_langgraph_node_tagged(self) -> None:
        """Production graphs tag internal LLM nodes; only call_llm may surface."""
        scripted = [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": _FakeChunk(content="accept")},
                "name": "ChatModel",
                "run_id": "lc-guard",
                "metadata": {"langgraph_node": "guard_input"},
            },
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": _FakeChunk(content="Hi")},
                "name": "ChatModel",
                "run_id": "lc-main",
                "metadata": {"langgraph_node": "call_llm"},
            },
        ]
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=scripted))
        out = []
        async for ev in rt.run(thread_id="t1", input={}, identity=_facts()):
            out.append(ev)
        token_events = [e for e in out if isinstance(e, LLMTokenEmitted)]
        assert len(token_events) == 1
        assert token_events[0].delta == "Hi"

    @pytest.mark.asyncio
    async def test_null_langgraph_node_does_not_drop_tokens(self) -> None:
        """LangGraph may include ``langgraph_node: null``; must not filter like ``!= call_llm``."""
        scripted = [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": _FakeChunk(content="Hello")},
                "name": "ChatModel",
                "run_id": "lc-1",
                "metadata": {"langgraph_node": None},
            },
        ]
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=scripted))
        out = [
            ev async for ev in rt.run(thread_id="t1", input={}, identity=_facts())
        ]
        token_events = [e for e in out if isinstance(e, LLMTokenEmitted)]
        assert len(token_events) == 1
        assert token_events[0].delta == "Hello"

    @pytest.mark.asyncio
    async def test_on_llm_stream_emits_tokens_for_legacy_run_type(self) -> None:
        class _GenChunk:
            def __init__(self, text: str) -> None:
                self.text = text

        scripted = [
            {
                "event": "on_llm_stream",
                "data": {"chunk": _GenChunk("legacy")},
                "name": "LLM",
                "run_id": "lc-legacy",
                "metadata": {"langgraph_node": "call_llm"},
            },
        ]
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=scripted))
        out = [
            ev async for ev in rt.run(thread_id="t1", input={}, identity=_facts())
        ]
        token_events = [e for e in out if isinstance(e, LLMTokenEmitted)]
        assert len(token_events) == 1
        assert token_events[0].delta == "legacy"

    @pytest.mark.asyncio
    async def test_chat_model_start_captures_input_text(self) -> None:
        scripted = [
            {
                "event": "on_chat_model_start",
                "data": {
                    "input": {
                        "messages": [
                            {"role": "user", "content": "What is the capital of France?"}
                        ]
                    }
                },
                "name": "ChatModel",
                "run_id": "lc-input",
                "metadata": {"langgraph_node": "call_llm"},
            },
        ]
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=scripted))
        out = [
            ev async for ev in rt.run(thread_id="t1", input={}, identity=_facts())
        ]
        starts = [e for e in out if isinstance(e, LLMMessageStarted)]
        assert len(starts) == 1
        assert starts[0].input_text == "user: What is the capital of France?"

    @pytest.mark.asyncio
    async def test_tool_only_chat_end_emits_preview(self) -> None:
        class _ToolOnlyMsg:
            content = ""
            tool_calls = [{"name": "calculator"}]

        scripted = [
            {
                "event": "on_chat_model_end",
                "data": {"output": _ToolOnlyMsg()},
                "name": "ChatModel",
                "run_id": "lc-tools",
                "metadata": {"langgraph_node": "call_llm"},
            },
        ]
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=scripted))
        out = [
            ev async for ev in rt.run(thread_id="t1", input={}, identity=_facts())
        ]
        token_events = [e for e in out if isinstance(e, LLMTokenEmitted)]
        assert len(token_events) == 1
        assert "calculator" in token_events[0].delta

    @pytest.mark.asyncio
    async def test_translates_tool_start_and_end(self) -> None:
        scripted = [
            {
                "event": "on_tool_start",
                "data": {"input": {"x": 1}},
                "name": "calc",
                "run_id": "lc-tool-1",
            },
            {
                "event": "on_tool_end",
                "data": {"output": "42"},
                "name": "calc",
                "run_id": "lc-tool-1",
            },
        ]
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=scripted))
        out = [
            ev async for ev in rt.run(thread_id="t1", input={}, identity=_facts())
        ]
        starts = [e for e in out if isinstance(e, ToolCallStarted)]
        results = [e for e in out if isinstance(e, ToolResultReceived)]
        assert len(starts) == 1
        assert starts[0].tool_name == "calc"
        assert len(results) == 1
        assert results[0].result == "42"


# ── Failure isolation: graph error becomes RunFinished(error=...) ─────


class _ExplodingGraph:
    async def astream_events(self, input, config=None, version="v2"):
        yield {"event": "on_chat_model_stream", "data": {"chunk": _FakeChunk("x")}, "name": "m", "run_id": "r"}
        raise RuntimeError("boom")

    async def aget_state(self, config):
        return None


class TestLangGraphRuntimeFailure:
    @pytest.mark.asyncio
    async def test_graph_exception_becomes_run_finished_error(self) -> None:
        rt = LangGraphRuntime(graph=_ExplodingGraph())
        out = []
        async for ev in rt.run(thread_id="t1", input={}, identity=_facts()):
            out.append(ev)
        # No raw exception leak
        last = out[-1]
        assert isinstance(last, RunFinishedDomain)
        assert last.error is not None
        assert "boom" in last.error


# ── Trace ID propagation: every emitted event has a trace_id ──────────


class TestTraceIdPropagation:
    @pytest.mark.asyncio
    async def test_every_event_carries_trace_id(self) -> None:
        scripted = [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": _FakeChunk("x")},
                "name": "m",
                "run_id": "r",
            },
        ]
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=scripted))
        out = [
            ev async for ev in rt.run(thread_id="t1", input={}, identity=_facts())
        ]
        assert all(isinstance(e, DomainEventBase) for e in out)
        trace_ids = {e.trace_id for e in out}
        assert len(trace_ids) == 1, "All events in one run must share a trace_id"
        assert next(iter(trace_ids))  # non-empty


# ── Helpers ───────────────────────────────────────────────────────────


class _FakeChunk:
    """Minimal stand-in for LangChain's AIMessageChunk."""

    def __init__(self, content: str = "") -> None:
        self.content = content
