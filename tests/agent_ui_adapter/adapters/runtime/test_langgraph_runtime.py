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
    LLMMessageEnded,
    LLMMessageStarted,
    LLMTokenEmitted,
    RunFinishedDomain,
    RunStartedDomain,
    StateMutated,
    StepProgressed,
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
    async def test_tool_only_chat_end_emits_no_text_token(self) -> None:
        """Eval-UI F2: the 'Using tools: ...' preview must NOT enter the
        answer body -- tool activity is rendered from ToolCall events by
        the UI's status slot / tool cards, never as message text. The
        GJ-012/GJ-F-008 inadmissible captures were this preview frozen
        mid-stream styled as a final answer."""

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
        assert token_events == []
        # The message lifecycle still closes cleanly.
        ended = [e for e in out if isinstance(e, LLMMessageEnded)]
        assert len(ended) == 1
        assert ended[0].output_text is None

    def test_extract_usage_from_message(self) -> None:
        """Phase 3: tokens + model pulled from usage_metadata/response_metadata."""

        class _Msg:
            content = "hi"
            usage_metadata = {"input_tokens": 2144, "output_tokens": 113}
            response_metadata = {"model_name": "gpt-4o-mini"}

        ti, to, model = LangGraphRuntime._extract_usage(_Msg())
        assert ti == 2144
        assert to == 113
        assert model == "gpt-4o-mini"

    def test_extract_usage_absent_returns_none(self) -> None:
        """Failure path: no usage metadata → all None, no raise."""

        class _Bare:
            content = "hi"

        assert LangGraphRuntime._extract_usage(_Bare()) == (None, None, None)

    def test_extract_usage_never_raises_on_garbage(self) -> None:
        assert LangGraphRuntime._extract_usage(object()) == (None, None, None)
        assert LangGraphRuntime._extract_usage(None) == (None, None, None)

    @pytest.mark.asyncio
    async def test_chat_model_end_populates_usage_on_message_ended(self) -> None:
        """The emitted LLMMessageEnded carries tokens/model from the message."""

        class _Msg:
            content = "Paris"
            usage_metadata = {"input_tokens": 50, "output_tokens": 20}
            response_metadata = {"model_name": "gpt-4o-mini"}

        scripted = [
            {
                "event": "on_chat_model_end",
                "data": {"output": _Msg()},
                "name": "ChatModel",
                "run_id": "lc-usage",
                "metadata": {"langgraph_node": "call_llm"},
            },
        ]
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=scripted))
        out = [
            ev async for ev in rt.run(thread_id="t1", input={}, identity=_facts())
        ]
        ended = [e for e in out if isinstance(e, LLMMessageEnded)]
        assert len(ended) == 1
        assert ended[0].tokens_in == 50
        assert ended[0].tokens_out == 20
        assert ended[0].model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_chat_model_end_without_usage_keeps_fields_none(self) -> None:
        class _Msg:
            content = "Paris"

        scripted = [
            {
                "event": "on_chat_model_end",
                "data": {"output": _Msg()},
                "name": "ChatModel",
                "run_id": "lc-nousage",
                "metadata": {"langgraph_node": "call_llm"},
            },
        ]
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=scripted))
        out = [
            ev async for ev in rt.run(thread_id="t1", input={}, identity=_facts())
        ]
        ended = [e for e in out if isinstance(e, LLMMessageEnded)]
        assert len(ended) == 1
        assert ended[0].tokens_in is None
        assert ended[0].model is None

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


# ── Eval-UI Phase 0: node completion → StateMutated + StepProgressed ──


def _chain_end(name: str, output: Any, run_id: str = "lc-chain-1") -> dict:
    return {
        "event": "on_chain_end",
        "data": {"output": output},
        "name": name,
        "run_id": run_id,
    }


async def _collect(rt: LangGraphRuntime) -> list:
    return [ev async for ev in rt.run(thread_id="t1", input={}, identity=_facts())]


class TestChainEndStateMutation:
    """Node outputs carrying ``todos``/``plan_ref`` surface as StateMutated.

    Failure paths first per TAP-4: malformed/irrelevant chain-end events
    must emit nothing (and never crash) before the happy path is asserted.
    """

    @pytest.mark.asyncio
    async def test_non_dict_output_emits_nothing(self) -> None:
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(scripted=[_chain_end("execute_tool", "a string")])
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, StateMutated)]

    @pytest.mark.asyncio
    async def test_output_without_state_keys_emits_no_state_mutated(self) -> None:
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[_chain_end("execute_tool", {"messages": [], "tool_cache": {}})]
            )
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, StateMutated)]

    @pytest.mark.asyncio
    async def test_malformed_todos_not_a_list_is_ignored(self) -> None:
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[_chain_end("execute_tool", {"todos": "not-a-list"})]
            )
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, StateMutated)]

    @pytest.mark.asyncio
    async def test_root_langgraph_chain_end_is_suppressed(self) -> None:
        """The compiled graph's own on_chain_end restates the final state --
        emitting it would duplicate the last node delta at stream end."""
        todos = [{"id": "t1", "content": "x", "status": "completed"}]
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(scripted=[_chain_end("LangGraph", {"todos": todos})])
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, StateMutated)]

    @pytest.mark.asyncio
    async def test_todos_in_node_output_emit_json_patch_replace(self) -> None:
        todos = [
            {"id": "t1", "content": "read file", "status": "completed"},
            {"id": "t2", "content": "write file", "status": "pending"},
        ]
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(scripted=[_chain_end("execute_tool", {"todos": todos})])
        )
        out = await _collect(rt)
        mutations = [e for e in out if isinstance(e, StateMutated)]
        assert len(mutations) == 1
        assert mutations[0].delta == [
            {"op": "replace", "path": "/todos", "value": todos}
        ]
        assert mutations[0].trace_id == out[0].trace_id

    @pytest.mark.asyncio
    async def test_selected_model_in_node_output_emits_json_patch_replace(self) -> None:
        """Eval-UI F5: the route node's model selection surfaces as a state
        delta so the UI can render the model badge (D6 telemetry seam)."""
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[_chain_end("route", {"selected_model": "haiku-tier"})]
            )
        )
        out = await _collect(rt)
        mutations = [e for e in out if isinstance(e, StateMutated)]
        assert len(mutations) == 1
        assert mutations[0].delta == [
            {"op": "replace", "path": "/selected_model", "value": "haiku-tier"}
        ]

    @pytest.mark.asyncio
    async def test_plan_ref_in_node_output_emits_json_patch_replace(self) -> None:
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[_chain_end("execute_tool", {"plan_ref": ".plans/p1.json"})]
            )
        )
        out = await _collect(rt)
        mutations = [e for e in out if isinstance(e, StateMutated)]
        assert len(mutations) == 1
        assert mutations[0].delta == [
            {"op": "replace", "path": "/plan_ref", "value": ".plans/p1.json"}
        ]


class TestChainEndStepMeter:
    """``evaluate`` node completion == one ReAct lap → StepProgressed."""

    @pytest.mark.asyncio
    async def test_non_evaluate_chain_end_emits_no_step(self) -> None:
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[
                    _chain_end("route", {"selected_model": "m"}),
                    _chain_end("execute_tool", {"messages": []}),
                ]
            )
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, StepProgressed)]

    @pytest.mark.asyncio
    async def test_evaluate_chain_ends_increment_step_meter(self) -> None:
        scripted = [
            _chain_end("evaluate", {"current_workflow_phase": "evaluation"}, "lc-1"),
            _chain_end("evaluate", {"current_workflow_phase": "evaluation"}, "lc-2"),
        ]
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=scripted))
        out = await _collect(rt)
        steps = [e for e in out if isinstance(e, StepProgressed)]
        assert [s.step_count for s in steps] == [1, 2]
        assert steps[0].step_name == "evaluation"

    @pytest.mark.asyncio
    async def test_evaluate_with_non_dict_output_still_counts(self) -> None:
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(scripted=[_chain_end("evaluate", None)])
        )
        out = await _collect(rt)
        steps = [e for e in out if isinstance(e, StepProgressed)]
        assert len(steps) == 1
        assert steps[0].step_count == 1
        assert steps[0].step_name == "evaluate"

    @pytest.mark.asyncio
    async def test_step_counter_resets_between_runs(self) -> None:
        scripted = [_chain_end("evaluate", {"current_workflow_phase": "evaluation"})]
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=scripted))
        first = [e for e in await _collect(rt) if isinstance(e, StepProgressed)]
        second = [e for e in await _collect(rt) if isinstance(e, StepProgressed)]
        assert [s.step_count for s in first] == [1]
        assert [s.step_count for s in second] == [1]


class TestChainEndJoinAnswer:
    """T3 fan-out: the ``join`` node's synthesized answer must reach the SSE
    stream as a real text token.

    The join answer is produced OUTSIDE the ``call_llm`` node — either by an
    LLM ``invoke`` (whose ``on_chat_model_*`` events are suppressed because
    ``langgraph_node != "call_llm"``) or by a deterministic floor (no LLM call
    at all). Either way no ``LLMTokenEmitted`` is emitted from the model-stream
    path, so the only carrier left is the join node's ``on_chain_end`` output
    (``last_final_answer``). Without this seam the browser receives 0 text
    segments and renders the "completed without producing any output" fallback
    -- the Stage B live defect this guards. Failure paths first (TAP-4).
    """

    @pytest.mark.asyncio
    async def test_join_without_final_answer_emits_no_text(self) -> None:
        """A join output lacking ``last_final_answer`` must emit no token
        (and not crash) -- the empty-state floor, not a phantom blank token."""
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(scripted=[_chain_end("join", {"worker_results": []})])
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, LLMTokenEmitted)]

    @pytest.mark.asyncio
    async def test_join_with_empty_string_final_answer_emits_no_text(self) -> None:
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[_chain_end("join", {"last_final_answer": "   "})]
            )
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, LLMTokenEmitted)]

    @pytest.mark.asyncio
    async def test_join_non_dict_output_emits_no_text(self) -> None:
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(scripted=[_chain_end("join", "a string")])
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, LLMTokenEmitted)]

    @pytest.mark.asyncio
    async def test_join_final_answer_emits_token_trio(self) -> None:
        """The happy path: join's ``last_final_answer`` becomes a
        Started -> Token(delta=answer) -> Ended trio so the UI renders one
        real text segment (the same shape ``call_llm`` produces)."""
        answer = "Branch 1: Paris weather is mild.\nBranch 2: 3 hotels found."
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[_chain_end("join", {"last_final_answer": answer})]
            )
        )
        out = await _collect(rt)
        tokens = [e for e in out if isinstance(e, LLMTokenEmitted)]
        assert len(tokens) == 1
        assert tokens[0].delta == answer
        assert tokens[0].trace_id == out[0].trace_id

        started = [e for e in out if isinstance(e, LLMMessageStarted)]
        ended = [e for e in out if isinstance(e, LLMMessageEnded)]
        assert len(started) == 1 and len(ended) == 1
        # All three share one message_id so the UI groups them into one segment.
        assert started[0].message_id == tokens[0].message_id == ended[0].message_id

    @pytest.mark.asyncio
    async def test_join_does_not_increment_step_meter(self) -> None:
        """join is not a ReAct lap; only ``evaluate`` advances the step meter."""
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[_chain_end("join", {"last_final_answer": "x"})]
            )
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, StepProgressed)]


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


class TestGoalJudgeSaturationTrace:
    @pytest.mark.asyncio
    async def test_predetermined_trace_id_from_saturation_overlay(self) -> None:
        predetermined = "a" * 32
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=[]))
        out = [
            ev
            async for ev in rt.run(
                thread_id="session-gj-010",
                input={
                    "_goaljudge_saturation": {
                        "trace_id": predetermined,
                        "task_id": predetermined,
                        "user_id": "synthetic-saturation-user",
                        "case_id": "GJ-010",
                        "checkpoint_thread_id": "session-gj-010",
                    }
                },
                identity=_facts(),
            )
        ]
        trace_ids = {e.trace_id for e in out if isinstance(e, DomainEventBase)}
        assert trace_ids == {predetermined}


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


def _tool_result_record(
    tool_name: str = "file_io",
    record_id: str = "1:call-1",
    **overrides: Any,
) -> dict:
    rec = {
        "record_id": record_id,
        "step_id": 1,
        "task_id": "task-1",
        "tool_name": tool_name,
        "tool_input": {"path": "/workspace/x.txt"},
        "tool_output": "ok",
        "ok": True,
        "error": None,
        "cached": False,
        "offloaded": False,
        "offload_ref": None,
    }
    rec.update(overrides)
    return rec


class TestExecuteToolChainEndSynthesis:
    """``execute_tool`` runs tools via ``_execute_tools_impl`` directly, so
    LangGraph never fires ``on_tool_start`` for them — the chain end's
    ``tool_results`` is the only signal. The runtime must synthesize
    ToolCallStarted + ToolResultReceived from it (eval-UI F3: tool cards
    were invisible against the real graph, T3 finding 2026-06-11).

    Failure paths first per TAP-4.
    """

    @pytest.mark.asyncio
    async def test_execute_tool_end_without_tool_results_emits_nothing(self) -> None:
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[_chain_end("execute_tool", {"messages": []})]
            )
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, ToolCallStarted)]
        assert not [e for e in out if isinstance(e, ToolResultReceived)]

    @pytest.mark.asyncio
    async def test_malformed_tool_results_entries_are_skipped(self) -> None:
        output = {"tool_results": ["not-a-dict", 42, None]}
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(scripted=[_chain_end("execute_tool", output)])
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, ToolCallStarted)]

    @pytest.mark.asyncio
    async def test_other_nodes_tool_results_do_not_synthesize(self) -> None:
        output = {"tool_results": [_tool_result_record()]}
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(scripted=[_chain_end("evaluate", output)])
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, ToolCallStarted)]

    @pytest.mark.asyncio
    async def test_synthesizes_started_and_result_per_record(self) -> None:
        output = {
            "tool_results": [
                _tool_result_record("file_io", "1:call-1"),
                _tool_result_record("web_search", "1:call-2", tool_output="hits"),
            ]
        }
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(scripted=[_chain_end("execute_tool", output)])
        )
        out = await _collect(rt)
        starts = [e for e in out if isinstance(e, ToolCallStarted)]
        results = [e for e in out if isinstance(e, ToolResultReceived)]
        assert [s.tool_name for s in starts] == ["file_io", "web_search"]
        assert [s.tool_call_id for s in starts] == ["1:call-1", "1:call-2"]
        assert '"path": "/workspace/x.txt"' in starts[0].args_json
        assert [r.tool_call_id for r in results] == ["1:call-1", "1:call-2"]
        assert results[1].result == "hits"

    @pytest.mark.asyncio
    async def test_failed_tool_result_surfaces_error_text(self) -> None:
        output = {
            "tool_results": [
                _tool_result_record(
                    "file_io", ok=False, error="permission denied", tool_output=""
                )
            ]
        }
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(scripted=[_chain_end("execute_tool", output)])
        )
        out = await _collect(rt)
        results = [e for e in out if isinstance(e, ToolResultReceived)]
        assert len(results) == 1
        # "Error:" prefix is the registry convention the UI keys errored
        # tool cards on.
        assert results[0].result == "Error: permission denied"

    @pytest.mark.asyncio
    async def test_live_on_tool_start_suppresses_duplicate_synthesis(self) -> None:
        """If LangGraph DID fire on_tool_start for a call id, the chain-end
        record for the same call must not be re-emitted."""
        scripted = [
            {
                "event": "on_tool_start",
                "data": {"input": {"x": 1}, "tool_call_id": "call-1"},
                "name": "calc",
                "run_id": "lc-tool-1",
            },
            {
                "event": "on_tool_end",
                "data": {"output": "42", "tool_call_id": "call-1"},
                "name": "calc",
                "run_id": "lc-tool-1",
            },
            _chain_end(
                "execute_tool",
                {"tool_results": [_tool_result_record("calc", "1:call-1")]},
            ),
        ]
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=scripted))
        out = await _collect(rt)
        starts = [e for e in out if isinstance(e, ToolCallStarted)]
        assert len(starts) == 1, "live + synthesized must dedupe to one start"


class TestReasoningRecapChainEnd:
    """F10 Tier-2: the ``reasoning_recap`` node's output carries
    ``reasoning_summary``; the runtime surfaces it as ReasoningSummarized
    and suppresses the recap LLM call's own chat-model events (tagged
    ``reasoning_recap``) so recap tokens never leak into the answer.
    """

    @pytest.mark.asyncio
    async def test_empty_or_missing_summary_emits_nothing(self) -> None:
        from agent_ui_adapter.wire.domain_events import ReasoningSummarized

        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[
                    _chain_end("reasoning_recap", {}),
                    _chain_end("reasoning_recap", {"reasoning_summary": "   "}),
                    _chain_end("reasoning_recap", {"reasoning_summary": 42}),
                ]
            )
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, ReasoningSummarized)]

    @pytest.mark.asyncio
    async def test_other_nodes_reasoning_summary_is_ignored(self) -> None:
        from agent_ui_adapter.wire.domain_events import ReasoningSummarized

        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[_chain_end("evaluate", {"reasoning_summary": "x"})]
            )
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, ReasoningSummarized)]

    @pytest.mark.asyncio
    async def test_recap_node_summary_surfaces_as_domain_event(self) -> None:
        from agent_ui_adapter.wire.domain_events import ReasoningSummarized

        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[
                    _chain_end(
                        "reasoning_recap", {"reasoning_summary": "Did A then B."}
                    )
                ]
            )
        )
        out = await _collect(rt)
        recaps = [e for e in out if isinstance(e, ReasoningSummarized)]
        assert len(recaps) == 1
        assert recaps[0].text == "Did A then B."

    @pytest.mark.asyncio
    async def test_tagged_chat_model_events_are_suppressed(self) -> None:
        """The recap completion streams through astream_events like any other
        model call; its tagged token/lifecycle events must not become
        answer text or an empty message bubble."""
        scripted = [
            {
                "event": "on_chat_model_start",
                "data": {},
                "name": "ChatModel",
                "run_id": "lc-recap-1",
                "tags": ["reasoning_recap"],
            },
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": _FakeChunk(content="leaked recap token")},
                "name": "ChatModel",
                "run_id": "lc-recap-1",
                "tags": ["reasoning_recap"],
            },
            {
                "event": "on_chat_model_end",
                "data": {"output": _FakeChunk(content="leaked recap token")},
                "name": "ChatModel",
                "run_id": "lc-recap-1",
                "tags": ["reasoning_recap"],
            },
        ]
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=scripted))
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, LLMTokenEmitted)]
        assert not [e for e in out if isinstance(e, LLMMessageStarted)]
        assert not [e for e in out if isinstance(e, LLMMessageEnded)]


# ── Helpers ───────────────────────────────────────────────────────────


class _FakeChunk:
    """Minimal stand-in for LangChain's AIMessageChunk."""

    def __init__(self, content: str = "") -> None:
        self.content = content


class TestTaskUnderstandingChainEnd:
    """task_understanding plan Phase 3: the ``route`` node's output carries
    the memoized ``task_understanding`` dict; the runtime surfaces it as
    TaskUnderstood exactly once per distinct payload (route re-runs every
    evaluate→continue→route iteration with the same memoized artifact —
    re-emitting would re-render the card every lap)."""

    _ARTIFACT = {
        "restated_intent": "Create the file and verify it.",
        "success_conditions": ["file exists", "contents verified"],
        "confidence": 0.8,
        "source": "generated",
        "model": "gpt-4o-mini",
    }

    @pytest.mark.asyncio
    async def test_missing_or_malformed_artifact_emits_nothing(self) -> None:
        from agent_ui_adapter.wire.domain_events import TaskUnderstood

        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[
                    _chain_end("route", {"selected_model": "m"}),
                    _chain_end("route", {"task_understanding": {}}),
                    _chain_end("route", {"task_understanding": "not a dict"}),
                    _chain_end("route", {"task_understanding": {"source": "generated"}}),
                ]
            )
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, TaskUnderstood)]

    @pytest.mark.asyncio
    async def test_other_nodes_artifact_is_ignored(self) -> None:
        from agent_ui_adapter.wire.domain_events import TaskUnderstood

        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[_chain_end("evaluate", {"task_understanding": self._ARTIFACT})]
            )
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, TaskUnderstood)]

    @pytest.mark.asyncio
    async def test_route_artifact_surfaces_once_and_dedupes_reruns(self) -> None:
        from agent_ui_adapter.wire.domain_events import TaskUnderstood

        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[
                    _chain_end("route", {"task_understanding": self._ARTIFACT}),
                    # Memoized re-entry: identical payload must not re-emit.
                    _chain_end("route", {"task_understanding": self._ARTIFACT}),
                ]
            )
        )
        out = await _collect(rt)
        cards = [e for e in out if isinstance(e, TaskUnderstood)]
        assert len(cards) == 1
        assert cards[0].restated_intent == "Create the file and verify it."
        assert cards[0].success_conditions == ["file exists", "contents verified"]
        assert cards[0].source == "generated"

    @pytest.mark.asyncio
    async def test_changed_artifact_re_emits(self) -> None:
        """A user edit (Phase 4) changes the payload — the card must update."""
        from agent_ui_adapter.wire.domain_events import TaskUnderstood

        edited = {**self._ARTIFACT, "source": "user_edited",
                  "success_conditions": ["file exists"]}
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[
                    _chain_end("route", {"task_understanding": self._ARTIFACT}),
                    _chain_end("route", {"task_understanding": edited}),
                ]
            )
        )
        out = await _collect(rt)
        cards = [e for e in out if isinstance(e, TaskUnderstood)]
        assert len(cards) == 2
        assert cards[1].source == "user_edited"


class TestMemoryRecalledChainEnd:
    """memory_layer_wiring Phase 3: the ``route`` node's output carries
    ``recalled_memories_count`` (metadata only); the runtime surfaces it as a
    MemoryRecalled event once per distinct count, so the transparent-recall
    indicator renders without re-emitting on every memoized reflexion lap."""

    @pytest.mark.asyncio
    async def test_count_surfaces_once_and_dedupes_reruns(self) -> None:
        from agent_ui_adapter.wire.domain_events import MemoryRecalled

        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[
                    _chain_end("route", {"recalled_memories_count": 2}),
                    # Memoized re-entry with the same count must not re-emit.
                    _chain_end("route", {"recalled_memories_count": 2}),
                ]
            )
        )
        out = await _collect(rt)
        recalled = [e for e in out if isinstance(e, MemoryRecalled)]
        assert len(recalled) == 1
        assert recalled[0].count == 2

    @pytest.mark.asyncio
    async def test_missing_count_emits_nothing(self) -> None:
        from agent_ui_adapter.wire.domain_events import MemoryRecalled

        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[_chain_end("route", {"selected_model": "m"})]
            )
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, MemoryRecalled)]

    @pytest.mark.asyncio
    async def test_other_nodes_count_is_ignored(self) -> None:
        from agent_ui_adapter.wire.domain_events import MemoryRecalled

        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(
                scripted=[_chain_end("evaluate", {"recalled_memories_count": 5})]
            )
        )
        out = await _collect(rt)
        assert not [e for e in out if isinstance(e, MemoryRecalled)]


# ── Phase 2: post-run autocapture seam ────────────────────────────────


class _SnapshotState:
    def __init__(self, values: dict, *, nxt=()) -> None:
        self.values = values
        self.next = nxt


class _SpyAutocapture:
    def __init__(self) -> None:
        self.scheduled: list[dict] = []

    def schedule(self, **kwargs) -> None:
        self.scheduled.append(kwargs)


class TestAutocaptureSeam:
    """The post-run typed auto-capture is OPTIONAL and never blocks the run.

    Failure paths first (TAP-4): no autocapture injected → byte-identical to
    today; an errored run → no capture (nothing salient to remember).
    """

    @pytest.mark.asyncio
    async def test_no_autocapture_injected_is_noop(self) -> None:
        # Default (no autocapture) must be unchanged — no aget_state-driven
        # scheduling, run still finishes clean.
        rt = LangGraphRuntime(graph=_FakeCompiledGraph(scripted=[]))
        out = await _collect(rt)
        assert isinstance(out[-1], RunFinishedDomain)
        assert out[-1].error is None

    @pytest.mark.asyncio
    async def test_successful_run_schedules_capture_with_window(self) -> None:
        spy = _SpyAutocapture()
        state = _SnapshotState(
            {
                "task_input": "I prefer metric units",
                "last_final_answer": "Noted, metric it is.",
            }
        )
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(scripted=[], state=state),
            autocapture=spy,
        )
        await _collect(rt)
        assert len(spy.scheduled) == 1
        call = spy.scheduled[0]
        roles = [m["role"] for m in call["messages"]]
        assert roles == ["user", "assistant"]
        # user_id == identity.owner (cross-user-leak guard upstream).
        assert call["user_id"] == "team"

    @pytest.mark.asyncio
    async def test_errored_run_does_not_schedule_capture(self) -> None:
        spy = _SpyAutocapture()

        class _RaisingGraph(_FakeCompiledGraph):
            async def astream_events(self, input, config=None, version="v2"):
                raise RuntimeError("boom")
                yield  # pragma: no cover

        rt = LangGraphRuntime(
            graph=_RaisingGraph(scripted=[], state=_SnapshotState({})),
            autocapture=spy,
        )
        out = await _collect(rt)
        assert out[-1].error is not None
        assert spy.scheduled == []

    @pytest.mark.asyncio
    async def test_empty_window_does_not_schedule(self) -> None:
        spy = _SpyAutocapture()
        rt = LangGraphRuntime(
            graph=_FakeCompiledGraph(scripted=[], state=_SnapshotState({})),
            autocapture=spy,
        )
        await _collect(rt)
        assert spy.scheduled == []
