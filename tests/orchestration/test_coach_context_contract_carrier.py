"""L4 Behavioral: the coach-context contract carrier (§13 audit finding F1).

The Phase-1 exit audit found ``coach_context``/mode had ZERO trace carriers:
``task.started.details.task_input`` is last-message-only, so the §13.2
derived-mode step was unauditable and the judge sampler froze every turn at
``pre_submit``. The fix records ONE ``guardrail_checked`` carrier with
``guardrail="coach_context_contract"`` per coach turn — the fail-closed mode
plus which answer-bearing fields rendered/were stripped (ADR-0012 evidence).

Mirrors ``test_capability_gating_carrier``: real ``build_graph`` + ``ainvoke``
with a real on-disk recorder; ChatLiteLLM + the guardrail judge mocked (no
live LLM).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.base_config import AgentConfig, ModelProfile

_ANSWER_FIELDS = {
    "answer_letter",
    "per_choice_rationale",
    "why_correct_md",
    "why_tempted_md",
}

_QUESTION = {
    "id": "q-1",
    "stem": "Which choice best fixes the underlined portion?",
    "choices": [{"letter": "A", "label": "NO CHANGE"}],
    "answer_letter": "B",
    "per_choice_rationale": {"A": "leaves the clause unclosed"},
    "why_correct_md": "closes the clause",
    "why_tempted_md": "reads fine aloud",
}


def _fast_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _read_events(cache_dir: Path, workflow_id: str) -> list[dict]:
    trace_file = cache_dir / "black_box_recordings" / workflow_id / "trace.jsonl"
    if not trace_file.exists():
        return []
    return [
        json.loads(line) for line in trace_file.read_text().strip().split("\n") if line
    ]


def _contract_events(events: list[dict]) -> list[dict]:
    return [
        e
        for e in events
        if e["event_type"] == "guardrail_checked"
        and e["details"].get("guardrail") == "coach_context_contract"
    ]


async def _run(
    tmp_path: Path, workflow_id: str, coach_context: dict[str, Any] | None
) -> list[dict]:
    mock_response = MagicMock()
    mock_response.content = "What does the underlined clause need?"
    mock_response.tool_calls = []
    mock_response.usage_metadata = {"input_tokens": 50, "output_tokens": 20}

    cache_dir = tmp_path / "cache"
    cfg = AgentConfig(default_model="gpt-4o-mini", models=[_fast_profile()])
    state: dict[str, Any] = {
        "task_id": "t",
        "task_input": "Why is this comma wrong?",
        "messages": [],
        "workflow_id": workflow_id,
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
        MockChatLiteLLM.return_value.ainvoke = AsyncMock(return_value=mock_response)

        from orchestration.react_loop import build_graph

        graph = build_graph(agent_config=cfg, cache_dir=cache_dir)
        await graph.ainvoke(
            state,
            config={"configurable": {"task_id": "t", "user_id": "learner-1"}},
        )
    return _read_events(cache_dir, workflow_id)


class TestCoachContextContractCarrier:
    @pytest.mark.asyncio
    async def test_non_coach_run_records_no_contract_carrier(self, tmp_path):
        """Failure path first: no coach_context ⇒ the carrier must NOT appear
        (default-agent traces stay byte-identical)."""
        events = await _run(tmp_path, "wf-default", coach_context=None)
        assert events, "run produced no trace events"
        assert _contract_events(events) == []

    @pytest.mark.asyncio
    async def test_pre_submit_turn_records_mode_and_stripped_fields(self, tmp_path):
        """A payload that evaded the BFF strip is VISIBLE: mode pre_submit,
        nothing rendered, all four answer fields reported stripped."""
        events = await _run(
            tmp_path,
            "wf-pre",
            coach_context={
                "mode": "pre_submit",
                "question_id": "q-1",
                "question": dict(_QUESTION),
            },
        )
        carriers = _contract_events(events)
        assert len(carriers) == 1, "exactly one contract carrier per coach turn"
        details = carriers[0]["details"]
        assert details["mode"] == "pre_submit"
        assert details["answer_fields_rendered"] == []
        assert set(details["answer_fields_stripped"]) == _ANSWER_FIELDS

    @pytest.mark.asyncio
    async def test_post_feedback_turn_records_rendered_fields(self, tmp_path):
        events = await _run(
            tmp_path,
            "wf-post",
            coach_context={
                "mode": "post_feedback",
                "question_id": "q-1",
                "question": dict(_QUESTION),
            },
        )
        carriers = _contract_events(events)
        assert len(carriers) == 1
        details = carriers[0]["details"]
        assert details["mode"] == "post_feedback"
        assert set(details["answer_fields_rendered"]) == _ANSWER_FIELDS
        assert details["answer_fields_stripped"] == []

    @pytest.mark.asyncio
    async def test_spoofed_mode_carrier_reports_pre_submit(self, tmp_path):
        """The carrier records the fail-closed mode the renderer APPLIED,
        never the advisory value the client sent."""
        events = await _run(
            tmp_path,
            "wf-spoof",
            coach_context={
                "mode": "POST_FEEDBACK",
                "question_id": "q-1",
                "question": dict(_QUESTION),
            },
        )
        carriers = _contract_events(events)
        assert len(carriers) == 1
        assert carriers[0]["details"]["mode"] == "pre_submit"
