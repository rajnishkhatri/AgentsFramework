"""Build the multi-surface deterministic planning-floor stress corpus.

Authors a coverage-matrix-driven synthetic corpus (~40-60 rows) that stresses
ALL FIVE deterministic floor surfaces, not just depth selection:

  1. select_planning_depth        -> want_depth (+ task_tool_results_count scoping)
  2. _extract_branches            -> want_branch_count / want_branches
  3. derive_success_conditions    -> want_min_conditions / want_generic_tail
  4. validate_plan_mece           -> want_mece_valid / want_mece_issue
  5. plan_is_stale (replan gate)   -> want_stale (+ last_tool_result fixture)

Each row carries ONLY the want_* fields relevant to the surface(s) it probes;
the scorer (scripts/diagnose_planning_floor.py) runs a surface only when its
want_* is present. The 11 rows of the existing depth oracle
(cache/goaljudge_eval/depth_strata_rich.jsonl) are imported verbatim as a
DEPTH subset so depth regression is preserved and never re-tuned away.

Ground-truth discipline: want_* values are authored from INTENT (what a task
SHOULD yield), independent of current code. The scorer records got_* beside
them; divergences become recorded baseline MISSES, not silent matches.

    python scripts/build_planning_floor_corpus.py            # writes the JSONL
    python scripts/build_planning_floor_corpus.py --stdout   # print, don't write

Output: cache/goaljudge_eval/planning_floor_strata.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_ORACLE = Path("cache/goaljudge_eval/depth_strata_rich.jsonl")
_OUT = Path("cache/goaljudge_eval/planning_floor_strata.jsonl")


def _row(
    rid: str,
    family: str,
    surface: str,
    task_input: str,
    *,
    note: str,
    task_tool_results_count: int = 0,
    last_tool_result: dict | None = None,
    want_depth: str | None = None,
    want_branch_count: int | None = None,
    want_branches: list[str] | None = None,
    want_min_conditions: int | None = None,
    want_generic_tail: bool | None = None,
    want_mece_valid: bool | None = None,
    want_mece_issue: str | None = None,
    want_stale: bool | None = None,
    mece_plan: dict | None = None,
) -> dict[str, Any]:
    """One corpus row. Only non-None want_* fields are scored."""
    row: dict[str, Any] = {
        "id": rid,
        "family": family,
        "surface": surface,
        "task_input": task_input,
        "task_tool_results_count": task_tool_results_count,
        "last_tool_result": last_tool_result,
        "want_depth": want_depth,
        "want_branch_count": want_branch_count,
        "want_branches": want_branches,
        "want_min_conditions": want_min_conditions,
        "want_generic_tail": want_generic_tail,
        "want_mece_valid": want_mece_valid,
        "want_mece_issue": want_mece_issue,
        "want_stale": want_stale,
        "mece_plan": mece_plan,
        "note": note,
    }
    return row


# ─────────────────────────────────────────────────────────────────────────────
# SURFACE 1 — depth selection (fresh synthetic rows; oracle rows merged later)
# ─────────────────────────────────────────────────────────────────────────────
def depth_rows() -> list[dict]:
    return [
        # L0 — genuinely single actions
        _row("depth-l0-1", "single-action", "depth",
             "Print the current working directory.",
             want_depth="L0", note="bare single action"),
        _row("depth-l0-2", "single-action", "depth",
             "Delete the file temp.log.",
             want_depth="L0", note="single mutation, short"),
        # L0 TRAP — long absolute path, single create: long-task-floor must NOT
        # over-promote (gate is word_count>=25, and a path is one token).
        _row("depth-l0-trap-1", "long-path-l0", "depth",
             "Create the file /var/lib/app/data/cache/segments/region-eu-west-1/shard-0007/index.meta.json",
             want_depth="L0", note="TRAP: long path, single create -> stays L0 (not long-task-floor)"),
        _row("depth-l0-trap-2", "long-path-l0", "depth",
             "Write OK to /opt/services/payments/config/feature-flags/rollout/canary/state.txt",
             want_depth="L0", note="TRAP: long path single write -> L0"),

        # L1 — lone strong-intent verbs
        _row("depth-l1-1", "lone-marker:investigate", "depth",
             "Investigate the latency regression.",
             want_depth="L1", note="strong-intent verb floor"),
        _row("depth-l1-2", "lone-marker:audit", "depth",
             "Audit the dependency tree.",
             want_depth="L1", note="strong-intent verb floor"),
        # L1 — sequenced two-step
        _row("depth-l1-3", "sequenced", "depth",
             "Build the index and then verify it loads.",
             want_depth="L1", note="and-then sequencing -> L1"),
        # L1 — moderate length explanatory
        _row("depth-l1-4", "moderate-length", "depth",
             ("Explain what happens to in-flight requests when the load balancer "
              "drains a backend, how connection draining interacts with keep-alive "
              "sockets, and what a client observes during the drain window."),
             want_depth="L1", note=">=25 words, no stacked markers -> L1"),

        # L2 — stacked markers + enumeration + conjunction
        _row("depth-l2-1", "marker+enum+conj", "depth",
             ("Compare Kafka and RabbitMQ for our event bus, (1) measure throughput "
              "(2) test ordering guarantees (3) assess operational cost, and then "
              "recommend one with a migration outline."),
             want_depth="L2", note="3 stacked signals -> high-complexity"),
        # L2 — incident narrative, lexically bare
        _row("depth-l2-2", "incident-narrative", "depth",
             ("Orders intermittently vanish from the dashboard after a successful "
              "checkout; trace how the order event propagates from the writer to "
              "the projection and identify every consumer that could drop it."),
             want_depth="L2", note="incident markers + length -> L2"),

        # L2 TRAP — multi-marker prose that the additive scorer caps at L1.
        # This is the KNOWN live miss; seed several variants to measure how
        # systematic the under-promotion is.
        _row("depth-l2-trap-1", "l2-under-promote", "depth",
             ("Audit the current deployment architecture, design a migration to the "
              "new region, refactor the routing layer to support it, and produce a "
              "staged rollout roadmap with rollback criteria for each phase."),
             want_depth="L2", note="TRAP: multi-marker prose, intended L2 (known L2->L1 miss)"),
        _row("depth-l2-trap-2", "l2-under-promote", "depth",
             ("Redesign the ingestion pipeline, migrate the existing jobs onto it, "
              "and refactor the downstream consumers so nothing breaks during cutover."),
             want_depth="L2", note="TRAP: redesign+migrate+refactor prose -> intended L2"),
        _row("depth-l2-trap-3", "l2-under-promote", "depth",
             ("Investigate the recurring OOM, design a memory-budget guard, and "
              "refactor the hot allocation path to stay under it across all tiers."),
             want_depth="L2", note="TRAP: investigate+design+refactor prose -> intended L2"),
        _row("depth-l2-trap-4", "l2-under-promote", "depth",
             ("Architect a multi-region failover story, design the data replication, "
              "and migrate the control plane without downtime."),
             want_depth="L2", note="TRAP: architecture+design+migrate prose -> intended L2"),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# SURFACE 5 — count-scoping (paired count=0 / count>0) — GJ-012
# Same prompt twice: fresh resolves to its real depth; post-tool MUST be L0.
# ─────────────────────────────────────────────────────────────────────────────
def count_scope_rows() -> list[dict]:
    pairs = [
        ("Compare Kafka and RabbitMQ for our event bus, (1) measure throughput "
         "(2) test ordering (3) assess cost, and then recommend one.", "L2"),
        ("Investigate the latency regression.", "L1"),
        ("Build the index and then verify it loads.", "L1"),
    ]
    rows: list[dict] = []
    for i, (prompt, fresh_depth) in enumerate(pairs, 1):
        rows.append(_row(
            f"count-fresh-{i}", "count-scope:fresh", "depth", prompt,
            task_tool_results_count=0, want_depth=fresh_depth,
            note=f"count=0 -> real depth {fresh_depth} (proves no leak from short-circuit)",
        ))
        rows.append(_row(
            f"count-posttool-{i}", "count-scope:post-tool", "depth", prompt,
            task_tool_results_count=2, want_depth="L0",
            note="count>0 -> MUST be L0 post-tool-synthesis (GJ-012 short-circuit)",
        ))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# SURFACE 2 — branch extraction (_extract_branches)
# ─────────────────────────────────────────────────────────────────────────────
def branch_rows() -> list[dict]:
    return [
        # newline / bullet list
        _row("branch-lines-1", "split:newline", "branches",
             "Set up the database\nSeed the fixtures\nRun the smoke test",
             want_branch_count=3, note="3 newline chunks"),
        _row("branch-bullets-1", "split:bullets", "branches",
             "- provision the bucket\n- set the lifecycle policy\n- enable versioning",
             want_branch_count=3, note="3 bullet markers stripped"),
        # inline enumeration
        # lead-in clause + enumeration: the lead-in ("Do the rollout in order:")
        # is itself a branch, so 3 enumerated items -> 4 branches total. (Authored
        # want corrected from 3->4 on review: the extractor is right; keeping a
        # pure-enum probe separate below.)
        _row("branch-enum-1", "split:enum", "branches",
             "Do the rollout in order: (1) drain traffic (2) deploy (3) re-enable traffic",
             want_branch_count=4, note="lead-in clause + (1)(2)(3) -> 4 branches"),
        # pure enumeration with no lead-in -> exactly 3
        _row("branch-enum-2", "split:enum", "branches",
             "(1) drain traffic (2) deploy the build (3) re-enable traffic",
             want_branch_count=3, note="pure (1)(2)(3) enumeration, no lead-in -> 3"),
        # comma + terminal ", and" imperative clauses (X, Y, and Z)
        _row("branch-comma-and-1", "split:comma-and", "branches",
             "Back up the volume, snapshot the metadata, and detach the disk.",
             want_branch_count=3, note="X, Y, and Z imperative -> 3 (comma-then-and)"),
        # ", then" sequencing
        _row("branch-then-1", "split:then", "branches",
             "Compile the assets, then upload them to the CDN.",
             want_branch_count=2, note=", then -> 2 imperative clauses"),
        # single action -> single branch
        _row("branch-single-1", "split:single", "branches",
             "Restart the worker pool.",
             want_branch_count=1, note="single action -> 1 branch"),

        # TRAP — path-safety: periods inside paths/versions must NOT split.
        _row("branch-trap-path-1", "split-trap:path-safe", "branches",
             "Open /workspace/f3.txt and read it.",
             want_branch_count=1, note="TRAP: /workspace/f3.txt must not sentence-split"),
        _row("branch-trap-version-1", "split-trap:path-safe", "branches",
             "Pin the dependency to v1.2.3 in the lockfile.",
             want_branch_count=1, note="TRAP: v1.2.3 must not sentence-split"),

        # TRAP — noun-phrase "and" must NOT split (no leading comma, not imperative)
        _row("branch-trap-nounphrase-1", "split-trap:noun-phrase", "branches",
             "Summarize the trade-offs and risks of the new design.",
             want_branch_count=1, note="TRAP: 'trade-offs and risks' is a noun phrase, 1 branch"),
        _row("branch-trap-nounphrase-2", "split-trap:noun-phrase", "branches",
             "Document the costs and benefits of the migration.",
             want_branch_count=1, note="TRAP: 'costs and benefits' noun phrase -> 1 branch"),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# SURFACE 3 — success conditions (derive_success_conditions)
# Conditions = one per branch (capped 6) + ALWAYS a generic tail.
# So want_min_conditions counts the tail too.
# ─────────────────────────────────────────────────────────────────────────────
def condition_rows() -> list[dict]:
    return [
        _row("cond-single-1", "cond:single", "conditions",
             "Restart the worker pool.",
             want_min_conditions=2, want_generic_tail=True,
             note="1 branch -> 1 condition + generic tail = 2"),
        _row("cond-three-1", "cond:multi", "conditions",
             "Back up the volume, snapshot the metadata, and detach the disk.",
             want_min_conditions=4, want_generic_tail=True,
             note="3 branches -> 3 conditions + tail = 4"),
        # >6 branches -> capped at 6 + tail = 7 total
        _row("cond-cap-1", "cond:cap", "conditions",
             ("Do these in order: (1) alpha (2) bravo (3) charlie (4) delta "
              "(5) echo (6) foxtrot (7) golf (8) hotel"),
             want_min_conditions=7, want_generic_tail=True,
             note="8 branches -> capped 6 conditions + tail = 7 (cap holds)"),
        # duplicate branches -> deduped (still tail present)
        _row("cond-dedup-1", "cond:dedup", "conditions",
             "Restart the worker pool\nRestart the worker pool\nRestart the worker pool",
             want_min_conditions=2, want_generic_tail=True,
             note="duplicate branches dedup to 1 condition + tail = 2"),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# SURFACE 4 — MECE structure gate (validate_plan_mece)
# These rows carry a hand-built mece_plan (PlanArtifact dict) rather than a
# task_input, since we are probing the validator on malformed structures.
# ─────────────────────────────────────────────────────────────────────────────
def mece_rows() -> list[dict]:
    return [
        _row("mece-valid-1", "mece:valid", "mece", "",
             mece_plan={
                 "ordered_steps": [
                     {"step_id": 1, "title": "a", "goal": "provision the bucket"},
                     {"step_id": 2, "title": "b", "goal": "set lifecycle policy"},
                 ],
                 "constraints": [],
                 "success_conditions": ["bucket exists", "policy set"],
             },
             want_mece_valid=True, note="contiguous ids, distinct goals, non-empty conds -> valid"),
        _row("mece-dupgoal-1", "mece:dup-goal", "mece", "",
             mece_plan={
                 "ordered_steps": [
                     {"step_id": 1, "title": "a", "goal": "deploy the service"},
                     {"step_id": 2, "title": "b", "goal": "deploy the service"},
                 ],
                 "constraints": [],
                 "success_conditions": ["deployed"],
             },
             want_mece_valid=False, want_mece_issue="overlapping goals",
             note="duplicate goals -> not MECE"),
        _row("mece-noncontig-1", "mece:non-contiguous", "mece", "",
             mece_plan={
                 "ordered_steps": [
                     {"step_id": 1, "title": "a", "goal": "step one"},
                     {"step_id": 3, "title": "b", "goal": "step two"},
                 ],
                 "constraints": [],
                 "success_conditions": ["done"],
             },
             want_mece_valid=False, want_mece_issue="contiguous step_id",
             note="step ids 1,3 not contiguous -> invalid"),
        _row("mece-emptygoal-1", "mece:empty-goal", "mece", "",
             mece_plan={
                 "ordered_steps": [
                     {"step_id": 1, "title": "a", "goal": "real goal"},
                     {"step_id": 2, "title": "b", "goal": "   "},
                 ],
                 "constraints": [],
                 "success_conditions": ["done"],
             },
             want_mece_valid=False, want_mece_issue="non-empty goal",
             note="blank goal -> invalid"),
        _row("mece-noconds-1", "mece:no-conditions", "mece", "",
             mece_plan={
                 "ordered_steps": [
                     {"step_id": 1, "title": "a", "goal": "only goal"},
                 ],
                 "constraints": [],
                 "success_conditions": [],
             },
             want_mece_valid=False, want_mece_issue="success_conditions",
             note="empty success_conditions -> invalid"),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# SURFACE 5b — replan gate (plan_is_stale). Coverage only (genuine stale vs
# genuine fresh); no adversarial near-miss traps per scope decision.
# Each row carries a non-empty plan implicitly (the scorer builds one) and a
# last_tool_result fixture.
# ─────────────────────────────────────────────────────────────────────────────
def replan_rows() -> list[dict]:
    base = "Build the index and then verify it loads."
    return [
        _row("replan-ok-fail", "replan:ok-false", "replan", base,
             last_tool_result={"ok": False, "tool_name": "shell", "output": ""},
             want_stale=True, note="ok=False -> stale"),
        _row("replan-error", "replan:error", "replan", base,
             last_tool_result={"ok": True, "error": "permission denied", "tool_name": "file_io"},
             want_stale=True, note="non-empty error -> stale"),
        _row("replan-outcome-failed", "replan:outcome", "replan", base,
             last_tool_result={"outcome": "failed", "tool_name": "http"},
             want_stale=True, note="outcome=failed -> stale"),
        _row("replan-surprising", "replan:surprising", "replan", base,
             last_tool_result={"ok": True, "surprising": True, "tool_name": "shell"},
             want_stale=True, note="surprising flag -> stale"),
        _row("replan-replan-flag", "replan:replan-flag", "replan", base,
             last_tool_result={"ok": True, "replan": True, "tool_name": "shell"},
             want_stale=True, note="replan flag -> stale"),
        _row("replan-clean", "replan:clean", "replan", base,
             last_tool_result={"ok": True, "output": "index built", "tool_name": "shell"},
             want_stale=False, note="clean success -> NOT stale (continues to evaluate)"),
        _row("replan-clean-2", "replan:clean", "replan", base,
             last_tool_result={"ok": True, "outcome": "success", "output": "ok", "tool_name": "file_io"},
             want_stale=False, note="explicit success outcome -> NOT stale"),
        _row("replan-none", "replan:none", "replan", base,
             last_tool_result=None,
             want_stale=False, note="no tool result -> NOT stale (nothing to invalidate)"),
    ]


def oracle_subset() -> list[dict]:
    """Import the 11 depth-oracle rows verbatim as a DEPTH subset.

    Only prompt + want_depth + trigger_family are carried. The oracle's
    ``fired_depth`` is the STALE pre-Phase-0 capture and is deliberately NOT
    trusted — the scorer re-runs the current select_planning_depth fresh.
    """
    rows: list[dict] = []
    if not _ORACLE.exists():
        return rows
    for i, line in enumerate(_ORACLE.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        rows.append(_row(
            f"oracle-{i}", f"oracle:{d.get('trigger_family', 'unknown')}", "depth",
            d["prompt"], want_depth=d["want_depth"],
            note="imported from depth_strata_rich.jsonl (depth regression guard)",
        ))
    return rows


def build() -> list[dict]:
    rows: list[dict] = []
    rows += depth_rows()
    rows += count_scope_rows()
    rows += branch_rows()
    rows += condition_rows()
    rows += mece_rows()
    rows += replan_rows()
    rows += oracle_subset()
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    args = ap.parse_args()

    rows = build()
    payload = "\n".join(json.dumps(r) for r in rows) + "\n"

    if args.stdout:
        print(payload, end="")
    else:
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(payload)
        # coverage summary by surface
        from collections import Counter
        by_surface = Counter(r["surface"] for r in rows)
        print(f"wrote {len(rows)} rows -> {_OUT}")
        for surface, n in sorted(by_surface.items()):
            print(f"  {surface:10} {n}")


if __name__ == "__main__":
    main()
