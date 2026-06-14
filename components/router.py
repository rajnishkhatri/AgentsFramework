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

import re
from typing import Literal

from components.reflexion import decide_reentry
from components.routing_config import RoutingConfig
from services.base_config import AgentConfig, ModelProfile, default_fast_profile

_FAST_TIER = "fast"
_CAPABLE_TIER = "capable"

# Strong single-intent verbs: a *leading* one signals planning work on its own,
# even when the prompt is short and carries no other complexity signal. Without
# this floor, "Plan the Postgres migration." / "Refactor the auth module." score
# at most 1 (a lone multi-part marker) and collapse to L0 — capping the planner
# at one step. Verified against the depth-strata oracle
# (cache/goaljudge_eval/depth_strata_rich.jsonl): these are exactly the L1 rows
# the additive scorer under-scored.
_STRONG_INTENT_VERBS = (
    "plan",
    "design",
    "refactor",
    "audit",
    "migrate",
    "implement",
    "build",
    "investigate",
    "debug",
    "diagnose",
    "optimize",
    "redesign",
    "trace",
    "compare",
)


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


def select_planning_depth(
    *,
    task_input: str,
    task_tool_results_count: int,
) -> tuple[Literal["L0", "L1", "L2"], str]:
    """Pick planning depth level for the current routing decision.

    Levels:
      - ``L0``: Minimal planning for simple or post-tool synthesis turns.
      - ``L1``: Moderate decomposition for medium-complexity requests.
      - ``L2``: Deep decomposition for broad, constrained, or multi-part tasks.

    ``task_tool_results_count`` must be scoped to the **current task**, not the
    underlying LangGraph thread. Using the thread-wide ``step_count`` /
    ``len(state["tool_results"])`` here causes a re-asked task on a long-lived
    thread (saturation runs, multi-turn UIs) to skip the multi-subtask
    heuristic and cap planning at ``L0`` — the agent then executes only one
    subtask and the judge marks the rest as fabricated.
    """
    if task_tool_results_count > 0:
        return "L0", "post-tool-synthesis"

    lowered = (task_input or "").lower()
    words = [part for part in lowered.replace("\n", " ").split(" ") if part]
    word_count = len(words)

    complexity_score = 0
    if word_count >= 35:
        complexity_score += 1
    if word_count >= 80:
        complexity_score += 1

    multi_part_markers = (
        "compare",
        "trade-off",
        "tradeoff",
        "architecture",
        "migration",
        "refactor",
        "roadmap",
        "design",
    )
    has_multi_part_marker = any(
        marker in lowered for marker in multi_part_markers
    )
    if has_multi_part_marker:
        complexity_score += 1

    has_conjunction = any(
        marker in lowered
        for marker in (" and ", " then ", " also ", "\n- ", "\n1.")
    )
    if has_conjunction:
        complexity_score += 1

    if task_input.count("\n") >= 2:
        complexity_score += 1

    if lowered.count("?") >= 2:
        complexity_score += 1

    # Composite imperative chain detector. Explicit enumeration "(1) … (2) …"
    # is a strong, orthogonal signal (subtask count is observably ≥2), so it
    # always contributes. The comma-then-and pattern, however, measures the
    # same underlying property as the conjunction + multi-part-marker
    # signals; double-counting would push architecture-style prompts
    # ("Compare …, design …, and produce …") from their intended L1 into
    # L2. So comma-then-and only fires when the other multi-part signals
    # have not. This still flips GJ-010/011/012 from L0 to L1 (they have no
    # multi-part markers and only the lone " and " trigger), without
    # double-stacking on the existing L1/L2 boundaries.
    if len(re.findall(r"\([1-9]\)", task_input)) >= 2:
        complexity_score += 1
    elif (
        not has_multi_part_marker
        and re.search(r",[^,]+,\s*(?:and|then)\s", lowered) is not None
    ):
        complexity_score += 1

    if complexity_score >= 3:
        return "L2", "high-complexity-initial-task"

    # ── L2 promotion — a long incident/debugging narrative is deep work ──
    # An "it sometimes breaks; figure out where / trace how it propagates /
    # identify every X" prompt (depth:L2:adversarial:bare-complex) carries no
    # enumeration or conjunctions, so the additive scorer tops out at L1 — but
    # the work is L2. This runs BEFORE the score>=2 return so it can promote
    # such a narrative from L1 to L2. Gated on word count (not char length) so
    # a short causal phrase or a long file path can't trip it.
    # Oracle: cache/goaljudge_eval/depth_strata_rich.jsonl (11/11 want==fired).
    incident_markers = (
        "trace how",
        "figure out",
        "root cause",
        "propagat",
        "identify every",
        "times out",
        "sometimes",
        "intermitt",
        "race condition",
    )
    if word_count >= 25 and any(m in lowered for m in incident_markers):
        return "L2", "incident-narrative"

    if complexity_score >= 2:
        return "L1", "moderate-complexity-initial-task"

    # ── L1 floors — recognition the additive scorer misses ──────────────
    # The additive score above rewards *breadth* signals (length, conjunctions,
    # enumeration). Tasks whose complexity is in the *intent* (a single strong
    # verb) score 0-1 and fall through to L0. These floors only fire when the
    # score has NOT already reached L1/L2, so they never override an existing
    # decision — they only rescue under-scored single-step collapses.

    # Floor 1 — a leading strong-intent verb is planning work on its own.
    first_word = words[0] if words else ""
    if first_word in _STRONG_INTENT_VERBS:
        return "L1", "strong-intent-verb"

    # Floor 2 — a long task that produced no other signal is still multi-step
    # work (e.g. an explanatory "walk me through what X does when Y…" prompt).
    # Measured in WORDS, not characters: a single file-create with a long
    # absolute path is short work that must stay L0 (a char-length gate would
    # misclassify it — caught by the fresh-task drift guard).
    if word_count >= 25:
        return "L1", "long-task-floor"

    # Floor 3 — explicit sequencing ("and then" / ", then" / ", and") names
    # two ordered actions: at least L1 ("Add caching and then update the docs").
    if re.search(r"\b(?:and then|, then|, and)\b", lowered) is not None:
        return "L1", "sequenced-multistep"

    return "L0", "simple-initial-task"


EscalationDecision = Literal["escalate", "hold"]


def decide_escalation(
    *,
    goal_verdict: str,            # "success"|"partial"|"failed" (primary, §5)
    unmet_conditions: list[str],
    prose_kind: str,              # "tool_repeat"|"prose_repeat"|"none" (tertiary, §5/D3)
    attempt: int,
    max_attempts: int,
) -> EscalationDecision:
    """Whether any §5 escalation signal fires for the current terminal turn. OBP-2.

    A *pure* predicate over scalars (LP-2: the router imports no
    ``goal_judge``/``evaluator``; the node reads the verdict and passes it in).
    This consolidates the escalation logic Phase 2 wired inline in
    ``_should_continue_or_escalate`` into one named, testable place.

    Budget-first contract (mirrors ``decide_reentry``): at/above the ceiling
    ALWAYS ``hold`` — no signal can override the budget, so the loop can never
    thrash. Below the ceiling the §5 priority order applies:

      - **Primary** — a ``failed``/``partial`` GoalJudge verdict escalates. This
        is the only signal that catches confidently-wrong output (plan §5).
        ``unmet_conditions`` is the evidence carried for the critique; the
        verdict alone decides.
      - **Tertiary (D3)** — a ``prose_repeat`` no-tool thrash escalates even when
        the verdict is clean, catching the OpenManus ``is_stuck`` failure that a
        verdict-only gate misses. ``tool_repeat`` does **not** escalate here: the
        existing ``check_continuation`` backstop already terminates it (it is the
        secondary, *non*-reflexion signal — see plan §5).

    Returns ``"hold"`` for every non-escalating case (the failure paths, AP6).
    """
    # Primary §5 — the verdict-reentry decision is the single source of truth for
    # the budget ceiling. Reusing it (not re-implementing the threshold) keeps
    # one place to change if the ceiling semantics ever move.
    if (
        decide_reentry(
            attempt=attempt, max_attempts=max_attempts, last_verdict=goal_verdict
        )
        == "reflect"
    ):
        return "escalate"
    # Budget already exhausted -> nothing escalates, including a prose thrash.
    if attempt >= max_attempts:
        return "hold"
    # Tertiary §5 / D3 — a prose thrash on an otherwise-clean verdict, budget
    # permitting. (tool_repeat is handled by check_continuation, not here.)
    if prose_kind == "prose_repeat":
        return "escalate"
    return "hold"


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
