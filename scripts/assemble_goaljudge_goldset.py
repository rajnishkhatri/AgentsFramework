#!/usr/bin/env python3
"""Stage 5 Tier 3 — Assemble, freeze, load, verify the gold set v1.

Single-shot pipeline per Tier 3 plan §"Phase 6":

  1. Read the adjudicated full sheet CSV.
  2. For each row, construct ``GoldsetItem(...)`` via
     :func:`services.governance.goaljudge_goldset_dataset.row_to_goldset_item`
     (firewall enforced by the pydantic model).
  3. Assert assembly invariants via
     :func:`assert_assembly_invariants` (cell-coverage + goal_met=false
     share + firewall).
  4. Compute test-split SHA-256 via :func:`compute_test_split_hash`.
  5. (unless --dry-run) Authenticate the real Langfuse client and
     ``upsert_many`` the items into ``goaljudge_goldset_v1``.
  6. Build the v1 manifest via :func:`build_goldset_manifest` and write
     to the configured path.

Usage:
  python scripts/assemble_goaljudge_goldset.py \\
      --sheet docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv \\
      --manifest cache/goaljudge_eval/goldset_v1_manifest.json \\
      --frozen-at 2026-06-09T12:00:00Z \\
      [--dry-run] \\
      [--min-goal-met-false-share 0.60] \\
      [--rubric-version stage4_confirmed]

The script exits non-zero on any invariant violation, and never writes
the manifest if assembly fails — a partial manifest would mask the
violation from Stage 6's diff.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.governance.goaljudge_goldset_dataset import (
    AssemblyInvariantError,
    GoalJudgeGoldsetRepository,
    InMemoryLangfuseDatasetClient,
    assert_assembly_invariants,
    build_goldset_manifest,
    compute_cell_coverage,
    compute_test_split_hash,
    row_to_goldset_item,
)


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _build_dimension_maps(rows: list[dict[str, str]]) -> tuple[
    dict[str, str], dict[str, str], dict[str, str]
]:
    """Carry sheet-side dimension labels into the invariant + manifest
    helpers keyed by ``item_id`` (the labels don't live on the
    GoldsetItem itself).
    """
    stratum_by_id: dict[str, str] = {}
    planning_depth_by_id: dict[str, str] = {}
    tool_cluster_by_id: dict[str, str] = {}
    for row in rows:
        iid = row.get("item_id", "").strip()
        if not iid:
            continue
        stratum_by_id[iid] = row.get("stratum", "").strip()
        planning_depth_by_id[iid] = row.get("planning_depth", "").strip()
        tool_cluster_by_id[iid] = row.get("tool_cluster", "").strip()
    return stratum_by_id, planning_depth_by_id, tool_cluster_by_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assemble, freeze, and (optionally) load the Stage 5 v1 gold set"
    )
    parser.add_argument("--sheet", type=Path, required=True,
                        help="Adjudicated full sheet CSV (Phase 3 builder output, "
                        "post-Phase 5 adjudication).")
    parser.add_argument("--manifest", type=Path, required=True,
                        help="Output path for goldset_v1_manifest.json.")
    parser.add_argument("--frozen-at", type=str, required=True,
                        help="ISO-8601 timestamp recorded as the freeze "
                        "moment in the manifest (e.g. 2026-06-09T12:00:00Z).")
    parser.add_argument("--rubric-version", type=str, default="stage4_confirmed",
                        help="Rubric version string (defaults to "
                        "stage4_confirmed per Tier 2 close).")
    parser.add_argument("--min-goal-met-false-share", type=float, default=0.60,
                        help="Minimum goal_met=false share required "
                        "(default 0.60 per spec §4).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip the Langfuse load step (use the in-memory "
                        "client). The manifest is still written on success.")
    parser.add_argument(
        "--dataset-name",
        type=str,
        default="goaljudge_goldset_v1",
        help="Langfuse dataset name (default: goaljudge_goldset_v1).",
    )
    parser.add_argument(
        "--skip-cell-coverage",
        action="store_true",
        help="Skip D1/D5 cell-coverage floors. Use for smoke runs only; "
        "the production freeze MUST run with floors enforced.",
    )
    parser.add_argument(
        "--provisional",
        action="store_true",
        help="Build a v0.9 provisional manifest: skips cell-coverage "
        "floors (like --skip-cell-coverage) AND records the per-cell "
        "gap summary into the manifest body, plus sets "
        "'provisional': true. Stage 6's gate_goldset_v1_floors() "
        "fails-closed on this — it's intended for downstream "
        "development against an interim artifact.",
    )
    args = parser.parse_args()

    # --- Step 1: read CSV --------------------------------------------------
    if not args.sheet.exists():
        print(f"sheet not found: {args.sheet}", file=sys.stderr)
        sys.exit(2)
    rows = _load_rows(args.sheet)
    if not rows:
        print(f"sheet {args.sheet} has no rows", file=sys.stderr)
        sys.exit(2)

    # --- Step 2: row → GoldsetItem ---------------------------------------
    items = []
    for row in rows:
        try:
            items.append(row_to_goldset_item(row))
        except ValueError as exc:
            print(
                f"row → GoldsetItem failed on item_id={row.get('item_id', '<?>')!r}: "
                f"{exc}",
                file=sys.stderr,
            )
            sys.exit(2)

    stratum_by_id, planning_depth_by_id, tool_cluster_by_id = \
        _build_dimension_maps(rows)

    # --- Step 3: assert assembly invariants -------------------------------
    skip_floors = args.skip_cell_coverage or args.provisional
    try:
        if skip_floors:
            assert_assembly_invariants(
                items,
                min_goal_met_false_share=args.min_goal_met_false_share,
            )
        else:
            # Pass dimension maps so D1/D5 floors are enforced; the
            # default D1_FLOORS / D5_FLOORS apply unless this is a test
            # fixture (small datasets pass --skip-cell-coverage).
            assert_assembly_invariants(
                items,
                planning_depth_by_id=planning_depth_by_id,
                tool_cluster_by_id=tool_cluster_by_id,
                min_goal_met_false_share=args.min_goal_met_false_share,
            )
    except AssemblyInvariantError as exc:
        print(f"assembly invariant violated: {exc}", file=sys.stderr)
        sys.exit(2)

    # Provisional runs: compute per-cell floor gap summary to embed.
    floor_gap_summary: dict[str, int] = {}
    if args.provisional:
        coverage = compute_cell_coverage(rows)
        for cell, gap in coverage.d1_gaps.items():
            if gap > 0:
                floor_gap_summary[cell] = gap
        for cell, gap in coverage.d5_gaps.items():
            if gap > 0:
                floor_gap_summary[cell] = gap

    # --- Step 4: test-split hash ------------------------------------------
    test_split_sha256 = compute_test_split_hash(items)

    # --- Step 5: Langfuse load (dry-run uses in-memory client) ------------
    if args.dry_run:
        client = InMemoryLangfuseDatasetClient()
    else:
        from scripts.langfuse_dataset_client import (
            build_real_langfuse_dataset_client,
        )
        client = build_real_langfuse_dataset_client()

    repo = GoalJudgeGoldsetRepository(client, dataset_name=args.dataset_name)
    inserted = repo.upsert_many(items)
    print(
        f"upserted {inserted} item(s) into {args.dataset_name} "
        f"(dry_run={args.dry_run})"
    )

    # --- Step 6: write the manifest ---------------------------------------
    manifest = build_goldset_manifest(
        items,
        test_split_sha256=test_split_sha256,
        rubric_version=args.rubric_version,
        frozen_at=args.frozen_at,
        stratum_by_id=stratum_by_id,
        planning_depth_by_id=planning_depth_by_id,
        tool_cluster_by_id=tool_cluster_by_id,
        dataset_name=args.dataset_name,
        provisional=args.provisional,
        floor_gap_summary=floor_gap_summary if args.provisional else None,
    )
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote manifest ({len(manifest)} keys) to {args.manifest}")


if __name__ == "__main__":
    main()
