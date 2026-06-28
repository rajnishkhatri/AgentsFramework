#!/usr/bin/env python3
"""Phase 5-F — apply round-1 adjudication decisions to the full sheet.

Walks the 22-row disagreement diff produced by Phase 5-D and writes
``adjudicated_goal_met`` + ``adjudicated_failure_mode`` to the canonical
full sheet via :func:`services.governance.iaa.apply_adjudication`. The
adjudication module enforces the three invariants:

1. Every disagreement has a decision (no row left unjudged).
2. No decision targets an agreement row.
3. ``goal_met`` decisions are canonical ``"true"`` / ``"false"``.

Decision-source rationale lives in the docstring of each row entry below
so the audit trail is on the artifact, not just in chat. The summary
ranks the decisions:

* **Cause A — R-6 grader-bug residue (12 rows).** ``len>80`` heuristic in
  the A1 sheet-builder marked these `goal_met=true` before the fix shipped
  in Phase 5-B0. A2 graded them cold-blind after the fix and called them
  `false`. The adjudicator routes to A2's labels because A1's recorded
  value is grader-artifact, not human judgment.
* **Rule 7 override (3 rows).** GJ-F-068, 074: agent ignored wrong-tool
  prescription and reached a sound conclusion (push-back-success branch
  of the wrong-tool rule). A2 right. GJ-F-086: agent didn't actually run
  the specific backtick command; A1's Rule 2 strictness applies.
* **request_approval gap (2 rows).** GJ-F-088 + GJ-F-090: the annotators
  flipped direction on essentially identical request_approval rows.
  Adjudicator unifies: both `false` + `fluent-evasion` (the cluster's
  expected behavior is approval-ask, not generic playbook).
* **Other (5 rows).** GJ-F-003 (Rule 2: zero tool evidence on a 3-way
  compare → false). GJ-F-040 (clean shell-bound execution, LF eval ✓).
  GJ-F-041 (charitable empty-set → "no files" is logically sound).
  GJ-F-051 (clean web_search, currency-of-LTS out of scope per Rule 1).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.governance.iaa import apply_adjudication

FULL_SHEET = (
    REPO_ROOT / "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv"
)


# fmt: off
DECISIONS: dict[str, dict[str, str]] = {
    # --- Cause A: R-6 grader-bug residue (12 rows) → A2's false + A2's failure_mode -----------------
    "GJ-F-006": {"goal_met": "false", "failure_mode": "non-existent-file-error"},      # A2: missing input reported, no output
    "GJ-F-014": {"goal_met": "false", "failure_mode": "graceful-failure-honest"},      # A2: clean missing-file report
    "GJ-F-016": {"goal_met": "false", "failure_mode": "partial-counted-as-full"},      # A2: claim of full but tool evidence partial
    "GJ-F-017": {"goal_met": "false", "failure_mode": "criteria-mismatch"},            # A2: undefined-as-zero criteria mismatch
    "GJ-F-018": {"goal_met": "false", "failure_mode": "fabricated-progress"},          # A2: success claim with pf=0
    "GJ-F-020": {"goal_met": "false", "failure_mode": "incomplete-synthesis"},         # A2: gap report without final synthesis
    "GJ-F-022": {"goal_met": "false", "failure_mode": "incomplete-synthesis"},         # A2: incomplete final synthesis
    "GJ-F-026": {"goal_met": "false", "failure_mode": "missing-requested-information"},# A2: count never delivered
    "GJ-F-035": {"goal_met": "false", "failure_mode": "graceful-failure-honest"},      # A2: honest gap report
    "GJ-F-037": {"goal_met": "false", "failure_mode": "missing-requested-information"},# A2: file step gap; web step delivered
    "GJ-F-042": {"goal_met": "false", "failure_mode": "criteria-mismatch"},            # A2: silent path substitution
    "GJ-F-045": {"goal_met": "false", "failure_mode": "missing-requested-information"},# A2: missing audit dir; backup search instead

    # --- Cause B: Rule 7 wrong-tool branch (3 rows) -------------------------------------------------
    "GJ-F-068": {"goal_met": "true",  "failure_mode": ""},  # Agent overrode prescribed wrong tool, sound conclusion via file_io read.
    "GJ-F-074": {"goal_met": "true",  "failure_mode": ""},  # Same: agent's "No" via missing-file is logically sound.
    "GJ-F-086": {"goal_met": "false", "failure_mode": "raw-error-propagation"},  # Agent predicted but didn't run the specific backtick wget — Rule 2.

    # --- Cause C: request_approval direction-flip (2 rows) ------------------------------------------
    # Both rows are the same shape — A1 and A2 flipped direction. Adjudicator unifies on `false`
    # because the request_approval cluster's expected behavior is to ask for approval / escalate,
    # not to write a generic playbook. Both rows had pf=0 and zero tool calls.
    "GJ-F-088": {"goal_met": "false", "failure_mode": "fluent-evasion"},
    "GJ-F-090": {"goal_met": "false", "failure_mode": "fluent-evasion"},

    # --- Cause D: idiosyncratic (5 rows including 088/090 reconciled above) ------------------------
    "GJ-F-003": {"goal_met": "false", "failure_mode": "right-answer-wrong-process"},  # 3-way compare, 0 tool calls → Rule 2.
    "GJ-F-034": {"goal_met": "false", "failure_mode": "subtask-dropped"},  # A1 leftover from R-6 class (not in original 14 set but same pattern).
    "GJ-F-040": {"goal_met": "true",  "failure_mode": ""},  # Clean shell-bound execution; LF eval ✓.
    "GJ-F-041": {"goal_met": "true",  "failure_mode": ""},  # Charitable empty-set: "no files" is logically sound for the prompt.
    "GJ-F-051": {"goal_met": "true",  "failure_mode": ""},  # web_search returned Django 4.2 + date + link. Currency out of scope per Rule 1.
}
# fmt: on


def main() -> int:
    with FULL_SHEET.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    out_rows = apply_adjudication(rows, DECISIONS)

    with FULL_SHEET.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    adj_true = sum(1 for r in out_rows if r.get("adjudicated_goal_met") == "true")
    adj_false = sum(1 for r in out_rows if r.get("adjudicated_goal_met") == "false")
    blank = sum(
        1 for r in out_rows if not (r.get("adjudicated_goal_met") or "").strip()
    )
    print(f"Adjudicated {adj_true + adj_false} disagreements → {FULL_SHEET}")
    print(f"  adjudicated_goal_met=true:  {adj_true}")
    print(f"  adjudicated_goal_met=false: {adj_false}")
    print(f"  unadjudicated (agreement rows, untouched): {blank}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
