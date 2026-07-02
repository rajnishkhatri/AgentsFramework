"""L2 Wiring: coach LLM turns land as EvalRecords with target="subject_coach".

Agent design §12.1 Stage-0: shadow traffic accumulates coach traces via the
existing ``eval_capture`` seam (H5 — every LLM call recorded with target +
user_id + task_id). The knob is generic (``AgentConfig.eval_capture_target``),
so the default agent's ``call_llm`` records stay byte-identical.
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


async def _run_and_capture_records(tmp_path, agent_config: AgentConfig) -> list[dict]:
    mock_response = MagicMock()
    mock_response.content = "FINAL ANSWER: ok"
    mock_response.tool_calls = []
    mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 5}

    records: list[dict] = []

    async def _capture_record(**kwargs):
        records.append(kwargs)

    with (
        patch("langchain_litellm.ChatLiteLLM") as MockChatLiteLLM,
        patch(
            "services.guardrails.InputGuardrail._call_judge",
            new_callable=AsyncMock,
            return_value="accept",
        ),
        patch(
            "services.eval_capture.record",
            new=AsyncMock(side_effect=_capture_record),
        ),
    ):
        mock_llm_instance = MockChatLiteLLM.return_value
        mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)

        from orchestration.react_loop import build_graph

        graph = build_graph(
            agent_config=agent_config,
            cache_dir=tmp_path / "cache",
        )
        await graph.ainvoke(
            {
                "task_id": "test-capture",
                "task_input": "Why is this comma wrong?",
                "messages": [],
                "workflow_id": "wf-capture",
                "registered_agent_id": "agent-test",
            },
            config={
                "configurable": {"task_id": "test-capture", "user_id": "learner-1"}
            },
        )
    return records


class TestCoachEvalCaptureTarget:
    @pytest.mark.asyncio
    async def test_coach_turns_record_target_subject_coach(self, tmp_path):
        cfg = AgentConfig(
            default_model="gpt-4o-mini",
            models=[_fast_profile()],
            eval_capture_target="subject_coach",
        )
        records = await _run_and_capture_records(tmp_path, cfg)
        llm_targets = [
            r["target"] for r in records if r["target"] in ("call_llm", "subject_coach")
        ]
        assert llm_targets, "no LLM-call eval record captured"
        assert set(llm_targets) == {"subject_coach"}

    @pytest.mark.asyncio
    async def test_default_agent_target_unchanged(self, tmp_path):
        cfg = AgentConfig(
            default_model="gpt-4o-mini",
            models=[_fast_profile()],
        )
        records = await _run_and_capture_records(tmp_path, cfg)
        llm_targets = [
            r["target"] for r in records if r["target"] in ("call_llm", "subject_coach")
        ]
        assert llm_targets
        assert set(llm_targets) == {"call_llm"}

    def test_coach_factory_sets_capture_target(self):
        from services.governance.subject_coach_identity import (
            subject_coach_agent_config,
        )

        assert subject_coach_agent_config().eval_capture_target == "subject_coach"
