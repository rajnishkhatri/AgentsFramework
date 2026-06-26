"""Measure GoalJudge vs the L2/L3 seed gold set — diagnosis only, no judge change.

docs/plans (GoalJudge-vs-seed measurement), Steps 2-4. Compares the automated
GoalJudge ``goal_met`` verdicts (harvested by harvest_l2l3_goaljudge.py) against the
human blind-adjudicated seed labels, across 6 cells:
  {full, clean} x {strict, lenient, exclude-partial}.

Reuses services/governance/goaljudge_calibration.py (confusion/precision-recall/kappa/
gate) — NOT hand-rolled. Both that module's maps are ``item_id -> goal_met`` (True =
met); the module treats "not-met" as the positive class internally, so:
  fp = judge not-met ∧ gold met   = FALSE DOWNGRADE (the off-label harm we quantify)
  fn = judge met     ∧ gold not-met = missed failure
We therefore pass natural True=met maps on both sides (no negation).

Partial mapping (seed 3-class -> binary gold goal_met):
  strict          : met <=> adjudicated == "correct"            (partial -> not-met)
  lenient         : met <=> adjudicated in {correct, partial}   (partial -> met)
  exclude-partial : drop partial rows; met <=> "correct"

Clean subset: drop the 15 harness-bug items (8 access-failures + 7 off-topic routing)
from the rater-2 root-cause notes — environment defects, not reasoning the judge
should be measured on.

Outputs cache/goaljudge_eval/model_ab_l2l3_goaljudge_vs_seed.{json,md}.
"""

from __future__ import annotations

import json
from pathlib import Path

from services.governance.goaljudge_calibration import (
    confusion_counts,
    evaluate_section_2_8_gates,
    expected_calibration_error,
    judge_gold_kappa,
    precision_recall_fd,
)

AGENT_ROOT = Path(__file__).resolve().parent.parent
ANSWER_DIR = AGENT_ROOT / "cache" / "model_ab_answer"
GJ_VERDICTS = ANSWER_DIR / "l2l3_goaljudge_verdicts.json"
SEED = AGENT_ROOT / "cache" / "goaljudge_eval" / "model_ab_l2l3_goldset_seed.json"
OUT_JSON = AGENT_ROOT / "cache" / "goaljudge_eval" / "model_ab_l2l3_goaljudge_vs_seed.json"
OUT_MD = AGENT_ROOT / "cache" / "goaljudge_eval" / "model_ab_l2l3_goaljudge_vs_seed.md"

# The 15 harness-bug items (rater-2 root-cause notes): item_id prefixes (12 hex).
ACCESS_FAILURE = [
    "f623fe11", "24ee3d4c", "18f180fd", "6d386b69",
    "6929d618", "b205d8bb", "d0460cfd", "0d11f2f8",
]
OFF_TOPIC = [
    "9c18000e", "17340957", "586630b5", "c6e723be",
    "2ba4b3f5", "f6245521", "3d6637de",
]
HARNESS_BUG_PREFIXES = set(ACCESS_FAILURE + OFF_TOPIC)


def _gold_met(adjudicated: str, mapping: str) -> bool | None:
    """seed 3-class -> binary gold goal_met (True = met); None drops the row."""
    if mapping == "strict":
        return adjudicated == "correct"
    if mapping == "lenient":
        return adjudicated in {"correct", "partial"}
    if mapping == "exclude-partial":
        if adjudicated == "partial":
            return None
        return adjudicated == "correct"
    raise ValueError(f"unknown mapping {mapping!r}")


def _is_harness_bug(item_id: str) -> bool:
    return item_id[:8] in {p[:8] for p in HARNESS_BUG_PREFIXES}


def _cell_metrics(
    items: list[str],
    judge_met: dict[str, bool],
    adjudicated: dict[str, str],
    criteria: dict[str, float | None],
    mapping: str,
) -> dict:
    """One {subset x mapping} cell."""
    judge: dict[str, bool] = {}
    gold: dict[str, bool] = {}
    for i in items:
        g = _gold_met(adjudicated[i], mapping)
        if g is None:  # exclude-partial drops partial rows
            continue
        judge[i] = judge_met[i]
        gold[i] = g

    if not judge:
        return {"n": 0, "note": "no rows after mapping"}

    counts = confusion_counts(judge, gold)
    prf = precision_recall_fd(counts)
    kappa = judge_gold_kappa(judge, gold)

    # ECE on the criteria_met confidence proxy (diagnostic only). Needs a proxy in
    # [0,1] for every graded item; skip rows whose criteria_met is missing.
    conf = {i: float(criteria[i]) for i in judge
            if criteria.get(i) is not None and 0.0 <= float(criteria[i]) <= 1.0}
    ece = (expected_calibration_error({i: conf[i] for i in conf},
                                      {i: gold[i] for i in conf})
           if conf else None)

    return {
        "n": len(judge),
        "tp_judge_notmet_gold_notmet": counts.tp,
        "fp_FALSE_DOWNGRADE": counts.fp,
        "fn_missed_failure": counts.fn,
        "tn": counts.tn,
        "precision": prf.precision,
        "recall": prf.recall,
        "false_downgrade_rate": prf.false_downgrade_rate,
        "kappa": kappa,
        "ece_criteria_met_proxy": ece,
    }


def measure() -> dict:
    gj = json.loads(GJ_VERDICTS.read_text())
    seed = json.loads(SEED.read_text())
    manifest = seed["manifest"]
    rows = {r["item_id"]: r for r in seed["rows"]}

    judge_met = {i: gj[i]["goal_met"] for i in gj}
    adjudicated = {i: rows[i]["adjudicated"] for i in gj}
    criteria = {i: gj[i].get("criteria_met") for i in gj}

    all_items = list(gj)
    clean_items = [i for i in all_items if not _is_harness_bug(i)]

    cells: dict[str, dict] = {}
    for subset_name, items in (("full", all_items), ("clean", clean_items)):
        for mapping in ("strict", "lenient", "exclude-partial"):
            cells[f"{subset_name}/{mapping}"] = _cell_metrics(
                items, judge_met, adjudicated, criteria, mapping)

    # Formal gate (uses the strict/full metrics + the provisional manifest). The
    # seed is provisional -> expect REFUSE_PROVISIONAL (a provisional seed cannot
    # certify the judge). We report this alongside the raw diagnostic metrics.
    strict_full = cells["full/strict"]
    gate = evaluate_section_2_8_gates(
        precision=strict_full.get("precision"),
        recall=strict_full.get("recall"),
        false_downgrade_rate=strict_full.get("false_downgrade_rate"),
        kappa=strict_full.get("kappa", float("nan")),
        flip=None,
        manifest=manifest,
    )

    # Per-arm confusion (strict/full): which models' answers the judge mis-judges.
    per_arm: dict[str, dict] = {}
    for i in all_items:
        arm = gj[i]["arm"]
        g = _gold_met(adjudicated[i], "strict")
        j = judge_met[i]
        d = per_arm.setdefault(arm, {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
        if not j and not g:
            d["tp"] += 1
        elif not j and g:
            d["fp"] += 1  # false downgrade
        elif j and not g:
            d["fn"] += 1
        else:
            d["tn"] += 1

    # Disagreement table (strict/full): judge_met != gold_met.
    disagreements = []
    for i in all_items:
        g = _gold_met(adjudicated[i], "strict")
        j = judge_met[i]
        if j != g:
            disagreements.append({
                "item_id": i,
                "case": gj[i]["case"],
                "arm": gj[i]["arm"],
                "goaljudge_goal_met": j,
                "seed_adjudicated": adjudicated[i],
                "gold_met_strict": g,
                "kind": "false_downgrade" if (not j and g) else "missed_failure",
                "goaljudge_rationale": gj[i].get("rationale", "")[:240],
            })

    return {
        "manifest_ref": {
            "name": manifest["name"],
            "provisional": manifest["provisional"],
            "n_items": len(all_items),
            "seed_alpha_3class": manifest["agreement"]["krippendorff_alpha_3class"],
        },
        "cells": cells,
        "formal_gate": {"verdict": gate.verdict, "gates": dict(gate.gates)},
        "per_arm_confusion_strict_full": per_arm,
        "disagreements_strict_full": disagreements,
    }


def _fmt(x) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.3f}"
    return str(x)


def to_markdown(result: dict) -> str:
    m = result["manifest_ref"]
    L = []
    L.append("# GoalJudge vs L2/L3 Seed Gold Set — Measurement\n")
    L.append(
        f"> **Diagnosis only, no judge code changed.** Gold = the PROVISIONAL "
        f"blind-adjudicated seed (`{m['name']}`, n={m['n_items']}, 2-rater "
        f"α={m['seed_alpha_3class']}). Positive class = *not-met* (the downgrade "
        f"signal): **fp = false downgrade** (judge fails a gold-met answer — the "
        f"off-label harm), fn = missed failure.\n"
    )
    L.append(
        "> Partial mapping: **strict** partial→not-met · **lenient** partial→met · "
        "**exclude-partial** drops partials. **clean** subset removes the 15 "
        "harness-bug items (8 access-failure + 7 off-topic routing).\n"
    )

    L.append("\n## Metrics (6 cells)\n")
    L.append("| cell | n | precision | recall | false-downgrade | κ(judge↔gold) | "
             "fp | fn |")
    L.append("|---|--:|--:|--:|--:|--:|--:|--:|")
    for name, c in result["cells"].items():
        if c.get("n", 0) == 0:
            L.append(f"| {name} | 0 | — | — | — | — | — | — |")
            continue
        L.append(
            f"| {name} | {c['n']} | {_fmt(c['precision'])} | {_fmt(c['recall'])} | "
            f"{_fmt(c['false_downgrade_rate'])} | {_fmt(c['kappa'])} | "
            f"{c['fp_FALSE_DOWNGRADE']} | {c['fn_missed_failure']} |"
        )

    g = result["formal_gate"]
    L.append(f"\n## Formal §2.8 gate verdict: **{g['verdict']}**")
    L.append("\nThe §2.8 evaluator refuses provisional manifests before reading a "
             "metric — `REFUSE_PROVISIONAL` is expected and correct: a provisional "
             "seed cannot certify the judge. The raw metrics above are the "
             "diagnostic finding.\n")

    L.append("\n## Per-arm confusion (strict / full)\n")
    L.append("| arm | tp | fp (false downgrade) | fn | tn |")
    L.append("|---|--:|--:|--:|--:|")
    for arm, d in sorted(result["per_arm_confusion_strict_full"].items()):
        L.append(f"| {arm} | {d['tp']} | {d['fp']} | {d['fn']} | {d['tn']} |")

    L.append("\n## Disagreements (strict / full) — where GoalJudge ≠ the seed\n")
    L.append("| item | case | arm | judge goal_met | seed | kind | rationale |")
    L.append("|---|---|---|:--:|:--:|---|---|")
    for d in result["disagreements_strict_full"]:
        rat = d["goaljudge_rationale"].replace("\n", " ").replace("|", "/")
        L.append(
            f"| {d['item_id'][:8]} | {d['case']} | {d['arm']} | "
            f"{d['goaljudge_goal_met']} | {d['seed_adjudicated']} | {d['kind']} | "
            f"{rat} |"
        )
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    result = measure()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n")
    OUT_MD.write_text(to_markdown(result))
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")
    sf = result["cells"]["full/strict"]
    sc = result["cells"]["clean/strict"]
    print(f"\nstrict/full : precision={_fmt(sf['precision'])} "
          f"recall={_fmt(sf['recall'])} FD={_fmt(sf['false_downgrade_rate'])} "
          f"κ={_fmt(sf['kappa'])}  (fp={sf['fp_FALSE_DOWNGRADE']} fn={sf['fn_missed_failure']})")
    print(f"strict/clean: precision={_fmt(sc['precision'])} "
          f"recall={_fmt(sc['recall'])} FD={_fmt(sc['false_downgrade_rate'])} "
          f"κ={_fmt(sc['kappa'])}  (fp={sc['fp_FALSE_DOWNGRADE']} fn={sc['fn_missed_failure']})")
    print(f"formal gate: {result['formal_gate']['verdict']}")
