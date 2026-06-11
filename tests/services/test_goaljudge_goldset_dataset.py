"""L2 tests for Stage 5 golden-dataset CRUD + contamination firewall."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from components.schemas import GOAL_FAILURE_MODES
from services.governance.goaljudge_goldset_dataset import (
    CELL_TOOL_CLUSTERS,
    D1_FLOORS,
    D5_FLOORS,
    FRESH_TASK_BENCHMARK_SCHEMAS,
    STRATA_SHARES,
    AssemblyInvariantError,
    CoverageReport,
    DuplicateItemError,
    FirewallError,
    FreshTask,
    FreshTaskValidationError,
    GoldsetItem,
    GoldsetProvenance,
    GoldsetSplit,
    GoalJudgeGoldsetRepository,
    InMemoryLangfuseDatasetClient,
    LangfuseDatasetClient,
    active_failure_modes,
    assert_assembly_invariants,
    assert_firewall_batch,
    build_goldset_manifest,
    classify_tool_cluster,
    compute_cell_coverage,
    compute_test_split_hash,
    evaluate_goldset_post_alpha_coverage,
    gate_goldset_v1_floors,
    jaccard_similarity,
    project_trajectory_tools,
    row_to_goldset_item,
    validate_fresh_task_set,
)


def _sample_item(**overrides: object) -> GoldsetItem:
    base = {
        "item_id": "GS-001",
        "task_input": "do the thing",
        "final_answer": "done",
        "goal_met": False,
        "split": GoldsetSplit.DEV,
        "provenance": GoldsetProvenance.PRODUCTION,
        "failure_mode": "fabricated-progress",
    }
    base.update(overrides)
    return GoldsetItem(**base)


class TestFailureModeVocabulary:
    def test_active_failure_modes_matches_components_schema(self) -> None:
        assert active_failure_modes() == GOAL_FAILURE_MODES

    def test_unknown_failure_mode_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown failure_mode"):
            _sample_item(failure_mode="made-up-code")


class TestContaminationFirewall:
    def test_synthetic_on_test_split_rejected_at_validation(self) -> None:
        with pytest.raises(ValueError, match="contamination firewall"):
            _sample_item(
                split=GoldsetSplit.TEST,
                provenance=GoldsetProvenance.SYNTHETIC,
            )

    def test_assert_firewall_batch_rejects_duplicate_ids(self) -> None:
        with pytest.raises(FirewallError, match="duplicate item_id"):
            assert_firewall_batch([_sample_item(), _sample_item()])


class TestGoalJudgeGoldsetRepository:
    def test_ensure_dataset_is_idempotent(self) -> None:
        client = InMemoryLangfuseDatasetClient()
        repo = GoalJudgeGoldsetRepository(client)
        repo.ensure_dataset()
        repo.ensure_dataset()
        assert client.datasets == {"goaljudge_goldset_v1"}

    def test_upsert_item_creates_dataset_and_tags_metadata(self) -> None:
        client = InMemoryLangfuseDatasetClient()
        repo = GoalJudgeGoldsetRepository(client)
        item = _sample_item(item_id="GS-010", split=GoldsetSplit.TEST)
        repo.upsert_item(item)

        assert repo.item_ids == frozenset({"GS-010"})
        assert len(client.dataset_items) == 1
        stored = client.dataset_items[0]
        assert stored["id"] == "GS-010"
        assert stored["metadata"] == {
            "split": "test",
            "provenance": "production",
        }
        assert stored["input"]["failure_mode"] == "fabricated-progress"

    def test_upsert_item_rejects_duplicate_id(self) -> None:
        client = InMemoryLangfuseDatasetClient()
        repo = GoalJudgeGoldsetRepository(client)
        repo.upsert_item(_sample_item(item_id="GS-DUP"))
        with pytest.raises(DuplicateItemError, match="GS-DUP"):
            repo.upsert_item(_sample_item(item_id="GS-DUP"))

    def test_upsert_many_inserts_batch_after_firewall(self) -> None:
        client = InMemoryLangfuseDatasetClient()
        repo = GoalJudgeGoldsetRepository(client)
        items = [
            _sample_item(item_id="GS-1"),
            _sample_item(
                item_id="GS-2",
                provenance=GoldsetProvenance.SYNTHETIC,
                failure_mode="subtask-dropped",
            ),
        ]
        assert repo.upsert_many(items) == 2
        assert repo.item_ids == frozenset({"GS-1", "GS-2"})

    def test_upsert_many_aborts_on_duplicate_id(self) -> None:
        client = InMemoryLangfuseDatasetClient()
        repo = GoalJudgeGoldsetRepository(client)
        items = [
            _sample_item(item_id="GS-OK"),
            _sample_item(item_id="GS-OK", failure_mode="subtask-dropped"),
        ]
        with pytest.raises(FirewallError, match="duplicate item_id"):
            repo.upsert_many(items)
        assert repo.item_ids == frozenset()
        assert client.dataset_items == []


class TestRealLangfuseDatasetClient:
    """Protocol-shape tests for the production wrapper.

    No live Langfuse calls — the SDK is mocked. The point is to prove the
    wrapper satisfies the same Protocol the repository injects, so the
    repository code is identical against the real SDK and the in-memory
    fake.
    """

    def test_real_client_satisfies_protocol(self) -> None:
        from scripts.langfuse_dataset_client import RealLangfuseDatasetClient

        client = RealLangfuseDatasetClient(MagicMock())
        assert isinstance(client, LangfuseDatasetClient)

    def test_real_client_create_dataset_passes_through(self) -> None:
        from scripts.langfuse_dataset_client import RealLangfuseDatasetClient

        sdk = MagicMock()
        sdk.create_dataset.return_value = {"name": "goaljudge_goldset_v1"}
        client = RealLangfuseDatasetClient(sdk)

        result = client.create_dataset(name="goaljudge_goldset_v1")

        sdk.create_dataset.assert_called_once_with(name="goaljudge_goldset_v1")
        assert result == {"name": "goaljudge_goldset_v1"}

    def test_real_client_create_dataset_item_passes_through(self) -> None:
        from scripts.langfuse_dataset_client import RealLangfuseDatasetClient

        sdk = MagicMock()
        sdk.create_dataset_item.return_value = {"id": "GS-001"}
        client = RealLangfuseDatasetClient(sdk)

        payload = {"item_id": "GS-001", "goal_met": False}
        result = client.create_dataset_item(
            dataset_name="goaljudge_goldset_v1",
            input=payload,
            id="GS-001",
            metadata={"split": "test"},
        )

        sdk.create_dataset_item.assert_called_once_with(
            dataset_name="goaljudge_goldset_v1",
            input=payload,
            id="GS-001",
            metadata={"split": "test"},
        )
        assert result == {"id": "GS-001"}

    def test_real_client_coerces_pydantic_return(self) -> None:
        """SDK returns a typed Dataset object; wrapper must coerce to dict."""
        from scripts.langfuse_dataset_client import RealLangfuseDatasetClient

        sdk_return = MagicMock()
        sdk_return.model_dump.return_value = {"name": "ds", "id": "abc"}
        sdk = MagicMock()
        sdk.create_dataset.return_value = sdk_return

        client = RealLangfuseDatasetClient(sdk)
        result = client.create_dataset(name="ds")
        assert result == {"name": "ds", "id": "abc"}

    def test_builder_raises_when_env_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from scripts.langfuse_dataset_client import build_real_langfuse_dataset_client

        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

        with pytest.raises(RuntimeError, match="LANGFUSE_PUBLIC_KEY"):
            build_real_langfuse_dataset_client()


class TestComputeTestSplitHash:
    """The Stage 5 spec §9 / master plan §8.2 freeze instrument.

    The hash must be:
      1. **Stable** — insertion order does not affect the digest.
      2. **Sensitive** — any field change on any test row changes the digest.
      3. **Test-only** — dev-split items are ignored; dev churn must not
         break Stage 6's diff.
    """

    def _test_item(self, **overrides: object) -> GoldsetItem:
        base: dict[str, object] = {
            "item_id": "GS-T-001",
            "task_input": "ground-truth task",
            "final_answer": "yes",
            "goal_met": False,
            "split": GoldsetSplit.TEST,
            "provenance": GoldsetProvenance.PRODUCTION,
            "failure_mode": "fabricated-progress",
        }
        base.update(overrides)
        return GoldsetItem(**base)

    def test_hash_is_stable_across_insertion_order(self) -> None:
        a = self._test_item(item_id="GS-T-A")
        b = self._test_item(item_id="GS-T-B")
        c = self._test_item(item_id="GS-T-C")

        h_forward = compute_test_split_hash([a, b, c])
        h_reverse = compute_test_split_hash([c, b, a])
        h_shuffled = compute_test_split_hash([b, c, a])

        assert h_forward == h_reverse == h_shuffled
        assert len(h_forward) == 64  # SHA-256 hex

    def test_hash_changes_when_any_field_changes(self) -> None:
        base = self._test_item(item_id="GS-T-A")
        original = compute_test_split_hash([base])

        # Mutate every salient field one at a time; each must shift the hash.
        for mutation in [
            self._test_item(item_id="GS-T-A", task_input="different prompt"),
            self._test_item(item_id="GS-T-A", final_answer="no"),
            self._test_item(item_id="GS-T-A", goal_met=True),
            self._test_item(item_id="GS-T-A", failure_mode="subtask-dropped"),
            self._test_item(item_id="GS-T-A", partial_fraction=0.5),
            self._test_item(item_id="GS-T-A", evidence_digest="new digest"),
            self._test_item(item_id="GS-T-A", source_trace_id="abc123"),
        ]:
            assert compute_test_split_hash([mutation]) != original, (
                f"hash did not change after mutating item: {mutation.model_dump()}"
            )

    def test_hash_ignores_dev_split_items(self) -> None:
        """Adding/removing dev items must not change the test-split hash."""
        test_item = self._test_item(item_id="GS-T-A")
        dev_item = GoldsetItem(
            item_id="GS-D-A",
            task_input="dev item",
            final_answer="anything",
            goal_met=False,
            split=GoldsetSplit.DEV,
            provenance=GoldsetProvenance.SYNTHETIC,
            failure_mode="subtask-dropped",
        )
        dev_item_other = GoldsetItem(
            item_id="GS-D-B",
            task_input="another dev item, very different content",
            final_answer="totally other",
            goal_met=True,
            split=GoldsetSplit.DEV,
            provenance=GoldsetProvenance.PRODUCTION,
        )

        h_test_only = compute_test_split_hash([test_item])
        h_with_one_dev = compute_test_split_hash([test_item, dev_item])
        h_with_two_dev = compute_test_split_hash([test_item, dev_item, dev_item_other])
        h_with_swapped_dev = compute_test_split_hash([test_item, dev_item_other])

        assert h_test_only == h_with_one_dev == h_with_two_dev == h_with_swapped_dev

    def test_hash_empty_test_split(self) -> None:
        """A dev-only set still produces a deterministic (empty-payload) hash."""
        dev_only = GoldsetItem(
            item_id="GS-D-A",
            task_input="dev",
            final_answer="x",
            goal_met=False,
            split=GoldsetSplit.DEV,
            provenance=GoldsetProvenance.PRODUCTION,
        )
        h = compute_test_split_hash([dev_only])
        # SHA-256 of "[]" (json of empty list)
        import hashlib
        expected = hashlib.sha256(b"[]").hexdigest()
        assert h == expected


# ---------------------------------------------------------------------------
# Phase 3 — Cell classifier (L1 pure)
# ---------------------------------------------------------------------------
#
# Architecture layer:  Trust-Foundation-style shared kernel for Stage 5
# Pyramid layer:       L1 Deterministic
# TDD protocol:        Protocol A (pure Red-Green-Refactor)
# Anti-patterns guarded against:
#   * AP-1 Tautological:  inputs are externally-defined fixtures with known
#                         expected outputs; never recompute the cluster.
#   * AP-6 Gap blindness: failure-path tests precede happy-path tests.
#   * AP-7 Dependency leak: this test imports only from `services/` and
#                         the closed `components/schemas` vocabulary; never
#                         touches `components/router` or `orchestration/`.


class TestClassifyToolCluster:
    """Failure paths first — every override + edge case has a rejection test
    before the success-path test that proves the cluster lands.

    The eight-cluster D5 vocabulary is locked by the Stage 5 Tier 3 assembly
    plan (§"Pipeline dimension space"):

        file-only · shell-bound · web-bound · no-tool · compose ·
        wrong-tool · blocked-tool · request_approval
    """

    # ── Failure path: empty / unknown ────────────────────────────────────

    def test_empty_evidence_classifies_no_tool(self) -> None:
        """No tools called ⇒ knowledge-only stratum."""
        assert classify_tool_cluster([]) == "no-tool"

    def test_none_evidence_classifies_no_tool(self) -> None:
        """Defensive: builder passes None when a fresh task has no observed run."""
        assert classify_tool_cluster(None) == "no-tool"

    def test_unknown_tool_name_classifies_no_tool(self) -> None:
        """An unknown tool name (e.g. typo, deprecated) ⇒ no-tool, not crash."""
        evidence = [{"tool_name": "nonexistent_tool", "args_keys": []}]
        assert classify_tool_cluster(evidence) == "no-tool"

    # ── Failure-precedence: override semantics ──────────────────────────

    def test_blocked_tool_overrides_other_tools(self) -> None:
        """If ANY recorded call is blocked, the whole row is blocked-tool —
        this is the GJ-011 pattern (shell metachar/allowlist block masks
        the otherwise file_io-bound shape)."""
        evidence = [
            {"tool_name": "file_io", "args_keys": ["operation", "path"]},
            {"tool_name": "shell", "args_keys": ["command"], "blocked": True},
        ]
        assert classify_tool_cluster(evidence) == "blocked-tool"

    def test_wrong_tool_overrides_file_only(self) -> None:
        """An explicit ``wrong_tool=True`` marker (set by the builder when the
        author tags an expected_tool_cluster mismatch) overrides the natural
        cluster — the GJ-012 ``ls`` vs ``contents`` pattern."""
        evidence = [
            {"tool_name": "shell", "args_keys": ["command"], "wrong_tool": True},
        ]
        assert classify_tool_cluster(evidence) == "wrong-tool"

    def test_request_approval_overrides_other_tools(self) -> None:
        """HITL is a structural cell — any request_approval call wins."""
        evidence = [
            {"tool_name": "file_io", "args_keys": ["operation", "path"]},
            {"tool_name": "request_approval", "args_keys": ["reason"]},
        ]
        assert classify_tool_cluster(evidence) == "request_approval"

    # ── Happy paths: natural clusters ────────────────────────────────────

    def test_file_io_only_is_file_only(self) -> None:
        evidence = [{"tool_name": "file_io", "args_keys": ["operation", "path"]}]
        assert classify_tool_cluster(evidence) == "file-only"

    def test_file_tools_only_is_file_only(self) -> None:
        """State file tools count toward the file family."""
        evidence = [{"tool_name": "file_tools", "args_keys": ["operation"]}]
        assert classify_tool_cluster(evidence) == "file-only"

    def test_shell_only_is_shell_bound(self) -> None:
        evidence = [{"tool_name": "shell", "args_keys": ["command"]}]
        assert classify_tool_cluster(evidence) == "shell-bound"

    def test_shell_plus_file_io_is_shell_bound(self) -> None:
        """Shell + file_io is the same family (shell-bound) — file_io is a
        common helper for shell-driven flows."""
        evidence = [
            {"tool_name": "file_io", "args_keys": ["operation", "path"]},
            {"tool_name": "shell", "args_keys": ["command"]},
        ]
        assert classify_tool_cluster(evidence) == "shell-bound"

    def test_web_search_only_is_web_bound(self) -> None:
        evidence = [{"tool_name": "web_search", "args_keys": ["query"]}]
        assert classify_tool_cluster(evidence) == "web-bound"

    def test_file_plus_web_is_compose(self) -> None:
        """Two distinct tool families (file_io ∪ web_search) ⇒ compose."""
        evidence = [
            {"tool_name": "file_io", "args_keys": ["operation", "path"]},
            {"tool_name": "web_search", "args_keys": ["query"]},
        ]
        assert classify_tool_cluster(evidence) == "compose"

    def test_shell_plus_web_is_compose(self) -> None:
        evidence = [
            {"tool_name": "shell", "args_keys": ["command"]},
            {"tool_name": "web_search", "args_keys": ["query"]},
        ]
        assert classify_tool_cluster(evidence) == "compose"

    def test_three_families_is_compose(self) -> None:
        evidence = [
            {"tool_name": "file_io", "args_keys": ["operation", "path"]},
            {"tool_name": "shell", "args_keys": ["command"]},
            {"tool_name": "web_search", "args_keys": ["query"]},
        ]
        assert classify_tool_cluster(evidence) == "compose"

    def test_think_tool_only_is_no_tool(self) -> None:
        """think_tool is metacognitive — it does not count as an action tool.

        A row that *only* used think_tool is knowledge-only, same as zero
        tool calls. This prevents inflating the no-tool stratum's coverage
        with rows that actually exercised the planner.
        """
        evidence = [{"tool_name": "think_tool", "args_keys": ["thought"]}]
        assert classify_tool_cluster(evidence) == "no-tool"


class TestCellVocabularyAndFloors:
    """The Tier 3 assembly plan locks specific floor numbers and cluster
    names. A future heuristic tweak that silently drifts them would invalidate
    the plan's sizing math without anyone noticing — these tests are the
    drift-guard."""

    def test_d1_floors_match_plan(self) -> None:
        """L0/L1/L2 floors from the plan §"Stratification matrix"."""
        assert D1_FLOORS == {"L0": 60, "L1": 100, "L2": 60}

    def test_d5_floors_match_plan(self) -> None:
        """Eight-cluster D5 floors from the plan §"Stratification matrix"."""
        assert D5_FLOORS == {
            "file-only": 25,
            "shell-bound": 30,
            "web-bound": 25,
            "no-tool": 15,
            "compose": 40,
            "wrong-tool": 20,
            "blocked-tool": 15,
            "request_approval": 10,
        }

    def test_strata_shares_sum_to_one(self) -> None:
        """Stratum shares (spec §4) must total 100 % so the allocator can't
        over-allocate by rounding."""
        assert sum(STRATA_SHARES.values()) == pytest.approx(1.0)
        assert set(STRATA_SHARES) == {
            "representative", "boundary", "edge", "impossible"
        }

    def test_cell_tool_clusters_locks_the_d5_vocabulary(self) -> None:
        """The classifier output ∈ CELL_TOOL_CLUSTERS — every result of
        classify_tool_cluster() must be a member of the closed vocabulary.

        This is the consumer-driven contract test (TDD Pattern 4): if a future
        cluster is added, the builder + manifest must learn about it via
        CELL_TOOL_CLUSTERS, not by reading classify_tool_cluster's source.
        """
        assert CELL_TOOL_CLUSTERS == frozenset({
            "file-only", "shell-bound", "web-bound", "no-tool",
            "compose", "wrong-tool", "blocked-tool", "request_approval",
        })


class TestComputeCellCoverage:
    """The gap report is what tells Phase 4 authors which cells need items.
    Failure paths first: zero items must report *every* floor as a gap;
    a partially-filled cell must report the remaining gap. Only then does
    the happy path (floor met ⇒ no gap) get a test."""

    def _row(self, **k: object) -> dict[str, object]:
        base: dict[str, object] = {
            "stratum": "representative",
            "planning_depth": "L0",
            "tool_cluster": "file-only",
            "failure_mode": None,
        }
        base.update(k)
        return base

    # ── Failure path ─────────────────────────────────────────────────────

    def test_empty_dataset_reports_every_floor_as_gap(self) -> None:
        report = compute_cell_coverage([])
        # D1: all three floors are gaps with full magnitude.
        assert report.d1_gaps == {"L0": 60, "L1": 100, "L2": 60}
        # D5: every cluster has a gap equal to its floor.
        assert report.d5_gaps["file-only"] == 25
        assert report.d5_gaps["compose"] == 40
        assert report.d5_gaps["request_approval"] == 10
        assert report.total_items == 0

    def test_under_floor_reports_partial_gap(self) -> None:
        rows = [self._row(planning_depth="L0", tool_cluster="file-only")] * 5
        report = compute_cell_coverage(rows)
        assert report.d1_gaps["L0"] == 55  # 60 floor − 5 actual
        assert report.d5_gaps["file-only"] == 20  # 25 floor − 5 actual
        assert report.total_items == 5

    def test_overlapping_cell_counts_once_per_dim(self) -> None:
        """A single row counts in BOTH its D1 cell AND its D5 cluster cell —
        the dimensions overlap by construction. This is not double-counting:
        each dimension is its own coverage axis."""
        rows = [self._row(planning_depth="L1", tool_cluster="web-bound")]
        report = compute_cell_coverage(rows)
        assert report.d1_gaps["L1"] == 99  # contributed 1 to L1
        assert report.d5_gaps["web-bound"] == 24  # contributed 1 to web-bound

    # ── Happy path: floor met ⇒ no gap ──────────────────────────────────

    def test_floor_met_reports_zero_gap(self) -> None:
        rows = [self._row(planning_depth="L0", tool_cluster="file-only")] * 60
        report = compute_cell_coverage(rows)
        assert report.d1_gaps["L0"] == 0
        # L1 and L2 still at full floor since no rows contributed.
        assert report.d1_gaps["L1"] == 100
        assert report.d1_gaps["L2"] == 60

    def test_over_floor_clamps_gap_at_zero(self) -> None:
        rows = [self._row(planning_depth="L2", tool_cluster="compose")] * 75
        report = compute_cell_coverage(rows)
        assert report.d1_gaps["L2"] == 0  # not negative
        assert report.d5_gaps["compose"] == 0

    def test_report_renders_markdown(self) -> None:
        """The CoverageReport must serialize to a human-readable markdown
        table — that's what Phase 4 authors actually read."""
        report = compute_cell_coverage([
            self._row(planning_depth="L1", tool_cluster="web-bound")
        ])
        rendered = report.to_markdown()
        assert "planning_depth" in rendered.lower() or "D1" in rendered
        assert "L1" in rendered
        assert "web-bound" in rendered


class TestProjectTrajectoryTools:
    """Project a corpus row's Langfuse trajectory into the
    ``[{tool_name, args_keys}]`` shape that :func:`classify_tool_cluster`
    already consumes.

    Failure paths first — the projection must never crash the builder on
    malformed / missing / oversized input. Then two happy-path tests prove
    the contract the classifier depends on.

    The contract this projection satisfies is owned by
    :func:`classify_tool_cluster` (it's the cluster-classification consumer);
    drift in the dict shape here breaks D5 classification downstream.
    """

    # ── Failure paths first ─────────────────────────────────────────────

    def test_none_trajectory_yields_empty_list(self) -> None:
        """Defensive: the builder may pass ``None`` when a row has no
        corpus join (the trace simply isn't in the corpus snapshot)."""
        assert project_trajectory_tools(None) == []

    def test_empty_trajectory_yields_empty_list(self) -> None:
        """A trace with zero observations ⇒ no tool calls. Don't infer
        a no-tool cluster here — that's :func:`classify_tool_cluster`'s job.
        The projection just returns the empty list."""
        assert project_trajectory_tools([]) == []

    def test_no_tool_called_spans_yields_empty_list(self) -> None:
        """Trajectories full of llm-generation / planner spans but no
        ``tool.called`` spans ⇒ empty list. The projection filters by
        ``span.name == 'tool.called'`` (the canonical Langfuse marker used
        across the corpus export)."""
        trajectory = [
            {"name": "llm.generated", "input": {"foo": "bar"}},
            {"name": "step.planned", "input": {"plan_steps": 3}},
            {"name": "task.completed", "input": {"outcome": "partial"}},
        ]
        assert project_trajectory_tools(trajectory) == []

    def test_malformed_args_string_falls_back_to_empty_keys(self) -> None:
        """The corpus emits ``input.details.args`` as a stringified Python
        dict. Truncated / corrupted strings must NOT raise — the projection
        must fall back to ``args_keys=[]`` and still emit the tool_name so
        the cluster is computable from the family alone."""
        trajectory = [
            {
                "name": "tool.called",
                "input": {
                    "details": {
                        "tool": "file_io",
                        # truncated mid-string — would crash literal_eval.
                        "args": "{'path': '/x'",
                    }
                },
            },
        ]
        result = project_trajectory_tools(trajectory)
        assert result == [{"tool_name": "file_io", "args_keys": []}]

    def test_last_n_cap_keeps_only_recent_calls(self) -> None:
        """Adversarial saturation input (50 tool calls) must not blow up the
        projection. The cap mirrors ``components.goal_judge._summarize_evidence``'s
        8-call ceiling — cluster classification cares about *families touched*,
        not call count."""
        trajectory = [
            {
                "name": "tool.called",
                "input": {
                    "details": {
                        "tool": "file_io",
                        "args": f"{{'path': '/f{i}.txt', 'operation': 'read'}}",
                    }
                },
            }
            for i in range(50)
        ]
        result = project_trajectory_tools(trajectory, last_n=8)
        # Last-8 cap: 8 entries.
        assert len(result) == 8
        # And they're the *last* eight — argument key extraction proves the
        # right spans survived (all `file_io` with operation+path).
        for entry in result:
            assert entry["tool_name"] == "file_io"
            assert entry["args_keys"] == ["operation", "path"]

    # ── Happy paths: shape contract for the classifier ──────────────────

    def test_single_file_io_call_emits_classifier_shape(self) -> None:
        """A single ``file_io`` span ⇒ exactly the shape
        ``classify_tool_cluster`` consumes: ``tool_name`` + sorted
        ``args_keys``. The sort is deterministic so re-runs are hash-stable."""
        trajectory = [
            {
                "name": "tool.called",
                "input": {
                    "details": {
                        "tool": "file_io",
                        "args": "{'path': '/workspace/note.txt', 'operation': 'read'}",
                    }
                },
            },
        ]
        result = project_trajectory_tools(trajectory)
        # Single call, classifier-ready shape, sorted keys.
        assert result == [
            {"tool_name": "file_io", "args_keys": ["operation", "path"]},
        ]
        # And the classifier consumes it without modification.
        assert classify_tool_cluster(result) == "file-only"

    def test_multi_family_call_emits_compose_via_classifier(self) -> None:
        """A multi-family trajectory (file_io + web_search) emits two
        classifier-ready entries; feeding them through
        :func:`classify_tool_cluster` yields ``compose`` — i.e. the
        projection's output is genuinely classifier-compatible (drift-guard
        on the dict-shape contract)."""
        trajectory = [
            {
                "name": "tool.called",
                "input": {
                    "details": {
                        "tool": "file_io",
                        "args": "{'path': '/x', 'operation': 'write', 'content': 'hi'}",
                    }
                },
            },
            {
                "name": "tool.called",
                "input": {
                    "details": {
                        "tool": "web_search",
                        "args": "{'query': 'weather'}",
                    }
                },
            },
        ]
        result = project_trajectory_tools(trajectory)
        assert len(result) == 2
        assert result[0]["tool_name"] == "file_io"
        # sorted keys — deterministic.
        assert result[0]["args_keys"] == ["content", "operation", "path"]
        assert result[1] == {"tool_name": "web_search", "args_keys": ["query"]}
        # End-to-end: classifier sees both families ⇒ compose.
        assert classify_tool_cluster(result) == "compose"


# ───────────────────────────────────────────────────────────────────────────
# Phase 4 — FreshTask (cell-targeted fresh authoring) — Pyramid L1
# ───────────────────────────────────────────────────────────────────────────


def _fresh_kwargs(**overrides: object) -> dict[str, object]:
    """A valid FreshTask kwargs dict — overrides flip individual contract dims."""
    base: dict[str, object] = {
        "id": "GJ-F-001",
        "prompt": "Sum a column from /workspace/data.csv and return the total.",
        "stratum": "representative",
        "domain": "file_io",
        "expected_planning_depth": "L0",
        "expected_tool_cluster": "file-only",
        "expected_failure_mode": None,
        "source_benchmark_schema": "the-agent-company-checkpoint",
    }
    base.update(overrides)
    return base


class TestFreshTaskSchema:
    """L1 schema-validation tests for the Phase 4 fresh-task contract.

    Failure paths first (AP-6 Gap Blindness guard, per TDD §4 "Failure paths
    first"): every contract dimension has its rejection test authored before
    its acceptance test. Two-test pairs are interleaved by dimension so a
    skimmer can see the reject/accept symmetry for each axis.

    The schema lives in ``services/governance/goaljudge_goldset_dataset.py``
    (Horizontal L1, same module as ``GoldsetItem``); the test imports only
    from ``services.governance`` (AP-7 Cross-Layer Dependency Leak guard).
    """

    # ── Dim 1: expected_planning_depth (D1 vocabulary) ────────────────────

    def test_rejects_unknown_planning_depth(self) -> None:
        """``expected_planning_depth`` is closed: L0 / L1 / L2 only.
        An unknown value (e.g. ``L3``) must be rejected at construction —
        otherwise Phase 4 authors could silently drift the cell vocabulary."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FreshTask(**_fresh_kwargs(expected_planning_depth="L3"))

    def test_accepts_l0_l1_l2(self) -> None:
        """Each canonical depth is constructible (locks the closed set)."""
        for depth in ("L0", "L1", "L2"):
            task = FreshTask(**_fresh_kwargs(expected_planning_depth=depth))
            assert task.expected_planning_depth == depth

    # ── Dim 2: expected_tool_cluster (D5 vocabulary) ──────────────────────

    def test_rejects_unknown_tool_cluster(self) -> None:
        """``expected_tool_cluster`` must be one of ``CELL_TOOL_CLUSTERS``.
        A typo or new-cluster drift must fail — silently accepting it would
        invalidate Phase 3's gap report."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FreshTask(**_fresh_kwargs(expected_tool_cluster="non-existent-cluster"))

    def test_accepts_every_member_of_cell_tool_clusters(self) -> None:
        """Every cluster in the locked D5 vocabulary is constructible
        (consumer-driven contract, Pattern 4)."""
        for cluster in sorted(CELL_TOOL_CLUSTERS):
            task = FreshTask(**_fresh_kwargs(expected_tool_cluster=cluster))
            assert task.expected_tool_cluster == cluster

    # ── Dim 3: expected_failure_mode (D7 vocabulary) ──────────────────────

    def test_rejects_unknown_failure_mode(self) -> None:
        """``expected_failure_mode`` must be a known GOAL_FAILURE_MODES code
        or ``None``. An unknown code must be rejected (consistency with the
        existing GoldsetItem._normalize_failure_mode validator)."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FreshTask(**_fresh_kwargs(expected_failure_mode="totally-made-up-mode"))

    def test_accepts_none_failure_mode(self) -> None:
        """A task that expects success carries ``expected_failure_mode=None``."""
        task = FreshTask(**_fresh_kwargs(expected_failure_mode=None))
        assert task.expected_failure_mode is None

    def test_accepts_known_failure_mode_for_failure_task(self) -> None:
        """A task that expects A2 corrupt-success carries a known D7 code."""
        task = FreshTask(**_fresh_kwargs(expected_failure_mode="fabricated-progress"))
        assert task.expected_failure_mode == "fabricated-progress"

    # ── Dim 4: source_benchmark_schema (closed source-of-prompt set) ─────

    def test_rejects_unknown_benchmark_schema(self) -> None:
        """``source_benchmark_schema`` ∈ FRESH_TASK_BENCHMARK_SCHEMAS.
        Phase 4 spec §8 locks the allowed schemas — silent drift here would
        break the "reuse schemas, not items" discipline."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FreshTask(**_fresh_kwargs(source_benchmark_schema="unknown-bench-2030"))

    def test_accepts_every_member_of_benchmark_schemas(self) -> None:
        """Every schema in the locked set is constructible."""
        for schema in sorted(FRESH_TASK_BENCHMARK_SCHEMAS):
            task = FreshTask(**_fresh_kwargs(source_benchmark_schema=schema))
            assert task.source_benchmark_schema == schema

    # ── Dim 5: stratum (D8 vocabulary, must match STRATA_SHARES keys) ─────

    def test_rejects_unknown_stratum(self) -> None:
        """``stratum`` must match the spec §4 closed set so the allocator
        can balance shares correctly."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FreshTask(**_fresh_kwargs(stratum="unstratified-bonus-bucket"))

    def test_accepts_every_stratum_in_strata_shares(self) -> None:
        """Strata vocab is consumer-driven: every share-table key is
        constructible (Pattern 4: schema follows the consumer)."""
        for stratum in STRATA_SHARES:
            task = FreshTask(**_fresh_kwargs(stratum=stratum))
            assert task.stratum == stratum

    # ── Dim 6: required-field omission ────────────────────────────────────

    def test_rejects_missing_prompt(self) -> None:
        """``prompt`` is required (no silent empty-prompt drift)."""
        from pydantic import ValidationError
        bad = _fresh_kwargs()
        del bad["prompt"]
        with pytest.raises(ValidationError):
            FreshTask(**bad)

    def test_rejects_empty_prompt(self) -> None:
        """Empty-string ``prompt`` rejected (`min_length=1`)."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FreshTask(**_fresh_kwargs(prompt=""))

    def test_rejects_extra_field(self) -> None:
        """Schema is ``extra='forbid'`` so a typo'd key (e.g. ``failure_mode``
        instead of ``expected_failure_mode``) becomes a loud error, not a
        silent drop."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FreshTask(**_fresh_kwargs(failure_mode="fabricated-progress"))  # typo

    # ── Happy path: full roundtrip ────────────────────────────────────────

    def test_valid_fresh_task_constructs(self) -> None:
        """The full kwargs dict produces a valid FreshTask — proves the
        ``_fresh_kwargs`` helper isn't itself drifted."""
        task = FreshTask(**_fresh_kwargs())
        assert task.id == "GJ-F-001"
        assert task.expected_planning_depth == "L0"
        assert task.expected_tool_cluster == "file-only"
        assert task.expected_failure_mode is None


class TestFreshTaskBenchmarkSchemasVocabulary:
    """Locked vocabulary drift-guard (consumer-driven contract, Pattern 4).

    The Phase 4 plan §"reusing public-benchmark schemas (spec §8)" locks
    five sources. Anyone adding a sixth must update both the constant and
    this test, which forces a code review of the schema list."""

    def test_benchmark_schemas_matches_phase4_spec(self) -> None:
        assert FRESH_TASK_BENCHMARK_SCHEMAS == frozenset({
            "tau-bench",
            "the-agent-company-checkpoint",
            "webarena-impossible",
            "agentboard-subgoal",
            "novel",
        })


class TestJaccardSimilarity:
    """L1 pure-function tests for ``jaccard_similarity``.

    Anti-Pattern 1 (Tautological) guard: every assertion uses an
    *externally-derived* expected value computed by hand from the set
    theory, NOT by running the implementation. The test would catch a
    re-implementation that introduces e.g. a bigram tokenizer or a stop
    word list — both would change the answers below.

    Failure paths first: empty strings + disjoint strings (where the
    function's behavior is most likely to drift) tested before the
    "realistic prompt" cases."""

    # ── Failure / boundary paths ──────────────────────────────────────────

    def test_both_empty_returns_zero(self) -> None:
        """No tokens in either string ⇒ 0.0 (Jaccard is undefined on the
        empty set; the convention is 0.0 to avoid a ZeroDivisionError that
        would crash validate_fresh_task_set on a corner case)."""
        assert jaccard_similarity("", "") == 0.0

    def test_one_empty_returns_zero(self) -> None:
        """Disjoint by construction ⇒ 0.0."""
        assert jaccard_similarity("nonempty prompt", "") == 0.0
        assert jaccard_similarity("", "nonempty prompt") == 0.0

    def test_disjoint_tokens_returns_zero(self) -> None:
        """Two prompts that share no tokens ⇒ 0.0. Externally-derived: the
        set theory itself."""
        assert jaccard_similarity("alpha beta gamma", "delta epsilon") == 0.0

    # ── Realistic boundary cases (externally-derived expected values) ─────

    def test_identical_returns_one(self) -> None:
        """Identical tokenizations ⇒ 1.0. Externally-derived from the
        Jaccard formula: |X ∩ X| / |X ∪ X| = 1.0."""
        assert jaccard_similarity("read the file", "read the file") == 1.0

    def test_partial_overlap_one_third(self) -> None:
        """Tokens {a, b} vs {b, c}: intersection = {b}, union = {a, b, c};
        Jaccard = 1/3. Externally-derived by hand from the set theory."""
        # pytest.approx because 1/3 is a recurring decimal.
        assert jaccard_similarity("a b", "b c") == pytest.approx(1.0 / 3.0)

    def test_case_insensitive(self) -> None:
        """Phase 4 plan calls for Jaccard over the *prompt surface form*;
        casing should not affect the score (otherwise authors trivially
        evade the drift-guard by capitalizing a word)."""
        # "Read the FILE" vs "read THE file" — same token set.
        assert jaccard_similarity("Read the FILE", "read THE file") == 1.0

    def test_symmetric(self) -> None:
        """Jaccard(a, b) == Jaccard(b, a) — a stability invariant the
        Phase 4 drift-guard relies on when comparing fresh tasks against
        each registry prompt in either order."""
        a = "summarize the article"
        b = "create a summary of the article"
        assert jaccard_similarity(a, b) == jaccard_similarity(b, a)


class TestValidateFreshTaskSet:
    """L1 contract tests for ``validate_fresh_task_set``.

    Failure paths first (AP-6 guard). Every drift-mode the Phase 4 plan
    §"drift-guards" lists has a rejection test before the happy-path
    "this corpus is clean" test.

    No mocks. ``router_fn`` is a simple lambda returning canned (depth,
    reason) tuples — that's a stub, not a mock, because we're not asserting
    on it; we're providing controlled inputs to the function under test."""

    def _stub_router(self, *, agree: bool = True):
        """Returns a callable matching ``select_planning_depth``'s shape.

        ``agree=True`` ⇒ the stub returns whatever depth the prompt asks
        for (encoded by a sentinel prefix); ``agree=False`` ⇒ always
        returns ``L0`` so any non-L0 expected depth disagrees.
        """
        if agree:
            def _agreeing(*, task_input: str, task_tool_results_count: int) -> tuple[str, str]:
                # Encode expected depth in the prompt prefix so the stub
                # mirrors author intent.
                for depth in ("L2", "L1", "L0"):
                    if task_input.startswith(depth + ":"):
                        return depth, "stub:agree"
                return "L0", "stub:default"
            return _agreeing
        else:
            def _disagreeing(*, task_input: str, task_tool_results_count: int) -> tuple[str, str]:
                return "L0", "stub:always-L0"
            return _disagreeing

    # ── Failure path 1: duplicate id ──────────────────────────────────────

    def test_rejects_duplicate_task_id(self) -> None:
        """Two FreshTasks with the same ``id`` ⇒ FreshTaskValidationError.
        Without this, the gold set could silently collide on freeze."""
        tasks = [
            FreshTask(**_fresh_kwargs(id="GJ-F-001")),
            FreshTask(**_fresh_kwargs(id="GJ-F-001", prompt="totally different prompt")),
        ]
        with pytest.raises(FreshTaskValidationError, match=r"(?i)duplicate"):
            validate_fresh_task_set(tasks, [], self._stub_router(agree=True))

    # ── Failure path 2: router-disagreement on D1 ─────────────────────────

    def test_rejects_router_disagreement_on_planning_depth(self) -> None:
        """The author's ``expected_planning_depth`` must agree with what
        ``select_planning_depth`` would route the prompt to. Otherwise
        the gold set drifts away from production routing behavior — the
        whole reason D1 is a cell dimension."""
        # Author says L2 but the stub router always returns L0 ⇒ disagreement.
        tasks = [FreshTask(**_fresh_kwargs(expected_planning_depth="L2"))]
        with pytest.raises(FreshTaskValidationError, match=r"(?i)router|planning_depth"):
            validate_fresh_task_set(tasks, [], self._stub_router(agree=False))

    # ── Failure path 3: registry-prompt contamination (Jaccard ≥ 0.5) ────

    def test_rejects_high_jaccard_against_registry(self) -> None:
        """Phase 4 contamination guard: a fresh prompt must be surface-form
        distinct from every CASE_BY_ID prompt. Threshold = 0.5 by spec."""
        registry_prompt = "Sum a column from /workspace/data.csv and return the total."
        # Identical prompt ⇒ Jaccard = 1.0 ⇒ must reject.
        tasks = [FreshTask(**_fresh_kwargs(prompt=registry_prompt))]
        with pytest.raises(FreshTaskValidationError, match=r"(?i)jaccard|registry|contamination"):
            validate_fresh_task_set(tasks, [registry_prompt], self._stub_router(agree=True))

    # ── Happy path: clean corpus passes ───────────────────────────────────

    def test_accepts_clean_corpus(self) -> None:
        """A corpus with: unique ids, router-agreement, and no
        registry-overlap passes silently (returns None)."""
        tasks = [
            FreshTask(**_fresh_kwargs(id="GJ-F-001", prompt="L0:Echo back the user's name verbatim.")),
            FreshTask(**_fresh_kwargs(id="GJ-F-002", prompt="L1:Open journal.md and append today's date.",
                                       expected_planning_depth="L1")),
        ]
        registry = ["completely unrelated registry prompt"]
        # Must not raise. Explicit None return = "all guards passed".
        result = validate_fresh_task_set(tasks, registry, self._stub_router(agree=True))
        assert result is None

    # ── Boundary: threshold is exclusive (< 0.5 passes, ≥ 0.5 fails) ─────

    def test_jaccard_threshold_is_configurable(self) -> None:
        """The threshold defaults to 0.5 but is parameterizable — Phase 4
        may tighten to 0.3 if 0.5 admits too much paraphrase."""
        # Identical prompts ⇒ Jaccard = 1.0 ⇒ even with threshold=0.99 should fail.
        tasks = [FreshTask(**_fresh_kwargs(prompt="L0:foo bar baz"))]
        registry = ["L0:foo bar baz"]
        with pytest.raises(FreshTaskValidationError):
            validate_fresh_task_set(
                tasks, registry, self._stub_router(agree=True),
                jaccard_threshold=0.99,
            )


# ───────────────────────────────────────────────────────────────────────────
# Phase 5 — Post-α coverage drift-guard
# ───────────────────────────────────────────────────────────────────────────


def _row(**overrides: object) -> dict[str, object]:
    """Minimal row mimicking the labeling-sheet shape the Phase 5 gate
    will pass into ``evaluate_goldset_post_alpha_coverage``."""
    base: dict[str, object] = {
        "item_id": "GJ-X",
        "planning_depth": "L0",
        "tool_cluster": "no-tool",
        "adjudicated_goal_met": "false",
    }
    base.update(overrides)
    return base


class TestEvaluateGoldsetPostAlphaCoverage:
    """Failure-paths-first then acceptance, per Pattern 11 (Failure Mode
    Matrix) and Pattern 1 (Property-Based — externally derived expected
    values).

    The function under test is the LABELING-quality gate (vs. the
    SOURCING-quality gate that ``compute_cell_coverage`` enforces in
    Phase 3). The difference: this function only considers rows whose
    adjudicated ``goal_met`` is ``False``, because Stage 6's primary
    metric class is the failure modes — a sourcing pass with all-success
    labels would leak through Phase 3 but be caught here."""

    # ── Failure path 1: empty input ────────────────────────────────────

    def test_empty_rows_yields_full_gap(self) -> None:
        """Zero rows ⇒ every floor is unmet ⇒ every d1_gap and d5_gap
        equals its floor. Crashing would surface as a Phase 5 silent
        false-pass — must return a usable report."""
        report = evaluate_goldset_post_alpha_coverage([])
        assert report.total_items == 0
        # Every floor unmet => gap == floor
        for depth, floor in D1_FLOORS.items():
            assert report.d1_gaps[depth] == floor
        for cluster, floor in D5_FLOORS.items():
            assert report.d5_gaps[cluster] == floor

    # ── Failure path 2: column collapse — adjudication is all True ─────

    def test_all_goal_met_true_yields_full_gap(self) -> None:
        """If labeling produced 100% goal_met=true, the failure-mode
        subset is empty — the gate MUST report 'every cell unmet', not
        silently re-use the agreement-row sourcing counts."""
        rows = [_row(adjudicated_goal_met="true") for _ in range(100)]
        report = evaluate_goldset_post_alpha_coverage(rows)
        assert report.total_items == 0
        assert report.d1_gaps["L0"] == D1_FLOORS["L0"]

    # ── Failure path 3: missing adjudication ───────────────────────────

    def test_rows_missing_adjudicated_goal_met_are_skipped(self) -> None:
        """A row whose adjudicated column is blank means adjudication
        hasn't happened (or this row wasn't a disagreement so the column
        is implicit — but at this gate we ONLY count rows that have been
        explicitly graded false). The cell-counter MUST skip blanks."""
        rows = [
            _row(adjudicated_goal_met=""),
            _row(adjudicated_goal_met=""),
        ]
        report = evaluate_goldset_post_alpha_coverage(rows)
        assert report.total_items == 0

    # ── Acceptance path 1: a single L0 / no-tool cell at floor ─────────

    def test_one_cell_filled_at_floor_closes_just_that_cell(self) -> None:
        """Fill the L0+no-tool cell to its floor; all other cells stay
        open. Verifies (a) per-cell accounting is independent and (b)
        the floor is met when count >= floor."""
        l0_floor = D1_FLOORS["L0"]
        no_tool_floor = D5_FLOORS["no-tool"]
        # Use the larger of the two floors so both cells close
        # simultaneously without over-filling either dimension.
        n = max(l0_floor, no_tool_floor)
        rows = [
            _row(planning_depth="L0", tool_cluster="no-tool")
            for _ in range(n)
        ]
        report = evaluate_goldset_post_alpha_coverage(rows)
        assert report.total_items == n
        assert report.d1_gaps["L0"] == 0
        assert report.d5_gaps["no-tool"] == 0
        # Other D1 cells remain at full floor
        assert report.d1_gaps["L1"] == D1_FLOORS["L1"]
        assert report.d1_gaps["L2"] == D1_FLOORS["L2"]

    # ── Acceptance path 2: mixed cells with some goal_met=true filter ──

    def test_filters_to_failure_subset_only(self) -> None:
        """The function must drop adjudicated_goal_met=true rows before
        counting. Construct a row set where the COMBINED count would
        close L1 but the FAILURE-ONLY count does not."""
        # 50 L1+file-only rows: half pass, half fail.
        successes = [
            _row(planning_depth="L1", tool_cluster="file-only",
                 adjudicated_goal_met="true")
            for _ in range(50)
        ]
        failures = [
            _row(planning_depth="L1", tool_cluster="file-only",
                 adjudicated_goal_met="false")
            for _ in range(50)
        ]
        report = evaluate_goldset_post_alpha_coverage(successes + failures)
        # Only the 50 failures count.
        assert report.total_items == 50
        l1_floor = D1_FLOORS["L1"]
        # Floor 100, only 50 failures ⇒ gap 50.
        assert report.d1_gaps["L1"] == max(0, l1_floor - 50)


# ───────────────────────────────────────────────────────────────────────────
# Phase 6 — Assemble, freeze, manifest
# ───────────────────────────────────────────────────────────────────────────
#
# Three new pure helpers live in the same horizontal L1 module so the
# CLI script (``scripts/assemble_goaljudge_goldset.py``) is a thin wrapper:
#
#   row_to_goldset_item(row)        — CSV row → validated GoldsetItem
#   assert_assembly_invariants(...) — integration-boundary safety net
#   build_goldset_manifest(...)     — assembles the v1 manifest dict
#
# Failure paths authored first per AP-6.


def _csv_row(**overrides: object) -> dict[str, str]:
    """One adjudicated sheet row matching the Phase 3 builder's FIELDS
    contract. All values are strings (csv.DictReader gives strings)."""
    base: dict[str, str] = {
        "item_id": "GJ-001",
        "split": "dev",
        "provenance": "production",
        "stratum": "representative",
        "domain": "file_io",
        "planning_depth": "L1",
        "tool_cluster": "file-only",
        "task": "Create a file at /workspace/x.txt and read it back.",
        "claim": "Wrote and read 'status=active'.",
        "evidence_summary": "file_io write+read evidenced in Langfuse",
        "r1_goal_met": "false",
        "r1_graceful_failure": "false",
        "r1_partial_fraction": "0.5",
        "r1_failure_mode": "subtask-dropped",
        "r2_goal_met": "false",
        "r2_graceful_failure": "false",
        "r2_partial_fraction": "0.5",
        "r2_failure_mode": "subtask-dropped",
        "adjudicated_goal_met": "false",
        "adjudicated_failure_mode": "subtask-dropped",
        "rubric_version": "stage4_confirmed",
        "note": "",
    }
    base.update({k: str(v) for k, v in overrides.items()})
    return base


# ───────────────────────────────────────────────────────────────────────────
# row_to_goldset_item — CSV row → GoldsetItem (validated)
# ───────────────────────────────────────────────────────────────────────────


class TestRowToGoldsetItem:
    """Failure paths first per AP-6, then acceptance. The function MUST
    map the FIELDS contract (Phase 3 builder) into a GoldsetItem (Phase 6
    schema) while *re-running* the GoldsetItem validators so a corrupt
    sheet row can never sneak past the firewall."""

    # ── Failure path 1: missing item_id ──────────────────────────────────

    def test_rejects_row_with_blank_item_id(self) -> None:
        """A blank ``item_id`` would yield duplicate-collision risk at
        Langfuse load. MUST raise (pydantic min_length=1)."""
        row = _csv_row(item_id="")
        with pytest.raises(ValueError, match=r"(?i)item_id|min_length|String should have at least"):
            row_to_goldset_item(row)

    # ── Failure path 2: invalid adjudicated_goal_met ─────────────────────

    def test_rejects_row_with_uninterpretable_goal_met(self) -> None:
        """Adjudicated column must be canonical true/false. A typo
        ('maybe', 'tru') must be caught up-front. The function defers
        truthiness recognition to services.governance.iaa.normalize_bool_label;
        an un-normalizable value triggers the validation error."""
        row = _csv_row(adjudicated_goal_met="maybe")
        with pytest.raises(ValueError, match=r"(?i)adjudicated_goal_met|goal_met"):
            row_to_goldset_item(row)

    # ── Failure path 3: unknown failure_mode ─────────────────────────────

    def test_rejects_row_with_unknown_failure_mode(self) -> None:
        """An unknown failure mode would silently survive a CSV round-trip
        because the column is free-text. The GoldsetItem field_validator
        rejects it; row_to_goldset_item MUST propagate."""
        row = _csv_row(adjudicated_failure_mode="invented-code")
        with pytest.raises(ValueError, match=r"(?i)unknown failure_mode"):
            row_to_goldset_item(row)

    # ── Failure path 4: firewall — synthetic in test split ───────────────

    def test_rejects_row_with_synthetic_in_test_split(self) -> None:
        """The GoldsetItem model_validator already enforces this; the test
        proves row_to_goldset_item doesn't accidentally swallow that
        error by setting a default split or coercing it."""
        row = _csv_row(provenance="synthetic", split="test")
        with pytest.raises(ValueError, match=r"contamination firewall"):
            row_to_goldset_item(row)

    # ── Failure path 5: blank task ───────────────────────────────────────

    def test_rejects_row_with_blank_task(self) -> None:
        """``task`` becomes ``task_input`` on the GoldsetItem. The pilot
        schema constrains via min_length implicitly through downstream
        consumers; the wrapper MUST surface a non-empty task to keep
        Stage 6 from prompting on empty strings."""
        row = _csv_row(task="")
        with pytest.raises(ValueError, match=r"(?i)task"):
            row_to_goldset_item(row)

    # ── Acceptance 1: dev/production goal_met=false roundtrip ────────────

    def test_dev_production_failure_row_roundtrips(self) -> None:
        """Happy path — the most common shape. Verifies field-by-field
        that the wrapper maps each FIELDS column to the expected
        GoldsetItem field with no surprises."""
        row = _csv_row()
        item = row_to_goldset_item(row)
        assert item.item_id == "GJ-001"
        assert item.split == GoldsetSplit.DEV
        assert item.provenance == GoldsetProvenance.PRODUCTION
        assert item.task_input == row["task"]
        assert item.final_answer == row["claim"]
        assert item.goal_met is False
        assert item.graceful_failure is False
        assert item.partial_fraction == pytest.approx(0.5)
        assert item.failure_mode == "subtask-dropped"

    # ── Acceptance 2: test/production goal_met=true blanks failure_mode ──

    def test_test_production_success_row_clears_failure_mode(self) -> None:
        """When goal_met=true, the row's failure_mode column may be
        blank. GoldsetItem.failure_mode must be None (not ''), per the
        model validator."""
        row = _csv_row(
            split="test",
            adjudicated_goal_met="true",
            adjudicated_failure_mode="",
            r1_goal_met="true",
            r1_partial_fraction="1.0",
            r2_goal_met="true",
            r2_partial_fraction="1.0",
        )
        item = row_to_goldset_item(row)
        assert item.goal_met is True
        assert item.failure_mode is None
        assert item.split == GoldsetSplit.TEST

    # ── Acceptance 3: normalize_bool_label spelling tolerance ────────────

    def test_accepts_truthy_spellings_for_adjudicated_goal_met(self) -> None:
        """``Y``/``1``/``True`` all collapse to ``goal_met=True``. The
        wrapper delegates to ``services.governance.iaa.normalize_bool_label``
        — proving by behavior that the spelling map is shared, not duplicated."""
        for spelling in ("Y", "yes", "1", "True", "TRUE"):
            row = _csv_row(
                adjudicated_goal_met=spelling,
                adjudicated_failure_mode="",
                r1_goal_met=spelling,
                r2_goal_met=spelling,
                r1_partial_fraction="1.0",
                r2_partial_fraction="1.0",
            )
            item = row_to_goldset_item(row)
            assert item.goal_met is True, f"spelling {spelling!r} failed"


# ───────────────────────────────────────────────────────────────────────────
# assert_assembly_invariants — integration-boundary safety net
# ───────────────────────────────────────────────────────────────────────────


def _item(item_id: str, **overrides: object) -> GoldsetItem:
    """Tiny helper for constructing GoldsetItems with sensible defaults."""
    base: dict[str, object] = {
        "item_id": item_id,
        "task_input": f"task for {item_id}",
        "final_answer": "answer",
        "goal_met": False,
        "split": GoldsetSplit.DEV,
        "provenance": GoldsetProvenance.PRODUCTION,
        "failure_mode": "subtask-dropped",
    }
    base.update(overrides)
    return GoldsetItem(**base)


class TestAssertAssemblyInvariants:
    """One failure test per invariant before the consolidated acceptance
    test. The function MUST raise ``AssemblyInvariantError`` (a distinct
    type from ``FirewallError`` so callers can route the error narrative
    differently) for each violation."""

    # ── Failure path 1: duplicate item_id (delegated to firewall) ────────

    def test_duplicate_item_id_raises(self) -> None:
        """Even though :func:`assert_firewall_batch` catches this,
        :func:`assert_assembly_invariants` MUST also surface it (the
        contract is *every* invariant on a single call site)."""
        items = [_item("GJ-1"), _item("GJ-1")]
        with pytest.raises(AssemblyInvariantError, match=r"(?i)duplicate"):
            assert_assembly_invariants(items)

    # ── Failure path 2: synthetic on test split (firewall) ───────────────

    def test_synthetic_on_test_split_raises(self) -> None:
        """GoldsetItem model_validator catches this on construction; the
        invariant bundle re-asserts in case a caller bypasses pydantic
        (e.g. constructs items via ``model_construct``).

        Construct two items: one legal synthetic-dev and one *illegal*
        synthetic-test using ``model_construct`` to bypass the GoldsetItem
        validator — this is the realistic failure path because the
        bundle is the only defense once pydantic is bypassed."""
        synthetic_dev = _item(
            "GJ-1", split=GoldsetSplit.DEV,
            provenance=GoldsetProvenance.SYNTHETIC,
        )
        # Use model_construct to bypass the model-level firewall on this
        # item, simulating a caller that did the same and now relies on
        # assert_assembly_invariants to catch the violation.
        synthetic_test = GoldsetItem.model_construct(
            item_id="GJ-2",
            task_input="t",
            final_answer="a",
            evidence_digest="",
            goal_met=False,
            graceful_failure=False,
            partial_fraction=0.0,
            failure_mode=None,
            evidence_spans=[],
            split=GoldsetSplit.TEST,
            provenance=GoldsetProvenance.SYNTHETIC,
            source_trace_id=None,
        )
        with pytest.raises(
            AssemblyInvariantError, match=r"(?i)firewall|synthetic"
        ):
            assert_assembly_invariants([synthetic_dev, synthetic_test])

    # ── Failure path 3: goal_met=false share below 60% ──────────────────

    def test_goal_met_false_share_below_60pct_raises(self) -> None:
        """Per spec §4: gold set must surface failure modes at ≥60% of
        rows. A goal_met=true-heavy set would produce a calibration corpus
        with not enough failure variety to power Stage 6's per-code
        precision/recall."""
        # 5 true, 5 false ⇒ false share = 50% ⇒ FAIL
        items = (
            [_item(f"T{i}", goal_met=True, failure_mode=None) for i in range(5)]
            + [_item(f"F{i}", goal_met=False) for i in range(5)]
        )
        with pytest.raises(
            AssemblyInvariantError, match=r"(?i)goal_met.*false|60"
        ):
            assert_assembly_invariants(items, min_goal_met_false_share=0.60)

    # ── Failure path 4: per-D1 floor unmet ──────────────────────────────

    def test_d1_floor_unmet_raises_with_named_cell(self) -> None:
        """Cell-coverage assertion is the most important *labeling-time*
        contract — if a cell collapsed because labels skewed, Phase 6
        catches it BEFORE the manifest is written. Asserts that the
        error message names the failing cell so the operator can act."""
        # Construct a tiny dataset where only L0 cell is populated and
        # the planning_depth floors are simulated via a custom floor
        # dict for testability.
        items = [
            _item(f"GJ-{i}", goal_met=False)
            for i in range(20)
        ]
        # Provide a CSV-side row index keyed by item_id so the bundle
        # can read planning_depth (which lives on the sheet, not the
        # GoldsetItem). All 20 items map to L0.
        depths = {f"GJ-{i}": "L0" for i in range(20)}
        clusters = {f"GJ-{i}": "no-tool" for i in range(20)}
        failure_modes_per_item = {f"GJ-{i}": "subtask-dropped" for i in range(20)}
        with pytest.raises(
            AssemblyInvariantError, match=r"(?i)L1|planning_depth|floor"
        ):
            assert_assembly_invariants(
                items,
                planning_depth_by_id=depths,
                tool_cluster_by_id=clusters,
                min_goal_met_false_share=0.0,  # disable that check for this test
            )

    # ── Acceptance: a well-formed 12-item set passes silently ────────────

    def test_well_formed_set_passes_silently(self) -> None:
        """A small set that meets the lowered floors (via the kwargs)
        passes. The default floors are unreachable at 12 items by design;
        we lower them via the floor-override kwargs so the test stays
        deterministic without authoring 250 items."""
        items = [
            _item(f"D{i}", goal_met=False)
            for i in range(10)
        ] + [
            _item(f"S{i}", goal_met=True, failure_mode=None)
            for i in range(2)
        ]
        depths = {item.item_id: "L1" for item in items}
        clusters = {item.item_id: "file-only" for item in items}
        # Lowered floors so the test set itself proves the path; the
        # production floor enforcement is the integration-test gate.
        result = assert_assembly_invariants(
            items,
            planning_depth_by_id=depths,
            tool_cluster_by_id=clusters,
            d1_floors={"L0": 0, "L1": 10, "L2": 0},
            d5_floors={"file-only": 10, "shell-bound": 0, "web-bound": 0,
                       "no-tool": 0, "compose": 0, "wrong-tool": 0,
                       "blocked-tool": 0, "request_approval": 0},
            min_goal_met_false_share=0.60,
        )
        assert result is None


# ───────────────────────────────────────────────────────────────────────────
# build_goldset_manifest — produces the v1 manifest dict
# ───────────────────────────────────────────────────────────────────────────


class TestBuildGoldsetManifest:
    """Failure paths first then acceptance. The manifest is the single
    source of truth Stage 6 diffs against; missing or malformed keys
    here would surface as silent calibration regressions later."""

    # ── Failure path 1: empty test_split_sha256 ──────────────────────────

    def test_blank_test_split_sha256_raises(self) -> None:
        """The hash is the WHOLE POINT of the manifest. A blank value
        means the caller forgot to compute it — must fail loudly."""
        items = [_item("GJ-1", goal_met=False)]
        with pytest.raises(ValueError, match=r"(?i)test_split_sha256|empty|blank"):
            build_goldset_manifest(
                items,
                test_split_sha256="",
                rubric_version="stage4_confirmed",
                frozen_at="2026-06-09T00:00:00Z",
            )

    # ── Failure path 2: blank rubric_version ────────────────────────────

    def test_blank_rubric_version_raises(self) -> None:
        items = [_item("GJ-1", goal_met=False)]
        with pytest.raises(ValueError, match=r"(?i)rubric_version"):
            build_goldset_manifest(
                items,
                test_split_sha256="abc123",
                rubric_version="",
                frozen_at="2026-06-09T00:00:00Z",
            )

    # ── Failure path 3: blank frozen_at ─────────────────────────────────

    def test_blank_frozen_at_raises(self) -> None:
        items = [_item("GJ-1", goal_met=False)]
        with pytest.raises(ValueError, match=r"(?i)frozen_at"):
            build_goldset_manifest(
                items,
                test_split_sha256="abc123",
                rubric_version="stage4_confirmed",
                frozen_at="",
            )

    # ── Acceptance 1: all 12 required keys present + correct counts ─────

    def test_manifest_has_all_required_keys_and_counts(self) -> None:
        """Externally-derived expected counts:
        * 3 items total ⇒ total_items=3
        * 2 dev + 1 test ⇒ dev_count=2, test_count=1
        * 2 goal_met=false / 3 ⇒ goal_met_false_share = 2/3 ≈ 0.6667
        """
        items = [
            _item("GJ-1", goal_met=False, split=GoldsetSplit.DEV),
            _item("GJ-2", goal_met=False, split=GoldsetSplit.DEV),
            _item("GJ-3", goal_met=True, failure_mode=None,
                  split=GoldsetSplit.TEST),
        ]
        manifest = build_goldset_manifest(
            items,
            test_split_sha256="abc123",
            rubric_version="stage4_confirmed",
            frozen_at="2026-06-09T12:00:00Z",
        )
        # Required keys
        expected_keys = {
            "dataset_name",
            "total_items",
            "dev_count",
            "test_count",
            "test_split_sha256",
            "rubric_version",
            "frozen_at",
            "stratum_distribution",
            "planning_depth_distribution",
            "tool_cluster_distribution",
            "failure_mode_distribution",
            "goal_met_false_share",
        }
        assert expected_keys.issubset(set(manifest.keys()))
        # Counts
        assert manifest["dataset_name"] == "goaljudge_goldset_v1"
        assert manifest["total_items"] == 3
        assert manifest["dev_count"] == 2
        assert manifest["test_count"] == 1
        assert manifest["test_split_sha256"] == "abc123"
        assert manifest["rubric_version"] == "stage4_confirmed"
        assert manifest["frozen_at"] == "2026-06-09T12:00:00Z"
        assert manifest["goal_met_false_share"] == pytest.approx(2.0 / 3.0)

    # ── Acceptance 2: failure_mode_distribution counts correctly ────────

    def test_failure_mode_distribution_aggregates_by_code(self) -> None:
        """Two distinct failure modes across three items — distribution
        dict should be {'subtask-dropped': 2, 'fabricated-progress': 1}."""
        items = [
            _item("GJ-1", goal_met=False, failure_mode="subtask-dropped"),
            _item("GJ-2", goal_met=False, failure_mode="subtask-dropped"),
            _item("GJ-3", goal_met=False, failure_mode="fabricated-progress"),
        ]
        manifest = build_goldset_manifest(
            items,
            test_split_sha256="abc",
            rubric_version="stage4_confirmed",
            frozen_at="2026-06-09T00:00:00Z",
        )
        assert manifest["failure_mode_distribution"] == {
            "subtask-dropped": 2,
            "fabricated-progress": 1,
        }

    # ── Acceptance 3: informational dicts default to empty when absent ──

    def test_observed_distributions_optional(self) -> None:
        """The three informational dicts (routing_reason / model_tier /
        cost_fraction_bins) are optional — they're prod-only and absent
        on synthetic-only sets. The manifest MUST still build and the
        keys MUST be present (empty dicts), so Stage 6 diff has a stable
        shape to compare against."""
        items = [_item("GJ-1", goal_met=False)]
        manifest = build_goldset_manifest(
            items,
            test_split_sha256="abc",
            rubric_version="stage4_confirmed",
            frozen_at="2026-06-09T00:00:00Z",
        )
        assert manifest.get("routing_reason_distribution_observed") == {}
        assert manifest.get("model_tier_distribution_observed") == {}
        assert manifest.get("cost_fraction_bins_observed") == {}

    # ── Acceptance 4: explicit observed_distributions pass through ──────

    def test_explicit_observed_distributions_pass_through(self) -> None:
        """When the assembler has the three informational counters,
        they're included verbatim — no recomputation by the manifest
        builder. This keeps the helper's responsibilities narrow."""
        items = [_item("GJ-1", goal_met=False)]
        observed = {
            "routing_reason_distribution_observed": {"depth-keyword": 12},
            "model_tier_distribution_observed": {"openai/gpt-4o-mini": 250},
            "cost_fraction_bins_observed": {"[0.0,0.1)": 30, "[0.1,0.2)": 10},
        }
        manifest = build_goldset_manifest(
            items,
            test_split_sha256="abc",
            rubric_version="stage4_confirmed",
            frozen_at="2026-06-09T00:00:00Z",
            observed_distributions=observed,
        )
        assert manifest["routing_reason_distribution_observed"] == {
            "depth-keyword": 12,
        }
        assert manifest["model_tier_distribution_observed"] == {
            "openai/gpt-4o-mini": 250,
        }
        assert manifest["cost_fraction_bins_observed"] == {
            "[0.0,0.1)": 30,
            "[0.1,0.2)": 10,
        }


# ---------------------------------------------------------------------------
# Phase 6-C — v0.9 provisional manifest gate
# ---------------------------------------------------------------------------


def _v1_manifest(**overrides: object) -> dict[str, object]:
    """A minimal v1-shaped manifest (provisional=false, no gap summary).

    Mirrors the shape that ``build_goldset_manifest`` produces on a
    production freeze: all required keys present, ``provisional=False``,
    ``floor_gap_summary={}``.
    """
    base: dict[str, object] = {
        "dataset_name": "goaljudge_goldset_v1",
        "total_items": 250,
        "dev_count": 50,
        "test_count": 200,
        "test_split_sha256": "deadbeef" * 8,
        "rubric_version": "stage4_confirmed",
        "frozen_at": "2026-06-09T12:00:00Z",
        "stratum_distribution": {},
        "planning_depth_distribution": {"L0": 60, "L1": 100, "L2": 60},
        "tool_cluster_distribution": {},
        "failure_mode_distribution": {},
        "routing_reason_distribution_observed": {},
        "model_tier_distribution_observed": {},
        "cost_fraction_bins_observed": {},
        "goal_met_false_share": 0.8,
        "provisional": False,
        "floor_gap_summary": {},
    }
    base.update(overrides)
    return base


class TestBuildGoldsetManifestProvisional:
    """The manifest builder must emit ``provisional`` + ``floor_gap_summary``
    in every manifest it writes. Without these keys the v0.9/v1 gate has
    nothing to read."""

    def test_default_invocation_emits_v1_shaped_manifest(self) -> None:
        """Calling ``build_goldset_manifest`` with no provisional kwargs
        produces ``provisional=False`` and ``floor_gap_summary={}``. This is
        the production-freeze shape — Stage 6's gate must PASS against it.
        """
        items = [_item("GJ-1", goal_met=False)]
        manifest = build_goldset_manifest(
            items,
            test_split_sha256="abc",
            rubric_version="stage4_confirmed",
            frozen_at="2026-06-09T00:00:00Z",
        )
        assert manifest["provisional"] is False
        assert manifest["floor_gap_summary"] == {}

    def test_provisional_true_with_gap_summary_records_both(self) -> None:
        """When the assembler is run with ``--provisional``, both flags
        flow through into the manifest body verbatim — they're the inputs
        Stage 6's gate reads."""
        items = [_item("GJ-1", goal_met=False)]
        gaps = {"L0": 28, "L1": 56, "L2": 35,
                "web-bound": 16, "wrong-tool": 14}
        manifest = build_goldset_manifest(
            items,
            test_split_sha256="abc",
            rubric_version="stage4_confirmed",
            frozen_at="2026-06-09T00:00:00Z",
            provisional=True,
            floor_gap_summary=gaps,
        )
        assert manifest["provisional"] is True
        assert manifest["floor_gap_summary"] == gaps

    def test_provisional_false_with_nonempty_gap_summary_raises(self) -> None:
        """Refuse the contradictory combination: a v1 manifest (not
        provisional) MUST have an empty gap summary. If callers try to
        ship a v1 with unmet floors, the manifest builder fails loud —
        the gate is a downstream re-check, not the only defense.
        """
        items = [_item("GJ-1", goal_met=False)]
        with pytest.raises(ValueError, match=r"(?i)provisional.*floor_gap"):
            build_goldset_manifest(
                items,
                test_split_sha256="abc",
                rubric_version="stage4_confirmed",
                frozen_at="2026-06-09T00:00:00Z",
                provisional=False,
                floor_gap_summary={"L0": 5},
            )


class TestGateGoldsetV1Floors:
    """Stage 6 calls this before consuming a manifest. The gate FAILS-CLOSED
    on anything that isn't a v1 production freeze:

      * provisional=True (it's v0.9, not v1)
      * floor_gap_summary non-empty (some cell is still under floor)
      * missing required keys (malformed / incomplete manifest)

    Idempotent on a healthy v1 manifest — no side effects, no mutation."""

    # ── Acceptance: clean v1 manifest passes ──────────────────────────────

    def test_v1_manifest_passes_silently(self) -> None:
        """A properly-shaped v1 manifest returns ``None`` and raises
        nothing. The "no return value" contract is intentional — the
        function is a gate, not a query."""
        manifest = _v1_manifest()
        assert gate_goldset_v1_floors(manifest) is None

    # ── Failure 1: provisional=True ───────────────────────────────────────

    def test_provisional_true_raises(self) -> None:
        manifest = _v1_manifest(provisional=True, floor_gap_summary={"L0": 5})
        with pytest.raises(AssemblyInvariantError, match=r"(?i)provisional"):
            gate_goldset_v1_floors(manifest)

    # ── Failure 2: non-empty floor_gap_summary on a non-provisional ──────

    def test_nonempty_gap_summary_raises(self) -> None:
        """Defense-in-depth: the manifest builder rejects this case, but
        if a caller hand-rolled a manifest dict the gate must still catch
        it."""
        manifest = _v1_manifest(
            provisional=False, floor_gap_summary={"web-bound": 16}
        )
        with pytest.raises(AssemblyInvariantError, match=r"(?i)floor"):
            gate_goldset_v1_floors(manifest)

    # ── Failure 3: missing test_split_sha256 ──────────────────────────────

    def test_missing_test_split_sha256_raises(self) -> None:
        """The hash is the WHOLE POINT — a manifest missing it is
        unusable for Stage 6's diff regardless of floor status."""
        manifest = _v1_manifest()
        del manifest["test_split_sha256"]
        with pytest.raises(AssemblyInvariantError, match=r"(?i)test_split_sha256"):
            gate_goldset_v1_floors(manifest)

    # ── Failure 4: blank test_split_sha256 ────────────────────────────────

    def test_blank_test_split_sha256_raises(self) -> None:
        manifest = _v1_manifest(test_split_sha256="")
        with pytest.raises(AssemblyInvariantError, match=r"(?i)test_split_sha256|blank|empty"):
            gate_goldset_v1_floors(manifest)

    # ── Idempotency: repeated calls don't mutate ──────────────────────────

    def test_idempotent_no_side_effects(self) -> None:
        """Calling the gate twice on the same manifest produces the same
        result and never mutates the input dict."""
        manifest = _v1_manifest()
        snapshot = dict(manifest)
        gate_goldset_v1_floors(manifest)
        gate_goldset_v1_floors(manifest)
        assert manifest == snapshot
