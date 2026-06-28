"""L2 Reproducible: Stage-6 calibration scorer for the memory extractor.

Failure paths first (TAP-4). The scorer is the trust anchor for the
``MEMORY_AUTOCAPTURE_ENABLED`` write-back flip, so the gate boundaries +
vacuous/NaN cases are pinned. No LLM, no I/O — pure scoring over labeled rows.

Gates under test (03_enable_policy.md §2): store-class precision ≥ 0.90,
false-store-on-trivia ≤ 0.02, mis-type ≤ 0.10, PII-flip == 0 (hard),
κ ≥ 0.60. Recall is reported, not gated.
"""

from __future__ import annotations

import math

from services.governance.memory_extractor_calibration import (
    GoldRow,
    Proposal,
    score,
)


def _gold(
    item_id: str,
    *,
    should_store: bool,
    stratum: str = "clear_store_semantic",
    gold_type: str | None = "semantic",
    split: str = "test",
) -> GoldRow:
    return GoldRow(
        item_id=item_id,
        split=split,
        stratum=stratum,
        window=f"window-{item_id}",
        should_store=should_store,
        gold_type=gold_type,
    )


def _prop(
    item_id: str, *, store: bool = True, ptype: str | None = "semantic"
) -> Proposal:
    return Proposal(item_id=item_id, proposed_store=store, proposed_type=ptype)


def _gate(report, name):
    return next(g for g in report.gates if g.name == name)


# ── Failure paths first ────────────────────────────────────────────────


class TestVacuousAndDegenerate:
    def test_no_store_proposals_precision_is_nan_and_blocks(self) -> None:
        # Extractor proposes nothing anywhere → precision vacuous → must NOT enable.
        gold = [_gold("a", should_store=True), _gold("b", should_store=False)]
        report = score(gold, [], split="test")
        prec = _gate(report, "store_class_precision")
        assert math.isnan(prec.value)
        assert prec.passed is False  # NaN treated as FAIL (can't enable on nothing)
        assert report.passed is False

    def test_empty_gold_does_not_crash(self) -> None:
        report = score([], [], split="test")
        assert report.total_rows == 0
        assert report.passed is False  # nothing proved → blocked

    def test_split_filter_excludes_dev_rows(self) -> None:
        gold = [
            _gold("d", should_store=True, split="dev"),
            _gold("t", should_store=True, split="test"),
        ]
        report = score(gold, [_prop("t")], split="test")
        assert report.total_rows == 1  # only the test-split row scored


class TestPiiHardZero:
    def test_single_pii_flip_blocks_even_if_everything_else_passes(self) -> None:
        # Perfect precision + recall, but one PII store → hard-zero gate fails.
        gold = [_gold(f"s{i}", should_store=True) for i in range(10)] + [
            _gold(
                "pii", should_store=False, stratum="pii_must_not_store", gold_type=None
            )
        ]
        proposals = [_prop(f"s{i}") for i in range(10)] + [_prop("pii")]
        report = score(gold, proposals, split="test")
        pii = _gate(report, "pii_flip_rate")
        assert pii.value == 1.0
        assert pii.passed is False
        assert report.passed is False


# ── Boundary acceptance ────────────────────────────────────────────────


class TestPrecisionGateBoundary:
    def test_precision_exactly_090_passes(self) -> None:
        # 9 true stores + 1 false store = 0.90 precision (the boundary).
        gold = [_gold(f"t{i}", should_store=True) for i in range(9)]
        gold.append(_gold("f", should_store=False, stratum="boundary_salience"))
        proposals = [_prop(f"t{i}") for i in range(9)] + [_prop("f")]
        report = score(gold, proposals, split="test")
        prec = _gate(report, "store_class_precision")
        assert abs(prec.value - 0.90) < 1e-9
        assert prec.passed is True

    def test_precision_below_090_fails(self) -> None:
        # 8 true + 2 false = 0.80 precision.
        gold = [_gold(f"t{i}", should_store=True) for i in range(8)]
        gold += [
            _gold("f1", should_store=False, stratum="boundary_salience"),
            _gold("f2", should_store=False, stratum="boundary_salience"),
        ]
        proposals = [_prop(f"t{i}") for i in range(8)] + [_prop("f1"), _prop("f2")]
        report = score(gold, proposals, split="test")
        assert _gate(report, "store_class_precision").passed is False


class TestTriviaFalseStore:
    def test_false_store_on_trivia_over_2pct_fails(self) -> None:
        # 50 trivia rows, 2 stored = 4% > 2% → fail.
        gold = [
            _gold(f"n{i}", should_store=False, stratum="clear_no_store", gold_type=None)
            for i in range(50)
        ]
        proposals = [_prop("n0"), _prop("n1")]  # 2 false stores
        report = score(gold, proposals, split="test")
        g = _gate(report, "false_store_on_trivia")
        assert abs(g.value - 0.04) < 1e-9
        assert g.passed is False


class TestMistype:
    def test_correct_type_no_mistype(self) -> None:
        gold = [_gold("a", should_store=True, gold_type="episodic")]
        proposals = [_prop("a", ptype="episodic")]
        report = score(gold, proposals, split="test")
        assert _gate(report, "mistype_rate").value == 0.0

    def test_wrong_type_counts_as_mistype(self) -> None:
        # Stored correctly (precision fine) but episodic filed as semantic.
        gold = [_gold("a", should_store=True, gold_type="episodic")]
        proposals = [_prop("a", ptype="semantic")]
        report = score(gold, proposals, split="test")
        mt = _gate(report, "mistype_rate")
        assert mt.value == 1.0
        assert mt.passed is False


class TestAllGatesPass:
    def test_clean_run_is_enable_eligible(self) -> None:
        gold = (
            [_gold(f"s{i}", should_store=True) for i in range(20)]
            + [
                _gold(
                    f"n{i}",
                    should_store=False,
                    stratum="clear_no_store",
                    gold_type=None,
                )
                for i in range(20)
            ]
            + [
                _gold(
                    "pii",
                    should_store=False,
                    stratum="pii_must_not_store",
                    gold_type=None,
                )
            ]
        )
        # Extractor: stores all true, refuses all no-store + the PII row.
        proposals = [_prop(f"s{i}") for i in range(20)]
        report = score(gold, proposals, split="test")
        assert report.passed is True, report.render()
        assert _gate(report, "store_class_precision").value == 1.0
        assert _gate(report, "pii_flip_rate").value == 0.0
        # recall reported (all true stored → 1.0) but not part of the verdict
        assert report.recall == 1.0

    def test_recall_is_reported_not_gated(self) -> None:
        # Miss half the true stores → recall 0.5, but precision still 1.0 and
        # the verdict should NOT be blocked by the miss alone.
        gold = [_gold(f"s{i}", should_store=True) for i in range(10)]
        proposals = [_prop(f"s{i}") for i in range(5)]  # only stored half
        report = score(gold, proposals, split="test")
        assert report.recall == 0.5
        assert _gate(report, "store_class_precision").value == 1.0
        # No gate named "recall" exists — it's report-only.
        assert all(g.name != "recall" for g in report.gates)
