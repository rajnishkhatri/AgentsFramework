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
