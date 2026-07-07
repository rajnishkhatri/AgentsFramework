"""Coach judge golden-regression gate — operator CLI (Phase-5 task 5.3).

Thin wrapper over ``meta.coach_regression_gate.run_coach_regression_gate``: grades the
COMMITTED recorded-label runs against the ADR-0019 certified floor + zero-flip and
prints a report. NEVER runs a live LLM — it scores already-recorded label snapshots.

Exit codes (mirroring scripts/eval_regression_gate.py):
  0 = all runs at/above floor, zero-flip (PASS)
  1 = floor breach or verdict flip (regression)
  2 = missing / empty / malformed / mislabeled artifact (error)

The always-on hard gate is the pytest test (tests/meta/test_coach_regression_gate.py,
in ``make check``); this CLI is the operator / quarterly-refresh entry point.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from meta.coach_regression_gate import (
    RUN_PATHS,
    SPLIT_PATH,
    run_coach_regression_gate,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Coach judge golden-regression gate (Phase-5 task 5.3)"
    )
    parser.add_argument(
        "--run",
        type=Path,
        action="append",
        dest="runs",
        help="a recorded-label run JSONL (repeat 3×); defaults to the committed runs",
    )
    parser.add_argument("--split", type=Path, default=SPLIT_PATH)
    parsed = parser.parse_args(argv)

    run_paths = tuple(parsed.runs) if parsed.runs else RUN_PATHS
    result = run_coach_regression_gate(run_paths=run_paths, split_path=parsed.split)

    if result.error is not None:
        print(f"COACH REGRESSION GATE: ERROR — {result.error}")
        return 2

    print(
        f"COACH REGRESSION GATE  ({len(result.per_run)} runs, flips={result.flip_count})"
    )
    for name, decision in result.per_run:
        gates = " ".join(f"{k}={v}" for k, v in decision.gates.items())
        print(f"  [{decision.verdict:7}] {name}: {gates}")

    if not result.ok:
        print(f"\nCOACH REGRESSION GATE: FAIL ({len(result.violations)} violation(s))")
        for v in result.violations:
            print(f"  - {v}")
        return 1

    print("\nCOACH REGRESSION GATE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
