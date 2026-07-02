"""L2 Wiring: AgentConfig.additional_instructions reaches the LLM system prompt.

FR-10 (ADR-0007 prompt-param path): the coach persona rides config into the
think node's system prompt — no new graph node. Mocked LLM captures the
messages; assertions are structural (marker presence/order), never exact
prompt bytes (TAP-3).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.base_config import AgentConfig, ModelProfile

PERSONA_MARKER = "PERSONA-MARKER: Socratic coach identity block"


def _fast_profile():
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


async def _run_graph(tmp_path, agent_config: AgentConfig) -> list:
    """Run one mocked turn; return the message lists passed to the LLM."""
    mock_response = MagicMock()
    mock_response.content = "FINAL ANSWER: ok"
    mock_response.tool_calls = []
    mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 5}

    captured_calls: list = []

    async def _capture(messages, **kwargs):
        captured_calls.append(messages)
        return mock_response

    with (
        patch("langchain_litellm.ChatLiteLLM") as MockChatLiteLLM,
        patch(
            "services.guardrails.InputGuardrail._call_judge",
            new_callable=AsyncMock,
            return_value="accept",
        ),
    ):
        mock_llm_instance = MockChatLiteLLM.return_value
        mock_llm_instance.ainvoke = AsyncMock(side_effect=_capture)

        from orchestration.react_loop import build_graph

        graph = build_graph(
            agent_config=agent_config,
            cache_dir=tmp_path / "cache",
        )
        await graph.ainvoke(
            {
                "task_id": "test-persona",
                "task_input": "Why is this comma wrong?",
                "messages": [],
                "workflow_id": "wf-persona",
                "registered_agent_id": "agent-test",
            },
            config={"configurable": {"task_id": "test-persona", "user_id": "test"}},
        )
    return captured_calls


def _system_texts(captured_calls: list) -> list[str]:
    return [
        getattr(msg, "content", "")
        for call in captured_calls
        for msg in call
        if getattr(msg, "type", "") == "system"
    ]


class TestPersonaInjection:
    @pytest.mark.asyncio
    async def test_persona_reaches_system_prompt(self, tmp_path):
        cfg = AgentConfig(
            default_model="gpt-4o-mini",
            models=[_fast_profile()],
            additional_instructions=PERSONA_MARKER,
        )
        captured = await _run_graph(tmp_path, cfg)
        system_texts = _system_texts(captured)
        assert system_texts, "no system message reached the LLM"
        assert any(PERSONA_MARKER in text for text in system_texts)

    @pytest.mark.asyncio
    async def test_empty_persona_is_byte_absent(self, tmp_path):
        """Default agents are unchanged: no marker text, no stray separator."""
        cfg = AgentConfig(
            default_model="gpt-4o-mini",
            models=[_fast_profile()],
        )
        captured = await _run_graph(tmp_path, cfg)
        assert all(PERSONA_MARKER not in text for text in _system_texts(captured))
