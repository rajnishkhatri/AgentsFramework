"""L2 Contract: InstrumentedCheckpointer tests (STORY-412).

These tests close the TAP-1 (tautological-test) gap noted in
``docs/PHASE4_CODE_REVIEW.md`` for STORY-412 by exercising the wrapper
both at the unit level (sync + async, passthrough) and at the
integration level (``build_graph`` + ``MemorySaver``).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.observability import (
    FrameworkTelemetry,
    InstrumentedCheckpointer,
)


class _SyncStub:
    """Minimal synchronous checkpointer stand-in."""

    def __init__(self, *, get_returns: Any = None) -> None:
        self.put_calls: list[tuple[tuple, dict]] = []
        self.get_calls: list[tuple[tuple, dict]] = []
        self._get_returns = get_returns

    def put(self, *args: Any, **kwargs: Any) -> str:
        self.put_calls.append((args, kwargs))
        return "stored"

    def get(self, *args: Any, **kwargs: Any) -> Any:
        self.get_calls.append((args, kwargs))
        return self._get_returns

    def list(self, *args: Any, **kwargs: Any) -> list[str]:
        return ["a", "b"]


class _AsyncStub:
    """Minimal async checkpointer stand-in."""

    def __init__(self, *, get_returns: Any = None) -> None:
        self.aput_calls: list[tuple[tuple, dict]] = []
        self.aget_calls: list[tuple[tuple, dict]] = []
        self._get_returns = get_returns

    async def aput(self, *args: Any, **kwargs: Any) -> str:
        self.aput_calls.append((args, kwargs))
        return "stored"

    async def aget(self, *args: Any, **kwargs: Any) -> Any:
        self.aget_calls.append((args, kwargs))
        return self._get_returns


class TestInstrumentedCheckpointerSync:
    def test_put_increments_checkpoint(self):
        inner = _SyncStub()
        telemetry = FrameworkTelemetry()
        wrapper = InstrumentedCheckpointer(inner, telemetry)

        result = wrapper.put({"checkpoint_id": "c1"})

        assert result == "stored"
        assert telemetry.checkpoint_invocations == 1
        assert telemetry.rollback_invocations == 0
        assert inner.put_calls == [(({"checkpoint_id": "c1"},), {})]

    def test_get_returning_none_does_not_increment(self):
        inner = _SyncStub(get_returns=None)
        telemetry = FrameworkTelemetry()
        wrapper = InstrumentedCheckpointer(inner, telemetry)

        assert wrapper.get({"thread_id": "t1"}) is None
        assert telemetry.rollback_invocations == 0
        assert telemetry.checkpoint_invocations == 0

    def test_get_returning_state_increments_rollback(self):
        inner = _SyncStub(get_returns={"channel_values": {"messages": []}})
        telemetry = FrameworkTelemetry()
        wrapper = InstrumentedCheckpointer(inner, telemetry)

        result = wrapper.get({"thread_id": "t1"})

        assert result is not None
        assert telemetry.rollback_invocations == 1
        assert telemetry.checkpoint_invocations == 0


class TestInstrumentedCheckpointerAsync:
    @pytest.mark.asyncio
    async def test_async_aput_increments(self):
        inner = _AsyncStub()
        telemetry = FrameworkTelemetry()
        wrapper = InstrumentedCheckpointer(inner, telemetry)

        result = await wrapper.aput({"checkpoint_id": "c1"})

        assert result == "stored"
        assert telemetry.checkpoint_invocations == 1
        assert telemetry.rollback_invocations == 0

    @pytest.mark.asyncio
    async def test_async_aget_returning_state_increments_rollback(self):
        inner = _AsyncStub(get_returns={"channel_values": {}})
        telemetry = FrameworkTelemetry()
        wrapper = InstrumentedCheckpointer(inner, telemetry)

        result = await wrapper.aget({"thread_id": "t1"})

        assert result is not None
        assert telemetry.rollback_invocations == 1

    @pytest.mark.asyncio
    async def test_async_aget_returning_none_does_not_increment(self):
        inner = _AsyncStub(get_returns=None)
        telemetry = FrameworkTelemetry()
        wrapper = InstrumentedCheckpointer(inner, telemetry)

        assert await wrapper.aget({"thread_id": "t1"}) is None
        assert telemetry.rollback_invocations == 0


class TestInstrumentedCheckpointerPassthrough:
    def test_passthrough_attribute_access(self):
        """Methods we don't wrap must still work via __getattr__."""
        inner = _SyncStub()
        telemetry = FrameworkTelemetry()
        wrapper = InstrumentedCheckpointer(inner, telemetry)

        assert wrapper.list("anything") == ["a", "b"]
        assert telemetry.checkpoint_invocations == 0
        assert telemetry.rollback_invocations == 0


# ── Integration: build_graph wires the wrapper end-to-end ──────────


class TestBuildGraphTelemetryIntegration:
    """STORY-412 binary outcome: do real graph runs increment counters?"""

    @pytest.mark.asyncio
    async def test_build_graph_wraps_checkpointer_when_telemetry_provided(
        self, tmp_path
    ):
        from langgraph.checkpoint.memory import MemorySaver

        from orchestration.react_loop import build_graph
        from services.base_config import AgentConfig, ModelProfile

        agent_config = AgentConfig(
            default_model="gpt-4o-mini",
            models=[
                ModelProfile(
                    name="gpt-4o-mini",
                    litellm_id="openai/gpt-4o-mini",
                    tier="fast",
                    context_window=128000,
                    cost_per_1k_input=0.00015,
                    cost_per_1k_output=0.0006,
                )
            ],
        )

        mock_response = MagicMock()
        mock_response.content = "FINAL ANSWER: 42"
        mock_response.tool_calls = []
        mock_response.usage_metadata = {
            "input_tokens": 5,
            "output_tokens": 3,
            "total_tokens": 8,
        }
        mock_response.response_metadata = {"model_name": "gpt-4o-mini"}

        telemetry = FrameworkTelemetry()
        checkpointer = MemorySaver()

        with (
            patch("langchain_litellm.ChatLiteLLM") as MockChatLiteLLM,
            patch(
                "services.guardrails.InputGuardrail._call_judge",
                new_callable=AsyncMock,
                return_value="accept",
            ),
        ):
            MockChatLiteLLM.return_value.ainvoke = AsyncMock(
                return_value=mock_response
            )

            graph = build_graph(
                agent_config=agent_config,
                cache_dir=tmp_path / "cache",
                checkpointer=checkpointer,
                telemetry=telemetry,
            )

            await graph.ainvoke(
                {
                    "task_id": "telemetry-test",
                    "task_input": "What is 6 * 7?",
                    "messages": [],
                    "workflow_id": "wf-telem-001",
                    "registered_agent_id": "agent-test",
                },
                config={
                    "configurable": {
                        "task_id": "telemetry-test",
                        "user_id": "test-user",
                        "workflow_id": "wf-telem-001",
                        "thread_id": "thread-telem-001",
                    }
                },
            )

        assert telemetry.checkpoint_invocations >= 1, (
            "Compiled graph with MemorySaver + telemetry must increment "
            "checkpoint_invocations on at least one put() call."
        )

    def test_build_graph_without_telemetry_leaves_checkpointer_unwrapped(self):
        """Backwards compatibility: telemetry param is optional."""
        from langgraph.checkpoint.memory import MemorySaver

        from orchestration.react_loop import build_graph
        from services.base_config import AgentConfig, ModelProfile

        agent_config = AgentConfig(
            default_model="gpt-4o-mini",
            models=[
                ModelProfile(
                    name="gpt-4o-mini",
                    litellm_id="openai/gpt-4o-mini",
                    tier="fast",
                    context_window=128000,
                    cost_per_1k_input=0.00015,
                    cost_per_1k_output=0.0006,
                )
            ],
        )
        checkpointer = MemorySaver()

        graph = build_graph(
            agent_config=agent_config,
            checkpointer=checkpointer,
        )

        assert graph is not None
        assert not isinstance(graph, InstrumentedCheckpointer)
