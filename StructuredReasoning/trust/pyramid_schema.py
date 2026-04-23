"""Structured output schema for the Pyramid ReACT agent.

Pure data only -- no I/O, no storage, no network, no logging.
Mirrors the ``analysis_output`` YAML schema in
``research/pyramid_react_system_prompt.md`` Section 5.

Lives in ``StructuredReasoning/trust/`` because the schema is consumed by
both ``StructuredReasoning/components/`` (validators, parser, confidence
scorer) and ``StructuredReasoning/services/`` (semantic judge, persistence).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Phase(str, Enum):
    """The four-phase reasoning loop from the system prompt."""

    DECOMPOSE = "decompose"
    HYPOTHESIZE = "hypothesize"
    ACT = "act"
    SYNTHESIZE = "synthesize"


class ProblemType(str, Enum):
    """Problem-shape classification from Phase 1."""

    DIAGNOSTIC = "diagnostic"
    DESIGN = "design"
    EVALUATION = "evaluation"
    PREDICTION = "prediction"


class OrderingType(str, Enum):
    """Logical ordering for branches at the same issue-tree level."""

    STRUCTURAL = "structural"
    CHRONOLOGICAL = "chronological"
    COMPARATIVE = "comparative"
    DEGREE = "degree"


class HypothesisStatus(str, Enum):
    """Resolution state of a branch's hypothesis after Phase 3."""

    CONFIRMED = "confirmed"
    KILLED = "killed"
    INCONCLUSIVE = "inconclusive"
    UNTESTED = "untested"


class ReasoningMode(str, Enum):
    """Reasoning mode for a key argument (top-level inductive, inner deductive)."""

    INDUCTIVE = "inductive"
    DEDUCTIVE = "deductive"


class SoWhatLevel(str, Enum):
    """Levels of the so-what chain that connects evidence to the governing thought."""

    FACT = "fact"
    IMPACT = "impact"
    IMPLICATION = "implication"
    CONNECTION = "connection"


class ValidationCheckName(str, Enum):
    """The eight self-validation checks defined in Section 4 of the system prompt."""

    COMPLETENESS = "completeness"
    NON_OVERLAP = "non_overlap"
    ITEM_PLACEMENT = "item_placement"
    SO_WHAT = "so_what"
    VERTICAL_LOGIC = "vertical_logic"
    REMOVE_ONE = "remove_one"
    NEVER_ONE = "never_one"
    MATHEMATICAL = "mathematical"


class ValidationResult(str, Enum):
    """Result of a single validation check."""

    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class WeaknessSeverity(str, Enum):
    """Severity of a known analytical weakness."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProblemDefinition(BaseModel):
    """Restated, scoped problem with measurable success criteria."""

    original_statement: str = Field(min_length=1)
    restated_question: str = Field(min_length=1)
    problem_type: ProblemType
    scope_boundaries: str = ""
    success_criteria: str = ""

    model_config = ConfigDict(extra="forbid")


class Branch(BaseModel):
    """A node in the MECE issue tree.

    ``sub_branches`` is a recursive list of further ``Branch`` instances.
    ``evidence_ids`` references ``Evidence.id`` values that support this branch.
    """

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    question: str = Field(min_length=1)
    hypothesis: str = ""
    hypothesis_status: HypothesisStatus = HypothesisStatus.UNTESTED
    evidence_ids: list[str] = Field(default_factory=list)
    sub_branches: list[Branch] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class IssueTree(BaseModel):
    """Phase 1 output: full MECE decomposition."""

    root_question: str = Field(min_length=1)
    ordering_type: OrderingType
    branches: list[Branch] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class GoverningThought(BaseModel):
    """The single-sentence apex of the pyramid.

    The system prompt requires this to be a complete, specific, actionable
    sentence that passes the elevator test -- not a topic label.
    """

    statement: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")


class DeductivePremise(BaseModel):
    """A single premise inside a deductive chain."""

    premise: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    conditionals: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class DeductiveChain(BaseModel):
    """Optional deductive sub-structure for a single key argument."""

    premises: list[DeductivePremise] = Field(min_length=1, max_length=4)
    conclusion: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class SoWhatChain(BaseModel):
    """A single step in the so-what chain (fact -> impact -> implication -> connection)."""

    level: SoWhatLevel
    statement: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class KeyArgument(BaseModel):
    """One of 3-5 inductive pillars supporting the governing thought."""

    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    dimension: str = Field(min_length=1)
    reasoning_mode: ReasoningMode = ReasoningMode.INDUCTIVE
    deductive_chain: DeductiveChain | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    so_what_chain: list[SoWhatChain] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _deductive_requires_chain(self) -> KeyArgument:
        if self.reasoning_mode is ReasoningMode.DEDUCTIVE and self.deductive_chain is None:
            raise ValueError(
                "reasoning_mode=deductive requires a deductive_chain"
            )
        return self


class Evidence(BaseModel):
    """A single fact gathered during Phase 3, tagged to one branch + one argument."""

    id: str = Field(min_length=1)
    fact: str = Field(min_length=1)
    source: str = Field(min_length=1)
    assigned_to: str = Field(min_length=1, description="KeyArgument.id")
    branch_id: str = Field(min_length=1, description="Branch.id")
    confidence: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")


class UntestedHypothesis(BaseModel):
    """A branch hypothesis that could not be tested with available tools."""

    branch_id: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    impact_on_confidence: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class MissingData(BaseModel):
    """Data that was needed for the analysis but unavailable."""

    description: str = Field(min_length=1)
    would_affect: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class KnownWeakness(BaseModel):
    """A known analytical limitation flagged by the agent."""

    description: str = Field(min_length=1)
    severity: WeaknessSeverity

    model_config = ConfigDict(extra="forbid")


class Gaps(BaseModel):
    """Catalog of analytical gaps -- the antidote to gap blindness (anti-pattern 6)."""

    untested_hypotheses: list[UntestedHypothesis] = Field(default_factory=list)
    missing_data: list[MissingData] = Field(default_factory=list)
    known_weaknesses: list[KnownWeakness] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class CrossBranchInteraction(BaseModel):
    """A finding in one branch that changes the interpretation in another."""

    branches: list[str] = Field(min_length=2)
    interaction: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class ValidationCheck(BaseModel):
    """One row of the validation log -- a single check's result."""

    check: ValidationCheckName
    result: ValidationResult
    details: str = ""

    model_config = ConfigDict(extra="forbid")


class PresentationNote(BaseModel):
    """A contextual observation about argument strength or stakeholder concerns."""

    note: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class Metadata(BaseModel):
    """Run-level metadata: tools used, iteration count, reasoning trace summary."""

    problem_scope: str = ""
    tools_used: list[str] = Field(default_factory=list)
    iteration_count: int = Field(ge=1, default=1)
    reasoning_trace_summary: str = ""
    communication_tone: str | None = None
    presentation_notes: list[PresentationNote] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class AnalysisOutput(BaseModel):
    """Top-level structured output of the Pyramid ReACT agent.

    Exactly the ``analysis_output`` shape from Section 5 of
    ``research/pyramid_react_system_prompt.md``.
    """

    problem_definition: ProblemDefinition
    issue_tree: IssueTree
    governing_thought: GoverningThought
    key_arguments: list[KeyArgument] = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)
    gaps: Gaps = Field(default_factory=Gaps)
    cross_branch_interactions: list[CrossBranchInteraction] = Field(default_factory=list)
    validation_log: list[ValidationCheck] = Field(default_factory=list)
    metadata: Metadata = Field(default_factory=Metadata)

    model_config = ConfigDict(extra="forbid")

    def to_dict(self) -> dict[str, Any]:
        """Convenience JSON-mode dump for persistence/rendering."""
        return self.model_dump(mode="json")


# Allow Branch.sub_branches forward reference resolution.
Branch.model_rebuild()
