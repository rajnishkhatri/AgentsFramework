"""L1/Protocol-C tests for components/reflexion.py (pure; mocked critique).

Failure-first (AP6): the budget-ceiling ``stop`` rows land BEFORE the under-budget
``reflect`` rows — the ceiling is the headline contract (the loop can never
thrash). ``generate_reflection`` is exercised with an injected callable AND with
the deterministic fallback; assertions are structural, never exact text (AP3).
"""

from __future__ import annotations

import pytest

from components.reflexion import (
    decide_reentry,
    generate_reflection,
    reflections_for_task,
)


# ── decide_reentry: ceiling first (failure-first, D1) ─────────────────────────


@pytest.mark.parametrize("verdict", ["failed", "partial", "success"])
def test_decide_reentry_stops_at_ceiling_even_on_failure(verdict: str) -> None:
    """At/above the budget, ALWAYS stop — a failed verdict cannot override it."""
    assert decide_reentry(attempt=2, max_attempts=2, last_verdict=verdict) == "stop"
    assert decide_reentry(attempt=3, max_attempts=2, last_verdict=verdict) == "stop"


@pytest.mark.parametrize("verdict", ["failed", "partial"])
def test_decide_reentry_reflects_under_budget_on_bad_verdict(verdict: str) -> None:
    assert decide_reentry(attempt=0, max_attempts=2, last_verdict=verdict) == "reflect"
    assert decide_reentry(attempt=1, max_attempts=2, last_verdict=verdict) == "reflect"


@pytest.mark.parametrize("verdict", ["success", "", "unknown"])
def test_decide_reentry_stops_on_non_failure_verdict(verdict: str) -> None:
    """A clean (or unrecognized) verdict never re-enters, even with budget left."""
    assert decide_reentry(attempt=0, max_attempts=2, last_verdict=verdict) == "stop"


def test_decide_reentry_zero_budget_never_reflects() -> None:
    assert decide_reentry(attempt=0, max_attempts=0, last_verdict="failed") == "stop"


# ── generate_reflection ───────────────────────────────────────────────────────


def test_generate_reflection_uses_injected_critique() -> None:
    captured: dict[str, str] = {}

    def fake_llm(prompt: str) -> str:
        captured["prompt"] = prompt
        return "Add the missing migration rollback step."

    critique = generate_reflection(
        unmet_conditions=["migration is reversible"],
        last_answer="Applied the migration.",
        generate=fake_llm,
    )
    assert critique == "Add the missing migration rollback step."
    # The unmet condition and prior answer reached the prompt (structure, AP3).
    assert "migration is reversible" in captured["prompt"]
    assert "Applied the migration." in captured["prompt"]


def test_generate_reflection_falls_back_when_llm_raises() -> None:
    """LLM raises -> deterministic critique that still names the unmet condition."""

    def boom(_prompt: str) -> str:
        raise RuntimeError("critique LLM down")

    critique = generate_reflection(
        unmet_conditions=["the API returns 200"],
        last_answer="It returned 500.",
        generate=boom,
    )
    assert critique.strip()
    assert "the API returns 200" in critique


def test_generate_reflection_falls_back_on_empty_llm_result() -> None:
    critique = generate_reflection(
        unmet_conditions=["x is documented"],
        last_answer="answer",
        generate=lambda _p: "   ",
    )
    assert critique.strip()
    assert "x is documented" in critique


def test_generate_reflection_no_llm_still_nonempty() -> None:
    """No injected callable (the pure default) -> non-empty fallback critique."""
    critique = generate_reflection(
        unmet_conditions=["covers the edge case"], last_answer="partial answer"
    )
    assert critique.strip()
    assert "covers the edge case" in critique


def test_generate_reflection_no_unmet_no_answer_still_nonempty() -> None:
    """D3 path: prose thrash with no unmet conditions still yields a critique."""
    critique = generate_reflection(unmet_conditions=[], last_answer="")
    assert critique.strip()


# ── reflections_for_task: the cross-turn leak guard (task_id memoize) ──────────
#
# reflections is an append-only state channel keyed on the LangGraph thread_id,
# which is REUSED across chat turns, while task_id is minted fresh per turn. Turn
# N's critiques therefore physically survive into Turn N+1's state. Every read
# site (prompt injection + the len()-as-attempt-counter) must filter to the
# CURRENT task_id so a prior turn's failure critique never bleeds into the next
# question. See ADR-0005 / orchestration/state.py:reflections.


def _reflection(task_id: str, critique: str, attempt: int = 0) -> dict:
    return {
        "step_id": attempt,
        "attempt": attempt,
        "critique": critique,
        "unmet_conditions": [],
        "task_id": task_id,
    }


def test_reflections_for_task_excludes_prior_turn_critiques() -> None:
    """THE BUG: a prior turn's (task T1) critique must not surface for task T2."""
    reflections = [
        _reflection("task-T1", "Turn-1 critique: cite a source."),
        _reflection("task-T2", "Turn-2 critique: show the steps."),
    ]
    current = reflections_for_task(reflections, "task-T2")
    critiques = [r["critique"] for r in current]
    assert "Turn-2 critique: show the steps." in critiques
    assert "Turn-1 critique: cite a source." not in critiques
    # And the len()-as-attempt-counter must reflect only THIS turn (1, not 2),
    # so the reflexion budget is not pre-consumed by a foreign turn.
    assert len(current) == 1


def test_reflections_for_task_keeps_same_task_in_order() -> None:
    """Within one turn, every entry is kept, in append order (the gradient)."""
    reflections = [
        _reflection("task-T2", "first", attempt=0),
        _reflection("task-T2", "second", attempt=1),
    ]
    current = reflections_for_task(reflections, "task-T2")
    assert [r["critique"] for r in current] == ["first", "second"]


def test_reflections_for_task_keeps_untagged_legacy_entries_as_current() -> None:
    """Entries with NO recorded task_id (legacy / in-flight, written before this
    guard shipped) are kept as the CURRENT task's — a one-deploy grace (ADR-0005).

    G8 note: this intentionally REVERSES the earlier "exclude untagged" assertion.
    The exclude behavior was unsound — it silently dropped a resumed pre-fix run's
    accumulated gradient AND reset its reflexion budget to 0 (a regression vs the
    pre-guard code that counted all entries). Grace is sound because untagged
    entries exist only transiently: ``reflect_node`` now always stamps a non-empty
    id, so no NEW entry is untagged, and a genuine foreign turn is tagged with a
    different id and still excluded (next assertion)."""
    reflections = [
        {"step_id": 0, "attempt": 0, "critique": "untagged", "unmet_conditions": []},
        _reflection("task-T2", "tagged"),
    ]
    current = reflections_for_task(reflections, "task-T2")
    assert [r["critique"] for r in current] == ["untagged", "tagged"]


def test_reflections_for_task_still_excludes_foreign_tagged_entries() -> None:
    """The grace does NOT weaken the leak guard: an entry tagged with a DIFFERENT,
    non-empty task_id (a real prior turn) is still excluded."""
    reflections = [
        _reflection("task-T1", "prior turn"),
        {"step_id": 1, "critique": "untagged", "unmet_conditions": []},
        _reflection("task-T2", "this turn"),
    ]
    current = reflections_for_task(reflections, "task-T2")
    assert [r["critique"] for r in current] == ["untagged", "this turn"]
    assert "prior turn" not in [r["critique"] for r in current]


def test_reflections_for_task_is_none_safe() -> None:
    """A None channel (cold checkpoint) is treated as empty, not a TypeError."""
    assert reflections_for_task(None, "task-T2") == []


def test_reflections_for_task_empty_and_missing_inputs() -> None:
    assert reflections_for_task([], "task-T2") == []
    # No current task_id (defensive): nothing can be confidently attributed,
    # so return empty rather than leak every entry into an unknown turn. (The
    # writer avoids this by falling back to workflow_id; see reflect_node.)
    assert reflections_for_task([_reflection("task-T1", "x")], "") == []
