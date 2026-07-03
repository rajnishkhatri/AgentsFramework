"""L2 contract for scripts/promote_test_item_seed.py (Phase 6, FR-25).

The convert:test01 demotion path: a seed enters at reviewed=false and is
promoted ONLY by the FR-23 cascade (re-verification incl. the solver key gate).
Failure paths first (TAP-4): a self-stamped reviewed:true seed row must be
DEMOTED on entry before any promotion, and a seed the solver disagrees with
must stay quarantined — before the clean promotion path.

The solver is injected (no live LLM). The seed is a JSON list of item dicts.
"""

from __future__ import annotations

import json

from scripts.promote_test_item_seed import demote_seed_row, promote_seed

_SEED_ITEM = {
    "stem_md": "Neither of the twins were ready for the exam.",
    "answer_letter": "C",
    "choices": [
        {"letter": "A", "label": "NO CHANGE"},
        {"letter": "B", "label": "were ready for their"},
        {"letter": "C", "label": "was ready for the"},
        {"letter": "D", "label": "was ready for their"},
    ],
    "skill_id": "s-gram",
    "difficulty": 3,
    # The converter self-stamps these — they must be retroactively unearned.
    "reviewed": True,
    "generated_by": "test01-import",
}


def _solver_returning(letter: str):
    async def solve(item):
        return letter

    return solve


class TestDemoteSeedRow:
    def test_self_stamped_reviewed_is_stripped_to_false(self):
        demoted = demote_seed_row(_SEED_ITEM)
        assert demoted["reviewed"] is False

    def test_declared_key_and_content_survive_demotion(self):
        demoted = demote_seed_row(_SEED_ITEM)
        assert demoted["answer_letter"] == "C"
        assert demoted["stem_md"] == _SEED_ITEM["stem_md"]
        assert [c["letter"] for c in demoted["choices"]] == ["A", "B", "C", "D"]


class TestPromoteSeed:
    async def test_solver_disagreement_stays_quarantined(self, tmp_path):
        seed = tmp_path / "seed.json"
        seed.write_text(json.dumps([_SEED_ITEM]))
        verdict = await promote_seed(
            seed,
            solver=_solver_returning("A"),  # disagrees with declared "C"
            existing_stems=[],
            generated_by="gpt-4o-mini@run-99",
        )
        assert verdict.passed == []
        assert verdict.quarantined[0]["stage"] == "answer_key"

    async def test_agreeing_seed_promotes_and_restamps_provenance(self, tmp_path):
        seed = tmp_path / "seed.json"
        seed.write_text(json.dumps([_SEED_ITEM]))
        verdict = await promote_seed(
            seed,
            solver=_solver_returning("C"),
            existing_stems=[],
            generated_by="gpt-4o-mini@run-99",
        )
        assert len(verdict.passed) == 1
        row = verdict.passed[0]
        assert row["reviewed"] is True
        # test01-import never appears on a reviewed=true row (ADR-0015 clause 6).
        assert row["generated_by"] == "gpt-4o-mini@run-99"
        assert row["answer_letter"] == "C"
