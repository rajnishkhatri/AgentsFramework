"""Generic configuration consumed by any layer.

NO langgraph or langchain imports allowed.

ModelProfile describes an LLM model's capabilities and costs.
AgentConfig holds global agent-level configuration.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ModelProfile(BaseModel):
    name: str
    litellm_id: str
    tier: str
    context_window: int
    cost_per_1k_input: float
    cost_per_1k_output: float
    median_latency_ms: float = 1000


class AgentConfig(BaseModel):
    # Identity (E9): surfaced on TASK_STARTED so the trace answers "who did it?"
    # from the first event without a registry round-trip. The registry, when
    # present and verified, refines agent_facts_id to the resolved agent id.
    agent_name: str = "governance-agent"
    agent_version: str = "0.0.0"
    max_steps: int = 20
    max_cost_usd: float = 1.0
    default_model: str = "gpt-4o-mini"
    models: list[ModelProfile] = []
    tool_output_offload_threshold_chars: int = 4000
    tool_output_preview_chars: int = 400
    tool_result_history_limit: int = 100
    trajectory_compaction_token_threshold: int = 3000
    delegation_max_cost_usd: float = 0.5
    delegation_max_calls_per_task: int = 4
    no_progress_repeat_threshold: int = 3
    no_progress_hard_limit: int = 5
    # I2: enable the task-adaptive LLM-as-judge to overlay goal_met/criteria_met
    # onto TaskOutcome. Off by default so CI stays L2-pure (no live LLM); the
    # deterministic keyword heuristic is the fallback when disabled.
    goal_judge_enabled: bool = False
    # Stage 2 rollout: when True, a goal_met=False verdict may downgrade a
    # clean ``success`` outcome to ``partial`` (strictly success->partial).
    # Decoupled from goal_judge_enabled so the judge can run in shadow mode
    # (gather verdicts, change nothing) before the gate is enabled. Default
    # off — stays off until the gold-set production-enable gate is met.
    goal_judge_downgrade_enabled: bool = False
    # Phase 1 (T1 plan-and-execute): source of the route_node plan artifact.
    #   "deterministic" — regex ``build_plan_artifact`` (steady-state, default).
    #   "shadow"        — LLM plan is generated + captured for eval, but the
    #                     deterministic artifact is what the run consumes.
    #   "generated"     — LLM plan is consumed, with ``build_plan_artifact`` as
    #                     the floor on any parse/validation failure.
    # Default stays deterministic so CI is L2-pure (no live LLM) and steady
    # state is unchanged; promote on evidence (GoalJudge shadow->consume idiom).
    plan_source: Literal["deterministic", "shadow", "generated"] = "deterministic"
    # Phase 2 (T2 reflexion): enable the evaluate->reflect->route re-entry loop.
    # When True, a GoalJudge failed/partial verdict (or a D3 prose-thrash) below
    # the budget ceiling writes a verbal critique and re-enters the loop. Off by
    # default — the reflect edge exists in the graph but decide_reentry returns
    # "stop" until flipped, so CI/prod behavior is unchanged (shadow-first, same
    # discipline as plan_source). Promote on evidence.
    reflexion_enabled: bool = False
    # D1: reflexion budget ceiling. decide_reentry returns "stop" once
    # len(reflections) >= this, even on a failed verdict — bounds the loop so
    # it can never thrash (Reflexion, arxiv 2303.11366; thrash-bound sim guard).
    max_reflexion_attempts: int = 2
    # Phase 4 (T3 supervisor fan-out): enable the route->supervisor->worker->join
    # parallel-fan-out fork. When False, _route_to_supervisor always returns
    # "direct" → today's graph EXACTLY (the route->call_llm path is byte-identical).
    # Off by default — same shadow-first discipline as plan_source/reflexion;
    # promote only on parallel-workload evidence (plan §3.5a / §5: don't grow T3
    # without it). The decline decision still bounds fan-out even when enabled.
    t3_fanout_enabled: bool = False
    # T3 fault-injection hook for the stress corpus timing-fault rows. When True,
    # the worker node honors the magic objective tokens __FAULT_TIMEOUT__ /
    # __FAULT_SLOW__ (corpus §4.3a) to exercise the superstep-cancellation /
    # straggler paths. MUST stay OFF in prod — set only on the --tag stress
    # revision (plan §5 Risks: "fault-injection hook leaks to prod").
    fanout_fault_inject: bool = False
    # T3 per-branch wall-clock ceiling (seconds). asyncio.wait_for bounds each
    # worker so one slow/hung branch cannot stall the whole superstep; on timeout
    # the worker records a sentinel and survivors still synthesize.
    fanout_branch_timeout_s: float = 60.0
    # Governance carrier-gate enforcement (enforcement gate Phase 2). The inline
    # gate ALWAYS records a shadow carrier (Phase 1); this field decides whether a
    # missing-pillar gap also ACTS:
    #   "off"     — shadow only; the gap is recorded, nothing blocks (prod parity,
    #               the Phase-1 default; stays here until calibration justifies it).
    #   "raise"   — a gap raises CarrierGateViolation (dev / CI — fail loud so a
    #               seam defect is caught at the source).
    #   "degrade" — a gap is annotated loudly on the trace + run, never silent, but
    #               the run still completes (prod — degrade-not-block).
    # composition.py sets it from CARRIER_GATE_ENFORCE_ENABLED + AGENT_ENV
    # (dev→raise, prod→degrade); default OFF preserves shadow-first discipline —
    # promote only on Phase-1 calibration evidence + explicit approval.
    carrier_gate_enforce_mode: Literal["off", "raise", "degrade"] = "off"
    # Phase 1 memory wiring (docs/plans/memory_layer_wiring.plan.md): wire the
    # orphaned LongTermMemoryService into the loop. When True, route_node recalls
    # the user's relevant memories once per run and injects them into the system
    # prompt, and the run-end path stores a salient memory. Off by default —
    # shadow-first, same discipline as reflexion_enabled/t3_fanout_enabled: with
    # the flag OFF the loop is byte-identical to today (should_recall returns
    # False, no search/store, no carriers). Promote on a dev/stress revision; the
    # injected memory_service is still constructed at the composition root so the
    # graph shape is stable regardless of the flag.
    memory_enabled: bool = False
    # Carrier-gate fault-injection hook (the LIVE gap-catch proof). When True, a
    # task whose input carries the magic token ``__DROP_CARRIER:<phase>__`` has the
    # required carrier for that phase SUPPRESSED before the gate checks it —
    # simulating the exact seam defect the gate exists to catch, so the enforce
    # path (alert carrier + raise/degrade) can be proven end-to-end on a live run.
    # MUST stay OFF in prod (same posture as fanout_fault_inject — a dedicated
    # tagged revision flips it; the magic token is inert without the flag).
    carrier_gate_fault_inject: bool = False


def default_fast_profile() -> ModelProfile:
    """Canonical fast-model profile used as fallback across the system."""
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )
