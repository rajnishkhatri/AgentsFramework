"""Phase 0: synthetic planning-depth strata + offline scoring.

Authors a BALANCED set of prompts that deliberately span the L0/L1/L2 axis and
its known trigger families, then runs each through the REAL deterministic
heuristic (components.router.select_planning_depth, count=0 = fresh task) and
reports fired-vs-intended.

This is free and offline. It characterizes the heuristic's precision/recall on
a designed set — the evidence for whether the planning seam under-plans complex
tasks — before spending anything on a live T3 run.

    python scripts/diagnose_planning_strata.py
"""

from __future__ import annotations

from collections import Counter

from components.router import select_planning_depth

# (intended_depth, trigger_family, prompt)
# Triggers reference select_planning_depth's signals: word_count>=35/80,
# multi_part_markers, conjunctions, newlines>=2, '?'>=2, (1)(2) enumeration.
CASES: list[tuple[str, str, str]] = [
    # ---- L0: genuinely simple single actions ----
    (
        "L0",
        "single-action",
        "Read the first line of /workspace/notes.txt and print it.",
    ),
    ("L0", "single-action", "Echo the phrase quarterly review verbatim."),
    (
        "L0",
        "single-action",
        "Overwrite /workspace/status.txt with the single character OK.",
    ),
    # ---- L1: one moderate signal (SHOULD decompose a little) ----
    ("L1", "lone-marker:refactor", "Refactor the auth module."),
    ("L1", "lone-marker:design", "Design a rate limiter for the API."),
    ("L1", "lone-marker:migration", "Plan the Postgres migration."),
    (
        "L1",
        "moderate-length",
        (
            "Walk me through what the login endpoint does when a session cookie "
            "is present but expired, including how the refresh path is triggered "
            "and what the client sees if refresh fails."
        ),
    ),
    # ---- L2: stacked signals (SHOULD deeply decompose) ----
    (
        "L2",
        "marker+enum+conj",
        (
            "Compare Redis and Memcached for our cache, (1) benchmark read latency "
            "(2) measure memory overhead (3) test eviction, and then recommend one."
        ),
    ),
    (
        "L2",
        "multi-marker+long",
        (
            "Audit the current deployment architecture, design a migration to the "
            "new region, refactor the routing layer to support it, and produce a "
            "staged rollout roadmap with rollback criteria for each phase."
        ),
    ),
    # ---- ADVERSARIAL: semantically complex, lexically bare ----
    # No multi_part_marker keyword; complexity is in the meaning, not the words.
    (
        "L2",
        "adversarial:bare-complex",
        (
            "Our checkout sometimes double-charges customers when the payment "
            "provider times out but later confirms; figure out where the "
            "idempotency boundary should live and what state we need to track so a "
            "retried request is recognized as the same purchase."
        ),
    ),
    (
        "L2",
        "adversarial:bare-complex",
        (
            "Users report the feed shows stale posts after they publish; trace how "
            "a write propagates to the read path and identify every cache or "
            "replica that could be serving the old version."
        ),
    ),
    # ---- POST-TOOL: re-ask shape (only matters with count>0, here count=0) ----
    ("L1", "control:short-multipart", "Add caching and then update the docs."),
]


def main() -> None:
    rows = []
    confusion: Counter[tuple[str, str]] = Counter()
    for intended, family, prompt in CASES:
        fired, reason = select_planning_depth(
            task_input=prompt, task_tool_results_count=0
        )
        match = "ok " if fired == intended else "MISS"
        confusion[(intended, fired)] += 1
        rows.append((match, intended, fired, family, reason, prompt))

    print(f"# {len(CASES)} synthetic depth cases — fired vs intended\n")
    for match, intended, fired, family, reason, prompt in rows:
        print(f"[{match}] want {intended} got {fired}  {family:26} ({reason})")
        print(f"        {prompt[:88].strip()!r}")

    print("\n## confusion (intended -> fired)")
    for (intended, fired), n in sorted(confusion.items()):
        mark = "" if intended == fired else "   <-- miss"
        print(f"  {intended} -> {fired}: {n}{mark}")

    misses = sum(n for (i, f), n in confusion.items() if i != f)
    print(
        f"\n## {misses}/{len(CASES)} mis-scored "
        f"({100 * (len(CASES) - misses) / len(CASES):.0f}% agreement)"
    )


if __name__ == "__main__":
    main()
