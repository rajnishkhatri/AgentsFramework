"""Task 3.3b — verify a coded.jsonl actually carries codes (FR-G3.1.4).

The skill's Step-4 trap: codes only persist if the human presses Enter to commit
each as a chip; a comma-list typed into the memo box leaves ``open_codes`` empty.
This reports every row whose ``open_codes`` is empty/absent, with its ``trace_id``
and a per-mode uncoded count, so an uncoded session is caught before export.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

__all__ = ["CodedVerifyReport", "verify_coded", "main"]


class CodedVerifyReport(BaseModel):
    total_rows: int = 0
    uncoded_trace_ids: list[str] = []
    per_mode_uncoded: dict[str, int] = {}

    @property
    def ok(self) -> bool:
        return not self.uncoded_trace_ids


def verify_coded(path: Path) -> CodedVerifyReport:
    """Read a coded JSONL; flag rows with empty/absent ``open_codes``."""
    uncoded: list[str] = []
    per_mode: dict[str, int] = {}
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        total += 1
        row = json.loads(line)
        codes = row.get("open_codes") or []
        if not codes:
            tid = str(row.get("trace_id", "<no-trace_id>"))
            uncoded.append(tid)
            mode = str(row.get("mode", "<unknown>"))
            per_mode[mode] = per_mode.get(mode, 0) + 1
    return CodedVerifyReport(
        total_rows=total, uncoded_trace_ids=uncoded, per_mode_uncoded=per_mode
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coded", required=True, type=Path, help="coded JSONL path")
    args = parser.parse_args(argv)

    if not args.coded.exists():
        print(f"coded file not found: {args.coded}")
        return 1

    report = verify_coded(args.coded)
    if report.ok:
        print(f"OK — {report.total_rows} rows, all have open_codes.")
        return 0
    print(
        f"UNCODED — {len(report.uncoded_trace_ids)}/{report.total_rows} rows have "
        f"NO open_codes (per-mode {report.per_mode_uncoded}):"
    )
    for tid in report.uncoded_trace_ids:
        print(f"  {tid}")
    print("→ Enter-commit codes as chips in the coder, Save, and re-verify.")
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
