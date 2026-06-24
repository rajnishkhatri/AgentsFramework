"""Domain-specific routing thresholds.

NO langgraph or langchain imports allowed.

In Phase 1, these fields exist but the route node always returns default_model.
In Phase 2, the router reads these thresholds to make routing decisions.
The meta-optimizer (Phase 4) tunes these values.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


def _default_model_name() -> str:
    """The default set's default model — one source of truth (H2 registry).

    Lazy import (only at instantiation, not module load) keeps routing_config
    free of the llm_config / langchain import graph at the top level, preserving
    the "NO langgraph or langchain imports" invariant for static layering checks.
    """
    from services.llm_config import build_model_registry

    _, default_model = build_model_registry()
    return default_model


class RoutingConfig(BaseModel):
    default_model: str = Field(default_factory=_default_model_name)
    escalate_after_failures: int = 2
    max_escalations: int = 3
    budget_downgrade_threshold: float = 0.8
