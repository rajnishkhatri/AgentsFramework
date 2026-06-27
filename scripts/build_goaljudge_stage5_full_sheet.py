#!/usr/bin/env python3
"""Build the Stage 5 Tier 3 full ~250-item gold-set sheet.

Extends ``build_goaljudge_stage5_pilot_sheet.py`` with:

* **Multi-batch input** — read N batch JSONLs, dedupe by ``case_id`` keeping
  the row from the newest batch (by file mtime).
* **D1 + D5 labels** — compute ``planning_depth`` for each row by calling
  ``components.router.select_planning_depth`` against the prompt, and
  ``tool_cluster`` from the row's ``tool_calls_summary`` (when present) via
  ``services.governance.goaljudge_goldset_dataset.classify_tool_cluster``.
* **Cell-coverage gap report** — per-(D1, D5) gap against the floors locked
  in ``D1_FLOORS`` / ``D5_FLOORS``; emitted at ``--dry-run`` time so Phase 4
  authoring knows which cells need items *before* anyone writes a prompt.
* **Deterministic per-stratum test-split allocator** — synthetic ⇒ dev (the
  firewall), production rows are sorted by ``item_id`` and the first ~40 %
  per stratum land in test. Same input ⇒ same split, so re-running the
  builder against the same data is hash-stable.

The builder lives in ``scripts/`` (outside the four-layer dependency grid)
because it composes ``components/`` (Vertical — the router) and
``services/governance/`` (Horizontal — the firewall + classifier) into a
single produces-CSV step. A ``services/`` module could not import the
router; a ``components/`` module could not own filesystem I/O. ``scripts/``
is the right home.

CLI::

    # Dry-run — only the gap report is written.
    python scripts/build_goaljudge_stage5_full_sheet.py --dry-run \
        --batches cache/goaljudge_eval/ui_batch_gcp_2026-06-09.jsonl,\
                  cache/goaljudge_eval/ui_batch_gcp_confirmation_2026-06-09_v7_full.jsonl

    # Real run — emits CSV + gap report.
    python scripts/build_goaljudge_stage5_full_sheet.py \
        --batches '...' \
        --csv docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv \
        --report cache/goaljudge_eval/goldset_cell_coverage_report.md

NO langgraph / langchain imports (AGENTS.md invariant #4).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from components.router import select_planning_depth
from services.governance.goaljudge_goldset_dataset import (
    CoverageReport,
    classify_tool_cluster,
    compute_cell_coverage,
    project_trajectory_tools,
)

logger = logging.getLogger("scripts.build_goaljudge_stage5_full_sheet")


# Extended FIELDS contract: pilot columns + Phase 3 dimension columns.
# Order is stable so apply_grades scripts that index by header survive.
FIELDS: list[str] = [
    # Identity + sourcing
    "item_id",
    "split",
    "provenance",
    "stratum",  # D8
    "domain",  # D8
    # Pipeline-dimension labels (Phase 3 additions)
    "planning_depth",  # D1
    "tool_cluster",  # D5
    # Task content (carried from pilot)
    "task",
    "claim",
    "evidence_summary",
    # Annotator slots (pilot columns — unchanged)
    "r1_goal_met",
    "r1_graceful_failure",
    "r1_partial_fraction",
    "r1_failure_mode",
    "r2_goal_met",
    "r2_graceful_failure",
    "r2_partial_fraction",
    "r2_failure_mode",
    "adjudicated_goal_met",
    "adjudicated_failure_mode",
    # Provenance
    "rubric_version",
    "note",
]


# ---------------------------------------------------------------------------
# Multi-batch input + dedupe
# ---------------------------------------------------------------------------


def load_and_dedupe_batches(paths: list[Path]) -> list[dict[str, Any]]:
    """Load N batch JSONLs; dedupe by ``case_id`` keeping the newest file.

    "Newest" is determined by ``os.path.getmtime`` — the same signal the
    Playwright batch spec uses to namespace ``ui_batch_${RUN_TAG}.jsonl``
    artifacts on disk. A later batch supersedes earlier batches for any
    overlapping ``case_id``.

    Rows without ``case_id`` are dropped with a warning (defensive: a
    malformed line shouldn't crash the whole build).
    """
    # Walk paths newest-mtime-first so the first row seen for a case wins.
    sorted_paths = sorted(
        (Path(p) for p in paths),
        key=lambda p: os.path.getmtime(p),
        reverse=True,
    )

    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for path in sorted_paths:
        with path.open(encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("skipping malformed jsonl line in %s", path)
                    continue
                cid = row.get("case_id")
                if not cid:
                    logger.warning("row missing case_id in %s: %r", path, line[:80])
                    continue
                if cid in seen:
                    continue  # older batch — drop
                seen.add(cid)
                merged.append(row)
    # Stable ordering so downstream allocator is deterministic regardless
    # of which batch was newest.
    merged.sort(key=lambda r: str(r.get("case_id", "")))
    return merged


# ---------------------------------------------------------------------------
# Corpus sidecar loader (trace_id → projected tool_calls_summary)
# ---------------------------------------------------------------------------


def load_corpus_tool_index(
    corpus_paths: list[Path] | None,
) -> dict[str, list[dict[str, Any]]]:
    """Build a ``{trace_id: tool_calls_summary}`` index from corpus JSONLs.

    The corpus JSONL (``cache/goaljudge_eval/corpus_gcp_*.jsonl``) carries
    one row per Langfuse trace with a ``trajectory`` of step-level spans;
    :func:`project_trajectory_tools` projects each row's ``tool.called``
    spans into the classifier-ready
    ``[{"tool_name", "args_keys"}]`` shape.

    Newest-mtime-first wins on duplicate ``trace_id`` (same convention as
    :func:`load_and_dedupe_batches`) so re-running against multiple
    corpus snapshots is stable.

    When ``corpus_paths`` is ``None`` or empty, returns ``{}`` so callers
    can pass the result unconditionally into :func:`enrich_row_with_dimensions`.
    """
    if not corpus_paths:
        return {}

    sorted_paths = sorted(
        (Path(p) for p in corpus_paths),
        key=lambda p: os.path.getmtime(p),
        reverse=True,
    )

    index: dict[str, list[dict[str, Any]]] = {}
    for path in sorted_paths:
        with path.open(encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("skipping malformed corpus line in %s", path)
                    continue
                trace_id = row.get("trace_id")
                if not trace_id or trace_id in index:
                    continue  # missing id, or older snapshot — skip
                index[trace_id] = project_trajectory_tools(row.get("trajectory"))
    return index


# ---------------------------------------------------------------------------
# Row enrichment with D1 + D5 labels
# ---------------------------------------------------------------------------


def enrich_row_with_dimensions(
    row: dict[str, Any],
    *,
    tool_index: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Compute D1 (planning_depth) and D5 (tool_cluster) for one row.

    ``planning_depth`` is computed by calling ``select_planning_depth``
    against the row's prompt with ``task_tool_results_count=0`` — i.e.
    the *first-step* depth the router would pick, which is the only
    depth the sourcing math cares about (subsequent steps collapse to
    L0 by design, regardless of prompt complexity).

    ``tool_cluster`` precedence (the actual extension):

      1. ``tool_index[row["trace_id"]]`` — corpus-trajectory projection.
         Set by the ``--corpus`` flag.
      2. ``row["tool_calls_summary"]`` — the Phase E.1 enriched
         eval-observation field, when batches start carrying it.
      3. ``[]`` — falls through to ``classify_tool_cluster`` ⇒ "no-tool".

    Order matters: when a future batch carries E.1 enrichment AND a
    corpus row exists, the *corpus* wins because the corpus snapshot is
    the more reliable source (the trajectory is authoritative; the eval
    observation can be stale if the trace was replayed).
    """
    prompt = row.get("prompt", "") or row.get("task", "")
    planning_depth, _reason = select_planning_depth(
        task_input=prompt,
        task_tool_results_count=0,
    )

    trace_id = row.get("trace_id", "")
    if tool_index and trace_id in tool_index:
        tool_calls = tool_index[trace_id]
    else:
        tool_calls = row.get("tool_calls_summary") or []
    tool_cluster = classify_tool_cluster(tool_calls)

    enriched = dict(row)
    enriched["planning_depth"] = planning_depth
    enriched["tool_cluster"] = tool_cluster
    return enriched


# ---------------------------------------------------------------------------
# Deterministic per-stratum test-split allocator
# ---------------------------------------------------------------------------


def allocate_splits(
    rows: list[dict[str, Any]],
    *,
    test_share: float = 0.40,
) -> list[dict[str, Any]]:
    """Assign ``split`` to each row.

    Firewall: ``provenance == "synthetic"`` ⇒ ``split = "dev"`` (the spec
    §9 invariant).

    Production rows are bucketed by stratum, sorted by ``item_id`` within
    each stratum, and the first ``ceil(test_share * |stratum|)`` rows
    land in test. The sort makes the allocation deterministic across
    re-runs and across input order — so the test-split hash (Phase 2) is
    stable.
    """
    by_stratum: dict[str, list[dict[str, Any]]] = {}
    out: list[dict[str, Any]] = []

    for row in rows:
        out_row = dict(row)
        if out_row.get("provenance") == "synthetic":
            out_row["split"] = "dev"
            out.append(out_row)
        elif out_row.get("provenance") == "fresh-authored":
            # Phase 4 test-split backbone — every fresh row is a test candidate.
            out_row["split"] = "test"
            out.append(out_row)
        else:
            by_stratum.setdefault(out_row.get("stratum", ""), []).append(out_row)

    for stratum, items in by_stratum.items():
        items.sort(key=lambda r: str(r.get("item_id", "")))
        test_target = math.ceil(test_share * len(items))
        for i, item in enumerate(items):
            item["split"] = "test" if i < test_target else "dev"
            out.append(item)

    # Stable global ordering of the returned list for predictable callers.
    out.sort(key=lambda r: str(r.get("item_id", "")))
    return out


# ---------------------------------------------------------------------------
# CSV + report serialization
# ---------------------------------------------------------------------------


def _row_for_csv(row: dict[str, Any]) -> dict[str, str]:
    """Project an enriched row down to the FIELDS contract for CSV output."""
    out: dict[str, str] = {f: "" for f in FIELDS}
    for field in FIELDS:
        if field in row:
            value = row[field]
            if value is None:
                out[field] = ""
            elif isinstance(value, (list, dict)):
                out[field] = json.dumps(value)
            else:
                out[field] = str(value)
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(_row_for_csv(row))


def _write_report(path: Path, report: CoverageReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.to_markdown(), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fresh-authored task loader (Phase 4 test-split backbone)
# ---------------------------------------------------------------------------


def fresh_task_to_sheet_row(task: Any) -> dict[str, Any]:
    """Project one :class:`FreshTask` into a builder row dict.

    Fresh tasks are authored synthesis — no Playwright trace. Annotators
    grade from Langfuse when a trace exists; otherwise the prompt + authored
    ``expected_failure_mode`` anchor the row. ``provenance=fresh-authored``
    is the Phase 5 walkthrough contract (distinct from production traces).
    """
    return {
        "case_id": task.id,
        "item_id": task.id,
        "provenance": "fresh-authored",
        "stratum": task.stratum,
        "domain": task.domain,
        "planning_depth": task.expected_planning_depth,
        "tool_cluster": task.expected_tool_cluster,
        "task": task.prompt,
        "prompt": task.prompt,
        "claim": "",
        "evidence_summary": "",
        "rubric_version": "stage4_confirmed",
    }


def load_fresh_task_rows() -> list[dict[str, Any]]:
    """Load ``FRESH_TEST_TASKS`` from the Phase 4 fixture module."""
    from tests.fixtures.goaljudge.fresh_test_tasks import FRESH_TEST_TASKS

    rows = [fresh_task_to_sheet_row(task) for task in FRESH_TEST_TASKS]
    rows.sort(key=lambda r: str(r.get("item_id", "")))
    return rows


# ---------------------------------------------------------------------------
# Builder result + entrypoint
# ---------------------------------------------------------------------------


@dataclass
class BuildResult:
    rows_written: int
    coverage_report: CoverageReport


def build_full_sheet(
    *,
    batch_jsonl_paths: list[Path] | None,
    csv_output: Path,
    report_output: Path,
    dry_run: bool = False,
    corpus_jsonl_paths: list[Path] | None = None,
    include_fresh_tasks: bool = False,
    fresh_only: bool = False,
) -> BuildResult:
    """One-shot full-sheet build with optional dry-run.

    Dry-run writes the gap report only. Real run writes CSV + gap report.
    The gap report is always emitted so a caller can read the cell
    coverage without parsing CSV.

    When ``corpus_jsonl_paths`` is provided, the builder loads the
    corpus sidecar(s) (the on-disk ``corpus_gcp_*.jsonl`` snapshots
    keyed by ``trace_id``) and projects each row's ``trajectory``
    tool-spans into the classifier-ready shape, joined onto UI-batch
    rows by ``trace_id``. Without it, behavior is byte-identical to
    today (every prod row falls to ``no-tool``).
    """
    if fresh_only:
        merged: list[dict[str, Any]] = []
    else:
        merged = load_and_dedupe_batches(batch_jsonl_paths or [])

    tool_index = load_corpus_tool_index(corpus_jsonl_paths)
    enriched = [
        enrich_row_with_dimensions(row, tool_index=tool_index) for row in merged
    ]
    enriched = _apply_default_metadata(enriched)

    if include_fresh_tasks or fresh_only:
        fresh_rows = load_fresh_task_rows()
        seen_ids = {str(r.get("item_id", "")) for r in enriched}
        for row in fresh_rows:
            if row["item_id"] not in seen_ids:
                enriched.append(row)
                seen_ids.add(row["item_id"])

    allocated = allocate_splits(enriched)

    report = compute_cell_coverage(allocated)
    _write_report(report_output, report)

    rows_written = 0
    if not dry_run:
        _write_csv(csv_output, allocated)
        rows_written = len(allocated)

    return BuildResult(rows_written=rows_written, coverage_report=report)


def _apply_default_metadata(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fill ``item_id``, ``provenance``, ``stratum`` / ``domain`` defaults
    from the registry. Batch JSONLs carry ``case_id`` but not item_id /
    split / provenance — those are sourcing-level fields the builder owns.
    """
    try:
        from tests.fixtures.goaljudge.case_registry import CASE_BY_ID
    except ImportError:  # pragma: no cover - registry should always import
        CASE_BY_ID = {}

    out: list[dict[str, Any]] = []
    for row in rows:
        out_row = dict(row)
        case_id = out_row.get("case_id", "")
        out_row.setdefault("item_id", case_id)
        out_row.setdefault("provenance", "production")
        if "stratum" not in out_row or "domain" not in out_row:
            registry = CASE_BY_ID.get(case_id)
            if registry is not None:
                out_row.setdefault(
                    "stratum", getattr(registry, "stratum", "representative")
                )
                out_row.setdefault("domain", getattr(registry, "domain", "composite"))
            else:
                out_row.setdefault("stratum", "representative")
                out_row.setdefault("domain", "composite")
        out_row.setdefault("rubric_version", "stage4_confirmed")
        out_row.setdefault("task", out_row.get("prompt", ""))
        out_row.setdefault("claim", (out_row.get("response_text", "") or "")[:500])
        out.append(out_row)
    return out


def _parse_paths_arg(value: str) -> list[Path]:
    """Comma-separated paths or a directory containing batch JSONLs."""
    parts = [p.strip() for p in value.split(",") if p.strip()]
    out: list[Path] = []
    for part in parts:
        p = Path(part)
        if p.is_dir():
            out.extend(sorted(p.glob("ui_batch_*.jsonl")))
        else:
            out.append(p)
    return out


def _parse_corpus_arg(value: str) -> list[Path]:
    """Comma-separated paths or a directory containing corpus JSONLs.

    Mirrors :func:`_parse_paths_arg` but expands a directory to
    ``corpus_*.jsonl`` (not ``ui_batch_*.jsonl``)."""
    parts = [p.strip() for p in value.split(",") if p.strip()]
    out: list[Path] = []
    for part in parts:
        p = Path(part)
        if p.is_dir():
            out.extend(sorted(p.glob("corpus_*.jsonl")))
        else:
            out.append(p)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batches",
        default=None,
        help="Comma-separated paths to batch JSONLs (or a directory). "
        "Optional when --fresh-only is set.",
    )
    parser.add_argument(
        "--csv",
        default=str(
            REPO_ROOT
            / "docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv"
        ),
        help="CSV output path (skipped in --dry-run).",
    )
    parser.add_argument(
        "--report",
        default=str(REPO_ROOT / "cache/goaljudge_eval/goldset_cell_coverage_report.md"),
        help="Gap-report output path (always written).",
    )
    parser.add_argument(
        "--corpus",
        default=None,
        help=(
            "Optional comma-separated paths to corpus JSONLs (or a "
            "directory of corpus_gcp_*.jsonl). When set, D5 (tool_cluster) "
            "for each UI-batch row is derived from the corpus trajectory "
            "tool-spans joined by trace_id."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit only the gap report; do not write CSV.",
    )
    parser.add_argument(
        "--fresh-tasks",
        "--include-fresh-tasks",
        dest="fresh_tasks",
        action="store_true",
        help="Merge FRESH_TEST_TASKS from tests/fixtures/goaljudge/fresh_test_tasks.py.",
    )
    parser.add_argument(
        "--fresh-only",
        action="store_true",
        help="Emit only fresh-authored rows (Phase 5 labeling sheet; skips batches).",
    )
    args = parser.parse_args(argv)

    if args.fresh_only:
        args.fresh_tasks = True

    paths: list[Path] = _parse_paths_arg(args.batches) if args.batches else []
    if not paths and not args.fresh_tasks:
        parser.error(
            "no batch JSONLs found — pass --batches or use --fresh-tasks / --fresh-only"
        )

    corpus_paths = _parse_corpus_arg(args.corpus) if args.corpus else None

    result = build_full_sheet(
        batch_jsonl_paths=paths or None,
        csv_output=Path(args.csv),
        report_output=Path(args.report),
        dry_run=args.dry_run,
        corpus_jsonl_paths=corpus_paths,
        include_fresh_tasks=args.fresh_tasks,
        fresh_only=args.fresh_only,
    )

    mode = "DRY-RUN" if args.dry_run else "WROTE"
    print(
        f"{mode}: {result.rows_written} rows, "
        f"D1 gaps={result.coverage_report.d1_gaps}, "
        f"D5 gaps={result.coverage_report.d5_gaps}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
