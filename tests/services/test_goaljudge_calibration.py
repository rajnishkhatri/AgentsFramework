"""L1 tests for ``services/governance/goaljudge_calibration.py`` (Stage 6 Phase 1).

Pyramid layer:   L1 Deterministic — pure functions, no I/O, no LLM.
Plan:            docs/plans/goaljudge_stage6_calibration.plan.md §5–§6 Phase 1.
Audit anchor:    docs/research/goaljudge_stage6_replay_audit.md §4 — the
                 production-shadow confusion counts (TP=69, FP=8, FN=8, TN=12,
                 n=97) are pinned here as golden numbers; if module math ever
                 disagrees with the audit doc, one of them is wrong.

Failure paths first (per research/tdd_agentic_systems_prompt.md), then golden
numbers, then the §2.8 gate evaluator's fail-closed contract.
"""

from __future__ import annotations

import math

import pytest

from services.governance.goaljudge_calibration import (
    ConfusionCounts,
    GateDecision,
    confusion_counts,
    evaluate_section_2_8_gates,
    expected_calibration_error,
    flip_rate,
    judge_gold_kappa,
    precision_recall_fd,
)
from services.governance.goaljudge_goldset_dataset import AssemblyInvariantError


# ───────────────────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────────────────


def _shadow_pairs() -> tuple[dict[str, bool], dict[str, bool]]:
    """The audit §4 production-shadow multiset as (judge, gold) dicts.

    69 × (judge not-met, gold not-met)   — TP
     8 × (judge not-met, gold met)       — FP (false downgrade)
     8 × (judge met,     gold not-met)   — FN
    12 × (judge met,     gold met)       — TN
    """
    judge: dict[str, bool] = {}
    gold: dict[str, bool] = {}
    i = 0
    for n, (j, g) in [(69, (False, False)), (8, (False, True)),
                      (8, (True, False)), (12, (True, True))]:
        for _ in range(n):
            judge[f"GJ-X-{i:03d}"] = j
            gold[f"GJ-X-{i:03d}"] = g
            i += 1
    return judge, gold


def _v1_manifest(**overrides: object) -> dict[str, object]:
    """Minimal manifest that passes ``gate_goldset_v1_floors``."""
    base: dict[str, object] = {
        "dataset_name": "goaljudge_goldset_v1",
        "total_items": 250,
        "test_count": 200,
        "test_split_sha256": "deadbeef" * 8,
        "rubric_version": "stage4_confirmed",
        "frozen_at": "2026-06-12T00:00:00Z",
        "provisional": False,
        "floor_gap_summary": {},
    }
    base.update(overrides)
    return base


_PASSING = dict(
    precision=0.95, recall=0.85, false_downgrade_rate=0.01,
    kappa=0.75, flip=0.02,
)


# ───────────────────────────────────────────────────────────────────────────
# confusion_counts
# ───────────────────────────────────────────────────────────────────────────


class TestConfusionCounts:
    """Positive class = the judge saying not-met (the downgrade signal):
    TP = judge False ∧ gold False."""

    # ── Failure paths ─────────────────────────────────────────────────────

    def test_empty_inputs_raise(self) -> None:
        with pytest.raises(ValueError, match=r"(?i)empty"):
            confusion_counts({}, {})

    def test_keyset_mismatch_raises(self) -> None:
        """The caller filters; this function never guesses an intersection.
        A judge verdict without a gold label (or vice versa) is a bug
        upstream, not a row to silently drop."""
        with pytest.raises(ValueError, match=r"(?i)key"):
            confusion_counts({"a": True, "b": False}, {"a": True})

    def test_extra_gold_key_raises(self) -> None:
        with pytest.raises(ValueError, match=r"(?i)key"):
            confusion_counts({"a": True}, {"a": True, "b": False})

    # ── Golden numbers ────────────────────────────────────────────────────

    def test_all_four_quadrants(self) -> None:
        judge = {"tp": False, "fp": False, "fn": True, "tn": True}
        gold = {"tp": False, "fp": True, "fn": False, "tn": True}
        assert confusion_counts(judge, gold) == ConfusionCounts(
            tp=1, fp=1, fn=1, tn=1
        )

    def test_shadow_fixture_counts(self) -> None:
        """Audit §4: TP=69 FP=8 FN=8 TN=12 over n=97."""
        judge, gold = _shadow_pairs()
        counts = confusion_counts(judge, gold)
        assert counts == ConfusionCounts(tp=69, fp=8, fn=8, tn=12)
        assert counts.tp + counts.fp + counts.fn + counts.tn == 97


# ───────────────────────────────────────────────────────────────────────────
# precision_recall_fd
# ───────────────────────────────────────────────────────────────────────────


class TestPrecisionRecallFd:
    # ── Degenerate denominators return None, never 0.0 and never raise ───
    # (0.0 would be a real claim — e.g. "precision is terrible" — about a
    # quadrant that has no data. AP-6 gap blindness.)

    def test_no_positive_predictions_precision_none(self) -> None:
        m = precision_recall_fd(ConfusionCounts(tp=0, fp=0, fn=3, tn=5))
        assert m.precision is None
        assert m.recall == 0.0

    def test_no_gold_negatives_recall_none(self) -> None:
        m = precision_recall_fd(ConfusionCounts(tp=0, fp=2, fn=0, tn=5))
        assert m.recall is None

    def test_no_gold_positives_fd_none(self) -> None:
        """No gold-met rows ⇒ the false-downgrade rate has no denominator.
        This is exactly the v0.9 hazard the plan §5 names (only ~20 gold-met
        rows) taken to its limit."""
        m = precision_recall_fd(ConfusionCounts(tp=4, fp=0, fn=2, tn=0))
        assert m.false_downgrade_rate is None

    # ── Golden numbers ────────────────────────────────────────────────────

    def test_shadow_fixture_metrics(self) -> None:
        """Audit §4: precision = recall = 69/77, FD = 8/20."""
        m = precision_recall_fd(ConfusionCounts(tp=69, fp=8, fn=8, tn=12))
        assert m.precision == pytest.approx(0.896104, abs=1e-6)
        assert m.recall == pytest.approx(0.896104, abs=1e-6)
        assert m.false_downgrade_rate == pytest.approx(0.4, abs=1e-12)

    def test_perfect_judge(self) -> None:
        m = precision_recall_fd(ConfusionCounts(tp=10, fp=0, fn=0, tn=10))
        assert m.precision == 1.0
        assert m.recall == 1.0
        assert m.false_downgrade_rate == 0.0


# ───────────────────────────────────────────────────────────────────────────
# judge_gold_kappa
# ───────────────────────────────────────────────────────────────────────────


class TestJudgeGoldKappa:
    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match=r"(?i)empty"):
            judge_gold_kappa({}, {})

    def test_keyset_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match=r"(?i)key"):
            judge_gold_kappa({"a": True}, {"b": True})

    def test_single_class_is_nan(self) -> None:
        """All four ratings the same class ⇒ chance agreement is undefined;
        NaN per the iaa.krippendorff_alpha_nominal contract, never 1.0."""
        judge = {"a": True, "b": True}
        gold = {"a": True, "b": True}
        assert math.isnan(judge_gold_kappa(judge, gold))

    def test_perfect_agreement_two_classes(self) -> None:
        judge = {"a": True, "b": False}
        gold = {"a": True, "b": False}
        assert judge_gold_kappa(judge, gold) == 1.0

    def test_shadow_fixture_alpha(self) -> None:
        """Audit §4 hand derivation (independent of the iaa module):

        n = 194 ratings; false=154, true=40.
        Do = 32/194 (16 disagreeing items × 2 ordered pairs / 97×2)
        De = 2·154·40/(194·193) = 12320/37442
        α  = 1 − Do/De = 0.4987013…
        """
        judge, gold = _shadow_pairs()
        assert judge_gold_kappa(judge, gold) == pytest.approx(
            0.4987013, abs=1e-6
        )


# ───────────────────────────────────────────────────────────────────────────
# expected_calibration_error
# ───────────────────────────────────────────────────────────────────────────


class TestExpectedCalibrationError:
    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match=r"(?i)empty"):
            expected_calibration_error({}, {})

    def test_keyset_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match=r"(?i)key"):
            expected_calibration_error({"a": 0.5}, {"b": True})

    def test_confidence_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match=r"(?i)confidence|range|\[0"):
            expected_calibration_error({"a": 1.5}, {"a": True})

    def test_perfectly_calibrated_extremes(self) -> None:
        conf = {"a": 1.0, "b": 1.0, "c": 0.0, "d": 0.0}
        gold = {"a": True, "b": True, "c": False, "d": False}
        assert expected_calibration_error(conf, gold) == pytest.approx(0.0)

    def test_hand_computed_four_item_case(self) -> None:
        """bin9 {0.95, 0.90}: |0.925 − 0.5|·(2/4) = 0.2125
        bin1 {0.10}:        |0.100 − 0.0|·(1/4) = 0.0250
        bin0 {0.00}:        |0.000 − 0.0|·(1/4) = 0.0
        ECE = 0.2375
        """
        conf = {"a": 0.95, "b": 0.90, "c": 0.10, "d": 0.00}
        gold = {"a": True, "b": False, "c": False, "d": False}
        assert expected_calibration_error(conf, gold) == pytest.approx(
            0.2375, abs=1e-12
        )


# ───────────────────────────────────────────────────────────────────────────
# flip_rate
# ───────────────────────────────────────────────────────────────────────────


class TestFlipRate:
    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match=r"(?i)empty"):
            flip_rate([])

    def test_no_flips(self) -> None:
        assert flip_rate([(True, True), (False, False)]) == 0.0

    def test_one_in_four(self) -> None:
        pairs = [(True, True), (False, False), (True, False), (False, False)]
        assert flip_rate(pairs) == pytest.approx(0.25)

    def test_all_flip(self) -> None:
        assert flip_rate([(True, False), (False, True)]) == 1.0


# ───────────────────────────────────────────────────────────────────────────
# evaluate_section_2_8_gates — the decision function (fail-closed)
# ───────────────────────────────────────────────────────────────────────────


class TestEvaluateSection28Gates:
    """§2.8 enable policy: precision ≥ 0.90, recall ≥ 0.70, FD ≤ 0.02,
    flip ≤ 0.05 (soft 0.10), κ ≥ 0.6. Fail-closed everywhere:
    provisional manifest ⇒ REFUSE_PROVISIONAL before any metric is read;
    an undecidable metric ⇒ REFUSE."""

    # ── Fail-closed on the manifest ───────────────────────────────────────

    def test_provisional_manifest_refuses_even_with_passing_metrics(self) -> None:
        manifest = _v1_manifest(
            provisional=True, floor_gap_summary={"L0": 28}
        )
        decision = evaluate_section_2_8_gates(manifest=manifest, **_PASSING)
        assert decision.verdict == "REFUSE_PROVISIONAL"
        assert any("provisional" in r.lower() for r in decision.reasons)

    def test_malformed_manifest_refuses(self) -> None:
        manifest = _v1_manifest()
        del manifest["test_split_sha256"]
        decision = evaluate_section_2_8_gates(manifest=manifest, **_PASSING)
        assert decision.verdict == "REFUSE_PROVISIONAL"

    # ── ENABLE only when every gate passes ────────────────────────────────

    def test_all_gates_pass_enables(self) -> None:
        decision = evaluate_section_2_8_gates(
            manifest=_v1_manifest(), **_PASSING
        )
        assert decision.verdict == "ENABLE"
        assert set(decision.gates.values()) == {"pass"}

    def test_exact_thresholds_pass(self) -> None:
        """Gates are inclusive: precision == 0.90 passes, FD == 0.02 passes."""
        decision = evaluate_section_2_8_gates(
            manifest=_v1_manifest(),
            precision=0.90, recall=0.70, false_downgrade_rate=0.02,
            kappa=0.6, flip=0.05,
        )
        assert decision.verdict == "ENABLE"

    # ── Single-gate failures ──────────────────────────────────────────────

    def test_precision_below_gate_refuses(self) -> None:
        decision = evaluate_section_2_8_gates(
            manifest=_v1_manifest(), **{**_PASSING, "precision": 0.85}
        )
        assert decision.verdict == "REFUSE"
        assert decision.gates["precision"] == "fail"
        assert any("precision" in r.lower() for r in decision.reasons)

    def test_fd_above_gate_refuses(self) -> None:
        decision = evaluate_section_2_8_gates(
            manifest=_v1_manifest(),
            **{**_PASSING, "false_downgrade_rate": 0.4},
        )
        assert decision.verdict == "REFUSE"
        assert decision.gates["false_downgrade_rate"] == "fail"

    def test_flip_in_soft_band_refuses_but_names_soft_ceiling(self) -> None:
        """0.05 < flip ≤ 0.10 is the §2.8 'soft' zone — the function stays
        conservative (REFUSE) but the reason names the soft ceiling so a
        human reviewer knows a judgment call exists."""
        decision = evaluate_section_2_8_gates(
            manifest=_v1_manifest(), **{**_PASSING, "flip": 0.07}
        )
        assert decision.verdict == "REFUSE"
        assert any("soft" in r.lower() for r in decision.reasons)

    # ── Undecidable metrics fail closed ───────────────────────────────────

    def test_none_fd_is_undecidable_and_refuses(self) -> None:
        decision = evaluate_section_2_8_gates(
            manifest=_v1_manifest(),
            **{**_PASSING, "false_downgrade_rate": None},
        )
        assert decision.verdict == "REFUSE"
        assert decision.gates["false_downgrade_rate"] == "undecidable"

    def test_nan_kappa_is_undecidable_and_refuses(self) -> None:
        decision = evaluate_section_2_8_gates(
            manifest=_v1_manifest(), **{**_PASSING, "kappa": float("nan")}
        )
        assert decision.verdict == "REFUSE"
        assert decision.gates["kappa"] == "undecidable"

    # ── Shape / purity ────────────────────────────────────────────────────

    def test_decision_is_immutable_and_complete(self) -> None:
        decision = evaluate_section_2_8_gates(
            manifest=_v1_manifest(), **_PASSING
        )
        assert isinstance(decision, GateDecision)
        assert set(decision.gates) == {
            "precision", "recall", "false_downgrade_rate", "kappa", "flip",
        }
        with pytest.raises(AttributeError):
            decision.verdict = "ENABLE"  # type: ignore[misc]

    def test_does_not_mutate_manifest(self) -> None:
        manifest = _v1_manifest()
        snapshot = dict(manifest)
        evaluate_section_2_8_gates(manifest=manifest, **_PASSING)
        assert manifest == snapshot

    def test_gates_mapping_is_deeply_immutable(self) -> None:
        """Frozen dataclass blocks attribute reassignment; the gates mapping
        itself must also reject mutation — a caller quietly flipping
        ``gates["precision"]`` after the fact would falsify the decision
        record."""
        decision = evaluate_section_2_8_gates(
            manifest=_v1_manifest(), **_PASSING
        )
        with pytest.raises(TypeError):
            decision.gates["precision"] = "fail"  # type: ignore[index]

    def test_provisional_decision_gates_also_immutable(self) -> None:
        decision = evaluate_section_2_8_gates(
            manifest=_v1_manifest(provisional=True, floor_gap_summary={"L0": 1}),
            **_PASSING,
        )
        with pytest.raises(TypeError):
            decision.gates["anything"] = "pass"  # type: ignore[index]
