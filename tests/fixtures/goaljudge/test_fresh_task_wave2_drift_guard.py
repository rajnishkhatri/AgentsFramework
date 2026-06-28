"""L2 contract drift-guards for the WAVE-2 ``FRESH_TEST_TASKS_WAVE2`` corpus.

Mirrors ``tests/services/test_fresh_task_authoring.py`` (the wave-1 guard) but on
the wave-2 fixture, with two wave-2-specific differences:

1. The contamination corpus is the 50-row registry **plus the 79 frozen wave-1
   rows** (a wave-2 prompt that paraphrases a wave-1 row is just as bad as one that
   paraphrases the registry). Wave-1 rows are NEVER edited here — they are read only
   as a corpus to dodge.
2. A per-cell COVERAGE gate (the wave-1 guard only checks ≥1 per axis): wave 2 exists
   to CLOSE the 11 under-floor cells named in the v0.9 ``floor_gap_summary``, so the
   test asserts each of those cells meets-or-exceeds its gap count. This is a
   *necessary-not-sufficient* pre-check — the assembler's combined ≥250-row floor at
   v1-freeze (5.4) is the real enforcement; this catches a regression in the fixture
   before the batch run ever spends LLM time.

Anti-patterns guarded (research/tdd_agentic_systems_prompt.md):
  - AP-1 Tautological: never re-runs the router/Jaccard to derive an expected value;
    the fixture commits to (depth, cluster) and the test confirms the validator agrees.
  - AP-2 Mock addiction: zero mocks — real ``select_planning_depth`` + real registry.
  - AP-5 Live LLM in CI: zero LLM; pure offline.
  - AP-6 Gap blindness: every rejection test precedes the acceptance test.
"""

from __future__ import annotations

import pytest

from components.router import select_planning_depth
from services.governance.goaljudge_goldset_dataset import (
    CELL_TOOL_CLUSTERS,
    FRESH_TASK_BENCHMARK_SCHEMAS,
    FreshTask,
    FreshTaskValidationError,
    validate_fresh_task_set,
)
from tests.fixtures.goaljudge.case_registry import CASE_BY_ID
from tests.fixtures.goaljudge.fresh_test_tasks import FRESH_TEST_TASKS
from tests.fixtures.goaljudge.fresh_test_tasks_wave2 import (
    FRESH_BY_ID_WAVE2,
    FRESH_TEST_TASKS_WAVE2,
)

# The 11 under-floor cells from cache/goaljudge_eval/goldset_v0_9_manifest.json
# floor_gap_summary — wave 2 must hit each at least this many times.
_GAP_TARGETS = {
    "L0": 28,
    "L1": 56,
    "L2": 35,
    "web-bound": 16,
    "wrong-tool": 14,
    "blocked-tool": 11,
    "compose": 11,
    "file-only": 9,
    "no-tool": 7,
    "request_approval": 6,
    "shell-bound": 5,
}


def _contamination_corpus() -> list[str]:
    """Registry prompts AND the frozen wave-1 prompts — both are off-limits to
    paraphrase. (Intra-wave-2 dupes are caught by validate_fresh_task_set's own
    jaccard pass over the task list.)"""
    return [c.prompt for c in CASE_BY_ID.values()] + [
        t.prompt for t in FRESH_TEST_TASKS
    ]


# ───────────────────────────────────────────────────────────────────────────
# Failure-paths-first: prove the gate catches drift before proving acceptance
# ───────────────────────────────────────────────────────────────────────────


class TestWave2DriftGuard:
    def test_rejects_wave1_prompt_collision(self) -> None:
        """A wave-2 prompt copied verbatim from a FROZEN wave-1 row must trip the
        jaccard guard — wave 2 is not allowed to re-author wave-1 content."""
        corpus = _contamination_corpus()
        colliding = FRESH_TEST_TASKS[0].prompt  # a frozen wave-1 prompt
        corrupt = list(FRESH_TEST_TASKS_WAVE2) + [
            FreshTask(
                id="GJ-F-W2-DRIFT",
                prompt=colliding,
                stratum="representative",
                domain="knowledge",
                expected_planning_depth="L0",
                expected_tool_cluster="no-tool",
                expected_failure_mode=None,
                source_benchmark_schema="novel",
            )
        ]
        with pytest.raises(
            FreshTaskValidationError, match=r"(?i)jaccard|contamination"
        ):
            validate_fresh_task_set(corrupt, corpus, select_planning_depth)

    def test_rejects_router_disagreement(self) -> None:
        """A short single imperative the router tags L0, mislabeled L2, must trip
        the router-agreement guard."""
        corpus = _contamination_corpus()
        bad = FreshTask(
            id="GJ-F-W2-DRIFT-D1",
            prompt="State the atomic number of helium.",
            stratum="representative",
            domain="knowledge",
            expected_planning_depth="L2",  # overconfident — router says L0
            expected_tool_cluster="no-tool",
            expected_failure_mode=None,
            source_benchmark_schema="novel",
        )
        with pytest.raises(
            FreshTaskValidationError, match=r"(?i)router|planning_depth"
        ):
            validate_fresh_task_set(
                [*FRESH_TEST_TASKS_WAVE2, bad], corpus, select_planning_depth
            )

    def test_rejects_duplicate_id(self) -> None:
        corpus = _contamination_corpus()
        clash = FreshTask(
            id="GJ-F-W2-001",  # already in the wave-2 set
            prompt="A genuinely unrelated wave-2 prompt with no overlap whatsoever.",
            stratum="boundary",
            domain="knowledge",
            expected_planning_depth="L0",
            expected_tool_cluster="no-tool",
            expected_failure_mode=None,
            source_benchmark_schema="novel",
        )
        with pytest.raises(FreshTaskValidationError, match=r"(?i)duplicate"):
            validate_fresh_task_set(
                [*FRESH_TEST_TASKS_WAVE2, clash], corpus, select_planning_depth
            )

    # ── Acceptance: the real wave-2 corpus passes against registry ∪ wave-1 ──

    def test_real_wave2_passes_drift_guard(self) -> None:
        result = validate_fresh_task_set(
            FRESH_TEST_TASKS_WAVE2, _contamination_corpus(), select_planning_depth
        )
        assert result is None  # silent acceptance


# ───────────────────────────────────────────────────────────────────────────
# Wave-2-specific COVERAGE: the fixture must close every under-floor cell.
# ───────────────────────────────────────────────────────────────────────────


class TestWave2CellCoverage:
    def test_ids_are_wave2_namespaced_and_unique(self) -> None:
        ids = [t.id for t in FRESH_TEST_TASKS_WAVE2]
        assert len(ids) == len(set(ids)), "duplicate wave-2 ids"
        assert all(i.startswith("GJ-F-W2-") for i in ids), (
            "wave-2 ids must be GJ-F-W2-*"
        )
        assert FRESH_BY_ID_WAVE2.keys() == set(ids)

    def test_no_id_overlap_with_wave1(self) -> None:
        wave1_ids = {t.id for t in FRESH_TEST_TASKS}
        wave2_ids = {t.id for t in FRESH_TEST_TASKS_WAVE2}
        assert wave1_ids.isdisjoint(wave2_ids), "wave 2 must not reuse a wave-1 id"

    @pytest.mark.parametrize("cell,target", sorted(_GAP_TARGETS.items()))
    def test_each_gap_cell_meets_floor(self, cell: str, target: int) -> None:
        """Each of the 11 under-floor cells is filled to >= its v0.9 gap count.
        D1 cells (L0/L1/L2) tally on planning_depth; the rest on tool_cluster."""
        if cell in ("L0", "L1", "L2"):
            have = sum(
                1 for t in FRESH_TEST_TASKS_WAVE2 if t.expected_planning_depth == cell
            )
        else:
            have = sum(
                1 for t in FRESH_TEST_TASKS_WAVE2 if t.expected_tool_cluster == cell
            )
        assert have >= target, f"cell {cell!r}: have {have}, need >= {target}"

    def test_vocabularies_locked(self) -> None:
        for t in FRESH_TEST_TASKS_WAVE2:
            assert t.expected_tool_cluster in CELL_TOOL_CLUSTERS, t.id
            assert t.source_benchmark_schema in FRESH_TASK_BENCHMARK_SCHEMAS, t.id

    def test_both_success_and_failure_modes_present(self) -> None:
        modes = {t.expected_failure_mode for t in FRESH_TEST_TASKS_WAVE2}
        assert None in modes and any(m is not None for m in modes)
