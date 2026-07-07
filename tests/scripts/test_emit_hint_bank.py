"""L1 contract for scripts/emit_hint_bank.py (coach-bank-hints spec FR-B1..B3).

The converter is the single-source seam of the hint-bank increment: it reads
the canonical corpus JSON (cascade PASS rows + FR-A3 waivers) and emits BOTH
generated serving modules — `frontend/lib/adapters/engine/_hint_bank.ts` and
`components/subject_coach_bank_hints.py`. Deterministic, stdlib-only, no LLM,
no network (invariant: nothing live in CI). These tests pin the emission
contract on a fixture corpus; the real-artifact parity pins live in
`tests/components/test_subject_coach_bank_hints.py` and `_hint_bank.test.ts`
once the Phase-A corpus exists.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.emit_hint_bank import emit_hint_bank

_STAMP = "vertex_ai/gemini-test@deadbeefdeadbeef"

# Deliberately UNSORTED (ti-gen-02 rung 2 first) so the sort contract is real.
FIXTURE_ROWS = [
    {
        "id": "h-gen-bbbbbbbbbbbbbbbb",
        "subject": "act-english",
        "question_id": "ti-gen-02",
        "rung": 2,
        "body_md": "Which words *fence off* the extra clause on both sides?",
        "reviewed": True,
        "generated_by": _STAMP,
    },
    {
        "id": "h-gen-aaaaaaaaaaaaaaaa",
        "subject": "act-english",
        "question_id": "ti-gen-01",
        "rung": 1,
        "body_md": "Read the sentence aloud — where do you naturally pause?",
        "reviewed": True,
        "generated_by": _STAMP,
    },
]
FIXTURE_WAIVERS = [
    {
        "question_id": "ti-gen-02",
        "rung": 3,
        "reason": "quarantined 3x (leakage) — FR-A3 waiver",
    }
]


def _write_corpus(tmp_path: Path, rows=None, waivers=None) -> Path:
    seed = tmp_path / "seed.json"
    seed.write_text(
        json.dumps(
            {
                "rows": FIXTURE_ROWS if rows is None else rows,
                "waivers": FIXTURE_WAIVERS if waivers is None else waivers,
            }
        )
    )
    return seed


def _emit(tmp_path: Path, **corpus) -> tuple[Path, Path]:
    seed = _write_corpus(tmp_path, **corpus)
    ts_out = tmp_path / "_hint_bank.ts"
    py_out = tmp_path / "subject_coach_bank_hints.py"
    emit_hint_bank(seed, ts_out, py_out)
    return ts_out, py_out


class TestEmission:
    def test_emits_both_modules_deterministically(self, tmp_path):
        ts_out, py_out = _emit(tmp_path)
        first = (ts_out.read_bytes(), py_out.read_bytes())
        ts_out2, py_out2 = _emit(tmp_path)
        assert (ts_out2.read_bytes(), py_out2.read_bytes()) == first

    def test_rows_sorted_by_question_then_rung(self, tmp_path):
        ts_out, _ = _emit(tmp_path)
        ts = ts_out.read_text()
        # Input order is 02 before 01; emission must sort.
        assert ts.index('"ti-gen-01"') < ts.index('"ti-gen-02"')

    def test_ts_module_shape(self, tmp_path):
        ts_out, _ = _emit(tmp_path)
        ts = ts_out.read_text()
        # JSON-quoted keys (provenance-detector convention) + the three exports.
        assert '"question_id": "ti-gen-01"' in ts
        assert "export const HINT_BANK" in ts
        assert "export const HINT_BANK_WAIVERS" in ts
        assert "quarantined 3x (leakage)" in ts
        assert "export function seedHintBank" in ts
        assert "GENERATED" in ts and "scripts/emit_hint_bank.py" in ts

    def test_py_module_maps_generated_by_to_authored_by(self, tmp_path):
        _, py_out = _emit(tmp_path)
        ns: dict = {}
        exec(compile(py_out.read_text(), str(py_out), "exec"), ns)  # noqa: S102
        rungs = ns["BANK_RUNGS"]
        assert [(r.question_id, r.rung) for r in rungs] == [
            ("ti-gen-01", 1),
            ("ti-gen-02", 2),
        ]
        assert all(r.authored_by == _STAMP for r in rungs)
        assert all(r.reviewed is True for r in rungs)


class TestRejection:
    def test_rejects_rung_out_of_bounds(self, tmp_path):
        bad = [dict(FIXTURE_ROWS[0], rung=4)]
        with pytest.raises(SystemExit):
            _emit(tmp_path, rows=bad)

    def test_rejects_unreviewed_row(self, tmp_path):
        # The corpus is cascade-earned by definition; an unreviewed row in the
        # canonical JSON is corruption, not content.
        bad = [dict(FIXTURE_ROWS[0], reviewed=False)]
        with pytest.raises(SystemExit):
            _emit(tmp_path, rows=bad)

    def test_rejects_duplicate_question_rung(self, tmp_path):
        # Unique (question_id, rung) mirrors the hint table constraint
        # (ADR-0014 clause 2).
        bad = [FIXTURE_ROWS[0], dict(FIXTURE_ROWS[1], question_id="ti-gen-02", rung=2)]
        with pytest.raises(SystemExit):
            _emit(tmp_path, rows=bad)
