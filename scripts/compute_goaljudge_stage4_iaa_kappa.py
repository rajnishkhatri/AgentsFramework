#!/usr/bin/env python3
"""Compute Cohen's κ for Stage 4 A2 human IAA grader sheets (G5).

Reads two filled copies of goaljudge_stage4_a2_iaa_grader_sheet.csv (or a single
sheet with r1_* and r2_* columns) and reports κ on the primary ``a2_fail`` unit.

Usage:
  python scripts/compute_goaljudge_stage4_iaa_kappa.py \\
    docs/IAA/goalJudge/goaljudge_stage4_a2_iaa_grader_sheet.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def cohen_kappa(a: list[str], b: list[str]) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("label lists must be non-empty and equal length")
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def landis_koch_band(kappa: float) -> str:
    if kappa < 0:
        return "poor"
    if kappa <= 0.20:
        return "slight"
    if kappa <= 0.40:
        return "fair"
    if kappa <= 0.60:
        return "moderate"
    if kappa <= 0.80:
        return "substantial"
    return "almost perfect"


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute Stage 4 A2 IAA Cohen's κ")
    parser.add_argument(
        "sheet",
        type=Path,
        help="Grader sheet CSV with r1_a2_fail and r2_a2_fail columns",
    )
    parser.add_argument(
        "--column",
        default="a2_fail",
        help="Primary agreement column suffix (default: a2_fail → r1_a2_fail / r2_a2_fail)",
    )
    args = parser.parse_args()

    rows = _load_rows(args.sheet)
    r1_col = f"r1_{args.column}"
    r2_col = f"r2_{args.column}"

    graded = [
        row for row in rows
        if row.get(r1_col, "").strip() and row.get(r2_col, "").strip()
    ]
    if not graded:
        raise SystemExit(f"No rows with both {r1_col} and {r2_col} filled")

    r1 = [row[r1_col].strip().upper() for row in graded]
    r2 = [row[r2_col].strip().upper() for row in graded]
    kappa = cohen_kappa(r1, r2)
    band = landis_koch_band(kappa)
    agreements = sum(x == y for x, y in zip(r1, r2))

    print(f"rows={len(graded)} agreements={agreements} kappa={kappa:.4f} band={band}")
    print(f"gate={'PASS' if kappa >= 0.8 else 'FAIL'} (threshold κ ≥ 0.8)")


if __name__ == "__main__":
    main()
