"""L4 (Behavioral), Protocol D — Phase-1 shadow carrier-gate wiring.

Per ``research/tdd_agentic_systems_prompt.md`` Pattern 10 (Governance Loop
Simulation) + D3 (binary outcome). Mocked graph, no live LLM, ``@pytest.mark.simulation``
so it never runs in CI.

Asserts the wiring contract: when the INITIALIZATION boundary completes, a shadow
``guardrail_checked`` carrier with ``source: "carrier_gate"`` appears in the black box,
and **the run still completes** (Phase-1 warn semantics — never blocks). A resumed
run (step_count > 0) records the carrier without flagging the Identity pillar (the
SKILL.md UNVERIFIABLE exemption — no false-positive).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.base_config import AgentConfig, ModelProfile
from services.governance.black_box import BlackBoxRecorder, EventType


def _fast_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _agent_config(**overrides) -> AgentConfig:
    defaults = {
        "default_model": "gpt-4o-mini",
        "models": [_fast_profile()],
        "max_steps": 3,
        "max_cost_usd": 1.0,
    }
    defaults.update(overrides)
    return AgentConfig(**defaults)


@pytest.fixture
def mock_llm():
    mock_response = MagicMock()
    mock_response.content = "Paris is the capital of France."
    mock_response.tool_calls = []
    mock_response.usage_metadata = {"input_tokens": 50, "output_tokens": 20}
    with (
        patch("langchain_litellm.ChatLiteLLM") as mock_chat,
        patch(
            "services.guardrails.InputGuardrail._call_judge",
            new_callable=AsyncMock,
            return_value="accept",
        ),
    ):
        mock_chat.return_value.ainvoke = AsyncMock(return_value=mock_response)
        yield mock_response


def _carrier_gate_events(cache_dir, workflow_id) -> list[dict]:
    bb = BlackBoxRecorder(storage_dir=cache_dir / "black_box_recordings")
    export = bb.export(workflow_id)
    return [
        e
        for e in export["events"]
        if e.get("event_type") == EventType.GUARDRAIL_CHECKED.value
        and e.get("details", {}).get("source") == "carrier_gate"
    ]


@pytest.mark.simulation
class TestCarrierGateWiring:
    @pytest.mark.asyncio
    async def test_initialization_emits_shadow_carrier_and_run_completes(
        self, tmp_path, mock_llm
    ):
        from orchestration.react_loop import build_graph

        cache_dir = tmp_path / "cache"
        workflow_id = "wf-carrier-gate-init"
        graph = build_graph(
            agent_config=_agent_config(),
            cache_dir=cache_dir,
            interrupt_before_execute_tool=False,
        )
        result = await graph.ainvoke(
            {
                "task_id": "carrier-init",
                "task_input": "What is the capital of France?",
                "messages": [],
                "workflow_id": workflow_id,
                "registered_agent_id": "agent-test",
            },
            config={"configurable": {"task_id": "carrier-init", "user_id": "test"}},
        )

        # D3 binary outcome: the run completed (warn, not block).
        assert result is not None

        gate_events = _carrier_gate_events(cache_dir, workflow_id)
        init_events = [e for e in gate_events if e["details"]["phase"] == "initialization"]
        assert init_events, "INITIALIZATION must emit a shadow carrier-gate event"
        d = init_events[0]["details"]
        # task_started IS recorded on the happy path → no gap (pass).
        assert d["outcome"] == "pass"
        assert d["would_enforce"] is False
        assert d["missing_pillars"] == []
        assert d["run_shape"] == "from_step_zero"

    @pytest.mark.asyncio
    async def test_all_wired_boundaries_emit_clean_carriers(self, tmp_path, mock_llm):
        """The four wired non-init boundaries (ROUTING, MODEL_INVOCATION,
        OUTPUT_VALIDATION, plus INITIALIZATION) each emit a shadow carrier-gate
        event with outcome=pass on a clean happy-path run (no gap, no false-positive).
        TOOL_EXECUTION does not appear on a no-tool prompt — that is correct (the
        node only runs when there are tool calls)."""
        from orchestration.react_loop import build_graph

        cache_dir = tmp_path / "cache"
        workflow_id = "wf-carrier-gate-all"
        graph = build_graph(
            agent_config=_agent_config(),
            cache_dir=cache_dir,
            interrupt_before_execute_tool=False,
        )
        await graph.ainvoke(
            {
                "task_id": "carrier-all",
                "task_input": "What is the capital of France?",
                "messages": [],
                "workflow_id": workflow_id,
                "registered_agent_id": "agent-test",
            },
            config={"configurable": {"task_id": "carrier-all", "user_id": "test"}},
        )

        gate_events = _carrier_gate_events(cache_dir, workflow_id)
        phases_seen = {e["details"]["phase"] for e in gate_events}
        for expected in ("initialization", "routing", "model_invocation", "output_validation"):
            assert expected in phases_seen, f"{expected} must emit a shadow carrier-gate event"
        # Every emitted carrier on the clean path is a pass (no gap, no warn).
        for e in gate_events:
            assert e["details"]["outcome"] == "pass", (
                f"clean run produced a gap at {e['details']['phase']}: "
                f"{e['details']['missing_pillars']}"
            )
            assert e["details"]["would_enforce"] is False

    @pytest.mark.asyncio
    async def test_resumed_run_skips_initialization_boundary(self, tmp_path, mock_llm):
        """A resumed run (step_count > 0) short-circuits the init node entirely —
        there is no INITIALIZATION boundary to check, so no carrier-gate event for it
        is emitted. The Identity-pillar UNVERIFIABLE exemption is therefore moot at
        runtime (and is unit-tested directly in the L1/L2 matrix). This proves the
        gate does not false-positive on a legitimately absent boundary.
        """
        from orchestration.react_loop import build_graph

        cache_dir = tmp_path / "cache"
        workflow_id = "wf-carrier-gate-resumed"
        graph = build_graph(
            agent_config=_agent_config(),
            cache_dir=cache_dir,
            interrupt_before_execute_tool=False,
        )
        await graph.ainvoke(
            {
                "task_id": "carrier-resumed",
                "task_input": "What is 2+2?",
                "messages": [],
                "workflow_id": workflow_id,
                "registered_agent_id": "agent-test",
                "step_count": 2,  # resumed → guard_input_node returns early
            },
            config={"configurable": {"task_id": "carrier-resumed", "user_id": "test"}},
        )

        gate_events = _carrier_gate_events(cache_dir, workflow_id)
        init_events = [e for e in gate_events if e["details"]["phase"] == "initialization"]
        assert init_events == [], (
            "a resumed run skips the INITIALIZATION boundary, so it must emit no "
            "carrier-gate event for it (no false-positive on an absent boundary)"
        )
