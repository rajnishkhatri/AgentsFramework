"""Task 3.3c — roll coded.jsonl into the Stage-1 inventory CSV (FR-G3.1.9).

The CSV must carry the GoalJudge inventory columns exactly (parity with
docs/research/goaljudge_step1_open_code_inventory.csv), one row per distinct
code, so Task 3.4 axial coding consumes the same shape.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.build_coach_open_code_inventory import GOALJUDGE_COLUMNS, build_inventory


def _write(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "coded.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return p


_ROWS = [
    {
        "trace_id": "t1",
        "mode": "pre_submit",
        "open_codes": ["rule-naming-as-leak"],
        "prompt": "why is B wrong",
        "final_answer": "the rule is X",
    },
    {
        "trace_id": "t2",
        "mode": "pre_submit",
        "open_codes": ["rule-naming-as-leak", "clarification-instead-of-action"],
    },
    {
        "trace_id": "t3",
        "mode": "post_feedback",
        "open_codes": ["clarification-instead-of-action"],
    },
]


class TestInventoryColumns:
    def test_csv_has_goaljudge_columns(self, tmp_path: Path) -> None:
        path = _write(tmp_path, _ROWS)
        out = tmp_path / "inventory.csv"
        build_inventory(path, out)
        with out.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader)
        assert header == list(GOALJUDGE_COLUMNS)

    def test_one_row_per_distinct_code(self, tmp_path: Path) -> None:
        path = _write(tmp_path, _ROWS)
        out = tmp_path / "inventory.csv"
        build_inventory(path, out)
        with out.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        codes = {r["code"] for r in rows}
        assert codes == {"rule-naming-as-leak", "clarification-instead-of-action"}
        assert len(rows) == 2

    def test_first_seen_case_is_earliest_trace(self, tmp_path: Path) -> None:
        path = _write(tmp_path, _ROWS)
        out = tmp_path / "inventory.csv"
        build_inventory(path, out)
        with out.open(newline="", encoding="utf-8") as fh:
            by_code = {r["code"]: r for r in csv.DictReader(fh)}
        # rule-naming-as-leak first appears on t1; clarification first on t2.
        assert "t1" in by_code["rule-naming-as-leak"]["first_seen_case"]
        assert "t2" in by_code["clarification-instead-of-action"]["first_seen_case"]


class TestAxialColumns:
    """FR-13 — the inventory CSV is the coder's single edit surface for axis +
    category; both columns ship blank (human-filled at axial coding)."""

    def test_header_includes_axis_and_category(self, tmp_path: Path) -> None:
        path = _write(tmp_path, _ROWS)
        out = tmp_path / "inventory.csv"
        build_inventory(path, out)
        with out.open(newline="", encoding="utf-8") as fh:
            header = next(csv.reader(fh))
        assert "axis" in header
        assert "category" in header

    def test_axis_and_category_cells_blank(self, tmp_path: Path) -> None:
        path = _write(tmp_path, _ROWS)
        out = tmp_path / "inventory.csv"
        build_inventory(path, out)
        with out.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert rows, "expected at least one code row"
        for r in rows:
            assert r["axis"] == ""
            assert r["category"] == ""


class TestEmptyAndOrdering:
    def test_empty_coded_yields_header_only(self, tmp_path: Path) -> None:
        path = _write(tmp_path, [{"trace_id": "t", "open_codes": []}])
        out = tmp_path / "inventory.csv"
        build_inventory(path, out)
        with out.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert rows == []

    def test_deterministic_code_ordering(self, tmp_path: Path) -> None:
        path = _write(tmp_path, _ROWS)
        out = tmp_path / "inventory.csv"
        build_inventory(path, out)
        with out.open(newline="", encoding="utf-8") as fh:
            codes = [r["code"] for r in csv.DictReader(fh)]
        assert codes == sorted(codes)
