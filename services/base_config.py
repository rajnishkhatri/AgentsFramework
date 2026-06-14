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
