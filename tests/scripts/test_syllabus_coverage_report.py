"""FR-7 (D3): the coverage report renders the standard x band matrix
deterministically on a fixture corpus — `-` for cells outside a standard's
syllabus bands, `.` for authorable-but-empty cells, counts elsewhere, and an
UNTAGGED foot listing rows the matrix refuses to count (FR-5 posture)."""

from __future__ import annotations

from scripts.syllabus_coverage_report import (
    coverage_matrix,
    render_report,
    untagged_rows,
)

_SYLLABUS = [
    {"standard_id": 5, "name": "Redundancy", "bands": [3], "app_skill": "s-style"},
    {
        "standard_id": 14,
        "name": "Commas (series, dates/places, addresses)",
        "bands": [1, 2, 3, 4, 5],
        "app_skill": "s-punc",
    },
]

_ROWS = [
    {"id": "ti-gen-aaaa", "standard_id": 14, "difficulty": 2},
    {"id": "ti-gen-bbbb", "standard_id": 14, "difficulty": 2},
    {"id": "ti-gen-cccc", "standard_id": 5, "difficulty": 3},
    {"id": "ti-gen-dddd", "difficulty": 4},  # pre-D3 row: flagged, never counted
]


class TestRenderReport:
    def _report(self) -> str:
        return render_report(_SYLLABUS, coverage_matrix(_ROWS), untagged_rows(_ROWS))

    def test_counts_dashes_and_gaps_render_per_cell(self):
        report = self._report()
        redundancy_line = next(
            line for line in report.splitlines() if "Redundancy" in line
        )
        # bands 1,2,4,5 are not authorable for Redundancy; band 3 holds 1 item.
        assert redundancy_line.count("-") == 4
        assert "  1" in redundancy_line
        commas_line = next(line for line in report.splitlines() if "Commas" in line)
        assert "  2" in commas_line  # the two band-2 rows
        assert "." in commas_line  # authorable-but-empty cells stay visible

    def test_untagged_rows_are_flagged_never_counted(self):
        report = self._report()
        assert "tagged rows total: 3" in report
        assert "UNTAGGED" in report
        assert "ti-gen-dddd" in report

    def test_report_is_deterministic(self):
        assert self._report() == self._report()
