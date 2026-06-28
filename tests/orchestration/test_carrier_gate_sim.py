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


def _enforce_events_from_cache(cache_dir, workflow_id) -> list[dict]:
    bb = BlackBoxRecorder(storage_dir=cache_dir / "black_box_recordings")
    export = bb.export(workflow_id)
    return [
        e
        for e in export["events"]
        if e.get("event_type") == EventType.GUARDRAIL_CHECKED.value
        and e.get("details", {}).get("source") == "carrier_gate_enforce"
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
        init_events = [
            e for e in gate_events if e["details"]["phase"] == "initialization"
        ]
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
        for expected in (
            "initialization",
            "routing",
            "model_invocation",
            "output_validation",
        ):
            assert expected in phases_seen, (
                f"{expected} must emit a shadow carrier-gate event"
            )
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
        init_events = [
            e for e in gate_events if e["details"]["phase"] == "initialization"
        ]
        assert init_events == [], (
            "a resumed run skips the INITIALIZATION boundary, so it must emit no "
            "carrier-gate event for it (no false-positive on an absent boundary)"
        )

    @pytest.mark.asyncio
    async def test_fault_injection_degrade_alerts_end_to_end_through_the_graph(
        self, tmp_path, mock_llm
    ):
        """The live gap-catch proof, through the REAL graph (the deployed path).
        With fault-inject + degrade mode and the magic token, a phase that emitted
        its carrier has it dropped → the gate raises a degrade alert carrier — and
        the run STILL completes (degrade never blocks). This is what the
        fault-injection validation revision exercises."""
        from orchestration.react_loop import build_graph

        cache_dir = tmp_path / "cache"
        workflow_id = "wf-carrier-fault"
        graph = build_graph(
            agent_config=_agent_config(
                carrier_gate_enforce_mode="degrade",
                carrier_gate_fault_inject=True,
            ),
            cache_dir=cache_dir,
            interrupt_before_execute_tool=False,
        )
        result = await graph.ainvoke(
            {
                "task_id": "carrier-fault",
                "task_input": "What is the capital of France? __DROP_CARRIER:initialization__",
                "messages": [],
                "workflow_id": workflow_id,
                "registered_agent_id": "agent-test",
            },
            config={"configurable": {"task_id": "carrier-fault", "user_id": "test"}},
        )

        # Degrade never blocks — the run completed.
        assert result is not None
        # The alarm rang: a loud enforce alert carrier for INITIALIZATION exists.
        enforced = _enforce_events_from_cache(cache_dir, workflow_id)
        init_alerts = [e for e in enforced if e["details"]["phase"] == "initialization"]
        assert init_alerts, "fault injection must produce a carrier_gate_enforce alert"
        assert init_alerts[0]["details"]["action"] == "degrade"
        assert init_alerts[0]["details"]["enforced"] is True


def _enforce_carriers(storage, workflow_id) -> list[dict]:
    bb = BlackBoxRecorder(storage_dir=storage)
    export = bb.export(workflow_id)
    return [
        e
        for e in export["events"]
        if e.get("event_type") == EventType.GUARDRAIL_CHECKED.value
        and e.get("details", {}).get("source") == "carrier_gate_enforce"
    ]


class TestEnforceWiring:
    """Phase 2 — the orchestration shim acts on the gap (deterministic, no graph,
    no LLM; drives ``_shadow_check_phase_carriers`` directly against a real
    recorder). This is the seam where governance's pure decision becomes the
    orchestration action — raise / degrade / nothing."""

    def test_raise_mode_blocks_on_a_real_gap(self, tmp_path):
        from orchestration.react_loop import _shadow_check_phase_carriers
        from services.governance.carrier_gate import CarrierGateViolation
        from services.governance.phase_logger import WorkflowPhase

        bb = BlackBoxRecorder(storage_dir=tmp_path)
        with pytest.raises(CarrierGateViolation):
            # Empty recorded set at a fresh INITIALIZATION ⇒ Identity gap ⇒ raise.
            _shadow_check_phase_carriers(
                bb,
                "wf-raise",
                WorkflowPhase.INITIALIZATION,
                set(),
                step=0,
                enforce_mode="raise",
            )
        # ... and it still left the shadow + enforced carriers (never silent).
        export = bb.export("wf-raise")
        sources = {e["details"].get("source") for e in export["events"]}
        assert "carrier_gate" in sources and "carrier_gate_enforce" in sources

    def test_degrade_mode_records_loud_carrier_but_does_not_raise(self, tmp_path):
        from orchestration.react_loop import _shadow_check_phase_carriers
        from services.governance.phase_logger import WorkflowPhase

        bb = BlackBoxRecorder(storage_dir=tmp_path)
        # No exception — degrade lets the run continue.
        _shadow_check_phase_carriers(
            bb,
            "wf-degrade",
            WorkflowPhase.INITIALIZATION,
            set(),
            step=0,
            enforce_mode="degrade",
        )
        enforced = _enforce_carriers(tmp_path, "wf-degrade")
        assert len(enforced) == 1
        assert enforced[0]["details"]["action"] == "degrade"
        assert enforced[0]["details"]["enforced"] is True

    def test_off_mode_acts_on_nothing(self, tmp_path):
        from orchestration.react_loop import _shadow_check_phase_carriers
        from services.governance.phase_logger import WorkflowPhase

        bb = BlackBoxRecorder(storage_dir=tmp_path)
        _shadow_check_phase_carriers(
            bb,
            "wf-off",
            WorkflowPhase.INITIALIZATION,
            set(),
            step=0,
            enforce_mode="off",
        )
        # Shadow carrier still recorded, but NO enforce carrier (Phase-1 parity).
        assert _enforce_carriers(tmp_path, "wf-off") == []
        export = bb.export("wf-off")
        assert any(
            e["details"].get("source") == "carrier_gate" for e in export["events"]
        )

    def test_clean_phase_never_enforces_even_in_raise_mode(self, tmp_path):
        from orchestration.react_loop import _shadow_check_phase_carriers
        from services.governance.black_box import EventType as ET
        from services.governance.phase_logger import WorkflowPhase

        bb = BlackBoxRecorder(storage_dir=tmp_path)
        # task_started IS present → clean → no raise, no enforce carrier.
        _shadow_check_phase_carriers(
            bb,
            "wf-clean",
            WorkflowPhase.INITIALIZATION,
            {ET.TASK_STARTED.value},
            step=0,
            enforce_mode="raise",
        )
        assert _enforce_carriers(tmp_path, "wf-clean") == []


class TestFaultInjection:
    """The live gap-catch proof: with ``fault_inject`` armed and the magic
    ``__DROP_CARRIER:<phase>__`` token, a phase that DID emit its carrier has it
    suppressed before the check — producing the exact gap the gate exists to catch.
    Proves the alarm actually rings (the 0.000 baseline was 'suspiciously perfect').
    Deterministic, no graph, no LLM."""

    def test_fault_drops_the_carrier_and_gate_raises(self, tmp_path):
        from orchestration.react_loop import _shadow_check_phase_carriers
        from services.governance.black_box import EventType as ET
        from services.governance.carrier_gate import CarrierGateViolation
        from services.governance.phase_logger import WorkflowPhase

        bb = BlackBoxRecorder(storage_dir=tmp_path)
        # The carrier IS present (task_started recorded), but the fault token drops
        # it → the gate sees a gap → raise. This simulates the real seam defect.
        with pytest.raises(CarrierGateViolation):
            _shadow_check_phase_carriers(
                bb,
                "wf-fault-raise",
                WorkflowPhase.INITIALIZATION,
                {ET.TASK_STARTED.value},
                step=0,
                enforce_mode="raise",
                fault_inject=True,
                task_input="please help __DROP_CARRIER:initialization__",
            )
        sources = {
            e["details"].get("source") for e in bb.export("wf-fault-raise")["events"]
        }
        assert "carrier_gate_enforce" in sources, "the alarm must leave a trace"

    def test_fault_drives_degrade_alert_without_blocking(self, tmp_path):
        from orchestration.react_loop import _shadow_check_phase_carriers
        from services.governance.black_box import EventType as ET
        from services.governance.phase_logger import WorkflowPhase

        bb = BlackBoxRecorder(storage_dir=tmp_path)
        # Degrade mode: the fault produces a gap → loud alert carrier, no raise.
        _shadow_check_phase_carriers(
            bb,
            "wf-fault-degrade",
            WorkflowPhase.OUTPUT_VALIDATION,
            {ET.GUARDRAIL_CHECKED.value},
            step=0,
            enforce_mode="degrade",
            fault_inject=True,
            task_input="__DROP_CARRIER:output_validation__ summarize this",
        )
        enf = _enforce_carriers(tmp_path, "wf-fault-degrade")
        assert len(enf) == 1
        assert enf[0]["details"]["action"] == "degrade"
        assert enf[0]["details"]["outcome"] == "alert"

    def test_token_is_inert_without_the_flag(self, tmp_path):
        from orchestration.react_loop import _shadow_check_phase_carriers
        from services.governance.black_box import EventType as ET
        from services.governance.phase_logger import WorkflowPhase

        bb = BlackBoxRecorder(storage_dir=tmp_path)
        # The token in the prompt does NOTHING when the flag is OFF (prod safety):
        # the carrier is present, so no gap, no enforce — even in raise mode.
        _shadow_check_phase_carriers(
            bb,
            "wf-token-inert",
            WorkflowPhase.INITIALIZATION,
            {ET.TASK_STARTED.value},
            step=0,
            enforce_mode="raise",
            fault_inject=False,
            task_input="__DROP_CARRIER:initialization__",
        )
        assert _enforce_carriers(tmp_path, "wf-token-inert") == []

    def test_fault_only_drops_the_named_phase(self, tmp_path):
        from orchestration.react_loop import _shadow_check_phase_carriers
        from services.governance.black_box import EventType as ET
        from services.governance.phase_logger import WorkflowPhase

        bb = BlackBoxRecorder(storage_dir=tmp_path)
        # Token names ROUTING, but we're checking INITIALIZATION → no drop, no gap.
        _shadow_check_phase_carriers(
            bb,
            "wf-other-phase",
            WorkflowPhase.INITIALIZATION,
            {ET.TASK_STARTED.value},
            step=0,
            enforce_mode="raise",
            fault_inject=True,
            task_input="__DROP_CARRIER:routing__",
        )
        assert _enforce_carriers(tmp_path, "wf-other-phase") == []
