"""Planning-depth instructions and plan artifacts (framework-agnostic)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PlanningDepth = Literal["L0", "L1", "L2"]


class PlanStep(BaseModel):
    step_id: int
    title: str
    goal: str


class PlanArtifact(BaseModel):
    ordered_steps: list[PlanStep] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    success_conditions: list[str] = Field(default_factory=list)


class PlanValidationResult(BaseModel):
    is_valid: bool
    issues: list[str] = Field(default_factory=list)


def _extract_branches(task_input: str) -> list[str]:
    raw = (task_input or "").replace("\n", ". ")
    parts = [part.strip(" -.\t") for part in raw.split(".")]
    branches = [part for part in parts if part]
    return branches or ["Solve the user request directly"]


def build_plan_artifact(
    planning_depth: PlanningDepth,
    *,
    task_input: str,
) -> PlanArtifact:
    """Build a deterministic plan artifact from task input and selected depth."""
    branches = _extract_branches(task_input)
    max_steps = {"L0": 1, "L1": 3, "L2": 5}[planning_depth]
    selected = branches[:max_steps]
    steps = [
        PlanStep(step_id=index + 1, title=f"Step {index + 1}", goal=branch)
        for index, branch in enumerate(selected)
    ]
    constraints = ["Preserve user intent and requested constraints."]
    if "without" in (task_input or "").lower():
        constraints.append("Respect explicit exclusion constraints from the request.")
    success_conditions = [
        "All planned branches are addressed in the final synthesis.",
        "Final answer is concise, actionable, and internally consistent.",
    ]
    return PlanArtifact(
        ordered_steps=steps,
        constraints=constraints,
        success_conditions=success_conditions,
    )


def validate_plan_mece(plan: PlanArtifact) -> PlanValidationResult:
    """Validate plan structure and basic MECE quality checks."""
    issues: list[str] = []
    expected_step_ids = list(range(1, len(plan.ordered_steps) + 1))
    actual_step_ids = [step.step_id for step in plan.ordered_steps]
    if actual_step_ids != expected_step_ids:
        issues.append("ordered_steps must use contiguous step_id values starting at 1.")

    normalized_goals = [step.goal.strip().lower() for step in plan.ordered_steps]
    if len(normalized_goals) != len(set(normalized_goals)):
        issues.append("ordered_steps contain overlapping goals; plan is not MECE.")

    if not plan.success_conditions:
        issues.append("success_conditions must include at least one completion criterion.")

    if any(not step.goal.strip() for step in plan.ordered_steps):
        issues.append("each step must define a non-empty goal.")

    return PlanValidationResult(is_valid=not issues, issues=issues)


def build_planning_instructions(
    planning_depth: PlanningDepth,
    *,
    task_input: str,
) -> str:
    """Build system prompt addendum based on selected planning depth."""
    _ = task_input  # reserved for future heuristics/content-specific directives
    if planning_depth == "L2":
        return (
            "Planning depth L2: create a brief multi-step plan before acting, "
            "state assumptions, and validate intermediate results before final synthesis."
        )
    if planning_depth == "L1":
        return (
            "Planning depth L1: outline 2-4 concrete steps before acting, "
            "then execute in order and synthesize clearly."
        )
    return (
        "Planning depth L0: keep planning minimal, proceed directly to the most relevant "
        "action, and provide concise synthesis."
    )
