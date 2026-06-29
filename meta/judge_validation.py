"""Judge validation: TPR/TNR + Rogan-Gladen, atop the calibration primitives.

Pyramid layer:   L1 Deterministic -- pure functions, no I/O in the metric core,
                 no LLM. (The CLI at the bottom does file I/O; the math does not.)
Architecture:    Horizontal (``meta/``). Composes -- never re-implements --
                 ``services.governance.goaljudge_calibration`` (the existing,
                 audit-pinned confusion/precision-recall math). ``meta/`` may
                 import ``services/`` (drift.py, run_eval.py already do); it must
                 NOT import ``orchestration/`` (tests/architecture rule).

Why this module exists (vs. ``meta/drift.py`` and ``goaljudge_calibration``):

* ``drift.py`` Level 2 computes Cohen's **kappa** -- a fine *drift* signal
  (chance-corrected, single scalar), but kappa **hides directionality**: it
  cannot tell you the judge's recall on real failures (TPR) apart from its
  false-alarm rate on clean runs. For a *governance* judge the asymmetry is the
  whole point -- a missed failure costs more than a false alarm -- so kappa is
  kept as the drift signal and TPR/TNR is added as the *validation* gate.
* ``goaljudge_calibration`` already computes ``recall`` (= TPR for the
  *not-met* / failure-detection class) and ``false_downgrade_rate`` (= FPR, the
  false alarm on gold-met runs). What it does NOT surface, and what a validation
  report needs, is: a **named TNR** (= 1 - FD-rate), the full FPR/FNR pair, and
  the **Rogan-Gladen** prevalence correction.

Positive-class convention (inherited from ``goaljudge_calibration``, do NOT
flip it): **positive = the judge says "not-met"** -- i.e. positive = detecting a
failure. Therefore, on the ``ConfusionCounts`` quadrants:

* TPR (sensitivity / recall) = tp / (tp + fn) -- real failures caught.
* TNR (specificity)          = tn / (tn + fp) -- clean runs correctly passed.
* FPR (false-downgrade rate) = fp / (fp + tn) -- clean runs wrongly failed.
* FNR (miss rate)            = fn / (fn + tp) -- real failures missed.

Rogan-Gladen (1978) corrects an *observed* failure prevalence measured by an
imperfect judge back to the *true* prevalence, given the judge's TPR/FPR::

    theta_true = (theta_obs - FPR) / (TPR - FPR)

It is undefined when ``TPR == FPR`` (the judge has no discriminative power) and
its raw output can fall outside [0, 1] under sampling noise; we clamp to [0, 1]
and report the unclamped value alongside, mirroring the AP-6 "``None`` when
undecidable, never a fabricated 0.0" convention the calibration module uses.

Threshold default: TPR >= 0.90 AND TNR >= 0.90 (the plan's symmetric 90% floor;
override per the judge's real asymmetric cost). This is a *validation* gate --
distinct from the §2.8 *enable* gate in ``goaljudge_calibration``, which also
folds in kappa, flip-rate, ECE, and the v1-manifest freeze check.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import NamedTuple

from services.governance.goaljudge_calibration import (
    ConfusionCounts,
    confusion_counts,
)

# ───────────────────────────────────────────────────────────────────────────
# Default validation thresholds (plan Track B-1: symmetric 90% floor)
# ───────────────────────────────────────────────────────────────────────────

DEFAULT_TPR_MIN = 0.90
DEFAULT_TNR_MIN = 0.90


# ───────────────────────────────────────────────────────────────────────────
# Rates (TPR / TNR / FPR / FNR) -- named, with the calibration convention
# ───────────────────────────────────────────────────────────────────────────


class JudgeRates(NamedTuple):
    """The four directional rates. ``None`` = undecidable (empty denominator).

    Positive class = judge-says-not-met (failure detection), so:

    * ``tpr`` -- recall / sensitivity: tp / (tp + fn)
    * ``tnr`` -- specificity:          tn / (tn + fp)  (= 1 - fpr)
    * ``fpr`` -- false-downgrade rate: fp / (fp + tn)  (= 1 - tnr)
    * ``fnr`` -- miss rate:            fn / (fn + tp)  (= 1 - tpr)

    A zero denominator yields ``None`` for that rate: 0.0 would assert a fact
    about a quadrant with no data (AP-6).
    """

    tpr: float | None
    tnr: float | None
    fpr: float | None
    fnr: float | None


def judge_rates(counts: ConfusionCounts) -> JudgeRates:
    """Compute TPR/TNR/FPR/FNR from the four confusion quadrants.

    Reuses the same quadrant definitions as
    ``services.governance.goaljudge_calibration.ConfusionCounts`` so the two
    modules can never disagree on what a "true positive" is.
    """
    gold_positive = counts.tp + counts.fn  # real failures (judge-positive class)
    gold_negative = counts.tn + counts.fp  # clean runs
    tpr = (counts.tp / gold_positive) if gold_positive else None
    fnr = (counts.fn / gold_positive) if gold_positive else None
    tnr = (counts.tn / gold_negative) if gold_negative else None
    fpr = (counts.fp / gold_negative) if gold_negative else None
    return JudgeRates(tpr=tpr, tnr=tnr, fpr=fpr, fnr=fnr)


# ───────────────────────────────────────────────────────────────────────────
# Rogan-Gladen prevalence correction
# ───────────────────────────────────────────────────────────────────────────


class RoganGladen(NamedTuple):
    """Result of the Rogan-Gladen correction.

    * ``observed`` -- the raw failure prevalence the judge measured.
    * ``corrected`` -- the prevalence corrected for the judge's TPR/FPR,
      clamped to [0, 1]. ``None`` when undecidable (``TPR == FPR`` -- the judge
      has no discriminative power, so no correction is possible).
    * ``corrected_raw`` -- the unclamped value, so a reader can see when the
      estimate fell outside [0, 1] under sampling noise (it is then clamped).
    * ``clamped`` -- True iff ``corrected_raw`` was pulled into range.
    """

    observed: float
    corrected: float | None
    corrected_raw: float | None
    clamped: bool


def rogan_gladen(
    observed_prevalence: float,
    *,
    tpr: float | None,
    fpr: float | None,
) -> RoganGladen:
    """Correct an observed failure prevalence for an imperfect judge.

    ``theta_true = (theta_obs - FPR) / (TPR - FPR)`` (Rogan & Gladen, 1978).

    Undecidable -> ``corrected=None`` (never a fabricated number) when either
    rate is missing or ``TPR == FPR`` (zero discriminative power: the
    denominator vanishes). The unclamped estimate is always reported in
    ``corrected_raw`` so out-of-range estimates are visible, not hidden.
    """
    if not 0.0 <= observed_prevalence <= 1.0:
        raise ValueError(
            f"observed_prevalence must be in [0, 1], got {observed_prevalence!r}"
        )
    if tpr is None or fpr is None or tpr == fpr:
        return RoganGladen(
            observed=observed_prevalence,
            corrected=None,
            corrected_raw=None,
            clamped=False,
        )
    raw = (observed_prevalence - fpr) / (tpr - fpr)
    clamped_value = min(1.0, max(0.0, raw))
    return RoganGladen(
        observed=observed_prevalence,
        corrected=clamped_value,
        corrected_raw=raw,
        clamped=clamped_value != raw,
    )


# ───────────────────────────────────────────────────────────────────────────
# Validation report + gate
# ───────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class JudgeValidation:
    """A judge's validation outcome against a held-out human-labeled set.

    ``passed`` is the gate: TPR and TNR both meet their floors. An undecidable
    rate (``None``) fails the gate -- a judge you cannot measure is a judge you
    cannot trust (fail-closed, mirroring the §2.8 evaluator).
    """

    counts: ConfusionCounts
    rates: JudgeRates
    rogan_gladen: RoganGladen
    tpr_min: float
    tnr_min: float
    passed: bool
    reasons: tuple[str, ...]


def validate_judge(
    judge: Mapping[str, bool],
    gold: Mapping[str, bool],
    *,
    tpr_min: float = DEFAULT_TPR_MIN,
    tnr_min: float = DEFAULT_TNR_MIN,
) -> JudgeValidation:
    """Validate a judge against item_id-aligned human labels.

    Both maps are ``item_id -> goal_met`` (True = met), the same shape and
    key-set discipline ``confusion_counts`` enforces (an unmatched key set is an
    upstream join bug and raises -- never a silent intersection).

    The Rogan-Gladen ``observed_prevalence`` is the judge's measured *failure*
    rate (share of items the judge marked not-met), corrected back to the true
    failure rate using the judge's own TPR/FPR measured on this set.
    """
    counts = confusion_counts(judge, gold)
    rates = judge_rates(counts)

    n = counts.tp + counts.fp + counts.fn + counts.tn
    observed_failure_prevalence = (counts.tp + counts.fp) / n if n else 0.0
    rg = rogan_gladen(observed_failure_prevalence, tpr=rates.tpr, fpr=rates.fpr)

    reasons: list[str] = []
    if rates.tpr is None:
        reasons.append(
            "TPR undecidable (no gold-positive / real-failure items) -- "
            "fail-closed: cannot certify failure recall"
        )
    elif rates.tpr < tpr_min:
        reasons.append(f"TPR {rates.tpr:.4f} < floor {tpr_min}")
    if rates.tnr is None:
        reasons.append(
            "TNR undecidable (no gold-negative / clean items) -- "
            "fail-closed: cannot certify false-alarm rate"
        )
    elif rates.tnr < tnr_min:
        reasons.append(f"TNR {rates.tnr:.4f} < floor {tnr_min}")

    return JudgeValidation(
        counts=counts,
        rates=rates,
        rogan_gladen=rg,
        tpr_min=tpr_min,
        tnr_min=tnr_min,
        passed=not reasons,
        reasons=tuple(reasons),
    )


# ───────────────────────────────────────────────────────────────────────────
# Test-retest reliability (2026 MVVP bar) -- judge self-consistency across runs
# ───────────────────────────────────────────────────────────────────────────


class TestRetest(NamedTuple):
    """Judge self-consistency across repeated runs on the SAME items.

    A judge that flips its verdict between identical re-runs is unreliable even
    if its average accuracy looks fine. ``consistency`` is the share of items on
    which EVERY trial agreed; ``mean_majority_fraction`` is the average, per
    item, of the majority verdict's share (1.0 = always unanimous). ``flipped``
    lists the item_ids that disagreed across trials. ``None`` rates mean the
    input was under-defined (no item had >= 2 trials).
    """

    n_items: int
    consistency: float | None
    mean_majority_fraction: float | None
    flipped: tuple[str, ...]


def test_retest(repeated: Mapping[str, list[bool]]) -> TestRetest:
    """Measure judge self-consistency from per-item repeated verdicts.

    ``repeated`` maps ``item_id -> [verdict_trial_1, verdict_trial_2, ...]`` (the
    shape ``residual_fp_revalidation.json`` already records: 5 trials per item).
    An item with fewer than 2 trials is skipped (no retest possible) -- never
    silently counted as consistent (AP-6: don't fabricate agreement from a
    single sample). Returns ``None`` rates when no item is eligible.
    """
    eligible = {i: v for i, v in repeated.items() if len(v) >= 2}
    n = len(eligible)
    if n == 0:
        return TestRetest(
            n_items=0, consistency=None, mean_majority_fraction=None, flipped=()
        )

    flipped: list[str] = []
    majority_fractions: list[float] = []
    for item_id, trials in eligible.items():
        trues = sum(1 for t in trials if t)
        majority = max(trues, len(trials) - trues)
        majority_fractions.append(majority / len(trials))
        if trues != 0 and trues != len(trials):
            flipped.append(item_id)

    consistency = (n - len(flipped)) / n
    mean_majority = sum(majority_fractions) / n
    return TestRetest(
        n_items=n,
        consistency=round(consistency, 4),
        mean_majority_fraction=round(mean_majority, 4),
        flipped=tuple(sorted(flipped)),
    )


# ───────────────────────────────────────────────────────────────────────────
# Position bias (pairwise judging only) -- order-swap agreement
# ───────────────────────────────────────────────────────────────────────────


class PositionBias(NamedTuple):
    """Order-dependence of a PAIRWISE judge (A-vs-B preference).

    Only meaningful when the judge compares two candidates and could be swayed
    by which one is presented first. For each item we have the verdict with the
    original order and with the candidates swapped; a *consistent* judge picks
    the same underlying winner both ways. ``agreement`` is the share of items
    whose decision was order-invariant; ``first_position_rate`` is how often the
    judge preferred whichever candidate was shown FIRST (0.5 = no positional
    pull; far from 0.5 = bias). ``None`` when there is no pairwise data -- which
    is the case for the single-answer GoalJudge, so this stays N/A there.
    """

    n_items: int
    agreement: float | None
    first_position_rate: float | None
    inconsistent: tuple[str, ...]


def position_bias(
    original: Mapping[str, bool],
    swapped: Mapping[str, bool],
) -> PositionBias:
    """Measure pairwise position bias from original vs order-swapped verdicts.

    Convention: each map is ``item_id -> chose_first`` -- ``True`` means the
    judge picked whichever candidate was in the FIRST slot of that presentation.
    A position-invariant judge picks the same real candidate regardless of order,
    so ``original[i]`` and ``swapped[i]`` should be OPPOSITE (the winner moved
    slots). Agreement on the underlying winner = ``original[i] != swapped[i]``.

    Returns ``None`` rates when the key sets don't align or are empty (no
    pairwise data) -- the single-answer GoalJudge has none, so position bias is
    reported N/A rather than a fabricated number.
    """
    keys = set(original) & set(swapped)
    if not keys or set(original) != set(swapped):
        return PositionBias(
            n_items=len(keys), agreement=None, first_position_rate=None, inconsistent=()
        )

    inconsistent: list[str] = []
    first_picks = 0
    for item_id in keys:
        # winner-invariant ⇒ the "chose first" flag flips when slots swap.
        if original[item_id] == swapped[item_id]:
            inconsistent.append(item_id)
        # count first-slot preference across BOTH presentations (2 obs/item).
        first_picks += int(original[item_id]) + int(swapped[item_id])

    n = len(keys)
    agreement = (n - len(inconsistent)) / n
    first_position_rate = first_picks / (2 * n)
    return PositionBias(
        n_items=n,
        agreement=round(agreement, 4),
        first_position_rate=round(first_position_rate, 4),
        inconsistent=tuple(sorted(inconsistent)),
    )


# ───────────────────────────────────────────────────────────────────────────
# CLI -- read the L2/L3 seed + judge verdicts, print the validation report
# ───────────────────────────────────────────────────────────────────────────


def _fmt(x: float | None) -> str:
    return "—" if x is None else f"{x:.4f}"


def run_validation_cli(args: list[str] | None = None) -> int:
    """CLI: validate GoalJudge against the blind-adjudicated L2/L3 seed.

    Reuses the *exact* 3-class -> binary mapping and harness-bug exclusion from
    ``scripts.measure_l2l3_goaljudge`` (single source of truth for the mapping
    rule -- this CLI must never re-derive it). Pairs the judge ``goal_met``
    verdicts against the seed's ``adjudicated`` label, then prints TPR/TNR +
    Rogan-Gladen and exits non-zero if the validation gate fails.

    Exit codes: 0 = pass, 1 = gate failed, 2 = error.
    """
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Judge validation (TPR/TNR + RG)")
    parser.add_argument(
        "--seed",
        type=str,
        default="cache/goaljudge_eval/model_ab_l2l3_goldset_seed.json",
        help="blind-adjudicated human seed (item_id -> adjudicated 3-class)",
    )
    parser.add_argument(
        "--judge",
        type=str,
        # Full-seed verdicts (52 base cascade + 45 growth = 97), aligned 1:1 with the
        # 97-row seed. The base-only file (l2l3_goaljudge_verdicts.json) covered just
        # cases 07-15 and no longer covers the eligible set, so the bare command would
        # abort on incomplete coverage. Mirrors scripts/measure_l2l3_goaljudge.GJ_VERDICTS.
        default="cache/model_ab_answer/l2l3_full97_goaljudge_verdicts.json",
        help="judge verdicts (item_id -> {goal_met}) to validate",
    )
    parser.add_argument(
        "--mapping",
        choices=["strict", "lenient", "exclude-partial"],
        default="strict",
        help="seed 3-class -> binary mapping (see measure_l2l3_goaljudge)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="drop the 15 harness-bug items (env defects, not judge errors)",
    )
    parser.add_argument("--tpr-min", type=float, default=DEFAULT_TPR_MIN)
    parser.add_argument("--tnr-min", type=float, default=DEFAULT_TNR_MIN)
    parser.add_argument(
        "--retest",
        type=str,
        default=None,
        help=(
            "optional path to a per-item repeated-verdict JSON "
            "(residual_fp_revalidation.json shape: cases[].verdicts[].goal_met); "
            "prints judge test-retest self-consistency"
        ),
    )
    parsed = parser.parse_args(args)

    # Single source of truth for the mapping + exclusion rule.
    from scripts.measure_l2l3_goaljudge import _gold_met, _is_excluded_from_clean

    try:
        seed = json.loads(Path(parsed.seed).read_text())
        gj = json.loads(Path(parsed.judge).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error reading inputs: {exc}")
        return 2

    rows = {r["item_id"]: r for r in seed["rows"]}
    judge: dict[str, bool] = {}
    gold: dict[str, bool] = {}
    eligible: list[str] = []
    for item_id, row in rows.items():
        if parsed.clean and _is_excluded_from_clean(item_id):
            continue
        g = _gold_met(row["adjudicated"], parsed.mapping)
        if g is None:  # exclude-partial drops partial rows
            continue
        eligible.append(item_id)
        if item_id not in gj:
            continue
        judge[item_id] = bool(gj[item_id]["goal_met"])
        gold[item_id] = g

    if not judge:
        print("no aligned (judge, gold) items after mapping -- nothing to validate")
        return 2
    if len(judge) < len(eligible):
        print(
            f"error: judge verdicts cover only {len(judge)}/{len(eligible)} eligible "
            f"seed items — incomplete validation set (missing verdicts are not "
            f"silently ignored)"
        )
        return 2

    result = validate_judge(judge, gold, tpr_min=parsed.tpr_min, tnr_min=parsed.tnr_min)
    c, r, rg = result.counts, result.rates, result.rogan_gladen
    verdict = "PASS" if result.passed else "FAIL"
    print(
        f"VALIDATION: {verdict}  (n={c.tp + c.fp + c.fn + c.tn}, "
        f"mapping={parsed.mapping}, clean={parsed.clean})"
    )
    print(f"  confusion  tp={c.tp} fp={c.fp} fn={c.fn} tn={c.tn}")
    print(f"  TPR (recall)      {_fmt(r.tpr)}  (floor {result.tpr_min})")
    print(f"  TNR (specificity) {_fmt(r.tnr)}  (floor {result.tnr_min})")
    print(f"  FPR (false-down)  {_fmt(r.fpr)}")
    print(f"  FNR (miss)        {_fmt(r.fnr)}")
    # Distinguish an UNDECIDABLE correction (TPR==FPR, the judge has no
    # discriminative power) from a real value — both would otherwise print the
    # bare "—" the _fmt(None) yields, which a reader could misread as zero (#11).
    corrected_str = "— (undecidable)" if rg.corrected is None else _fmt(rg.corrected)
    print(
        f"  Rogan-Gladen: observed_failure={_fmt(rg.observed)} "
        f"corrected={corrected_str}"
        + (f" (clamped from {_fmt(rg.corrected_raw)})" if rg.clamped else "")
    )
    for reason in result.reasons:
        print(f"  - {reason}")

    # Optional test-retest self-consistency from a repeated-verdict file
    # (residual_fp_revalidation.json shape). Diagnostic only -- it does not gate.
    if parsed.retest:
        try:
            retest_raw = json.loads(Path(parsed.retest).read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  test-retest: error reading {parsed.retest}: {exc}")
        else:
            repeated: dict[str, list[bool]] = {}
            for case in retest_raw.get("cases", []):
                verdicts = case.get("verdicts", [])
                item = str(case.get("item", case.get("case", "")))
                if item and verdicts:
                    repeated[item] = [bool(v.get("goal_met")) for v in verdicts]
            tr = test_retest(repeated)
            print(
                f"  test-retest (n={tr.n_items}): "
                f"consistency={_fmt(tr.consistency)} "
                f"mean_majority={_fmt(tr.mean_majority_fraction)}"
                + (f" flipped={list(tr.flipped)}" if tr.flipped else "")
            )

    # Position bias only applies to a PAIRWISE judge; the single-answer GoalJudge
    # has no order-swapped data, so we state N/A explicitly rather than silently
    # omit it (a reader must not infer "no bias" from an absent line).
    print("  position-bias: N/A (single-answer judge; pairwise-only metric)")

    return 0 if result.passed else 1


if __name__ == "__main__":
    import sys

    sys.exit(run_validation_cli())
