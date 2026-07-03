"""L2 Wiring: the reviewed hint ladder reaches the coach's system prompt.

Phase 4 (FR-20) closes the Phase-1 gap the Stage-0 audit exposed: the persona
prose said "select and paraphrase a ladder rung" but NO code path fed it one,
so it free-generated (the rule-naming leak class). The orchestrator now
resolves the authored asset (``components.subject_coach_hints``) for the
turn's ``question_id`` and passes the rung dicts to the context formatter —
peer components never import each other (invariant #5).

Failure paths first: no coach_context / unknown question / post_feedback must
all keep the ladder OUT of the prompt.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.base_config import AgentConfig, ModelProfile

# A distinctive authored q-punc-1 rung-1 fragment (components/subject_coach_hints.py).
_RUNG_FRAGMENT = "What job is the phrase 'which opened in 1974' doing"


def _fast_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


async def _system_prompt_for(tmp_path, coach_context: dict[str, Any] | None) -> str:
    mock_response = MagicMock()
    mock_response.content = "What does the clause need?"
    mock_response.tool_calls = []
    mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 5}

    captured: list[Any] = []

    async def _capture(messages, **kwargs):
        captured.append(messages)
        return mock_response

    state: dict[str, Any] = {
        "task_id": "t",
        "task_input": "Give me a nudge on this one?",
        "messages": [],
        "workflow_id": "wf-ladder",
    }
    if coach_context is not None:
        state["coach_context"] = coach_context

    with (
        patch("langchain_litellm.ChatLiteLLM") as MockChatLiteLLM,
        patch(
            "services.guardrails.InputGuardrail._call_judge",
            new_callable=AsyncMock,
            return_value="accept",
        ),
    ):
        MockChatLiteLLM.return_value.ainvoke = AsyncMock(side_effect=_capture)

        from orchestration.react_loop import build_graph

        graph = build_graph(
            agent_config=AgentConfig(
                default_model="gpt-4o-mini", models=[_fast_profile()]
            ),
            cache_dir=tmp_path / "cache",
        )
        await graph.ainvoke(
            state, config={"configurable": {"task_id": "t", "user_id": "u"}}
        )

    assert captured, "LLM was never invoked"
    system = captured[0][0]
    return str(getattr(system, "content", system))


class TestLadderInPrompt:
    @pytest.mark.asyncio
    async def test_no_coach_context_has_no_ladder(self, tmp_path):
        prompt = await _system_prompt_for(tmp_path, None)
        assert "hint ladder" not in prompt

    @pytest.mark.asyncio
    async def test_unknown_question_has_no_ladder(self, tmp_path):
        prompt = await _system_prompt_for(
            tmp_path, {"mode": "pre_submit", "question_id": "q-no-such"}
        )
        assert "hint ladder" not in prompt

    @pytest.mark.asyncio
    async def test_post_feedback_has_no_ladder(self, tmp_path):
        prompt = await _system_prompt_for(
            tmp_path, {"mode": "post_feedback", "question_id": "q-punc-1"}
        )
        assert "hint ladder" not in prompt
        assert _RUNG_FRAGMENT not in prompt

    @pytest.mark.asyncio
    async def test_pre_submit_carries_the_reviewed_ladder(self, tmp_path):
        prompt = await _system_prompt_for(
            tmp_path, {"mode": "pre_submit", "question_id": "q-punc-1"}
        )
        assert "hint ladder" in prompt
        assert _RUNG_FRAGMENT in prompt
        assert "paraphrase" in prompt
