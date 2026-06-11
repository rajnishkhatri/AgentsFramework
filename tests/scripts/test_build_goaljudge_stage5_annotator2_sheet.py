"""Contract tests for the cold-blind A2 sheet builder.

Phase 5 / A2 plan §6 — the builder must produce an `annotator2_sheet.csv` that:

- Carries r2_* label columns and r2_review_* columns ONLY (no r1_*, no
  adjudicated_* — those would leak A1 information into A2's cold-blind round).
- Carries one row per item_id in the source full sheet, in order.
- Populates `evidence_summary` from the SHARED corpus/UI evidence (not from A1's
  recorded notes — derive independently to avoid prose leakage).
- Leaves every r2_* label cell BLANK (A2 fills them by hand).
- Mirrors the source sheet's `item_id`, `split`, `provenance`, `stratum`,
  `domain`, `task` so the row contract still joins back to the full sheet at
  the α merge step.
"""
from __future__ import annotations

import csv
import json
import sys
import tempfile
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.build_goaljudge_stage5_annotator2_sheet import build_a2_sheet


def _tool_called_span(tool: str) -> dict:
    return {
        "name": "tool.called",
        "input": {"details": {"tool": tool, "args": "{'path': '/workspace/x'}"}},
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _write_full_sheet(path: Path, rows: list[dict]) -> None:
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _sample_full_sheet_row(item_id: str, **overrides) -> dict:
    base = {
        "item_id": item_id,
        "split": "test",
        "provenance": "fresh-authored",
        "stratum": "representative",
        "domain": "file_io",
        "planning_depth": "L1",
        "tool_cluster": "file-only",
        "task": "Read /workspace/input.txt and report the contents.",
        "claim": "A1 PRE-FILLED CLAIM — MUST NOT LEAK",
        "evidence_summary": "A1 EVIDENCE NOTES — MUST NOT LEAK",
        "r1_goal_met": "true",
        "r1_graceful_failure": "false",
        "r1_partial_fraction": "1",
        "r1_failure_mode": "",
        "r2_goal_met": "",
        "r2_graceful_failure": "",
        "r2_partial_fraction": "",
        "r2_failure_mode": "",
        "adjudicated_goal_met": "",
        "adjudicated_failure_mode": "",
        "rubric_version": "",
        "note": "stage4_confirmed",
    }
    base.update(overrides)
    return base


class TestA2SheetSchema:
    """The output sheet must NOT carry A1 or adjudicator columns."""

    def _build(self) -> tuple[Path, Path]:
        tmp = Path(tempfile.mkdtemp())
        item_id = "GJ-F-002"
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, item_id).hex
        full_sheet_path = tmp / "full.csv"
        batch_path = tmp / "batch.jsonl"
        corpus_path = tmp / "corpus.jsonl"
        out_path = tmp / "a2.csv"

        _write_full_sheet(full_sheet_path, [_sample_full_sheet_row(item_id)])
        _write_jsonl(
            batch_path,
            [
                {
                    "case_id": item_id,
                    "trace_id": trace_id,
                    "outcome": "pass",
                    "response_text": "Using tools: file_io… contents reported.",
                    "tool_card_count": 1,
                }
            ],
        )
        _write_jsonl(
            corpus_path,
            [
                {
                    "trace_id": trace_id,
                    "final_answer": "I read the file and report its contents.",
                    "trajectory": [_tool_called_span("file_io")],
                }
            ],
        )

        build_a2_sheet(
            full_sheet_path=full_sheet_path,
            batch_path=batch_path,
            corpus_path=corpus_path,
            output_path=out_path,
        )
        return out_path, tmp

    def test_output_has_no_r1_columns(self) -> None:
        out_path, _ = self._build()
        with out_path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            cols = reader.fieldnames or []
        leaked = [c for c in cols if c.startswith("r1_")]
        assert not leaked, f"A1 label columns leaked into A2 sheet: {leaked}"

    def test_output_has_no_adjudicated_columns(self) -> None:
        out_path, _ = self._build()
        with out_path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            cols = reader.fieldnames or []
        leaked = [c for c in cols if c.startswith("adjudicated_")]
        assert not leaked, f"adjudicator columns leaked into A2 sheet: {leaked}"

    def test_output_has_r2_label_columns(self) -> None:
        out_path, _ = self._build()
        with out_path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            cols = set(reader.fieldnames or [])
        required = {
            "r2_goal_met",
            "r2_graceful_failure",
            "r2_partial_fraction",
            "r2_failure_mode",
        }
        missing = required - cols
        assert not missing, f"r2_* label columns missing: {missing}"

    def test_output_has_r2_review_text_columns(self) -> None:
        out_path, _ = self._build()
        with out_path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            cols = set(reader.fieldnames or [])
        required = {"r2_review_assessment", "r2_review_open_question"}
        missing = required - cols
        assert not missing, f"r2 review-text columns missing: {missing}"


class TestA2BlindnessFirewall:
    """A1 prose written into the full sheet must never appear in the A2 output."""

    def test_a1_claim_does_not_leak_into_evidence_summary(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        item_id = "GJ-F-002"
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, item_id).hex
        full_sheet_path = tmp / "full.csv"
        batch_path = tmp / "batch.jsonl"
        corpus_path = tmp / "corpus.jsonl"
        out_path = tmp / "a2.csv"

        leak_marker = "ZZZ_A1_NOTE_LEAK_MARKER_ZZZ"
        _write_full_sheet(
            full_sheet_path,
            [
                _sample_full_sheet_row(
                    item_id,
                    claim=f"A1 said: {leak_marker}",
                    evidence_summary=f"A1 evidence notes: {leak_marker}",
                )
            ],
        )
        _write_jsonl(
            batch_path,
            [
                {
                    "case_id": item_id,
                    "trace_id": trace_id,
                    "outcome": "pass",
                    "response_text": "Using tools: file_io… contents reported.",
                    "tool_card_count": 1,
                }
            ],
        )
        _write_jsonl(
            corpus_path,
            [
                {
                    "trace_id": trace_id,
                    "final_answer": "I read the file and report its contents.",
                    "trajectory": [_tool_called_span("file_io")],
                }
            ],
        )

        build_a2_sheet(
            full_sheet_path=full_sheet_path,
            batch_path=batch_path,
            corpus_path=corpus_path,
            output_path=out_path,
        )

        with out_path.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        for row in rows:
            for col, val in row.items():
                assert leak_marker not in (val or ""), (
                    f"A1 prose leaked into column {col!r}: {val!r}"
                )

    def test_r2_label_cells_are_blank_pre_labeling(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        item_id = "GJ-F-002"
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, item_id).hex
        full_sheet_path = tmp / "full.csv"
        batch_path = tmp / "batch.jsonl"
        corpus_path = tmp / "corpus.jsonl"
        out_path = tmp / "a2.csv"

        _write_full_sheet(full_sheet_path, [_sample_full_sheet_row(item_id)])
        _write_jsonl(
            batch_path,
            [
                {
                    "case_id": item_id,
                    "trace_id": trace_id,
                    "outcome": "pass",
                    "response_text": "Using tools: file_io… contents reported.",
                    "tool_card_count": 1,
                }
            ],
        )
        _write_jsonl(
            corpus_path,
            [
                {
                    "trace_id": trace_id,
                    "final_answer": "I read the file and report its contents.",
                    "trajectory": [_tool_called_span("file_io")],
                }
            ],
        )

        build_a2_sheet(
            full_sheet_path=full_sheet_path,
            batch_path=batch_path,
            corpus_path=corpus_path,
            output_path=out_path,
        )

        with out_path.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        for row in rows:
            for col in (
                "r2_goal_met",
                "r2_graceful_failure",
                "r2_partial_fraction",
                "r2_failure_mode",
                "r2_review_assessment",
                "r2_review_open_question",
            ):
                assert row[col] == "", (
                    f"{col!r} must be blank pre-labeling, got {row[col]!r}"
                )


class TestA2RowContract:
    """Row count + identity must match the source full sheet."""

    def test_row_count_matches_source(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        ids = [f"GJ-F-{n:03d}" for n in (1, 2, 6, 14)]
        full_sheet_path = tmp / "full.csv"
        batch_path = tmp / "batch.jsonl"
        corpus_path = tmp / "corpus.jsonl"
        out_path = tmp / "a2.csv"

        _write_full_sheet(
            full_sheet_path, [_sample_full_sheet_row(iid) for iid in ids]
        )
        batch_rows = []
        corpus_rows = []
        for iid in ids:
            trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, iid).hex
            batch_rows.append(
                {
                    "case_id": iid,
                    "trace_id": trace_id,
                    "outcome": "pass",
                    "response_text": "Using tools: file_io… done.",
                    "tool_card_count": 1,
                }
            )
            corpus_rows.append(
                {
                    "trace_id": trace_id,
                    "final_answer": "did the thing.",
                    "trajectory": [_tool_called_span("file_io")],
                }
            )
        _write_jsonl(batch_path, batch_rows)
        _write_jsonl(corpus_path, corpus_rows)

        build_a2_sheet(
            full_sheet_path=full_sheet_path,
            batch_path=batch_path,
            corpus_path=corpus_path,
            output_path=out_path,
        )

        with out_path.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == len(ids)
        assert [r["item_id"] for r in rows] == ids

    def test_evidence_summary_derived_from_corpus_not_source_sheet(self) -> None:
        """The A1 sheet's evidence_summary may carry A1-written prose. The A2
        sheet must derive evidence_summary from the corpus/batch independently
        so we know A1 prose did not leak."""
        tmp = Path(tempfile.mkdtemp())
        item_id = "GJ-F-002"
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, item_id).hex
        full_sheet_path = tmp / "full.csv"
        batch_path = tmp / "batch.jsonl"
        corpus_path = tmp / "corpus.jsonl"
        out_path = tmp / "a2.csv"

        _write_full_sheet(
            full_sheet_path,
            [
                _sample_full_sheet_row(
                    item_id, evidence_summary="A1 SAYS_THIS_IS_GOOD"
                )
            ],
        )
        _write_jsonl(
            batch_path,
            [
                {
                    "case_id": item_id,
                    "trace_id": trace_id,
                    "outcome": "pass",
                    "response_text": "Using tools: file_io… contents reported.",
                    "tool_card_count": 1,
                }
            ],
        )
        _write_jsonl(
            corpus_path,
            [
                {
                    "trace_id": trace_id,
                    "final_answer": "I read the file and report its contents.",
                    "trajectory": [_tool_called_span("file_io")],
                }
            ],
        )

        build_a2_sheet(
            full_sheet_path=full_sheet_path,
            batch_path=batch_path,
            corpus_path=corpus_path,
            output_path=out_path,
        )

        with out_path.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        ev = rows[0]["evidence_summary"]
        # Must reflect the trace+tool shape (derived), not the A1 prose
        assert "A1 SAYS_THIS_IS_GOOD" not in ev
        assert "trace_id=" in ev
        assert "lf_tools=" in ev
