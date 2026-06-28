"""Synthetic end-to-end scenarios for deep-agent planning/state behavior.

These tests execute the compiled graph (L4 simulation) with deterministic,
scripted LLM responses so planning depth, todo updates, virtual files, and
offload behavior can be evaluated without live model calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from services.base_config import AgentConfig, ModelProfile
from services.tools.file_tools import StateFileToolInput, execute_state_file_tool
from services.tools.registry import ToolDefinition, ToolRegistry
from services.tools.todo_tools import StateTodoToolInput, execute_state_todo_tool


def _fast_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _capable_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o",
        litellm_id="openai/gpt-4o",
        tier="capable",
        context_window=128000,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.015,
    )


class _EmitLargeInput(BaseModel):
    size: int
    char: str = "X"


def _emit_large_output(args: dict) -> str:
    size = max(1, int(args.get("size", 1)))
    char = str(args.get("char", "X"))[:1] or "X"
    return char * size


def _build_registry() -> ToolRegistry:
    return ToolRegistry(
        {
            "state_file": ToolDefinition(
                executor=execute_state_file_tool,
                schema=StateFileToolInput,
                cacheable=False,
            ),
            "state_todo": ToolDefinition(
                executor=execute_state_todo_tool,
                schema=StateTodoToolInput,
                cacheable=False,
            ),
            "emit_large": ToolDefinition(
                executor=_emit_large_output,
                schema=_EmitLargeInput,
                cacheable=False,
            ),
        }
    )


def _load_cases(fixture_name: str) -> list[dict]:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / fixture_name
    return json.loads(fixture_path.read_text())


def _make_llm_response(content: str, tool_calls: list[dict], idx: int) -> MagicMock:
    response = MagicMock()
    response.content = content
    response.tool_calls = [
        {
            "name": tc["name"],
            "args": tc["args"],
            "id": f"tool-call-{idx}-{pos}",
            "type": "tool_call",
        }
        for pos, tc in enumerate(tool_calls)
    ]
    response.usage_metadata = {
        "input_tokens": 50,
        "output_tokens": 20,
        "total_tokens": 70,
    }
    response.response_metadata = {"model_name": "gpt-4o-mini"}
    return response


async def _run_case(
    case: dict,
    tmp_path,
    *,
    assert_initial_depth: bool,
    assert_no_unexpected_offload: bool,
):
    from orchestration.react_loop import build_graph

    script = case["llm_script"]
    expectations = case["expectations"]
    responses = [
        _make_llm_response(
            content=step["content"],
            tool_calls=step["tool_calls"],
            idx=index,
        )
        for index, step in enumerate(script)
    ]

    with (
        patch("langchain_litellm.ChatLiteLLM") as MockChatLiteLLM,
        patch(
            "services.guardrails.InputGuardrail._call_judge",
            new_callable=AsyncMock,
            return_value="accept",
        ),
    ):
        mock_llm_instance = MockChatLiteLLM.return_value
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        mock_llm_instance.ainvoke = AsyncMock(side_effect=responses)

        graph = build_graph(
            agent_config=AgentConfig(
                default_model="gpt-4o-mini",
                models=[_fast_profile(), _capable_profile()],
                tool_output_offload_threshold_chars=40,
                tool_output_preview_chars=12,
            ),
            tool_registry=_build_registry(),
            cache_dir=tmp_path / "cache",
        )

        workflow_id = f"wf-{case['id']}"
        result = await graph.ainvoke(
            {
                "task_id": f"task-{case['id']}",
                "task_input": case["task_input"],
                "messages": [],
                "workflow_id": workflow_id,
                "registered_agent_id": "synthetic-agent",
            },
            config={
                "configurable": {
                    "task_id": f"task-{case['id']}",
                    "user_id": "synthetic-user",
                    "workflow_id": workflow_id,
                    "registered_agent_id": "synthetic-agent",
                }
            },
        )

    files = result.get("files", {})
    todos = result.get("todos", [])
    tool_results = result.get("tool_results", [])

    assert result.get("last_outcome") == "success"
    assert result.get("step_count", 0) >= 2
    assert result.get("plan_ref"), "plan_ref should be set by route_node"

    if assert_initial_depth:
        initial_plan_ref = next(
            (
                path
                for path in files.keys()
                if path.startswith(".agent_plans/") and "_step_0.json" in path
            ),
            None,
        )
        assert initial_plan_ref is not None, "expected initial step plan artifact"
        initial_plan_payload = json.loads(files[initial_plan_ref])
        assert initial_plan_payload["planning_depth"] == expectations["initial_depth"]

    assert result.get("planning_depth") == expectations["final_depth"]

    todo_index = {todo["id"]: todo for todo in todos}
    for required in expectations["required_todos"]:
        assert required["id"] in todo_index
        assert todo_index[required["id"]]["status"] == required["status"]

    for required_file in expectations["required_files"]:
        assert required_file in files

    offloaded = [record for record in tool_results if record.get("offloaded")]
    if expectations["expect_offload"]:
        assert offloaded, "expected at least one offloaded tool result"
        for record in offloaded:
            ref = record.get("offload_ref")
            assert isinstance(ref, str) and ref in files
    elif assert_no_unexpected_offload:
        assert not offloaded


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    _load_cases("deep_agent_synthetic_e2e_cases.json"),
    ids=lambda case: case["id"],
)
async def test_synthetic_cases_run_end_to_end(case: dict, tmp_path):
    await _run_case(
        case,
        tmp_path,
        assert_initial_depth=True,
        assert_no_unexpected_offload=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    _load_cases("deep_agent_benchmark_adapted_cases.json"),
    ids=lambda case: case["id"],
)
async def test_adapted_benchmark_cases_run_end_to_end(case: dict, tmp_path):
    await _run_case(
        case,
        tmp_path,
        assert_initial_depth=False,
        assert_no_unexpected_offload=False,
    )
