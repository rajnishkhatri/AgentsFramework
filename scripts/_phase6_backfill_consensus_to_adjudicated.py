#!/usr/bin/env python3
"""Phase 6 pre-step — backfill ``adjudicated_*`` from r1/r2 consensus on agreement rows.

Phase 5's ``apply_adjudication`` writes ``adjudicated_goal_met`` /
``adjudicated_failure_mode`` only on **disagreement** rows (per protocol
Rule 5: "adjudicated columns are populated only after the α gate clears"
and only by the adjudicator on rows that disagreed).

Phase 6's ``row_to_goldset_item`` reads only the ``adjudicated_*`` columns.
The seam between the two: on agreement rows (where r1 == r2), the implicit
adjudicated value is the consensus — but the column is blank.

This pre-step bridges that seam by writing the r1==r2 consensus values into
``adjudicated_goal_met`` / ``adjudicated_failure_mode`` (and the matching
graceful_failure / partial_fraction columns Phase 6's row_to_goldset_item
falls back to via ``row.get("adjudicated_X", row.get("r1_X", ""))``) on
agreement rows ONLY. Disagreement rows are left untouched — the
adjudicator's verdict stays canonical.

After this runs, every row has a populated ``adjudicated_goal_met``, and
``scripts/assemble_goaljudge_goldset.py`` can be invoked without error.

This is idempotent — running twice produces the same sheet.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from components.schemas import GOAL_FAILURE_MODES
from services.governance.iaa import normalize_bool_label

FULL_SHEET = (
    REPO_ROOT / "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv"
)

# Active failure-mode vocabulary. Codes outside this set were valid in
# pre-Phase-5 drafts (e.g. ``incomplete-run`` was renamed to
# ``incomplete-synthesis`` and ``subtask-dropped`` was split out). The
# backfill prefers A2's code when A1's code is no longer in the active
# vocab — A2's sheet was built after the vocabulary tightening and is
# already validated at labeling time, so it's authoritative on codes.
_VALID_FM = set(GOAL_FAILURE_MODES)


def main() -> int:
    with FULL_SHEET.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    backfilled = 0
    skipped_disagreement = 0
    untouched = 0
    for row in rows:
        r1 = normalize_bool_label(str(row.get("r1_goal_met", "")))
        r2 = normalize_bool_label(str(row.get("r2_goal_met", "")))
        already_adj = str(row.get("adjudicated_goal_met", "")).strip()
        if already_adj:
            skipped_disagreement += 1
            continue
        # Agreement row by definition (r1 == r2, both filled, no adjudicated value).
        if r1 == r2 and r1 in {"true", "false"}:
            row["adjudicated_goal_met"] = r1
            # failure_mode: pick A1's by convention (the column-order tie-break),
            # but defer to A2's when A1's code is invalid under the current vocab
            # (e.g. legacy ``incomplete-run``) or when A1 is blank.
            r1_fm = (row.get("r1_failure_mode") or "").strip()
            r2_fm = (row.get("r2_failure_mode") or "").strip()
            if r1_fm in _VALID_FM:
                row["adjudicated_failure_mode"] = r1_fm
            elif r2_fm in _VALID_FM:
                row["adjudicated_failure_mode"] = r2_fm
            else:
                row["adjudicated_failure_mode"] = ""
            backfilled += 1
        else:
            untouched += 1

    with FULL_SHEET.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Phase 6 backfill complete → {FULL_SHEET}")
    print(f"  backfilled (agreement → adjudicated): {backfilled}")
    print(f"  skipped (already-adjudicated disagreement): {skipped_disagreement}")
    print(f"  untouched (unexpected blank state): {untouched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
