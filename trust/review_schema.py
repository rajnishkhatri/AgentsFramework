"""Structured output models for the Code Review Validator Agent.

Pure data -- no I/O, no storage, no network. Satisfies T1-T4.
These models define the review report structure that the agent
produces as its final output.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    """How severe a finding is."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class Verdict(str, Enum):
    """Governing verdict for a review."""

    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"


class DimensionStatus(str, Enum):
    """Per-dimension pass/fail status."""

    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    SKIPPED = "skipped"


class Certificate(BaseModel):
    """Semi-formal reasoning certificate for a single finding.

    Captures the premises (evidence), optional traces (dependency or execution
    chains), and a rule-scoped conclusion so that every finding is auditable.
    """

    premises: list[str] = Field(
        description="Tool output or code observations with line numbers"
    )
    traces: list[str] = Field(
        default_factory=list,
        description="Dependency chain or execution path",
    )
    conclusion: str = Field(
        description="rule_id PASS|FAIL -- one-sentence justification"
    )

    model_config = ConfigDict(frozen=True)


class ReviewFinding(BaseModel):
    """A single violation or observation discovered during review."""

    rule_id: str = Field(description="e.g. D1.R3, D2.H1, D5.AP4")
    dimension: str = Field(description="D1-D5 dimension name")
    severity: Severity
    file: str
    line: int | None = None
    description: str
    fix_suggestion: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    certificate: Certificate

    model_config = ConfigDict(frozen=True)


class DimensionResult(BaseModel):
    """Aggregated result for one of the five validation dimensions."""

    dimension: str = Field(description="D1-D5 identifier")
    name: str = Field(description="Human-readable dimension name")
    status: DimensionStatus
    hypotheses_tested: int = 0
    hypotheses_confirmed: int = 0
    hypotheses_killed: int = 0
    findings: list[ReviewFinding] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class ReviewReport(BaseModel):
    """Top-level review output -- the governing structure for the agent."""

    verdict: Verdict
    statement: str = Field(
        description="One-paragraph governing statement (Pyramid Principle)"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    dimensions: list[DimensionResult] = Field(default_factory=list)
    gaps: list[str] = Field(
        default_factory=list,
        description="Areas not covered or requiring human review",
    )
    validation_log: list[str] = Field(
        default_factory=list,
        description="Phase-by-phase reasoning trace",
    )
    files_reviewed: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)
