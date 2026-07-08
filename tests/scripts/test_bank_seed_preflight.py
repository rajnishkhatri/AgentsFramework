"""Bank-seed pre-flight — D3 tag sections + Phase B seed gates.

The authored seed (`docs/plan/coach-item-bank-live.seed.json`) is validated
against the canonical syllabus BEFORE any promotion run burns LLM calls: an
unknown `standard_id`, a difficulty outside the standard's syllabus bands, a
`skill_id` that contradicts the standard's app-skill mapping, or the retired
pre-D3 `topic` key each fail closed with a message NAMING the offending row
(D3 spec FR-1 / FR-2 / FR-8).

Phase B sections (its spec FR-8 / FR-9): every seed row must clear the SAME
`_schema_violations` gate the cascade applies (a schema reject at promotion
time is a wasted authoring slot), and the finished corpus must satisfy the
§10 allocation matrix — that conformance test is red-by-design (xfail
strict) until the T6 authoring tranche lands, then the marker comes off.
"""

from __future__ import annotations

from collections import Counter

import pytest

from components.test_item_generation import _schema_violations
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


# ── Phase B seed gates (act-english-bank-phase-b.spec.md FR-8 / FR-9) ──────


class TestSeedSchemaSection:
    """FR-8 — every authored row clears the cascade's OWN schema gate before
    a promotion run spends solver calls on it."""

    def test_every_row_passes_the_cascade_schema(self):
        for index, row in enumerate(load_seed_rows()):
            violations = _schema_violations(row)
            stem = str(row.get("stem_md", ""))[:48]
            assert violations == [], f"row {index} ({stem!r}): {violations}"

    def test_seed_rows_are_unpromoted(self):
        """Seed rows never self-assert review — the cascade earns it
        (ADR-0015; promote demotes anyway, this catches authoring slips)."""
        for index, row in enumerate(load_seed_rows()):
            assert row.get("reviewed") is False, f"row {index} self-asserts review"
            assert str(row.get("generated_by", "")).strip(), f"row {index} unattributed"

    def test_stems_are_unique_after_normalization(self):
        """Exact-normalized duplicates are authoring copy-paste accidents; the
        cascade's Jaccard gate would quarantine them AFTER solver spend."""
        seen: dict[str, int] = {}
        for index, row in enumerate(load_seed_rows()):
            key = " ".join(str(row["stem_md"]).lower().split())
            assert key not in seen, f"rows {seen[key]} and {index} share a stem"
            seen[key] = index

    def test_stem_does_not_reveal_the_answer(self):
        """ADR-0012 pedagogy rule: the item must not hand the learner its own
        answer BEFORE they reason. A stem that quotes the correct choice's label
        (or asserts its letter) is a pre-reveal — the same leak class the coach's
        deterministic per-rung check (`components.hint_leakage`) forbids for
        hints, applied to the stem itself. Two nets: (1) the repo's own leak
        predicate over the stem, (2) a lexical scan for the correct label
        appearing verbatim in the stem (catches reveals outside the predicate's
        keyword window, e.g. a stem asking to 'express honoring' when the key is
        'honor')."""
        from components.hint_leakage import check_rung_leakage

        def _norm(s: object) -> str:
            return " ".join(str(s).lower().split())

        offenders: list[str] = []
        for index, row in enumerate(load_seed_rows()):
            labels = {c["letter"]: c["label"] for c in row.get("choices", [])}
            ans = row.get("answer_letter")
            stem = str(row.get("stem_md", ""))
            tag = f"row {index} [{row.get('skill_id')}/std{row.get('standard_id')}]"

            if isinstance(ans, str) and ans in labels:
                leak = [
                    v
                    for v in check_rung_leakage(stem, row)
                    if "unverifiable" not in v and "empty rung" not in v
                ]
                if leak:
                    offenders.append(f"{tag}: predicate {leak}")
                key = _norm(labels[ans])
                if key != "no change" and len(key) >= 4 and key in _norm(stem):
                    offenders.append(f"{tag}: stem contains the key label {key!r}")
        assert offenders == [], f"stems that reveal their answer: {offenders}"

    def test_answer_key_is_not_position_biased(self):
        """A lopsided key column both teaches test-takers a false meta-strategy
        ('when unsure, guess B') and lets a positional prior inflate the T7
        independent-solver's apparent agreement — contaminating promotion.

        'A' is exempt: it is 'NO CHANGE' by ACT convention (its rate reflects how
        often the original is correct, not a placement choice). Among the freely
        placeable slots B/C/D, no single letter may exceed 45% of the non-A keys
        (even placement is ~33% each; 45% tolerates variance, catches the skew)."""
        from collections import Counter

        rows = load_seed_rows()
        keys = Counter(str(r["answer_letter"]) for r in rows)
        non_a = sum(v for k, v in keys.items() if k != "A")
        assert non_a, "no non-'NO CHANGE' keys to balance"
        offenders = {
            letter: f"{keys.get(letter, 0)}/{non_a} = {100 * keys.get(letter, 0) // non_a}%"
            for letter in ("B", "C", "D")
            if keys.get(letter, 0) / non_a > 0.45
        }
        assert offenders == {}, f"answer-key position bias among B/C/D: {offenders}"


# The §10 allocation matrix: per bucket, standard_id -> minimum item count
# for the 150 NEW Phase B items. Base/fold rows only ADD to cells, so the
# finished seed must meet every cell as a >= floor.
_MATRIX: dict[str, dict[int, int]] = {
    "s-punc": {14: 7, 24: 6, 29: 6, 30: 3, 31: 3},
    "s-gram": {
        17: 3,
        7: 2,
        11: 2,
        12: 2,
        13: 2,
        18: 2,
        19: 2,
        22: 2,
        26: 2,
        28: 2,
        3: 1,
        16: 1,
        23: 1,
        27: 1,
    },
    "s-sent": {15: 5, 21: 5, 10: 4, 25: 4, 32: 4, 20: 3},
    "s-rhet": {2: 13, 4: 12},
    "s-org": {1: 25},
    "s-style": {9: 7, 5: 6, 6: 6, 8: 6},
}


class TestSeedMatrixConformance:
    """FR-8 / FR-9 — the finished corpus satisfies the §10 matrix."""

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "G8-OK: red-by-design until Phase B T6 lands the authored tranche "
            "(spec §12 T2: 'RED until authoring lands'); strict=True forces "
            "this marker's removal in the same change that turns it green"
        ),
    )
    def test_seed_satisfies_the_phase_b_allocation_matrix(self):
        rows = load_seed_rows()
        assert len(rows) >= 192, f"seed has {len(rows)} rows; FR-8 wants >= 192"
        untagged = [i for i, r in enumerate(rows) if "standard_id" not in r]
        assert untagged == [], f"rows without standard_id: {untagged}"
        counts = Counter((r["skill_id"], r["standard_id"]) for r in rows)
        shortfalls = {
            f"{bucket}/standard {sid}": f"{counts.get((bucket, sid), 0)} < {need}"
            for bucket, cells in _MATRIX.items()
            for sid, need in cells.items()
            if counts.get((bucket, sid), 0) < need
        }
        assert shortfalls == {}, f"matrix shortfalls: {shortfalls}"
        covered = {r["standard_id"] for r in rows}
        assert covered == set(range(1, 33)), (
            f"standards with zero items: {sorted(set(range(1, 33)) - covered)}"
        )
