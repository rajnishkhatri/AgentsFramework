"""Multi-surface deterministic planning-floor diagnostic.

Reads cache/goaljudge_eval/planning_floor_strata.jsonl and, for each row, runs
ONLY the floor surfaces whose ``want_*`` field is present, against the REAL
components (no LLM, no network, no deploy). Surfaces:

  depth       select_planning_depth(task_input, task_tool_results_count)
  branches    _extract_branches(task_input)
  conditions  derive_success_conditions(_extract_branches(task_input))
  mece        validate_plan_mece(PlanArtifact(**mece_plan))
  replan      plan_is_stale(<built plan>, last_tool_result)

Records got_* beside want_* and prints a per-surface scorecard plus an explicit
DIVERGENCES section (every got != want row, with its note). Divergences are the
real baseline misses — they are surfaced, never silently matched. This makes
the run a baseline, not a snapshot.

Exit code is always 0 (manual diagnostic; not yet a CI gate). A ``--strict``
flag is provided so it CAN later become a pytest gate without code change.

    python scripts/diagnose_planning_floor.py
    python scripts/diagnose_planning_floor.py --strict   # exit 1 if any divergence
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from components.plan_builder import (
    PlanArtifact,
    _extract_branches,
    derive_success_conditions,
    plan_is_stale,
    validate_plan_mece,
)
from components.router import select_planning_depth

_CORPUS = Path("cache/goaljudge_eval/planning_floor_strata.jsonl")

_SURFACES = ("depth", "branches", "conditions", "mece", "replan")


def _score_row(row: dict) -> list[dict]:
    """Run every assertable surface on one row. Returns a list of results."""
    results: list[dict] = []
    task_input = row.get("task_input", "")

    # ── depth ────────────────────────────────────────────────────────────
    if row.get("want_depth") is not None:
        got, reason = select_planning_depth(
            task_input=task_input,
            task_tool_results_count=int(row.get("task_tool_results_count") or 0),
        )
        results.append({
            "surface": "depth", "want": row["want_depth"], "got": got,
            "ok": got == row["want_depth"], "detail": reason,
        })

    # ── branches ─────────────────────────────────────────────────────────
    if row.get("want_branch_count") is not None or row.get("want_branches") is not None:
        branches = _extract_branches(task_input)
        if row.get("want_branches") is not None:
            want = row["want_branches"]
            ok = branches == want
            results.append({
                "surface": "branches", "want": want, "got": branches,
                "ok": ok, "detail": f"{len(branches)} branches",
            })
        else:
            want_n = int(row["want_branch_count"])
            ok = len(branches) == want_n
            results.append({
                "surface": "branches", "want": want_n, "got": len(branches),
                "ok": ok, "detail": " | ".join(branches)[:80],
            })

    # ── conditions ───────────────────────────────────────────────────────
    if row.get("want_min_conditions") is not None or row.get("want_generic_tail") is not None:
        branches = _extract_branches(task_input)
        conds = derive_success_conditions(branches)
        checks = []
        ok = True
        if row.get("want_min_conditions") is not None:
            want_n = int(row["want_min_conditions"])
            c_ok = len(conds) == want_n
            ok = ok and c_ok
            checks.append(f"count {len(conds)}=={want_n}:{c_ok}")
        if row.get("want_generic_tail") is not None:
            from components.plan_builder import _GENERIC_TAIL_CONDITION
            tail_ok = (_GENERIC_TAIL_CONDITION in conds) == bool(row["want_generic_tail"])
            ok = ok and tail_ok
            checks.append(f"tail:{tail_ok}")
        results.append({
            "surface": "conditions",
            "want": row.get("want_min_conditions"), "got": len(conds),
            "ok": ok, "detail": " ".join(checks),
        })

    # ── mece ─────────────────────────────────────────────────────────────
    if row.get("want_mece_valid") is not None:
        plan = PlanArtifact(**row["mece_plan"])
        res = validate_plan_mece(plan)
        valid_ok = res.is_valid == bool(row["want_mece_valid"])
        issue_ok = True
        if row.get("want_mece_issue"):
            issue_ok = any(row["want_mece_issue"] in i for i in res.issues)
        ok = valid_ok and issue_ok
        results.append({
            "surface": "mece",
            "want": row["want_mece_valid"], "got": res.is_valid,
            "ok": ok, "detail": "; ".join(res.issues)[:80] or "valid",
        })

    # ── replan ───────────────────────────────────────────────────────────
    if row.get("want_stale") is not None:
        # plan_is_stale needs a non-empty plan to do anything but the None/empty
        # short-circuit; build a minimal 2-step plan so the scalar checks run.
        plan = PlanArtifact(
            ordered_steps=[
                {"step_id": 1, "title": "a", "goal": "build"},
                {"step_id": 2, "title": "b", "goal": "verify"},
            ],
            success_conditions=["done"],
        )
        got = plan_is_stale(plan, row.get("last_tool_result"))
        ok = got == bool(row["want_stale"])
        results.append({
            "surface": "replan", "want": row["want_stale"], "got": got,
            "ok": ok, "detail": str(row.get("last_tool_result"))[:60],
        })

    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if any surface diverges (CI-gate mode)")
    args = ap.parse_args()

    rows = [json.loads(l) for l in _CORPUS.read_text().splitlines() if l.strip()]

    per_surface: dict[str, Counter] = {s: Counter() for s in _SURFACES}
    divergences: list[tuple[dict, dict]] = []

    for row in rows:
        for res in _score_row(row):
            s = res["surface"]
            per_surface[s]["total"] += 1
            if res["ok"]:
                per_surface[s]["ok"] += 1
            else:
                per_surface[s]["miss"] += 1
                divergences.append((row, res))

    print(f"# planning-floor multi-surface diagnostic — {len(rows)} corpus rows\n")
    print("## per-surface scorecard")
    grand_total = grand_ok = 0
    for s in _SURFACES:
        c = per_surface[s]
        total = c["total"]
        if not total:
            continue
        ok = c["ok"]
        grand_total += total
        grand_ok += ok
        pct = 100 * ok / total
        print(f"  {s:11} {ok:3}/{total:<3} ({pct:5.1f}%)")
    gpct = 100 * grand_ok / grand_total if grand_total else 0.0
    print(f"  {'OVERALL':11} {grand_ok:3}/{grand_total:<3} ({gpct:5.1f}%)")

    print(f"\n## DIVERGENCES ({len(divergences)})  — baseline misses, surfaced not hidden")
    if not divergences:
        print("  (none)")
    for row, res in divergences:
        print(f"  [{res['surface']}] {row['id']} ({row['family']})")
        print(f"        want={res['want']!r} got={res['got']!r}  — {res['detail']}")
        print(f"        note: {row['note']}")

    if args.strict and divergences:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
