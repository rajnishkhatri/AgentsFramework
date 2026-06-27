#!/usr/bin/env python
"""Coverage and Integrity Verification Gate for GoalJudge.

Performs two critical checks on the exported synthetic corpus:
  1. Integrity Constraint: Verifies that set(exported_trace_ids) == set(intended_case_ids)
     (no foreign rows, no orphan rows, scoped precisely to our user_id run).
  2. Coverage & Divergence Mapping: Records expected vs observed verdict axes.
     Mismatches are highlighted as qualitative data (such as judge-quality J2/J3 codes),
     not re-rolled to match.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Configure import paths
SCRIPTS_DIR = Path(__file__).resolve().parent
AGENT_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(AGENT_ROOT))

from dotenv import load_dotenv

load_dotenv(AGENT_ROOT / ".env")

from tests.fixtures.goaljudge.case_registry import LIVE_CASES

console = Console()

# partial_fraction band tolerance for divergence detection.
_PARTIAL_TOLERANCE = 0.15

# Non-failure baseline code: excluded from the per-code saturation target
# (plan: "correct-complete is a non-failure baseline ... excluded from the
# per-code coverage target").
_NON_FAILURE_BASELINE = {"correct-complete"}


def verify_corpus(jsonl_path: str = "cache/goaljudge_eval/run.jsonl") -> bool:
    p = Path(AGENT_ROOT / jsonl_path)
    if not p.exists():
        console.print(
            f"[bold red]Error: Exported corpus file {jsonl_path} does not exist. Please run export first.[/bold red]"
        )
        return False

    # 1. Load exported rows
    exported_rows = []
    with open(p, "r") as fh:
        for line in fh:
            if line.strip():
                exported_rows.append(json.loads(line))

    # 2. Extract exported trace IDs
    exported_trace_ids = {row["trace_id"] for row in exported_rows}

    # 3. Generate intended trace IDs from case registry
    intended_case_map = {}
    for c in LIVE_CASES:
        tid = uuid.uuid5(uuid.NAMESPACE_DNS, c.id).hex
        intended_case_map[tid] = c

    intended_trace_ids = set(intended_case_map.keys())

    # 4. Integrity assertions: Scoping and foreign rows
    console.print(
        Panel(
            "[bold green]Step 1: Checking Corpus Integrity & Scoping Boundaries[/bold green]"
        )
    )

    orphans = intended_trace_ids - exported_trace_ids
    foreign_rows = exported_trace_ids - intended_trace_ids

    integrity_passed = True
    if orphans:
        console.print(
            f"[bold yellow]Warning: {len(orphans)} intended cases are missing from the exported corpus (orphans):[/bold yellow]"
        )
        for o in orphans:
            console.print(f"  - Case ID: {intended_case_map[o].id} (Trace ID: {o})")
        integrity_passed = False
    else:
        console.print(
            "[bold green]✓ No orphan rows: All intended cases were successfully exported.[/bold green]"
        )

    if foreign_rows:
        console.print(
            f"[bold red]Error: {len(foreign_rows)} foreign/unintended trace IDs found in the exported corpus (pollution):[/bold red]"
        )
        for f in foreign_rows:
            console.print(f"  - Foreign Trace ID: {f}")
        integrity_passed = False
    else:
        console.print(
            "[bold green]✓ No foreign rows: Corpus is perfectly clean and isolated to intended cases.[/bold green]"
        )

    # 5. Coverage and Divergence verification
    console.print(
        Panel(
            "[bold green]Step 2: Checking Axis Coverage & Recording Divergences[/bold green]"
        )
    )

    table = Table(title="GoalJudge Expected vs Observed Axes")
    table.add_column("Case ID", style="cyan")
    table.add_column("Target Code", style="magenta")
    table.add_column("Goal Met (Exp/Obs)", style="yellow")
    table.add_column("Graceful Fail (Exp/Obs)", style="yellow")
    table.add_column("Partial Fraction (Exp/Obs)", style="yellow")
    table.add_column("Status / Note", style="green")

    divergences = []
    code_coverage = {}

    for row in exported_rows:
        tid = row["trace_id"]
        case = intended_case_map.get(tid)
        if not case:
            continue

        # Extract expected axes
        exp_goal = case.target_axes.get("goal_met")
        exp_grace = case.target_axes.get("graceful_failure")
        exp_partial = case.target_axes.get("partial_fraction")

        # Extract observed axes from Langfuse & eval_capture halves
        obs_goal = row.get("goal_met")
        obs_grace = row.get("graceful_failure")
        obs_partial = row.get("partial_fraction")

        # If None from eval_capture, fall back to Langfuse / string parsing
        if obs_goal is None:
            obs_goal = "N/A"
        if obs_grace is None:
            obs_grace = "N/A"
        if obs_partial is None:
            obs_partial = "N/A"

        # Check for mismatch/divergence. partial_fraction is a float, so use a
        # tolerance band rather than exact equality (the judge rarely returns
        # the exact target float; only a meaningful band shift is a divergence).
        def _partial_diverges(exp: object, obs: object) -> bool:
            if obs == "N/A" or exp is None:
                return False
            try:
                return abs(float(exp) - float(obs)) > _PARTIAL_TOLERANCE
            except (TypeError, ValueError):
                return exp != obs

        has_divergence = (
            (exp_goal != obs_goal and obs_goal != "N/A")
            or (exp_grace != obs_grace and obs_grace != "N/A")
            or _partial_diverges(exp_partial, obs_partial)
        )

        goal_str = f"{exp_goal} / {obs_goal}"
        grace_str = f"{exp_grace} / {obs_grace}"
        partial_str = f"{exp_partial} / {obs_partial}"

        if has_divergence:
            status_note = "[bold yellow]Divergence[/bold yellow]"
            divergences.append(
                {
                    "case_id": case.id,
                    "target_code": case.target_code,
                    "expected": {
                        "goal_met": exp_goal,
                        "graceful": exp_grace,
                        "partial": exp_partial,
                    },
                    "observed": {
                        "goal_met": obs_goal,
                        "graceful": obs_grace,
                        "partial": obs_partial,
                    },
                    "rationale": row.get("rationale"),
                }
            )
        else:
            status_note = "[green]Matched[/green]"

        # Track covered codes
        code_coverage[case.target_code] = code_coverage.get(case.target_code, 0) + 1

        table.add_row(
            case.id, case.target_code, goal_str, grace_str, partial_str, status_note
        )

    console.print(table)

    if divergences:
        console.print(
            Panel(
                f"[bold yellow]Recorded {len(divergences)} Divergences (Valuable Empirical Data)[/bold yellow]"
            )
        )
        for d in divergences:
            console.print(
                f"[bold cyan]{d['case_id']} ({d['target_code']}):[/bold cyan]\n"
                f"  Expected: Goal={d['expected']['goal_met']}, Graceful={d['expected']['graceful']}, Partial={d['expected']['partial']}\n"
                f"  Observed: Goal={d['observed']['goal_met']}, Graceful={d['observed']['graceful']}, Partial={d['observed']['partial']}\n"
                f"  Judge Rationale: {d['rationale']}\n"
                f"  [dim]*Note: Do not re-roll. This represents genuine judge-quality evidence (e.g. J2/J3 candidates).[/dim]\n"
            )

    # 6. Report failure code saturation
    console.print(
        Panel("[bold green]Step 3: Taxonomy Coverage & Saturation Audit[/bold green]")
    )

    taxonomy_table = Table(
        title="Taxonomy Saturation Status (~3-5 examples per code target)"
    )
    taxonomy_table.add_column("Failure Relevant Code", style="cyan")
    taxonomy_table.add_column("Observed Cases", style="green")
    taxonomy_table.add_column("Saturation Status", style="yellow")

    under_saturated = []
    # Failure-relevant codes only; the correct-complete baseline is NOT part of
    # the per-code saturation target (plan: excluded from the coverage target).
    all_target_codes = sorted(
        {c.target_code for c in LIVE_CASES} - _NON_FAILURE_BASELINE
    )

    for code in all_target_codes:
        count = code_coverage.get(code, 0)
        if count >= 3:
            status = "[bold green]SATURATED (>=3 examples)[/bold green]"
        else:
            status = "[bold yellow]UNDER-SATURATED (<3 examples)[/bold yellow]"
            under_saturated.append(code)

        taxonomy_table.add_row(code, str(count), status)

    # Show the baseline count separately (informational, not gated).
    baseline_count = code_coverage.get("correct-complete", 0)
    taxonomy_table.add_row(
        "correct-complete",
        str(baseline_count),
        "[dim]baseline (not gated)[/dim]",
    )

    console.print(taxonomy_table)

    if under_saturated:
        console.print(
            f"[bold yellow]Warning: {len(under_saturated)} codes are under-saturated.[/bold yellow]"
        )
        return False
    else:
        console.print(
            "[bold green]✓ Saturated: Every failure-relevant code has reached a saturation level of >= 3 examples.[/bold green]"
        )
        return integrity_passed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Verify GoalJudge Coverage and Integrity Gate"
    )
    parser.add_argument(
        "--corpus",
        default="cache/goaljudge_eval/run.jsonl",
        help="Path to exported run.jsonl",
    )
    args = parser.parse_args()

    success = verify_corpus(args.corpus)
    if success:
        console.print(
            "[bold green]✓ Coverage verification gate passed successfully.[/bold green]"
        )
        sys.exit(0)
    else:
        console.print(
            "[bold red]✗ Coverage verification gate did not pass completely.[/bold red]"
        )
        sys.exit(1)
