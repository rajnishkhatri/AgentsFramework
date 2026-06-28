#!/usr/bin/env python3
"""Merge A1's r1_* columns and A2's r2_* columns into the combined full sheet.

Phase 5-D pre-step. Runs after A2 cold-blind labeling completes. The full
sheet is the canonical IAA artifact that ``compute_goaljudge_stage5_alpha.py``
consumes. The blindness firewall lifts at this point (per A2 plan §9.4) —
the coordinator role can read both sheets together.

The full sheet schema is the source of truth for column order. A1's r1_*
labels are joined into the full sheet by item_id, then A2's r2_* labels are
joined the same way. Identity columns (split, provenance, stratum, domain,
planning_depth, tool_cluster, task, claim, evidence_summary) come from the
A1 sheet — they were authored at full-sheet build time and A2's sheet derives
``claim`` and ``evidence_summary`` independently from corpus to enforce
blindness, so a value-level cross-check against A1 should not be expected.

Validates row-set parity (both sheets carry the same 79 GJ-F-* ids) and
fail-fast if they drift.

Usage:
  python scripts/merge_goaljudge_stage5_iaa_sheets.py \\
    --a1 docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator1_sheet.csv \\
    --a2 docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator2_sheet.csv \\
    --full docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

R1_COLS = (
    "r1_goal_met",
    "r1_graceful_failure",
    "r1_partial_fraction",
    "r1_failure_mode",
)
R2_COLS = (
    "r2_goal_met",
    "r2_graceful_failure",
    "r2_partial_fraction",
    "r2_failure_mode",
)
R1_REVIEW_COLS = ("r1_review_assessment", "r1_review_open_question")


def _load(path: Path) -> tuple[list[str], dict[str, dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return reader.fieldnames or [], {r["item_id"]: r for r in rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a1", type=Path, required=True)
    parser.add_argument("--a2", type=Path, required=True)
    parser.add_argument("--full", type=Path, required=True)
    args = parser.parse_args()

    a1_fields, a1 = _load(args.a1)
    a2_fields, a2 = _load(args.a2)
    full_fields, full = _load(args.full)

    if set(a1) != set(a2):
        print(
            f"FATAL: A1/A2 row sets diverge: only in A1={sorted(set(a1) - set(a2))[:5]} only in A2={sorted(set(a2) - set(a1))[:5]}",
            file=sys.stderr,
        )
        return 1
    if set(a1) != set(full):
        print(
            f"FATAL: A1/full row sets diverge: only in A1={sorted(set(a1) - set(full))[:5]} only in full={sorted(set(full) - set(a1))[:5]}",
            file=sys.stderr,
        )
        return 1

    a1_filled = sum(1 for r in a1.values() if r.get("r1_goal_met", "").strip())
    a2_filled = sum(1 for r in a2.values() if r.get("r2_goal_met", "").strip())
    if a1_filled != len(a1):
        print(
            f"FATAL: A1 has {a1_filled}/{len(a1)} r1_goal_met filled — A1 labeling is incomplete",
            file=sys.stderr,
        )
        return 1
    if a2_filled != len(a2):
        print(
            f"FATAL: A2 has {a2_filled}/{len(a2)} r2_goal_met filled — A2 labeling is incomplete",
            file=sys.stderr,
        )
        return 1

    out_rows: list[dict[str, str]] = []
    for item_id in sorted(full):
        target = dict(full[item_id])
        # Copy r1_* from A1
        for col in R1_COLS + R1_REVIEW_COLS:
            target[col] = a1[item_id].get(col, "")
        # Copy r2_* from A2 (note: A2 has its own r2_review_* but full schema has r1_review_* not r2_review_*)
        for col in R2_COLS:
            target[col] = a2[item_id].get(col, "")
        out_rows.append(target)

    with args.full.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=full_fields)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Merged {len(out_rows)} rows → {args.full}")
    print(
        f"  r1_goal_met filled: {sum(1 for r in out_rows if r.get('r1_goal_met', '').strip())}"
    )
    print(
        f"  r2_goal_met filled: {sum(1 for r in out_rows if r.get('r2_goal_met', '').strip())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
