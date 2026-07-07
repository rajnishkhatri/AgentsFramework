"""Offline tests for the Fireworks candidate-screening harness (FR-7, ADR-0019).

The harness runs the frozen recert split against each candidate profile on
Fireworks and records a per-candidate scoreboard (TNR/TPR/κ/abstain) to RANK
before the full ≥3-replay cert. Its PURE core is tested here with no live call:

* ``score_candidate`` — labels → a scoreboard row (metrics from the shared
  ``coach_calibration`` helpers), abstentions dropped from the confusion.
* ``screen_candidate`` — wraps one candidate so a host that does not serve it
  (a ``TrustProviderError`` / 404) is recorded ``status="unavailable"``, never a
  fabricated 0.0 score.

The live loop (``main`` / the per-candidate replay) is manual-only, creds-gated
(``# pragma: no cover - live only``) — never wired to CI.
"""

from __future__ import annotations

import pytest

from services.governance.coach_goldset_dataset import (
    CoachGoldsetItem,
    GoldsetProvenance,
    GoldsetSplit,
)
from trust.exceptions import TrustProviderError


def _item(iid: str, leak: bool) -> CoachGoldsetItem:
    return CoachGoldsetItem(
        item_id=iid,
        learner_utterance="u",
        coach_reply="r",
        question="q",
        mode="post_feedback",
        answer_leakage=leak,
        leak_channel="rule-naming" if leak else None,
        split=GoldsetSplit.TEST,
        stratum="s",
        provenance=GoldsetProvenance.PRODUCTION,
        taxonomy_version="coach_axial_v1",
    )


# 2 leak + 2 clean; a perfect judge scores TNR=TPR=κ=1.0.
_ITEMS = [_item("T1", True), _item("T2", False), _item("T3", True), _item("T4", False)]


class TestScoreCandidate:
    def test_perfect_labels_score_all_ones(self):
        from scripts.screen_coach_candidates import score_candidate

        judge = {i.item_id: i.answer_leakage for i in _ITEMS}  # perfect
        row = score_candidate("glm-5.2-fireworks", judge_labels=judge, items=_ITEMS)
        assert row["status"] == "scored"
        assert row["model"] == "glm-5.2-fireworks"
        assert row["tpr"] == 1.0
        assert row["tnr"] == 1.0
        assert row["kappa"] == 1.0
        assert row["abstain"] == 0
        assert row["n_scored"] == 4

    def test_abstentions_drop_from_confusion_not_scored_false(self):
        """An abstained row (label missing) is NOT scored as a clean/false — it
        drops from the denominator (mirrors the cert's FR-11)."""
        from scripts.screen_coach_candidates import score_candidate

        # T3 (a leak) abstained → omitted from judge_labels entirely.
        judge = {"T1": True, "T2": False, "T4": False}
        row = score_candidate("cand", judge_labels=judge, items=_ITEMS)
        assert row["abstain"] == 1
        assert row["n_scored"] == 3
        # TNR uses the 2 clean rows (both correct) → 1.0; the dropped leak does
        # not inflate a false-negative in the TNR denominator.
        assert row["tnr"] == 1.0
        # TPR sees only T1 (the surviving leak) → 1.0.
        assert row["tpr"] == 1.0


class TestScreenCandidate:
    def test_unavailable_candidate_recorded_not_fabricated(self):
        """FR-7: a candidate the host does not serve is recorded ``unavailable``
        with the error message — NOT a fabricated 0.0-score row."""
        from scripts.screen_coach_candidates import screen_candidate

        def _raise():
            raise TrustProviderError(
                "Fireworks returned HTTP 404: model not found",
                provider="fireworks",
                operation="acompletion",
            )

        row = screen_candidate("ln-ultra-fireworks", run_labels=_raise)
        assert row["status"] == "unavailable"
        assert row["model"] == "ln-ultra-fireworks"
        assert "404" in row["error"]
        # No fabricated metrics on an unavailable candidate.
        assert row.get("tnr") is None
        assert row.get("tpr") is None

    def test_served_candidate_is_scored(self):
        """A served candidate: its labels flow through score_candidate."""
        from scripts.screen_coach_candidates import screen_candidate

        judge = {i.item_id: i.answer_leakage for i in _ITEMS}
        row = screen_candidate(
            "glm-5.2-fireworks",
            run_labels=lambda: (judge, _ITEMS),
        )
        assert row["status"] == "scored"
        assert row["tnr"] == 1.0
        assert row["model"] == "glm-5.2-fireworks"

    def test_screen_does_not_swallow_unexpected_errors(self):
        """Only provider-availability failures become ``unavailable``; a coding
        bug (e.g. KeyError) must propagate, not masquerade as unavailable."""
        from scripts.screen_coach_candidates import screen_candidate

        def _bug():
            raise KeyError("oops")

        with pytest.raises(KeyError):
            screen_candidate("cand", run_labels=_bug)
