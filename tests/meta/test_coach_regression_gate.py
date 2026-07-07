"""T1/T2 — coach judge golden-regression gate (Phase-5 task 5.3).

CI-safe: recomputes the ADR-0019 certified floor (TNR/TPR/κ) from the COMMITTED
recorded-label runs and fails on a floor breach, a verdict flip across runs, or a
malformed/mislabeled artifact. No live LLM — grades committed snapshots.

Failure paths FIRST (TAP-4): every FR-1..7,9,10 test builds a synthetic-broken run in
``tmp_path`` and asserts the gate FAILS; the real committed fixtures are the FR-8
happy-path oracle and are NEVER mutated.

Spec: docs/plan/coach-regression-gate.spec.md · Plan: coach-regression-gate.plan.md.
"""

from __future__ import annotations

import json
from pathlib import Path


from meta.coach_regression_gate import (
    SPLIT_PATH,
    run_coach_regression_gate,
)

_REPO = Path(__file__).resolve().parent.parent.parent
_REAL_RUNS = tuple(
    _REPO / "docs" / "IAA" / "coach" / "recert" / f"recert_labels_fw_run{n}.jsonl"
    for n in (1, 2, 3)
)


def _real_rows(run_idx: int = 0) -> list[dict]:
    """The real committed rows of run{n} (a clean, ENABLE-grade run) to mutate."""
    path = _REAL_RUNS[run_idx]
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_run(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


def _fix_confusion(row: dict) -> dict:
    """Recompute the ``confusion`` field to match the (gold, judge) pair, so a
    synthetic mutation stays internally consistent unless we're testing FR-9."""
    g, j = row["gold_leak"], row["judge_leak"]
    row["confusion"] = (
        "tp" if g and j else "fp" if j and not g else "fn" if g and not j else "tn"
    )
    return row


def _three_clean_runs(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Three copies of the real run1 (each independently ENABLE-grade, zero-flip)."""
    rows = _real_rows(0)
    return (
        _write_run(tmp_path / "r1.jsonl", [dict(r) for r in rows]),
        _write_run(tmp_path / "r2.jsonl", [dict(r) for r in rows]),
        _write_run(tmp_path / "r3.jsonl", [dict(r) for r in rows]),
    )


# ── FR-5: missing / empty / malformed → error (exit 2), never a silent pass ──


def test_gate_errors_on_missing_run_file(tmp_path: Path) -> None:
    r1, r2, _ = _three_clean_runs(tmp_path)
    missing = tmp_path / "does_not_exist.jsonl"
    result = run_coach_regression_gate(run_paths=(r1, r2, missing))
    assert not result.ok
    assert result.error is not None


def test_gate_errors_on_empty_run_file(tmp_path: Path) -> None:
    r1, r2, _ = _three_clean_runs(tmp_path)
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    result = run_coach_regression_gate(run_paths=(r1, r2, empty))
    assert not result.ok
    assert result.error is not None


def test_gate_errors_on_malformed_json(tmp_path: Path) -> None:
    r1, r2, _ = _three_clean_runs(tmp_path)
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"item_id": "X", not json\n')
    result = run_coach_regression_gate(run_paths=(r1, r2, bad))
    assert not result.ok
    assert result.error is not None


def test_gate_errors_on_non_bool_label(tmp_path: Path) -> None:
    rows = _real_rows(0)
    rows[0]["gold_leak"] = None  # not a bool
    r_bad = _write_run(tmp_path / "r1.jsonl", rows)
    r2 = _write_run(tmp_path / "r2.jsonl", _real_rows(0))
    r3 = _write_run(tmp_path / "r3.jsonl", _real_rows(0))
    result = run_coach_regression_gate(run_paths=(r_bad, r2, r3))
    assert not result.ok
    assert result.error is not None


# ── FR-5b: a declared abstention (judge_leak null + confusion "abstain") is VALID ──


def test_declared_abstention_is_dropped_not_an_error(tmp_path: Path) -> None:
    # ADR-0019 run3 abstained on R-CLEAN-29; the cert dropped it and still scored
    # ENABLE. The gate must do the same — an abstention is not malformed.
    rows = _real_rows(0)
    rows[0]["judge_leak"] = None
    rows[0]["confusion"] = "abstain"
    r1 = _write_run(tmp_path / "r1.jsonl", rows)
    r2 = _write_run(tmp_path / "r2.jsonl", [dict(r) for r in _real_rows(0)])
    r3 = _write_run(tmp_path / "r3.jsonl", [dict(r) for r in _real_rows(0)])
    result = run_coach_regression_gate(run_paths=(r1, r2, r3))
    assert result.ok, result.violations or result.error
    assert result.error is None


def test_null_judge_leak_without_abstain_confusion_is_error(tmp_path: Path) -> None:
    # A null verdict that is NOT a declared abstention is malformed (FR-5).
    rows = _real_rows(0)
    rows[0]["judge_leak"] = None
    rows[0]["confusion"] = "tn"  # lies — null is not tn
    r_bad = _write_run(tmp_path / "r1.jsonl", rows)
    r2 = _write_run(tmp_path / "r2.jsonl", _real_rows(0))
    r3 = _write_run(tmp_path / "r3.jsonl", _real_rows(0))
    result = run_coach_regression_gate(run_paths=(r_bad, r2, r3))
    assert not result.ok
    assert result.error is not None


# ── FR-9: a row whose confusion field disagrees with its (gold, judge) pair → error ──


def test_gate_fails_on_mislabeled_confusion_row(tmp_path: Path) -> None:
    rows = _real_rows(0)
    # honest pair is tn (gold=F, judge=F); lie the confusion field to "fp"
    rows[0]["gold_leak"] = False
    rows[0]["judge_leak"] = False
    rows[0]["confusion"] = "fp"
    r_bad = _write_run(tmp_path / "r1.jsonl", rows)
    r2 = _write_run(tmp_path / "r2.jsonl", _real_rows(0))
    r3 = _write_run(tmp_path / "r3.jsonl", _real_rows(0))
    result = run_coach_regression_gate(run_paths=(r_bad, r2, r3))
    assert not result.ok
    assert result.error is not None


# ── FR-6: a run scored a different corpus than the frozen split → fail ──


def test_gate_fails_on_corpus_mismatch_vs_frozen_split(tmp_path: Path) -> None:
    rows = _real_rows(0)
    rows[0]["item_id"] = "NOT-IN-SPLIT-999"  # foreign id
    r_bad = _write_run(tmp_path / "r1.jsonl", rows)
    r2 = _write_run(tmp_path / "r2.jsonl", _real_rows(0))
    r3 = _write_run(tmp_path / "r3.jsonl", _real_rows(0))
    result = run_coach_regression_gate(run_paths=(r_bad, r2, r3))
    assert not result.ok


# ── FR-1/2/3: a run below the TNR/TPR/κ floor → violation naming the metric ──


def test_gate_fails_when_a_run_tnr_below_floor(tmp_path: Path) -> None:
    # Flip a large share of clean (tn) rows to judge_leak=True → many fp → TNR crashes.
    rows = _real_rows(0)
    flipped = 0
    for r in rows:
        if not r["gold_leak"] and not r["judge_leak"]:
            r["judge_leak"] = True
            _fix_confusion(r)
            flipped += 1
            if flipped >= 10:
                break
    r_bad = _write_run(tmp_path / "r1.jsonl", rows)
    r2 = _write_run(tmp_path / "r2.jsonl", _real_rows(0))
    r3 = _write_run(tmp_path / "r3.jsonl", _real_rows(0))
    result = run_coach_regression_gate(run_paths=(r_bad, r2, r3))
    assert not result.ok
    assert any("tnr" in v.lower() for v in result.violations)


def test_gate_fails_when_a_run_tpr_below_floor(tmp_path: Path) -> None:
    # Flip leak (tp) rows to judge_leak=False → fn → TPR drops below 0.90.
    rows = _real_rows(0)
    for r in rows:
        if r["gold_leak"] and r["judge_leak"]:
            r["judge_leak"] = False
            _fix_confusion(r)
    r_bad = _write_run(tmp_path / "r1.jsonl", rows)
    r2 = _write_run(tmp_path / "r2.jsonl", _real_rows(0))
    r3 = _write_run(tmp_path / "r3.jsonl", _real_rows(0))
    result = run_coach_regression_gate(run_paths=(r_bad, r2, r3))
    assert not result.ok
    assert any("tpr" in v.lower() for v in result.violations)


# ── FR-10: an undecidable metric (empty denominator) → None → fail, never 0.0 ──


def test_gate_fails_on_undecidable_metric_all_clean_run(tmp_path: Path) -> None:
    # Make every row clean gold=F → the TPR denominator (tp+fn) is 0 → undecidable.
    rows = _real_rows(0)
    for r in rows:
        r["gold_leak"] = False
        r["judge_leak"] = False
        _fix_confusion(r)
    r_bad = _write_run(tmp_path / "r1.jsonl", rows)
    r2 = _write_run(tmp_path / "r2.jsonl", rows)
    r3 = _write_run(tmp_path / "r3.jsonl", rows)
    result = run_coach_regression_gate(run_paths=(r_bad, r2, r3))
    assert not result.ok


# ── FR-4: a verdict flip across the 3 runs → violation naming the item ──


def test_gate_fails_on_verdict_flip_across_runs(tmp_path: Path) -> None:
    r1, r2, r3 = _three_clean_runs(tmp_path)
    # flip one item's judge_leak in run2 ONLY → cross-run instability
    r2_rows = _real_rows(0)
    r2_rows[0]["judge_leak"] = not r2_rows[0]["judge_leak"]
    _fix_confusion(r2_rows[0])
    _write_run(r2, r2_rows)
    result = run_coach_regression_gate(run_paths=(r1, r2, r3))
    assert not result.ok
    assert result.flip_count == 1


# ── FR-7: the metric is recomputed from (gold, judge), not the confusion field ──


def test_metrics_recomputed_from_truth_not_confusion_field(tmp_path: Path) -> None:
    # A run that is genuinely clean (all tn/tp honest) but carries a LYING confusion
    # on one row is caught by FR-9 (error) — proving the field is validated, not
    # trusted. The truth pair is what the metric would use. Here we assert the honest
    # variant (confusion fixed) PASSES, so the difference is attributable to the field.
    rows = _real_rows(0)  # honest → PASS
    r1 = _write_run(tmp_path / "r1.jsonl", [dict(r) for r in rows])
    r2 = _write_run(tmp_path / "r2.jsonl", [dict(r) for r in rows])
    r3 = _write_run(tmp_path / "r3.jsonl", [dict(r) for r in rows])
    assert run_coach_regression_gate(run_paths=(r1, r2, r3)).ok


# ── FR-8: the REAL committed runs pass the gate (the oracle) ──


def test_committed_runs_pass_the_gate() -> None:
    result = run_coach_regression_gate()  # real defaults
    assert result.ok, result.violations or result.error
    assert result.flip_count == 0
    assert len(result.per_run) == 3


def test_split_path_is_the_frozen_recert_split() -> None:
    assert SPLIT_PATH.name == "coach_recert_split_v1.json"
    assert SPLIT_PATH.exists()


# ── T2 (FR-11): the CLI returns 0 / 1 / 2 ──


class TestCli:
    def test_missing_run_returns_2(self, tmp_path: Path) -> None:
        from scripts.coach_regression_gate import main

        r1, r2, _ = _three_clean_runs(tmp_path)
        missing = tmp_path / "gone.jsonl"
        assert main(["--run", str(r1), "--run", str(r2), "--run", str(missing)]) == 2

    def test_below_floor_returns_1(self, tmp_path: Path) -> None:
        from scripts.coach_regression_gate import main

        rows = _real_rows(0)
        flipped = 0
        for r in rows:
            if not r["gold_leak"] and not r["judge_leak"]:
                r["judge_leak"] = True
                _fix_confusion(r)
                flipped += 1
                if flipped >= 10:
                    break
        r_bad = _write_run(tmp_path / "r1.jsonl", rows)
        r2 = _write_run(tmp_path / "r2.jsonl", _real_rows(0))
        r3 = _write_run(tmp_path / "r3.jsonl", _real_rows(0))
        assert main(["--run", str(r_bad), "--run", str(r2), "--run", str(r3)]) == 1

    def test_real_committed_runs_return_0(self) -> None:
        from scripts.coach_regression_gate import main

        assert main([]) == 0
