"""L1 Contract: the test-item verifier cascade (Phase 6, ADR-0015, FR-23).

Second content family after hints (`test_item_generation.py` mirrors
`hint_generation.py`). Cascade order is load-bearing: schema-parse →
answer-key consistency (an INDEPENDENT solver pass, the critical gate) →
duplicate/similarity. PASS flips ``reviewed=True`` (the cascade IS the
reviewer — never self-stamped). FAIL or undecidable → quarantine row with the
owning stage + violations, never a served item (AP-6). Failure paths FIRST
(TAP-4).

The solver is INJECTED (the `hint_generation.py` provider seam) so these tests
are pure/deterministic with no live LLM: a stub solver replays a canned letter
(or an empty/garbled reply for the undecidable path).
"""

from __future__ import annotations

import json

from components.test_item_generation import (
    extract_solver_letter,
    run_test_item_cascade,
)

# A well-formed candidate: ACT-English underlined-span MC, key = "B".
_CANDIDATE = {
    "stem_md": "The committee were unanimous in their decision.",
    "answer_letter": "B",
    "choices": [
        {"letter": "A", "label": "NO CHANGE"},
        {"letter": "B", "label": "was unanimous in its"},
        {"letter": "C", "label": "were unanimous in its"},
        {"letter": "D", "label": "was unanimous in their"},
    ],
    "skill_id": "s-gram",
    "difficulty": 3,
}


def _solver_returning(*letters: str):
    """A stub solver: replays one canned reply per call (round-robin over the
    batch), recording the prompts it saw so a test can assert the key was
    withheld."""
    replies = list(letters)
    calls: list[dict] = []

    async def solve(item: dict) -> str:
        calls.append(item)
        return replies[(len(calls) - 1) % len(replies)]

    solve.calls = calls  # type: ignore[attr-defined]
    return solve


async def _run(reply: str, *, solver=None, existing=None):
    return await run_test_item_cascade(
        reply,
        subject="act-english",
        solver=solver or _solver_returning("B"),
        existing_stems=existing or [],
        generated_by="gpt-4o-mini@run-77",
    )


class TestSchemaStage:
    """Stage 1 — a malformed candidate quarantines at 'schema', never later.

    The solver must NOT be reached for a schema failure (a malformed item can't
    be solved); the stub is set to raise if called.
    """

    async def _solver_must_not_run(self):
        async def solve(item: dict) -> str:
            raise AssertionError("solver reached on a schema-stage failure")

        return solve

    async def test_non_json_reply_quarantines(self):
        verdict = await _run(
            "Sure! Here is a question...", solver=await self._solver_must_not_run()
        )
        assert verdict.passed == []
        assert verdict.quarantined
        assert all(q["stage"] == "schema" for q in verdict.quarantined)

    async def test_missing_items_key_quarantines(self):
        verdict = await _run(
            json.dumps({"questions": []}), solver=await self._solver_must_not_run()
        )
        assert verdict.passed == []
        assert verdict.quarantined[0]["stage"] == "schema"

    async def test_answer_letter_not_in_choices_quarantines(self):
        bad = {**_CANDIDATE, "answer_letter": "Z"}
        verdict = await _run(
            json.dumps({"items": [bad]}), solver=await self._solver_must_not_run()
        )
        assert verdict.passed == []
        assert verdict.quarantined[0]["stage"] == "schema"

    async def test_empty_stem_quarantines(self):
        bad = {**_CANDIDATE, "stem_md": "   "}
        verdict = await _run(
            json.dumps({"items": [bad]}), solver=await self._solver_must_not_run()
        )
        assert verdict.passed == []
        assert verdict.quarantined[0]["stage"] == "schema"

    async def test_too_few_choices_quarantines(self):
        bad = {**_CANDIDATE, "choices": _CANDIDATE["choices"][:2]}
        verdict = await _run(
            json.dumps({"items": [bad]}), solver=await self._solver_must_not_run()
        )
        assert verdict.passed == []
        assert verdict.quarantined[0]["stage"] == "schema"


class TestExtractSolverLetter:
    """The pure comparator (FR-23.3), parity-pinned to `ExactLetterGrader`
    semantics: a solver reply is decided by the single choice letter it names.
    A bare letter, a fenced letter, and a letter-with-prose all extract; an
    ambiguous or letter-free reply is undecidable → None."""

    def test_bare_letter(self):
        assert extract_solver_letter("B", {"A", "B", "C", "D"}) == "B"

    def test_letter_with_prose_extracts(self):
        # "The answer is C because…" — the grader compares letters, so the
        # comparator must pull the named letter out of chatty prose.
        assert (
            extract_solver_letter(
                "The answer is C because the verb must agree.", {"A", "B", "C", "D"}
            )
            == "C"
        )

    def test_lowercase_answer_prefix(self):
        assert extract_solver_letter("answer: d", {"A", "B", "C", "D"}) == "D"

    def test_ambiguous_two_letters_is_undecidable(self):
        # Names both A and C with no single verdict → undecidable, not a guess.
        assert (
            extract_solver_letter("It's between A and C.", {"A", "B", "C", "D"}) is None
        )

    def test_no_letter_is_undecidable(self):
        assert extract_solver_letter("I am not sure.", {"A", "B", "C", "D"}) is None

    def test_empty_reply_is_undecidable(self):
        assert extract_solver_letter("", {"A", "B", "C", "D"}) is None

    def test_letter_outside_choice_set_is_undecidable(self):
        # Solver names 'F' but the item is A–D → not a valid verdict.
        assert extract_solver_letter("F", {"A", "B", "C", "D"}) is None


class TestSolverKeyGate:
    """Stage 2 — the critical gate (FR-23.3). Failure paths FIRST: a key the
    solver disagrees with, and an undecidable reply, both quarantine BEFORE the
    agreeing (passing) path."""

    async def test_key_mismatch_quarantines(self):
        # Declared key is "B"; independent solver says "C" → quarantine.
        verdict = await _run(
            json.dumps({"items": [_CANDIDATE]}), solver=_solver_returning("C")
        )
        assert verdict.passed == []
        assert verdict.quarantined[0]["stage"] == "answer_key"

    async def test_undecidable_solver_reply_quarantines(self):
        # Empty/garbled solver reply → undecidable → quarantine (AP-6), never a
        # fabricated pass.
        verdict = await _run(
            json.dumps({"items": [_CANDIDATE]}), solver=_solver_returning("")
        )
        assert verdict.passed == []
        assert verdict.quarantined[0]["stage"] == "answer_key"

    async def test_key_match_passes(self):
        verdict = await _run(
            json.dumps({"items": [_CANDIDATE]}), solver=_solver_returning("B")
        )
        assert verdict.quarantined == []
        assert len(verdict.passed) == 1
        assert verdict.passed[0]["answer_letter"] == "B"
        assert verdict.passed[0]["reviewed"] is True

    async def test_solver_never_sees_the_declared_key(self):
        # FR-23.3: the item handed to the solver must carry stem + choices but
        # NOT answer_letter (a solver that sees the key can't independently
        # confirm it).
        solver = _solver_returning("B")
        await _run(json.dumps({"items": [_CANDIDATE]}), solver=solver)
        assert solver.calls, "solver was never reached"
        seen = solver.calls[0]
        assert "answer_letter" not in seen
        assert seen["stem_md"] == _CANDIDATE["stem_md"]
        assert [c["letter"] for c in seen["choices"]] == ["A", "B", "C", "D"]


class TestDuplicateStage:
    """Stage 3 — a key-consistent item that duplicates an existing bank stem
    quarantines at 'duplicate' (FR-23.1). Runs AFTER the solver gate, so a
    duplicate is only reached once the item is otherwise sound."""

    async def test_exact_existing_stem_quarantines(self):
        verdict = await _run(
            json.dumps({"items": [_CANDIDATE]}),
            solver=_solver_returning("B"),
            existing=[_CANDIDATE["stem_md"]],
        )
        assert verdict.passed == []
        assert verdict.quarantined[0]["stage"] == "duplicate"

    async def test_near_duplicate_within_batch_quarantines(self):
        # Two items with the same stem in one batch: the second is a duplicate
        # of the first (accepted) one.
        second = {**_CANDIDATE, "answer_letter": "B"}
        verdict = await _run(
            json.dumps({"items": [_CANDIDATE, second]}),
            solver=_solver_returning("B", "B"),
        )
        assert len(verdict.passed) == 1
        assert len(verdict.quarantined) == 1
        assert verdict.quarantined[0]["stage"] == "duplicate"


class TestReviewedProvenanceAndIdempotency:
    """FR-23.5 — reviewed earned in-cascade only, content-hash id idempotent."""

    async def test_reviewed_row_carries_cascade_provenance(self):
        verdict = await _run(
            json.dumps({"items": [_CANDIDATE]}), solver=_solver_returning("B")
        )
        row = verdict.passed[0]
        assert row["reviewed"] is True
        assert row["generated_by"] == "gpt-4o-mini@run-77"
        assert row["id"].startswith("ti-gen-")

    async def test_self_stamped_reviewed_is_ignored_and_re_earned(self):
        # A candidate that self-asserts reviewed=true must NOT ride that in;
        # the emitted row's reviewed is the cascade's, not the input's.
        sneaky = {**_CANDIDATE, "reviewed": True, "generated_by": "test01-import"}
        verdict = await _run(
            json.dumps({"items": [sneaky]}), solver=_solver_returning("B")
        )
        row = verdict.passed[0]
        assert row["generated_by"] == "gpt-4o-mini@run-77"  # re-stamped

    async def test_row_id_is_stable_across_reruns(self):
        ids = []
        for _ in range(10):
            verdict = await _run(
                json.dumps({"items": [_CANDIDATE]}), solver=_solver_returning("B")
            )
            ids.append(verdict.passed[0]["id"])
        assert len(set(ids)) == 1  # deterministic content hash
