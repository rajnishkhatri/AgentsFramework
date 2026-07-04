#!/usr/bin/env python
"""Leak-rate over the coded slice, partitioning out the truncated-reply confound.

Leak codes (per task): leak-strong-implication, rule-naming-as-leak,
hands-over-conclusion. A trace "leaks" if it carries >=1 of these.

The confound: some replies were cut off mid-sentence (truncated-reply). A leak
call on a truncated trace is only trustworthy if the leak is visible in the
SURVIVING text — not inferred from the lost tail. This script surfaces the
overlap so that judgment can be applied per-case (see NOTES.md); it does not
auto-drop truncated leaks.

Usage: .venv/bin/python leak_rate.py
"""

import json
import sys
from pathlib import Path

FIXTURE = Path(
    "docs/skills/agentsframework-axial-coding/evals/fixtures/coded_slice.jsonl"
)
LEAK_CODES = {
    "leak-strong-implication",
    "rule-naming-as-leak",
    "hands-over-conclusion",
}
TRUNC_CODE = "truncated-reply"


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def is_leak(row):
    return bool(LEAK_CODES & set(row["open_codes"]))


def is_trunc(row):
    return TRUNC_CODE in row["open_codes"]


def main():
    rows = load(FIXTURE)
    n = len(rows)
    leaks = [r for r in rows if is_leak(r)]
    truncs = [r for r in rows if is_trunc(r)]
    both = [r for r in rows if is_leak(r) and is_trunc(r)]

    print(f"N traces:            {n}")
    print(f"Leaking traces:      {len(leaks)}")
    print(f"Truncated traces:    {len(truncs)}")
    print(f"Leak AND truncated:  {len(both)}")
    print()
    print(
        f"Naive leak-rate  (leaks / N)          = {len(leaks)}/{n} = {len(leaks) / n:.3f}"
    )

    # Sensitivity floor: drop ALL truncated from both numerator and denominator.
    non_trunc = [r for r in rows if not is_trunc(r)]
    leaks_nt = [r for r in non_trunc if is_leak(r)]
    print(
        f"Drop-all-truncated (leaks / non-trunc) = "
        f"{len(leaks_nt)}/{len(non_trunc)} = {len(leaks_nt) / len(non_trunc):.3f}"
    )
    print()
    print("Truncated-and-leaking traces (need per-case judgment):")
    for r in both:
        print(
            f"  {r['trace_id'][:12]}  codes={sorted(LEAK_CODES & set(r['open_codes']))}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
