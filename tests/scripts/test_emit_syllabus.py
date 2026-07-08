"""L1 contract for scripts/emit_syllabus.py (D3 spec FR-4, FR-9, FR-10).

The syllabus converter is the D3 single-source seam: the canonical
`docs/plan/act-english-syllabus.seed.json` (the brainstorm's 32-topic
extraction table as data) is deterministically emitted into BOTH consumption
planes — `frontend/lib/adapters/engine/_act_english_syllabus.ts` (D4's
consumer) and `components/act_english_syllabus.py` (coverage tooling).
Deterministic, stdlib-only, no LLM, no network (nothing live in CI). Fixture
tests pin the emission contract; the drift tests pin the committed planes
byte-for-byte against a re-emit of the canonical seed (FR-10).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.emit_syllabus import (
    DEFAULT_PY_OUT,
    DEFAULT_SEED,
    DEFAULT_TS_OUT,
    emit_syllabus,
)

_CATEGORIES = ("production", "knowledge", "conventions")
_APP_SKILLS = ("s-org", "s-rhet", "s-gram", "s-style", "s-punc", "s-sent")


def _standard(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "standard_id": 1,
        "name": "Commas",
        "category": "conventions",
        "bands": [1, 2],
        "app_skill": "s-punc",
    }
    row.update(overrides)
    return row


def _full_fixture() -> list[dict[str, object]]:
    """A minimal VALID canonical corpus: exactly 32 well-formed standards."""
    return [
        _standard(
            standard_id=i,
            name=f"Standard {i}",
            category=_CATEGORIES[i % 3],
            bands=[(i % 5) + 1],
            app_skill=_APP_SKILLS[i % 6],
        )
        for i in range(1, 33)
    ]


def _emit(tmp_path: Path, rows: list[dict[str, object]]) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    seed = tmp_path / "syllabus.seed.json"
    seed.write_text(json.dumps(rows), encoding="utf-8")
    ts_out = tmp_path / "out.ts"
    py_out = tmp_path / "out.py"
    emit_syllabus(seed, ts_out, py_out)
    return ts_out, py_out


class TestCanonicalSeed:
    """FR-4 — the checked-in syllabus IS the brainstorm extraction table."""

    def _rows(self) -> list[dict[str, object]]:
        return json.loads(DEFAULT_SEED.read_text(encoding="utf-8"))

    def test_exactly_32_standards_with_the_locked_shape(self):
        rows = self._rows()
        assert isinstance(rows, list)
        assert [r["standard_id"] for r in rows] == list(range(1, 33))
        for r in rows:
            assert set(r) == {"standard_id", "name", "category", "bands", "app_skill"}
            assert str(r["name"]).strip()
            assert r["category"] in _CATEGORIES
            assert r["app_skill"] in _APP_SKILLS
            bands = r["bands"]
            assert bands == sorted(set(bands))
            assert bands and set(bands) <= {1, 2, 3, 4, 5}

    def test_names_are_unique(self):
        names = [r["name"] for r in self._rows()]
        assert len(names) == len(set(names))

    def test_extraction_table_spot_checks(self):
        """Load-bearing rows pinned against the brainstorm table (incl. the
        non-contiguous-bands edge, spec §6)."""
        rows = {r["standard_id"]: r for r in self._rows()}
        assert rows[14]["app_skill"] == "s-punc"
        assert rows[14]["bands"] == [1, 2, 3, 4, 5]
        assert rows[13]["bands"] == [1, 3]
        assert rows[1]["category"] == "production"
        assert rows[9]["category"] == "knowledge"
        assert rows[32]["category"] == "conventions"
        assert rows[32]["app_skill"] == "s-sent"


class TestEmission:
    """FR-9 — deterministic two-plane emission."""

    def test_double_emit_is_byte_identical(self, tmp_path: Path):
        ts_a, py_a = _emit(tmp_path / "a", _full_fixture())
        ts_b, py_b = _emit(tmp_path / "b", _full_fixture())
        assert ts_a.read_bytes() == ts_b.read_bytes()
        assert py_a.read_bytes() == py_b.read_bytes()

    def test_ts_plane_shape(self, tmp_path: Path):
        ts_out, _ = _emit(tmp_path, _full_fixture())
        text = ts_out.read_text(encoding="utf-8")
        assert "GENERATED FILE" in text
        assert "export const ACT_ENGLISH_SYLLABUS" in text
        assert text.count('"standard_id"') == 32

    def test_py_plane_executes_standalone_with_32_standards(self, tmp_path: Path):
        _, py_out = _emit(tmp_path, _full_fixture())
        namespace: dict[str, object] = {}
        exec(
            compile(py_out.read_text(encoding="utf-8"), str(py_out), "exec"), namespace
        )
        syllabus = namespace["ACT_ENGLISH_SYLLABUS"]
        assert len(syllabus) == 32  # type: ignore[arg-type]
        first = syllabus[0]  # type: ignore[index]
        assert first.standard_id == 1
        assert isinstance(first.bands, tuple)

    def test_emission_sorts_by_standard_id(self, tmp_path: Path):
        rows = _full_fixture()
        rows.reverse()  # deliberately unsorted so the sort contract is real
        _, py_out = _emit(tmp_path, rows)
        namespace: dict[str, object] = {}
        exec(
            compile(py_out.read_text(encoding="utf-8"), str(py_out), "exec"), namespace
        )
        ids = [s.standard_id for s in namespace["ACT_ENGLISH_SYLLABUS"]]  # type: ignore[attr-defined]
        assert ids == list(range(1, 33))


class TestFailClosed:
    """FR-4 fail-closed — a malformed canonical corpus never emits."""

    def test_wrong_count_dies(self, tmp_path: Path):
        with pytest.raises(SystemExit):
            _emit(tmp_path, _full_fixture()[:31])

    def test_unknown_category_dies(self, tmp_path: Path):
        rows = _full_fixture()
        rows[0]["category"] = "grammar"
        with pytest.raises(SystemExit):
            _emit(tmp_path, rows)

    def test_band_out_of_range_dies(self, tmp_path: Path):
        rows = _full_fixture()
        rows[0]["bands"] = [1, 6]
        with pytest.raises(SystemExit):
            _emit(tmp_path, rows)

    def test_duplicate_standard_id_dies(self, tmp_path: Path):
        rows = _full_fixture()
        rows[1]["standard_id"] = 1
        with pytest.raises(SystemExit):
            _emit(tmp_path, rows)

    def test_unknown_app_skill_dies(self, tmp_path: Path):
        rows = _full_fixture()
        rows[0]["app_skill"] = "s-nope"
        with pytest.raises(SystemExit):
            _emit(tmp_path, rows)

    def test_unknown_field_dies(self, tmp_path: Path):
        rows = _full_fixture()
        rows[0]["topic"] = 1  # the pre-D3 field name must never reappear
        with pytest.raises(SystemExit):
            _emit(tmp_path, rows)


class TestCommittedPlanesDrift:
    """FR-10 — hand-editing an emitted plane fails CI (re-emit-and-compare)."""

    def test_committed_planes_match_reemit(self, tmp_path: Path):
        ts_out = tmp_path / "reemit.ts"
        py_out = tmp_path / "reemit.py"
        emit_syllabus(DEFAULT_SEED, ts_out, py_out)
        assert ts_out.read_bytes() == DEFAULT_TS_OUT.read_bytes()
        assert py_out.read_bytes() == DEFAULT_PY_OUT.read_bytes()
