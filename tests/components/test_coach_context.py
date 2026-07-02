"""L2 Contract: coach-context prompt formatter (ADR-0012, review finding I3).

Mirrors the ``memory_context`` OBP-1 pattern: a framework-agnostic formatter
that turns the sanitized ``coach_context`` state channel into an
``additional_instructions`` block. Failure paths first (TAP-6): the
pre-submit re-strip (defense in depth behind the BFF sanitizer) is pinned
before any happy-path rendering.

Pure function, deterministic, no mocks (TAP-2).
"""

from __future__ import annotations

from components.coach_context import (
    coach_context_contract,
    render_coach_context_block,
)

_QUESTION = {
    "id": "q-punc-1",
    "stem": "Which choice best fixes the underlined portion?",
    "context_html": "The museum, <u>which opened in 1974 has</u> welcomed visitors.",
    "choices": [
        {"letter": "A", "label": "NO CHANGE"},
        {"letter": "B", "label": "which opened in 1974, has"},
    ],
    "answer_letter": "B",
    "per_choice_rationale": {"A": "leaves the clause unclosed"},
    "why_correct_md": "closes the nonrestrictive clause",
    "why_tempted_md": "reads fine aloud",
    "rule_md": "Nonrestrictive clauses take paired commas.",
}


def _context(mode: str) -> dict:
    return {
        "mode": mode,
        "question_id": "q-punc-1",
        "skill_id": "s-punc",
        "question": dict(_QUESTION),
    }


class TestPreSubmitReStrip:
    """Failure path FIRST: answer-bearing fields never render pre-submit,
    even when present in the payload (a BFF strip that was evaded)."""

    def test_answer_fields_absent_pre_submit(self):
        block = render_coach_context_block(_context("pre_submit"))
        assert "closes the nonrestrictive clause" not in block
        assert "reads fine aloud" not in block
        assert "leaves the clause unclosed" not in block
        assert "correct answer" not in block

    def test_unknown_mode_fails_closed_to_pre_submit(self):
        ctx = _context("totally_bogus_mode")
        block = render_coach_context_block(ctx)
        assert "pre_submit" in block
        assert "closes the nonrestrictive clause" not in block

    def test_missing_mode_fails_closed_to_pre_submit(self):
        ctx = _context("pre_submit")
        del ctx["mode"]
        block = render_coach_context_block(ctx)
        assert "pre_submit" in block
        assert "closes the nonrestrictive clause" not in block


class TestRendering:
    def test_none_and_empty_render_empty_string(self):
        assert render_coach_context_block(None) == ""
        assert render_coach_context_block({}) == ""

    def test_pre_submit_renders_stem_choices_and_mode(self):
        block = render_coach_context_block(_context("pre_submit"))
        assert "pre_submit" in block
        assert "Which choice best fixes the underlined portion?" in block
        assert "A) NO CHANGE" in block
        assert "B) which opened in 1974, has" in block
        assert "q-punc-1" in block

    def test_post_feedback_renders_the_full_rationale(self):
        block = render_coach_context_block(_context("post_feedback"))
        assert "post_feedback" in block
        assert "closes the nonrestrictive clause" in block
        assert "reads fine aloud" in block
        assert "leaves the clause unclosed" in block
        assert "B" in block

    def test_deterministic(self):
        a = render_coach_context_block(_context("post_feedback"))
        b = render_coach_context_block(_context("post_feedback"))
        assert a == b

    def test_non_mapping_question_is_tolerated(self):
        ctx = _context("pre_submit")
        ctx["question"] = "not-a-record"
        block = render_coach_context_block(ctx)
        assert "pre_submit" in block


_ALL_ANSWER_FIELDS = {
    "answer_letter",
    "per_choice_rationale",
    "why_correct_md",
    "why_tempted_md",
}


class TestCoachContextContract:
    """§13 audit finding F1: the assembly facts need a trace carrier. The
    contract is the pure payload — {mode, answer_fields_rendered,
    answer_fields_stripped} — the orchestrator records as ONE
    ``guardrail_checked`` event per coach turn. Failure paths first."""

    def test_no_context_yields_no_contract(self):
        assert coach_context_contract(None) is None
        assert coach_context_contract({}) is None
        assert coach_context_contract("not-a-mapping") is None

    def test_spoofed_mode_fails_closed_to_pre_submit(self):
        contract = coach_context_contract(_context("POST_FEEDBACK"))
        assert contract is not None
        assert contract["mode"] == "pre_submit"
        assert contract["answer_fields_rendered"] == []

    def test_pre_submit_reports_the_stripped_fields(self):
        """An evaded BFF strip is VISIBLE in the carrier: the payload carried
        all four answer fields, none rendered, all stripped."""
        contract = coach_context_contract(_context("pre_submit"))
        assert contract["mode"] == "pre_submit"
        assert contract["answer_fields_rendered"] == []
        assert set(contract["answer_fields_stripped"]) == _ALL_ANSWER_FIELDS

    def test_post_feedback_reports_the_rendered_fields(self):
        contract = coach_context_contract(_context("post_feedback"))
        assert contract["mode"] == "post_feedback"
        assert set(contract["answer_fields_rendered"]) == _ALL_ANSWER_FIELDS
        assert contract["answer_fields_stripped"] == []

    def test_question_absent_reports_empty_field_lists(self):
        contract = coach_context_contract({"mode": "post_feedback", "skill_id": "s"})
        assert contract["mode"] == "post_feedback"
        assert contract["answer_fields_rendered"] == []
        assert contract["answer_fields_stripped"] == []

    def test_contract_mode_matches_what_the_renderer_uses(self):
        """One mode derivation, two consumers: the carrier must never claim a
        mode the renderer didn't apply."""
        for raw in ("pre_submit", "post_feedback", "bogus"):
            ctx = _context(raw)
            contract = coach_context_contract(ctx)
            block = render_coach_context_block(ctx)
            assert f"(mode: {contract['mode']})" in block
