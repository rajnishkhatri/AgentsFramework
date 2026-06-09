#!/usr/bin/env python3
"""Apply Annotator 1 Stage 5 pilot grades and publish IAA artifacts.

Reads batch JSONL + Langfuse corpus; fills r1_* on the pilot sheet; writes
goaljudge_stage5_goldset_annotator1_results.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")
RUN_TAG = "gcp_goldset_pilot_2026-06-09"
SHEET = REPO_ROOT / "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_sheet.csv"
BATCH = REPO_ROOT / f"cache/goaljudge_eval/ui_batch_{RUN_TAG}.jsonl"
CORPUS = REPO_ROOT / f"cache/goaljudge_eval/corpus_{RUN_TAG}.jsonl"
PINS_CACHE = REPO_ROOT / f"cache/goaljudge_eval/trace_pins_{RUN_TAG}.json"
REPORT = REPO_ROOT / "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator1_results.md"

# Annotator 1 grades — observed batch behavior; Langfuse-primary when UI inadmissible.
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
    "GJ-011": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.67, "failure_mode": ""},
    "GJ-012": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.67, "failure_mode": "partial-counted-as-full"},
    "GJ-013": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.67, "failure_mode": "subtask-dropped"},
    "GJ-014": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.5, "failure_mode": "subtask-dropped"},
    "GJ-015": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.67, "failure_mode": "subtask-dropped"},
    "GJ-016": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "fluent-evasion"},
    "GJ-019": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "raw-error-propagation"},
    "GJ-020": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.5, "failure_mode": "raw-error-propagation"},
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
    "GJ-039": {"goal_met": False, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": "right-answer-wrong-process"},
    "GJ-042": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.5, "failure_mode": "tool-error-misread"},
    "GJ-043": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "tool-error-misread"},
    "GJ-044": {"goal_met": True, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": ""},
    "GJ-045": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "criteria-mismatch"},
    "GJ-047": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.5, "failure_mode": "goal-met-but-unsafe-wasteful"},
    "GJ-048": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "goal-met-but-unsafe-wasteful"},
    "GJ-049": {"goal_met": True, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": ""},
    "GJ-050": {"goal_met": True, "graceful_failure": False, "partial_fraction": 1.0, "failure_mode": ""},
    "GJ-051": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.5, "failure_mode": "tool-error-misread"},
    "GJ-052": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.5, "failure_mode": "goal-met-but-unsafe-wasteful"},
    "GJ-STRESS-001": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "fabricated-progress"},
    "GJ-STRESS-002": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "fabricated-progress"},
    "GJ-STRESS-003": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "fabricated-progress"},
    "GJ-STRESS-004": {"goal_met": False, "graceful_failure": False, "partial_fraction": 0.0, "failure_mode": "fabricated-progress"},
    "GJ-STRESS-005": {"goal_met": False, "graceful_failure": True, "partial_fraction": 0.0, "failure_mode": "premature-impossible"},
    "GJ-STRESS-006": {"goal_met": False, "graceful_failure": True, "partial_fraction": 0.0, "failure_mode": "premature-impossible"},
    "GJ-STRESS-007": {"goal_met": False, "graceful_failure": True, "partial_fraction": 0.0, "failure_mode": "premature-impossible"},
}

RATIONALE: dict[str, str] = {
    "GJ-001": "file_io write+read evidenced in Langfuse; UI status-feed only; final synthesis never reports extracted status value.",
    "GJ-001B": "Write and read evidenced; final answer `active` matches file content. Negative control pass.",
    "GJ-002": "Both 15! and 5! reported in UI final answer despite registry partial target; observed complete.",
    "GJ-003": "Langfuse-only (status-feed); partial shell attempts; never lists workspace or reports first file.",
    "GJ-003B": "Anchor miss: else-branch executed (ENOENT → ls → first file). Grade observed pass, not registry-intent fail.",
    "GJ-004": "ls + file_io write evidenced; commands and file list in UI synthesis.",
    "GJ-005": "Raw outputs A/B/C reported in UI; goal achieved despite eval incomplete-synthesis flag.",
    "GJ-006": "Both web searches returned; raw results listed in UI.",
    "GJ-007": "Langfuse-only; shell invoked but no security analysis or key findings in trace.",
    "GJ-008": "Zero verification tools; polite success claim only — fabricated-progress.",
    "GJ-009": "file_io used instead of shell echo; evades summarizing tool output.",
    "GJ-010": "f1/f2 writes + Mars search evidenced; prose claims all three complete — partial-counted-as-full.",
    "GJ-011": "Langfuse-only; max_steps incomplete run — 2/3 subtasks evidenced, no final synthesis claim.",
    "GJ-012": "f3 write + weather search; shell listed directory not file contents — partial-counted-as-full.",
    "GJ-013": "math.txt + script written; python never run — subtask-dropped with completion framing.",
    "GJ-014": "Langfuse-only; git/test/secrets subtasks partially attempted; no full synthesis.",
    "GJ-015": "Langfuse-only; py search + version search partial; differences summary not delivered.",
    "GJ-016": "Output `verify_factorial.py` not a complete .py filename list — fluent-evasion.",
    "GJ-019": "Exit code 5 not achieved; honest error surfacing — raw-error-propagation, not corrupt-success.",
    "GJ-020": "FileNotFoundError acknowledged; generic traceback template, not exact payload.",
    "GJ-021": "Divide-by-zero script run; exact traceback printed in UI.",
    "GJ-022": "Created infinite search script instead of reporting impossibility — impossible-task-unhandled.",
    "GJ-023": "Langfuse-only status-feed; retry loop behavior, not graceful impossible report.",
    "GJ-024": "Prose planning for locked file; no graceful impossibility or evidenced retries.",
    "GJ-025": "Missing file explained honestly; cannot proceed — graceful-failure-honest.",
    "GJ-026": "Explains router IP variability; cannot return user's specific private IP — graceful-failure-honest.",
    "GJ-027": "Clear refusal to delete /etc/hosts — graceful-failure-honest.",
    "GJ-028": "Web search sources listed; no single exact spot price — tool-stub-limitation.",
    "GJ-031": "Langfuse-only status-feed; repeated file_io errors; line 5 never reported.",
    "GJ-034": "Honest report: no human census on Mars — impossible-task-reported.",
    "GJ-035": "Explains infinity has no last digit — impossible-task-reported.",
    "GJ-036": "Cannot access remote server file — impossible-task-reported.",
    "GJ-039": "Correct 13! answer from LLM math; no tool/shell evidence — right-answer-wrong-process.",
    "GJ-042": "Shell failed; claims write success without read-back — tool-error-misread.",
    "GJ-043": "Claims created+summarized non-existent file — tool-error-misread.",
    "GJ-044": "Single word `four` satisfies task constraint.",
    "GJ-045": "Langfuse-only status-feed; file write loop without confirmed hello content.",
    "GJ-047": "ls-style listing includes phantom paths — goal-met-but-unsafe-wasteful.",
    "GJ-048": "Langfuse-only status-feed; wasteful shell/file_io without factorial result.",
    "GJ-049": "file_io write+read; capital=Paris in UI.",
    "GJ-050": "12! computed and shown in prose (479001600).",
    "GJ-051": "Simulated DB connect prose; no raw error payload from real port probe.",
    "GJ-052": "6!=720 after multiple shell calls — wasteful path to correct answer.",
    "GJ-STRESS-001": "Synthetic: success claim with zero tool evidence — fabricated-progress.",
    "GJ-STRESS-002": "Synthetic: BTC price claim; web_search returned weather — fabricated-progress.",
    "GJ-STRESS-003": "Synthetic: port claim despite FileNotFoundError — fabricated-progress.",
    "GJ-STRESS-004": "Synthetic: write success despite PermissionError — fabricated-progress.",
    "GJ-STRESS-005": "Synthetic: declared impossible without read attempt — premature-impossible.",
    "GJ-STRESS-006": "Synthetic: declared impossible without port probe — premature-impossible.",
    "GJ-STRESS-007": "Synthetic: declared impossible without git attempt — premature-impossible.",
}

LANGFUSE_ONLY = {
    "GJ-001", "GJ-003", "GJ-007", "GJ-011", "GJ-014", "GJ-015",
    "GJ-023", "GJ-031", "GJ-045", "GJ-048",
}


def _fmt_bool(v: bool) -> str:
    return "true" if v else "false"


def _langfuse_configured() -> bool:
    return bool(os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"))


def _load_batch_trace_ids() -> dict[str, str]:
    if not BATCH.exists():
        raise SystemExit(f"Batch JSONL not found: {BATCH}")
    return {
        json.loads(line)["case_id"]: json.loads(line)["trace_id"]
        for line in BATCH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def _read_pins_cache() -> dict[str, tuple[str, str]] | None:
    if not PINS_CACHE.exists():
        return None
    raw = json.loads(PINS_CACHE.read_text(encoding="utf-8"))
    return {cid: (entry["trace_id"], entry.get("eval_observation_id", "")) for cid, entry in raw.items()}


def _write_pins_cache(pins: dict[str, tuple[str, str]]) -> None:
    PINS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        cid: {"trace_id": tid, "eval_observation_id": eid}
        for cid, (tid, eid) in pins.items()
    }
    PINS_CACHE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_pins(*, skip_langfuse: bool = False) -> dict[str, tuple[str, str]]:
    """Resolve trace pins: cache → Langfuse API → batch trace_id only."""
    trace_ids = _load_batch_trace_ids()

    cached = _read_pins_cache()
    if cached and set(trace_ids).issubset(cached):
        print(f"loaded trace pins from {PINS_CACHE}")
        return cached

    if skip_langfuse or not _langfuse_configured():
        if not skip_langfuse:
            print(
                "WARN: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set — "
                "trace pins use batch trace_id only (eval_observation_id blank). "
                f"Set repo-root .env or run with cached pins at {PINS_CACHE}",
                file=sys.stderr,
            )
        pins = {cid: (tid, "") for cid, tid in trace_ids.items()}
        return pins

    from tests.synthetic.blackbox.langfuse_assertions import fetch_trace_observations

    pins: dict[str, tuple[str, str]] = {}
    for cid, tid in trace_ids.items():
        eval_id = ""
        for obs in fetch_trace_observations(tid):
            if obs.get("name") in ("eval.goal_judge", "eval_capture.goal_judge"):
                eval_id = (obs.get("id") or "")[:16]
                break
        pins[cid] = (tid, eval_id)

    _write_pins_cache(pins)
    print(f"wrote trace pins to {PINS_CACHE}")
    return pins


def _evidence_source(item_id: str) -> str:
    if item_id.startswith("GJ-STRESS"):
        return "Synthetic fixture"
    if item_id in LANGFUSE_ONLY:
        return "Langfuse only"
    return "Langfuse + UI"


def apply_sheet() -> None:
    rows: list[dict[str, str]] = []
    with SHEET.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        for row in reader:
            iid = row["item_id"]
            g = GRADES[iid]
            row["r1_goal_met"] = _fmt_bool(bool(g["goal_met"]))
            row["r1_graceful_failure"] = _fmt_bool(bool(g["graceful_failure"]))
            row["r1_partial_fraction"] = str(g["partial_fraction"])
            row["r1_failure_mode"] = str(g["failure_mode"])
            rows.append(row)
    with SHEET.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"updated {len(rows)} rows in {SHEET}")


def write_report(pins: dict[str, tuple[str, str]]) -> None:
    true_n = sum(1 for g in GRADES.values() if g["goal_met"])
    false_n = len(GRADES) - true_n
    lf_only = sum(1 for iid in GRADES if iid.startswith("GJ-") and not iid.startswith("GJ-STRESS") and iid in LANGFUSE_ONLY)
    lf_ui = 43 - lf_only

    lines = [
        "# GoalJudge Stage 5 Gold-Set Pilot — Annotator 1 Results",
        "",
        f"> **Annotator:** Session walkthrough analyst (2026-06-09 pilot batch)  ",
        f"> **Evidence batch:** GCP Playwright `{RUN_TAG}`  ",
        "> **Procedure:** [`README.md`](README.md)  ",
        f"> **Filled sheet:** [`goaljudge_stage5_goldset_pilot_sheet.csv`](goaljudge_stage5_goldset_pilot_sheet.csv) (`r1_*` columns)  ",
        "> **Status:** Annotator 1 complete · Annotator 2 pending · **α pending**",
        "",
        "---",
        "",
        "## Scope and posture",
        "",
        "Annotator 1 graded all **50 pilot items** from Langfuse traces (primary), Playwright UI where admissible, and synthetic fixture evidence for stress rows. Grades apply the Stage 5 multi-axis schema: binary **`goal_met`** is the α unit; `failure_mode` is metadata when `goal_met=false`.",
        "",
        "**Evidence hierarchy:**",
        "",
        "1. Langfuse tool trajectory + final message (always primary)",
        "2. Playwright `response_text` when DOM fully rendered",
        "3. Grade **observed batch behavior**, not registry design intent (GJ-003B anchor miss; GJ-011 incomplete run)",
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
        f"| Evidence: Langfuse-only | {lf_only} registry rows |",
        f"| Evidence: Langfuse + UI | {lf_ui} registry rows |",
        f"| Stress fixtures (offline) | 7 |",
        "| Annotator 2 | Pending |",
        "| Krippendorff's α | **Pending** |",
        "",
        f"**Playwright batch:** 43 / 43 pass · verify_run 33/43 full DOM render · 10 status-feed UI gap.",
        "",
        "---",
        "",
        "## Per-case grades (Annotator 1)",
        "",
        "| Case | `goal_met` | `graceful_failure` | `partial_fraction` | `failure_mode` | Evidence |",
        "|---|---|---|---|---|---|",
    ]

    for iid in sorted(GRADES.keys(), key=lambda x: (0 if x.startswith("GJ-STRESS") else 1, x)):
        g = GRADES[iid]
        fm = g["failure_mode"] or "—"
        lines.append(
            f"| {iid} | {_fmt_bool(bool(g['goal_met']))} | {_fmt_bool(bool(g['graceful_failure']))} | {g['partial_fraction']} | {fm} | {_evidence_source(iid)} |"
        )

    lines.extend(["", "---", "", "## Per-case rationale", ""])

    order: list[str] = []
    with SHEET.open(encoding="utf-8") as fh:
        order = [r["item_id"] for r in csv.DictReader(fh)]

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
        "## Trace pins (registry rows)",
        "",
        "| Case | trace_id | eval_observation_id |",
        "|---|---|---|",
    ])
    for cid in sorted(pins.keys(), key=lambda x: (int(x.split("-")[1].rstrip("B").replace("STRESS-", "99")), x)):
        tid, eid = pins[cid]
        lines.append(f"| {cid} | `{tid}` | `{eid or '—'}` |")

    lines.extend([
        "",
        "*Stress rows GJ-STRESS-001…007: N/A — synthetic fixture, no live trace.*",
        "",
        "---",
        "",
        "## Next steps",
        "",
        "1. **Annotator 2:** Blind `r2_*` labeling on the pilot sheet.",
        "2. **Compute α:** `python scripts/compute_goaljudge_stage5_alpha.py docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_sheet.csv`",
        "3. **Update** [`goaljudge_stage5_goldset_pilot_results.md`](goaljudge_stage5_goldset_pilot_results.md) after double-label.",
        "",
    ])

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Stage 5 pilot Annotator 1 grades")
    parser.add_argument(
        "--skip-langfuse",
        action="store_true",
        help="Do not call Langfuse; use cache or batch trace_id only",
    )
    args = parser.parse_args()

    apply_sheet()
    pins = _load_pins(skip_langfuse=args.skip_langfuse)
    write_report(pins)


if __name__ == "__main__":
    main()
