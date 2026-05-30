"""Framework-agnostic Pydantic models for the ReAct agent.

NO langgraph or langchain imports allowed.

ErrorRecord, StepResult, EvalRecord, and TaskResult are consumed by
services (eval_capture, observability) and orchestration (state, nodes).
EvalRecord uses schema_version for forward compatibility.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
    """

    goal_met: bool
    criteria_met: float = 0.0
    per_criterion: list[CriterionVerdict] = Field(default_factory=list)
    rationale: str = ""

    @property
    def unmet_conditions(self) -> list[str]:
        """Success conditions the judge marked as not met."""
        return [c.criterion for c in self.per_criterion if not c.met]
