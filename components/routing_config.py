"""Domain-specific routing thresholds.

NO langgraph or langchain imports allowed.

In Phase 1, these fields exist but the route node always returns default_model.
In Phase 2, the router reads these thresholds to make routing decisions.
The meta-optimizer (Phase 4) tunes these values.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


def _default_model_name() -> str:
    """The ACTIVE set's default model — one source of truth (H2 registry).

    Reads ``MODEL_PROFILE_SET`` (the same env var every ``build_model_registry``
    call site honors) so a bare ``RoutingConfig()`` tracks whatever profile set
    ``AgentConfig`` was built from. Without this, the factory would resolve the
    *openai* default (``build_model_registry()``'s own no-arg default) regardless
    of the active set — i.e. ``routing_config.default_model`` and
    ``agent_config.models`` would come from two UNSYNCHRONIZED registry reads and
    could disagree (F1/F10: under ``anthropic``/``deepseek``, the field would
    still be ``gpt-4o-mini``, a model not in those sets). Callers that already
    have ``default_model`` in hand should still pass it explicitly
    (``RoutingConfig(default_model=...)``) — that's the primary path and makes the
    data flow legible; this factory is the safety net for bare ``RoutingConfig()``.

    Lazy import (only at instantiation, not module load) keeps routing_config
    free of the llm_config / langchain import graph at the top level, preserving
    the "NO langgraph or langchain imports" invariant for static layering checks.
    """
    import os

    from services.llm_config import build_model_registry

    _, default_model = build_model_registry(
        os.environ.get("MODEL_PROFILE_SET", "openai")
    )
    return default_model


class RoutingConfig(BaseModel):
    default_model: str = Field(default_factory=_default_model_name)
    escalate_after_failures: int = 2
    max_escalations: int = 3
    budget_downgrade_threshold: float = 0.8
