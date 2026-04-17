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
