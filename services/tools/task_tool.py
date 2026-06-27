"""Delegation tool with budget gates and filesystem handoff.

This service-layer tool is framework-agnostic: it validates a delegation
request, enforces deterministic gates, persists handoff artifacts to the
in-state virtual filesystem, and returns a structured ToolExecutionResult.
"""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from services.tools.registry import ToolExecutionResult

ReasonCode = Literal[
    "DELEGATION_BUDGET_EXCEEDED",
    "DELEGATION_POLICY_DENY",
    "DELEGATION_APPROVAL_REQUIRED",
    "DELEGATION_THROTTLED",
    "DELEGATION_SUBAGENT_NOT_ALLOWED",
    "DELEGATION_DISPATCH_FAILED",
    "HANDOFF_NOT_FOUND",
    "HANDOFF_INVALID",
]


class TaskToolInput(BaseModel):
    """Delegation request envelope consumed by the ``task`` tool."""

    operation: Literal["delegate", "reconcile"] = "delegate"
    objective: str = Field(min_length=1, max_length=400)
    subagent_type: str = Field(min_length=1, max_length=80)
    constraints: list[str] = Field(default_factory=list)
    expected_output_schema: dict[str, Any] = Field(default_factory=dict)
    handoff_ref: str | None = None

    # Gate controls
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    policy_mode: Literal["allow", "deny", "require_approval", "throttle"] = "allow"

    # Internal-only fields (hidden from tool schema by registry).
    state: dict[str, Any] = Field(default_factory=dict, alias="_state")
    dispatch: Any = Field(default=None, alias="_delegate_dispatch", exclude=True)

    model_config = ConfigDict(populate_by_name=True)


def _build_trace_event(
    *,
    event_type: str,
    outcome: Literal["pass", "fail", "alert"],
    details: dict[str, Any],
    causation_id: str | None = None,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "outcome": outcome,
        "details": details,
        "causation_id": causation_id,
    }


def _gate_policy(validated: TaskToolInput) -> ReasonCode | None:
    if validated.policy_mode == "deny":
        return "DELEGATION_POLICY_DENY"
    if validated.policy_mode == "require_approval":
        return "DELEGATION_APPROVAL_REQUIRED"
    if validated.policy_mode == "throttle":
        return "DELEGATION_THROTTLED"
    return None


def _gate_budget(validated: TaskToolInput) -> ReasonCode | None:
    state = validated.state or {}
    total_cost = float(state.get("total_cost_usd", 0.0) or 0.0)
    global_budget = float(state.get("max_cost_usd", 0.0) or 0.0)
    delegation_budget = float(state.get("delegation_max_cost_usd", 0.0) or 0.0)

    effective_limit = delegation_budget if delegation_budget > 0 else global_budget
    if effective_limit <= 0:
        effective_limit = 0.0
    call_count = int(state.get("delegation_call_count", 0) or 0)
    max_calls = int(state.get("delegation_max_calls_per_task", 0) or 0)
    if max_calls > 0 and call_count >= max_calls:
        return "DELEGATION_THROTTLED"
    if effective_limit <= 0:
        return None
    if total_cost + validated.estimated_cost_usd > effective_limit:
        return "DELEGATION_BUDGET_EXCEEDED"
    return None


def _with_reason_error(code: ReasonCode, msg: str, trace_event: dict[str, Any]) -> ToolExecutionResult:
    payload = json.dumps({"ok": False, "reason_code": code, "message": msg})
    return ToolExecutionResult(
        output=f"Error: {payload}",
        ok=False,
        error=code,
        # Delegation/handoff gate denials are policy/ACL decisions, not a tool
        # that ran-and-failed nor malformed args — surface a distinct class so
        # they don't collapse into the generic tool_reported bucket (F1).
        error_class="gating",
        metadata={"trace_records": [trace_event]},
    )


def _gate_subagent_allowlist(validated: TaskToolInput) -> ReasonCode | None:
    state = validated.state or {}
    capabilities = state.get("agent_capabilities", []) or []
    capability_names = {str(item).strip() for item in capabilities if str(item).strip()}
    wildcard = "delegate.subagent.*"
    required = f"delegate.subagent.{validated.subagent_type}"
    if wildcard in capability_names or required in capability_names:
        return None
    return "DELEGATION_SUBAGENT_NOT_ALLOWED"


def execute_task_tool(args: dict[str, Any]) -> ToolExecutionResult:
    """Validate and execute delegation/handoff operations."""
    try:
        validated = TaskToolInput(**args)
    except Exception as exc:
        return ToolExecutionResult(
            output=f"Error: {exc}", ok=False, error=str(exc), error_class="validation"
        )

    state = validated.state or {}
    workflow_id = str(state.get("workflow_id", "wf"))
    step_count = int(state.get("step_count", 0) or 0)
    parent_correlation_id = f"{workflow_id}:step:{step_count}:{validated.subagent_type}"
    handoff_root = f".agent_handoff/{parent_correlation_id.replace(':', '_')}"

    if validated.operation == "reconcile":
        if not validated.handoff_ref:
            err = "reconcile requires handoff_ref"
            return ToolExecutionResult(output=f"Error: {err}", ok=False, error=err)
        files = state.get("files", {}) or {}
        raw = files.get(validated.handoff_ref)
        if raw is None:
            trace = _build_trace_event(
                event_type="delegation_reconcile_failed",
                outcome="fail",
                details={"reason_code": "HANDOFF_NOT_FOUND", "handoff_ref": validated.handoff_ref},
            )
            return _with_reason_error("HANDOFF_NOT_FOUND", "handoff artifact not found", trace)
        try:
            handoff_payload = json.loads(str(raw))
        except Exception:
            trace = _build_trace_event(
                event_type="delegation_reconcile_failed",
                outcome="fail",
                details={"reason_code": "HANDOFF_INVALID", "handoff_ref": validated.handoff_ref},
            )
            return _with_reason_error("HANDOFF_INVALID", "handoff artifact is not valid JSON", trace)

        handoff_parent = str(PurePosixPath(validated.handoff_ref).parent)
        reconcile_ref = f"{handoff_parent}/reconciled.json"
        reconciled = {
            "correlation_id": handoff_payload.get("correlation_id", parent_correlation_id),
            "status": handoff_payload.get("status", "unknown"),
            "output": handoff_payload.get("output", ""),
            "error": handoff_payload.get("error"),
        }
        trace = _build_trace_event(
            event_type="delegation_reconciled",
            outcome="pass",
            details={"handoff_ref": validated.handoff_ref, "reconcile_ref": reconcile_ref},
        )
        return ToolExecutionResult(
            output=f"Reconciled child output from {validated.handoff_ref}",
            ok=True,
            state_delta={"files": {reconcile_ref: json.dumps(reconciled, sort_keys=True)}},
            metadata={"trace_records": [trace]},
        )

    # operation == "delegate"
    policy_reason = _gate_policy(validated)
    if policy_reason is not None:
        trace = _build_trace_event(
            event_type="delegation_denied",
            outcome="fail",
            details={"reason_code": policy_reason, "policy_mode": validated.policy_mode},
        )
        return _with_reason_error(policy_reason, "delegation denied by policy gate", trace)

    allowlist_reason = _gate_subagent_allowlist(validated)
    if allowlist_reason is not None:
        trace = _build_trace_event(
            event_type="delegation_denied",
            outcome="fail",
            details={
                "reason_code": allowlist_reason,
                "subagent_type": validated.subagent_type,
            },
        )
        return _with_reason_error(
            allowlist_reason,
            f"delegation denied: subagent_type '{validated.subagent_type}' not allowed",
            trace,
        )

    budget_reason = _gate_budget(validated)
    if budget_reason is not None:
        trace = _build_trace_event(
            event_type="delegation_denied",
            outcome="fail",
            details={
                "reason_code": budget_reason,
                "estimated_cost_usd": validated.estimated_cost_usd,
            },
        )
        return _with_reason_error(budget_reason, "delegation denied by budget gate", trace)

    request_ref = f"{handoff_root}/request.json"
    result_ref = f"{handoff_root}/result.json"
    request_payload = {
        "correlation_id": parent_correlation_id,
        "workflow_id": workflow_id,
        "step_count": step_count,
        "objective": validated.objective,
        "subagent_type": validated.subagent_type,
        "constraints": validated.constraints,
        "expected_output_schema": validated.expected_output_schema,
    }

    if callable(validated.dispatch):
        try:
            dispatch_output = validated.dispatch(request_payload)
        except Exception as exc:
            trace = _build_trace_event(
                event_type="delegation_dispatch_failed",
                outcome="fail",
                details={"reason_code": "DELEGATION_DISPATCH_FAILED", "error": str(exc)},
            )
            return _with_reason_error("DELEGATION_DISPATCH_FAILED", str(exc), trace)
    else:
        dispatch_output = {
            "status": "completed",
            "output": "Delegation accepted (no external dispatcher configured).",
            "error": None,
            "child_correlation_id": f"{parent_correlation_id}:child:local",
        }

    result_payload = {
        "correlation_id": parent_correlation_id,
        "child_correlation_id": dispatch_output.get("child_correlation_id"),
        "status": dispatch_output.get("status", "completed"),
        "output": dispatch_output.get("output", ""),
        "error": dispatch_output.get("error"),
    }
    traces = [
        _build_trace_event(
            event_type="delegation_requested",
            outcome="pass",
            details={
                "correlation_id": parent_correlation_id,
                "subagent_type": validated.subagent_type,
                "request_ref": request_ref,
            },
        ),
        _build_trace_event(
            event_type="delegation_completed",
            outcome="pass" if not result_payload.get("error") else "alert",
            details={
                "correlation_id": parent_correlation_id,
                "child_correlation_id": result_payload.get("child_correlation_id"),
                "result_ref": result_ref,
                "status": result_payload.get("status"),
            },
        ),
    ]
    return ToolExecutionResult(
        output=f"Delegated task via {validated.subagent_type}. Handoff: {result_ref}",
        ok=True,
        state_delta={
            "files": {
                request_ref: json.dumps(request_payload, sort_keys=True),
                result_ref: json.dumps(result_payload, sort_keys=True),
            }
        },
        metadata={"trace_records": traces},
    )


def build_task_tool_executor(
    dispatcher: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], ToolExecutionResult]:
    """Bind a dispatcher callback into the task tool executor."""

    def _executor(args: dict[str, Any]) -> ToolExecutionResult:
        if dispatcher is None:
            return execute_task_tool(args)
        return execute_task_tool({**args, "_delegate_dispatch": dispatcher})

    return _executor
