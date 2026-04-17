"""Round-trip and validation for sprint backlog structured output."""

from components.sprint_schemas import (
    GapItem,
    LayerTag,
    SprintGaps,
    SprintPlan,
    SprintTheme,
    Story,
    ValidationCheckName,
    ValidationCheckResult,
)


def test_sprint_plan_minimal_roundtrip() -> None:
    plan = SprintPlan(
        sprint_id="SPRINT-01",
        name="Foundation hardening",
        themes=[
            SprintTheme(
                theme_id="T1",
                name="Trust kernel tests",
                phase_alignment=1,
                story_ids=["STORY-001"],
            )
        ],
        stories=[
            Story(
                id="STORY-001",
                title="Add signature tamper tests",
                phase=1,
                layers=[LayerTag.foundation],
                modules_touched=["agent/trust/signature.py"],
                acceptance_criteria=["Tampered signed field fails verify_signature"],
                tdd_tier="L1",
                style_violations_to_avoid=["DEP.trust_no_upward", "T1"],
            )
        ],
        validation_log=[
            ValidationCheckResult(
                check=ValidationCheckName.layer_alignment,
                result="pass",
                details="Story maps to trust/",
            )
        ],
        gaps=SprintGaps(
            uncovered_plan_goals=[],
            explicit_deferrals=[
                GapItem(description="AWS live STS", deferred_to="Phase 3")
            ],
        ),
    )
    dumped = plan.model_dump(mode="json")
    restored = SprintPlan.model_validate(dumped)
    assert restored.stories[0].tdd_tier == "L1"
    assert restored.gaps.explicit_deferrals[0].deferred_to == "Phase 3"
