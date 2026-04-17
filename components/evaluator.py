"""Outcome classification and continuation logic (framework-agnostic).

NO langgraph or langchain imports allowed.

parse_llm_response: inspects AIMessage for tool calls vs final answer.
classify_outcome: categorizes errors by type, returns ErrorRecord.
build_step_result: folds ErrorRecord + cost/latency into StepResult.
check_continuation: decides whether to continue the loop (respects backoff_until).
parse_response_structured: optional pydantic-ai typed parsing (graceful fallback).
"""

from __future__ import annotations

import time
from typing import Any

from components.schemas import ErrorRecord, StepResult
from services.base_config import AgentConfig


def parse_llm_response(message: Any) -> str:
    """Classify an LLM response as 'tool_call', 'final_answer', or 'budget_exceeded'."""
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        return "tool_call"
    return "final_answer"


def classify_outcome(
    response_content: str,
    error: Exception | None,
    *,
    model: str = "",
    step: int = 0,
) -> tuple[str, ErrorRecord | None]:
    """Classify a step outcome. Returns (outcome, ErrorRecord | None).

    Phase 2 change: instead of returning the error_type as a string, we return
    a full ErrorRecord so downstream consumers (router, governance, step result)
    can cite structured evidence. When no error occurred, the second tuple
    element is None.
    """
    if error is None:
        return "success", None

    status_code = getattr(error, "status_code", None)
    if status_code in (429, 503):
        error_type = "retryable"
    elif status_code in (400, 401, 403):
        error_type = "model_error"
    elif "tool" in str(error).lower():
        error_type = "tool_error"
    else:
        error_type = "terminal"

    record = ErrorRecord(
        step=step,
        error_type=error_type,
        error_code=status_code if isinstance(status_code, int) else None,
        message=str(error),
        model=model,
        timestamp=time.time(),
    )
    return "failure", record


def build_step_result(
    *,
    step_id: int,
    action: str,
    model_used: str,
    routing_reason: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: float,
    outcome: str,
    error_record: ErrorRecord | None,
    reasoning: str,
    tool_name: str | None = None,
    tool_input: dict[str, Any] | None = None,
    tool_output: str | None = None,
) -> StepResult:
    """Fold an ErrorRecord plus token/cost/latency into a StepResult."""
    return StepResult(
        step_id=step_id,
        action=action,
        model_used=model_used,
        routing_reason=routing_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output,
        outcome=outcome,
        error_type=error_record.error_type if error_record else None,
        reasoning=reasoning,
    )


def check_continuation(
    step_count: int,
    total_cost_usd: float,
    last_outcome: str,
    last_error_type: str | None,
    agent_config: AgentConfig,
    has_pending_tool_result: bool = False,
    *,
    backoff_until: float | None = None,
    now: float | None = None,
) -> str:
    """Decide whether to continue the ReAct loop. Returns 'continue' or 'done'.

    If ``backoff_until`` is in the future, the loop always continues — we do
    not trip the early-exit on a prior success because the retry schedule is
    already committed. Budget and step limits still win over backoff.
    """
    if step_count >= agent_config.max_steps:
        return "done"
    if total_cost_usd >= agent_config.max_cost_usd:
        return "done"
    if last_error_type == "terminal":
        return "done"

    current_time = now if now is not None else time.time()
    if backoff_until is not None and current_time < backoff_until:
        return "continue"

    if last_outcome == "success" and not has_pending_tool_result:
        return "done"
    return "continue"


def parse_response_structured(
    response_content: str,
    schema: Any,
) -> Any:
    """Optionally parse a response into a typed Pydantic model via pydantic-ai.

    Falls back to returning ``response_content`` unchanged when pydantic-ai is
    unavailable or parsing fails, so callers written for Phase 1 keep working.
    """
    try:
        from pydantic_ai import Agent  # type: ignore[import-not-found]
    except ImportError:
        return response_content

    try:
        agent = Agent(model=None, result_type=schema)
        return agent.run_sync(response_content).data  # type: ignore[attr-defined]
    except Exception:
        return response_content
