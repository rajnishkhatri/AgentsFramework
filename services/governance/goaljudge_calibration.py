"""GoalJudge Stage 6 calibration metrics + the §2.8 enable-gate evaluator.

Pyramid layer:   L1 Deterministic — pure functions, no I/O, no logging, no LLM.
Architecture:    Horizontal (services/governance/). Imported by the Stage 6
                 replay harness (``scripts/run_goaljudge_calibration.py``) and
                 the calibration report builder. Zero imports from
                 ``components/``, ``orchestration/``, ``langgraph``, or
                 ``langchain``; the only sibling import is the local
                 Horizontal→Horizontal :func:`gate_goldset_v1_floors` call.

Public API:

* :func:`confusion_counts` — TP/FP/FN/TN on ``goal_met`` where the positive
  class is the judge saying *not-met* (the downgrade signal).
* :func:`precision_recall_fd` — precision / recall on the not-met class +
  the false-downgrade rate over gold-met rows. Degenerate denominators
  return ``None`` (AP-6: 0.0 would be a real claim about a quadrant with
  no data).
* :func:`judge_gold_kappa` — judge-vs-gold agreement via
  :func:`services.governance.iaa.krippendorff_alpha_nominal`. For two
  raters with complete data, nominal α coincides with Cohen's κ — the same
  convention Stage 5 used (see the Stage 5 master plan §7.1).
* :func:`expected_calibration_error` — reliability-diagram ECE of a
  confidence proxy against the gold labels. Diagnostic-only per §2.8; the
  Stage 6 Phase 0 audit (§5) showed the ``criteria_met`` proxy is
  trimodal, so treat the number as a sanity plot, not a calibration curve.
* :func:`flip_rate` — CoT-gaming verdict-flip rate over (clean, gamed)
  evidence pairs.
* :func:`evaluate_section_2_8_gates` — the decision function. Fail-closed:
  refuses provisional manifests before reading a single metric, and treats
  any undecidable metric as a refusal.

Threshold source: foundation pyramid Decision 5 /
``docs/research/fix2_goaljudge_rubric_feasibility_pyramid.md`` §2.8 —
precision ≥ 0.90, recall ≥ 0.70, false-downgrade ≤ 0.02,
flip ≤ 0.05 (soft 0.10), κ ≥ 0.6; ECE diagnostic-only; flag default-off.

Golden-number anchor: the production-shadow confusion counts in
``docs/research/goaljudge_stage6_replay_audit.md`` §4 (TP=69, FP=8, FN=8,
TN=12 ⇒ precision = recall = 69/77, FD = 8/20, α = 0.4987013…) are pinned
in the L1 test suite against this module.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, NamedTuple

Verdict = Literal["ENABLE", "REFUSE", "REFUSE_PROVISIONAL"]
"""The closed §2.8 decision vocabulary (A3 enum-completeness)."""

_EMPTY_GATES: Mapping[str, str] = MappingProxyType({})

# ───────────────────────────────────────────────────────────────────────────
# §2.8 thresholds (Decision 5 — see module docstring for the source)
# ───────────────────────────────────────────────────────────────────────────

SECTION_2_8_THRESHOLDS: Mapping[str, float] = {
    "precision_min": 0.90,
    "recall_min": 0.70,
    "false_downgrade_max": 0.02,
    "flip_max": 0.05,
    "flip_soft_max": 0.10,
    "kappa_min": 0.60,
}


# ───────────────────────────────────────────────────────────────────────────
# Confusion counts
# ───────────────────────────────────────────────────────────────────────────


class ConfusionCounts(NamedTuple):
    """Quadrant tallies where positive = judge says *not-met*.

    tp — judge not-met ∧ gold not-met (correct downgrade signal)
    fp — judge not-met ∧ gold met     (the harm case: false downgrade)
    fn — judge met     ∧ gold not-met (missed failure)
    tn — judge met     ∧ gold met
    """

    tp: int
    fp: int
    fn: int
    tn: int


def _require_matching_keys(
    left: Mapping[str, Any], right: Mapping[str, Any], *, what: str
) -> None:
    if not left or not right:
        raise ValueError(f"{what}: inputs must be non-empty")
    if set(left) != set(right):
        only_left = sorted(set(left) - set(right))[:5]
        only_right = sorted(set(right) - set(left))[:5]
        raise ValueError(
            f"{what}: key sets differ — the caller must align item_ids "
            f"explicitly, never an implicit intersection. "
            f"only-left={only_left} only-right={only_right}"
        )


def confusion_counts(
    judge: Mapping[str, bool], gold: Mapping[str, bool]
) -> ConfusionCounts:
    """Tally the four quadrants over item_id-aligned verdict maps.

    Both maps are ``item_id → goal_met``. The key sets must match exactly:
    a judge verdict without a gold label (or vice versa) is an upstream
    join bug, and silently dropping it would bias every downstream gate.
    """
    _require_matching_keys(judge, gold, what="confusion_counts")
    tp = fp = fn = tn = 0
    for item_id, j_met in judge.items():
        g_met = gold[item_id]
        if not j_met and not g_met:
            tp += 1
        elif not j_met and g_met:
            fp += 1
        elif j_met and not g_met:
            fn += 1
        else:
            tn += 1
    return ConfusionCounts(tp=tp, fp=fp, fn=fn, tn=tn)


# ───────────────────────────────────────────────────────────────────────────
# Precision / recall / false-downgrade rate
# ───────────────────────────────────────────────────────────────────────────


class PrecisionRecallFD(NamedTuple):
    """§2.8 gate inputs. ``None`` = undecidable (empty denominator)."""

    precision: float | None
    recall: float | None
    false_downgrade_rate: float | None


def precision_recall_fd(counts: ConfusionCounts) -> PrecisionRecallFD:
    """Compute the three §2.8 rate gates from quadrant tallies.

    * precision            = tp / (tp + fp) — share of downgrades deserved
    * recall               = tp / (tp + fn) — share of real failures caught
    * false_downgrade_rate = fp / (fp + tn) — share of *gold-met* (clean
      successful) runs the judge would wrongly downgrade

    A zero denominator returns ``None`` for that metric: 0.0 would assert
    something about data that does not exist (AP-6), and the §2.8
    evaluator maps ``None`` to an *undecidable* gate, which refuses.
    """
    predicted_positive = counts.tp + counts.fp
    gold_negative = counts.tp + counts.fn
    gold_positive = counts.fp + counts.tn
    return PrecisionRecallFD(
        precision=(counts.tp / predicted_positive) if predicted_positive else None,
        recall=(counts.tp / gold_negative) if gold_negative else None,
        false_downgrade_rate=(counts.fp / gold_positive) if gold_positive else None,
    )


# ───────────────────────────────────────────────────────────────────────────
# Judge-vs-gold agreement (κ via nominal α)
# ───────────────────────────────────────────────────────────────────────────


def judge_gold_kappa(judge: Mapping[str, bool], gold: Mapping[str, bool]) -> float:
    """Nominal Krippendorff α over the (judge, gold) pair per item.

    Two raters, complete data ⇒ α coincides with Cohen's κ; Stage 5 used
    the identical convention for its IAA gate, so the §2.8 ``κ ≥ 0.6``
    prerequisite reads this value directly.

    Returns ``NaN`` when agreement is undefined (e.g. only one class
    appears overall) — same contract as the underlying iaa primitive.
    """
    # Local import: Horizontal→Horizontal within services/governance/
    # (mirrors row_to_goldset_item's iaa import).
    from services.governance.iaa import krippendorff_alpha_nominal

    _require_matching_keys(judge, gold, what="judge_gold_kappa")
    items = [
        ["true" if judge[i] else "false", "true" if gold[i] else "false"]
        for i in sorted(judge)
    ]
    return krippendorff_alpha_nominal(items)


# ───────────────────────────────────────────────────────────────────────────
# Expected calibration error (diagnostic-only)
# ───────────────────────────────────────────────────────────────────────────


def expected_calibration_error(
    confidence: Mapping[str, float],
    gold: Mapping[str, bool],
    *,
    n_bins: int = 10,
) -> float:
    """Reliability-diagram ECE of a confidence proxy vs. the gold labels.

    ``confidence`` maps item_id → proxy ∈ [0, 1] read as "the judge's
    score that the goal was met" (Stage 6 uses ``criteria_met``).
    Equal-width bins (index ``min(int(c · n_bins), n_bins − 1)`` so 1.0
    lands in the top bin); per-bin contribution is
    ``|bin|/N · |mean(confidence) − fraction(gold met)|``.

    Diagnostic-only per §2.8 — never feeds a gate. The Phase 0 audit (§5)
    found the proxy effectively trimodal {0, 0.5, ~1}; report the number
    with that caveat.
    """
    _require_matching_keys(confidence, gold, what="expected_calibration_error")
    out_of_range = {k: v for k, v in confidence.items() if not 0.0 <= v <= 1.0}
    if out_of_range:
        sample = dict(sorted(out_of_range.items())[:3])
        raise ValueError(f"confidence values out of range [0, 1]: {sample}")
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for item_id, conf in confidence.items():
        bins[min(int(conf * n_bins), n_bins - 1)].append((conf, gold[item_id]))
    total = len(confidence)
    ece = 0.0
    for members in bins:
        if not members:
            continue
        mean_conf = sum(c for c, _ in members) / len(members)
        frac_met = sum(1 for _, g in members if g) / len(members)
        ece += (len(members) / total) * abs(mean_conf - frac_met)
    return ece


# ───────────────────────────────────────────────────────────────────────────
# CoT-gaming flip rate
# ───────────────────────────────────────────────────────────────────────────


def flip_rate(pairs: Sequence[tuple[bool, bool]]) -> float:
    """Fraction of (clean_verdict, gamed_verdict) pairs whose ``goal_met``
    flips under fabricated-progress pressure. Either direction counts —
    a judge argued *into* met and a judge argued *out of* met are both
    instability."""
    if not pairs:
        raise ValueError("flip_rate: pairs must be non-empty")
    return sum(1 for clean, gamed in pairs if clean != gamed) / len(pairs)


# ───────────────────────────────────────────────────────────────────────────
# §2.8 gate evaluator — fail-closed decision function
# ───────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GateDecision:
    """Outcome of the §2.8 evaluation. Deeply immutable: the dataclass is
    frozen AND ``gates`` is a read-only mapping view — a caller can never
    falsify the decision record after the fact.

    verdict — ``"ENABLE"`` (every gate passed on a v1 manifest),
              ``"REFUSE"`` (≥ 1 gate failed or was undecidable),
              ``"REFUSE_PROVISIONAL"`` (manifest is not a v1 freeze; no
              metric was evaluated).
    gates   — per-gate status: ``"pass"`` / ``"fail"`` / ``"undecidable"``.
              Empty for ``REFUSE_PROVISIONAL``.
    reasons — human-readable lines for every non-pass condition.
    """

    verdict: Verdict
    gates: Mapping[str, str] = field(default=_EMPTY_GATES)
    reasons: tuple[str, ...] = ()


def _gate(
    name: str,
    value: float | None,
    *,
    threshold: float,
    direction: str,
    gates: dict[str, str],
    reasons: list[str],
) -> None:
    """Evaluate one gate in place. ``direction`` is ``"min"`` (value must be
    ≥ threshold) or ``"max"`` (value must be ≤ threshold). ``None``/NaN ⇒
    undecidable."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        gates[name] = "undecidable"
        reasons.append(
            f"{name}: undecidable (no data / empty denominator) — fail-closed per §2.8"
        )
        return
    ok = value >= threshold if direction == "min" else value <= threshold
    gates[name] = "pass" if ok else "fail"
    if not ok:
        cmp = "≥" if direction == "min" else "≤"
        reasons.append(f"{name}: {value:.4f} violates gate {cmp} {threshold}")


def evaluate_section_2_8_gates(
    *,
    precision: float | None,
    recall: float | None,
    false_downgrade_rate: float | None,
    kappa: float,
    flip: float | None,
    manifest: Mapping[str, Any],
) -> GateDecision:
    """The §2.8 enable decision. Fail-closed at every layer:

    1. ``gate_goldset_v1_floors(manifest)`` runs first — a provisional /
       malformed manifest returns ``REFUSE_PROVISIONAL`` before any metric
       is read (per-cell power doesn't exist, so no number is decision-grade;
       see the Stage 6 plan §5 on FD undecidability at v0.9).
    2. Each metric gate is inclusive at its threshold; ``None``/NaN ⇒
       *undecidable* ⇒ the overall verdict is ``REFUSE``.
    3. A flip rate in the soft band (0.05, 0.10] still refuses, but the
       reason names the soft ceiling so a reviewer knows §2.8 leaves a
       judgment call there.

    The function never mutates ``manifest`` and never flips any flag —
    it produces the *evaluated decision*; acting on it is a human step.
    """
    # Local import: Horizontal→Horizontal within services/governance/.
    from services.governance.goaljudge_goldset_dataset import (
        AssemblyInvariantError,
        gate_goldset_v1_floors,
    )

    try:
        gate_goldset_v1_floors(manifest)
    except AssemblyInvariantError as exc:
        return GateDecision(
            verdict="REFUSE_PROVISIONAL",
            gates=_EMPTY_GATES,
            reasons=(f"manifest is not a v1 freeze: {exc}",),
        )

    t = SECTION_2_8_THRESHOLDS
    gates: dict[str, str] = {}
    reasons: list[str] = []
    _gate(
        "precision",
        precision,
        threshold=t["precision_min"],
        direction="min",
        gates=gates,
        reasons=reasons,
    )
    _gate(
        "recall",
        recall,
        threshold=t["recall_min"],
        direction="min",
        gates=gates,
        reasons=reasons,
    )
    _gate(
        "false_downgrade_rate",
        false_downgrade_rate,
        threshold=t["false_downgrade_max"],
        direction="max",
        gates=gates,
        reasons=reasons,
    )
    _gate(
        "kappa",
        kappa,
        threshold=t["kappa_min"],
        direction="min",
        gates=gates,
        reasons=reasons,
    )
    _gate(
        "flip",
        flip,
        threshold=t["flip_max"],
        direction="max",
        gates=gates,
        reasons=reasons,
    )
    if (
        gates.get("flip") == "fail"
        and flip is not None
        and not math.isnan(flip)
        and flip <= t["flip_soft_max"]
    ):
        reasons.append(
            f"flip: {flip:.4f} is within the §2.8 soft ceiling "
            f"≤ {t['flip_soft_max']} — refusing conservatively, but this "
            "gate admits a documented judgment call"
        )

    verdict: Verdict = "ENABLE" if set(gates.values()) == {"pass"} else "REFUSE"
    return GateDecision(
        verdict=verdict,
        gates=MappingProxyType(gates),
        reasons=tuple(reasons),
    )
