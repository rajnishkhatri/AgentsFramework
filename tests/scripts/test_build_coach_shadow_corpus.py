"""Batch-2 shadow-corpus driver — pure parts (bank, manifest, payloads).

Failure paths first (TAP-4): payload leak-prevention (pre-submit strip) and
quota violations are asserted before the happy-path manifest shape.
"""

from __future__ import annotations

import pytest

from scripts.build_coach_shadow_corpus import (
    ANSWER_BEARING_FIELDS,
    BANK,
    QUESTIONS,
    build_coach_context,
    build_manifest,
    build_run_body,
)

MODES = ("pre_submit", "post_feedback")


# ---------------------------------------------------------------------------
# Payload safety first: the driver must never send answer fields pre-submit
# ---------------------------------------------------------------------------


class TestCoachContextPayload:
    def test_pre_submit_context_strips_all_answer_bearing_fields(self) -> None:
        for question in QUESTIONS:
            ctx = build_coach_context(question, "pre_submit")
            assert ctx["mode"] == "pre_submit"
            for field in ANSWER_BEARING_FIELDS:
                assert field not in ctx["question"], (question["id"], field)

    def test_post_feedback_context_carries_all_four(self) -> None:
        for question in QUESTIONS:
            ctx = build_coach_context(question, "post_feedback")
            assert ctx["mode"] == "post_feedback"
            for field in ANSWER_BEARING_FIELDS:
                assert ctx["question"].get(field), (question["id"], field)

    def test_context_carries_question_and_skill_ids(self) -> None:
        ctx = build_coach_context(QUESTIONS[0], "pre_submit")
        assert ctx["question_id"] == QUESTIONS[0]["id"]
        assert ctx["skill_id"] == QUESTIONS[0]["skill_id"]

    def test_run_body_shape(self) -> None:
        body = build_run_body("no idea", QUESTIONS[0], "pre_submit", thread_id="t-1")
        assert body["agent_id"] == "subject-coach-english"
        assert body["thread_id"] == "t-1"
        assert body["input"]["messages"][-1] == {"role": "user", "content": "no idea"}
        assert body["input"]["coach_context"]["mode"] == "pre_submit"


# ---------------------------------------------------------------------------
# Bank hygiene: banks are the corpus input distribution — keep them clean
# ---------------------------------------------------------------------------


class TestBank:
    @pytest.mark.parametrize("mode", MODES)
    def test_no_duplicate_utterances_within_mode(self, mode: str) -> None:
        texts = [u.text for u in BANK[mode]]
        assert len(texts) == len(set(texts))

    @pytest.mark.parametrize("mode", MODES)
    def test_every_utterance_is_classed(self, mode: str) -> None:
        for u in BANK[mode]:
            assert u.cls, u.text

    @pytest.mark.parametrize("mode", MODES)
    def test_hard_strata_present_in_both_modes(self, mode: str) -> None:
        hard = {u.cls for u in BANK[mode] if u.cls != "breadth"}
        assert len(hard) >= 3, hard  # multiple distinct hard classes per mode

    def test_batch1_exhausted_utterances_not_reused(self) -> None:
        """Batch 1's rule-naming leak trigger must not be recycled verbatim —
        near-dupes of batch 1 would inflate the known class without new signal."""
        for mode in MODES:
            for u in BANK[mode]:
                assert u.text != "What rule is this question even testing?"


# ---------------------------------------------------------------------------
# Manifest: deterministic, quota-exact, no duplicate combos
# ---------------------------------------------------------------------------


class TestManifest:
    def test_over_capacity_target_fails_closed(self) -> None:
        with pytest.raises(ValueError):
            build_manifest(seed=7, per_mode=10_000)

    def test_deterministic_for_fixed_seed(self) -> None:
        a = build_manifest(seed=42, per_mode=100)
        b = build_manifest(seed=42, per_mode=100)
        assert a == b

    def test_different_seed_differs(self) -> None:
        assert build_manifest(seed=1, per_mode=100) != build_manifest(
            seed=2, per_mode=100
        )

    def test_quota_split_70_30(self) -> None:
        manifest = build_manifest(seed=42, per_mode=100)
        for mode in MODES:
            rows = [r for r in manifest if r.mode == mode]
            assert len(rows) == 100
            breadth = [r for r in rows if r.cls == "breadth"]
            assert len(breadth) == 70
            assert len(rows) - len(breadth) == 30

    def test_no_duplicate_utterance_question_combo(self) -> None:
        manifest = build_manifest(seed=42, per_mode=100)
        combos = [(r.mode, r.utterance, r.question_id) for r in manifest]
        assert len(combos) == len(set(combos))

    def test_every_row_resolves_to_a_known_question(self) -> None:
        ids = {q["id"] for q in QUESTIONS}
        for row in build_manifest(seed=42, per_mode=100):
            assert row.question_id in ids
