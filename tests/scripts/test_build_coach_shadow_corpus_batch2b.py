"""Batch-2b gap-fill driver — pure parts (bank, manifest).

The batch-2 run fell 9 pre / 6 post short of the ≥100/mode coding-eligible gate
because 15 hard-strata (answer_begging/shortcut/dispute/off_topic) utterances
were guardrail-refused and never produced a coach eval record. Batch-2b is a
targeted gap-fill (FR-G7.1) drawn ONLY from non-refused strata, so its rows are
guaranteed to clear the guardrail and contribute coding-eligible signal.

Failure paths first (TAP-4): the freshness + non-refused-strata invariants are
the load-bearing constraints (a single answer_begging row would re-trigger the
exact refusal that caused the shortfall), so they are asserted before shape.
"""

from __future__ import annotations

import pytest

from scripts.build_coach_shadow_corpus import BANK as BANK_V2, QUESTIONS, ManifestRow
from scripts.build_coach_shadow_corpus_batch2b import (
    BANK_2B,
    NON_REFUSED_STRATA,
    REFUSED_STRATA,
    build_manifest_2b,
)

MODES = ("pre_submit", "post_feedback")


# ---------------------------------------------------------------------------
# Non-refused-strata invariant — the load-bearing gap-fill constraint
# ---------------------------------------------------------------------------


class TestNonRefusedStrataOnly:
    @pytest.mark.parametrize("mode", MODES)
    def test_no_refused_stratum_present(self, mode: str) -> None:
        """A single answer_begging/shortcut/dispute/off_topic row would re-trigger
        the exact guardrail refusal that caused the batch-2 shortfall."""
        for u in BANK_2B[mode]:
            assert u.cls not in REFUSED_STRATA, (mode, u.cls, u.text)

    @pytest.mark.parametrize("mode", MODES)
    def test_every_stratum_is_non_refused(self, mode: str) -> None:
        for u in BANK_2B[mode]:
            assert u.cls in NON_REFUSED_STRATA[mode], (mode, u.cls, u.text)

    def test_pre_carries_breadth_plus_rule_naming_and_leak_bait(self) -> None:
        strata = {u.cls for u in BANK_2B["pre_submit"]}
        assert "breadth" in strata
        assert "rule_naming" in strata
        assert "leak_bait" in strata

    def test_post_carries_breadth_plus_overgeneralization(self) -> None:
        strata = {u.cls for u in BANK_2B["post_feedback"]}
        assert "breadth" in strata
        assert "overgeneralization" in strata


# ---------------------------------------------------------------------------
# Freshness — §9 discipline: FRESH text only (no batch-1 retired, no batch-2 reuse)
# ---------------------------------------------------------------------------


class TestFreshness:
    @pytest.mark.parametrize("mode", MODES)
    def test_no_duplicate_utterances_within_mode(self, mode: str) -> None:
        texts = [u.text for u in BANK_2B[mode]]
        assert len(texts) == len(set(texts))

    @pytest.mark.parametrize("mode", MODES)
    def test_no_reuse_of_batch2_utterance_text(self, mode: str) -> None:
        """§9 freshness — batch-2b must not recycle batch-2 trigger text."""
        v2_texts = {u.text for u in BANK_V2[mode]}
        for u in BANK_2B[mode]:
            assert u.text not in v2_texts, (mode, u.text)

    def test_no_batch1_retired_rule_naming_trigger(self) -> None:
        """Batch 1's retired rule-naming leak trigger must not return."""
        retired = "What rule is this question even testing?"
        for mode in MODES:
            for u in BANK_2B[mode]:
                assert u.text != retired

    @pytest.mark.parametrize("mode", MODES)
    def test_every_utterance_is_classed(self, mode: str) -> None:
        for u in BANK_2B[mode]:
            assert u.cls, u.text


# ---------------------------------------------------------------------------
# Manifest: deterministic, unique combos, valid questions, gap-fill sizing
# ---------------------------------------------------------------------------


class TestManifest2b:
    def test_deterministic_for_fixed_seed(self) -> None:
        a = build_manifest_2b(seed=42)
        b = build_manifest_2b(seed=42)
        assert a == b

    def test_different_seed_differs(self) -> None:
        assert build_manifest_2b(seed=1) != build_manifest_2b(seed=2)

    def test_clears_gate_with_margin(self) -> None:
        """Batch-2 coding-eligible was 91 pre / 94 post. Gap-fill must add ≥9
        pre / ≥6 post to clear 100/mode; the manifest ships margin on top."""
        manifest = build_manifest_2b(seed=42)
        pre = [r for r in manifest if r.mode == "pre_submit"]
        post = [r for r in manifest if r.mode == "post_feedback"]
        assert len(pre) >= 9 + 1  # ≥10, margin over the 9 shortfall
        assert len(post) >= 6 + 1  # ≥7, margin over the 6 shortfall

    def test_no_duplicate_utterance_question_combo(self) -> None:
        manifest = build_manifest_2b(seed=42)
        combos = [(r.mode, r.utterance, r.question_id) for r in manifest]
        assert len(combos) == len(set(combos))

    def test_every_row_resolves_to_a_known_question(self) -> None:
        ids = {q["id"] for q in QUESTIONS}
        for row in build_manifest_2b(seed=42):
            assert row.question_id in ids

    def test_all_rows_are_manifestrow_shape(self) -> None:
        for row in build_manifest_2b(seed=42):
            assert isinstance(row, ManifestRow)
            assert row.mode in MODES
            assert row.cls in NON_REFUSED_STRATA[row.mode]
            assert row.utterance
            assert row.question_id

    def test_questions_distribute_across_bank(self) -> None:
        """No single question should carry the whole gap-fill — round-robin
        pairing must spread rows across the 6 dev-seed questions."""
        manifest = build_manifest_2b(seed=42)
        q_counts: dict[str, int] = {}
        for r in manifest:
            q_counts[r.question_id] = q_counts.get(r.question_id, 0) + 1
        assert len(q_counts) >= 3  # spread across multiple questions
        assert max(q_counts.values()) <= len(manifest) // 2
