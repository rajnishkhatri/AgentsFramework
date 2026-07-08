"""L1 contract for scripts/emit_test_item_bank.py (Phase B spec FR-6 / FR-12).

The bank emitter is the ADR-0014-pattern single-source seam for the practice
bank: the frozen promoted corpus (`docs/plan/coach-item-bank-live.promoted.json`,
the cascade's `passed` list verbatim) is deterministically emitted into the
serving plane `frontend/lib/adapters/engine/_test_item_bank.ts` — JSON-quoted
keys (the provenance detector matches the quoted form), `is_no_change` derived
per choice, `seedTestItemBank(db)` for the composition root. Deterministic,
stdlib-only, no LLM. Fail-closed: an unpromoted or provenance-broken row never
reaches the serving plane.

`standard_id` is tolerated on input rows and HELD BACK from emission until D4
declares it on the wire (D4 spec §4 emitter seam) — the Zod kernel would
silently strip it anyway; withholding keeps the emitted plane honest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.emit_test_item_bank import emit_test_item_bank

_STAMP = "gpt-4o-mini@976a393626bf4e3eab85adf818db0096"


def _promoted_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "ti-gen-aaaaaaaaaaaaaaaa",
        "subject": "act-english",
        "skill_id": "s-punc",
        "difficulty": 2,
        "context_html": "The recipe calls for three <u>ingredients flour</u>, sugar.",
        "stem_md": "Which choice correctly punctuates the introduction of the list?",
        "choices": [
            {"letter": "A", "label": "NO CHANGE"},
            {"letter": "B", "label": "ingredients: flour"},
            {"letter": "C", "label": "ingredients; flour"},
            {"letter": "D", "label": "ingredients', flour"},
        ],
        "answer_letter": "B",
        "per_choice_rationale": {
            "A": "No punctuation runs the list into the noun naming it.",
            "B": "A colon after a complete statement introduces the list.",
            "C": "A semicolon cannot introduce a list.",
            "D": "Nothing calls for a possessive apostrophe.",
        },
        "why_correct_md": "A **colon** introduces the list it announces.",
        "why_tempted_md": "The sentence reads smoothly aloud.",
        "rule_md": "Use a colon after a complete clause to introduce a list.",
        "item_type": "underlined-span-mc",
        "reviewed": True,
        "generated_by": _STAMP,
    }
    row.update(overrides)
    return row


def _fixture_rows() -> list[dict[str, object]]:
    # Deliberately UNSORTED (s-style d3 first) so the sort contract is real.
    return [
        _promoted_row(
            id="ti-gen-cccccccccccccccc",
            skill_id="s-style",
            difficulty=3,
            stem_md="Which choice removes the redundancy without changing meaning?",
        ),
        _promoted_row(
            id="ti-gen-bbbbbbbbbbbbbbbb",
            difficulty=4,
            stem_md="Which choice makes the possessive correct?",
        ),
        _promoted_row(),
    ]


def _emit(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    corpus = tmp_path / "promoted.json"
    corpus.write_text(json.dumps(rows), encoding="utf-8")
    ts_out = tmp_path / "out.ts"
    emit_test_item_bank(corpus, ts_out)
    return ts_out


class TestEmission:
    def test_double_emit_is_byte_identical(self, tmp_path: Path):
        out_a = _emit(tmp_path / "a", _fixture_rows())
        out_b = _emit(tmp_path / "b", _fixture_rows())
        assert out_a.read_bytes() == out_b.read_bytes()

    def test_ts_plane_shape(self, tmp_path: Path):
        text = _emit(tmp_path, _fixture_rows()).read_text(encoding="utf-8")
        assert "GENERATED FILE" in text
        assert "export const TEST_ITEM_BANK: readonly TestItem[]" in text
        assert "export function seedTestItemBank(db: InMemoryEngineDb)" in text
        assert text.count('"generated_by"') == 3
        # JSON-quoted keys are the provenance detector's contract.
        assert '"reviewed": true' in text

    def test_rows_sort_by_skill_then_difficulty_then_id(self, tmp_path: Path):
        text = _emit(tmp_path, _fixture_rows()).read_text(encoding="utf-8")
        positions = [
            text.index("ti-gen-aaaaaaaaaaaaaaaa"),  # s-punc d2
            text.index("ti-gen-bbbbbbbbbbbbbbbb"),  # s-punc d4
            text.index("ti-gen-cccccccccccccccc"),  # s-style d3
        ]
        assert positions == sorted(positions)

    def test_is_no_change_derived_per_choice(self, tmp_path: Path):
        text = _emit(tmp_path, [_promoted_row()]).read_text(encoding="utf-8")
        assert text.count('"is_no_change": true') == 1  # the NO CHANGE choice
        assert text.count('"is_no_change": false') == 3

    def test_standard_id_is_held_back_until_d4(self, tmp_path: Path):
        rows = [_promoted_row(standard_id=14)]
        text = _emit(tmp_path, rows).read_text(encoding="utf-8")
        assert "standard_id" not in text


class TestFailClosed:
    def test_unreviewed_row_dies(self, tmp_path: Path):
        with pytest.raises(SystemExit):
            _emit(tmp_path, [_promoted_row(reviewed=False)])

    def test_non_cascade_provenance_dies(self, tmp_path: Path):
        with pytest.raises(SystemExit):
            _emit(tmp_path, [_promoted_row(generated_by="claude-session-authored")])

    def test_missing_teaching_field_dies(self, tmp_path: Path):
        row = _promoted_row()
        del row["rule_md"]
        with pytest.raises(SystemExit):
            _emit(tmp_path, [row])

    def test_answer_letter_outside_choices_dies(self, tmp_path: Path):
        with pytest.raises(SystemExit):
            _emit(tmp_path, [_promoted_row(answer_letter="E")])

    def test_duplicate_ids_die(self, tmp_path: Path):
        with pytest.raises(SystemExit):
            _emit(tmp_path, [_promoted_row(), _promoted_row(difficulty=3)])

    def test_rationale_missing_a_letter_dies(self, tmp_path: Path):
        rationale = {
            "A": "No punctuation runs the list into the noun naming it.",
            "B": "A colon after a complete statement introduces the list.",
            "C": "A semicolon cannot introduce a list.",
        }
        with pytest.raises(SystemExit):
            _emit(tmp_path, [_promoted_row(per_choice_rationale=rationale)])

    def test_empty_corpus_dies(self, tmp_path: Path):
        # An empty bank would silently blank the practice quiz (FR-B4
        # posture) — refuse to emit nothing.
        with pytest.raises(SystemExit):
            _emit(tmp_path, [])
