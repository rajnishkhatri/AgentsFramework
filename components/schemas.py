"""Framework-agnostic Pydantic models for the ReAct agent.

NO langgraph or langchain imports allowed.

ErrorRecord, StepResult, EvalRecord, and TaskResult are consumed by
services (eval_capture, observability) and orchestration (state, nodes).
EvalRecord uses schema_version for forward compatibility.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


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
    rationale: str = ""
    graceful_failure: bool = False
    partial_fraction: float = 0.0
    failure_mode: str | None = None

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
        raise ValueError(f"failure_mode must be a string or null, got {type(value).__name__}")

    @property
    def unmet_conditions(self) -> list[str]:
        """Success conditions the judge marked as not met."""
        return [c.criterion for c in self.per_criterion if not c.met]
