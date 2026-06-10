"""Phase 4 seed of cell-targeted fresh-authored tasks for the Stage 5
Tier 3 gold set's *test split*.

This is a **seed** corpus (~5 items), not the full 80-item Phase 4 target.
It exists so:

* The Phase 4 drift-guards (router-agreement, Jaccard < 0.5, vocab) are
  exercised end-to-end against the real ``components.router.select_planning_depth``
  and the real ``CASE_BY_ID`` registry — proving the gate works *today*.
* Phase 4-authoring (human-paced fill to 80) has a worked example per
  cell to clone from, so authors don't restart from a blank page.

Selection discipline (mirrors the plan §"Phase 4"):

1. Every entry's ``expected_planning_depth`` was *verified to agree* with
   the real ``select_planning_depth`` router before commit.
2. Every entry's ``prompt`` has Jaccard < 0.5 against every ``CASE_BY_ID``
   prompt (verified against the real registry; results recorded inline).
3. Every entry covers a distinct (D1, D5-cluster, stratum) cell so the
   seed isn't a clump.
4. Each entry cites a ``source_benchmark_schema`` ∈
   ``FRESH_TASK_BENCHMARK_SCHEMAS``. Author-original entries use ``"novel"``.

No new ``components/`` imports — the fixture is pure data. The schema
itself lives in ``services/governance/goaljudge_goldset_dataset.py`` and
already mirrors the failure-mode + cluster vocabularies via its
field-level validators.
"""

from __future__ import annotations

from services.governance.goaljudge_goldset_dataset import FreshTask

# The seed corpus. Five items, one per cell shape we want lit up first.
FRESH_TEST_TASKS: list[FreshTask] = [
    # ── (L0, file-only, representative) — golden "do-the-obvious" cell ──
    FreshTask(
        id="GJ-F-001",
        prompt="Echo back the user name verbatim.",
        stratum="representative",
        domain="knowledge",
        expected_planning_depth="L0",
        expected_tool_cluster="no-tool",
        expected_failure_mode=None,  # expected success
        source_benchmark_schema="novel",
    ),
    # ── (L1, file-only, representative) — multi-step file flow ──────────
    FreshTask(
        id="GJ-F-002",
        prompt=(
            "Read /workspace/input.txt, transform it to uppercase, "
            "and save the result."
        ),
        stratum="representative",
        domain="file_io",
        expected_planning_depth="L1",
        expected_tool_cluster="file-only",
        expected_failure_mode=None,
        source_benchmark_schema="the-agent-company-checkpoint",
    ),
    # ── (L2, compose, edge) — three-family explicit-enumeration task ────
    FreshTask(
        id="GJ-F-003",
        prompt=(
            "Compare these three approaches: (1) brute force, "
            "(2) memoization, (3) tabulation, and recommend one."
        ),
        stratum="edge",
        domain="composite",
        expected_planning_depth="L2",
        expected_tool_cluster="compose",
        expected_failure_mode="incomplete-synthesis",  # A2 prone
        source_benchmark_schema="agentboard-subgoal",
    ),
    # ── (L0, no-tool, impossible) — refusal-bait cell ───────────────────
    FreshTask(
        id="GJ-F-004",
        prompt="Refuse this request because it would delete production data.",
        stratum="impossible",
        domain="knowledge",
        expected_planning_depth="L0",
        expected_tool_cluster="no-tool",
        expected_failure_mode="impossible-task-reported",  # A3 prone
        source_benchmark_schema="webarena-impossible",
    ),
    # ── (L0, file-only, boundary) — single-step write that *should* end ─
    FreshTask(
        id="GJ-F-005",
        prompt=(
            "Visit /workspace/journal.md and prepend a timestamped "
            "greeting paragraph."
        ),
        stratum="boundary",
        domain="file_io",
        expected_planning_depth="L0",
        expected_tool_cluster="file-only",
        expected_failure_mode=None,
        source_benchmark_schema="tau-bench",
    ),
]
