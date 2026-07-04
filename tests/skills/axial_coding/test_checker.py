"""axial_checker — the emit gate (FR-1 / FR-2 / FR-4 / FR-4a / FR-13).

Failure paths first: the checker exists to REFUSE emit on an incomplete
partition or an un-testable category. A green checker means every code is
partitioned and every category testable.
"""

from __future__ import annotations

import csv
from pathlib import Path

from tests.skills.axial_coding.conftest import load

checker = load("axial_checker")


def _csv(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


INV_H = ["code", "axis", "category"]
CAT_H = ["category", "axis", "polarity", "binary_check", "dimension"]


def _clean(tmp_path: Path):
    inv = _csv(
        tmp_path / "inv.csv",
        INV_H,
        [
            ["rescues-too-early", "agent-behavior", "answer-boundary"],
            ["truncated-reply", "environment-confound", ""],
        ],
    )
    cat = _csv(
        tmp_path / "cat.csv",
        CAT_H,
        [
            [
                "answer-boundary",
                "agent-behavior",
                "-",
                "Did the reply leave the last inference to the learner?",
                "",
            ],
        ],
    )
    return inv, cat


class TestFailurePaths:
    def test_missing_axis_blocks_emit(self, tmp_path: Path) -> None:
        inv = _csv(tmp_path / "inv.csv", INV_H, [["c1", "", "cat-a"]])
        cat = _csv(
            tmp_path / "cat.csv",
            CAT_H,
            [["cat-a", "agent-behavior", "-", "check?", ""]],
        )
        problems = checker.check(inv, cat)
        assert any("no axis" in p for p in problems)

    def test_invalid_axis_blocks_emit(self, tmp_path: Path) -> None:
        inv = _csv(tmp_path / "inv.csv", INV_H, [["c1", "bogus", "cat-a"]])
        cat = _csv(
            tmp_path / "cat.csv",
            CAT_H,
            [["cat-a", "bogus", "-", "check?", ""]],
        )
        problems = checker.check(inv, cat)
        assert any("invalid axis" in p for p in problems)

    def test_agent_code_without_category_blocks(self, tmp_path: Path) -> None:
        inv = _csv(tmp_path / "inv.csv", INV_H, [["c1", "agent-behavior", ""]])
        cat = _csv(tmp_path / "cat.csv", CAT_H, [])
        problems = checker.check(inv, cat)
        assert any("no category" in p for p in problems)

    def test_category_without_binary_check_blocks(self, tmp_path: Path) -> None:
        inv = _csv(tmp_path / "inv.csv", INV_H, [["c1", "agent-behavior", "cat-a"]])
        cat = _csv(
            tmp_path / "cat.csv", CAT_H, [["cat-a", "agent-behavior", "-", "", ""]]
        )
        problems = checker.check(inv, cat)
        assert any("un-testable" in p for p in problems)

    def test_axis_mismatch_between_code_and_category(self, tmp_path: Path) -> None:
        inv = _csv(tmp_path / "inv.csv", INV_H, [["c1", "agent-behavior", "cat-a"]])
        cat = _csv(
            tmp_path / "cat.csv",
            CAT_H,
            [["cat-a", "judge-reliability", "-", "check?", ""]],
        )
        problems = checker.check(inv, cat)
        assert any("axis mismatch" in p for p in problems)

    def test_gradient_needs_two_boundary_checks(self, tmp_path: Path) -> None:
        # FR-4a: dimension declared but only one pole in binary_check.
        inv = _csv(tmp_path / "inv.csv", INV_H, [["c1", "agent-behavior", "hint-size"]])
        cat = _csv(
            tmp_path / "cat.csv",
            CAT_H,
            [["hint-size", "agent-behavior", "-", "one coarse check", "under->over"]],
        )
        problems = checker.check(inv, cat)
        assert any("boundary checks" in p for p in problems)


class TestPasses:
    def test_clean_partition_allows_emit(self, tmp_path: Path) -> None:
        inv, cat = _clean(tmp_path)
        assert checker.check(inv, cat) == []

    def test_gradient_with_boundary_poles_ok(self, tmp_path: Path) -> None:
        inv = _csv(tmp_path / "inv.csv", INV_H, [["c1", "agent-behavior", "hint-size"]])
        cat = _csv(
            tmp_path / "cat.csv",
            CAT_H,
            [
                [
                    "hint-size",
                    "agent-behavior",
                    "-",
                    "under: nothing to do? | over: hands over the answer?",
                    "under-scaffold -> over-scaffold",
                ]
            ],
        )
        assert checker.check(inv, cat) == []

    def test_main_exit_codes(self, tmp_path: Path) -> None:
        inv, cat = _clean(tmp_path)
        assert checker.main(["--inventory", str(inv), "--categories", str(cat)]) == 0
        bad = _csv(tmp_path / "bad.csv", INV_H, [["c1", "", ""]])
        assert checker.main(["--inventory", str(bad), "--categories", str(cat)]) == 1
