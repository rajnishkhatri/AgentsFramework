"""Task 3.3b — verify coded.jsonl has real codes, not memo prose (FR-G3.1.4).

Failure path first: a row whose ``open_codes`` is empty is reported with its
``trace_id`` + the per-mode uncoded count. This is the skill's Step-4 trap
(codes typed into the memo box do not populate ``open_codes``).
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_coded_open_codes import verify_coded


def _write(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "coded.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return p


class TestVerify:
    def test_flags_empty_open_codes_rows(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            [
                {
                    "trace_id": "a",
                    "mode": "pre_submit",
                    "open_codes": ["depth-under-plan"],
                },
                {
                    "trace_id": "b",
                    "mode": "pre_submit",
                    "open_codes": [],
                    "memo": "prose",
                },
                {"trace_id": "c", "mode": "post_feedback", "open_codes": []},
            ],
        )
        report = verify_coded(path)
        assert report.uncoded_trace_ids == ["b", "c"]
        assert report.total_rows == 3
        assert report.per_mode_uncoded == {"pre_submit": 1, "post_feedback": 1}
        assert report.ok is False

    def test_missing_open_codes_key_counts_as_uncoded(self, tmp_path: Path) -> None:
        path = _write(tmp_path, [{"trace_id": "x", "mode": "pre_submit"}])
        report = verify_coded(path)
        assert report.uncoded_trace_ids == ["x"]
        assert report.ok is False

    def test_all_coded_is_ok(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            [
                {"trace_id": "a", "mode": "pre_submit", "open_codes": ["x"]},
                {"trace_id": "b", "mode": "post_feedback", "open_codes": ["y", "z"]},
            ],
        )
        report = verify_coded(path)
        assert report.uncoded_trace_ids == []
        assert report.ok is True
        assert report.total_rows == 2
