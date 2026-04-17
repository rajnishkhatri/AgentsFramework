"""Model selection logic (framework-agnostic).

NO langgraph or langchain imports allowed.

Phase 2: ``select_model`` implements a 5-branch MECE decision tree. Branches
are totally ordered — first match wins — so every state tuple maps to exactly
one branch.

Branch order (highest priority first):
  1. Budget pressure       -> fast tier,   reason "budget-downgrade"
  2. Retryable error       -> same model,  reason "retry-after-backoff"
  3. Escalation threshold  -> capable tier, reason "escalate-after-N-failures"
  4. First step (planning) -> capable tier, reason "capable-for-planning"
  5. Default steady state  -> fast tier,    reason "steady-state-fast"
"""

from __future__ import annotations

from components.routing_config import RoutingConfig
from services.base_config import AgentConfig, ModelProfile, default_fast_profile

_FAST_TIER = "fast"
_CAPABLE_TIER = "capable"


def _pick_profile_by_tier(models: list[ModelProfile], tier: str) -> ModelProfile | None:
    for profile in models:
        if profile.tier == tier:
            return profile
    return None


def _fallback_profile(agent_config: AgentConfig, default_name: str) -> ModelProfile:
    """Return a usable ModelProfile when the preferred tier has no entry."""
    if agent_config.models:
        for profile in agent_config.models:
            if profile.name == default_name:
                return profile
        return agent_config.models[0]

    fallback = default_fast_profile()
    if fallback.name != default_name:
        fallback = fallback.model_copy(
            update={"name": default_name, "litellm_id": f"openai/{default_name}"}
        )
    return fallback


def _select_same_model(
    model_history: list[dict],
    agent_config: AgentConfig,
    default_name: str,
) -> ModelProfile:
    """Return the model used most recently; fall back to default if empty."""
    last_name = ""
    for entry in reversed(model_history):
        candidate = entry.get("model") if isinstance(entry, dict) else None
        if candidate:
            last_name = candidate
            break

    for profile in agent_config.models:
        if profile.name == last_name:
            return profile

    return _fallback_profile(agent_config, default_name)


def select_model(
    step_count: int,
    consecutive_errors: int,
    last_error_type: str,
    total_cost_usd: float,
    model_history: list[dict],
    agent_config: AgentConfig,
    routing_config: RoutingConfig,
) -> tuple[ModelProfile, str]:
    """Select a model for the current step. Returns (profile, reason).

    See module docstring for branch ordering.
    """
    default_name = routing_config.default_model
    max_cost = max(agent_config.max_cost_usd, 1e-9)
    cost_fraction = total_cost_usd / max_cost

    # ── Branch 1: budget pressure ────────────────────────────────────
    if cost_fraction >= routing_config.budget_downgrade_threshold:
        fast = _pick_profile_by_tier(agent_config.models, _FAST_TIER)
        chosen = fast or _fallback_profile(agent_config, default_name)
        return chosen, "budget-downgrade"

    # ── Branch 2: retryable error -> retry same model ───────────────
    if last_error_type == "retryable":
        chosen = _select_same_model(model_history, agent_config, default_name)
        return chosen, "retry-after-backoff"

    # ── Branch 3: escalation after N failures ────────────────────────
    escalations_used = sum(
        1
        for entry in model_history
        if isinstance(entry, dict) and entry.get("tier") == _CAPABLE_TIER
    )
    if (
        consecutive_errors >= routing_config.escalate_after_failures
        and escalations_used < routing_config.max_escalations
    ):
        capable = _pick_profile_by_tier(agent_config.models, _CAPABLE_TIER)
        if capable is not None:
            return capable, f"escalate-after-{consecutive_errors}-failures"

    # ── Branch 4: first step — prefer capable tier for planning ──────
    if step_count == 0:
        capable = _pick_profile_by_tier(agent_config.models, _CAPABLE_TIER)
        if capable is not None:
            return capable, "capable-for-planning"

    # ── Branch 5: default steady state — fast tier ───────────────────
    fast = _pick_profile_by_tier(agent_config.models, _FAST_TIER)
    chosen = fast or _fallback_profile(agent_config, default_name)
    return chosen, "steady-state-fast"
