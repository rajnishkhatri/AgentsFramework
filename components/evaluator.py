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


def _normalize_for_matching(text: str) -> str:
    """Lowercase and strip punctuation for keyword matching."""
    import re
    return re.sub(r"[^\w\s]", " ", text.lower())


def _keyword_overlap(text: str, reference: str) -> float:
    """Fraction of meaningful reference words found in text (>3 chars)."""
    text_words = set(_normalize_for_matching(text).split())
    ref_words = {w for w in _normalize_for_matching(reference).split() if len(w) > 3}
    if not ref_words:
        return 1.0
    return len(text_words & ref_words) / len(ref_words)


def parse_llm_response(message: Any) -> str:
    """Classify an LLM response as 'tool_call', 'final_answer', or 'budget_exceeded'."""
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        return "tool_call"
    return "final_answer"


def _echo_normalized_output(entry: dict[str, Any]) -> str:
    """Return ``tool_output`` with the call's own input values removed.

    Some tools/providers echo their input back into the output (e.g. the
    search stub renders ``"Search result for: <query>"``). Two such calls
    produce *different* raw outputs even when no real progress was made.
    Stripping the input echo lets :func:`count_trailing_repeats` recognize
    them as the same non-advancing work, while genuinely different results
    (real search hits, distinct file contents) remain distinct.
    """
    out = str(entry.get("tool_output", "") or "")
    for value in (entry.get("tool_input", {}) or {}).values():
        token = str(value)
        if len(token) >= 3:
            out = out.replace(token, "")
    return out


def count_trailing_repeats(tool_results: list[dict[str, Any]]) -> int:
    """Count consecutive trailing tool_results that repeat the same work.

    Returns the length of the longest trailing run where entries share the
    same normalized ``(tool_name, tool_input)`` key OR the same non-empty
    ``tool_output`` (after stripping input-echo) — i.e. how many times in a
    row the agent did the same thing. This is a domain heuristic (it informs
    the no-progress policy in :func:`check_continuation`) so it lives in
    components, not orchestration.
    """
    if len(tool_results) < 2:
        return 0

    last = tool_results[-1]
    last_key = (last.get("tool_name"), str(sorted(last.get("tool_input", {}).items())))
    last_output = last.get("tool_output", "")
    last_sig = _echo_normalized_output(last)

    count = 1
    for entry in reversed(tool_results[:-1]):
        entry_key = (entry.get("tool_name"), str(sorted(entry.get("tool_input", {}).items())))
        entry_output = entry.get("tool_output", "")
        # Output match ignores input-echo: two calls that return the same
        # template differing only by an echoed query (e.g. the search stub's
        # "Search result for: <query>") count as no-progress, while genuinely
        # different results stay distinct.
        same_output = bool(last_output) and (
            entry_output == last_output
            or _echo_normalized_output(entry) == last_sig
        )
        if entry_key == last_key or same_output:
            count += 1
        else:
            break
    return count


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
    elif str(error).startswith("Error:"):
        # Tool validators (shell allowlist, file_io path sandbox) return
        # "Error: …" strings — recoverable, not loop-terminating (B4).
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
    repeated_tool_calls: int = 0,
    no_progress_directive_sent: bool = False,
) -> str:
    """Decide whether to continue the ReAct loop. Returns 'continue' or 'done'.

    If ``backoff_until`` is in the future, the loop always continues — we do
    not trip the early-exit on a prior success because the retry schedule is
    already committed. Budget and step limits still win over backoff.

    Graduated no-progress backstop (warn -> hard-stop):
      - ``no_progress_hard_limit``: absolute failsafe, terminates regardless.
      - At ``no_progress_repeat_threshold`` with ``no_progress_directive_sent``:
        the model ignored the wrap-up directive, terminate.
      - At ``no_progress_repeat_threshold`` without the directive: allow one
        more synthesis pass (caller will inject the directive).
    """
    if step_count >= agent_config.max_steps:
        return "done"
    if total_cost_usd >= agent_config.max_cost_usd:
        return "done"
    if last_error_type == "terminal":
        return "done"

    if repeated_tool_calls >= agent_config.no_progress_hard_limit:
        return "done"
    if repeated_tool_calls >= agent_config.no_progress_repeat_threshold and no_progress_directive_sent:
        return "done"

    current_time = now if now is not None else time.time()
    if backoff_until is not None and current_time < backoff_until:
        return "continue"

    if last_outcome == "success" and not has_pending_tool_result:
        return "done"
    return "continue"


def evaluate_task_outcome(
    *,
    final_answer: str,
    success_conditions: list[str],
    plan_steps: list[dict[str, Any]],
    termination_reason: str,
    tool_results: list[dict[str, Any]] | None = None,
) -> Any:
    """Evaluate task completion (process-level, not content-level).

    Deterministic, CI-safe heuristic. Evaluates whether the agent completed
    its process successfully, NOT whether the answer is semantically correct
    (that requires L3 LLM-as-judge evals).

    Signals:
      - Clean termination: did the agent finish normally?
      - Substantive answer: did it produce a non-trivial response?
      - Branch coverage: informational metric for telemetry (not gating).

    Outcome mapping (process signals only — NOT semantic goal satisfaction):
      - "success": clean termination with a substantive answer.
      - "partial": unclean termination (budget/step/hard_limit/no_progress) but has an answer.
      - "failed": empty answer, or unclean termination with no useful output.

    ``no_progress`` is treated as *unclean*: a loop-exhausted run that synthesised
    a final answer via the wrap-up directive is downgraded ``success -> partial``
    (the corrupt-success fix). Goal progress is reported separately via
    ``goal_met`` and never gates ``outcome``.
    """
    from components.schemas import TaskOutcome

    is_clean = termination_reason in ("success", "final_answer", "")
    termination_score = 1.0 if is_clean else 0.0

    answer_text = (final_answer or "").strip()
    trajectory_text = ""
    if tool_results:
        trajectory_text = " ".join(
            str(r.get("tool_output", "")) for r in tool_results
        )
    combined_text = f"{answer_text} {trajectory_text}"

    has_substance = len(answer_text) > 10 and not answer_text.startswith("Error:")
    is_error_content = answer_text.startswith("Error:")
    substance_score = 1.0 if has_substance else (0.3 if answer_text and not is_error_content else 0.0)

    if plan_steps:
        branch_scores = []
        for step in plan_steps:
            goal = step.get("goal", "")
            if goal:
                overlap = _keyword_overlap(combined_text, goal)
                branch_scores.append(overlap)
        branch_coverage = sum(branch_scores) / len(branch_scores) if branch_scores else 1.0
    else:
        branch_coverage = 1.0

    unmet: list[str] = []
    criteria_met = 1.0
    goal_met: bool | None = None
    if success_conditions:
        condition_scores = []
        for condition in success_conditions:
            overlap = _keyword_overlap(combined_text, condition)
            condition_scores.append(overlap)
            if overlap < 0.3:
                unmet.append(condition)
        criteria_met = sum(condition_scores) / len(condition_scores)
        # Non-gating goal-progress signal. Deliberately decoupled from
        # ``outcome``: keyword overlap is too fragile to gate the process
        # verdict (TAP-3 determinism theater). ``None`` when no conditions.
        goal_met = criteria_met >= 0.5

    composite_score = (
        0.20 * termination_score
        + 0.50 * substance_score
        + 0.30 * branch_coverage
    )

    if is_clean and has_substance:
        outcome = "success"
    elif is_clean and answer_text and not is_error_content:
        outcome = "success"
    elif not is_clean and has_substance:
        outcome = "partial"
    elif not is_clean and answer_text and not is_error_content:
        outcome = "partial"
    else:
        outcome = "failed"

    return TaskOutcome(
        outcome=outcome,
        termination_clean=is_clean,
        criteria_met=round(criteria_met, 3),
        branch_coverage=round(branch_coverage, 3),
        unmet_conditions=unmet,
        score=round(composite_score, 3),
        termination_reason=termination_reason,
        goal_met=goal_met,
    )


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
