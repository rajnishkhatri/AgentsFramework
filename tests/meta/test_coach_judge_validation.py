"""Task 3.5c — offline replay test for the coach judge-validation scorer.

Failure paths first (TAP-4): FR-1..FR-5 are unwanted-condition guards; FR-6..FR-8
are the reporting/mapping contract. All L1, deterministic, no live LLM — the
scorer replays committed JSON only.

Spec: docs/plan/coach-judge-validation-harness.spec.md
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meta.coach_judge_validation import (
    CoachValidationReport,
    ScorerError,
    load_cases,
    load_verdicts,
    score,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "coach_judge_validation"
CASES = FIXTURES / "cases.jsonl"
PINNED = FIXTURES / "verdicts_pinned.json"


def _report() -> CoachValidationReport:
    cases = load_cases(CASES)
    verdicts = load_verdicts(PINNED)
    # score only the pinned subset (the L1 fixture is a 6-case slice)
    subset = {cid: cases[cid] for cid in verdicts}
    return score(subset, verdicts)


# ── FR-1: unscorable excluded from denominators ────────────────────────────


def test_unscorable_excluded_from_denominators():
    """FR-1: I1 (scorable:false) must not appear in any leakage quadrant."""
    rep = _report()
    total_scored = rep.counts.tp + rep.counts.fp + rep.counts.fn + rep.counts.tn
    # 6 pinned rows, I1 unscorable → at most 5 land in the confusion matrix
    assert total_scored == 5
    assert "I1" in rep.excluded_unscorable


def test_unscorable_case_not_synthesized():
    """FR-1: no fabricated verdict for an unscorable case."""
    rep = _report()
    assert "I1" not in rep.per_axis_results


# ── FR-2: null expected matched only by abstain ────────────────────────────


# A synthetic case that is SCORABLE but expects null leakage (must abstain).
# The real fixture's only null case (I1) is also unscorable, where FR-1 exclusion
# takes precedence; this isolates the FR-2 null-vs-abstain contract on its own.
_NULL_SCORABLE_CASE = {
    "N0": {
        "case_id": "N0",
        "expected": {
            "answer_leakage": None,
            "leak_channel": None,
            "axis_fails": [],
            "axis_passes": [],
            "scorable": True,
        },
    }
}


def test_null_expected_matched_only_by_abstain():
    """FR-2: expected.answer_leakage null is satisfied by abstain, not by false."""
    bad = {
        "N0": {
            "case_id": "N0",
            "judge": "pedagogy",
            "abstained": False,
            "verdict": {**_MIN_PED, "answer_leakage": False},
        }
    }
    rep = score(_NULL_SCORABLE_CASE, bad)
    assert "N0" in rep.null_mismatches


def test_null_expected_ok_when_abstained():
    good = {
        "N0": {"case_id": "N0", "judge": "pedagogy", "abstained": True, "verdict": None}
    }
    rep = score(_NULL_SCORABLE_CASE, good)
    assert rep.null_mismatches == []


# ── FR-3: cases/verdicts mismatch fails loud ───────────────────────────────


def test_verdicts_cases_mismatch_fails_loud():
    """FR-3: a verdict for a case_id absent from the case set is a hard error."""
    cases = load_cases(CASES)
    stray = {
        "ZZ9": {
            "case_id": "ZZ9",
            "judge": "pedagogy",
            "abstained": True,
            "verdict": None,
        }
    }
    with pytest.raises(ScorerError, match="ZZ9"):
        score(cases, stray)


def test_duplicate_case_id_in_verdicts_fails(tmp_path):
    """FR-3 / edge: duplicate case_id must not be last-wins silently."""
    dup = tmp_path / "dup.json"
    dup.write_text(
        json.dumps(
            {
                "model": "x",
                "verdicts": [
                    {
                        "case_id": "A1",
                        "judge": "pedagogy",
                        "abstained": True,
                        "verdict": None,
                    },
                    {
                        "case_id": "A1",
                        "judge": "pedagogy",
                        "abstained": True,
                        "verdict": None,
                    },
                ],
            }
        )
    )
    with pytest.raises(ScorerError, match="duplicate"):
        load_verdicts(dup)


# ── FR-4: H1 ≡ C2 determinism ──────────────────────────────────────────────


def test_h1_c2_determinism_holds_on_pinned():
    """FR-4: byte-identical inputs H1/C2 carry identical pinned verdicts → pass."""
    rep = _report()
    assert rep.determinism_ok is True
    assert rep.determinism_divergence is None


def test_h1_c2_determinism_divergence_fails():
    """FR-4: divergent H1/C2 verdicts must be flagged, naming both ids."""
    cases = load_cases(CASES)
    v = {
        "H1": {
            "case_id": "H1",
            "judge": "pedagogy",
            "abstained": False,
            "verdict": {**_MIN_PED, "answer_leakage": False},
        },
        "C2": {
            "case_id": "C2",
            "judge": "pedagogy",
            "abstained": False,
            "verdict": {**_MIN_PED, "answer_leakage": True},
        },  # diverges
    }
    rep = score({k: cases[k] for k in v}, v)
    assert rep.determinism_ok is False
    assert "H1" in rep.determinism_divergence and "C2" in rep.determinism_divergence


def test_determinism_ignores_rationale_prose():
    """FR-4 refinement: byte-identical inputs may differ only in free-text
    ``rationale`` at temp>0 — that is NOT a decision-bearing divergence, so
    determinism must still hold (else every re-record would falsely fail)."""
    cases = load_cases(CASES)
    v = {
        "H1": {
            "case_id": "H1",
            "judge": "pedagogy",
            "abstained": False,
            "verdict": {
                **_MIN_PED,
                "answer_leakage": False,
                "rationale": "phrasing one",
            },
        },
        "C2": {
            "case_id": "C2",
            "judge": "pedagogy",
            "abstained": False,
            "verdict": {
                **_MIN_PED,
                "answer_leakage": False,
                "rationale": "phrasing two",
            },
        },
    }
    rep = score({k: cases[k] for k in v}, v)
    assert rep.determinism_ok is True
    assert rep.determinism_divergence is None
    # prose-only divergence is surfaced separately, not as a hard failure.
    assert rep.determinism_prose_only is True


def test_determinism_fails_on_scored_field_even_with_prose_diff():
    """FR-4 refinement: a divergence on a SCORED field (a *_pass or
    answer_leakage) still fails, even when rationale also differs."""
    cases = load_cases(CASES)
    v = {
        "H1": {
            "case_id": "H1",
            "judge": "pedagogy",
            "abstained": False,
            "verdict": {**_MIN_PED, "answer_leakage": False, "rationale": "a"},
        },
        "C2": {
            "case_id": "C2",
            "judge": "pedagogy",
            "abstained": False,
            "verdict": {
                **_MIN_PED,
                "mistake_identification_pass": False,  # scored divergence
                "answer_leakage": False,
                "rationale": "b",
            },
        },
    }
    rep = score({k: cases[k] for k in v}, v)
    assert rep.determinism_ok is False
    assert "mistake_identification_pass" in rep.determinism_divergence
    assert rep.determinism_prose_only is False


# ── FR-5: control regression ───────────────────────────────────────────────


def test_control_leakage_regression_fails():
    """FR-5: a control case recorded leakage=true must be flagged by name."""
    cases = load_cases(CASES)
    v = {
        "G4": {
            "case_id": "G4",
            "judge": "pedagogy",
            "abstained": False,
            "verdict": {**_MIN_PED, "answer_leakage": True},
        },  # control regressed
    }
    rep = score({"G4": cases["G4"]}, v)
    assert "G4" in rep.control_regressions


def test_controls_clean_on_pinned():
    rep = _report()
    assert rep.control_regressions == []


# ── FR-6: rates report raw counts ──────────────────────────────────────────


def test_leakage_rates_report_raw_counts():
    """FR-6: the report exposes tp/fp/fn/tn alongside the rates."""
    rep = _report()
    assert hasattr(rep.counts, "tp")
    # pinned: A1 leak-true→judge true (tp=1); C1,C2,H1,G4 leak-false→judge false (tn=4)
    assert rep.counts.tp == 1
    assert rep.counts.tn == 4
    assert rep.counts.fp == 0 and rep.counts.fn == 0
    assert rep.rates.tpr == 1.0 and rep.rates.tnr == 1.0


# ── FR-7: undecidable rate is None not 0.0 ─────────────────────────────────


def test_undecidable_rate_is_none_not_zero():
    """FR-7: with no gold-positive cases, TPR is None (AP-6), never 0.0."""
    cases = load_cases(CASES)
    # G4 alone: a single leak-false control → zero gold-positives
    v = {
        "G4": {
            "case_id": "G4",
            "judge": "pedagogy",
            "abstained": False,
            "verdict": {**_MIN_PED, "answer_leakage": False},
        }
    }
    rep = score({"G4": cases["G4"]}, v)
    assert rep.rates.tpr is None
    assert rep.rates.tnr == 1.0


# ── FR-8: axis mapping to binary *_pass companion ──────────────────────────


def test_axis_fail_maps_to_pass_false():
    """FR-8: expected.axis_fails:[X] ⇒ verdict.X_pass must be False."""
    rep = _report()
    # C1 expects illusion_of_competence in axis_fails; pinned verdict has it False → match
    c1 = rep.per_axis_results["C1"]
    assert c1["illusion_of_competence"] == "match"


def test_axis_fail_mismatch_detected():
    cases = load_cases(CASES)
    # C1 expects illusion_of_competence fail; give it a passing verdict → mismatch
    v = {
        "C1": {
            "case_id": "C1",
            "judge": "pedagogy",
            "abstained": False,
            "verdict": {
                **_MIN_PED,
                "illusion_of_competence_pass": True,
                "answer_leakage": False,
            },
        }
    }
    rep = score({"C1": cases["C1"]}, v)
    assert rep.per_axis_results["C1"]["illusion_of_competence"] == "mismatch"


def test_axis_pass_maps_to_pass_true():
    """FR-8: expected.axis_passes:[X] ⇒ verdict.X_pass must be True."""
    rep = _report()
    # C2 expects illusion_of_competence in axis_passes; pinned verdict True → match
    assert rep.per_axis_results["C2"]["illusion_of_competence"] == "match"


def test_unlisted_axes_unconstrained():
    """FR-8: axes in neither list are not graded (absent from per-axis results)."""
    rep = _report()
    # G4 lists no axes → it is unconstrained, so it carries no per-axis entry.
    assert "G4" not in rep.per_axis_results


# ── FR-11: CI replay does not gate on leak rate ────────────────────────────


def test_report_carries_no_pass_fail_gate():
    """FR-11: the report reports rates; it exposes no boolean leak-rate gate."""
    rep = _report()
    assert not hasattr(rep, "leak_gate_passed")


# minimal valid PedagogyVerdict body (all passes true, no leak) for constructing
# targeted verdicts in tests
_MIN_PED = {
    "mistake_identification": 0.6,
    "mistake_location": 0.6,
    "actionability": 0.6,
    "coherence": 0.6,
    "productive_struggle": 0.6,
    "illusion_of_competence": 0.6,
    "mistake_identification_pass": True,
    "mistake_location_pass": True,
    "actionability_pass": True,
    "coherence_pass": True,
    "productive_struggle_pass": True,
    "illusion_of_competence_pass": True,
    "rationale": "test",
}
