#!/usr/bin/env python3
"""Compute Krippendorff's α for Stage 5 gold-set human IAA label sheets.

Reads a filled gold-set sheet CSV (``r1_*`` / ``r2_*`` columns) and reports α
on the primary ``goal_met`` unit. For two raters with complete data this
equals Cohen's κ; the general nominal formula handles ≥2 raters and missing
labels.

The α math, the Landis-Koch band, the boolean normalization, and the
disagreement-diff helper all live in :mod:`services.governance.iaa` (L1
horizontal). This script is a thin CLI wrapper so the L1 module can be
imported by Phase 6 assembly and by the manifest builder without forking
the algorithm.

Usage:
  python scripts/compute_goaljudge_stage5_alpha.py \\
    docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_sheet.csv
  python scripts/compute_goaljudge_stage5_alpha.py \\
    docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv \\
    --diff cache/goaljudge_eval/stage5_full_alpha_disagreements.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.governance.iaa import (
    compute_disagreement_diff,
    krippendorff_alpha_nominal,
    landis_koch_band,
    normalize_bool_label,
)


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _write_disagreement_diff(path: Path, diff: list[dict[str, str]]) -> None:
    """Emit the disagreement diff as ``item_id, r1, r2`` CSV — the
    adjudicator's working copy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["item_id", "r1", "r2"])
        writer.writeheader()
        writer.writerows(diff)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute Stage 5 gold-set Krippendorff's α"
    )
    parser.add_argument(
        "sheet",
        type=Path,
        help="Label sheet CSV with r1_goal_met and r2_goal_met columns",
    )
    parser.add_argument(
        "--column",
        default="goal_met",
        help=(
            "Primary agreement column suffix "
            "(default: goal_met → r1_goal_met / r2_goal_met)"
        ),
    )
    parser.add_argument(
        "--diff",
        type=Path,
        default=None,
        help=(
            "Optional path to write the disagreement diff CSV. Phase 5 "
            "step 4 adjudication consumes this directly."
        ),
    )
    args = parser.parse_args()

    rows = _load_rows(args.sheet)
    r1_col = f"r1_{args.column}"
    r2_col = f"r2_{args.column}"

    items: list[list[str]] = []
    graded = 0
    agreements = 0
    for row in rows:
        r1 = normalize_bool_label(row.get(r1_col, ""))
        r2 = normalize_bool_label(row.get(r2_col, ""))
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

    if args.diff is not None:
        diff = compute_disagreement_diff(rows, column=args.column)
        _write_disagreement_diff(args.diff, diff)
        print(f"wrote disagreement diff ({len(diff)} rows) to {args.diff}")


if __name__ == "__main__":
    main()
