"""Gate for the Phase 3 escalation-precision oracle (impl §6.3).

The script ``scripts/measure_escalation_precision.py`` is the operator-facing
diagnostic; this is the CI gate that keeps it honest. It runs the oracle over the
**committed** labelled corpus and asserts the hybrid's escalation half is exactly
right — separately from entry-router accuracy (the other half, measured live by
``diagnose_planning_depth.py``).

Failure-first framing (AP6): the headline assertion is *no mismatches* — a single
false-escalate (thrash risk) or missed-escalate (ships a wrong answer) fails the
gate. Pure, deterministic, no LLM (D2) — Protocol A/C, zero flake.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.measure_escalation_precision import (
    _DEFAULT_CORPUS,
    _load_corpus,
    score_corpus,
)


def test_committed_corpus_scores_perfectly() -> None:
    rows = _load_corpus(_DEFAULT_CORPUS)
    metrics = score_corpus(rows)

    # Headline: zero mismatches — no false escalate, no missed escalate.
    assert metrics["mismatches"] == [], "escalation oracle drifted:\n" + "\n".join(
        metrics["mismatches"]
    )
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    # Both sides of the confusion matrix are exercised (the corpus isn't all-positive).
    assert metrics["tp"] > 0 and metrics["tn"] > 0


def test_corpus_is_balanced_enough_to_be_meaningful() -> None:
    """A precision number over an all-escalate corpus would be vacuous (AP6)."""
    rows = _load_corpus(_DEFAULT_CORPUS)
    wants = [bool(r["want_escalate"]) for r in rows]
    assert any(wants), "corpus has no positive (escalate) rows"
    assert any(not w for w in wants), "corpus has no negative (hold) rows"


def test_corpus_rows_are_well_formed() -> None:
    rows = json.loads(Path(_DEFAULT_CORPUS).read_text())
    required = {
        "case",
        "goal_verdict",
        "prose_kind",
        "attempt",
        "max_attempts",
        "want_escalate",
    }
    for row in rows:
        missing = required - set(row)
        assert not missing, f"row {row.get('case', '?')} missing keys: {missing}"
