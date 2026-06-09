#!/usr/bin/env python3
"""Compute Krippendorff's α for Stage 5 gold-set human IAA label sheets.

Reads a filled gold-set sheet CSV (``r1_*`` / ``r2_*`` columns) and reports α on
the primary ``goal_met`` unit. For two raters with complete data this equals
Cohen's κ; the general nominal formula handles ≥2 raters and missing labels.

Usage:
  python scripts/compute_goaljudge_stage5_alpha.py \\
    docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_sheet.csv
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from itertools import combinations
from pathlib import Path


def landis_koch_band(alpha: float) -> str:
    if alpha < 0:
        return "poor"
    if alpha <= 0.20:
        return "slight"
    if alpha <= 0.40:
        return "fair"
    if alpha <= 0.60:
        return "moderate"
    if alpha <= 0.80:
        return "substantial"
    return "almost perfect"


def krippendorff_alpha_nominal(items: list[list[str]]) -> float:
    """α for nominal data. Each inner list is one item's rater labels (omit missing)."""
    do_num = do_den = 0
    all_labels: Counter[str] = Counter()
    for labels in items:
        present = [x for x in labels if x]
        m = len(present)
        if m < 2:
            continue
        all_labels.update(present)
        for a, b in combinations(present, 2):
            do_den += 1
            do_num += int(a != b)
    if do_den == 0:
        return float("nan")
    do = do_num / do_den
    n = sum(all_labels.values())
    if n < 2:
        return float("nan")
    de = 1 - sum(c * (c - 1) for c in all_labels.values()) / (n * (n - 1))
    return 1 - (do / de) if de else float("nan")


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _normalize_bool_label(raw: str) -> str:
    value = raw.strip().lower()
    if value in {"true", "t", "yes", "y", "1"}:
        return "true"
    if value in {"false", "f", "no", "n", "0"}:
        return "false"
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute Stage 5 gold-set Krippendorff's α")
    parser.add_argument(
        "sheet",
        type=Path,
        help="Label sheet CSV with r1_goal_met and r2_goal_met columns",
    )
    parser.add_argument(
        "--column",
        default="goal_met",
        help="Primary agreement column suffix (default: goal_met → r1_goal_met / r2_goal_met)",
    )
    args = parser.parse_args()

    rows = _load_rows(args.sheet)
    r1_col = f"r1_{args.column}"
    r2_col = f"r2_{args.column}"

    items: list[list[str]] = []
    graded = 0
    agreements = 0
    for row in rows:
        r1 = _normalize_bool_label(row.get(r1_col, ""))
        r2 = _normalize_bool_label(row.get(r2_col, ""))
        labels = [x for x in (r1, r2) if x]
        if len(labels) < 2:
            continue
        graded += 1
        if r1 == r2:
            agreements += 1
        items.append(labels)

    if not graded:
        raise SystemExit(f"No rows with both {r1_col} and {r2_col} filled")

    alpha = krippendorff_alpha_nominal(items)
    band = landis_koch_band(alpha)

    print(f"rows={graded} agreements={agreements} alpha={alpha:.4f} band={band}")
    print(f"gate={'PASS' if alpha >= 0.8 else 'FAIL'} (threshold α ≥ 0.8)")


if __name__ == "__main__":
    main()
