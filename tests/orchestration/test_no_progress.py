"""L4 Behavioral: No-progress detection in orchestration layer.

Tests the _count_trailing_repeats helper and the integration with
_should_continue — verifying that a repeating tool terminates the loop
with a graceful wrap-up (graduated warn -> hard-stop pattern).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from components.evaluator import count_trailing_repeats as _count_trailing_repeats
from services.base_config import AgentConfig, ModelProfile
from services.governance.black_box import EventType
from services.tools.registry import ToolDefinition, ToolExecutionResult, ToolRegistry


def _fast_profile():
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


class _WebSearchArgs(BaseModel):
    """Search the web for information."""
    query: str = ""


def _stub_web_search_executor(args: dict) -> ToolExecutionResult:
    return ToolExecutionResult(output="sunny and 75F", error=None)


def _read_bb_events(bb_dir, workflow_id: str) -> list[dict]:
    """Read all BlackBox events for a workflow from the JSONL trace file."""
    trace_file = bb_dir / workflow_id / "trace.jsonl"
    if not trace_file.exists():
        return []
    return [json.loads(ln) for ln in trace_file.read_text().splitlines() if ln]


def _events_of_type(events: list[dict], event_type: str) -> list[dict]:
    return [e for e in events if e.get("event_type") == event_type]


class TestCountTrailingRepeats:
    """Failure paths first: repeated calls detected before non-repeated."""

    def test_identical_tool_name_and_input_counted(self):
        results = [
            {"tool_name": "web_search", "tool_input": {"query": "weather"}, "tool_output": "sunny"},
            {"tool_name": "web_search", "tool_input": {"query": "weather"}, "tool_output": "sunny"},
            {"tool_name": "web_search", "tool_input": {"query": "weather"}, "tool_output": "sunny"},
        ]
        assert _count_trailing_repeats(results) == 3

    def test_identical_output_different_input_counted(self):
        results = [
            {"tool_name": "web_search", "tool_input": {"query": "weather austin"}, "tool_output": "error: timeout"},
            {"tool_name": "web_search", "tool_input": {"query": "austin weather"}, "tool_output": "error: timeout"},
            {"tool_name": "web_search", "tool_input": {"query": "weather in austin"}, "tool_output": "error: timeout"},
        ]
        assert _count_trailing_repeats(results) == 3

    def test_different_calls_returns_one(self):
        results = [
            {"tool_name": "shell", "tool_input": {"command": "ls"}, "tool_output": "file.txt"},
            {"tool_name": "web_search", "tool_input": {"query": "weather"}, "tool_output": "sunny"},
        ]
        assert _count_trailing_repeats(results) == 1

    def test_empty_results_returns_zero(self):
        assert _count_trailing_repeats([]) == 0

    def test_single_result_returns_zero(self):
        results = [
            {"tool_name": "web_search", "tool_input": {"query": "test"}, "tool_output": "ok"},
        ]
        assert _count_trailing_repeats(results) == 0

    def test_break_in_sequence_counts_trailing_only(self):
        results = [
            {"tool_name": "web_search", "tool_input": {"query": "weather"}, "tool_output": "sunny"},
            {"tool_name": "shell", "tool_input": {"command": "date"}, "tool_output": "Mon"},
            {"tool_name": "web_search", "tool_input": {"query": "weather"}, "tool_output": "sunny"},
            {"tool_name": "web_search", "tool_input": {"query": "weather"}, "tool_output": "sunny"},
        ]
        assert _count_trailing_repeats(results) == 2

    def test_different_tool_name_breaks_sequence(self):
        results = [
            {"tool_name": "web_search", "tool_input": {"query": "weather"}, "tool_output": "sunny"},
            {"tool_name": "web_search", "tool_input": {"query": "weather"}, "tool_output": "sunny"},
            {"tool_name": "file_io", "tool_input": {"path": "/x"}, "tool_output": "content"},
        ]
        assert _count_trailing_repeats(results) == 1

    def test_empty_output_does_not_match(self):
        """Empty tool_output should not trigger output-based matching."""
        results = [
            {"tool_name": "shell", "tool_input": {"command": "ls"}, "tool_output": ""},
            {"tool_name": "web_search", "tool_input": {"query": "test"}, "tool_output": ""},
        ]
        assert _count_trailing_repeats(results) == 1


class TestNoProgressGracefulWrapUp:
    """Binary outcome: Does a repeating tool terminate with a final answer? YES.

    L4 simulation-driven test mirroring test_graph_completes_with_final_answer.
    Uses a mocked LLM that emits the same tool-call repeatedly, then produces
    a final answer on the toolless synthesis pass.
    """

    @pytest.mark.asyncio
    async def test_repeating_tool_terminates_with_synthesis(self, tmp_path):
        """Graph terminates via graduated wrap-up, not GraphRecursionError."""

        call_count = 0

        def _make_tool_call_response():
            resp = MagicMock()
            resp.content = ""
            resp.tool_calls = [{"name": "web_search", "id": "tc1", "args": {"query": "weather"}}]
            resp.usage_metadata = {"input_tokens": 50, "output_tokens": 20, "total_tokens": 70}
            resp.response_metadata = {"model_name": "gpt-4o-mini"}
            return resp

        def _make_final_response():
            resp = MagicMock()
            resp.content = "Based on the information gathered, the weather is sunny."
            resp.tool_calls = []
            resp.usage_metadata = {"input_tokens": 80, "output_tokens": 30, "total_tokens": 110}
            resp.response_metadata = {"model_name": "gpt-4o-mini"}
            return resp

        async def _mock_ainvoke(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if mock_llm_instance._bound_for_this_call:
                mock_llm_instance._bound_for_this_call = False
                return _make_tool_call_response()
            return _make_final_response()

        tool_registry = ToolRegistry({
            "web_search": ToolDefinition(
                executor=_stub_web_search_executor,
                schema=_WebSearchArgs,
            ),
        })

        agent_config = AgentConfig(
            default_model="gpt-4o-mini",
            models=[_fast_profile()],
            max_steps=20,
            no_progress_repeat_threshold=3,
            no_progress_hard_limit=5,
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
            mock_llm_instance._bound_for_this_call = False
            mock_llm_instance.ainvoke = AsyncMock(side_effect=_mock_ainvoke)

            def _track_bind_tools(schemas):
                mock_llm_instance._bound_for_this_call = True
                return mock_llm_instance

            mock_llm_instance.bind_tools = MagicMock(side_effect=_track_bind_tools)

            from orchestration.react_loop import build_graph

            graph = build_graph(
                agent_config=agent_config,
                tool_registry=tool_registry,
                cache_dir=tmp_path / "cache",
                interrupt_before_execute_tool=False,
            )

            result = await graph.ainvoke(
                {
                    "task_id": "test-noprog-001",
                    "task_input": "What is the weather in Austin?",
                    "messages": [],
                    "workflow_id": "wf-noprog-001",
                    "registered_agent_id": "agent-test",
                },
                config={
                    "configurable": {
                        "task_id": "test-noprog-001",
                        "user_id": "test-user",
                        "workflow_id": "wf-noprog-001",
                    },
                    "recursion_limit": 50,
                },
            )

        messages = result.get("messages", [])
        assert len(messages) > 0
        last_ai = [m for m in messages if isinstance(m, AIMessage)]
        assert len(last_ai) > 0
        assert last_ai[-1].content  # final answer is not empty
        assert not last_ai[-1].tool_calls  # no tool calls in final answer

        bb_events = _read_bb_events(tmp_path / "cache" / "black_box_recordings", "wf-noprog-001")
        no_progress_events = _events_of_type(bb_events, EventType.STEP_PLANNED.value)
        assert any(e["details"].get("no_progress") for e in no_progress_events)

    @pytest.mark.asyncio
    async def test_hard_limit_failsafe_terminates(self, tmp_path):
        """When model keeps emitting tool calls ignoring the directive,
        the hard_limit failsafe terminates the loop."""

        async def _mock_ainvoke_always_tool_call(*args, **kwargs):
            resp = MagicMock()
            resp.content = ""
            resp.tool_calls = [{"name": "web_search", "id": "tc1", "args": {"query": "weather"}}]
            resp.usage_metadata = {"input_tokens": 50, "output_tokens": 20, "total_tokens": 70}
            resp.response_metadata = {"model_name": "gpt-4o-mini"}
            return resp

        tool_registry = ToolRegistry({
            "web_search": ToolDefinition(
                executor=_stub_web_search_executor,
                schema=_WebSearchArgs,
            ),
        })

        agent_config = AgentConfig(
            default_model="gpt-4o-mini",
            models=[_fast_profile()],
            max_steps=30,
            no_progress_repeat_threshold=3,
            no_progress_hard_limit=5,
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
            mock_llm_instance.ainvoke = AsyncMock(side_effect=_mock_ainvoke_always_tool_call)

            from orchestration.react_loop import build_graph

            graph = build_graph(
                agent_config=agent_config,
                tool_registry=tool_registry,
                cache_dir=tmp_path / "cache",
                interrupt_before_execute_tool=False,
            )

            result = await graph.ainvoke(
                {
                    "task_id": "test-hardlimit-001",
                    "task_input": "What is the weather in Austin?",
                    "messages": [],
                    "workflow_id": "wf-hardlimit-001",
                    "registered_agent_id": "agent-test",
                },
                config={
                    "configurable": {
                        "task_id": "test-hardlimit-001",
                        "user_id": "test-user",
                        "workflow_id": "wf-hardlimit-001",
                    },
                    "recursion_limit": 50,
                },
            )

        assert result is not None
        assert result.get("step_count", 0) < 30


class TestModelSelectedStepRegression:
    """I7: MODEL_SELECTED black-box events MUST carry a non-null integer step.

    Regression guard: the routing node previously emitted MODEL_SELECTED without
    a ``step``, breaking step-based span nesting (I6) downstream. A null step
    means the relay cannot attach the generation to its step span.
    """

    @pytest.mark.asyncio
    async def test_model_selected_carries_non_null_int_step(self, tmp_path):
        async def _mock_ainvoke(*args, **kwargs):
            resp = MagicMock()
            resp.content = "The capital of France is Paris."
            resp.tool_calls = []
            resp.usage_metadata = {
                "input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
            }
            resp.response_metadata = {"model_name": "gpt-4o-mini"}
            return resp

        agent_config = AgentConfig(
            default_model="gpt-4o-mini",
            models=[_fast_profile()],
            max_steps=5,
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
            mock_llm_instance.ainvoke = AsyncMock(side_effect=_mock_ainvoke)
            mock_llm_instance.bind_tools = MagicMock(return_value=mock_llm_instance)

            from orchestration.react_loop import build_graph

            graph = build_graph(
                agent_config=agent_config,
                cache_dir=tmp_path / "cache",
                interrupt_before_execute_tool=False,
            )

            await graph.ainvoke(
                {
                    "task_id": "test-i7-001",
                    "task_input": "What is the capital of France?",
                    "messages": [],
                    "workflow_id": "wf-i7-001",
                    "registered_agent_id": "agent-test",
                },
                config={
                    "configurable": {
                        "task_id": "test-i7-001",
                        "user_id": "test-user",
                        "workflow_id": "wf-i7-001",
                    },
                    "recursion_limit": 50,
                },
            )

        bb_events = _read_bb_events(
            tmp_path / "cache" / "black_box_recordings", "wf-i7-001"
        )
        model_selected = _events_of_type(bb_events, EventType.MODEL_SELECTED.value)
        assert len(model_selected) >= 1, "expected at least one MODEL_SELECTED event"
        for ev in model_selected:
            assert ev.get("step") is not None, "MODEL_SELECTED step must not be null"
            assert isinstance(ev["step"], int)
