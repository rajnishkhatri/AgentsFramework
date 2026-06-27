#!/usr/bin/env python3
"""One-shot impact report: rerun fixed A1 grader; diff vs recorded A1 sheet.

Identifies item_ids where the FIXED grader (with the `len>80 + lf goal_met` gate)
would have produced a different ``r1_goal_met`` than what A1 recorded. Two
categories:

  - A1 RECORDED true, FIXED would say false → candidate over-grade row.
    If A1 also wrote an `r1_review_assessment` for it, human judgment ratified;
    leave it. If no assessment (one of the 22 unflagged rows), this is an R-6
    candidate per the A2 plan §5.2 / §13.
  - A1 RECORDED false, FIXED would say true → candidate under-grade. Should be
    rare and likely the result of A1's separate human review path; surfaced for
    completeness.

Output: a markdown report at cache/goaljudge_eval/a1_len80_fix_impact_report.md.
Do NOT modify A1's sheet. The R-6 candidates route to post-α adjudication.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_goaljudge_stage5_annotator1_fresh_sheet import (
    _grade_row,
    _load_batch,
    _load_corpus,
)
from tests.fixtures.goaljudge.fresh_test_tasks import FRESH_TEST_TASKS


BATCH_PATH = (
    REPO_ROOT / "cache/goaljudge_eval/ui_batch_gcp_fresh_stage5_rerun_2026-06-10.jsonl"
)
CORPUS_PATH = (
    REPO_ROOT / "cache/goaljudge_eval/corpus_gcp_fresh_stage5_rerun_2026-06-10.jsonl"
)
A1_SHEET_PATH = (
    REPO_ROOT
    / "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator1_sheet.csv"
)
REPORT_PATH = REPO_ROOT / "cache/goaljudge_eval/a1_len80_fix_impact_report.md"


def main() -> int:
    batch = _load_batch(BATCH_PATH)
    corpus_by_trace = _load_corpus(CORPUS_PATH)
    with A1_SHEET_PATH.open(encoding="utf-8") as fh:
        a1_rows = {r["item_id"]: r for r in csv.DictReader(fh)}

    fresh_by_id = {t.id: t for t in FRESH_TEST_TASKS}

    over_grades: list[tuple[str, dict, dict]] = []  # A1=true, fixed=false
    under_grades: list[tuple[str, dict, dict]] = []  # A1=false, fixed=true
    skipped_missing: list[str] = []

    for item_id, a1_row in a1_rows.items():
        if not item_id.startswith("GJ-F-"):
            continue
        capture = batch.get(item_id)
        if capture is None:
            skipped_missing.append(item_id + " (no batch capture)")
            continue
        trace_id = capture.get("trace_id")
        corpus_row = corpus_by_trace.get(trace_id) if trace_id else None
        if corpus_row is None:
            skipped_missing.append(item_id + " (no corpus row)")
            continue
        task = fresh_by_id.get(item_id)
        if task is None:
            skipped_missing.append(item_id + " (no fresh task fixture)")
            continue

        fixed = _grade_row(
            task_id=item_id,
            prompt=task.prompt,
            tool_cluster=task.expected_tool_cluster,
            stratum=task.stratum,
            capture=capture,
            corpus_row=corpus_row,
            authored_failure=task.expected_failure_mode,
        )

        a1_goal_met = (a1_row.get("r1_goal_met") or "").strip().lower()
        fixed_goal_met = (fixed.get("r1_goal_met") or "").strip().lower()
        if a1_goal_met == fixed_goal_met:
            continue
        if a1_goal_met == "true" and fixed_goal_met == "false":
            over_grades.append((item_id, a1_row, fixed))
        elif a1_goal_met == "false" and fixed_goal_met == "true":
            under_grades.append((item_id, a1_row, fixed))

    # Render report
    lines: list[str] = []
    lines.append("# A1 `len>80` Fix Impact Report")
    lines.append("")
    lines.append(
        "> Re-ran A1's grader with the new gate (`has_tools and len(substantive) > 80 "
        "and corpus_row['goal_met'] is not False`) against A1's frozen evidence bundle. "
        "Each row below is a place where the fixed grader DISAGREES with what A1 actually recorded."
    )
    lines.append("")
    lines.append(f"- Batch: `{BATCH_PATH.relative_to(REPO_ROOT)}`")
    lines.append(f"- Corpus: `{CORPUS_PATH.relative_to(REPO_ROOT)}`")
    lines.append(f"- A1 sheet: `{A1_SHEET_PATH.relative_to(REPO_ROOT)}`")
    lines.append(
        f"- Total GJ-F-* rows compared: {sum(1 for k in a1_rows if k.startswith('GJ-F-'))}"
    )
    lines.append(f"- Skipped (missing corpus/batch/fixture): {len(skipped_missing)}")
    lines.append(
        f"- **Over-grade candidates** (A1=true, fixed=false): **{len(over_grades)}**"
    )
    lines.append(
        f"- Under-grade candidates (A1=false, fixed=true): {len(under_grades)}"
    )
    lines.append("")
    lines.append(
        "**Action policy (per A2 plan §5.2 / R-6):** do NOT modify A1's sheet pre-α. "
        "Rows where A1 already wrote an `r1_review_assessment` were ratified by human "
        "judgment (the authority). Rows with NO assessment (the 22 unflagged from §7.2) "
        "are R-6 candidates — route to post-α adjudication."
    )
    lines.append("")

    def render_bucket(title: str, bucket: list[tuple[str, dict, dict]]) -> None:
        lines.append(f"## {title}")
        lines.append("")
        if not bucket:
            lines.append("_None._")
            lines.append("")
            return
        lines.append(
            "| item_id | A1 r1_goal_met | A1 r1_failure_mode | Fixed r1_goal_met | "
            "Fixed r1_failure_mode | A1 has r1_review_assessment? | A1 note |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for item_id, a1_row, fixed in bucket:
            has_assessment = (
                "yes"
                if (a1_row.get("r1_review_assessment") or "").strip()
                else "**NO (R-6)**"
            )
            a1_note = (a1_row.get("note") or "").replace("|", "\\|")[:60]
            lines.append(
                f"| {item_id} | {a1_row.get('r1_goal_met')} | "
                f"{a1_row.get('r1_failure_mode') or '—'} | {fixed.get('r1_goal_met')} | "
                f"{fixed.get('r1_failure_mode') or '—'} | {has_assessment} | {a1_note} |"
            )
        lines.append("")

    render_bucket("Over-grade candidates — A1=true, fixed=false", over_grades)
    render_bucket("Under-grade candidates — A1=false, fixed=true", under_grades)

    if skipped_missing:
        lines.append("## Skipped rows (missing data)")
        lines.append("")
        for s in skipped_missing:
            lines.append(f"- {s}")
        lines.append("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote: {REPORT_PATH.relative_to(REPO_ROOT)}")
    print(f"Over-grade candidates: {len(over_grades)}")
    print(f"Under-grade candidates: {len(under_grades)}")
    print(f"Skipped: {len(skipped_missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
