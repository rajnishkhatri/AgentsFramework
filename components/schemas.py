"""Framework-agnostic Pydantic models for the ReAct agent.

NO langgraph or langchain imports allowed.

ErrorRecord, StepResult, EvalRecord, and TaskResult are consumed by
services (eval_capture, observability) and orchestration (state, nodes).
EvalRecord uses schema_version for forward compatibility.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ErrorRecord(BaseModel):
    step: int
    error_type: str
    error_code: int | None = None
    message: str
    model: str
    timestamp: float


class StepResult(BaseModel):
    step_id: int
    action: str
    model_used: str
    routing_reason: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_output: str | None = None
    outcome: str
    error_type: str | None = None
    reasoning: str


class EvalRecord(BaseModel):
    schema_version: int = 1
    timestamp: datetime
    task_id: str
    user_id: str
    step: int
    target: str
    model: str | None = None
    ai_input: dict[str, Any]
    ai_response: dict[str, Any] | str
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    latency_ms: float | None = None
    error_type: str | None = None


class TaskResult(BaseModel):
    task_id: str
    task_input: str
    steps: list[StepResult]
    final_answer: str | None = None
    total_cost_usd: float
    total_latency_ms: float
    total_steps: int
    status: str


class TaskOutcome(BaseModel):
    """Structured task-completion evaluation result.

    Follows the FutureAGI three-signal approach:
      - termination_clean: did the agent finish normally (not budget/step exhaustion)?
      - criteria_met: fraction of success_conditions found in the output/trajectory.
      - branch_coverage: fraction of planned steps addressed in the final answer.
      - outcome: "success" | "partial" | "failed" derived from PROCESS signals only.
      - unmet_conditions: which success_conditions were not satisfied.
      - termination_reason: why the loop ended (success/max_steps/budget_exceeded/no_progress).
      - goal_met: non-gating goal-progress signal derived from criteria_met. ``None``
        when no success_conditions were declared. NEVER changes ``outcome`` — semantic
        goal satisfaction belongs in a future L3 LLM-as-judge.
    """

    outcome: str
    termination_clean: bool
    criteria_met: float
    branch_coverage: float
    unmet_conditions: list[str] = Field(default_factory=list)
    score: float = 0.0
    termination_reason: str = ""
    goal_met: bool | None = None


# Stage 5 gold-set ``failure_mode`` enum (the Axis-A member codes).
# ---------------------------------------------------------------------------
# The closed vocabulary a Stage-5 gold-set / calibration label may carry on the
# ``failure_mode`` axis. These are the **Axis-A agent-behavior member codes**
# from the Stage-3 failure taxonomy (``goaljudge_phase3_axial_coding.md`` §3),
# kept in sync with the executable registry's ``target_code`` values
# (``tests/fixtures/goaljudge/case_registry.py``). ``tool-stub-limitation`` is
# intentionally absent (retired to Axis-B B5 — see the A3 note in §3).
#
# Stage 4 v1 only *populates* this axis for the A2 cluster (spec §9:
# ``fabricated-progress`` / ``partial-counted-as-full`` / ``subtask-dropped``);
# the rest are reserved for the A1/A3/A4/A5 rollout so the gold-set schema is
# stable across that expansion. ``failure_mode`` is **telemetry-only**, exactly
# like ``partial_fraction`` — it MUST NOT be wired into the downgrade gate.
GOAL_FAILURE_MODES: frozenset[str] = frozenset(
    {
        # A1 · semantic / synthesis
        "missing-requested-information",
        "incomplete-synthesis",
        "fluent-evasion",
        "criteria-mismatch",
        # A2 · decomposition / corrupt-success (the Stage 4 v1 cluster)
        "subtask-dropped",
        "partial-counted-as-full",
        "fabricated-progress",
        # A3 · error & exception handling
        "raw-error-propagation",
        "tool-error-misread",
        "non-existent-file-error",
        # A4 · feasibility & gracefulness
        "graceful-failure-honest",
        "impossible-task-reported",
        "impossible-task-unhandled",
        "premature-impossible",
        # A5 · process quality
        "right-answer-wrong-process",
        "goal-met-but-unsafe-wasteful",
    }
)


class CriterionVerdict(BaseModel):
    """Per-criterion judgment from the task-adaptive LLM-as-judge (I2).

    ``criterion`` is the success condition (verbatim or paraphrased from the
    plan); ``met`` is the judge's boolean call; ``evidence`` cites the span of
    the final answer / trajectory that justifies the call.
    """

    criterion: str
    met: bool
    evidence: str = ""


class GoalVerdict(BaseModel):
    """Structured verdict from the goal judge (I2 LLM-as-judge).

    Reference-free rubric over the final answer + trajectory evidence. Replaces
    the keyword-overlap ``goal_met``/``criteria_met`` heuristic. It overlays onto
    ``TaskOutcome`` (goal_met / criteria_met / unmet_conditions) but NEVER gates
    ``outcome`` — the deterministic process floor owns that signal.

      - goal_met: did the answer actually satisfy the task's goal?
      - criteria_met: fraction (0..1) of declared success conditions satisfied.
      - per_criterion: per-condition breakdown with evidence.
      - criteria_met_derived: parser-set repair marker — ``criteria_met`` was
        derived from the ``per_criterion`` met-flags because the model omitted
        the value or contradicted its own breakdown. TELEMETRY-ONLY, like
        ``partial_fraction`` — calibration stratifies on it; it MUST NOT be
        wired into gating.
      - rationale: short chain-of-thought summary (audit trail).
      - graceful_failure: the agent correctly reported an impossible task
        (behaved correctly, goal not met). Pure metadata — distinguishes a
        well-behaved impossibility report from a hallucinated completion.
      - partial_fraction: completion fraction (0..1) for a partially solved
        task. TELEMETRY-ONLY: the orchestration downgrade gate reads ONLY
        ``goal_met``; ``partial_fraction`` MUST NOT be wired into gating.
      - failure_mode: optional Axis-A taxonomy code (Stage 5 gold-set axis).
        One of ``GOAL_FAILURE_MODES`` or ``None`` when unclassified / a pass.
        TELEMETRY-ONLY, like ``partial_fraction`` — it MUST NOT be wired into
        gating. Stage 4 v1 populates it only for the A2 cluster (spec §9); it
        defaults to ``None`` so a v1 verdict (which omits the key) is unchanged.
    """

    goal_met: bool
    criteria_met: float = 0.0
    per_criterion: list[CriterionVerdict] = Field(default_factory=list)
    criteria_met_derived: bool = False
    rationale: str = ""
    graceful_failure: bool = False
    partial_fraction: float = 0.0
    failure_mode: str | None = None
    verifier_source: str | None = None
    """Provenance of ``goal_met`` when a deterministic verifier owned the verdict
    (e.g. ``"deterministic"`` for a topological-sort correctness check). ``None``
    means the LLM rubric produced the verdict. TELEMETRY-ONLY, like
    ``criteria_met_derived`` — calibration stratifies on it; it MUST NOT be wired
    into gating. Defaults to ``None`` so a verdict that omits the key is
    unchanged (v1 / LLM-path back-compat)."""

    @field_validator("failure_mode", mode="before")
    @classmethod
    def _normalize_failure_mode(cls, value: object) -> str | None:
        """Coerce an absent / blank ``failure_mode`` to ``None``; reject unknown codes.

        Mirrors the permissive spirit of the ``partial_fraction`` handling: a
        missing or empty value is the no-op default (``None``), not an error.
        A *present, non-empty* value, however, must be a known Axis-A member
        code — an unrecognised string is a labelling bug worth surfacing, not
        silently stored telemetry.
        """
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped or stripped.lower() in {"none", "null"}:
                return None
            if stripped not in GOAL_FAILURE_MODES:
                raise ValueError(
                    f"unknown failure_mode {stripped!r}; expected one of "
                    f"{sorted(GOAL_FAILURE_MODES)} or null"
                )
            return stripped
        raise ValueError(
            f"failure_mode must be a string or null, got {type(value).__name__}"
        )

    @property
    def unmet_conditions(self) -> list[str]:
        """Success conditions the judge marked as not met."""
        return [c.criterion for c in self.per_criterion if not c.met]


class GraderVerdict(BaseModel):
    """Grades the COACH'S generated content (FR-14, Subject-Coach design §7.1).

    Reference-free rubric over a hint / explanation / mini-question the coach
    produced. Sibling of ``GoalVerdict`` and bound by the same TELEMETRY-ONLY
    discipline: recorded via eval_capture (``target="coach_judges"``), never
    gating until certified (ADR-0008).

    Each 0..1 float axis pairs with a REQUIRED binary ``*_pass`` companion
    (design gap G8): the judge asserts the binary directly in the rubric
    prompt — it is never derived post-hoc from the float. Only the binaries
    enter κ calibration and the §12.6 gates; the floats are trend telemetry.
    All axis fields are required — a judge that cannot decide must yield no
    verdict at all (AP-6), never a defaulted one.
    """

    faithfulness: float = Field(ge=0.0, le=1.0)
    correctness: float = Field(ge=0.0, le=1.0)
    justification: float = Field(ge=0.0, le=1.0)
    actionability: float = Field(ge=0.0, le=1.0)
    faithfulness_pass: bool
    correctness_pass: bool
    justification_pass: bool
    actionability_pass: bool
    rationale: str = ""


class PedagogyVerdict(BaseModel):
    """Grades a coaching TURN as teaching (FR-15/16, Subject-Coach design §7.1).

    Same TELEMETRY-ONLY + binary-companion contract as ``GraderVerdict``.
    ``answer_leakage`` is the FIRST-CLASS flag (FR-16): it is REQUIRED — a
    verdict without it is a ``ValidationError``, never a fail-open ``False`` —
    and it is recorded distinctly, never averaged into a quality score (the
    schema deliberately offers no aggregate field to average into). It stays
    telemetry-only until the §7.4 floor (TNR ≥ 0.95, TPR ≥ 0.90, κ ≥ 0.75)
    certifies it, exactly the ``GoalVerdict.failure_mode`` precedent.
    """

    mistake_identification: float = Field(ge=0.0, le=1.0)
    mistake_location: float = Field(ge=0.0, le=1.0)
    actionability: float = Field(ge=0.0, le=1.0)
    coherence: float = Field(ge=0.0, le=1.0)
    productive_struggle: float = Field(ge=0.0, le=1.0)
    illusion_of_competence: float = Field(ge=0.0, le=1.0)
    mistake_identification_pass: bool
    mistake_location_pass: bool
    actionability_pass: bool
    coherence_pass: bool
    productive_struggle_pass: bool
    illusion_of_competence_pass: bool
    answer_leakage: bool
    rationale: str = ""


# Answer-grading backstop criterion. This checks the FINAL ANSWER ("is it
# internally consistent and responsive"), so it is applied at JUDGE-TIME
# (components.goal_judge / components.evaluator) — NOT baked into the plan-time
# TaskUnderstanding/plan_builder checklist, which is built before any answer
# exists. plan_builder still uses it as the empty-list backstop so a degenerate
# (no-branch) task can never yield an empty checklist. Single source of truth:
# task_understanding, plan_builder, goal_judge, evaluator all import THIS.
GENERIC_TAIL_CONDITION = (
    "The final answer is internally consistent and directly responds to the request."
)


class TaskUnderstanding(BaseModel):
    """Restated task intent + task-specific success checklist (plan-time D1).

    Generated once at step 0 by ``components.task_understanding`` (fast-tier
    LLM), or built from the deterministic plan_builder floor when generation
    fails. Consumed at the terminal evaluate by the keyword evaluator, the
    GoalJudge, and the eval telemetry. ``source`` is the provenance tier:
    deterministic < generated < user_edited (a user edit via the soft-gate
    card is the highest authority and skips lexical grounding).
    """

    restated_intent: str
    success_conditions: list[str] = Field(min_length=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: Literal["deterministic", "generated", "user_edited"] = "deterministic"
    model: str = ""


# The three human memory types the Phase-2 extractor classifies (research §1):
# semantic = stable facts about the user; episodic = how a past task went
# (observation/action/result); procedural = a rule/strategy that worked.
MemoryType = Literal["semantic", "episodic", "procedural"]


class TypedMemory(BaseModel):
    """One memory item proposed by the Phase-2 background extractor.

    Framework-agnostic output of ``components.memory_extractor`` (L3). The
    *schema is the classifier* (research §3): handing the LLM these typed
    constraints is how it decides which of the three human memory types an
    item is, and ``extra="forbid"`` (V6) rejects an item that invents fields
    — the first guard against a malformed/hallucinated proposal reaching the
    store. ``content`` is the distilled fact (NOT raw turns); ``key`` is the
    stable store key (``"profile"`` for the latest-state semantic record, a
    ``task_id``-derived key for an episodic item); ``salience`` is the
    extractor's own worth-storing estimate, surfaced to the carrier (never
    content) and used by the eval gate's precision metric.

    Phase 2 is ADD-only (research §3): no live UPDATE/DELETE — a periodic
    consolidation pass is the deferred conflict-resolution path.
    """

    model_config = ConfigDict(extra="forbid")

    type: MemoryType
    content: str = Field(min_length=1)
    key: str = Field(min_length=1)
    salience: float = Field(ge=0.0, le=1.0)
