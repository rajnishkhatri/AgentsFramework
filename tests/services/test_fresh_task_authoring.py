"""L2 contract drift-guards for the Phase 4 ``FRESH_TEST_TASKS`` corpus.

Pyramid layer:  L2 Reproducible (TDD Protocol B — Contract-Driven TDD)
Architecture:   ``tests/services/`` — drives the
                ``services.governance.validate_fresh_task_set`` gate
                against the *real* ``components.router.select_planning_depth``
                and the *real* ``tests.fixtures.goaljudge.case_registry``.

Why "L2 contract" not "L1 unit": the L1 file
``tests/services/test_goaljudge_goldset_dataset.py`` already pins the
validator's behavior on synthetic inputs via TDD Pattern 6 (Mock Provider —
the agreeing/disagreeing router stub). *This* file proves the gate works
against the real corpus the gold set will actually freeze, which is the
"reproducible reality" the Tier 3 gate cares about.

Anti-patterns guarded against (per ``research/tdd_agentic_systems_prompt.md``):

* AP-1 Tautological: the test never re-runs the router or the Jaccard
  algorithm to derive its own expected value. The fixture authors *commit*
  to a (depth, threshold) answer; the test only confirms the validator agrees.
* AP-2 Mock addiction: zero mocks. ``select_planning_depth`` is deterministic
  pure code; ``CASE_BY_ID`` is a constant. Both are imported directly.
* AP-5 Live LLM in CI: zero LLM. The whole drift-guard runs offline.
* AP-6 Gap blindness: every contract has a *rejection* test (corrupt the
  fixture in-memory, prove the validator catches it) authored BEFORE the
  acceptance test that the real fixture passes.
* AP-7 Cross-layer dependency leak: this test file lives in ``tests/services/``
  and imports from ``services.governance.*`` (its own layer), ``components.router``
  (lower layer — components/router is L3 vertical; this is permitted because
  ``services/`` is the L1/L2 horizontal layer and components is downstream of
  the *test* directory's allowed reach, mirroring the established pattern in
  ``scripts/build_goaljudge_stage5_full_sheet.py``), and ``tests/fixtures/`` (peer).
  No imports from ``orchestration/`` or ``governance/`` (meta).
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


def _registry_prompts() -> list[str]:
    """All registry prompts the contamination guard must dodge."""
    return [case.prompt for case in CASE_BY_ID.values()]


# ───────────────────────────────────────────────────────────────────────────
# Failure-paths-first: prove the gate catches drift before proving acceptance
# ───────────────────────────────────────────────────────────────────────────


class TestFreshTaskCorpusDriftGuard:
    """Failure-modes the validator MUST catch on the real fixture, then the
    end-to-end happy path. Per Protocol B (Contract-Driven TDD) + TDD
    §"Failure paths first": every rejection test is paired with the
    corresponding acceptance test below."""

    # ── Failure path 1: a fresh prompt that duplicates a registry case ──

    def test_rejects_corpus_with_registry_prompt_collision(self) -> None:
        """Inject a copy of an existing registry prompt; the validator
        must raise on the Jaccard guard. The point: the real registry
        is the comparison set, not a fixture; a future case_registry
        addition that paraphrases an existing FRESH_TEST_TASKS entry
        would trigger the same failure (drift caught early)."""
        # Pick any concrete registry case to ensure the test isn't
        # accidentally comparing against the fresh task itself.
        registry = _registry_prompts()
        colliding_prompt = registry[0]

        corrupt = list(FRESH_TEST_TASKS) + [
            FreshTask(
                id="GJ-F-DRIFT",
                prompt=colliding_prompt,
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
            validate_fresh_task_set(corrupt, registry, select_planning_depth)

    # ── Failure path 2: an author's D1 prediction disagreeing with router ─

    def test_rejects_corpus_with_router_disagreement(self) -> None:
        """Inject a task whose prompt the real router would tag L0 but
        the author claims L2 for. Catches the most common authoring
        mistake (overconfident depth prediction on a simple prompt)."""
        registry = _registry_prompts()
        # "Echo back …" is a confirmed L0 (see fresh_test_tasks.py header).
        # Forging expected_planning_depth=L2 must trip the router-agreement
        # guard.
        bad = FreshTask(
            id="GJ-F-DRIFT-D1",
            prompt="Echo back the user name verbatim.",
            stratum="representative",
            domain="knowledge",
            expected_planning_depth="L2",  # author overconfident
            expected_tool_cluster="no-tool",
            expected_failure_mode=None,
            source_benchmark_schema="novel",
        )
        corrupt = list(FRESH_TEST_TASKS) + [bad]
        with pytest.raises(
            FreshTaskValidationError, match=r"(?i)router|planning_depth"
        ):
            validate_fresh_task_set(corrupt, registry, select_planning_depth)

    # ── Failure path 3: duplicated id within the corpus ─────────────────

    def test_rejects_corpus_with_duplicate_ids(self) -> None:
        """Duplicate id ⇒ collision at Phase 6 freeze. The validator
        catches it before the freeze ever runs."""
        registry = _registry_prompts()
        # GJ-F-001 is already in FRESH_TEST_TASKS. Add a second with same id.
        clash = FreshTask(
            id="GJ-F-001",  # duplicate
            prompt="A genuinely different prompt with no overlap.",
            stratum="boundary",
            domain="knowledge",
            expected_planning_depth="L0",
            expected_tool_cluster="no-tool",
            expected_failure_mode=None,
            source_benchmark_schema="novel",
        )
        corrupt = list(FRESH_TEST_TASKS) + [clash]
        with pytest.raises(FreshTaskValidationError, match=r"(?i)duplicate"):
            validate_fresh_task_set(corrupt, registry, select_planning_depth)

    # ── Acceptance path: the real FRESH_TEST_TASKS corpus passes ────────

    def test_real_fresh_test_tasks_passes_drift_guard(self) -> None:
        """The end-to-end gate: every FRESH_TEST_TASKS entry survives
        the validator with the real registry and the real router. If a
        future author adds a task that fails this, CI catches it on the
        PR."""
        registry = _registry_prompts()
        result = validate_fresh_task_set(
            FRESH_TEST_TASKS, registry, select_planning_depth
        )
        # validate_fresh_task_set returns None on success (silent acceptance).
        assert result is None


# ───────────────────────────────────────────────────────────────────────────
# Cell-coverage drift-guards: the seed must hit ≥1 entry per cell axis
# (so the gap report has a worked example to read from when Phase 4
# authoring fills toward 80)
# ───────────────────────────────────────────────────────────────────────────


class TestFreshTaskCorpusCoverage:
    """Coverage drift-guards on the seed corpus. These are intentionally
    *minimal*: the seed isn't trying to meet Phase 4's per-cell floors
    (that's the human-paced authoring work), just to *light up at least
    one example per dimension* so authors have one of each shape to clone.

    Anti-Pattern 6 guard: every shape we claim the seed lights up has a
    test that proves it (no silent gap)."""

    def test_seed_covers_all_three_planning_depths(self) -> None:
        """D1 vocabulary literacy: ≥ 1 seed each for L0 / L1 / L2."""
        depths_seen = {t.expected_planning_depth for t in FRESH_TEST_TASKS}
        assert depths_seen == {"L0", "L1", "L2"}, (
            f"seed missing planning_depth coverage; saw {depths_seen}"
        )

    def test_seed_uses_only_known_tool_clusters(self) -> None:
        """D5 vocabulary literacy: every seed entry's
        ``expected_tool_cluster`` is in the locked vocabulary.

        This is *technically* enforced at FreshTask construction (the
        schema's field_validator); the test stays for documentation
        and as a belt-and-suspenders guard against a future
        validator-bypass refactor."""
        for task in FRESH_TEST_TASKS:
            assert task.expected_tool_cluster in CELL_TOOL_CLUSTERS, (
                f"{task.id}: unknown tool_cluster {task.expected_tool_cluster!r}"
            )

    def test_seed_covers_multiple_strata(self) -> None:
        """D8 stratum coverage: the seed should hit at least 3 of the 4
        strata (representative / boundary / edge / impossible) so the
        gap report shows non-trivial stratum spread on day one. If the
        seed clumps to one stratum, the gap report becomes uninformative."""
        strata_seen = {t.stratum for t in FRESH_TEST_TASKS}
        assert len(strata_seen) >= 3, f"seed should span ≥3 strata; saw {strata_seen}"

    def test_seed_cites_only_known_benchmark_schemas(self) -> None:
        """Phase 4 §8: reuse schemas, not items. Every seed cites a
        schema in the locked set (additive drift forces a code review)."""
        for task in FRESH_TEST_TASKS:
            assert task.source_benchmark_schema in FRESH_TASK_BENCHMARK_SCHEMAS, (
                f"{task.id}: unknown source_benchmark_schema "
                f"{task.source_benchmark_schema!r}"
            )

    def test_seed_lights_up_at_least_one_failure_mode(self) -> None:
        """Phase 4 has to seed *both* success-expected and failure-expected
        tasks so the eventual annotators see both. Catches a seed that
        is accidentally all-success or all-failure."""
        modes_seen = {t.expected_failure_mode for t in FRESH_TEST_TASKS}
        has_success = None in modes_seen
        has_failure = any(m is not None for m in modes_seen)
        assert has_success and has_failure, (
            f"seed must contain both success (None) and failure (non-None) "
            f"expected_failure_mode entries; saw {modes_seen}"
        )
