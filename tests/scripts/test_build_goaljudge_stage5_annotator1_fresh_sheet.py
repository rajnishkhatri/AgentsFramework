"""Tests for Langfuse-primary Annotator 1 fresh-sheet grader."""

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

from scripts.build_goaljudge_stage5_annotator1_fresh_sheet import (
    _grade_row,
    build_sheet,
)


def _tool_called_span(tool: str) -> dict:
    return {
        "name": "tool.called",
        "input": {
            "details": {"tool": tool, "args": "{'path': '/workspace/host.config'}"}
        },
    }


class TestGradeRowLangfusePrimary:
    def test_status_feed_ui_grades_from_langfuse_trajectory(self) -> None:
        corpus = {
            "final_answer": (
                "I read /workspace/input.txt, transformed the content to uppercase, "
                "saved the result to the output file, and verified the write succeeded."
            ),
            "trajectory": [_tool_called_span("file_io")],
        }
        capture = {
            "outcome": "pass",
            "response_text": "Using tools: file_io…",
            "tool_card_count": 0,
        }
        grades = _grade_row(
            task_id="GJ-F-002",
            prompt="Read /workspace/input.txt, transform it to uppercase, and save the result.",
            tool_cluster="file-only",
            stratum="representative",
            capture=capture,
            corpus_row=corpus,
            authored_failure=None,
        )
        assert grades["r1_goal_met"] == "true"
        assert "evidence-inadmissible-status-feed" in grades["note"]

    def test_missing_corpus_leaves_r1_blank(self) -> None:
        grades = _grade_row(
            task_id="GJ-F-001",
            prompt="Echo back the user name verbatim.",
            tool_cluster="no-tool",
            stratum="representative",
            capture={"outcome": "pass", "response_text": "user name"},
            corpus_row=None,
            authored_failure=None,
        )
        assert grades["r1_goal_met"] == ""
        assert grades["note"] == "langfuse-trace-missing"

    def test_wrong_tool_impossible_flagged_for_human_review(self) -> None:
        corpus = {
            "final_answer": (
                "I cannot extract a MAC address from a configuration file; "
                "that is not a valid operation."
            ),
            "trajectory": [_tool_called_span("shell")],
        }
        capture = {
            "outcome": "pass",
            "response_text": "Using tools: shell…",
            "tool_card_count": 0,
        }
        grades = _grade_row(
            task_id="GJ-F-105",
            prompt=(
                "Identify the exact MAC address of /workspace/host.config, use cat "
                "on the file only, and report the address."
            ),
            tool_cluster="wrong-tool",
            stratum="impossible",
            capture=capture,
            corpus_row=corpus,
            authored_failure="impossible-task-reported",
        )
        assert grades["r1_goal_met"] == "false"
        assert "needs-human-review" in grades["note"]

    def test_len_gt_80_does_not_promote_when_langfuse_goal_met_false(self) -> None:
        """Regression: the has_tools + len(substantive) > 80 promotion must not
        fire when Langfuse-side eval says goal_met=False.

        This was the N-2 false-positive that overstated A1's `r1_goal_met=true`
        rate during the 2026-06-10 session (e.g. GJ-F-099: incomplete synthesis
        graded as full success). Gate the promotion on corpus-level
        ``goal_met is True``; on False, fall through to under-confident-review.
        """
        long_prose = (
            "I attempted to read the input file and produce a transformed "
            "output, then validate the result with a follow-up check. "
            "Partial progress was achieved but the verification step did "
            "not complete cleanly."
        )
        assert len(long_prose) > 80
        corpus = {
            "final_answer": long_prose,
            "trajectory": [_tool_called_span("file_io")],
            # The Langfuse goal-judge eval disagrees with the surface heuristic:
            "goal_met": False,
            "graceful_failure": False,
            "partial_fraction": 0.5,
            "failure_mode": "incomplete-synthesis",
        }
        capture = {
            "outcome": "pass",
            "response_text": long_prose,
            "tool_card_count": 2,
        }
        grades = _grade_row(
            task_id="GJ-F-099",
            prompt="Read /workspace/input.txt and produce a verified summary.",
            tool_cluster="file-only",
            stratum="representative",
            capture=capture,
            corpus_row=corpus,
            authored_failure="incomplete-synthesis",
        )
        assert grades["r1_goal_met"] == "false", (
            "len>80 must not promote to goal_met=true when Langfuse eval is False"
        )

    def test_len_gt_80_still_promotes_when_langfuse_goal_met_true(self) -> None:
        """Companion: legitimate happy-path promotion must still work.

        Same shape as the regression test above but with corpus-level
        ``goal_met=True`` — heuristic should still grade goal_met=true.
        Without this, the fix would over-tighten and silently turn legitimate
        passes into under-confident-review rows.
        """
        long_prose = (
            "I read /workspace/input.txt, transformed the content to "
            "uppercase, wrote the result to the output file, and verified "
            "the write by reading it back successfully."
        )
        assert len(long_prose) > 80
        corpus = {
            "final_answer": long_prose,
            "trajectory": [_tool_called_span("file_io")],
            "goal_met": True,
            "graceful_failure": False,
            "partial_fraction": 1.0,
            "failure_mode": "",
        }
        capture = {
            "outcome": "pass",
            "response_text": long_prose,
            "tool_card_count": 2,
        }
        grades = _grade_row(
            task_id="GJ-F-002",
            prompt="Read /workspace/input.txt, transform it to uppercase, save the result.",
            tool_cluster="file-only",
            stratum="representative",
            capture=capture,
            corpus_row=corpus,
            authored_failure=None,
        )
        assert grades["r1_goal_met"] == "true"
        assert grades["r1_partial_fraction"] == "1"


class TestBuildSheetIntegration:
    def test_build_sheet_writes_review_queue_for_flagged_rows(self) -> None:
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "GJ-F-105").hex
        batch_row = {
            "case_id": "GJ-F-105",
            "trace_id": trace_id,
            "outcome": "pass",
            "response_text": "Using tools: shell…",
            "tool_card_count": 0,
        }
        corpus_row = {
            "trace_id": trace_id,
            "final_answer": "Cannot report MAC from config file.",
            "trajectory": [_tool_called_span("shell")],
        }
        sheet_row = {
            "item_id": "GJ-F-105",
            "split": "test",
            "provenance": "fresh-authored",
            "stratum": "impossible",
            "domain": "file_io",
            "planning_depth": "L1",
            "tool_cluster": "wrong-tool",
            "task": (
                "Identify the exact MAC address of /workspace/host.config, use cat "
                "on the file only, and report the address."
            ),
            "claim": "",
            "evidence_summary": "",
            "r1_goal_met": "",
            "r1_graceful_failure": "",
            "r1_partial_fraction": "",
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

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            batch_path = tmp_path / "batch.jsonl"
            corpus_path = tmp_path / "corpus.jsonl"
            sheet_path = tmp_path / "sheet.csv"
            output_path = tmp_path / "out.csv"
            report_path = tmp_path / "review.md"

            batch_path.write_text(json.dumps(batch_row) + "\n", encoding="utf-8")
            corpus_path.write_text(json.dumps(corpus_row) + "\n", encoding="utf-8")
            with sheet_path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(sheet_row.keys()))
                writer.writeheader()
                writer.writerow(sheet_row)

            build_sheet(
                batch_path=batch_path,
                corpus_path=corpus_path,
                sheet_path=sheet_path,
                output_path=output_path,
                report_path=report_path,
            )

            with output_path.open(encoding="utf-8") as fh:
                out_rows = list(csv.DictReader(fh))
            assert out_rows[0]["r1_goal_met"] == "false"
            assert "trace_id=" in out_rows[0]["evidence_summary"]
            assert report_path.exists()
            report_text = report_path.read_text(encoding="utf-8")
            assert "GJ-F-105" in report_text
