"""Task 3.3c — roll coded.jsonl → coach_step1_open_code_inventory.csv (FR-G3.1.9).

One row per distinct code, GoalJudge inventory columns (parity with
docs/research/goaljudge_step1_open_code_inventory.csv) so Task 3.4 axial coding
consumes the same shape. The human fills ``short_definition``/``alias_note``
during axial coding; this seeds the mechanical fields (code, first-seen case,
an exemplar) from the coded pass.
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

__all__ = ["GOALJUDGE_COLUMNS", "build_inventory", "main"]

GOALJUDGE_COLUMNS = (
    "code",
    "short_definition",
    "source_doc",
    "first_seen_case",
    "alias_note",
    "example",
    "example_ref",
    # Axial-coding columns (FR-13): the coder's single edit surface. ``axis`` is
    # the partition source of truth (agent-behavior / environment-confound /
    # judge-reliability); ``category`` joins to the categories CSV. Both blank
    # here; the human fills them during axial coding.
    "axis",
    "category",
)

_SOURCE_DOC = "coach_phase2_open_coding.md (Task 3.3 open coding)"


def build_inventory(coded_path: Path, out_path: Path) -> None:
    """Read a coded JSONL; write the distinct-code inventory CSV."""
    # Preserve first-seen order per code, capture an exemplar from that row.
    first_seen: dict[str, dict[str, str]] = {}
    for line in coded_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        tid = str(row.get("trace_id", "<no-trace_id>"))
        mode = str(row.get("mode", ""))
        example = str(row.get("final_answer", "") or row.get("prompt", ""))[:200]
        for code in row.get("open_codes") or []:
            if code not in first_seen:
                first_seen[code] = {
                    "first_seen_case": f"trace {tid}" + (f" · {mode}" if mode else ""),
                    "example": example,
                    "example_ref": tid,
                }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(GOALJUDGE_COLUMNS)
        for code in sorted(first_seen):
            info = first_seen[code]
            writer.writerow(
                [
                    code,
                    "",  # short_definition — human fills at axial coding
                    _SOURCE_DOC,
                    info["first_seen_case"],
                    "",  # alias_note — human fills if merged/renamed
                    info["example"],
                    info["example_ref"],
                    "",  # axis — human fills at axial coding (FR-13)
                    "",  # category — human fills at axial coding (FR-13)
                ]
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coded", required=True, type=Path, help="coded JSONL path")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/research/coach_step1_open_code_inventory.csv"),
        help="inventory CSV output path",
    )
    args = parser.parse_args(argv)

    if not args.coded.exists():
        print(f"coded file not found: {args.coded}")
        return 1

    build_inventory(args.coded, args.out)
    print(f"wrote inventory → {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
