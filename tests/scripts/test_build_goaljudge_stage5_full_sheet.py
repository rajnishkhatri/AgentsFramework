"""L2 contract tests for ``scripts/build_goaljudge_stage5_full_sheet.py``.

Pyramid layer:  L2 Reproducible
Architecture:   ``scripts/`` (outside the four-layer grid — composes
                ``components/router`` (Vertical) + ``services/governance``
                (Horizontal) into a CSV+report producer).
TDD protocol:   B — Contract-Driven TDD (failure paths first, deterministic
                fixtures, no live LLM, no Langfuse SDK).

Anti-patterns guarded against:

* AP-1 Tautological — fixtures are tiny hand-written JSONL rows with
  known expected D1/D5 outputs; the test never re-invokes the classifier
  to compute its own expected value.
* AP-2 Mock addiction — ``select_planning_depth`` is deterministic, so
  it is called for real (not mocked). The only filesystem isolation is
  ``tmp_path``.
* AP-5 Live LLM in CI — zero LLM calls; the builder is pure data.
* AP-6 Gap blindness — every contract has a failure-path test before
  the happy-path test.
* AP-7 Dependency leak — this test imports only from ``scripts/`` (the
  builder) and ``services.governance.goaljudge_goldset_dataset``; it
  does **not** import from ``components/`` (that would couple this L2
  test to L3 internals).
"""

from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path

import pytest

from services.governance.goaljudge_goldset_dataset import (
    CELL_TOOL_CLUSTERS,
    D1_FLOORS,
    D5_FLOORS,
    STRATA_SHARES,
)


pytestmark = pytest.mark.usefixtures("_isolate_cwd")


@pytest.fixture
def _isolate_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Run each test from a tmp dir so the builder's report-output paths
    are sandboxed even if the builder reads ``cwd`` for outputs.
    """
    monkeypatch.chdir(tmp_path)
    yield


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _batch_row(
    case_id: str,
    *,
    trace_id: str = "trace-x",
    prompt: str = "do the thing",
    response_text: str = "did it",
    target_code: str = "fabricated-progress",
    target_axes: dict | None = None,
) -> dict:
    """One row from a Playwright batch JSONL (matches the on-disk shape)."""
    return {
        "case_id": case_id,
        "trace_id": trace_id,
        "prompt": prompt,
        "response_text": response_text,
        "target_code": target_code,
        "target_axes": target_axes or {"goal_met": False, "partial_fraction": 0.0},
        "outcome": "pass",
        "screenshot_path": "/tmp/x.png",
        "session_id": "sess-1",
        "thread_title": case_id,
    }


def _write_batch(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _set_mtime(path: Path, when: float) -> None:
    os.utime(path, (when, when))


# ---------------------------------------------------------------------------
# Failure-path contract tests (RED-first)
# ---------------------------------------------------------------------------


class TestMultiBatchDedupe:
    """The builder reads multiple batch JSONLs and may see the same
    case_id in more than one. The contract: keep the *newest* (by file
    mtime), drop the older.
    """

    def test_stale_row_does_not_leak_when_newer_batch_present(
        self, tmp_path: Path
    ) -> None:
        from scripts.build_goaljudge_stage5_full_sheet import (
            load_and_dedupe_batches,
        )

        older = tmp_path / "ui_batch_old.jsonl"
        newer = tmp_path / "ui_batch_new.jsonl"
        _write_batch(older, [
            _batch_row("GJ-001", trace_id="OLD", response_text="stale claim")
        ])
        _write_batch(newer, [
            _batch_row("GJ-001", trace_id="NEW", response_text="fresh claim")
        ])
        _set_mtime(older, time.time() - 3600)  # 1 hour old
        _set_mtime(newer, time.time())          # now

        rows = load_and_dedupe_batches([older, newer])

        # Only ONE row for GJ-001, and it must be the newer one.
        gj001 = [r for r in rows if r["case_id"] == "GJ-001"]
        assert len(gj001) == 1
        assert gj001[0]["trace_id"] == "NEW"
        assert gj001[0]["response_text"] == "fresh claim"

    def test_dedupe_preserves_unique_case_ids_across_batches(
        self, tmp_path: Path
    ) -> None:
        from scripts.build_goaljudge_stage5_full_sheet import (
            load_and_dedupe_batches,
        )

        a = tmp_path / "ui_batch_a.jsonl"
        b = tmp_path / "ui_batch_b.jsonl"
        _write_batch(a, [_batch_row("GJ-001")])
        _write_batch(b, [_batch_row("GJ-002")])

        rows = load_and_dedupe_batches([a, b])
        case_ids = sorted(r["case_id"] for r in rows)
        assert case_ids == ["GJ-001", "GJ-002"]


class TestFirewallAtWrite:
    """The firewall (synthetic ⇒ dev) must be asserted at builder
    output time, not just at GoldsetItem construction time. Otherwise a
    bug in the allocator could write a CSV that crashes Phase 6.
    """

    def test_synthetic_row_lands_on_dev_split(self, tmp_path: Path) -> None:
        from scripts.build_goaljudge_stage5_full_sheet import (
            allocate_splits,
        )

        rows = [
            {
                "item_id": "GS-S-001",
                "provenance": "synthetic",
                "stratum": "representative",
                "planning_depth": "L0",
                "tool_cluster": "file-only",
            }
        ]
        allocated = allocate_splits(rows)
        assert allocated[0]["split"] == "dev"

    def test_synthetic_row_never_lands_on_test_split(
        self, tmp_path: Path
    ) -> None:
        """Defense in depth: even with 100 synthetic items in a stratum
        whose test target is 40, none of them may end up in test."""
        from scripts.build_goaljudge_stage5_full_sheet import (
            allocate_splits,
        )

        rows = [
            {
                "item_id": f"GS-S-{i:03d}",
                "provenance": "synthetic",
                "stratum": "representative",
                "planning_depth": "L0",
                "tool_cluster": "file-only",
            }
            for i in range(100)
        ]
        allocated = allocate_splits(rows)
        assert all(r["split"] == "dev" for r in allocated)


class TestDeterministicAllocator:
    """The test-split allocator must be deterministic: same inputs in any
    order ⇒ same split assignment. Otherwise re-running the builder
    against the same data would shift the test-split hash."""

    def _prod_rows(self, n: int) -> list[dict]:
        return [
            {
                "item_id": f"GJ-P-{i:03d}",
                "provenance": "production",
                "stratum": "representative",
                "planning_depth": "L0",
                "tool_cluster": "file-only",
            }
            for i in range(n)
        ]

    def test_allocator_is_deterministic_across_input_order(self) -> None:
        from scripts.build_goaljudge_stage5_full_sheet import (
            allocate_splits,
        )

        rows = self._prod_rows(20)
        reversed_rows = list(reversed(rows))

        forward = allocate_splits(rows)
        backward = allocate_splits(reversed_rows)

        # Compare split assignments by item_id, ignoring list order.
        f_by_id = {r["item_id"]: r["split"] for r in forward}
        b_by_id = {r["item_id"]: r["split"] for r in backward}
        assert f_by_id == b_by_id

    def test_allocator_respects_per_stratum_test_share(self) -> None:
        """With 100 prod rows in one stratum, ≈ 40 % should end up in test
        per spec §6 (rep target = 40 in 100-item stratum)."""
        from scripts.build_goaljudge_stage5_full_sheet import (
            allocate_splits,
        )

        rows = self._prod_rows(100)
        allocated = allocate_splits(rows)
        test_count = sum(1 for r in allocated if r["split"] == "test")
        assert 35 <= test_count <= 45  # 40 ± 5 tolerance for rounding


class TestBuilderCLI:
    """End-to-end contract tests for the ``build_full_sheet`` entrypoint.
    These prove the CLI produces the right artifacts; they don't recompute
    the classifier or the allocator (those have their own tests above).
    """

    def test_dry_run_emits_gap_report_does_not_write_csv(
        self, tmp_path: Path
    ) -> None:
        from scripts.build_goaljudge_stage5_full_sheet import build_full_sheet

        batch = tmp_path / "batches" / "ui_batch_x.jsonl"
        _write_batch(batch, [_batch_row("GJ-001"), _batch_row("GJ-002")])

        csv_out = tmp_path / "out_sheet.csv"
        report_out = tmp_path / "out_report.md"

        result = build_full_sheet(
            batch_jsonl_paths=[batch],
            csv_output=csv_out,
            report_output=report_out,
            dry_run=True,
        )

        # The report MUST be written even in dry run.
        assert report_out.exists()
        assert "Stage 5 Tier 3 cell-coverage gap report" in report_out.read_text()
        # The CSV MUST NOT be written in dry run.
        assert not csv_out.exists()
        # The result carries the gap counts so a caller can act on them.
        assert result.coverage_report is not None

    def test_real_run_writes_csv_with_extended_fields(
        self, tmp_path: Path
    ) -> None:
        from scripts.build_goaljudge_stage5_full_sheet import (
            FIELDS,
            build_full_sheet,
        )

        batch = tmp_path / "batches" / "ui_batch_x.jsonl"
        _write_batch(batch, [_batch_row("GJ-001"), _batch_row("GJ-002")])

        csv_out = tmp_path / "out_sheet.csv"
        report_out = tmp_path / "out_report.md"

        build_full_sheet(
            batch_jsonl_paths=[batch],
            csv_output=csv_out,
            report_output=report_out,
            dry_run=False,
        )

        assert csv_out.exists()
        with csv_out.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
            written = list(reader)
        # The extended-FIELDS contract is locked: D1, D5 cluster, D7 must
        # all appear as columns so Phase 5 labelers can see the cell.
        for required in ("planning_depth", "tool_cluster", "stratum", "item_id"):
            assert required in header, f"{required!r} missing from CSV header"
        # At least one row per known case made it in.
        case_ids = {r["item_id"] for r in written}
        assert "GJ-001" in case_ids
        assert "GJ-002" in case_ids

    def test_builder_computes_planning_depth_for_prod_rows(
        self, tmp_path: Path
    ) -> None:
        """For production-trace rows, the builder must compute D1 by
        calling ``select_planning_depth`` against the registry prompt —
        this is the D1 oracle hook that keeps the gold set aligned with
        production routing behavior. A row whose prompt is complex enough
        to trigger L1+ must NOT be tagged L0.
        """
        from scripts.build_goaljudge_stage5_full_sheet import (
            FIELDS,
            build_full_sheet,
        )

        # This prompt has all the heuristic triggers for L2:
        # multi-part marker ("compare"), conjunction ("and"), enumeration.
        complex_prompt = (
            "Compare the three approaches in design.md, "
            "(1) read the file, "
            "(2) summarize trade-offs, "
            "and (3) recommend one."
        )
        batch = tmp_path / "batches" / "ui_batch.jsonl"
        _write_batch(batch, [_batch_row("GJ-001", prompt=complex_prompt)])

        csv_out = tmp_path / "sheet.csv"
        report_out = tmp_path / "report.md"

        build_full_sheet(
            batch_jsonl_paths=[batch],
            csv_output=csv_out,
            report_output=report_out,
            dry_run=False,
        )

        with csv_out.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        gj001 = [r for r in rows if r["item_id"] == "GJ-001"][0]
        # NOT L0 — the heuristic must have escalated.
        assert gj001["planning_depth"] in ("L1", "L2"), (
            f"router did not escalate: planning_depth={gj001['planning_depth']!r}"
        )


class TestExtendedFieldsContract:
    """The Phase 3 builder extends the pilot's FIELDS contract with
    pipeline-dimension columns. This is the consumer-driven contract test
    (Pattern 4): if a future builder change drops one of these columns,
    Phase 5 labelers and Phase 6 assemble would silently lose dimension
    coverage — these tests guard the boundary.
    """

    def test_fields_includes_all_phase3_dimension_columns(self) -> None:
        from scripts.build_goaljudge_stage5_full_sheet import FIELDS

        # D1 + D5 + D7 + D8 must be present.
        for required in (
            "planning_depth",  # D1
            "tool_cluster",    # D5
            "stratum",         # D8
            "domain",          # D8
            "provenance",
            "split",
            "item_id",
        ):
            assert required in FIELDS, f"FIELDS missing {required!r}"

    def test_fields_preserves_pilot_labeling_columns(self) -> None:
        """Backward compat: the pilot's r1/r2/adjudicated columns must
        survive into the full sheet so existing apply_grades scripts
        still work."""
        from scripts.build_goaljudge_stage5_full_sheet import FIELDS

        for required in (
            "r1_goal_met", "r1_partial_fraction", "r1_failure_mode",
            "r2_goal_met", "r2_partial_fraction", "r2_failure_mode",
            "adjudicated_goal_met", "adjudicated_failure_mode",
        ):
            assert required in FIELDS, f"FIELDS missing pilot column {required!r}"


# ---------------------------------------------------------------------------
# Sidecar-corpus join contract tests (the actual extension)
# ---------------------------------------------------------------------------


def _corpus_row(
    trace_id: str,
    *,
    tool_calls: list[tuple[str, str]],
) -> dict:
    """One row from a corpus JSONL with a minimal trajectory.

    ``tool_calls`` is a list of ``(tool_name, args_dict_repr)`` pairs;
    each becomes a ``tool.called`` span in the trajectory. The
    ``args_dict_repr`` mimics the on-disk shape — a *stringified Python
    dict* (single-quoted) so the projection's ``ast.literal_eval``
    fallback path is exercised by the L2 test as well as the L1 test.
    """
    trajectory = [
        {
            "name": "tool.called",
            "input": {
                "details": {
                    "tool": tool_name,
                    "args": args_repr,
                    "cached": "False",
                }
            },
        }
        for tool_name, args_repr in tool_calls
    ]
    return {
        "trace_id": trace_id,
        "task_input": "irrelevant",
        "final_answer": "irrelevant",
        "trajectory": trajectory,
        "outcome": "partial",
        "goal_met": False,
    }


class TestFreshTaskMerge:
    """Phase 4/5 extension: ``--fresh-tasks`` rolls ``FRESH_TEST_TASKS`` into
    the sheet; ``--fresh-only`` skips batch JSONLs for the 79-row Phase 5
    labeling corpus."""

    def test_fresh_only_writes_seventy_nine_gj_f_rows(
        self, tmp_path: Path
    ) -> None:
        from scripts.build_goaljudge_stage5_full_sheet import build_full_sheet

        csv_out = tmp_path / "sheet.csv"
        report_out = tmp_path / "report.md"

        result = build_full_sheet(
            batch_jsonl_paths=None,
            csv_output=csv_out,
            report_output=report_out,
            dry_run=False,
            include_fresh_tasks=True,
            fresh_only=True,
        )

        assert result.rows_written == 79
        with csv_out.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 79
        assert all(r["item_id"].startswith("GJ-F-") for r in rows)
        assert all(r["provenance"] == "fresh-authored" for r in rows)
        assert all(r["split"] == "test" for r in rows)
        assert all(r["r1_goal_met"] == "" and r["r2_goal_met"] == "" for r in rows)
        assert all(r["stratum"] for r in rows)

    def test_fresh_tasks_merge_appended_after_batch_rows(
        self, tmp_path: Path
    ) -> None:
        from scripts.build_goaljudge_stage5_full_sheet import build_full_sheet

        batch = tmp_path / "ui_batch.jsonl"
        _write_batch(batch, [_batch_row("GJ-001")])

        csv_out = tmp_path / "sheet.csv"
        report_out = tmp_path / "report.md"

        result = build_full_sheet(
            batch_jsonl_paths=[batch],
            csv_output=csv_out,
            report_output=report_out,
            dry_run=False,
            include_fresh_tasks=True,
            fresh_only=False,
        )

        assert result.rows_written == 80  # 1 prod + 79 fresh
        with csv_out.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        gj_f = [r for r in rows if r["item_id"].startswith("GJ-F-")]
        assert len(gj_f) == 79


class TestCorpusSidecarJoin:
    """The Tier 3 extension: when ``--corpus`` is supplied, the builder
    loads corpus JSONLs, indexes by ``trace_id``, and joins
    projected tool_calls_summary onto each UI-batch row before D5
    classification. Without ``--corpus``, behavior is byte-identical
    to today (regression guard).

    Contract:

      1. ``--corpus`` unset  ⇒ D5 stays ``no-tool`` for prod rows
         (today's behavior; we don't want a silent regression).
      2. ``--corpus`` set + ``trace_id`` matches  ⇒ D5 reflects the
         projected cluster (the whole point of the extension).
      3. ``--corpus`` set + ``trace_id`` absent   ⇒ D5 falls through
         to ``no-tool`` (defensive join — a corpus snapshot need not
         cover every UI batch row).
    """

    def test_corpus_unset_preserves_no_tool_default(
        self, tmp_path: Path
    ) -> None:
        """Regression guard: today's behavior must survive."""
        from scripts.build_goaljudge_stage5_full_sheet import build_full_sheet

        batch = tmp_path / "ui_batch.jsonl"
        _write_batch(batch, [_batch_row("GJ-X", trace_id="trace-x")])
        csv_out = tmp_path / "sheet.csv"
        report_out = tmp_path / "report.md"

        build_full_sheet(
            batch_jsonl_paths=[batch],
            csv_output=csv_out,
            report_output=report_out,
            dry_run=False,
            corpus_jsonl_paths=None,
        )

        with csv_out.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        gjx = next(r for r in rows if r["item_id"] == "GJ-X")
        # No corpus, no tool_calls_summary on the row ⇒ classifier falls
        # back to "no-tool". This is today's behavior — guard against
        # silent regression.
        assert gjx["tool_cluster"] == "no-tool"

    def test_corpus_match_shifts_cluster_off_no_tool(
        self, tmp_path: Path
    ) -> None:
        """The point of the extension: when the corpus carries a
        ``tool.called`` span for the row's ``trace_id``, D5 reflects the
        projected cluster, not the bare-batch ``no-tool`` default."""
        from scripts.build_goaljudge_stage5_full_sheet import build_full_sheet

        # Batch row + matching corpus row by trace_id.
        batch = tmp_path / "ui_batch.jsonl"
        _write_batch(batch, [_batch_row("GJ-Y", trace_id="trace-match")])

        corpus = tmp_path / "corpus.jsonl"
        _write_batch(corpus, [
            _corpus_row(
                "trace-match",
                tool_calls=[
                    ("file_io", "{'path': '/x', 'operation': 'read'}"),
                    ("web_search", "{'query': 'weather'}"),
                ],
            ),
        ])

        csv_out = tmp_path / "sheet.csv"
        report_out = tmp_path / "report.md"

        build_full_sheet(
            batch_jsonl_paths=[batch],
            csv_output=csv_out,
            report_output=report_out,
            dry_run=False,
            corpus_jsonl_paths=[corpus],
        )

        with csv_out.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        gjy = next(r for r in rows if r["item_id"] == "GJ-Y")
        # file_io + web_search ⇒ two distinct families ⇒ compose.
        # Drift-guard: re-implementing the classifier here would be
        # AP-1 tautological — instead, we assert the cluster is no
        # longer "no-tool" and is exactly the family-mix answer the L1
        # classifier test pins (compose).
        assert gjy["tool_cluster"] != "no-tool", (
            "corpus join did not change cluster — projection or join broken"
        )
        assert gjy["tool_cluster"] == "compose"

    def test_corpus_miss_falls_through_to_no_tool(
        self, tmp_path: Path
    ) -> None:
        """Defensive join: a UI-batch row whose ``trace_id`` is NOT in
        any provided corpus must NOT crash; it must classify as
        ``no-tool`` so the builder is safe to run with a partial-corpus
        sidecar (e.g. a corpus snapshot exported before the latest
        batch ran)."""
        from scripts.build_goaljudge_stage5_full_sheet import build_full_sheet

        batch = tmp_path / "ui_batch.jsonl"
        _write_batch(batch, [_batch_row("GJ-Z", trace_id="trace-absent")])

        # Corpus has a different trace_id — the join misses.
        corpus = tmp_path / "corpus.jsonl"
        _write_batch(corpus, [
            _corpus_row(
                "trace-other",
                tool_calls=[("shell", "{'command': 'ls'}")],
            ),
        ])

        csv_out = tmp_path / "sheet.csv"
        report_out = tmp_path / "report.md"

        # Must not raise.
        build_full_sheet(
            batch_jsonl_paths=[batch],
            csv_output=csv_out,
            report_output=report_out,
            dry_run=False,
            corpus_jsonl_paths=[corpus],
        )

        with csv_out.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        gjz = next(r for r in rows if r["item_id"] == "GJ-Z")
        # Defensive: trace_id miss ⇒ no-tool, not crash, not stale
        # "shell-bound" leaked from the other trace.
        assert gjz["tool_cluster"] == "no-tool"
