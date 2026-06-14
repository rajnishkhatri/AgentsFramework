"""Reflexion critique + re-entry decision (framework-agnostic, Phase 2 / T2).

Two pure functions, both OBP-1/OBP-2 (no ``langgraph`` / ``orchestration`` /
``AgentState`` imports — verified by the dependency-rule test):

- :func:`generate_reflection` turns the unmet success conditions + the last
  answer into a verbal critique (Reflexion's "semantic gradient", arxiv
  2303.11366). The LLM is injected as a plain ``generate`` callable — the only
  boundary — so the orchestration node owns the async LLM invocation and this
  module stays a unit-testable pure function (same split as Phase 1's
  ``build_plan_artifact_llm`` vs ``PlanGenerator``).
- :func:`decide_reentry` is a pure predicate over scalars: at/above the budget
  ceiling -> ``stop`` ALWAYS (even on a failed verdict, D1); below ceiling AND a
  failed/partial verdict -> ``reflect``; otherwise ``stop``.

Splitting "should we reflect" (a deterministic, CI-pure predicate) from
"what is the critique" (the LLM call) keeps the budget ceiling provable without
a model in the loop.
"""

from __future__ import annotations

from typing import Callable, Literal

ReentryDecision = Literal["reflect", "stop"]

__all__ = ["ReentryDecision", "decide_reentry", "generate_reflection"]


# Deterministic critique used when no LLM is injected or the call fails. Built
# from the unmet conditions so the re-entry prompt still carries a concrete,
# actionable gradient rather than a generic "try again".
def _fallback_critique(unmet_conditions: list[str], last_answer: str) -> str:
    unmet = [c.strip() for c in unmet_conditions if c and c.strip()]
    if unmet:
        joined = "; ".join(unmet)
        return (
            "The previous answer did not satisfy these conditions: "
            f"{joined}. Address each one explicitly in the next attempt."
        )
    # No unmet conditions but still routed to reflect (e.g. D3 prose thrash):
    # the answer is not converging — change approach rather than repeat.
    answer = (last_answer or "").strip()
    if answer:
        return (
            "The previous attempt did not make progress toward the goal. "
            "Take a different approach instead of repeating the last response."
        )
    return "No usable answer was produced. Restart the task with a concrete first step."


def generate_reflection(
    *,
    unmet_conditions: list[str],
    last_answer: str,
    generate: Callable[[str], str] | None = None,
) -> str:
    """Produce a verbal critique (the semantic gradient) for the next attempt.

    ``generate`` is the injected critique-LLM callable (the orchestration node's
    boundary). It receives a compact prompt built from the unmet conditions +
    last answer and returns the critique text. On ANY failure (no callable,
    raise, empty result) the deterministic :func:`_fallback_critique` is used —
    the loop always re-enters with a non-empty, actionable critique. Pure
    (AP-5): the only side effect is the injected call.
    """
    if generate is not None:
        try:
            prompt = (
                "You are critiquing a failed task attempt to guide a retry. "
                "Unmet success conditions:\n"
                + "\n".join(f"- {c}" for c in unmet_conditions if c and c.strip())
                + "\n\nPrevious answer:\n"
                + (last_answer or "").strip()
                + "\n\nWrite a brief, specific critique naming what to fix next. "
                "Do not rewrite the answer; only say what was missing and how to "
                "address it."
            )
            critique = str(generate(prompt)).strip()
            if critique:
                return critique
        except Exception:
            pass
    return _fallback_critique(unmet_conditions, last_answer)


def decide_reentry(
    *,
    attempt: int,
    max_attempts: int,
    last_verdict: str,
) -> ReentryDecision:
    """Whether to re-enter the loop for another reflexion attempt (D1).

    Pure predicate over scalars (OBP-2 — reads no AgentState). Failure-first
    contract: at or above the ceiling -> ``stop`` ALWAYS, even on a failed
    verdict (the budget bound can never be overridden by a bad outcome). Below
    the ceiling AND ``last_verdict`` in {failed, partial} -> ``reflect``.
    A ``success`` verdict (or any other value) -> ``stop``.
    """
    if attempt >= max_attempts:
        return "stop"
    if last_verdict in ("failed", "partial"):
        return "reflect"
    return "stop"
