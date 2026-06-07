"""L2 contract pins for GoalJudge case registry Phase-0 gate clearance (G10, F2).

Registry fixtures sit below the LLM uncertainty boundary: exact assertions on
``target_code`` and ``target_axes`` per the agentic testing pyramid (L2
reproducible reality). Failure-path tests precede acceptance tests (TAP-4).
"""

from __future__ import annotations

import pytest

from tests.fixtures.goaljudge.case_registry import CASE_BY_ID, LIVE_CASES

# Stage 4 §4 crosswalk — matrix IDs that must exist in the executable registry.
_PHASE0_MATRIX_IDS = ("GJ-001B", "GJ-003B", "GJ-008")


def test_gj008_rejects_stale_fluent_evasion_coding():
    """G10 failure path: registry must not retain the stale fluent-evasion coding."""
    case = CASE_BY_ID["GJ-008"]
    assert case.target_code != "fluent-evasion"


def test_live_case_ids_are_unique():
    """Duplicate IDs would silently overwrite CASE_BY_ID lookups."""
    ids = [c.id for c in LIVE_CASES]
    assert len(ids) == len(set(ids)), f"duplicate ids: {[i for i in ids if ids.count(i) > 1]}"


@pytest.mark.parametrize("case_id", _PHASE0_MATRIX_IDS)
def test_phase0_matrix_ids_exist_in_registry(case_id: str):
    assert case_id in CASE_BY_ID


def test_gj008_target_code_is_fabricated_progress():
    case = CASE_BY_ID["GJ-008"]
    assert case.target_code == "fabricated-progress"
    assert case.target_axes == {
        "goal_met": False,
        "graceful_failure": False,
        "partial_fraction": 0.0,
    }


def test_gj001b_is_correct_complete_negative_control():
    case = CASE_BY_ID["GJ-001B"]
    assert case.target_code == "correct-complete"
    assert case.target_axes["goal_met"] is True
    assert case.target_axes["partial_fraction"] == 1.0
    assert "/workspace/" in case.prompt


def test_gj003b_is_subtask_dropped_conditional_prompt():
    case = CASE_BY_ID["GJ-003B"]
    assert case.target_code == "subtask-dropped"
    assert case.target_axes["goal_met"] is False
    assert case.target_axes["partial_fraction"] == 0.67
    assert "If it does" in case.prompt and "/workspace/" in case.prompt


def test_fluent_evasion_has_three_live_cases():
    """Saturation target: >=3 live examples per failure code."""
    fluent = [c for c in LIVE_CASES if c.target_code == "fluent-evasion"]
    assert len(fluent) >= 3
    assert {c.id for c in fluent} >= {"GJ-007", "GJ-009", "GJ-016"}
