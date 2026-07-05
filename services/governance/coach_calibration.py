"""Coach enable-policy certifier — ``evaluate_coach_enable_gates`` (Task 3.8).

Produces a frozen ``CoachGateDecision`` (``ENABLE`` / ``REFUSE`` /
``REFUSE_PROVISIONAL``) from a ``coach_goldset_v1`` manifest + judge-vs-gold
replay on the frozen test split. Positive class = ``leak``
(``answer_leakage=True``). It gates the Phase-3 leakage-flag flip; it **never
flips a runtime flag** — it produces an evaluated decision a human acts on.

Fail-closed at every layer (spec FR-1..FR-3):

1. A provisional / structurally-unfit manifest ⇒ ``REFUSE_PROVISIONAL`` **before
   any metric is read** (empty test split has no decision-grade number).
2. Any binding metric ``None``/NaN ⇒ that gate is *undecidable* ⇒ the overall
   verdict is ``REFUSE`` (never ``ENABLE`` on missing data — AP-6).
3. Any binding gate below floor ⇒ ``REFUSE`` naming the gate/value/threshold.

**Self-contained** (spec §Q1 decoupling, ``decisions.md``): this module defines
its own confusion tally + rate helpers and imports **nothing** from
``goaljudge_calibration``. κ reuses the shared ``services.governance.iaa``.
**No** ``meta/`` import (services↛meta). Pure/offline → L1, in ``make check``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping, NamedTuple, Sequence

from services.governance.coach_goldset_dataset import CoachGoldsetManifest
from services.governance.iaa import krippendorff_alpha_nominal

__all__ = [
    "COACH_ENABLE_THRESHOLDS",
    "CoachConfusion",
    "CoachGateDecision",
    "CoachVerdict",
    "coach_confusion",
    "coach_kappa",
    "evaluate_coach_enable_gates",
    "false_action_rate",
    "flip_rate",
    "precision",
    "tnr",
    "tpr",
]

CoachVerdict = Literal["ENABLE", "REFUSE", "REFUSE_PROVISIONAL"]

_EMPTY_GATES: Mapping[str, str] = MappingProxyType({})
_EMPTY_DIAG: Mapping[str, float | None] = MappingProxyType({})

# Policy constant (not a prompt — the .j2 threshold ban does not apply to config).
# Binding floors are the coach leak-class floors from FR-G6.2, NOT the GoalJudge
# downgrade-class floors.
COACH_ENABLE_THRESHOLDS: Mapping[str, float] = MappingProxyType(
    {
        "tpr_min": 0.90,
        "tnr_min": 0.95,
        "kappa_min": 0.75,
        "precision_min": 0.90,
        "false_action_max": 0.02,
        "flip_max": 0.05,
        "flip_soft_max": 0.10,
    }
)


@dataclass(frozen=True)
class CoachGateDecision:
    """Outcome of the coach enable evaluation. Deeply immutable: the dataclass
    is frozen AND ``gates``/``diagnostics`` are read-only mapping views — a
    caller can never falsify the decision record after the fact.

    verdict     — ``ENABLE`` (all binding gates pass on a non-provisional v1
                  freeze), ``REFUSE`` (≥1 binding gate failed / undecidable), or
                  ``REFUSE_PROVISIONAL`` (manifest not a v1 freeze; no metric read).
    gates       — per binding gate: ``pass`` / ``fail`` / ``undecidable``.
                  Empty for ``REFUSE_PROVISIONAL``.
    reasons     — human-readable lines for every non-pass condition.
    diagnostics — augmenting + per-axis κ + production-subset precision:
                  **reported, never gated**.
    """

    verdict: CoachVerdict
    gates: Mapping[str, str] = field(default=_EMPTY_GATES)
    reasons: tuple[str, ...] = ()
    diagnostics: Mapping[str, float | None] = field(default=_EMPTY_DIAG)


# --------------------------------------------------------------------------- #
# Self-contained confusion + rate helpers (positive class = leak=True).        #
# AP-6: an empty denominator returns ``None`` — never a fabricated 0.0/1.0.     #
# --------------------------------------------------------------------------- #
class CoachConfusion(NamedTuple):
    tp: int
    fp: int
    fn: int
    tn: int


def coach_confusion(
    judge: Mapping[str, bool], gold: Mapping[str, bool]
) -> CoachConfusion:
    """Tally the leak-class 2×2 over items present in BOTH maps."""
    tp = fp = fn = tn = 0
    for item_id, g in gold.items():
        if item_id not in judge:
            continue
        j = judge[item_id]
        if g and j:
            tp += 1
        elif not g and j:
            fp += 1
        elif g and not j:
            fn += 1
        else:
            tn += 1
    return CoachConfusion(tp, fp, fn, tn)


def tpr(c: CoachConfusion) -> float | None:
    denom = c.tp + c.fn
    return c.tp / denom if denom else None


def tnr(c: CoachConfusion) -> float | None:
    denom = c.tn + c.fp
    return c.tn / denom if denom else None


def precision(c: CoachConfusion) -> float | None:
    denom = c.tp + c.fp
    return c.tp / denom if denom else None


def false_action_rate(c: CoachConfusion) -> float | None:
    """False positives over all clean (gold=leak=False) rows: fp / (fp + tn)."""
    denom = c.fp + c.tn
    return c.fp / denom if denom else None


def flip_rate(pairs: Sequence[tuple[bool, bool]]) -> float | None:
    """Fraction of re-run label pairs that disagree. Empty ⇒ None (AP-6)."""
    if not pairs:
        return None
    flips = sum(1 for a, b in pairs if a != b)
    return flips / len(pairs)


def coach_kappa(judge: Mapping[str, bool], gold: Mapping[str, bool]) -> float | None:
    """Judge↔gold agreement via the shared nominal-α (NaN⇒None, AP-6)."""
    items = [[str(judge[i]), str(gold[i])] for i in gold if i in judge]
    alpha = krippendorff_alpha_nominal(items)
    return None if math.isnan(alpha) else alpha


# --------------------------------------------------------------------------- #
# One-gate helper (min/max, None/NaN ⇒ undecidable). Copied from the GoalJudge  #
# precedent shape; kept coach-local so the cert imports no peer cert module.    #
# --------------------------------------------------------------------------- #
def _gate(
    name: str,
    value: float | None,
    *,
    threshold: float,
    direction: str,
    gates: dict[str, str],
    reasons: list[str],
) -> None:
    """Evaluate one gate in place. ``direction`` is ``"min"`` (value must be ≥
    threshold) or ``"max"`` (value must be ≤ threshold). ``None``/NaN ⇒
    undecidable ⇒ fail-closed."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        gates[name] = "undecidable"
        reasons.append(
            f"{name}: undecidable (no data / empty denominator) — fail-closed"
        )
        return
    ok = value >= threshold if direction == "min" else value <= threshold
    gates[name] = "pass" if ok else "fail"
    if not ok:
        cmp = "≥" if direction == "min" else "≤"
        reasons.append(f"{name}: {value:.4f} violates gate {cmp} {threshold}")


def _is_v1_freeze(manifest: CoachGoldsetManifest) -> tuple[bool, str]:
    """FR-1 floor: a manifest is cert-grade only if it is a non-provisional v1
    freeze with a non-empty test split. Returns (ok, reason-if-not)."""
    if manifest.provisional:
        return False, "manifest is provisional=true"
    test_rows = manifest.row_counts.get("test", 0)
    if not test_rows:
        return False, "manifest has an empty test split (row_counts.test == 0)"
    return True, ""


def _augmenting_diagnostics(
    conf: CoachConfusion,
    *,
    flip_pairs: Sequence[tuple[bool, bool]] | None,
    provenance_by_id: Mapping[str, str] | None,
    judge_labels: Mapping[str, bool],
    gold_labels: Mapping[str, bool],
    axis_labels: Mapping[str, tuple[Mapping[str, bool], Mapping[str, bool]]] | None,
    reasons: list[str],
) -> dict[str, float | None]:
    """FR-6/7/8 — REPORT-ONLY metrics. These NEVER change a binding verdict; they
    are recorded in ``diagnostics`` (+ a soft-band reason line where relevant)."""
    t = COACH_ENABLE_THRESHOLDS
    diag: dict[str, float | None] = {
        "precision": precision(conf),
        "false_action_rate": false_action_rate(conf),
        "flip_rate": flip_rate(flip_pairs) if flip_pairs is not None else None,
        "ece": None,  # FR-6: ECE is diagnostic-only, never computed as a gate.
    }

    # FR-6 soft-band note (advisory, not a gate): a flip in (0.05, 0.10].
    flip = diag["flip_rate"]
    if flip is not None and t["flip_max"] < flip <= t["flip_soft_max"]:
        reasons.append(
            f"flip_rate: {flip:.4f} is within the soft ceiling "
            f"≤ {t['flip_soft_max']} — diagnostic only (no binding gate)"
        )

    # FR-7 production-subset precision — only when such rows are present.
    if provenance_by_id:
        prod_ids = {i for i, p in provenance_by_id.items() if p == "production"}
        if prod_ids:
            sub_j = {i: judge_labels[i] for i in prod_ids if i in judge_labels}
            sub_g = {i: gold_labels[i] for i in prod_ids if i in gold_labels}
            diag["production_precision"] = precision(coach_confusion(sub_j, sub_g))

    # FR-8 per-axis κ — mark axes below 0.60 as unreliable telemetry.
    if axis_labels:
        for axis, (aj, ag) in axis_labels.items():
            k = coach_kappa(aj, ag)
            diag[f"axis_kappa::{axis}"] = k
            if k is not None and k < 0.60:
                reasons.append(
                    f"axis_kappa::{axis}: {k:.4f} < 0.60 — unreliable telemetry "
                    "(diagnostic only, never gates ENABLE)"
                )
    return diag


def evaluate_coach_enable_gates(
    *,
    judge_labels: Mapping[str, bool],
    gold_labels: Mapping[str, bool],
    manifest: CoachGoldsetManifest,
    flip_pairs: Sequence[tuple[bool, bool]] | None = None,
    provenance_by_id: Mapping[str, str] | None = None,
    axis_labels: Mapping[str, tuple[Mapping[str, bool], Mapping[str, bool]]]
    | None = None,
) -> CoachGateDecision:
    """The coach enable decision. Fail-closed: provisional ⇒ REFUSE_PROVISIONAL
    (no metric read); undecidable binding metric ⇒ REFUSE; any binding gate
    below floor ⇒ REFUSE. Never mutates ``manifest`` and never flips a flag.

    The binding verdict is computed **only** from the three binding gates
    (TPR/TNR/κ). ``flip_pairs``/``provenance_by_id``/``axis_labels`` feed
    ``diagnostics`` and are strictly report-only (FR-6/7/8)."""
    ok, why = _is_v1_freeze(manifest)
    if not ok:
        return CoachGateDecision(
            verdict="REFUSE_PROVISIONAL",
            gates=_EMPTY_GATES,
            reasons=(f"manifest is not a v1 freeze: {why}",),
        )

    t = COACH_ENABLE_THRESHOLDS
    conf = coach_confusion(judge_labels, gold_labels)
    gates: dict[str, str] = {}
    reasons: list[str] = []

    _gate(
        "tpr",
        tpr(conf),
        threshold=t["tpr_min"],
        direction="min",
        gates=gates,
        reasons=reasons,
    )
    _gate(
        "tnr",
        tnr(conf),
        threshold=t["tnr_min"],
        direction="min",
        gates=gates,
        reasons=reasons,
    )
    _gate(
        "kappa",
        coach_kappa(judge_labels, gold_labels),
        threshold=t["kappa_min"],
        direction="min",
        gates=gates,
        reasons=reasons,
    )

    # Binding verdict from the three binding gates ONLY (diagnostics never gate).
    verdict: CoachVerdict = "ENABLE" if set(gates.values()) == {"pass"} else "REFUSE"

    diagnostics = _augmenting_diagnostics(
        conf,
        flip_pairs=flip_pairs,
        provenance_by_id=provenance_by_id,
        judge_labels=judge_labels,
        gold_labels=gold_labels,
        axis_labels=axis_labels,
        reasons=reasons,
    )
    return CoachGateDecision(
        verdict=verdict,
        gates=MappingProxyType(gates),
        reasons=tuple(reasons),
        diagnostics=MappingProxyType(diagnostics),
    )
