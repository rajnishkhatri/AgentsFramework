"""L1 Contract: deterministic per-rung leakage check (ADR-0012/ADR-0014, FR-12).

The Phase-4 verifier cascade's critical gate for hint rows: a pure,
deterministic function — the judge-assist path stays OFF until the ADR-0008
cond#1 κ floor certifies. Failure paths FIRST (TAP-4): every leak class the
check must catch is pinned before any clean rung passes.

Grounding: the Stage-0 live batch caught the coach free-generating
"rule-naming" replies that uniquely narrow to the correct choice — the
generator's rungs must be mechanically screened for the same classes.
"""

from __future__ import annotations

from components.hint_leakage import check_rung_leakage

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
    "why_tempted_md": "D's semicolon splits the subject from its own verb.",
}


class TestFailClosed:
    """Unverifiable input must never pass silently (AP-6 posture: the
    cascade treats a non-empty violation list as FAIL → quarantine)."""

    def test_question_without_answer_key_is_unverifiable(self):
        violations = check_rung_leakage(
            "What does the clause between the commas do?",
            {"id": "q", "stem_md": "..."},
        )
        assert violations, "no answer key ⇒ cannot verify ⇒ must not pass"
        assert any("unverifiable" in v for v in violations)

    def test_empty_body_is_a_violation(self):
        assert check_rung_leakage("", _QUESTION)
        assert check_rung_leakage("   \n", _QUESTION)


class TestLeakClasses:
    """Each class the deterministic gate must catch, before any happy path."""

    def test_assertive_answer_reveal(self):
        for body in (
            "The answer is B.",
            "The correct answer is B — the clause needs its closing comma.",
            "You should pick B here.",
            "Choose B and move on.",
            "Go with B.",
            "Option B is correct.",
            "B is right because the clause must close.",
        ):
            assert check_rung_leakage(body, _QUESTION), f"not flagged: {body!r}"

    def test_quoting_the_correct_choice_label(self):
        body = "Notice how 'which opened in 1974, has' closes the clause."
        assert check_rung_leakage(body, _QUESTION)

    def test_correct_label_quoted_with_different_case_and_spacing(self):
        body = "Consider: WHICH OPENED IN 1974,  HAS."
        assert check_rung_leakage(body, _QUESTION)

    def test_reciting_the_why_correct_rationale(self):
        body = (
            "Think about it: the nonrestrictive clause needs a closing comma "
            "before the verb."
        )
        assert check_rung_leakage(body, _QUESTION)

    def test_eliminating_every_distractor(self):
        body = "It's not A, you can rule out C, and D is wrong too."
        assert check_rung_leakage(body, _QUESTION)


class TestCleanRungs:
    """Real ladder shapes (probe → conceptual → directive) must pass."""

    def test_probe_rung_is_clean(self):
        assert (
            check_rung_leakage(
                "What is the clause between the commas doing in this sentence?",
                _QUESTION,
            )
            == []
        )

    def test_conceptual_rung_is_clean(self):
        assert (
            check_rung_leakage(
                "Nonrestrictive clauses add extra information — think about "
                "what punctuation they need on BOTH sides.",
                _QUESTION,
            )
            == []
        )

    def test_directive_rung_is_clean(self):
        assert (
            check_rung_leakage(
                "Look at where the clause that starts with 'which' ends, and "
                "check what mark appears there.",
                _QUESTION,
            )
            == []
        )

    def test_non_assertive_letter_mention_is_clean(self):
        """Rungs may reference choices; only asserting/uniquely narrowing to
        the correct one is a leak."""
        assert (
            check_rung_leakage(
                "Compare how A and B treat the end of the clause.", _QUESTION
            )
            == []
        )

    def test_eliminating_one_distractor_is_clean(self):
        """Ruling out a single distractor does not uniquely narrow."""
        assert (
            check_rung_leakage(
                "You can rule out D — a semicolon can't sit between a subject "
                "and its verb.",
                _QUESTION,
            )
            == []
        )

    def test_wrong_letter_assertion_still_flags_nothing_about_b(self):
        """Asserting a DISTRACTOR is pedagogically wrong but not an answer
        leak — the leakage gate only guards the key. (The grader judge owns
        content quality.)"""
        assert check_rung_leakage("A is a strong option to consider.", _QUESTION) == []


class TestDeterminism:
    def test_stable_across_repeats(self):
        body = "The answer is B."
        assert all(
            check_rung_leakage(body, _QUESTION) == check_rung_leakage(body, _QUESTION)
            for _ in range(5)
        )
