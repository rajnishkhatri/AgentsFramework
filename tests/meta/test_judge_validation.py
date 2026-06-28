"""L1 tests for ``meta/judge_validation.py`` (Track B-1).

Pyramid layer:   L1 Deterministic -- pure functions, no I/O, no LLM.
Plan:            docs/plan/agentic_engineering_harness_adoption.plan.md Track B-1.

Failure paths first (per research/tdd_agentic_systems_prompt.md), then golden
numbers (pinned against the audit §4 shadow multiset, the SAME anchor
test_goaljudge_calibration.py uses -- if the two disagree, one is wrong), then
the Rogan-Gladen contract and the validation gate.
"""

from __future__ import annotations

import json

import pytest

from meta.judge_validation import (
    DEFAULT_TNR_MIN,
    DEFAULT_TPR_MIN,
    JudgeRates,
    judge_rates,
    position_bias,
    rogan_gladen,
    validate_judge,
)
from meta.judge_validation import test_retest as retest  # aliased: not a test fn
from services.governance.goaljudge_calibration import ConfusionCounts


# ───────────────────────────────────────────────────────────────────────────
# Fixtures -- the audit §4 production-shadow multiset (positive = not-met)
# ───────────────────────────────────────────────────────────────────────────


def _shadow_pairs() -> tuple[dict[str, bool], dict[str, bool]]:
    """69 TP / 8 FP / 8 FN / 12 TN as (judge, gold) item maps (True = met)."""
    judge: dict[str, bool] = {}
    gold: dict[str, bool] = {}
    i = 0
    for n, (j, g) in [
        (69, (False, False)),  # tp: judge not-met, gold not-met
        (8, (False, True)),  # fp: judge not-met, gold met (false downgrade)
        (8, (True, False)),  # fn: judge met, gold not-met (missed failure)
        (12, (True, True)),  # tn: judge met, gold met
    ]:
        for _ in range(n):
            judge[f"GJ-X-{i:03d}"] = j
            gold[f"GJ-X-{i:03d}"] = g
            i += 1
    return judge, gold


# ───────────────────────────────────────────────────────────────────────────
# judge_rates -- undecidable (failure paths first)
# ───────────────────────────────────────────────────────────────────────────


def test_rates_no_gold_positives_tpr_undecidable() -> None:
    """No real failures (tp+fn == 0) -> TPR/FNR undecidable, not 0.0."""
    rates = judge_rates(ConfusionCounts(tp=0, fp=3, fn=0, tn=5))
    assert rates.tpr is None
    assert rates.fnr is None
    # The negative class still has data -> TNR/FPR are decidable.
    assert rates.tnr == pytest.approx(5 / 8)
    assert rates.fpr == pytest.approx(3 / 8)


def test_rates_no_gold_negatives_tnr_undecidable() -> None:
    """No clean runs (tn+fp == 0) -> TNR/FPR undecidable, not 0.0."""
    rates = judge_rates(ConfusionCounts(tp=4, fp=0, fn=1, tn=0))
    assert rates.tnr is None
    assert rates.fpr is None
    assert rates.tpr == pytest.approx(4 / 5)
    assert rates.fnr == pytest.approx(1 / 5)


# ───────────────────────────────────────────────────────────────────────────
# judge_rates -- golden numbers + complements
# ───────────────────────────────────────────────────────────────────────────


def test_rates_shadow_golden_numbers() -> None:
    """Pinned against audit §4: TPR = 69/77, TNR = 12/20."""
    rates = judge_rates(ConfusionCounts(tp=69, fp=8, fn=8, tn=12))
    assert rates.tpr == pytest.approx(69 / 77)
    assert rates.tnr == pytest.approx(12 / 20)
    assert rates.fpr == pytest.approx(8 / 20)
    assert rates.fnr == pytest.approx(8 / 77)


def test_rates_complements_sum_to_one() -> None:
    """TPR+FNR == 1 and TNR+FPR == 1 by construction."""
    rates = judge_rates(ConfusionCounts(tp=69, fp=8, fn=8, tn=12))
    assert rates.tpr is not None and rates.fnr is not None
    assert rates.tnr is not None and rates.fpr is not None
    assert rates.tpr + rates.fnr == pytest.approx(1.0)
    assert rates.tnr + rates.fpr == pytest.approx(1.0)


def test_tnr_is_one_minus_false_downgrade_rate() -> None:
    """TNR must equal 1 - the calibration module's false_downgrade_rate."""
    from services.governance.goaljudge_calibration import precision_recall_fd

    counts = ConfusionCounts(tp=69, fp=8, fn=8, tn=12)
    tnr = judge_rates(counts).tnr
    fd = precision_recall_fd(counts).false_downgrade_rate
    assert tnr is not None and fd is not None
    assert tnr == pytest.approx(1.0 - fd)


# ───────────────────────────────────────────────────────────────────────────
# rogan_gladen
# ───────────────────────────────────────────────────────────────────────────


def test_rogan_gladen_perfect_judge_is_identity() -> None:
    """TPR=1, FPR=0 -> the correction returns the observed prevalence unchanged."""
    rg = rogan_gladen(0.4, tpr=1.0, fpr=0.0)
    assert rg.corrected == pytest.approx(0.4)
    assert not rg.clamped


def test_rogan_gladen_corrects_for_imperfect_judge() -> None:
    """(obs - FPR) / (TPR - FPR): a known hand-computed value."""
    # obs=0.5, TPR=0.9, FPR=0.1 -> (0.5-0.1)/(0.9-0.1) = 0.4/0.8 = 0.5
    rg = rogan_gladen(0.5, tpr=0.9, fpr=0.1)
    assert rg.corrected == pytest.approx(0.5)
    # obs above the FPR floor but judge over-flags -> corrected < observed.
    rg2 = rogan_gladen(0.3, tpr=0.9, fpr=0.1)
    assert rg2.corrected == pytest.approx(0.25)
    assert rg2.corrected is not None and rg2.corrected < 0.3


def test_rogan_gladen_no_discriminative_power_undecidable() -> None:
    """TPR == FPR -> denominator vanishes -> corrected is None (never 0.0)."""
    rg = rogan_gladen(0.5, tpr=0.5, fpr=0.5)
    assert rg.corrected is None
    assert rg.corrected_raw is None


def test_rogan_gladen_missing_rate_undecidable() -> None:
    rg = rogan_gladen(0.5, tpr=None, fpr=0.1)
    assert rg.corrected is None


def test_rogan_gladen_clamps_out_of_range_estimate() -> None:
    """An observed rate below FPR yields a negative raw estimate -> clamp to 0."""
    rg = rogan_gladen(0.05, tpr=0.9, fpr=0.1)
    assert rg.corrected_raw is not None and rg.corrected_raw < 0.0
    assert rg.corrected == 0.0
    assert rg.clamped


def test_rogan_gladen_rejects_out_of_range_observed() -> None:
    with pytest.raises(ValueError, match="observed_prevalence"):
        rogan_gladen(1.5, tpr=0.9, fpr=0.1)


# ───────────────────────────────────────────────────────────────────────────
# validate_judge -- the gate
# ───────────────────────────────────────────────────────────────────────────


def test_validate_judge_shadow_fails_default_floor() -> None:
    """The shadow judge (TPR=0.896, TNR=0.60) fails the symmetric 90% floor."""
    judge, gold = _shadow_pairs()
    result = validate_judge(judge, gold)
    assert not result.passed
    # Both rates are below 0.90 -> two reasons.
    assert result.rates.tpr is not None and result.rates.tpr < DEFAULT_TPR_MIN
    assert result.rates.tnr is not None and result.rates.tnr < DEFAULT_TNR_MIN
    assert any("TPR" in r for r in result.reasons)
    assert any("TNR" in r for r in result.reasons)


def test_validate_judge_passes_when_both_floors_met() -> None:
    judge = {f"i{n}": (n % 10 == 0) for n in range(100)}  # judge: 10 met, 90 not
    gold = dict(judge)  # perfect agreement -> TPR=TNR=1.0
    result = validate_judge(judge, gold)
    assert result.passed
    assert result.reasons == ()
    assert result.rates.tpr == pytest.approx(1.0)
    assert result.rates.tnr == pytest.approx(1.0)


def test_validate_judge_undecidable_rate_fails_closed() -> None:
    """All-clean gold (no real failures) -> TPR undecidable -> gate FAILS."""
    judge = {f"i{n}": True for n in range(10)}
    gold = {f"i{n}": True for n in range(10)}
    result = validate_judge(judge, gold)
    assert not result.passed
    assert any("undecidable" in r for r in result.reasons)


def test_validate_judge_mismatched_keys_raises() -> None:
    """An unaligned key set is an upstream join bug -- never a silent drop."""
    with pytest.raises(ValueError):
        validate_judge({"a": True}, {"b": False})


def test_validate_judge_custom_asymmetric_floors() -> None:
    """Asymmetric cost: a high-recall judge can pass a relaxed TNR floor."""
    judge, gold = _shadow_pairs()  # TPR ~0.896, TNR 0.60
    # Relax both below the shadow values -> should pass.
    result = validate_judge(judge, gold, tpr_min=0.85, tnr_min=0.55)
    assert result.passed


def test_default_floors_are_symmetric_ninety() -> None:
    assert DEFAULT_TPR_MIN == 0.90
    assert DEFAULT_TNR_MIN == 0.90


def test_judge_rates_returns_named_tuple() -> None:
    """Stable public shape for downstream report builders."""
    rates = judge_rates(ConfusionCounts(tp=1, fp=1, fn=1, tn=1))
    assert isinstance(rates, JudgeRates)
    assert rates._fields == ("tpr", "tnr", "fpr", "fnr")


def test_validation_cli_rejects_partial_judge_coverage(tmp_path) -> None:
    """Judge file missing seed items must fail loud — not PASS on a thin subset."""
    from meta.judge_validation import run_validation_cli

    seed = {
        "rows": [
            {"item_id": "a", "adjudicated": "met"},
            {"item_id": "b", "adjudicated": "not_met"},
        ]
    }
    judge = {"a": {"goal_met": True}}
    seed_path = tmp_path / "seed.json"
    judge_path = tmp_path / "judge.json"
    seed_path.write_text(json.dumps(seed))
    judge_path.write_text(json.dumps(judge))
    rc = run_validation_cli(
        ["--seed", str(seed_path), "--judge", str(judge_path), "--mapping", "strict"]
    )
    assert rc == 2


# ── test-retest reliability ─────────────────────────────────────────────────


class TestTestRetest:
    def test_unanimous_items_are_fully_consistent(self):
        r = retest({"a": [True, True, True], "b": [False, False]})
        assert r.n_items == 2
        assert r.consistency == 1.0
        assert r.mean_majority_fraction == 1.0
        assert r.flipped == ()

    def test_flipped_item_is_flagged(self):
        # 'b' disagrees across trials (2 True / 3 False) -> a flip.
        r = retest({"a": [True, True], "b": [True, False, False]})
        assert r.consistency == 0.5
        assert r.flipped == ("b",)
        # majority fraction: a=1.0, b=2/3 -> mean ~0.8333
        assert r.mean_majority_fraction == pytest.approx(0.8333, abs=1e-3)

    def test_single_trial_items_are_skipped(self):
        # An item with one trial gives no retest signal -> excluded, not counted.
        r = retest({"a": [True], "b": [True, True]})
        assert r.n_items == 1
        assert r.consistency == 1.0

    def test_no_eligible_items_returns_none(self):
        r = retest({"a": [True], "b": []})
        assert r.n_items == 0
        assert r.consistency is None
        assert r.mean_majority_fraction is None


# ── position bias (pairwise only) ───────────────────────────────────────────


class TestPositionBias:
    def test_invariant_judge_full_agreement(self):
        # winner-invariant: chose_first flips when slots swap -> opposite verdicts.
        pb = position_bias({"x": True, "y": False}, {"x": False, "y": True})
        assert pb.n_items == 2
        assert pb.agreement == 1.0
        assert pb.inconsistent == ()
        # each item: one first-pick across the two presentations -> 0.5.
        assert pb.first_position_rate == 0.5

    def test_order_dependent_item_is_inconsistent(self):
        # 'x' picks the first slot BOTH ways -> order-dependent (biased).
        pb = position_bias({"x": True, "y": False}, {"x": True, "y": True})
        assert pb.inconsistent == ("x",)
        assert pb.agreement == 0.5
        # x contributes 2 first-picks, y contributes 1 -> 3/4.
        assert pb.first_position_rate == 0.75

    def test_misaligned_keys_return_none(self):
        pb = position_bias({"x": True}, {"y": False})
        assert pb.agreement is None
        assert pb.first_position_rate is None

    def test_empty_returns_none(self):
        pb = position_bias({}, {})
        assert pb.agreement is None
