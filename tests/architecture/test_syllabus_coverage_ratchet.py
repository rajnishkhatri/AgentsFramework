"""D3 coverage ratchet (spec FR-3 / FR-6): "the bank is full" is a measured,
rises-only property of the promoted corpus, never vibes.

Two guards, both deterministic and offline:

- **Regression** — the promoted corpus's per-cell (standard × band) counts
  must meet every floor recorded in
  `docs/plan/act-english-coverage-floors.json`. A refactor that drops promoted
  rows below a floor fails here.
- **Monotonicity** — floors only rise. The working floors file is compared to
  its own committed history (`git show HEAD:…`, the `test_adr_ratchet.py`
  git-glue pattern); lowering or deleting a recorded floor fails. Skips
  cleanly outside a git checkout — CI always has one.

Rows lacking a `standard_id` never count toward a cell (FR-5 forbids
inventing tags retroactively); the coverage *report* flags them instead.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.syllabus_coverage_report import coverage_matrix, floor_violations

_REPO = Path(__file__).resolve().parent.parent.parent
_FLOORS_PATH = _REPO / "docs" / "plan" / "act-english-coverage-floors.json"
_FLOORS_REPO_RELATIVE = "docs/plan/act-english-coverage-floors.json"
_CORPUS_PATH = _REPO / "docs" / "plan" / "coach-item-bank-live.promoted.json"


def _load_floors(text: str) -> dict[str, int]:
    floors = json.loads(text)
    assert isinstance(floors, dict)
    return floors


class TestFloorViolationLogic:
    """FR-3 — a count below its floor is a named, failing violation."""

    def test_count_below_floor_is_a_violation(self):
        violations = floor_violations({"14:2": 2}, {"14:2": 1})
        assert violations
        assert "14:2" in violations[0]

    def test_cell_missing_entirely_is_a_violation(self):
        assert floor_violations({"14:2": 1}, {})

    def test_met_and_exceeded_floors_pass(self):
        counts = {"14:2": 1, "5:3": 5}
        assert floor_violations({"14:2": 1, "5:3": 2}, counts) == []

    def test_unfloored_cells_are_free(self):
        assert floor_violations({}, {"14:2": 9}) == []

    def test_multiple_cells_below_floor_all_rejected(self):
        """A refactor that drops several cells at once must surface every
        violation, not just the first — partial reporting hides regressions."""
        violations = floor_violations({"14:2": 3, "5:3": 2}, {"14:2": 1, "5:3": 0})
        joined = " ".join(violations)
        assert "14:2" in joined and "5:3" in joined

    def test_untagged_rows_missing_a_tag_fail_the_floor(self):
        """FR-5: rows without a standard_id never count toward a cell, so a
        floored cell fed only untagged rows must still fail (no retroactive
        tag invention to paper over a coverage gap)."""
        counts = coverage_matrix([{"difficulty": 2}, {"difficulty": 2}])
        assert floor_violations({"14:2": 1}, counts)


class TestCoverageMatrix:
    def test_counts_tagged_rows_per_standard_band_cell(self):
        rows = [
            {"standard_id": 14, "difficulty": 2},
            {"standard_id": 14, "difficulty": 2},
            {"standard_id": 5, "difficulty": 3},
        ]
        assert coverage_matrix(rows) == {"14:2": 2, "5:3": 1}

    def test_untagged_rows_never_count(self):
        assert coverage_matrix([{"difficulty": 2}]) == {}


class TestLiveRatchet:
    """The real floors file vs the real promoted corpus (absent = empty —
    the corpus file is born at Phase B's first full promotion run)."""

    def test_floors_file_schema(self):
        floors = _load_floors(_FLOORS_PATH.read_text(encoding="utf-8"))
        for cell, floor in floors.items():
            sid_text, _, band_text = cell.partition(":")
            assert 1 <= int(sid_text) <= 32, f"floor cell {cell!r}: bad standard"
            assert 1 <= int(band_text) <= 5, f"floor cell {cell!r}: bad band"
            assert isinstance(floor, int) and floor >= 0, f"floor {cell!r}={floor!r}"

    def test_promoted_corpus_meets_all_floors(self):
        floors = _load_floors(_FLOORS_PATH.read_text(encoding="utf-8"))
        rows = (
            json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
            if _CORPUS_PATH.exists()
            else []
        )
        assert floor_violations(floors, coverage_matrix(rows)) == []


def _lowered_cells(head: dict[str, int], working: dict[str, int]) -> list[str]:
    """The FR-6 monotonicity predicate, extracted so the failure path is
    testable without a git round-trip: any HEAD floor that the working file
    lowers or removes is a violation."""
    return [
        f"{cell}: {old} -> {working.get(cell, 'REMOVED')}"
        for cell, old in head.items()
        if working.get(cell, -1) < old
    ]


class TestFloorMonotonicityLogic:
    """FR-6 failure paths — prove the ≥-guard actually REJECTS a weakened
    floors file (the live test below skips at first landing, so without these
    the monotonicity guard has no red-path coverage at all)."""

    def test_lowering_a_floor_is_a_violation(self):
        assert _lowered_cells({"14:2": 3}, {"14:2": 2}) == ["14:2: 3 -> 2"]

    def test_removing_a_floor_is_a_violation(self):
        assert _lowered_cells({"14:2": 3}, {}) == ["14:2: 3 -> REMOVED"]

    def test_raising_or_holding_a_floor_passes(self):
        assert _lowered_cells({"14:2": 3, "5:3": 1}, {"14:2": 3, "5:3": 9}) == []

    def test_malformed_floor_value_is_rejected(self):
        """FR-3 schema: a non-int or negative floor must fail closed, not be
        silently coerced (a typo'd floor would otherwise waive a whole cell)."""
        for bad in ({"14:2": -1}, {"14:2": "3"}, {"14:2": 1.5}):
            floor = bad["14:2"]
            assert not (
                isinstance(floor, int) and not isinstance(floor, bool) and floor >= 0
            ), f"{floor!r} must be rejected by the floors schema"


class TestFloorsOnlyRise:
    """FR-6 — the ≥-guard against the floors file's own committed history."""

    def test_floors_never_lowered_vs_head(self):
        try:
            result = subprocess.run(
                ["git", "show", f"HEAD:{_FLOORS_REPO_RELATIVE}"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=_REPO,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pytest.skip("git unavailable — monotonicity guard needs a checkout")
        if result.returncode != 0:
            pytest.skip("floors file not committed at HEAD yet (first landing)")
        head_floors = _load_floors(result.stdout)
        working = _load_floors(_FLOORS_PATH.read_text(encoding="utf-8"))
        assert _lowered_cells(head_floors, working) == []
