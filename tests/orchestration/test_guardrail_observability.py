"""L4 Behavioral: guardrail rail observability (G2).

Proves that the rails leave a record even when they pass cleanly:

* ``call_llm_node`` always emits an output-stage ``guardrail_checked`` event
  (``checked=True``) regardless of clean/blocked/redacted — the "guard who
  showed up and left no log entry" failure mode.
* ``guard_input_node`` threads the cascade ``decision_stage`` into the
  ``prompt_injection`` event so a clean pass is attributable to a rail.

Failure paths (blocked/redacted) are asserted alongside the clean pass so the
event is provable in every outcome, not just the happy one.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.base_config import AgentConfig, ModelProfile


def _fast_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _agent_config() -> AgentConfig:
    return AgentConfig(default_model="gpt-4o-mini", models=[_fast_profile()])


def _read_events(cache_dir: Path, workflow_id: str) -> list[dict]:
    trace_file = cache_dir / "black_box_recordings" / workflow_id / "trace.jsonl"
    if not trace_file.exists():
        return []
    return [
        json.loads(line)
        for line in trace_file.read_text().strip().split("\n")
        if line
    ]


def _guardrail_events(events: list[dict], stage: str | None = None) -> list[dict]:
    out = [e for e in events if e["event_type"] == "guardrail_checked"]
    if stage is not None:
        out = [e for e in out if e["details"].get("stage") == stage]
    return out


async def _run_with_content(content: str, tmp_path: Path, workflow_id: str) -> Path:
    mock_response = MagicMock()
    mock_response.content = content
    mock_response.tool_calls = []
    mock_response.usage_metadata = {"input_tokens": 50, "output_tokens": 20}

    cache_dir = tmp_path / "cache"
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

        graph = build_graph(agent_config=_agent_config(), cache_dir=cache_dir)
        await graph.ainvoke(
            {
                "task_id": "t",
                "task_input": "What is the capital of France?",
                "messages": [],
                "workflow_id": workflow_id,
            },
            config={"configurable": {"task_id": "t", "user_id": "test"}},
        )
    return cache_dir


class TestOutputGuardrailAlwaysObservable:
    @pytest.mark.asyncio
    async def test_clean_output_still_emits_checked_event(self, tmp_path):
        cache_dir = await _run_with_content(
            "Paris is the capital of France.", tmp_path, "wf-clean"
        )
        outputs = _guardrail_events(_read_events(cache_dir, "wf-clean"), stage="output")
        assert len(outputs) >= 1
        first = outputs[0]["details"]
        assert first["checked"] is True
        assert first["blocked"] is False
        assert first["redacted"] is False
        assert first["failed_rules"] == []

    @pytest.mark.asyncio
    async def test_redacted_output_marks_redacted(self, tmp_path):
        cache_dir = await _run_with_content(
            "Contact bob@foo.com for details.", tmp_path, "wf-redact"
        )
        outputs = _guardrail_events(_read_events(cache_dir, "wf-redact"), stage="output")
        assert any(
            e["details"]["checked"] and e["details"]["redacted"] and not e["details"]["blocked"]
            for e in outputs
        )

    @pytest.mark.asyncio
    async def test_blocked_output_marks_blocked(self, tmp_path):
        cache_dir = await _run_with_content(
            "The user's SSN is 123-45-6789.", tmp_path, "wf-block"
        )
        outputs = _guardrail_events(_read_events(cache_dir, "wf-block"), stage="output")
        blocked = [e for e in outputs if e["details"]["blocked"]]
        assert blocked, "blocked output must still emit a checked event"
        assert blocked[0]["details"]["checked"] is True
        assert blocked[0]["details"]["failed_rules"]


class TestInputDecisionStageRecorded:
    @pytest.mark.asyncio
    async def test_prompt_injection_event_carries_decision_stage(self, tmp_path):
        cache_dir = await _run_with_content(
            "Paris is the capital of France.", tmp_path, "wf-stage"
        )
        events = _read_events(cache_dir, "wf-stage")
        inj = [
            e
            for e in _guardrail_events(events)
            if e["details"].get("guardrail") == "prompt_injection"
        ]
        assert len(inj) == 1
        details = inj[0]["details"]
        assert details["accepted"] is True
        # Benign short prompt is owned by the deterministic pre-check.
        assert details["decision_stage"] == "precheck:clean_short"
