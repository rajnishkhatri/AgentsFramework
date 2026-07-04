"""Task 3.3a — open-coding cases builder (FR-G3.1.1–.3, .5–.7).

Failure paths first (TAP-4): a sub-floor mode is a HARD ERROR before any
cases.json is written (FR-G3.1.2); a confound/refused row never reaches a card
(FR-G3.1.1); an eligible row with no resolvable answer is excluded, not blanked
(FR-G3.1.3). Then the happy shape: >=100/mode, required keys, mode-contiguous,
seed-deterministic (FR-G3.1.5-.7).

The builder is a THIN ADAPTER over export_coach_coding_sample.build_coder_rows
(Stage-4: the coach answer lives in logs/evals.log EvalRecords, NOT
outcomes.jsonl). It does not re-derive the posture/manifest join.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from components.schemas import EvalRecord

from scripts.build_coach_open_coding_cases import (
    SubFloorError,
    build_cases,
    write_cases_json,
)


def _rec(
    *,
    task_id: str,
    coach_mode: str = "pre_submit",
    task_input: str = "a short learner utterance",
    response: str = "a coach reply that guides without leaking",
) -> EvalRecord:
    ai_input: dict = {"task_input": task_input}
    if coach_mode is not None:
        ai_input["coach_mode"] = coach_mode
    return EvalRecord(
        schema_version=1,
        timestamp=datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC),
        task_id=task_id,
        user_id="learner-1",
        step=0,
        target="subject_coach",
        model="gpt-4o",
        ai_input=ai_input,
        ai_response=response,
    )


def _pool(*, per_mode: int) -> list[EvalRecord]:
    """A clean eligible pool of `per_mode` rows in each mode."""
    recs: list[EvalRecord] = []
    for mode in ("pre_submit", "post_feedback"):
        for i in range(per_mode):
            recs.append(
                _rec(
                    task_id=f"{mode}-{i}",
                    coach_mode=mode,
                    task_input=f"{mode} utterance {i}",
                )
            )
    return recs


# ---------------------------------------------------------------------------
# FR-G3.1.2 — sub-floor mode is a HARD ERROR (failure path first)
# ---------------------------------------------------------------------------


class TestSubFloor:
    def test_rejects_submfloor_mode(self) -> None:
        # 100 pre, only 3 post -> post is below the 100 floor.
        recs = _pool(per_mode=100)
        recs = [r for r in recs if r.ai_input.get("coach_mode") != "post_feedback"]
        recs += [
            _rec(task_id=f"post-{i}", coach_mode="post_feedback") for i in range(3)
        ]
        with pytest.raises(SubFloorError) as ei:
            build_cases(recs, min_per_mode=100, seed=42)
        # names the short mode + its count
        assert "post_feedback" in str(ei.value)
        assert "3" in str(ei.value)

    def test_both_modes_submfloor_names_both(self) -> None:
        recs = _pool(per_mode=5)
        with pytest.raises(SubFloorError) as ei:
            build_cases(recs, min_per_mode=100, seed=42)
        assert "pre_submit" in str(ei.value)
        assert "post_feedback" in str(ei.value)


# ---------------------------------------------------------------------------
# FR-G3.1.1 — confound / refused excluded (failure path)
# ---------------------------------------------------------------------------


class TestConfoundExcluded:
    def test_excludes_confound_missing_carrier(self) -> None:
        # A row with no coach_mode carrier classifies as confound and must not
        # appear in any card. Keep 100/mode clean + 1 confound.
        recs = _pool(per_mode=100)
        recs.append(
            _rec(task_id="confound-1", coach_mode=None, task_input="no carrier")
        )
        cases = build_cases(recs, min_per_mode=100, seed=42)
        assert all(c["trace_id"] != "confound-1" for c in cases)


# ---------------------------------------------------------------------------
# FR-G3.1.3 — eligible row with no resolvable answer is excluded, not blanked
# ---------------------------------------------------------------------------


class TestNoBlankAnswerCards:
    def test_no_card_has_empty_final_answer(self) -> None:
        recs = _pool(per_mode=100)
        # An eligible-looking row whose reply is empty must not ship a blank card.
        recs.append(_rec(task_id="blank-1", coach_mode="pre_submit", response=""))
        cases = build_cases(recs, min_per_mode=100, seed=42)
        assert all(str(c.get("final_answer", "")).strip() for c in cases)
        assert all(c["trace_id"] != "blank-1" for c in cases)


# ---------------------------------------------------------------------------
# FR-G3.1.5 / .6 — happy shape: >=100/mode, required keys, mode-contiguous
# ---------------------------------------------------------------------------


class TestCasesShape:
    def test_cases_have_min_100_per_mode_and_required_keys(self) -> None:
        cases = build_cases(_pool(per_mode=120), min_per_mode=100, seed=42)
        pre = [c for c in cases if c["mode"] == "pre_submit"]
        post = [c for c in cases if c["mode"] == "post_feedback"]
        assert len(pre) >= 100
        assert len(post) >= 100
        required = {
            "trace_id",
            "mode",
            "stratum",
            "question_id",
            "prompt",
            "final_answer",
        }
        for c in cases:
            assert required <= set(c.keys()), f"missing keys on {c.get('trace_id')}"

    def test_modes_are_contiguous_blocks(self) -> None:
        cases = build_cases(_pool(per_mode=120), min_per_mode=100, seed=42)
        modes = [c["mode"] for c in cases]
        # exactly one transition between the two mode blocks
        transitions = sum(1 for a, b in zip(modes, modes[1:]) if a != b)
        assert transitions == 1, f"modes not contiguous: {transitions} transitions"


class TestCapPerMode:
    def test_cap_truncates_each_mode_to_cap(self) -> None:
        # 130 available per mode; cap at 100 → exactly 100 each.
        cases = build_cases(
            _pool(per_mode=130), min_per_mode=100, cap_per_mode=100, seed=42
        )
        pre = [c for c in cases if c["mode"] == "pre_submit"]
        post = [c for c in cases if c["mode"] == "post_feedback"]
        assert len(pre) == 100
        assert len(post) == 100

    def test_cap_is_deterministic_subset(self) -> None:
        recs = _pool(per_mode=130)
        a = build_cases(recs, min_per_mode=100, cap_per_mode=100, seed=42)
        b = build_cases(recs, min_per_mode=100, cap_per_mode=100, seed=42)
        assert [c["trace_id"] for c in a] == [c["trace_id"] for c in b]

    def test_cap_below_floor_is_rejected(self) -> None:
        # A cap under the floor is a misconfig — the floor still binds.
        with pytest.raises(ValueError):
            build_cases(_pool(per_mode=130), min_per_mode=100, cap_per_mode=50, seed=42)

    def test_no_cap_keeps_full_pool(self) -> None:
        cases = build_cases(_pool(per_mode=120), min_per_mode=100, seed=42)
        assert sum(1 for c in cases if c["mode"] == "pre_submit") == 120


# ---------------------------------------------------------------------------
# FR-G3.1.7 — deterministic for a fixed seed
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_deterministic_for_fixed_seed(self) -> None:
        recs = _pool(per_mode=130)
        a = build_cases(recs, min_per_mode=100, seed=42)
        b = build_cases(recs, min_per_mode=100, seed=42)
        assert [c["trace_id"] for c in a] == [c["trace_id"] for c in b]

    def test_different_seed_may_reorder_selection(self) -> None:
        recs = _pool(per_mode=130)
        a = build_cases(recs, min_per_mode=100, seed=42)
        c = build_cases(recs, min_per_mode=100, seed=7)
        # determinism per seed is the binding property; a different seed is
        # allowed (not required) to differ. Assert both are valid + sized.
        assert len({x["trace_id"] for x in a}) == len(a)
        assert len({x["trace_id"] for x in c}) == len(c)


# ---------------------------------------------------------------------------
# write_cases_json — array on disk the coder's /cases serves
# ---------------------------------------------------------------------------


class TestWriteCasesJson:
    def test_writes_json_array(self, tmp_path: Path) -> None:
        cases = build_cases(_pool(per_mode=110), min_per_mode=100, seed=42)
        out = tmp_path / "work" / "cases.json"
        write_cases_json(out, cases)
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(loaded, list)
        assert len(loaded) == len(cases)
        assert loaded[0]["trace_id"] == cases[0]["trace_id"]
