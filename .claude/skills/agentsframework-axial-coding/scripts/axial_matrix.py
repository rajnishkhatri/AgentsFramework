"""Code x category frequency matrix (FR-3 / FR-9).

Joins the coded JSONL (code occurrences) to the inventory CSV (code -> axis,
category) and the categories CSV (category -> axis), then rolls per-category
frequencies. The load-bearing rule is FR-3: **environment-confound rows are a
validity precondition, not a behavioral bucket** — they are excluded from the
agent-behavior denominator so counts are not poisoned by sandbox artifacts.

Read-only, stdlib only, framework-agnostic.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def _load_axis_category(inventory_path: Path) -> dict[str, tuple[str, str]]:
    """code -> (axis, category) from the inventory CSV."""
    out: dict[str, tuple[str, str]] = {}
    with inventory_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            code = (row.get("code") or "").strip()
            if code:
                out[code] = (
                    (row.get("axis") or "").strip(),
                    (row.get("category") or "").strip(),
                )
    return out


def build_matrix(coded_path: Path, inventory_path: Path) -> dict[str, object]:
    """Return per-category counts + the agent-behavior denominator.

    ``agent_denominator`` counts traces carrying >=1 agent-behavior code, with
    traces whose codes are ALL environment-confound excluded (FR-3).
    """
    axis_cat = _load_axis_category(inventory_path)
    occurrence_counts: Counter[str] = Counter()
    trace_counts: Counter[str] = Counter()
    agent_traces = 0
    confound_only_traces = 0

    for line in coded_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        codes = row.get("open_codes") or []
        axes = {axis_cat.get(c, ("", ""))[0] for c in codes}
        has_agent = "agent-behavior" in axes
        # A trace is a pure confound if it has confound codes and no agent code.
        if not has_agent and "environment-confound" in axes:
            confound_only_traces += 1
            continue  # FR-3: excluded from the agent denominator
        if has_agent:
            agent_traces += 1
        # Occurrence counts sum code hits; trace counts count each category once
        # per trace even when >1 of its codes co-occur. Reporting only the
        # former (and pairing it with a trace-level denominator) overstates
        # prevalence — the mislabel the iteration-1 review caught.
        cats_this_trace: set[str] = set()
        for c in codes:
            axis, cat = axis_cat.get(c, ("", ""))
            if axis == "agent-behavior" and cat:
                occurrence_counts[cat] += 1
                cats_this_trace.add(cat)
        for cat in cats_this_trace:
            trace_counts[cat] += 1

    return {
        "category_occurrence_counts": dict(occurrence_counts),
        "category_trace_counts": dict(trace_counts),
        "agent_denominator": agent_traces,
        "confound_only_excluded": confound_only_traces,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coded", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    args = parser.parse_args(argv)
    for p in (args.coded, args.inventory):
        if not p.exists():
            print(f"file not found: {p}")
            return 2
    result = build_matrix(args.coded, args.inventory)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
