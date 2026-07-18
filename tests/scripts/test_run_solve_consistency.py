"""L1 adjudication for Step-4 solve-consistency (no live LLM)."""

from __future__ import annotations

from scripts.run_solve_consistency import adjudicate_votes


class TestAdjudicateVotes:
    def test_unanimous_match_is_pass(self) -> None:
        assert (
            adjudicate_votes(
                key="B",
                votes={"openai:fast": "B", "anthropic:fast": "B"},
            )
            == "pass"
        )

    def test_any_undecidable_quarantines(self) -> None:
        assert (
            adjudicate_votes(
                key="B",
                votes={"openai:fast": "B", "anthropic:fast": None},
            )
            == "undecidable"
        )

    def test_cross_family_disagreement_quarantines(self) -> None:
        assert (
            adjudicate_votes(
                key="B",
                votes={"openai:fast": "B", "anthropic:fast": "C"},
            )
            == "disagree"
        )

    def test_unanimous_wrong_key_is_mismatch(self) -> None:
        assert (
            adjudicate_votes(
                key="B",
                votes={"openai:fast": "A", "anthropic:fast": "A"},
            )
            == "mismatch"
        )

    def test_empty_votes_undecidable(self) -> None:
        assert adjudicate_votes(key="B", votes={}) == "undecidable"
