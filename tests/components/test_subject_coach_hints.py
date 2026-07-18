"""L1 Deterministic: authored hint-rung asset + FR-20 lock tests (ADR-0012).

The hint ladder has exactly three rungs — probe(1) → conceptual(2) →
directive(3). There is NO assertion rung: the schema cannot represent one
(Protocol A1 invalid-data pair — the rejection test comes first), and the
serving seam never returns an unreviewed rung.

Interim asset (agent design §11 step-2): hand-authored rungs keyed to the
dev-seed questions, replaced by generated+verified rows in Phase 4.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from components.subject_coach_hints import (
    AUTHORED_RUNGS,
    HintRung,
    rungs_for_question,
)

DEV_SEED_QUESTION_IDS = (
    "q-punc-1",
    "q-gram-1",
    "q-sent-1",
    "q-rhet-1",
    "q-org-1",
    "q-style-1",
)


class TestNoAssertionRungRepresentable:
    """FR-20 failure paths FIRST: the assertion rung must be UNREPRESENTABLE."""

    @pytest.mark.parametrize("bad_rung", [0, 4, 5, -1])
    def test_rung_outside_ladder_rejected(self, bad_rung):
        with pytest.raises(ValidationError):
            HintRung(
                question_id="q-punc-1",
                rung=bad_rung,
                body_md="Look again at the clause boundaries.",
                reviewed=True,
                authored_by="human",
            )

    def test_empty_body_rejected(self):
        with pytest.raises(ValidationError):
            HintRung(
                question_id="q-punc-1",
                rung=1,
                body_md="   ",
                reviewed=True,
                authored_by="human",
            )

    def test_rung_is_immutable(self):
        rung = HintRung(
            question_id="q-punc-1",
            rung=1,
            body_md="What kind of clause is set off here?",
            reviewed=True,
            authored_by="human",
        )
        with pytest.raises(ValidationError):
            rung.rung = 3


class TestServingGate:
    """FR-20: only reviewed=true rungs are ever served."""

    def test_unreviewed_rung_never_served(self):
        ladder = [
            HintRung(
                question_id="q-x",
                rung=1,
                body_md="probe",
                reviewed=True,
                authored_by="human",
            ),
            HintRung(
                question_id="q-x",
                rung=2,
                body_md="conceptual",
                reviewed=False,
                authored_by="generator",
            ),
        ]
        served = rungs_for_question("q-x", source=ladder)
        assert [r.rung for r in served] == [1]

    def test_served_rungs_are_ordered_probe_to_directive(self):
        served = rungs_for_question("q-punc-1")
        assert [r.rung for r in served] == sorted(r.rung for r in served)

    def test_unknown_question_serves_empty(self):
        assert rungs_for_question("q-nonexistent") == []


class TestAuthoredAsset:
    def test_every_dev_seed_question_has_a_full_ladder(self):
        for qid in DEV_SEED_QUESTION_IDS:
            served = rungs_for_question(qid)
            assert [r.rung for r in served] == [1, 2, 3], (
                f"{qid} must carry exactly one probe, one conceptual, one "
                f"directive rung"
            )

    def test_all_authored_rungs_are_reviewed_and_human_authored(self):
        assert AUTHORED_RUNGS, "interim asset must not be empty"
        for rung in AUTHORED_RUNGS:
            assert rung.reviewed is True
            assert rung.authored_by == "human"


class TestBankPlane:
    """FR-D1 (coach-bank-hints): the DEFAULT serving path must include the
    generated bank ladders — the ADR-0021 bank swapped the quiz to `ti-gen-*`
    ids, and an empty ladder makes the persona free-generate (the Stage-0
    rule-naming leak class the react_loop comment warns about)."""

    def test_every_bank_item_serves_a_full_ladder_by_default(self):
        """ADR-0031: Gen1 item-level via default; Gen2 via each choice_letter."""
        from components.subject_coach_bank_hints import BANK_RUNGS

        bank_ids = sorted({r.question_id for r in BANK_RUNGS})
        assert bank_ids, "generated bank asset must not be empty"
        by_qid: dict[str, list] = {}
        for r in BANK_RUNGS:
            by_qid.setdefault(r.question_id, []).append(r)
        for qid in bank_ids:
            rows = by_qid[qid]
            item_level = [r for r in rows if r.choice_letter is None]
            if item_level:
                served = rungs_for_question(qid)
                assert [r.rung for r in served] == [1, 2, 3], (
                    f"{qid}: default rungs_for_question must serve the Gen1 "
                    f"ladder (got rungs {[r.rung for r in served]})"
                )
                continue
            letters = sorted({r.choice_letter for r in rows if r.choice_letter})
            assert len(letters) >= 3, f"{qid}: Gen2 needs ≥3 wrong-letter ladders"
            for letter in letters:
                served = rungs_for_question(qid, choice_letter=letter)
                assert [r.rung for r in served] == [1, 2, 3], (
                    f"{qid}/{letter}: choice-conditional ladder incomplete "
                    f"(got {[r.rung for r in served]})"
                )

    def test_bank_rungs_carry_cascade_provenance(self):
        from components.subject_coach_bank_hints import BANK_RUNGS

        first = BANK_RUNGS[0]
        served = rungs_for_question(
            first.question_id, choice_letter=first.choice_letter
        )
        assert served and all("@" in r.authored_by for r in served)

    def test_unknown_id_still_serves_empty_never_fabricated(self):
        assert rungs_for_question("ti-gen-does-not-exist") == []


class TestAuthoredLeakLint:
    def test_no_rung_asserts_the_answer(self):
        """Deterministic leakage lint (the generator cascade's per-rung check,
        applied to the authored interim asset): no rung states the answer."""
        for rung in AUTHORED_RUNGS:
            body = rung.body_md.lower()
            for leak_marker in (
                "the answer is",
                "correct answer is",
                "choose option",
                "pick choice",
                "the correct choice is",
            ):
                assert leak_marker not in body, (
                    f"{rung.question_id} rung {rung.rung} leaks: {leak_marker!r}"
                )
