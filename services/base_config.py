"""Generic configuration consumed by any layer.

NO langgraph or langchain imports allowed.

ModelProfile describes an LLM model's capabilities and costs.
AgentConfig holds global agent-level configuration.
"""

from __future__ import annotations

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
