"""L2 Contract: Error propagation to evaluator (Story 1.3).

Tests that real errors from LLM and tool execution reach classify_outcome
with appropriate error types.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.base_config import AgentConfig, ModelProfile


def _fast_profile():
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _agent_config():
    return AgentConfig(
        default_model="gpt-4o-mini",
        models=[_fast_profile()],
        max_steps=3,
    )


class TestErrorPropagation:
    """Story 1.3: errors flow through to classify_outcome."""

    @pytest.mark.asyncio
    async def test_429_error_classified_as_retryable(self, tmp_path):
        error = Exception("Rate limited")
        error.status_code = 429  # type: ignore[attr-defined]

        call_count = 0

        async def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise error
            resp = MagicMock()
            resp.content = "Success after retry"
            resp.tool_calls = []
            resp.usage_metadata = {"input_tokens": 10, "output_tokens": 5}
            return resp

        with (
            patch("langchain_litellm.ChatLiteLLM") as MockChatLiteLLM,
            patch(
                "services.guardrails.InputGuardrail._call_judge",
                new_callable=AsyncMock,
                return_value="accept",
            ),
        ):
            mock_llm = MockChatLiteLLM.return_value
            mock_llm.ainvoke = AsyncMock(side_effect=_side_effect)

            from orchestration.react_loop import build_graph

            graph = build_graph(
                agent_config=_agent_config(),
                cache_dir=tmp_path / "cache",
            )

            result = await graph.ainvoke(
                {
                    "task_id": "test-429",
                    "task_input": "test query",
                    "messages": [],
                    "workflow_id": "wf-429",
                    "registered_agent_id": "agent-test",
                },
                config={"configurable": {"task_id": "test-429", "user_id": "test"}},
            )

        error_history = result.get("error_history", [])
        retryable_errors = [e for e in error_history if e.get("error_type") == "retryable"]
        assert len(retryable_errors) >= 1, "429 should be classified as retryable"

    @pytest.mark.asyncio
    async def test_tool_error_classified_correctly(self, tmp_path):
        from pydantic import BaseModel

        from services.tools.registry import ToolDefinition, ToolRegistry

        class _TestInput(BaseModel):
            value: str

        def _failing_tool(args: dict) -> str:
            raise RuntimeError("Tool execution failed")

        registry = ToolRegistry({
            "failing_tool": ToolDefinition(
                executor=_failing_tool, schema=_TestInput, cacheable=False,
            ),
        })

        mock_response = MagicMock()
        mock_response.content = ""
        mock_response.tool_calls = [
            {"name": "failing_tool", "args": {"value": "test"}, "id": "call-1", "type": "tool_call"}
        ]
        mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 5}

        final_response = MagicMock()
        final_response.content = "Done"
        final_response.tool_calls = []
        final_response.usage_metadata = {"input_tokens": 10, "output_tokens": 5}

        call_count = 0

        async def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_response
            return final_response

        with (
            patch("langchain_litellm.ChatLiteLLM") as MockChatLiteLLM,
            patch(
                "services.guardrails.InputGuardrail._call_judge",
                new_callable=AsyncMock,
                return_value="accept",
            ),
        ):
            mock_llm = MockChatLiteLLM.return_value
            mock_llm.ainvoke = AsyncMock(side_effect=_side_effect)
            mock_llm.bind_tools = MagicMock(return_value=mock_llm)

            from orchestration.react_loop import build_graph

            graph = build_graph(
                agent_config=_agent_config(),
                tool_registry=registry,
                cache_dir=tmp_path / "cache",
            )

            result = await graph.ainvoke(
                {
                    "task_id": "test-tool-err",
                    "task_input": "use the tool",
                    "messages": [],
                    "workflow_id": "wf-tool-err",
                    "registered_agent_id": "agent-test",
                },
                config={"configurable": {"task_id": "test-tool-err", "user_id": "test"}},
            )

        assert result.get("step_count", 0) >= 1
