"""Deterministic synthesis validation contracts (framework-agnostic)."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field


class SynthesisValidationResult(BaseModel):
    passed: bool
    confidence: float
    feedback: list[str] = Field(default_factory=list)


def _extract_task_branches(task_input: str) -> list[str]:
    if not task_input.strip():
        return []
    normalized = task_input.replace("\n", ". ")
    parts = [part.strip(" -.\t") for part in normalized.split(".")]
    return [part for part in parts if part]


def _branch_covered(branch: str, answer: str) -> bool:
    tokens = re.findall(r"[a-zA-Z]{4,}", branch.lower())
    if not tokens:
        return True
    answer_lc = answer.lower()
    return any(token in answer_lc for token in tokens[:3])


def validate_synthesis(
    *,
    final_answer: str,
    task_input: str,
    planning_depth: Literal["L0", "L1", "L2"],
    todos: list[dict] | None,
) -> SynthesisValidationResult:
    """Validate that final synthesis is complete enough for selected depth."""
    feedback: list[str] = []
    confidence = 1.0
    answer = (final_answer or "").strip()
    if not answer:
        return SynthesisValidationResult(
            passed=False,
            confidence=0.0,
            feedback=["Final synthesis is empty."],
        )

    open_todos = [
        todo for todo in (todos or [])
        if str(todo.get("status", "")).lower() in {"pending", "in_progress"}
    ]
    if planning_depth in {"L1", "L2"} and open_todos:
        feedback.append("Open todos remain; synthesis may be premature.")
        confidence -= 0.5

    branches = _extract_task_branches(task_input)
    if planning_depth == "L2" and len(branches) >= 2:
        covered = sum(1 for branch in branches if _branch_covered(branch, answer))
        coverage_ratio = covered / max(1, len(branches))
        if coverage_ratio < 0.6:
            feedback.append(
                f"Low branch coverage ({covered}/{len(branches)} task branches addressed)."
            )
            confidence -= 0.4

    if len(answer.split()) < 8 and planning_depth in {"L1", "L2"}:
        feedback.append("Synthesis is unusually short for medium/high planning depth.")
        confidence -= 0.2

    confidence = max(0.0, min(1.0, confidence))
    return SynthesisValidationResult(
        passed=confidence >= 0.6 and not any("empty" in item.lower() for item in feedback),
        confidence=confidence,
        feedback=feedback,
    )
