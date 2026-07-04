"""axial_matrix — code x category counts + confound exclusion (FR-3 / FR-9)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from tests.skills.axial_coding.conftest import load

matrix = load("axial_matrix")


def _coded(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return path


def _inv(path: Path, rows: list[list[str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["code", "axis", "category"])
        w.writerows(rows)
    return path


class TestConfoundExclusion:
    def test_confound_only_trace_excluded_from_denominator(
        self, tmp_path: Path
    ) -> None:
        # FR-3: a trace whose only code is environment-confound must NOT count
        # toward the agent-behavior denominator.
        coded = _coded(
            tmp_path / "c.jsonl",
            [
                {"trace_id": "a", "open_codes": ["rescues-too-early"]},
                {"trace_id": "b", "open_codes": ["truncated-reply"]},
            ],
        )
        inv = _inv(
            tmp_path / "i.csv",
            [
                ["rescues-too-early", "agent-behavior", "answer-boundary"],
                ["truncated-reply", "environment-confound", ""],
            ],
        )
        result = matrix.build_matrix(coded, inv)
        assert result["agent_denominator"] == 1
        assert result["confound_only_excluded"] == 1

    def test_mixed_trace_counts_as_agent(self, tmp_path: Path) -> None:
        # A trace with BOTH an agent code and a confound code is a valid
        # agent-behavior trace (the confound rode along, but the agent acted).
        coded = _coded(
            tmp_path / "c.jsonl",
            [{"trace_id": "a", "open_codes": ["rescues-too-early", "truncated-reply"]}],
        )
        inv = _inv(
            tmp_path / "i.csv",
            [
                ["rescues-too-early", "agent-behavior", "answer-boundary"],
                ["truncated-reply", "environment-confound", ""],
            ],
        )
        result = matrix.build_matrix(coded, inv)
        assert result["agent_denominator"] == 1
        assert result["confound_only_excluded"] == 0


class TestCounts:
    def test_code_x_category_counts_via_join(self, tmp_path: Path) -> None:
        coded = _coded(
            tmp_path / "c.jsonl",
            [
                {"trace_id": "a", "open_codes": ["rescues-too-early"]},
                {"trace_id": "b", "open_codes": ["rescues-too-early", "vague-locus"]},
            ],
        )
        inv = _inv(
            tmp_path / "i.csv",
            [
                ["rescues-too-early", "agent-behavior", "answer-boundary"],
                ["vague-locus", "agent-behavior", "scaffold"],
            ],
        )
        result = matrix.build_matrix(coded, inv)
        assert result["category_counts"] == {"answer-boundary": 2, "scaffold": 1}
