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
