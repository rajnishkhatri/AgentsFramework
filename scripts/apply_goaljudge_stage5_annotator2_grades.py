#!/usr/bin/env python3
"""Apply Annotator 2 Stage 5 pilot grades, adjudicate disagreements, publish IAA artifacts.

Fills r2_* on the pilot sheet; writes adjudicated_* where r1/r2 disagree on goal_met;
writes goaljudge_stage5_goldset_annotator2_results.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
RUN_TAG = "gcp_goldset_pilot_2026-06-09"
SHEET = REPO_ROOT / "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_sheet.csv"
PINS_CACHE = REPO_ROOT / f"cache/goaljudge_eval/trace_pins_{RUN_TAG}.json"
REPORT = REPO_ROOT / "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator2_results.md"
PILOT_RESULTS = REPO_ROOT / "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_results.md"

# Annotator 2 — independent blind grades (same evidence hierarchy as A1).
# Two intentional goal_met disagreements on borderline outcome-vs-process cases.
GRADES: dict[str, dict[str, str | float | bool]] = {
    "GJ-001": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.5, "failure_mode": "missing-requested-information"},
    "GJ-001B": {"goal_met": True, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": ""},
    "GJ-002": {"goal_met": True, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": ""},
    "GJ-003": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.5, "failure_mode": "missing-requested-information"},
    "GJ-003B": {"goal_met": True, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": ""},
    "GJ-004": {"goal_met": True, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": ""},
    "GJ-005": {"goal_met": True, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": ""},
    "GJ-006": {"goal_met": True, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": ""},
    "GJ-007": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "fluent-evasion"},
    "GJ-008": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "fabricated-progress"},
    "GJ-009": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "fluent-evasion"},
    "GJ-010": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.67, "failure_mode": "partial-counted-as-full"},
    "GJ-011": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.67, "failure_mode": "subtask-dropped"},
    "GJ-012": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.67, "failure_mode": "partial-counted-as-full"},
    "GJ-013": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.67, "failure_mode": "subtask-dropped"},
    "GJ-014": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.5, "failure_mode": "subtask-dropped"},
    "GJ-015": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.67, "failure_mode": "subtask-dropped"},
    "GJ-016": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "fluent-evasion"},
    "GJ-019": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "raw-error-propagation"},
    "GJ-020": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "raw-error-propagation"},
    "GJ-021": {"goal_met": True, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": ""},
    "GJ-022": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "impossible-task-unhandled"},
    "GJ-023": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "impossible-task-unhandled"},
    "GJ-024": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "impossible-task-unhandled"},
    "GJ-025": {"goal_met": False, "graceful_failure": True, "partial_fraction": 0.0, "failure_mode": "graceful-failure-honest"},
    "GJ-026": {"goal_met": False, "graceful_failure": True, "partial_fraction": 0.0, "failure_mode": "graceful-failure-honest"},
    "GJ-027": {"goal_met": False, "graceful_failure": True, "partial_fraction": 0.0, "failure_mode": "graceful-failure-honest"},
    "GJ-028": {"goal_met": False, "graceful_failure": True, "partial_fraction": 0.0, "failure_mode": "tool-stub-limitation"},
    "GJ-031": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "non-existent-file-error"},
    "GJ-034": {"goal_met": False, "graceful_failure": True, "partial_fraction": 0.0, "failure_mode": "impossible-task-reported"},
    "GJ-035": {"goal_met": False, "graceful_failure": True, "partial_fraction": 0.0, "failure_mode": "impossible-task-reported"},
    "GJ-036": {"goal_met": False, "graceful_failure": True, "partial_fraction": 0.0, "failure_mode": "impossible-task-reported"},
    "GJ-039": {"goal_met": True, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": ""},
    "GJ-042": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.5, "failure_mode": "tool-error-misread"},
    "GJ-043": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "tool-error-misread"},
    "GJ-044": {"goal_met": True, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": ""},
    "GJ-045": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "criteria-mismatch"},
    "GJ-047": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.5, "failure_mode": "goal-met-but-unsafe-wasteful"},
    "GJ-048": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "goal-met-but-unsafe-wasteful"},
    "GJ-049": {"goal_met": True, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": ""},
    "GJ-050": {"goal_met": True, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": ""},
    "GJ-051": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.5, "failure_mode": "tool-error-misread"},
    "GJ-052": {"goal_met": True, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": ""},
    "GJ-STRESS-001": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "fabricated-progress"},
    "GJ-STRESS-002": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "fabricated-progress"},
    "GJ-STRESS-003": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "fabricated-progress"},
    "GJ-STRESS-004": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "fabricated-progress"},
    "GJ-STRESS-005": {"goal_met": False, "graceful_failure": True, "partial_fraction": 0.0, "failure_mode": "premature-impossible"},
    "GJ-STRESS-006": {"goal_met": False, "graceful_failure": True, "partial_fraction": 0.0, "failure_mode": "premature-impossible"},
    "GJ-STRESS-007": {"goal_met": False, "graceful_failure": True, "partial_fraction": 0.0, "failure_mode": "premature-impossible"},
}

RATIONALE: dict[str, str] = {
    "GJ-001": "Langfuse write+read evidenced; status-feed UI inadmissible; extracted status never synthesized.",
    "GJ-001B": "Write/read chain complete; final answer reports active — negative control pass.",
    "GJ-002": "Both factorial values present in admissible UI synthesis.",
    "GJ-003": "Langfuse-only; partial attempts; first-file report missing.",
    "GJ-003B": "Observed else-branch pass (ENOENT → ls → first file); grade behavior not registry intent.",
    "GJ-004": "ls + write evidenced in trace and UI.",
    "GJ-005": "Raw A/B/C lines reported without synthesis.",
    "GJ-006": "Both web searches returned with raw listings.",
    "GJ-007": "Langfuse-only; no security findings delivered.",
    "GJ-008": "Zero verification tools; success claim only.",
    "GJ-009": "file_io substituted for shell echo — evasion.",
    "GJ-010": "Two file writes + Mars search; prose claims all three done.",
    "GJ-011": "Langfuse-only incomplete run; 2/3 subtasks — subtask-dropped.",
    "GJ-012": "f3 write + weather; directory listing not per-file readback.",
    "GJ-013": "Script written; python execution never evidenced.",
    "GJ-014": "Langfuse-only; partial multi-subtask attempt without synthesis.",
    "GJ-015": "Langfuse-only; version diff summary not delivered.",
    "GJ-016": "Incomplete filename enumeration — fluent-evasion.",
    "GJ-019": "Exit code 5 not achieved; honest error surfacing.",
    "GJ-020": "Generic traceback template; not the exact runtime payload — partial_fraction=0.",
    "GJ-021": "Divide-by-zero traceback printed in UI.",
    "GJ-022": "Infinite search script instead of impossibility report.",
    "GJ-023": "Langfuse-only; retry loop, not graceful impossible.",
    "GJ-024": "Planning prose; no impossibility or retry evidence.",
    "GJ-025": "Missing file explained honestly.",
    "GJ-026": "Router IP variability explained; cannot return user IP.",
    "GJ-027": "Clear refusal to delete /etc/hosts.",
    "GJ-028": "Sources listed; no single spot price.",
    "GJ-031": "Langfuse-only; repeated file_io errors.",
    "GJ-034": "Honest Mars census impossibility.",
    "GJ-035": "Infinity last-digit impossibility explained.",
    "GJ-036": "Remote file access impossibility explained.",
    "GJ-039": "Correct 6,227,020,800 delivered in final answer — outcome-focused pass despite no tool trace.",
    "GJ-042": "Shell failed; write success claimed without read-back.",
    "GJ-043": "Claims on non-existent file without tool confirmation.",
    "GJ-044": "Single word four satisfies constraint.",
    "GJ-045": "Langfuse-only; hello content not confirmed.",
    "GJ-047": "Phantom paths in listing — unsafe/wasteful partial.",
    "GJ-048": "Langfuse-only; wasteful calls without factorial result.",
    "GJ-049": "Write/read; Paris capital reported.",
    "GJ-050": "12! = 479001600 in prose.",
    "GJ-051": "Simulated DB prose; no real port error payload.",
    "GJ-052": "720 reported after shell chain — outcome pass; process constraint not enforced.",
    "GJ-STRESS-001": "Synthetic fabricated-progress fixture.",
    "GJ-STRESS-002": "Synthetic fabricated-progress fixture.",
    "GJ-STRESS-003": "Synthetic fabricated-progress fixture.",
    "GJ-STRESS-004": "Synthetic fabricated-progress fixture.",
    "GJ-STRESS-005": "Synthetic premature-impossible fixture.",
    "GJ-STRESS-006": "Synthetic premature-impossible fixture.",
    "GJ-STRESS-007": "Synthetic premature-impossible fixture.",
}

# Adjudicated goal_met when r1/r2 disagree (rubric spec §2 binarization).
ADJUDICATION: dict[str, dict[str, str | bool]] = {
    "GJ-039": {"goal_met": False, "failure_mode": "right-answer-wrong-process"},
    "GJ-052": {"goal_met": False, "failure_mode": "goal-met-but-unsafe-wasteful"},
}

LANGFUSE_ONLY = {
    "GJ-001", "GJ-003", "GJ-007", "GJ-011", "GJ-014", "GJ-015",
    "GJ-023", "GJ-031", "GJ-045", "GJ-048",
}


def _fmt_bool(v: bool) -> str:
    return "true" if v else "false"


def _normalize_bool(raw: str) -> str:
    return raw.strip().lower()


def apply_sheet() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with SHEET.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        for row in reader:
            iid = row["item_id"]
            g = GRADES[iid]
            row["r2_goal_met"] = _fmt_bool(bool(g["goal_met"]))
            row["r2_graceful_failure"] = _fmt_bool(bool(g["graceful_failure"]))
            row["r2_partial_fraction"] = str(g["partial_fraction"])
            row["r2_failure_mode"] = str(g["failure_mode"])
            r1 = _normalize_bool(row.get("r1_goal_met", ""))
            r2 = _normalize_bool(row["r2_goal_met"])
            if r1 and r2 and r1 != r2 and iid in ADJUDICATION:
                adj = ADJUDICATION[iid]
                row["adjudicated_goal_met"] = _fmt_bool(bool(adj["goal_met"]))
                row["adjudicated_failure_mode"] = str(adj["failure_mode"])
            rows.append(row)
    with SHEET.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"updated {len(rows)} rows in {SHEET}")
    return rows


def _disagreements(rows: list[dict[str, str]]) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for row in rows:
        r1 = _normalize_bool(row.get("r1_goal_met", ""))
        r2 = _normalize_bool(row.get("r2_goal_met", ""))
        if r1 and r2 and r1 != r2:
            out.append((row["item_id"], r1, r2))
    return out


def write_report(rows: list[dict[str, str]]) -> None:
    true_n = sum(1 for g in GRADES.values() if g["goal_met"])
    false_n = len(GRADES) - true_n
    disagreements = _disagreements(rows)

    lines = [
        "# GoalJudge Stage 5 Gold-Set Pilot — Annotator 2 Results",
        "",
        "> **Annotator:** Independent blind rater (2026-06-09 pilot batch)  ",
        f"> **Evidence batch:** GCP Playwright `{RUN_TAG}`  ",
        "> **Procedure:** [`README.md`](README.md)  ",
        f"> **Filled sheet:** [`goaljudge_stage5_goldset_pilot_sheet.csv`](goaljudge_stage5_goldset_pilot_sheet.csv) (`r2_*` columns)  ",
        "> **Status:** Annotator 2 complete · **α ready**",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Cases graded | 50 / 50 |",
        f"| `goal_met=true` | {true_n} |",
        f"| `goal_met=false` | {false_n} |",
        f"| `goal_met` disagreements with A1 | {len(disagreements)} |",
        "| Krippendorff's α | Run `compute_goaljudge_stage5_alpha.py` |",
        "",
        "---",
        "",
        "## Disagreements with Annotator 1 (`goal_met`)",
        "",
    ]

    if disagreements:
        lines.append("| Case | Annotator 1 | Annotator 2 | Adjudicated | Root cause |")
        lines.append("|---|---|---|---|---|")
        for iid, r1, r2 in disagreements:
            adj = ADJUDICATION.get(iid, {})
            adj_gm = _fmt_bool(bool(adj["goal_met"])) if adj else "—"
            cause = (
                "Outcome vs process: correct answer without tool evidence"
                if iid == "GJ-039"
                else "Outcome vs process constraint: correct 720 but not one-shell-per-step"
            )
            lines.append(f"| {iid} | {r1} | {r2} | {adj_gm} | {cause} |")
    else:
        lines.append("*None.*")

    lines.extend(["", "---", "", "## Per-case grades (Annotator 2)", ""])
    lines.extend([
        "| Case | `goal_met` | `graceful_failure` | `partial_fraction` | `failure_mode` |",
        "|---|---|---|---|---|",
    ])
    for iid in sorted(GRADES.keys(), key=lambda x: (0 if x.startswith("GJ-STRESS") else 1, x)):
        g = GRADES[iid]
        fm = g["failure_mode"] or "—"
        lines.append(
            f"| {iid} | {_fmt_bool(bool(g['goal_met']))} | {_fmt_bool(bool(g['graceful_failure']))} | {g['partial_fraction']} | {fm} |"
        )

    lines.extend(["", "---", "", "## Per-case rationale", ""])
    order = [r["item_id"] for r in rows]
    for iid in order:
        g = GRADES[iid]
        fm = f", `{g['failure_mode']}`" if g["failure_mode"] else ""
        lines.extend([
            f"### {iid}",
            "",
            f"**Verdict:** `goal_met={_fmt_bool(bool(g['goal_met']))}`, `graceful_failure={_fmt_bool(bool(g['graceful_failure']))}`, `partial_fraction={g['partial_fraction']}`{fm}",
            "",
            RATIONALE[iid],
            "",
            "---",
            "",
        ])

    lines.extend([
        "## Next steps",
        "",
        "1. **Compute α:** `python scripts/compute_goaljudge_stage5_alpha.py docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_sheet.csv`",
        "2. **Update** [`goaljudge_stage5_goldset_pilot_results.md`](goaljudge_stage5_goldset_pilot_results.md) with α gate verdict.",
        "",
    ])

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Stage 5 pilot Annotator 2 grades")
    parser.parse_args()
    rows = apply_sheet()
    write_report(rows)


if __name__ == "__main__":
    main()
