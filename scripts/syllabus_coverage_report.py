"""Deterministic standard x band coverage report over the promoted corpus.

D3 spec FR-7: "the bank is full" as a measurable artifact — the 32-standard
ACT-English syllabus crossed with score bands 1..5, filled with counts from
the promoted corpus (`docs/plan/coach-item-bank-live.promoted.json`; absent
file = zero coverage, the pre-Phase-B state). Rows lacking a ``standard_id``
NEVER count toward a cell (FR-5 forbids inventing tags retroactively); they
are flagged at the foot of the report instead.

The pure helpers here are also the ratchet's substrate
(`tests/architecture/test_syllabus_coverage_ratchet.py`, FR-3/FR-6): floors
in `docs/plan/act-english-coverage-floors.json` only rise. Offline, stdlib
only, zero LLM. Run:

    .venv/bin/python scripts/syllabus_coverage_report.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = _REPO / "docs" / "plan" / "coach-item-bank-live.promoted.json"
DEFAULT_SYLLABUS = _REPO / "docs" / "plan" / "act-english-syllabus.seed.json"
DEFAULT_FLOORS = _REPO / "docs" / "plan" / "act-english-coverage-floors.json"

_BANDS = (1, 2, 3, 4, 5)


def coverage_matrix(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Per-cell fill counts keyed ``"<standard_id>:<band>"``. Only rows that
    carry a ``standard_id`` count; band = the row's ``difficulty``."""
    counts: Counter[str] = Counter()
    for row in rows:
        if "standard_id" not in row:
            continue
        counts[f"{row['standard_id']}:{row.get('difficulty')}"] += 1
    return dict(counts)


def untagged_rows(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Identifiers of corpus rows that lack a ``standard_id`` (pre-D3 rows)."""
    return [
        str(row.get("id", row.get("stem_md", "?")))[:60]
        for row in rows
        if "standard_id" not in row
    ]


def floor_violations(floors: Mapping[str, int], counts: Mapping[str, int]) -> list[str]:
    """Every recorded floor the measured coverage fails to meet (FR-3). A
    cell absent from ``counts`` measures 0 — a floored cell must exist."""
    return [
        f"cell {cell}: floor {floor}, measured {counts.get(cell, 0)}"
        for cell, floor in sorted(floors.items())
        if counts.get(cell, 0) < floor
    ]


def render_report(
    syllabus: list[Mapping[str, Any]],
    counts: Mapping[str, int],
    untagged: list[str],
) -> str:
    """The standard x band matrix as fixed-width text. Cells outside a
    standard's syllabus bands render ``-`` (not authorable), zero-fill
    renders ``.`` (the gap the bank must close)."""
    lines = [
        "standard                                  | b1 | b2 | b3 | b4 | b5 | total"
    ]
    lines.append("-" * len(lines[0]))
    total = 0
    for std in sorted(syllabus, key=lambda s: int(s["standard_id"])):
        sid = int(std["standard_id"])
        cells = []
        row_total = 0
        for band in _BANDS:
            if band not in std["bands"]:
                cells.append("  -")
                continue
            n = counts.get(f"{sid}:{band}", 0)
            row_total += n
            cells.append(f"{n:3d}" if n else "  .")
        total += row_total
        label = f"{sid:2d} {str(std['name'])[:37]:<37}"
        lines.append(f"{label} |{' |'.join(cells)} | {row_total:5d}")
    lines.append(f"tagged rows total: {total}")
    if untagged:
        lines.append(f"UNTAGGED rows (never counted, FR-5): {len(untagged)}")
        lines.extend(f"  - {ident}" for ident in untagged)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--syllabus", type=Path, default=DEFAULT_SYLLABUS)
    parser.add_argument("--floors", type=Path, default=DEFAULT_FLOORS)
    args = parser.parse_args()
    rows = (
        json.loads(args.corpus.read_text(encoding="utf-8"))
        if args.corpus.exists()
        else []
    )
    syllabus = json.loads(args.syllabus.read_text(encoding="utf-8"))
    counts = coverage_matrix(rows)
    print(render_report(syllabus, counts, untagged_rows(rows)))
    floors = json.loads(args.floors.read_text(encoding="utf-8"))
    violations = floor_violations(floors, counts)
    if violations:
        print("\nFLOOR VIOLATIONS (ratchet would fail):", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
