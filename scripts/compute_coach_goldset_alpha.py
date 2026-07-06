"""Task 3.7c — Krippendorff's α on the coach gold-set ``answer_leakage`` axis.

Reads a filled combined sheet (``r1_answer_leakage`` / ``r2_answer_leakage``
columns) and reports α on the binary ``answer_leakage`` unit. For two raters
with complete data this equals Cohen's κ; the general nominal formula handles
missing labels and ≥2 raters.

The α math, the Landis–Koch band, and the boolean normalization all live in
:mod:`services.governance.iaa` (L1 horizontal) — this script is a thin CLI so
the algorithm is never forked. NaN (under-defined input) surfaces as ``None``,
never a fake ``0.0`` (AP-6), so a downstream gate cannot misread chance
agreement.

Usage::

    .venv/bin/python -m scripts.compute_coach_goldset_alpha \\
        docs/IAA/coach/goldset/coach_goldset_combined_sheet.csv \\
        --diff cache/coach_eval/coach_goldset_alpha_disagreements.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.governance.iaa import (
    krippendorff_alpha_nominal,
    landis_koch_band,
    normalize_bool_label,
)

__all__ = ["alpha_from_combined_rows", "main"]

_R1 = "r1_answer_leakage"
_R2 = "r2_answer_leakage"


def alpha_from_combined_rows(rows: list[dict[str, Any]]) -> float | None:
    """Krippendorff α on ``answer_leakage`` across the combined sheet.

    Each row contributes one ``[r1, r2]`` pair of normalized boolean labels
    (empty string = 'this rater did not label this item'). Returns ``None`` when
    the input is under-defined (empty, <2 raters anywhere, or a single class) —
    NaN→None, never ``0.0``.
    """
    items: list[list[str]] = []
    for r in rows:
        pair = [
            normalize_bool_label(r.get(_R1, "")),
            normalize_bool_label(r.get(_R2, "")),
        ]
        items.append([x for x in pair if x != ""])
    alpha = krippendorff_alpha_nominal(items)
    return None if math.isnan(alpha) else alpha


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _write_disagreements(
    path: Path, rows: list[dict[str, Any]]
) -> None:  # pragma: no cover - CLI
    diffs = [
        {
            "item_id": r.get("item_id", ""),
            "r1": normalize_bool_label(r.get(_R1, "")),
            "r2": normalize_bool_label(r.get(_R2, "")),
        }
        for r in rows
        if normalize_bool_label(r.get(_R1, ""))
        and normalize_bool_label(r.get(_R2, ""))
        and normalize_bool_label(r.get(_R1, "")) != normalize_bool_label(r.get(_R2, ""))
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["item_id", "r1", "r2"])
        writer.writeheader()
        writer.writerows(diffs)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - thin CLI
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sheet", type=Path, help="filled combined sheet CSV")
    parser.add_argument(
        "--diff", type=Path, default=None, help="write disagreement diff CSV here"
    )
    args = parser.parse_args(argv)

    rows = _load_rows(args.sheet)
    alpha = alpha_from_combined_rows(rows)
    if args.diff is not None:
        _write_disagreements(args.diff, rows)

    if alpha is None:
        print("α = None (under-defined: empty / <2 raters / single class)")
        print("verdict: INSUFFICIENT — cannot clear the α ≥ 0.80 gate")
        return 0
    band = landis_koch_band(alpha)
    gate = "PASS" if alpha >= 0.80 else "FAIL"
    print(f"α (answer_leakage) = {alpha:.4f}  [{band}]  gate α≥0.80: {gate}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
