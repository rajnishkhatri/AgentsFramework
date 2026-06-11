#!/usr/bin/env python3
"""Print labeling context for A2 cold-blind labeling, one row at a time.

Loads the shared evidence bundle (UI batch JSONL + Langfuse corpus JSONL +
fresh-task fixture) and prints, for a given item_id, exactly what A2 needs
to grade per A2 plan §7.2:

  - the prompt (from fresh task fixture; authored intent is shared between A1/A2)
  - the agent's claim text (from corpus final_answer / UI response)
  - Langfuse trace_id + trajectory tools + eval axes (goal_met etc.)
  - UI admissibility verdict
  - the row's stratum + tool_cluster + expected_failure_mode (authoring hint)

Does NOT read the A1 sheet, A1 review queue, or the A2 sheet's r1_* columns.

Usage:
  python scripts/_a2_labeling_context.py GJ-F-001
  python scripts/_a2_labeling_context.py --range 1 10
  python scripts/_a2_labeling_context.py --all
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

from scripts.goaljudge_ui_evidence import (
    extract_answer_text,
    is_ui_admissible,
    strip_status_prefix,
)
from services.governance.goaljudge_goldset_dataset import project_trajectory_tools
from tests.fixtures.goaljudge.fresh_test_tasks import FRESH_TEST_TASKS

A2_SHEET = REPO_ROOT / "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator2_sheet.csv"
BATCH = REPO_ROOT / "cache/goaljudge_eval/ui_batch_gcp_fresh_stage5_rerun_2026-06-10.jsonl"
CORPUS = REPO_ROOT / "cache/goaljudge_eval/corpus_gcp_fresh_stage5_rerun_2026-06-10.jsonl"


def _load_jsonl_by_key(path: Path, key: str) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        v = row.get(key)
        if v:
            out[v] = row
    return out


def print_row_context(item_id: str, batch: dict, corpus: dict, fresh_by_id: dict, a2_rows: dict) -> None:
    print(f"\n{'=' * 78}")
    print(f"ITEM: {item_id}")
    print(f"{'=' * 78}")

    a2_row = a2_rows.get(item_id)
    if a2_row is None:
        print(f"  [A2 sheet has no row for {item_id}]")
        return

    task = fresh_by_id.get(item_id)
    cap = batch.get(item_id)
    trace_id = (cap or {}).get("trace_id")
    corp = corpus.get(trace_id) if trace_id else None

    # Identity + authored intent
    print(f"stratum: {a2_row['stratum']}    cluster: {a2_row['tool_cluster']}    depth: {a2_row['planning_depth']}    domain: {a2_row['domain']}")
    if task:
        print(f"AUTHORED expected_failure_mode: {task.expected_failure_mode or '(blank - representative pass-shaped)'}")
    print()

    # Prompt
    print("PROMPT:")
    print(f"  {a2_row['task']}")
    print()

    # Claim
    print("AGENT CLAIM (final_answer or UI):")
    print(f"  {a2_row['claim'][:400]}")
    print()

    # Langfuse evidence
    print("LANGFUSE EVIDENCE:")
    print(f"  trace_id: {trace_id}")
    if corp:
        gm = corp.get("goal_met")
        gf = corp.get("graceful_failure")
        pf = corp.get("partial_fraction")
        fm = corp.get("failure_mode")
        print(f"  LF eval: goal_met={gm} graceful={gf} pf={pf} failure_mode={fm}")
        traj = corp.get("trajectory") or []
        tools = project_trajectory_tools(traj)
        tool_names = [t.get("tool_name") for t in tools]
        print(f"  trajectory tools ({len(tool_names)}): {tool_names}")
    else:
        print("  [NO CORPUS ROW - langfuse-trace-missing]")

    # UI admissibility
    if cap:
        ui_resp = cap.get("response_text") or ""
        outcome = cap.get("outcome") or ""
        ui_adm = is_ui_admissible(ui_resp, outcome)
        print(f"  UI outcome: {outcome}    admissible: {ui_adm}")
        if not ui_adm:
            print(f"  → status-feed-only UI; langfuse-only evidence")
    else:
        print("  [NO BATCH CAPTURE]")

    print(f"\n  evidence_summary: {a2_row['evidence_summary']}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("item_id", nargs="?", help="single item id to print")
    parser.add_argument("--range", nargs=2, type=int, help="numeric range, e.g. --range 1 10")
    parser.add_argument("--all", action="store_true", help="print all 79 rows")
    args = parser.parse_args()

    batch = _load_jsonl_by_key(BATCH, "case_id")
    corpus = _load_jsonl_by_key(CORPUS, "trace_id")
    fresh_by_id = {t.id: t for t in FRESH_TEST_TASKS}
    a2_rows = {r["item_id"]: r for r in csv.DictReader(A2_SHEET.open(encoding="utf-8"))}

    if args.all:
        ids = sorted(a2_rows.keys())
    elif args.range:
        lo, hi = args.range
        ids = [f"GJ-F-{n:03d}" for n in range(lo, hi + 1) if f"GJ-F-{n:03d}" in a2_rows]
    elif args.item_id:
        ids = [args.item_id]
    else:
        parser.error("provide item_id, --range, or --all")

    for iid in ids:
        print_row_context(iid, batch, corpus, fresh_by_id, a2_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
