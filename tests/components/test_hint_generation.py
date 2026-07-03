"""L1 Contract: the hint verifier cascade (Phase 4, ADR-0012/ADR-0014, FR-12).

Cascade order is load-bearing: schema-parse → deterministic per-rung leakage
check → duplicate/similarity. PASS flips ``reviewed=True`` (the cascade IS the
reviewer — deterministic-first; judge assist stays out until the ADR-0008
cond#1 κ floor certifies). FAIL → quarantine row with the owning stage +
violations, never a served hint. Failure paths FIRST (TAP-4).
"""

from __future__ import annotations

import json

from components.hint_generation import run_hint_cascade

_QUESTION = {
    "id": "q-comma-021",
    "stem_md": "The museum, which opened in 1974 has welcomed visitors.",
    "answer_letter": "B",
    "choices": [
        {"letter": "A", "label": "NO CHANGE"},
        {"letter": "B", "label": "which opened in 1974, has"},
        {"letter": "C", "label": "that opened in 1974, has"},
        {"letter": "D", "label": "opened in 1974; has"},
    ],
    "why_correct_md": "The nonrestrictive clause needs a closing comma before the verb.",
}

_CLEAN_LADDER = {
    "rungs": [
        {"rung": 1, "body_md": "What is the clause between the commas doing here?"},
        {"rung": 2, "body_md": "Droppable clauses need fencing on BOTH sides."},
        {"rung": 3, "body_md": "Find where the clause ends and check that spot."},
    ]
}


def _run(reply: str, existing: list[str] | None = None):
    return run_hint_cascade(
        reply,
        question=_QUESTION,
        subject="act-english",
        existing_bodies=existing or [],
        generated_by="gpt-4o-mini@run-42",
    )


class TestSchemaStage:
    """Stage 1 — a malformed reply quarantines at 'schema', never later."""

    def test_non_json_reply_quarantines(self):
        verdict = _run("Sure! Here are some hints...")
        assert verdict.passed == []
        assert verdict.quarantined
        assert all(q["stage"] == "schema" for q in verdict.quarantined)

    def test_assertion_rung_is_unrepresentable(self):
        reply = json.dumps({"rungs": [{"rung": 4, "body_md": "The answer is B."}]})
        verdict = _run(reply)
        assert verdict.passed == []
        assert verdict.quarantined[0]["stage"] == "schema"

    def test_empty_body_quarantines_at_schema(self):
        reply = json.dumps({"rungs": [{"rung": 1, "body_md": "  "}]})
        verdict = _run(reply)
        assert verdict.passed == []
        assert verdict.quarantined[0]["stage"] == "schema"

    def test_duplicate_rung_level_within_ladder_quarantines(self):
        reply = json.dumps(
            {
                "rungs": [
                    {"rung": 1, "body_md": "First probe."},
                    {"rung": 1, "body_md": "Second probe at the same level."},
                ]
            }
        )
        verdict = _run(reply)
        # One rung per level (ADR-0014 unique index): the second is quarantined.
        assert len(verdict.passed) == 1
        assert verdict.quarantined[0]["stage"] == "schema"


class TestLeakageStage:
    """Stage 2 — the critical gate: a leaking rung NEVER earns reviewed."""

    def test_answer_assertion_quarantines_with_violations(self):
        reply = json.dumps(
            {"rungs": [{"rung": 3, "body_md": "You should pick B here."}]}
        )
        verdict = _run(reply)
        assert verdict.passed == []
        q = verdict.quarantined[0]
        assert q["stage"] == "leakage"
        assert q["violations"]

    def test_clean_rungs_pass_while_the_leaking_one_quarantines(self):
        reply = json.dumps(
            {
                "rungs": [
                    {"rung": 1, "body_md": "What is the clause doing here?"},
                    {"rung": 2, "body_md": "The correct answer is B."},
                ]
            }
        )
        verdict = _run(reply)
        assert [r["rung"] for r in verdict.passed] == [1]
        assert verdict.quarantined[0]["stage"] == "leakage"


class TestDuplicateStage:
    """Stage 3 — near-duplicates of existing content are quarantined."""

    def test_exact_duplicate_of_existing_body_quarantines(self):
        existing = ["What is the clause between the commas doing here?"]
        verdict = _run(json.dumps(_CLEAN_LADDER), existing=existing)
        stages = {q["stage"] for q in verdict.quarantined}
        assert stages == {"duplicate"}
        assert len(verdict.passed) == 2  # rungs 2 and 3 survive

    def test_near_duplicate_with_trivial_rewording_quarantines(self):
        existing = ["what is the clause between the commas doing here"]
        verdict = _run(json.dumps(_CLEAN_LADDER), existing=existing)
        assert any(q["stage"] == "duplicate" for q in verdict.quarantined)


class TestPassPath:
    def test_clean_ladder_earns_reviewed_true_with_provenance(self):
        verdict = _run(json.dumps(_CLEAN_LADDER))
        assert verdict.quarantined == []
        assert [r["rung"] for r in verdict.passed] == [1, 2, 3]
        for row in verdict.passed:
            assert row["reviewed"] is True
            assert row["generated_by"] == "gpt-4o-mini@run-42"
            assert row["subject"] == "act-english"
            assert row["question_id"] == "q-comma-021"
            assert row["id"]

    def test_row_ids_are_deterministic_across_reruns(self):
        a = _run(json.dumps(_CLEAN_LADDER)).passed
        b = _run(json.dumps(_CLEAN_LADDER)).passed
        assert [r["id"] for r in a] == [r["id"] for r in b]

    def test_json_inside_prose_fences_is_extracted(self):
        reply = "Here you go:\n```json\n" + json.dumps(_CLEAN_LADDER) + "\n```"
        verdict = _run(reply)
        assert len(verdict.passed) == 3
