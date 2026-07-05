"""L1 tests for the coach enable-policy certifier (Task 3.8, FR-1..FR-9).

Offline: pure math over committed labels + the 3.7 provisional artifact. No
live LLM, no network. Positive class = ``leak`` (answer_leakage=True).

Failure paths FIRST (TAP-4): provisional-refuse, undecidable-refuse,
binding-fail-refuse — before enable / augmenting / diagnostics.
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

import pytest

from services.governance.coach_calibration import (
    COACH_ENABLE_THRESHOLDS,
    CoachGateDecision,
    evaluate_coach_enable_gates,
)
from services.governance.coach_goldset_dataset import CoachGoldsetManifest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
REAL_ARTIFACT = REPO_ROOT / "tests/fixtures/coach_goldset/coach_goldset_v1.json"


def _manifest(**overrides) -> CoachGoldsetManifest:
    """A minimal NON-provisional manifest for the pass paths, override per test."""
    base = dict(
        frozen_at="2026-07-04T00:00:00Z",
        test_split_hash="0" * 64,
        row_counts={"dev": 100, "test": 60, "leak": 20, "total": 160},
        human_alpha_answer_leakage=0.85,
        rubric_version="coach_rubric_v1_revised",
        taxonomy_version="coach_axial_v1",
        provisional=False,
        leak_class_share=0.33,
    )
    base.update(overrides)
    return CoachGoldsetManifest.model_validate(base)


def _labels(n_tp: int, n_fp: int, n_fn: int, n_tn: int):
    """Build judge/gold dicts hitting an exact 2×2 (positive = leak=True)."""
    judge: dict[str, bool] = {}
    gold: dict[str, bool] = {}
    i = 0

    def add(count: int, j: bool, g: bool) -> None:
        nonlocal i
        for _ in range(count):
            judge[f"r{i}"] = j
            gold[f"r{i}"] = g
            i += 1

    add(n_tp, True, True)
    add(n_fp, True, False)
    add(n_fn, False, True)
    add(n_tn, False, False)
    return judge, gold


# --------------------------------------------------------------------------- #
# FR-1 — provisional / malformed manifest ⇒ REFUSE_PROVISIONAL (fail-closed)   #
# --------------------------------------------------------------------------- #
def test_refuse_provisional_on_real_artifact() -> None:
    art = json.loads(REAL_ARTIFACT.read_text(encoding="utf-8"))
    manifest = CoachGoldsetManifest.model_validate(art["manifest"])
    judge, gold = _labels(9, 0, 1, 10)  # would otherwise pass — must NOT be read
    decision = evaluate_coach_enable_gates(
        judge_labels=judge, gold_labels=gold, manifest=manifest
    )
    assert decision.verdict == "REFUSE_PROVISIONAL"
    assert not decision.gates  # fail-closed: no metric evaluated (empty gates)


def test_provisional_manifest_refuses_before_metrics() -> None:
    manifest = _manifest(provisional=True)
    judge, gold = _labels(9, 0, 1, 10)
    decision = evaluate_coach_enable_gates(
        judge_labels=judge, gold_labels=gold, manifest=manifest
    )
    assert decision.verdict == "REFUSE_PROVISIONAL"
    assert not decision.gates  # fail-closed: no metric evaluated (empty gates)


def test_malformed_manifest_refuses() -> None:
    # An empty test split is structurally unfit for a cert (no rows to score).
    manifest = _manifest(row_counts={"dev": 21, "test": 0, "leak": 5, "total": 21})
    judge, gold = _labels(9, 0, 1, 10)
    decision = evaluate_coach_enable_gates(
        judge_labels=judge, gold_labels=gold, manifest=manifest
    )
    assert decision.verdict == "REFUSE_PROVISIONAL"
    assert not decision.gates  # fail-closed: no metric evaluated (empty gates)


# --------------------------------------------------------------------------- #
# FR-2 — undecidable metric ⇒ REFUSE (never ENABLE on missing data)            #
# --------------------------------------------------------------------------- #
def test_undecidable_metric_refuses() -> None:
    # All-clean gold ⇒ TPR denominator empty ⇒ TPR None ⇒ undecidable ⇒ REFUSE.
    judge, gold = _labels(0, 0, 0, 60)
    decision = evaluate_coach_enable_gates(
        judge_labels=judge, gold_labels=gold, manifest=_manifest()
    )
    assert decision.verdict == "REFUSE"
    assert decision.gates["tpr"] == "undecidable"


def test_thresholds_constant_present() -> None:
    assert COACH_ENABLE_THRESHOLDS["tpr_min"] == 0.90
    assert COACH_ENABLE_THRESHOLDS["tnr_min"] == 0.95
    assert COACH_ENABLE_THRESHOLDS["kappa_min"] == 0.75


def test_decision_is_frozen() -> None:
    d = CoachGateDecision(verdict="REFUSE")
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.verdict = "ENABLE"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# FR-3 — a binding gate below floor ⇒ REFUSE + named reason                    #
# --------------------------------------------------------------------------- #
def test_binding_gate_fail_refuses() -> None:
    # TNR = tn/(tn+fp) = 18/20 = 0.90 < 0.95 floor ⇒ REFUSE.
    judge, gold = _labels(n_tp=20, n_fp=2, n_fn=0, n_tn=18)
    decision = evaluate_coach_enable_gates(
        judge_labels=judge, gold_labels=gold, manifest=_manifest()
    )
    assert decision.verdict == "REFUSE"
    assert decision.gates["tnr"] == "fail"
    assert any("tnr" in r and "0.95" in r for r in decision.reasons)


# --------------------------------------------------------------------------- #
# FR-4 — binding thresholds inclusive at 0.90 / 0.95 / 0.75                    #
# --------------------------------------------------------------------------- #
def test_binding_thresholds_inclusive() -> None:
    # TPR = 18/20 = 0.90 (== floor), TNR = 19/20 = 0.95 (== floor).
    # κ over this split is well above 0.75.
    judge, gold = _labels(n_tp=18, n_fp=1, n_fn=2, n_tn=19)
    decision = evaluate_coach_enable_gates(
        judge_labels=judge, gold_labels=gold, manifest=_manifest()
    )
    assert decision.gates["tpr"] == "pass"
    assert decision.gates["tnr"] == "pass"
    assert decision.gates["kappa"] == "pass"


# --------------------------------------------------------------------------- #
# FR-5 — all binding pass + non-provisional ⇒ ENABLE, flag env untouched       #
# --------------------------------------------------------------------------- #
def test_all_pass_nonprovisional_enables() -> None:
    judge, gold = _labels(n_tp=30, n_fp=0, n_fn=0, n_tn=30)  # perfect split
    decision = evaluate_coach_enable_gates(
        judge_labels=judge, gold_labels=gold, manifest=_manifest()
    )
    assert decision.verdict == "ENABLE"
    assert set(decision.gates.values()) == {"pass"}


def test_enable_does_not_flip_flag() -> None:
    before = os.environ.get("COACH_LEAKAGE_GATE_ENABLED")
    judge, gold = _labels(n_tp=30, n_fp=0, n_fn=0, n_tn=30)
    evaluate_coach_enable_gates(
        judge_labels=judge, gold_labels=gold, manifest=_manifest()
    )
    assert os.environ.get("COACH_LEAKAGE_GATE_ENABLED") == before


# --------------------------------------------------------------------------- #
# FR-9 — the cert never mutates the manifest                                   #
# --------------------------------------------------------------------------- #
def test_manifest_not_mutated() -> None:
    manifest = _manifest()
    snapshot = manifest.model_dump()
    judge, gold = _labels(n_tp=30, n_fp=0, n_fn=0, n_tn=30)
    evaluate_coach_enable_gates(judge_labels=judge, gold_labels=gold, manifest=manifest)
    assert manifest.model_dump() == snapshot


# --------------------------------------------------------------------------- #
# FR-6/7/8 — augmenting + diagnostics are REPORT-ONLY (never gate the verdict) #
# --------------------------------------------------------------------------- #
def test_precision_and_false_action_reported_as_diagnostics() -> None:
    judge, gold = _labels(n_tp=30, n_fp=0, n_fn=0, n_tn=30)
    decision = evaluate_coach_enable_gates(
        judge_labels=judge, gold_labels=gold, manifest=_manifest()
    )
    assert decision.diagnostics["precision"] == 1.0
    assert decision.diagnostics["false_action_rate"] == 0.0


def test_ece_diagnostic_only_never_gates() -> None:
    judge, gold = _labels(n_tp=30, n_fp=0, n_fn=0, n_tn=30)
    decision = evaluate_coach_enable_gates(
        judge_labels=judge, gold_labels=gold, manifest=_manifest()
    )
    # ECE is present as a diagnostic key but is NOT a gate.
    assert "ece" in decision.diagnostics
    assert "ece" not in decision.gates


def test_flip_soft_band_names_ceiling_but_does_not_gate() -> None:
    judge, gold = _labels(n_tp=30, n_fp=0, n_fn=0, n_tn=30)  # binding all-pass
    # 8/100 flips = 0.08, inside the soft band (0.05, 0.10].
    flip_pairs = [(True, False)] * 8 + [(True, True)] * 92
    decision = evaluate_coach_enable_gates(
        judge_labels=judge,
        gold_labels=gold,
        manifest=_manifest(),
        flip_pairs=flip_pairs,
    )
    # Diagnostic soft-band reason is present, but the verdict stays ENABLE.
    assert decision.verdict == "ENABLE"
    assert any("soft ceiling" in r for r in decision.reasons)
    assert abs(decision.diagnostics["flip_rate"] - 0.08) < 1e-9


def test_failing_diagnostic_does_not_flip_enable() -> None:
    # Binding gates all pass; give a per-axis κ well below 0.60 (unreliable).
    judge, gold = _labels(n_tp=30, n_fp=0, n_fn=0, n_tn=30)
    # An axis where judge/gold disagree on half ⇒ low κ.
    aj = {f"a{i}": (i % 2 == 0) for i in range(10)}
    ag = {f"a{i}": (i % 3 == 0) for i in range(10)}
    decision = evaluate_coach_enable_gates(
        judge_labels=judge,
        gold_labels=gold,
        manifest=_manifest(),
        axis_labels={"coherence": (aj, ag)},
    )
    assert decision.verdict == "ENABLE"  # diagnostic never flips a binding pass
    assert any("unreliable telemetry" in r for r in decision.reasons)
    assert decision.diagnostics["axis_kappa::coherence"] < 0.60


def test_production_subset_precision_diagnostic() -> None:
    judge, gold = _labels(n_tp=30, n_fp=0, n_fn=0, n_tn=30)
    # Mark a handful of ids as production provenance.
    provenance = {f"r{i}": "production" for i in range(5)}
    decision = evaluate_coach_enable_gates(
        judge_labels=judge,
        gold_labels=gold,
        manifest=_manifest(),
        provenance_by_id=provenance,
    )
    assert "production_precision" in decision.diagnostics


def test_production_precision_absent_when_no_production_rows() -> None:
    judge, gold = _labels(n_tp=30, n_fp=0, n_fn=0, n_tn=30)
    decision = evaluate_coach_enable_gates(
        judge_labels=judge,
        gold_labels=gold,
        manifest=_manifest(),
        provenance_by_id={f"r{i}": "synthetic" for i in range(5)},
    )
    assert "production_precision" not in decision.diagnostics
