#!/usr/bin/env python3
"""Build the cold-blind Annotator 2 sheet for Stage 5 fresh-corpus labeling.

Per the A2 session plan §6, A2 labels each row from scratch — no semi-auto
pre-fill, no exposure to A1's grades or notes. This script reads the source
full sheet (which carries A1's columns) plus the shared corpus + UI evidence
JSONLs, and writes a SEPARATE ``annotator2_sheet.csv`` carrying:

  - identity columns (item_id, split, provenance, stratum, domain, task)
  - the agent's claim text (derived from corpus/UI, NOT copied from A1's
    `claim` column)
  - an evidence_summary derived from the corpus trajectory + UI admissibility
    (NOT copied from A1's evidence_summary — A1 prose must never appear)
  - BLANK ``r2_goal_met`` / ``r2_graceful_failure`` / ``r2_partial_fraction``
    / ``r2_failure_mode`` label cells
  - BLANK ``r2_review_assessment`` / ``r2_review_open_question`` text cells
  - the source `note` column (carries authoring metadata like
    `stage4_confirmed`; A1's runtime annotations are not in this column)

Critically, the output sheet has **no r1_* columns and no adjudicated_***
columns. The blindness firewall (§9 of the A2 plan) is enforced by file
shape: A2 opens this file, period.

Usage:

  python scripts/build_goaljudge_stage5_annotator2_sheet.py \\
    --full-sheet docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv \\
    --batch cache/goaljudge_eval/ui_batch_gcp_fresh_stage5_rerun_2026-06-10.jsonl \\
    --corpus cache/goaljudge_eval/corpus_gcp_fresh_stage5_rerun_2026-06-10.jsonl \\
    --output docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator2_sheet.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.goaljudge_ui_evidence import (
    extract_answer_text,
    is_ui_admissible,
)
from services.governance.goaljudge_goldset_dataset import project_trajectory_tools


# Columns carried over from the source full sheet AS-IS (identity + authored
# metadata that both annotators share — same prompt, same stratum). Notably
# absent: `claim`, `evidence_summary` (derived independently below), and any
# r1_* / adjudicated_* columns (firewall).
IDENTITY_COLUMNS = (
    "item_id",
    "split",
    "provenance",
    "stratum",
    "domain",
    "planning_depth",
    "tool_cluster",
    "task",
    "rubric_version",
    "note",
)

# r2-side label columns A2 fills.
R2_LABEL_COLUMNS = (
    "r2_goal_met",
    "r2_graceful_failure",
    "r2_partial_fraction",
    "r2_failure_mode",
)

# r2-side free-text columns for A2's rationale + open questions.
R2_REVIEW_COLUMNS = (
    "r2_review_assessment",
    "r2_review_open_question",
)

# Final output column order — identity first, then derived evidence, then
# blank r2_* cells. Stable schema for downstream merge at the α step.
OUTPUT_FIELDNAMES = (
    "item_id",
    "split",
    "provenance",
    "stratum",
    "domain",
    "planning_depth",
    "tool_cluster",
    "task",
    "claim",
    "evidence_summary",
    *R2_LABEL_COLUMNS,
    *R2_REVIEW_COLUMNS,
    "rubric_version",
    "note",
)


def _load_batch(path: Path) -> dict[str, dict[str, Any]]:
    """Index UI batch JSONL rows by case_id (last capture wins)."""
    by_id: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        by_id[row["case_id"]] = row
    return by_id


def _load_corpus(path: Path) -> dict[str, dict[str, Any]]:
    """Index Langfuse corpus JSONL rows by trace_id (last row wins)."""
    by_trace: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        trace_id = row.get("trace_id")
        if trace_id:
            by_trace[trace_id] = row
    return by_trace


def _lf_tools(corpus_row: dict[str, Any] | None) -> list[str]:
    if not corpus_row:
        return []
    projected = project_trajectory_tools(corpus_row.get("trajectory"))
    return [p["tool_name"] for p in projected if p.get("tool_name")]


def _claim_text(
    *,
    corpus_row: dict[str, Any] | None,
    capture: dict[str, Any] | None,
    ui_admissible: bool,
) -> str:
    """Resolve the agent's success-claim text from corpus + UI evidence.

    Derived independently of A1's `claim` column in the source full sheet,
    so A1 prose cannot reach A2.
    """
    ui_text = str((capture or {}).get("response_text") or "")
    answer = extract_answer_text(
        corpus_final_answer=(corpus_row or {}).get("final_answer"),
        ui_response=ui_text,
        ui_admissible=ui_admissible,
    )
    if answer:
        return answer[:500]
    return ui_text[:500]


def _evidence_summary(
    *,
    trace_id: str,
    capture: dict[str, Any] | None,
    corpus_row: dict[str, Any] | None,
    ui_admissible: bool,
    lf_tool_names: list[str],
) -> str:
    """Build a single-line evidence pointer string from corpus + UI.

    Mirrors the shape A1's builder emits so the two sheets line up at the
    α merge step. Critically, this is derived from the SHARED evidence (the
    same Langfuse corpus + Playwright UI batch A1 saw), NOT copied from
    A1's evidence_summary column — so no A1 prose can reach A2.
    """
    ui_tools = int((capture or {}).get("tool_card_count") or 0)
    dom = "full" if ui_admissible else "status_feed_only"
    source = "langfuse+ui" if ui_admissible and corpus_row else "langfuse-only"
    if not corpus_row:
        source = "missing"
    return (
        f"trace_id={trace_id}; dom={dom}; lf_tools={lf_tool_names}; "
        f"ui_tools={ui_tools}; source={source}"
    )


def build_a2_sheet(
    *,
    full_sheet_path: Path,
    batch_path: Path,
    corpus_path: Path,
    output_path: Path,
) -> int:
    """Build the cold-blind A2 sheet; return row count.

    Reads the source full sheet for the identity columns + task prompt,
    discards any A1 prose/labels, derives `claim` and `evidence_summary`
    independently from the corpus + UI batch, and writes one blank-labeled
    row per source row to `output_path`.
    """
    batch = _load_batch(batch_path)
    corpus = _load_corpus(corpus_path)

    rows_out: list[dict[str, str]] = []
    with full_sheet_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for src in reader:
            iid = src["item_id"]
            capture = batch.get(iid)
            trace_id = str((capture or {}).get("trace_id") or "")
            corpus_row = corpus.get(trace_id) if trace_id else None
            ui_admissible = (
                is_ui_admissible(
                    str(capture.get("response_text") or ""),
                    str(capture.get("outcome") or ""),
                )
                if capture
                else False
            )
            lf_tool_names = _lf_tools(corpus_row)

            row = {col: src.get(col, "") for col in IDENTITY_COLUMNS}
            row["claim"] = _claim_text(
                corpus_row=corpus_row,
                capture=capture,
                ui_admissible=ui_admissible,
            )
            row["evidence_summary"] = _evidence_summary(
                trace_id=trace_id,
                capture=capture,
                corpus_row=corpus_row,
                ui_admissible=ui_admissible,
                lf_tool_names=lf_tool_names,
            )
            for col in R2_LABEL_COLUMNS:
                row[col] = ""
            for col in R2_REVIEW_COLUMNS:
                row[col] = ""
            rows_out.append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(OUTPUT_FIELDNAMES))
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"wrote {len(rows_out)} rows → {output_path}")
    print(
        f"all r2_* cells blank; identity columns preserved; "
        f"claim+evidence derived from corpus (not A1 sheet)"
    )
    return len(rows_out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-sheet", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    build_a2_sheet(
        full_sheet_path=args.full_sheet,
        batch_path=args.batch,
        corpus_path=args.corpus,
        output_path=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
