"""L2 contract tests for synthesis validation rules."""

from __future__ import annotations

from components.synthesis_validator import validate_synthesis


def test_validate_synthesis_rejects_open_todos_for_l2() -> None:
    result = validate_synthesis(
        final_answer="We should migrate in phases and validate risks.",
        task_input="Design migration and include risk controls.",
        planning_depth="L2",
        todos=[{"id": "1", "content": "Finalize risks", "status": "pending"}],
    )
    assert result.passed is False
    assert any("Open todos remain" in item for item in result.feedback)


def test_validate_synthesis_accepts_complete_answer() -> None:
    result = validate_synthesis(
        final_answer=(
            "Compare architectures, evaluate migration risks, and define a phased rollout "
            "with tests and governance checkpoints."
        ),
        task_input=(
            "Compare architectures. Evaluate migration risks. "
            "Define phased rollout and test governance checks."
        ),
        planning_depth="L2",
        todos=[{"id": "1", "content": "Done", "status": "completed"}],
    )
    assert result.passed is True
    assert result.confidence >= 0.6
