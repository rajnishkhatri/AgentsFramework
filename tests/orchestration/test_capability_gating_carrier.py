"""L4 Behavioral: the ADR-0007 capability-gating Identity carrier is emitted
per-run under the correct ``workflow_id`` (not at build time into the recorder
root).

Regression for the review finding: the gate evidence carrier was originally
emitted at *build* time with ``workflow_id=""``, so ``BlackBoxRecorder.record()``
wrote ``trace.jsonl`` into the storage ROOT (``storage_dir / "" == storage_dir``),
unreadable by ``export(workflow_id)`` and polluting the root. This test drives a
real ``build_graph`` + ``ainvoke`` with a real on-disk recorder and asserts the
carrier lands in ``black_box_recordings/<workflow_id>/trace.jsonl`` — and NOT in
the storage root — while the privileged tools are excluded from the bound set.

No live LLM: ChatLiteLLM + the guardrail judge are mocked (same discipline as
``test_guardrail_observability``).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from services.base_config import AgentConfig, ModelProfile
from services.tools.registry import ToolDefinition, ToolRegistry


class _Noop(BaseModel):
    pass


def _stub(args: dict) -> str:  # pragma: no cover - tools never execute here
    return "ok"


def _full_registry() -> ToolRegistry:
    """A registry that HAS shell/web_search — the tools a coach must not gain."""
    return ToolRegistry(
        {
            "think": ToolDefinition(executor=_stub, schema=_Noop),
            "file_io": ToolDefinition(executor=_stub, schema=_Noop),
            "shell": ToolDefinition(executor=_stub, schema=_Noop),
            "web_search": ToolDefinition(executor=_stub, schema=_Noop),
        }
    )


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


async def _run_gated(tmp_path: Path, workflow_id: str) -> Path:
    """Drive a capability-gated graph end-to-end with a real on-disk recorder."""
    mock_response = MagicMock()
    mock_response.content = "Paris is the capital of France."
    mock_response.tool_calls = []
    mock_response.usage_metadata = {"input_tokens": 50, "output_tokens": 20}

    cache_dir = tmp_path / "cache"
    cfg = AgentConfig(
        default_model="gpt-4o-mini",
        models=[_fast_profile()],
        capability_gating_enabled=True,
    )
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

        graph = build_graph(
            agent_config=cfg,
            tool_registry=_full_registry(),
            cache_dir=cache_dir,
            bound_capabilities=["think", "file_io"],
        )
        await graph.ainvoke(
            {
                "task_id": "t",
                "task_input": "How do I fix a comma splice?",
                "messages": [],
                "workflow_id": workflow_id,
            },
            config={"configurable": {"task_id": "t", "user_id": "test"}},
        )
    return cache_dir


class TestCapabilityGatingCarrier:
    @pytest.mark.asyncio
    async def test_carrier_lands_in_workflow_trace(self, tmp_path):
        """The declared==bound evidence is recorded under the run's workflow_id."""
        cache_dir = await _run_gated(tmp_path, "wf-gated")
        events = _read_events(cache_dir, "wf-gated")
        gate_events = [
            e
            for e in events
            if e["event_type"] == "guardrail_checked"
            and e["details"].get("guardrail") == "capability_gating"
        ]
        assert len(gate_events) == 1, "exactly one capability_gating carrier per run"
        details = gate_events[0]["details"]
        # declared == bound, and the privileged tools are NOT in the bound set.
        assert set(details["declared_capabilities"]) == {"think", "file_io"}
        assert set(details["bound_tools"]) == {"think", "file_io"}
        assert "shell" not in details["bound_tools"]
        assert "web_search" not in details["bound_tools"]

    @pytest.mark.asyncio
    async def test_carrier_not_written_to_storage_root(self, tmp_path):
        """Regression: a workflow_id="" carrier would write trace.jsonl into the
        recorder root. Assert the root holds only per-workflow subdirs, never a
        stray trace file."""
        cache_dir = await _run_gated(tmp_path, "wf-root-check")
        root = cache_dir / "black_box_recordings"
        assert not (root / "trace.jsonl").exists(), (
            "capability-gating carrier must not be written to the recorder root"
        )
        # The only child that matters is the real workflow directory.
        assert (root / "wf-root-check" / "trace.jsonl").exists()
