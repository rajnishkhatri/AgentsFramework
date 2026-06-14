"""L1/Protocol-C tests for components/reflexion.py (pure; mocked critique).

Failure-first (AP6): the budget-ceiling ``stop`` rows land BEFORE the under-budget
``reflect`` rows — the ceiling is the headline contract (the loop can never
thrash). ``generate_reflection`` is exercised with an injected callable AND with
the deterministic fallback; assertions are structural, never exact text (AP3).
"""

from __future__ import annotations

import pytest

from components.reflexion import decide_reentry, generate_reflection


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
