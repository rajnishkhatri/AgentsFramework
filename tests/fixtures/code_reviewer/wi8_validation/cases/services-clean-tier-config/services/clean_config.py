"""Clean service config — selects profiles by tier (H2), no trust types."""

from services.base_config import AgentConfig
from services.llm_config import build_model_registry


def config_for_tier(tier: str) -> AgentConfig:
    """Build an AgentConfig whose default model is the first of the given tier.

    H2-respecting: the caller names a *tier* ("fast" / "capable" / "reasoning"),
    never a model name. No trust types, no components import, no langgraph.
    """
    models, default_model = build_model_registry()
    matching = [m for m in models if m.tier == tier]
    if not matching:
        raise ValueError(f"no profile for tier {tier!r}")
    return AgentConfig(default_model=matching[0].name, models=models)
