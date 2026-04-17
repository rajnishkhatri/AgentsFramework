"""Structured output for the Sprint Planning and Story Agent (backlog / PM-meta).

Pure data models — no I/O. Used with `prompts/sprint_story_agent_system.j2` and optional
YAML/JSON rendering. Aligns with patterns in `trust/review_schema.py` (frozen Pydantic).
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LayerTag(str, Enum):
    """Architectural layer tags for stories (four-layer grid + meta)."""

    foundation = "foundation"
    horizontal = "horizontal"
    vertical = "vertical"
    orchestration = "orchestration"
    meta = "meta"


class ValidationCheckName(str, Enum):
    """Eight backlog validation checks (aligned with TDD prompt analog)."""

    coverage_completeness = "coverage_completeness"
    layer_alignment = "layer_alignment"
    dependency_rule_compliance = "dependency_rule_compliance"
    failure_path_coverage = "failure_path_coverage"
    anti_pattern_scan = "anti_pattern_scan"
    contract_coverage = "contract_coverage"
    determinism_policy = "determinism_policy"
    cicd_marker_policy = "cicd_marker_policy"


class Story(BaseModel):
    """Single sprint-scoped story with architecture and test obligations."""

    id: str = Field(description="Stable slug, e.g. STORY-014")
    title: str
    phase: int = Field(ge=1, le=4, description="PLAN_v2 phase")
    layers: list[LayerTag] = Field(min_length=1)
    modules_touched: list[str] = Field(
        description="Paths under agent/, canonical per PLAN_v2",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Story ids or EXTERNAL:...",
    )
    acceptance_criteria: list[str] = Field(min_length=1)
    tdd_tier: Literal["L1", "L2", "L3", "L4"]
    test_obligations: list[str] = Field(default_factory=list)
    governance_touchpoints: dict[str, str] = Field(
        default_factory=dict,
        description="e.g. workflow_id, eval_capture targets",
    )
    style_violations_to_avoid: list[str] = Field(
        default_factory=list,
        description="Rule ids: DEP.*, T1, H1, AP2, ...",
    )

    model_config = ConfigDict(frozen=True)


class SprintTheme(BaseModel):
    """MECE theme grouping stories under a phase focus."""

    theme_id: str
    name: str
    phase_alignment: int = Field(ge=1, le=4)
    story_ids: list[str] = Field(default_factory=list)
    summary: str = ""

    model_config = ConfigDict(frozen=True)


class ValidationCheckResult(BaseModel):
    """One row in the artifact validation suite."""

    check: ValidationCheckName | str
    result: Literal["pass", "fail", "skipped"]
    details: str = ""

    model_config = ConfigDict(frozen=True)


class GapItem(BaseModel):
    """Explicit deferral or uncovered work."""

    description: str
    impact: str = ""
    deferred_to: str | None = None

    model_config = ConfigDict(frozen=True)


class SprintGaps(BaseModel):
    """Structured gaps block."""

    uncovered_plan_goals: list[str] = Field(default_factory=list)
    cross_sprint_risks: list[str] = Field(default_factory=list)
    explicit_deferrals: list[GapItem] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class SprintPlan(BaseModel):
    """Top-level output for the sprint story agent."""

    sprint_id: str
    name: str
    plan_reference: str = "PLAN_v2"
    themes: list[SprintTheme] = Field(default_factory=list)
    stories: list[Story] = Field(default_factory=list)
    validation_log: list[ValidationCheckResult] = Field(default_factory=list)
    gaps: SprintGaps = Field(default_factory=SprintGaps)

    model_config = ConfigDict(frozen=True)
