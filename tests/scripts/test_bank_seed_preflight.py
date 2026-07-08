"""Bank-seed pre-flight — D3 tag sections (spec FR-1 / FR-2 / FR-8).

The authored seed (`docs/plan/coach-item-bank-live.seed.json`) is validated
against the canonical syllabus BEFORE any promotion run burns LLM calls: an
unknown `standard_id`, a difficulty outside the standard's syllabus bands, a
`skill_id` that contradicts the standard's app-skill mapping, or the retired
pre-D3 `topic` key each fail closed with a message NAMING the offending row.

Untagged rows pass the TAG sections — requiredness (every row tagged, §10
matrix conformance) is Phase B T2's section of this file, red until the
authoring tranche lands.
"""

from __future__ import annotations

from scripts.bank_seed_preflight import (
    load_seed_rows,
    load_syllabus,
    seed_tag_violations,
)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "skill_id": "s-punc",
        "difficulty": 2,
        "stem_md": "Which choice correctly punctuates the list?",
        "standard_id": 14,
    }
    row.update(overrides)
    return row


class TestTagValidation:
    def test_unknown_standard_id_fails_naming_row_and_id(self):
        """FR-1 — the message carries the unknown id AND identifies the row."""
        violations = seed_tag_violations([_row(standard_id=99)], load_syllabus())
        assert len(violations) == 1
        assert "99" in violations[0]
        assert "punctuates" in violations[0]

    def test_band_mismatch_fails_closed(self):
        """FR-2 — standard 5 (Redundancy) is band 3 only; a band-2 item
        tagged with it is a tagging error."""
        rows = [_row(skill_id="s-style", standard_id=5, difficulty=2)]
        violations = seed_tag_violations(rows, load_syllabus())
        assert violations
        assert "band" in violations[0].lower()

    def test_non_contiguous_bands_validate_by_membership(self):
        """Spec §6 — standard 13 spans bands {1,3}: 3 is legal, 2 is not
        (set membership, never a range check)."""
        syllabus = load_syllabus()
        ok = [_row(skill_id="s-gram", standard_id=13, difficulty=3)]
        assert seed_tag_violations(ok, syllabus) == []
        bad = [_row(skill_id="s-gram", standard_id=13, difficulty=2)]
        assert seed_tag_violations(bad, syllabus)

    def test_skill_contradicting_the_standard_fails_closed(self):
        """A row claiming standard 14 (s-punc) under skill s-gram would corrupt
        D4's two-level scheduling — fail at authoring time."""
        violations = seed_tag_violations([_row(skill_id="s-gram")], load_syllabus())
        assert violations
        assert "s-punc" in violations[0]

    def test_retired_topic_key_fails_closed(self):
        """FR-8 — one rename, no dual-field era: `topic` never reappears."""
        violations = seed_tag_violations([_row(topic=14)], load_syllabus())
        assert violations
        assert "topic" in violations[0]

    def test_untagged_row_has_no_tag_violations(self):
        row: dict[str, object] = {
            "skill_id": "s-punc",
            "difficulty": 2,
            "stem_md": "Which choice is correct?",
        }
        assert seed_tag_violations([row], load_syllabus()) == []

    def test_well_tagged_row_passes(self):
        assert seed_tag_violations([_row()], load_syllabus()) == []


class TestCanonicalSeedTagSection:
    def test_canonical_seed_has_no_tag_violations(self):
        assert seed_tag_violations(load_seed_rows(), load_syllabus()) == []
