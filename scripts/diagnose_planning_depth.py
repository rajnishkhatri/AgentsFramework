"""Read-only diagnostic: are recent runs being mis-planned?

Pulls recent traces from Langfuse, reads the planning_depth + routing_reason
that fired (carried on the eval.goal_judge observation's input, alongside the
task_input — see orchestration/react_loop.py:1640), and flags rows where the
DETERMINISTIC heuristic (components.router.select_planning_depth) looks like it
under- or mis-scored the task.

It does NOT mutate anything. It re-runs the heuristic locally on each captured
task_input so you can see the exact (depth, reason) and compare to a re-score —
catching the "single strong marker capped at L0" and "post-tool-synthesis on a
fresh multi-part task" failure modes.

Reuses the repo's tested Langfuse helpers; no hand-rolled API surface.

    python scripts/diagnose_planning_depth.py --hours 6
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from components.router import select_planning_depth
from scripts.export_goaljudge_corpus import (
    fetch_trace_observations,
    list_recent_trace_ids,
)


def _planning_input(trace_id: str) -> dict | None:
    """Return the gj_ai_input dict that carries planning_depth, or None."""
    for obs in fetch_trace_observations(trace_id):
        name = obs.get("name") if isinstance(obs, dict) else getattr(obs, "name", "")
        if name not in ("eval.goal_judge", "eval_capture.goal_judge"):
            continue
        inp = obs.get("input") if isinstance(obs, dict) else getattr(obs, "input", None)
        if isinstance(inp, dict):
            return inp
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=6)
    ap.add_argument(
        "--all", action="store_true", help="print every trace's depth, not just flagged"
    )
    args = ap.parse_args()

    trace_ids = list_recent_trace_ids(hours=args.hours)
    print(f"# scanned {len(trace_ids)} traces over last {args.hours}h\n")

    suspects = []
    seen = 0
    for tid in trace_ids:
        inp = _planning_input(tid)
        if not inp:
            continue
        seen += 1
        task = inp.get("task_input") or ""
        fired_depth = inp.get("planning_depth", "?")
        fired_reason = inp.get("routing_reason", "")

        # Re-score with a FRESH-task assumption (count=0). A divergence between
        # this and what fired means the live count short-circuited planning.
        rescored, rescore_reason = select_planning_depth(
            task_input=task, task_tool_results_count=0
        )

        flag = ""
        # Miss A: post-tool-synthesis on a task that, scored fresh, wanted >L0.
        if "post-tool-synthesis" in str(fired_reason) and rescored != "L0":
            flag = f"SHORT-CIRCUIT: fired L0 but fresh-score is {rescored}"
        # Miss B: fired simple, but the prompt is long / multi-line.
        elif fired_depth == "L0" and (len(task.split()) >= 25 or task.count("\n") >= 2):
            flag = "UNDER-PLANNED: L0 on a long/multi-line prompt"
        # Miss C: a strong marker present but still capped at L0.
        elif fired_depth == "L0" and any(
            m in task.lower()
            for m in (
                "refactor",
                "migration",
                "architecture",
                "design",
                "compare",
                "roadmap",
            )
        ):
            flag = "MARKER-CAPPED: strong complexity marker but L0"

        if args.all:
            print(
                f"{fired_depth:3} ({fired_reason:32}) {tid[:12]}  ::  {task[:70].strip()!r}"
            )

        if flag:
            suspects.append((tid, fired_depth, fired_reason, rescored, flag, task))

    print(f"\n# {seen}/{len(trace_ids)} traces carried a planning label\n")

    if not suspects:
        print("No planning-depth misses flagged. Heuristic agreed with prompt shape.")
        return

    print(f"## {len(suspects)} suspected planning misses:\n")
    for tid, depth, reason, rescored, flag, task in suspects:
        print(f"- trace {tid}")
        print(f"    fired: {depth} ({reason})  | fresh-rescore: {rescored}")
        print(f"    >>> {flag}")
        print(f"    task: {task[:120].strip()!r}\n")


if __name__ == "__main__":
    main()
