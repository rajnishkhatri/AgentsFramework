#!/usr/bin/env python3
"""Phase 6 Path A — Build the combined fresh + pilot-production sheet.

Combines:
  * 79 rows from the fresh-corpus full sheet (Phase 5 frozen labels)
  * 22 rows from the pilot's *production-provenance* subset
    (synthetic-dev rows are excluded — they aren't part of the test corpus)

The pilot rows need three transformations to slot into the fresh-sheet schema:

1. **Classify D1/D5 dimensions.** The pilot sheet predates the Tier-3
   stratification; rows lack ``planning_depth`` and ``tool_cluster``.
   This script re-runs the classifier (router.select_planning_depth +
   classify_tool_cluster) against the pilot's corpus JSONL evidence
   bundle to assign them.
2. **Backfill ``adjudicated_*`` from consensus.** All 22 pilot production
   rows have 100% A1/A2 agreement on ``goal_met`` (measured), so the
   adjudicator's verdict equals the consensus. Same backfill logic the
   Phase 6 fresh-sheet pre-step uses.
3. **Map ``split=dev`` → ``split=test`` for pilot prod rows.** The pilot
   originally split most production rows into dev for early calibration,
   but for the combined gold-set freeze they become test rows (they're
   production-provenance, not synthetic). Synthetic rows are excluded
   entirely from the combined sheet.

The fresh sheet's extended schema (4 columns: ``planning_depth``,
``tool_cluster``, ``r1_review_assessment``, ``r1_review_open_question``)
becomes the combined sheet's schema. Pilot rows get blank values for the
two ``r1_review_*`` columns (they weren't part of the Phase 5 review pass).

Pilot legacy failure_mode codes (``incomplete-run`` etc.) are remapped to
the active vocabulary via the same precedence rule the fresh-sheet
backfill uses: prefer A1's iff in vocab, else A2's, else blank.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from components.router import select_planning_depth
from components.schemas import GOAL_FAILURE_MODES
from services.governance.goaljudge_goldset_dataset import (
    classify_tool_cluster,
    project_trajectory_tools,
)
from services.governance.iaa import normalize_bool_label

FRESH_SHEET = REPO_ROOT / "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv"
PILOT_SHEET = REPO_ROOT / "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_sheet.csv"
PILOT_CORPUS = REPO_ROOT / "cache/goaljudge_eval/corpus_gcp_goldset_pilot_2026-06-09.jsonl"
REGISTRY = REPO_ROOT / "frontend/e2e/fixtures/goaljudge_registry.json"
COMBINED_SHEET = REPO_ROOT / "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_combined_sheet.csv"

_VALID_FM = set(GOAL_FAILURE_MODES)


def _pick_failure_mode(a1: str, a2: str) -> str:
    a1, a2 = a1.strip(), a2.strip()
    if a1 in _VALID_FM:
        return a1
    if a2 in _VALID_FM:
        return a2
    return ""


def main() -> int:
    # Load fresh sheet — defines the schema.
    with FRESH_SHEET.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fresh_fields = reader.fieldnames or []
        fresh_rows = list(reader)

    # Load pilot sheet — filter to production provenance only.
    with PILOT_SHEET.open(newline="", encoding="utf-8") as fh:
        pilot_rows = [
            r for r in csv.DictReader(fh)
            if r.get("provenance", "").strip().lower() == "production"
        ]

    # Build trace_id → projected tool calls index from pilot corpus.
    tool_index: dict[str, list[dict]] = {}
    for line in PILOT_CORPUS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        tid = row.get("trace_id")
        if tid:
            tool_index[tid] = project_trajectory_tools(row.get("trajectory") or [])

    # Build item_id → trace_id from registry.
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    trace_for_id = {r["id"]: r.get("trace_id") for r in registry}

    # Transform each pilot row into the fresh-sheet schema.
    transformed: list[dict[str, str]] = []
    for r in pilot_rows:
        iid = r["item_id"]
        task = r.get("task", "")
        trace_id = trace_for_id.get(iid, "")
        tools = tool_index.get(trace_id, [])

        depth, _reason = select_planning_depth(task_input=task, task_tool_results_count=0)
        cluster = classify_tool_cluster(tools)

        r1_gm = normalize_bool_label(r.get("r1_goal_met", ""))
        r2_gm = normalize_bool_label(r.get("r2_goal_met", ""))
        if r1_gm == r2_gm and r1_gm in {"true", "false"}:
            adj_gm = r1_gm
        else:
            # Pilot prod is 100% agreement; this branch shouldn't fire. Leave
            # blank to surface as an error during assembly if it ever did.
            adj_gm = ""

        adj_fm = _pick_failure_mode(
            r.get("r1_failure_mode", ""), r.get("r2_failure_mode", "")
        )

        new_row: dict[str, str] = {f: "" for f in fresh_fields}
        new_row["item_id"] = iid
        new_row["split"] = "test"  # Promote pilot prod to test split for the freeze.
        new_row["provenance"] = "production"
        new_row["stratum"] = r.get("stratum", "")
        new_row["domain"] = r.get("domain", "")
        new_row["planning_depth"] = depth
        new_row["tool_cluster"] = cluster
        new_row["task"] = task
        new_row["claim"] = r.get("claim", "")
        new_row["evidence_summary"] = r.get("evidence_summary", "")
        new_row["r1_goal_met"] = r.get("r1_goal_met", "")
        new_row["r1_graceful_failure"] = r.get("r1_graceful_failure", "")
        new_row["r1_partial_fraction"] = r.get("r1_partial_fraction", "")
        new_row["r1_failure_mode"] = r.get("r1_failure_mode", "")
        new_row["r2_goal_met"] = r.get("r2_goal_met", "")
        new_row["r2_graceful_failure"] = r.get("r2_graceful_failure", "")
        new_row["r2_partial_fraction"] = r.get("r2_partial_fraction", "")
        new_row["r2_failure_mode"] = r.get("r2_failure_mode", "")
        new_row["adjudicated_goal_met"] = adj_gm
        new_row["adjudicated_failure_mode"] = adj_fm
        new_row["rubric_version"] = r.get("rubric_version", "")
        new_row["note"] = r.get("note", "")
        new_row["r1_review_assessment"] = ""
        new_row["r1_review_open_question"] = ""
        transformed.append(new_row)

    # Combined: fresh first, then pilot.
    combined_rows = fresh_rows + transformed

    with COMBINED_SHEET.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fresh_fields)
        writer.writeheader()
        writer.writerows(combined_rows)

    print(f"Wrote combined sheet → {COMBINED_SHEET}")
    print(f"  fresh rows:  {len(fresh_rows):>3d}")
    print(f"  pilot rows:  {len(transformed):>3d}  (production-provenance only)")
    print(f"  total:       {len(combined_rows):>3d}")

    # Sanity tallies.
    import collections
    print()
    print(f"D1 (planning_depth): {dict(collections.Counter(r['planning_depth'] for r in combined_rows))}")
    print(f"D5 (tool_cluster):   {dict(collections.Counter(r['tool_cluster'] for r in combined_rows))}")
    print(f"Split:              {dict(collections.Counter(r['split'] for r in combined_rows))}")
    print(f"Provenance:         {dict(collections.Counter(r['provenance'] for r in combined_rows))}")
    print(f"adjudicated_goal_met: {dict(collections.Counter(r['adjudicated_goal_met'] for r in combined_rows))}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
