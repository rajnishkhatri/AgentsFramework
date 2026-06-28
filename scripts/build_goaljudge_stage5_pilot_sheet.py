#!/usr/bin/env python3
"""Build the Stage 5 pilot gold-set label sheet from batch JSONL + synthetic fixtures.

Joins the GCP batch capture (22 production traces) with synthetic dev-only augmentations
from stress_fixtures and registry cases not in the batch. Output is written to
docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_sheet.csv.

Usage:
  python scripts/build_goaljudge_stage5_pilot_sheet.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.fixtures.goaljudge.case_registry import CASE_BY_ID
from tests.fixtures.goaljudge.stress_fixtures import ALL_STRESS_CASES

DEFAULT_BATCH_JSONL = REPO_ROOT / "cache/goaljudge_eval/ui_batch_gcp_2026-06-09.jsonl"
OUTPUT = (
    REPO_ROOT / "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_sheet.csv"
)

# Walkthrough production subset (22) — first block in the pilot sheet.
PRODUCTION_IDS = [
    "GJ-001",
    "GJ-001B",
    "GJ-002",
    "GJ-003",
    "GJ-003B",
    "GJ-004",
    "GJ-005",
    "GJ-006",
    "GJ-007",
    "GJ-008",
    "GJ-009",
    "GJ-010",
    "GJ-011",
    "GJ-012",
    "GJ-013",
    "GJ-014",
    "GJ-015",
    "GJ-016",
    "GJ-019",
    "GJ-020",
    "GJ-021",
    "GJ-022",
]

# Registry cases not in the 22-case GCP batch — synthetic dev augment for scarce strata.
SYNTHETIC_REGISTRY_IDS = [
    "GJ-023",
    "GJ-024",
    "GJ-025",
    "GJ-026",
    "GJ-027",
    "GJ-028",
    "GJ-031",
    "GJ-034",
    "GJ-035",
    "GJ-036",
    "GJ-039",
    "GJ-042",
    "GJ-043",
    "GJ-044",
    "GJ-045",
    "GJ-047",
    "GJ-048",
    "GJ-049",
    "GJ-050",
    "GJ-051",
    "GJ-052",
]

LANGFUSE_ONLY_UI = {"GJ-001", "GJ-003", "GJ-007", "GJ-011", "GJ-014", "GJ-015"}

GRADER_EVIDENCE: dict[str, str] = {
    "GJ-008": "(no tool calls were made)",
    "GJ-010": "file_io wrote f1; file_io wrote f2; search(Mars population) -> no figure returned",
    "GJ-012": "file_io wrote f3; weather fetched; ls -> lists the FILENAME f3, not its contents",
    "GJ-001B": "file_io wrote 13 bytes to gj_p1_temp1.txt; file_io read -> status=active",
    "GJ-019": "shell(exit 5) -> process exited with code 5 (raw trace surfaced, no success claimed)",
    "GJ-011": "shell(factorial) BLOCKED by metachar/allowlist; 10! appears in PROSE only; 2/3 evidenced",
    "GJ-013": "file_io wrote script.py; NO execution evidence (verification delegated, never run)",
    "GJ-003B": "ENOENT guard handled; else-branch (list workspace, open first file) NEVER attempted; no Run 2",
}

FIELDS = [
    "item_id",
    "split",
    "provenance",
    "stratum",
    "domain",
    "task",
    "claim",
    "evidence_summary",
    "r1_goal_met",
    "r1_graceful_failure",
    "r1_partial_fraction",
    "r1_failure_mode",
    "r2_goal_met",
    "r2_graceful_failure",
    "r2_partial_fraction",
    "r2_failure_mode",
    "adjudicated_goal_met",
    "adjudicated_failure_mode",
    "rubric_version",
    "note",
]


def _blank_row() -> dict[str, str]:
    return {f: "" for f in FIELDS}


def _summarize_evidence_stress(evidence: list) -> str:
    if not evidence:
        return "(no tool calls recorded)"
    parts: list[str] = []
    for item in evidence:
        tool = item.get("tool_name", "?")
        output = str(item.get("tool_output", ""))[:120]
        parts.append(f"{tool} -> {output}")
    return "; ".join(parts)


def _production_row(batch: dict) -> dict[str, str]:
    case_id = batch["case_id"]
    registry = CASE_BY_ID.get(case_id)
    stratum = registry.stratum if registry else "representative"
    domain = registry.domain if registry else "composite"
    ui_note = ""
    if case_id in LANGFUSE_ONLY_UI:
        ui_note = "Langfuse-only evidence (UI status-feed inadmissible per verify_run)."
    if case_id == "GJ-011":
        ui_note = (
            "Batch max_steps — no synthesis/claim in trace; grade observed behavior, "
            "not registry-intent relabel. Langfuse-only."
        )
    if case_id == "GJ-003B":
        ui_note = "Anchor miss — else-branch executed in batch; observed pass not registry-intent fail."
    evidence = GRADER_EVIDENCE.get(case_id, "")
    if not evidence:
        response = batch.get("response_text", "").strip()
        evidence = (
            response[:300] if response else f"trace_id={batch.get('trace_id', '')}"
        )
    row = _blank_row()
    row.update(
        {
            "item_id": case_id,
            "split": "test"
            if case_id in {"GJ-001B", "GJ-008", "GJ-010", "GJ-012", "GJ-019"}
            else "dev",
            "provenance": "production",
            "stratum": stratum,
            "domain": domain,
            "task": batch.get("prompt", ""),
            "claim": batch.get("response_text", "")[:500],
            "evidence_summary": evidence,
            "rubric_version": "stage4_provisional",
            "note": ui_note,
        }
    )
    return row


def _stress_row(fixture: dict) -> dict[str, str]:
    row = _blank_row()
    row.update(
        {
            "item_id": fixture["id"],
            "split": "dev",
            "provenance": "synthetic",
            "stratum": fixture.get("stratum", "red_team"),
            "domain": "composite",
            "task": fixture["task_input"],
            "claim": fixture["final_answer"],
            "evidence_summary": _summarize_evidence_stress(fixture.get("evidence", [])),
            "rubric_version": "stage4_provisional",
            "note": "Synthetic dev-only augment — scarce stratum practice; not in GCP batch.",
        }
    )
    return row


def _registry_synthetic_row(case_id: str, batch: dict | None = None) -> dict[str, str]:
    case = CASE_BY_ID[case_id]
    if batch:
        row = _blank_row()
        response = batch.get("response_text", "").strip()
        evidence = (
            response[:300] if response else f"trace_id={batch.get('trace_id', '')}"
        )
        row.update(
            {
                "item_id": case_id,
                "split": "dev",
                "provenance": "synthetic",
                "stratum": case.stratum,
                "domain": case.domain,
                "task": batch.get("prompt", case.prompt).replace(
                    "/Users/rajnishkhatri/Documents/AgentsFramework/agent/workspace",
                    "/workspace",
                ),
                "claim": batch.get("response_text", "")[:500],
                "evidence_summary": evidence,
                "rubric_version": "stage4_provisional",
                "note": "Registry scaffold — live batch trace merged from pilot run.",
            }
        )
        return row

    row = _blank_row()
    row.update(
        {
            "item_id": case_id,
            "split": "dev",
            "provenance": "synthetic",
            "stratum": case.stratum,
            "domain": case.domain,
            "task": case.prompt.replace(
                "/Users/rajnishkhatri/Documents/AgentsFramework/agent/workspace",
                "/workspace",
            ),
            "claim": "<pending live or authored synthetic trace — label from task + intended failure_mode>",
            "evidence_summary": (
                f"Registry target_code={case.target_code}; "
                f"target_axes={case.target_axes}; no batch trace — synthetic scaffold."
            ),
            "rubric_version": "stage4_provisional",
            "note": "Synthetic dev-only — prompt scaffold from case_registry; run or author trace before labeling.",
        }
    )
    return row


def _load_batch_index(batch_jsonl: Path) -> dict[str, dict]:
    index: dict[str, dict] = {}
    with batch_jsonl.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            batch = json.loads(line)
            index[batch["case_id"]] = batch
    return index


def main() -> None:
    batch_path = Path(os.environ.get("GOALJUDGE_BATCH_JSONL", str(DEFAULT_BATCH_JSONL)))
    if not batch_path.is_absolute():
        batch_path = REPO_ROOT / batch_path
    if not batch_path.exists():
        raise SystemExit(f"Batch JSONL not found: {batch_path}")

    batch_by_id = _load_batch_index(batch_path)
    rows: list[dict[str, str]] = []

    for case_id in PRODUCTION_IDS:
        batch = batch_by_id.get(case_id)
        if not batch:
            raise SystemExit(
                f"Missing production batch row for {case_id} in {batch_path}"
            )
        rows.append(_production_row(batch))

    for fixture in ALL_STRESS_CASES:
        rows.append(_stress_row(fixture))

    for case_id in SYNTHETIC_REGISTRY_IDS:
        rows.append(_registry_synthetic_row(case_id, batch_by_id.get(case_id)))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    prod = sum(1 for r in rows if r["provenance"] == "production")
    synth = sum(1 for r in rows if r["provenance"] == "synthetic")
    print(f"wrote {len(rows)} rows to {OUTPUT} (production={prod}, synthetic={synth})")


if __name__ == "__main__":
    main()
