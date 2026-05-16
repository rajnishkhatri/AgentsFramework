"""L4 Behavioral + L2 Contract: Tests for orchestration/react_loop.py.

The simulation-driven test proves the full graph completes. The L2 contract
tests for the tool cache use an in-memory ``ToolRegistry`` (no mocks) per
Anti-Pattern 2 (Mock Addiction).
No live LLM calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from components.schemas import StepResult  # noqa: F401  (ensures pydantic is wired)
from services.base_config import AgentConfig, ModelProfile
from services.governance.black_box import BlackBoxRecorder
from services.trace_service import InMemoryTraceSink, TraceService
from services.tools.registry import ToolDefinition, ToolExecutionResult, ToolRegistry
from services.tools.task_tool import TaskToolInput, execute_task_tool
from services.tools.think_tool import ThinkToolInput, execute_think_tool


def _fast_profile():
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


class TestReactLoopHappyPath:
    """Binary outcome: Can the graph complete a simple task with mocked LLM? YES."""

    @pytest.mark.asyncio
    async def test_graph_completes_with_final_answer(self, tmp_path):
        mock_response = MagicMock()
        mock_response.content = "FINAL ANSWER: Paris is the capital of France."
        mock_response.tool_calls = []
        mock_response.usage_metadata = {"input_tokens": 50, "output_tokens": 20, "total_tokens": 70}
        mock_response.response_metadata = {"model_name": "gpt-4o-mini"}

        agent_config = AgentConfig(
            default_model="gpt-4o-mini",
            models=[_fast_profile()],
        )

        with (
            patch("langchain_litellm.ChatLiteLLM") as MockChatLiteLLM,
            patch(
                "services.guardrails.InputGuardrail._call_judge",
                new_callable=AsyncMock,
                return_value="accept",
            ),
        ):
            mock_llm_instance = MockChatLiteLLM.return_value
            mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)

            from orchestration.react_loop import build_graph

            graph = build_graph(
                agent_config=agent_config,
                cache_dir=tmp_path / "cache",
            )

            result = await graph.ainvoke(
                {
                    "task_id": "test-001",
                    "task_input": "What is the capital of France?",
                    "messages": [],
                    "workflow_id": "wf-test-001",
                    "registered_agent_id": "agent-test",
                },
                config={
                    "configurable": {
                        "task_id": "test-001",
                        "user_id": "test-user",
                        "workflow_id": "wf-test-001",
                    }
                },
            )

        assert "messages" in result
        assert result.get("step_count", 0) >= 1


# ─────────────────────────────────────────────────────────────────────
# L2 Contract: Tool result cache (Workstream C)
# ─────────────────────────────────────────────────────────────────────


class _EchoArgs(BaseModel):
    value: str


def _build_registry(call_counter: dict[str, int], *, cacheable: bool = True) -> ToolRegistry:
    def _echo_executor(args: dict) -> str:
        call_counter["count"] = call_counter.get("count", 0) + 1
        return f"echo:{args.get('value', '')}"

    return ToolRegistry({
        "echo": ToolDefinition(executor=_echo_executor, schema=_EchoArgs, cacheable=cacheable),
    })


def _build_tool_message_state(tool_name: str, args: dict, *, cache: dict | None = None) -> dict:
    ai_msg = AIMessage(
        content="",
        tool_calls=[{"name": tool_name, "args": args, "id": "call-1", "type": "tool_call"}],
    )
    return {
        "messages": [ai_msg],
        "tool_cache": dict(cache or {}),
        "workflow_id": "wf-contract",
        "step_count": 0,
    }


def _tool_cfg(**overrides) -> AgentConfig:
    return AgentConfig(**overrides)


class TestToolCache:
    def test_cache_miss_executes_and_populates(self, tmp_path):
        from orchestration.react_loop import _compute_tool_cache_key, _execute_tools_impl

        counter: dict[str, int] = {}
        registry = _build_registry(counter)
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")

        state = _build_tool_message_state("echo", {"value": "hello"})
        result = _execute_tools_impl(
            state, tool_registry=registry, black_box=bb, agent_config=_tool_cfg()
        )

        assert counter["count"] == 1
        key = _compute_tool_cache_key("echo", {"value": "hello"})
        assert key in result["tool_cache"]
        assert result["tool_cache"][key] == "echo:hello"

    def test_cache_hit_skips_executor(self, tmp_path):
        from orchestration.react_loop import _compute_tool_cache_key, _execute_tools_impl

        counter: dict[str, int] = {}
        registry = _build_registry(counter)
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")

        key = _compute_tool_cache_key("echo", {"value": "hello"})
        state = _build_tool_message_state(
            "echo", {"value": "hello"}, cache={key: "cached-output"}
        )
        result = _execute_tools_impl(
            state, tool_registry=registry, black_box=bb, agent_config=_tool_cfg()
        )

        assert counter.get("count", 0) == 0, "executor must not run on cache hit"
        assert result["messages"][0].content == "cached-output"
        assert result["tool_cache"][key] == "cached-output"

    def test_cache_hit_emits_cached_true_black_box_event(self, tmp_path):
        import json as _json

        from orchestration.react_loop import _compute_tool_cache_key, _execute_tools_impl

        counter: dict[str, int] = {}
        registry = _build_registry(counter)
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")

        key = _compute_tool_cache_key("echo", {"value": "x"})
        state = _build_tool_message_state(
            "echo", {"value": "x"}, cache={key: "c"}
        )
        _execute_tools_impl(
            state, tool_registry=registry, black_box=bb, agent_config=_tool_cfg()
        )

        trace_file = tmp_path / "bb" / "wf-contract" / "trace.jsonl"
        lines = [ln for ln in trace_file.read_text().splitlines() if ln]
        events = [_json.loads(ln) for ln in lines]
        tool_events = [e for e in events if e["event_type"] == "tool_called"]
        assert tool_events and tool_events[0]["details"]["cached"] is True

    def test_non_cacheable_tool_bypasses_cache(self, tmp_path):
        from orchestration.react_loop import _execute_tools_impl

        counter: dict[str, int] = {}
        registry = _build_registry(counter, cacheable=False)
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")

        state = _build_tool_message_state("echo", {"value": "hi"})
        result = _execute_tools_impl(
            state, tool_registry=registry, black_box=bb, agent_config=_tool_cfg()
        )

        assert counter["count"] == 1
        assert result["tool_cache"] == {}

        state2 = _build_tool_message_state("echo", {"value": "hi"}, cache=result["tool_cache"])
        _execute_tools_impl(
            state2, tool_registry=registry, black_box=bb, agent_config=_tool_cfg()
        )
        assert counter["count"] == 2  # executor ran again — bypassed cache

    def test_repeat_call_same_args_hits_cache_second_time(self, tmp_path):
        from orchestration.react_loop import _execute_tools_impl

        counter: dict[str, int] = {}
        registry = _build_registry(counter)
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")

        s1 = _build_tool_message_state("echo", {"value": "once"})
        r1 = _execute_tools_impl(
            s1, tool_registry=registry, black_box=bb, agent_config=_tool_cfg()
        )
        assert counter["count"] == 1

        s2 = _build_tool_message_state("echo", {"value": "once"}, cache=r1["tool_cache"])
        _execute_tools_impl(
            s2, tool_registry=registry, black_box=bb, agent_config=_tool_cfg()
        )
        assert counter["count"] == 1  # cache hit, executor not called again

    def test_cache_key_argument_order_independent(self):
        from orchestration.react_loop import _compute_tool_cache_key

        k1 = _compute_tool_cache_key("t", {"a": 1, "b": 2})
        k2 = _compute_tool_cache_key("t", {"b": 2, "a": 1})
        assert k1 == k2

    def test_tool_state_delta_updates_files_todos_and_plan_ref(self, tmp_path):
        from orchestration.react_loop import _execute_tools_impl

        class _StateAwareArgs(BaseModel):
            value: str

        def _stateful_executor(_args: dict) -> ToolExecutionResult:
            return ToolExecutionResult(
                output="state updated",
                ok=True,
                state_delta={
                    "files": {"notes.md": "draft"},
                    "todos": [{"id": "1", "content": "Draft notes", "status": "completed"}],
                    "plan_ref": "plan://s1-us1",
                },
            )

        registry = ToolRegistry({
            "stateful": ToolDefinition(
                executor=_stateful_executor,
                schema=_StateAwareArgs,
                cacheable=False,
            ),
        })
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        state = _build_tool_message_state("stateful", {"value": "x"})

        result = _execute_tools_impl(
            state, tool_registry=registry, black_box=bb, agent_config=_tool_cfg()
        )

        assert result["files"]["notes.md"] == "draft"
        assert result["todos"][0]["status"] == "completed"
        assert result["plan_ref"] == "plan://s1-us1"
        assert result["tool_results"][0]["tool_name"] == "stateful"

    def test_large_tool_output_is_offloaded_and_cleared(self, tmp_path):
        from orchestration.react_loop import _execute_tools_impl

        class _LargeArgs(BaseModel):
            value: str

        registry = ToolRegistry({
            "large": ToolDefinition(
                executor=lambda _args: "X" * 40,
                schema=_LargeArgs,
                cacheable=False,
            ),
        })
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        state = _build_tool_message_state("large", {"value": "x"})

        result = _execute_tools_impl(
            state,
            tool_registry=registry,
            black_box=bb,
            agent_config=_tool_cfg(
                tool_output_offload_threshold_chars=10,
                tool_output_preview_chars=5,
            ),
        )

        tool_result = result["tool_results"][0]
        assert tool_result["offloaded"] is True
        assert tool_result["offload_ref"].startswith(".agent_offload/")
        assert tool_result["offload_ref"] in result["files"]
        assert result["files"][tool_result["offload_ref"]] == "X" * 40
        assert "[offloaded:" in result["messages"][0].content

    def test_tool_result_history_limit_trims_old_entries(self, tmp_path):
        from orchestration.react_loop import _execute_tools_impl

        class _EchoManyArgs(BaseModel):
            value: str

        registry = ToolRegistry({
            "echo": ToolDefinition(
                executor=lambda args: f"echo:{args.get('value', '')}",
                schema=_EchoManyArgs,
                cacheable=False,
            ),
        })
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "echo", "args": {"value": "1"}, "id": "call-1", "type": "tool_call"},
                {"name": "echo", "args": {"value": "2"}, "id": "call-2", "type": "tool_call"},
                {"name": "echo", "args": {"value": "3"}, "id": "call-3", "type": "tool_call"},
            ],
        )
        state = {
            "messages": [ai_msg],
            "tool_cache": {},
            "workflow_id": "wf-contract",
            "step_count": 0,
        }

        result = _execute_tools_impl(
            state,
            tool_registry=registry,
            black_box=bb,
            agent_config=_tool_cfg(tool_result_history_limit=2),
        )
        assert len(result["tool_results"]) == 2
        assert result["tool_results"][0]["tool_input"]["value"] == "2"
        assert result["tool_results"][1]["tool_input"]["value"] == "3"

    def test_reasoning_trace_delta_from_think_tool_is_propagated(self, tmp_path):
        from orchestration.react_loop import _execute_tools_impl

        registry = ToolRegistry({
            "think": ToolDefinition(
                executor=execute_think_tool,
                schema=ThinkToolInput,
                cacheable=False,
            ),
        })
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        state = _build_tool_message_state(
            "think",
            {"thought": "Need better branch coverage", "category": "observation"},
        )

        result = _execute_tools_impl(
            state,
            tool_registry=registry,
            black_box=bb,
            agent_config=_tool_cfg(),
        )
        assert "reasoning_trace" in result
        assert len(result["reasoning_trace"]) == 1

    def test_task_tool_emits_delegation_trace_records(self, tmp_path):
        from orchestration.react_loop import _execute_tools_impl

        registry = ToolRegistry({
            "task": ToolDefinition(
                executor=execute_task_tool,
                schema=TaskToolInput,
                cacheable=False,
            ),
        })
        bb = BlackBoxRecorder(storage_dir=tmp_path / "bb")
        sink = InMemoryTraceSink()
        trace_service = TraceService([sink])
        state = _build_tool_message_state(
            "task",
            {
                "operation": "delegate",
                "objective": "collect test evidence",
                "subagent_type": "research",
            },
        )
        state["registered_agent_id"] = "agent-test"
        state["agent_capabilities"] = ["delegate.subagent.*"]

        result = _execute_tools_impl(
            state,
            tool_registry=registry,
            black_box=bb,
            agent_config=_tool_cfg(),
            trace_service=trace_service,
        )
        assert result["tool_results"][0]["ok"] is True
        assert any(r.event_type == "delegation_requested" for r in sink.records)
        assert any(r.event_type == "delegation_completed" for r in sink.records)
