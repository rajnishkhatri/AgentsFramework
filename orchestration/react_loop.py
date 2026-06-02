"""StateGraph definition: nodes, edges, compilation (TOPOLOGY ONLY).

Every node function is a thin wrapper that delegates to
framework-agnostic logic in components/ and services/.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from components.evaluator import (
    build_step_result,
    check_continuation,
    classify_outcome,
    count_trailing_repeats as _count_trailing_repeats,
    evaluate_task_outcome,
    parse_llm_response,
)
from components.goal_judge import GoalJudge
from components.plan_builder import build_planning_instructions
from components.plan_builder import build_plan_artifact
from components.plan_builder import validate_plan_mece
from components.schemas import ErrorRecord
from components.router import select_model
from components.router import select_planning_depth
from components.routing_config import RoutingConfig
from components.synthesis_validator import validate_synthesis
from orchestration.state import AgentState
from services.base_config import AgentConfig, ModelProfile, default_fast_profile
from services.governance.agent_facts_registry import AgentFactsRegistry
from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent
from services.governance.guardrail_validator import (
    FailAction,
    GuardRailValidator,
    api_key_rules,
    pii_rules,
)
from services.governance.injection_classifier import InjectionClassifier
from services.governance.phase_logger import Decision, PhaseLogger, WorkflowPhase
from services.guardrails import InputGuardrail, output_guardrail_scan
from services.llm_config import LLMService
from services.observability import FrameworkTelemetry, InstrumentedCheckpointer
from services.prompt_service import PromptService
from services.summarizer import (
    build_compaction_summary,
    should_compact_trajectory,
)
from services.tools.registry import ToolExecutionResult, ToolRegistry

logger = logging.getLogger("orchestration.react_loop")


def _ensure_checkpoint_saver_instance(checkpointer: Any) -> None:
    """Reject a bare ``from_conn_string`` context manager (common footgun).

    ``AsyncSqliteSaver.from_conn_string`` / ``SqliteSaver.from_conn_string`` are
    context managers. LangGraph expects the *entered* saver (with
    ``get_next_version``, etc.). Passing the manager yields::

        AttributeError: '_AsyncGeneratorContextManager' object has no attribute 'get_next_version'
    """
    getter = getattr(checkpointer, "get_next_version", None)
    if not callable(getter):
        raise TypeError(
            "checkpointer must be the saver instance from "
            "`async with AsyncSqliteSaver.from_conn_string(...) as saver` or "
            "`with SqliteSaver.from_conn_string(...) as saver`, not the "
            "unentered `from_conn_string(...)` context manager."
        )


def _compute_tool_cache_key(tool_name: str, tool_args: dict[str, Any]) -> str:
    """Deterministic cache key from tool_name + sorted-JSON of args."""
    digest = hashlib.md5(json.dumps(tool_args, sort_keys=True).encode()).hexdigest()
    return f"{tool_name}:{digest}"


def _apply_tool_output_thresholds(
    *,
    tool_name: str,
    output: str,
    offload_key: str,
    files: dict[str, str],
    agent_config: AgentConfig,
) -> tuple[str, str, bool, str | None]:
    """Apply explicit output offload/clearing thresholds.

    Returns:
      - ``message_output``: compact output to put in ToolMessage
      - ``recorded_output``: output to store in ``tool_results``
      - ``offloaded``: whether full output was offloaded to virtual files
      - ``offload_ref``: file reference when offloaded
    """
    threshold = max(1, int(agent_config.tool_output_offload_threshold_chars))
    preview_len = max(1, int(agent_config.tool_output_preview_chars))

    if len(output) <= threshold:
        return output, output, False, None

    ref_hash = hashlib.md5(f"{tool_name}:{offload_key}".encode()).hexdigest()[:12]
    offload_ref = f".agent_offload/{tool_name}_{ref_hash}.txt"
    files[offload_ref] = output

    preview = output[:preview_len]
    compact = (
        f"[offloaded:{offload_ref}] "
        f"tool output was {len(output)} chars and exceeded threshold {threshold}. "
        f"Preview:\n{preview}"
    )
    return compact, compact, True, offload_ref


def _execute_tools_impl(
    state: dict[str, Any],
    *,
    tool_registry: ToolRegistry,
    black_box: BlackBoxRecorder,
    agent_config: AgentConfig,
    trace_service: Any | None = None,
) -> dict[str, Any]:
    """Pure-ish executor for tool calls with cache-aware dispatch.

    Contract: reads ``state['tool_cache']``, returns a dict with ``messages``
    (ToolMessage list), ``tool_cache`` (updated), and ``current_workflow_phase``.
    Cache hits skip registry dispatch and emit TOOL_CALLED with cached=True.
    Tool results may include optional ``state_delta`` updates for ``files``,
    ``todos``, and ``plan_ref``.
    """
    from langchain_core.messages import ToolMessage

    workflow_id = state.get("workflow_id", "")
    messages = state.get("messages", [])
    if not messages:
        return {}

    last_msg = messages[-1]
    tool_calls = getattr(last_msg, "tool_calls", [])
    if not tool_calls:
        return {}

    updated_cache: dict[str, Any] = dict(state.get("tool_cache", {}) or {})
    results: list[ToolMessage] = []
    tool_results: list[dict[str, Any]] = []
    updated_files: dict[str, str] = dict(state.get("files", {}) or {})
    updated_todos = state.get("todos", [])
    updated_plan_ref = state.get("plan_ref", "")
    reasoning_trace_delta: list[str] = []

    delegation_call_count = sum(
        1 for result in state.get("tool_results", []) if result.get("tool_name") == "task"
    )

    for tc in tool_calls:
        tool_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
        tool_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
        tool_id = tc.get("id", str(uuid.uuid4())) if isinstance(tc, dict) else getattr(tc, "id", str(uuid.uuid4()))

        cache_key = _compute_tool_cache_key(tool_name, tool_args)
        cacheable = tool_registry.has(tool_name) and tool_registry.is_cacheable(tool_name)
        tool_args_with_state = {
            **tool_args,
            "_state": {
                "files": updated_files,
                "todos": updated_todos,
                "plan_ref": updated_plan_ref,
                "task_id": state.get("task_id", ""),
                "user_id": state.get("user_id", "anonymous"),
                "workflow_id": workflow_id,
                "step_count": state.get("step_count", 0),
                "total_cost_usd": state.get("total_cost_usd", 0.0),
                "max_cost_usd": agent_config.max_cost_usd,
                "delegation_max_cost_usd": agent_config.delegation_max_cost_usd,
                "delegation_call_count": delegation_call_count,
                "delegation_max_calls_per_task": agent_config.delegation_max_calls_per_task,
                "agent_capabilities": state.get("agent_capabilities", []),
            },
        }

        if cacheable and cache_key in updated_cache:
            execution_result = ToolExecutionResult(
                output=updated_cache[cache_key],
                ok=True,
                metadata={"cached": True},
            )
            message_output, recorded_output, offloaded, offload_ref = _apply_tool_output_thresholds(
                tool_name=tool_name,
                output=execution_result.output,
                offload_key=cache_key,
                files=updated_files,
                agent_config=agent_config,
            )
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.TOOL_CALLED,
                timestamp=datetime.now(UTC),
                step=state.get("step_count", 0),
                details={"tool": tool_name, "args": tool_args, "cached": True},
            ))
            results.append(ToolMessage(content=message_output, tool_call_id=tool_id))
            tool_results.append({
                "record_id": f"{state.get('step_count', 0)}:{tool_id}",
                "step_id": state.get("step_count", 0),
                "tool_name": tool_name,
                "tool_input": tool_args,
                "tool_output": recorded_output,
                "ok": execution_result.ok,
                "error": execution_result.error,
                "cached": True,
                "offloaded": offloaded,
                "offload_ref": offload_ref,
            })
            continue

        try:
            execution_result = tool_registry.execute_with_result(tool_name, tool_args_with_state)
        except KeyError:
            execution_result = ToolExecutionResult(
                output=f"Error: Unknown tool '{tool_name}'",
                ok=False,
                error=f"Unknown tool '{tool_name}'",
            )
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.ERROR_OCCURRED,
                timestamp=datetime.now(UTC),
                step=state.get("step_count", 0),
                details={
                    "source": "tool_execution",
                    "tool": tool_name,
                    "error": f"Unknown tool '{tool_name}'",
                },
            ))
        except Exception as exc:
            execution_result = ToolExecutionResult(
                output=f"Error: Tool '{tool_name}' failed: {exc}",
                ok=False,
                error=str(exc),
            )
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.ERROR_OCCURRED,
                timestamp=datetime.now(UTC),
                step=state.get("step_count", 0),
                details={
                    "source": "tool_execution",
                    "tool": tool_name,
                    "error": str(exc),
                },
            ))

        black_box.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.TOOL_CALLED,
            timestamp=datetime.now(UTC),
            step=state.get("step_count", 0),
            details={"tool": tool_name, "args": tool_args, "cached": False},
        ))

        if not execution_result.ok:
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.ERROR_OCCURRED,
                timestamp=datetime.now(UTC),
                step=state.get("step_count", 0),
                details={
                    "source": "tool_execution",
                    "tool": tool_name,
                    "error": execution_result.error or "tool returned failure",
                },
            ))

        if cacheable:
            updated_cache[cache_key] = execution_result.output

        state_delta = execution_result.state_delta or {}
        if "files" in state_delta and isinstance(state_delta["files"], dict):
            updated_files.update(state_delta["files"])
        if "todos" in state_delta and isinstance(state_delta["todos"], list):
            updated_todos = state_delta["todos"]
        if "plan_ref" in state_delta and isinstance(state_delta["plan_ref"], str):
            updated_plan_ref = state_delta["plan_ref"]
        if "reasoning_trace" in state_delta and isinstance(state_delta["reasoning_trace"], list):
            reasoning_trace_delta.extend(str(item) for item in state_delta["reasoning_trace"])
        if trace_service is not None:
            trace_records = (execution_result.metadata or {}).get("trace_records", [])
            if trace_records:
                from trust.models import TrustTraceRecord

                configurable_agent_id = str(state.get("registered_agent_id", "") or "")
                for trace_record in trace_records:
                    if not isinstance(trace_record, dict):
                        continue
                    try:
                        trace_service.emit(
                            TrustTraceRecord(
                                event_id=str(uuid.uuid4()),
                                timestamp=datetime.now(UTC),
                                trace_id=workflow_id,
                                agent_id=configurable_agent_id or "unknown-agent",
                                source_agent_id=configurable_agent_id or None,
                                layer="L4",
                                event_type=str(trace_record.get("event_type", "delegation_event")),
                                details=dict(trace_record.get("details", {})),
                                causation_id=trace_record.get("causation_id"),
                                outcome=trace_record.get("outcome"),
                            )
                        )
                    except Exception:
                        logger.exception("failed to emit delegation trace event")

        message_output, recorded_output, offloaded, offload_ref = _apply_tool_output_thresholds(
            tool_name=tool_name,
            output=execution_result.output,
            offload_key=cache_key,
            files=updated_files,
            agent_config=agent_config,
        )

        results.append(ToolMessage(content=message_output, tool_call_id=tool_id))
        tool_results.append({
            "record_id": f"{state.get('step_count', 0)}:{tool_id}",
            "step_id": state.get("step_count", 0),
            "tool_name": tool_name,
            "tool_input": tool_args,
            "tool_output": recorded_output,
            "ok": execution_result.ok,
            "error": execution_result.error,
            "cached": False,
            "offloaded": offloaded,
            "offload_ref": offload_ref,
        })

    history_limit = max(1, int(agent_config.tool_result_history_limit))
    if len(tool_results) > history_limit:
        tool_results = tool_results[-history_limit:]

    response: dict[str, Any] = {
        "messages": results,
        "tool_cache": updated_cache,
        "tool_results": tool_results,
        "current_workflow_phase": WorkflowPhase.TOOL_EXECUTION.value,
    }
    if updated_files:
        response["files"] = updated_files
    if updated_todos:
        response["todos"] = updated_todos
    if updated_plan_ref:
        response["plan_ref"] = updated_plan_ref
    if reasoning_trace_delta:
        response["reasoning_trace"] = reasoning_trace_delta
    return response


def build_graph(
    agent_config: AgentConfig,
    routing_config: RoutingConfig | None = None,
    tool_registry: ToolRegistry | None = None,
    cache_dir: Path | str = Path("cache"),
    checkpointer: Any | None = None,
    agent_facts_registry: AgentFactsRegistry | None = None,
    telemetry: FrameworkTelemetry | None = None,
    authorization_service: Any | None = None,
    trace_service: Any | None = None,
    *,
    interrupt_before_execute_tool: bool = True,
) -> Any:
    """Build and compile the ReAct StateGraph.

    When both ``checkpointer`` and ``telemetry`` are supplied, the
    checkpointer is wrapped with :class:`InstrumentedCheckpointer` so
    every ``put``/``get`` updates the telemetry counters that feed the
    STORY-413 feasibility gate.

    The caller is responsible for persisting the telemetry after
    invocation, e.g.::

        from services.observability import FrameworkTelemetry, save_telemetry

        telemetry = FrameworkTelemetry()
        app = build_graph(cfg, checkpointer=cp, telemetry=telemetry)
        await app.ainvoke({...})
        save_telemetry(telemetry)

    ``interrupt_before_execute_tool`` (default True when a checkpointer is
    supplied) compiles with ``interrupt_before=['execute_tool']`` for HITL /
    risky-tool gating. Streaming dev entry points pass ``False`` so tools run
    automatically and the assistant can return after tool results.
    """
    routing_config = routing_config or RoutingConfig()
    tool_registry = tool_registry or ToolRegistry({})
    cache_dir = Path(cache_dir)

    llm_service = LLMService(config=agent_config)
    prompt_service = PromptService()
    black_box = BlackBoxRecorder(storage_dir=cache_dir / "black_box_recordings")
    phase_logger = PhaseLogger(storage_dir=cache_dir / "phase_logs")
    guardrail = InputGuardrail(
        name="prompt_injection",
        accept_condition="The input is a legitimate user query",
        llm_service=llm_service,
        prompt_service=prompt_service,
        judge_profile=default_fast_profile(),
        classifier=InjectionClassifier.maybe_load(),
    )
    output_validator = GuardRailValidator(pii_rules() + api_key_rules())

    # I2: task-adaptive goal judge, flag-gated (off in CI). When enabled it
    # overlays goal_met/criteria_met/unmet_conditions onto the TaskOutcome; the
    # deterministic keyword heuristic is the fallback when disabled or on error.
    goal_judge: GoalJudge | None = None
    if getattr(agent_config, "goal_judge_enabled", False):
        judge_profile = next(
            (m for m in agent_config.models if m.tier == "fast"),
            default_fast_profile(),
        )
        # Reuse the canonical PII + API-key rule sets, but coerce every rule to
        # REDACT so the judge-evidence scrubber masks secrets/PII in the tool
        # trajectory before they reach the judge prompt (the shared
        # output_validator leaves CRITICAL rules as BLOCK, which redact() skips).
        judge_redactor = GuardRailValidator([
            rule.model_copy(update={"fail_action": FailAction.REDACT})
            for rule in (pii_rules() + api_key_rules())
        ])
        goal_judge = GoalJudge(
            llm_service=llm_service,
            prompt_service=prompt_service,
            judge_profile=judge_profile,
            redactor=judge_redactor,
        )

    tool_schemas = tool_registry.get_schemas() if tool_registry else []

    # ── Story 1.2 + 1.4: guard_input_node with rejection branching + AgentFacts ──

    async def guard_input_node(state: AgentState, config: RunnableConfig) -> dict:
        step_count = state.get("step_count", 0)
        if step_count > 0:
            return {}

        workflow_id = state.get("workflow_id", "")
        task_input = state.get("task_input", "")

        black_box.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.TASK_STARTED,
            timestamp=datetime.now(UTC),
            details={"task_input": task_input[:200]},
        ))

        # Story 1.4: AgentFacts identity verification
        agent_facts_verified = True
        agent_capabilities: list[str] = []
        if agent_facts_registry is not None:
            registered_agent_id = (
                config.get("configurable", {}).get("registered_agent_id")
                or state.get("registered_agent_id", "")
            )
            if registered_agent_id:
                agent_facts_verified = agent_facts_registry.verify(registered_agent_id)
                if agent_facts_verified:
                    try:
                        facts = agent_facts_registry.get(registered_agent_id)
                        agent_capabilities = [cap.name for cap in facts.capabilities]
                    except Exception:
                        agent_capabilities = []
                black_box.record(TraceEvent(
                    event_id=str(uuid.uuid4()),
                    workflow_id=workflow_id,
                    event_type=EventType.GUARDRAIL_CHECKED,
                    timestamp=datetime.now(UTC),
                    details={
                        "guardrail": "agent_facts",
                        "agent_id": registered_agent_id,
                        "verified": agent_facts_verified,
                    },
                ))
                if not agent_facts_verified:
                    black_box.record(TraceEvent(
                        event_id=str(uuid.uuid4()),
                        workflow_id=workflow_id,
                        event_type=EventType.TASK_COMPLETED,
                        timestamp=datetime.now(UTC),
                        details={
                            "outcome": "rejected",
                            "reason": "agent_facts_verification_failed",
                            "step_count": 0,
                            "total_cost_usd": 0.0,
                        },
                    ))
                    return {
                        "agent_facts_verified": False,
                        "agent_capabilities": [],
                        "last_outcome": "rejected",
                        "current_workflow_phase": WorkflowPhase.INPUT_VALIDATION.value,
                    }

        # Story 1.2: guardrail with rejection branching
        try:
            accepted = await guardrail.is_acceptable(task_input)
        except Exception:
            accepted = True

        black_box.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.GUARDRAIL_CHECKED,
            timestamp=datetime.now(UTC),
            details={"accepted": accepted, "guardrail": "prompt_injection"},
        ))

        from services import eval_capture
        await eval_capture.record(
            target="guardrail",
            ai_input={"prompt": task_input[:200]},
            ai_response={"accepted": accepted},
            config=config,
        )

        if not accepted:
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.TASK_COMPLETED,
                timestamp=datetime.now(UTC),
                details={
                    "outcome": "rejected",
                    "reason": "guardrail_rejected",
                    "step_count": 0,
                    "total_cost_usd": 0.0,
                },
            ))
            return {
                "agent_facts_verified": agent_facts_verified,
                "agent_capabilities": agent_capabilities,
                "last_outcome": "rejected",
                "current_workflow_phase": WorkflowPhase.INPUT_VALIDATION.value,
            }

        return {
            "agent_facts_verified": agent_facts_verified,
            "agent_capabilities": agent_capabilities,
            "current_workflow_phase": WorkflowPhase.INPUT_VALIDATION.value,
        }

    def _guard_routing(state: AgentState) -> str:
        """Story 1.2: Branch on guard rejection -- halt graph instead of continuing."""
        if state.get("last_outcome") == "rejected":
            return "rejected"
        return "accepted"

    # ── Story 5.1: per-user budget enforcement ──

    async def route_node(state: AgentState, config: RunnableConfig) -> dict:
        workflow_id = state.get("workflow_id", "")

        # Story 5.1: per-user budget check
        configurable = config.get("configurable", {})
        user_max_cost = configurable.get("user_max_cost_per_task")
        budget_limit = user_max_cost if user_max_cost is not None else agent_config.max_cost_usd
        total_cost = state.get("total_cost_usd", 0.0)
        if total_cost >= budget_limit:
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.TASK_COMPLETED,
                timestamp=datetime.now(UTC),
                details={
                    "outcome": "budget_exceeded",
                    "step_count": state.get("step_count", 0),
                    "total_cost_usd": total_cost,
                    "budget_limit": budget_limit,
                },
            ))
            return {
                "last_outcome": "budget_exceeded",
                "current_workflow_phase": WorkflowPhase.ROUTING.value,
            }

        profile, reason = select_model(
            step_count=state.get("step_count", 0),
            consecutive_errors=state.get("consecutive_errors", 0),
            last_error_type=state.get("last_error_type", ""),
            total_cost_usd=state.get("total_cost_usd", 0.0),
            model_history=state.get("model_history", []),
            agent_config=agent_config,
            routing_config=routing_config,
        )

        if reason == "budget-downgrade" or reason.startswith("escalate-after"):
            prev_history = state.get("model_history", [])
            prev_tier = prev_history[-1]["tier"] if prev_history else "fast"
            if profile.tier != prev_tier:
                black_box.record(TraceEvent(
                    event_id=str(uuid.uuid4()),
                    workflow_id=workflow_id,
                    event_type=EventType.PARAMETER_CHANGED,
                    timestamp=datetime.now(UTC),
                    step=state.get("step_count", 0),
                    details={
                        "parameter": "model_tier",
                        "old_value": prev_tier,
                        "new_value": profile.tier,
                        "reason": reason,
                    },
                ))

        planning_depth, planning_depth_reason = select_planning_depth(
            task_input=state.get("task_input", ""),
            step_count=state.get("step_count", 0),
            tool_results_count=len(state.get("tool_results", [])),
        )
        plan_artifact = build_plan_artifact(
            planning_depth,
            task_input=state.get("task_input", ""),
        )

        black_box.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.STEP_PLANNED,
            timestamp=datetime.now(UTC),
            step=state.get("step_count", 0),
            details={
                "planning_depth": planning_depth,
                "plan_steps": len(plan_artifact.ordered_steps),
                "constraints": len(plan_artifact.constraints),
                "success_conditions": len(plan_artifact.success_conditions),
            },
        ))

        plan_validation = validate_plan_mece(plan_artifact)
        if not plan_validation.is_valid:
            capable = next(
                (item for item in agent_config.models if item.tier == "capable"),
                None,
            )
            if capable is not None:
                old_tier = profile.tier
                profile = capable
                reason = "plan-validation-escalation"

                black_box.record(TraceEvent(
                    event_id=str(uuid.uuid4()),
                    workflow_id=workflow_id,
                    event_type=EventType.PARAMETER_CHANGED,
                    timestamp=datetime.now(UTC),
                    step=state.get("step_count", 0),
                    details={
                        "parameter": "model_tier",
                        "old_value": old_tier,
                        "new_value": capable.tier,
                        "reason": "plan-validation-escalation",
                        "plan_issues": plan_validation.issues,
                    },
                ))

        alternatives = [m.name for m in agent_config.models if m.name != profile.name]
        if not alternatives:
            alternatives = [profile.name]

        confidence = 0.7
        if reason.startswith("budget-downgrade"):
            confidence = 1.0
        elif reason.startswith("escalate-after"):
            confidence = 0.9
        elif reason.startswith("retry-after-backoff"):
            confidence = 0.8
        elif reason.startswith("capable-for-planning"):
            confidence = 0.75

        detail_bits = [
            f"step={state.get('step_count', 0)}",
            f"errors={state.get('consecutive_errors', 0)}",
            f"last_err={state.get('last_error_type', '') or 'none'}",
            f"cost_usd={state.get('total_cost_usd', 0.0):.4f}",
            f"plan_depth={planning_depth}",
        ]
        rationale = f"{reason} ({', '.join(detail_bits)})"

        decision = Decision(
            phase=WorkflowPhase.ROUTING,
            description=f"Selected {profile.name}",
            alternatives=alternatives,
            rationale=rationale,
            confidence=confidence,
        )
        phase_logger.log_decision(workflow_id, decision)

        black_box.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.MODEL_SELECTED,
            timestamp=datetime.now(UTC),
            step=state.get("step_count", 0),
            details={
                "model": profile.name,
                "reason": reason,
                "plan_depth": planning_depth,
                "plan_valid": plan_validation.is_valid,
            },
        ))

        plan_ref = f".agent_plans/{workflow_id or 'wf'}_step_{state.get('step_count', 0)}.json"
        plan_payload = {
            "planning_depth": planning_depth,
            "planning_depth_reason": planning_depth_reason,
            "artifact": plan_artifact.model_dump(mode="json"),
            "validation": plan_validation.model_dump(mode="json"),
        }

        return {
            "selected_model": profile.name,
            "routing_reason": reason,
            "planning_depth": planning_depth,
            "planning_depth_reason": planning_depth_reason,
            "files": {
                plan_ref: json.dumps(plan_payload, sort_keys=True),
            },
            "plan_ref": plan_ref,
            "model_history": [
                {"step": state.get("step_count", 0), "model": profile.name, "tier": profile.tier, "reason": reason}
            ],
            "current_workflow_phase": WorkflowPhase.ROUTING.value,
        }

    # ── Story 1.1: call_llm_node with tool binding + multi-turn messages ──

    async def call_llm_node(state: AgentState, config: RunnableConfig) -> dict:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        workflow_id = state.get("workflow_id", "")
        model_name = state.get("selected_model", agent_config.default_model)

        try:
            profile = llm_service.get_profile(model_name)
        except KeyError:
            profile = agent_config.models[0] if agent_config.models else default_fast_profile()

        system_prompt = prompt_service.render_prompt(
            "system_prompt",
            additional_instructions=build_planning_instructions(
                state.get("planning_depth", "L0"),
                task_input=state.get("task_input", ""),
            ),
            include_routing_policy=True,
            budget_downgrade_pct=int(routing_config.budget_downgrade_threshold * 100),
            escalate_after_failures=routing_config.escalate_after_failures,
            max_escalations=routing_config.max_escalations,
        )

        # Story 1.1: build full multi-turn message list
        existing_messages = state.get("messages", [])
        if existing_messages:
            lc_messages = [SystemMessage(content=system_prompt)] + list(existing_messages)
        else:
            lc_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=state.get("task_input", "")),
            ]

        # ── No-progress graceful wrap-up: inject directive + strip tools ──
        repeats = _count_trailing_repeats(state.get("tool_results") or [])
        inject_wrapup = (
            repeats >= agent_config.no_progress_repeat_threshold
            and not state.get("no_progress_directive_sent", False)
        )
        effective_tool_schemas = tool_schemas or None
        if inject_wrapup:
            wrapup_directive = prompt_service.render_prompt(
                "no_progress_wrapup",
                task_input=state.get("task_input", ""),
            )
            lc_messages.append(HumanMessage(content=wrapup_directive))
            effective_tool_schemas = None
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.STEP_PLANNED,
                timestamp=datetime.now(UTC),
                step=state.get("step_count", 0),
                details={"no_progress": True, "repeats": repeats},
            ))

        start_time = time.time()
        error: Exception | None = None
        try:
            # Story 1.1: use invoke_with_tools for tool binding
            response = await llm_service.invoke_with_tools(
                profile,
                lc_messages,
                tool_schemas=effective_tool_schemas,
            )
            latency_ms = (time.time() - start_time) * 1000
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error = e
            response = type("ErrorResponse", (), {
                "content": f"Error: {e}",
                "tool_calls": [],
                "usage_metadata": {},
                "response_metadata": {},
            })()
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.ERROR_OCCURRED,
                timestamp=datetime.now(UTC),
                step=state.get("step_count", 0),
                details={
                    "source": "llm_call",
                    "model": profile.name,
                    "error": str(e),
                    "latency_ms": latency_ms,
                },
            ))

        usage = getattr(response, "usage_metadata", {}) or {}
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)
        cost = (tokens_in * profile.cost_per_1k_input / 1000) + (tokens_out * profile.cost_per_1k_output / 1000)

        black_box.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.STEP_EXECUTED,
            timestamp=datetime.now(UTC),
            step=state.get("step_count", 0),
            details={
                "model": profile.name,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": cost,
                "latency_ms": latency_ms,
                "error": str(error) if error else None,
            },
        ))

        from services import eval_capture
        await eval_capture.record(
            target="call_llm",
            ai_input={"task_input": state.get("task_input", "")[:200]},
            ai_response=str(getattr(response, "content", ""))[:500],
            config=config,
            step=state.get("step_count", 0),
            model=profile.name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            latency_ms=latency_ms,
        )

        content = getattr(response, "content", "")
        tool_calls = getattr(response, "tool_calls", [])

        scan = output_guardrail_scan(str(content or ""), output_validator)
        if scan.blocked:
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.GUARDRAIL_CHECKED,
                timestamp=datetime.now(UTC),
                step=state.get("step_count", 0),
                details={
                    "stage": "output",
                    "blocked": True,
                    "failed_rules": [
                        r.guardrail_name for r in scan.rule_results if not r.passed
                    ],
                },
            ))
            content = scan.sanitized_content
            tool_calls = []
        else:
            if scan.sanitized_content != content:
                black_box.record(TraceEvent(
                    event_id=str(uuid.uuid4()),
                    workflow_id=workflow_id,
                    event_type=EventType.GUARDRAIL_CHECKED,
                    timestamp=datetime.now(UTC),
                    step=state.get("step_count", 0),
                    details={
                        "stage": "output",
                        "blocked": False,
                        "redacted": True,
                        "failed_rules": [
                            r.guardrail_name for r in scan.rule_results if not r.passed
                        ],
                    },
                ))
            content = scan.sanitized_content

        ai_msg = AIMessage(content=content, tool_calls=tool_calls)

        # Story 1.3: store error for propagation to evaluator
        result: dict[str, Any] = {
            "messages": [ai_msg],
            "total_cost_usd": cost,
            "total_input_tokens": tokens_in,
            "total_output_tokens": tokens_out,
            "current_token_count": tokens_in + tokens_out,
            "current_workflow_phase": WorkflowPhase.MODEL_INVOCATION.value,
        }
        if inject_wrapup:
            result["no_progress_directive_sent"] = True
        if error is not None:
            result["last_llm_error"] = str(error)
            result["last_llm_error_code"] = getattr(error, "status_code", None)
        return result

    # ── Story 1.3: execute_tool_node with error capture ──

    async def execute_tool_node(state: AgentState, config: RunnableConfig) -> dict:
        result = _execute_tools_impl(
            dict(state),
            tool_registry=tool_registry,
            black_box=black_box,
            agent_config=agent_config,
            trace_service=trace_service,
        )
        return result

    # ── verify_authorize_log_node: per-tool-call PEP (opt-in) ──

    async def verify_authorize_log_node(state: AgentState, config: RunnableConfig) -> dict:
        """Per-action PEP per docs/Architectures/FOUR_LAYER_ARCHITECTURE.md §verify_authorize_log_node.

        When ``authorization_service`` is configured, checks every pending
        tool call against the identity's capabilities/policies. A ``deny``
        short-circuits: the tool is not executed and the graph proceeds to
        evaluation with an error outcome.
        """
        if authorization_service is None:
            return {}

        messages = state.get("messages", [])
        if not messages:
            return {}

        last_msg = messages[-1]
        tool_calls = getattr(last_msg, "tool_calls", [])
        if not tool_calls:
            return {}

        configurable = config.get("configurable", {})
        registered_agent_id = (
            configurable.get("registered_agent_id")
            or state.get("registered_agent_id", "")
        )

        facts = None
        if agent_facts_registry is not None and registered_agent_id:
            try:
                facts = agent_facts_registry.get(registered_agent_id)
            except Exception:
                facts = None

        if facts is None:
            return {}

        workflow_id = state.get("workflow_id", "")
        trace_id = configurable.get("trace_id") or workflow_id

        for tc in tool_calls:
            tool_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
            decision = authorization_service.authorize(
                facts, tool_name, {}, trace_id=trace_id
            )
            if not decision.allowed:
                logger.warning(
                    "verify_authorize_log_node denied tool=%s agent=%s reason=%s",
                    tool_name,
                    registered_agent_id,
                    decision.reason,
                )
                if trace_service is not None:
                    from trust.models import TrustTraceRecord as _TTR

                    trace_service.emit(
                        _TTR(
                            event_id=str(uuid.uuid4()),
                            timestamp=datetime.now(UTC),
                            trace_id=trace_id,
                            agent_id=registered_agent_id,
                            layer="L4",
                            event_type="tool_call_denied",
                            details={
                                "tool": tool_name,
                                "enforcement": decision.enforcement,
                                "reason": decision.reason,
                            },
                            outcome="fail",
                        )
                    )
                return {
                    "last_outcome": "rejected",
                    "last_error_type": "authorization_denied",
                    "current_workflow_phase": WorkflowPhase.TOOL_EXECUTION.value,
                }

        return {}

    def _verify_authz_routing(state: AgentState) -> str:
        if state.get("last_outcome") == "rejected":
            return "denied"
        return "authorized"

    # ── Story 1.3: evaluate_node with real error propagation ──

    async def evaluate_node(state: AgentState, config: RunnableConfig) -> dict:
        workflow_id = state.get("workflow_id", "")
        messages = state.get("messages", [])
        last_msg = messages[-1] if messages else None
        content = getattr(last_msg, "content", "") if last_msg else ""

        # Story 1.3: reconstruct error from state if present
        llm_error_str = state.get("last_llm_error")
        error: Exception | None = None
        if llm_error_str:
            error = Exception(llm_error_str)
            error_code = state.get("last_llm_error_code")
            if error_code is not None:
                error.status_code = error_code  # type: ignore[attr-defined]

        # Check for tool execution errors in content
        if error is None and content and content.startswith("Error:"):
            error = Exception(content)
            if "tool" in content.lower():
                pass  # classify_outcome will detect "tool" keyword

        outcome, error_record = classify_outcome(
            content,
            error,
            model=state.get("selected_model", ""),
            step=state.get("step_count", 0),
        )
        if outcome == "success":
            synthesis_validation = validate_synthesis(
                final_answer=content,
                task_input=state.get("task_input", ""),
                planning_depth=state.get("planning_depth", "L0"),
                todos=state.get("todos", []),
            )
            if not synthesis_validation.passed:
                outcome = "failure"
                error_record = ErrorRecord(
                    step=state.get("step_count", 0),
                    error_type="synthesis_validation_error",
                    error_code=None,
                    message="; ".join(synthesis_validation.feedback) or "synthesis validation failed",
                    model=state.get("selected_model", ""),
                    timestamp=time.time(),
                )
        error_type = error_record.error_type if error_record else None

        # Story 5.2: backoff calculation for retryable errors
        backoff_until: float | None = None
        if error_type == "retryable":
            consecutive = state.get("consecutive_errors", 0) + 1
            backoff_seconds = min(2 ** consecutive, 64)
            backoff_until = time.time() + backoff_seconds

        step_result = build_step_result(
            step_id=state.get("step_count", 0),
            action="answer",
            model_used=state.get("selected_model", ""),
            routing_reason=state.get("routing_reason", ""),
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            latency_ms=0.0,
            outcome=outcome,
            error_record=error_record,
            reasoning=content[:200] if content else "",
        )

        rationale = (
            f"Error type: {error_type}; {error_record.message[:120]}"
            if error_record
            else "Step completed successfully"
        )
        decision = Decision(
            phase=WorkflowPhase.EVALUATION,
            description=f"Outcome: {outcome}",
            alternatives=["retry", "escalate", "terminal"],
            rationale=rationale,
            confidence=1.0 if error_record is None else 0.8,
        )
        phase_logger.log_decision(workflow_id, decision)

        result: dict[str, Any] = {
            "step_count": 1,
            "last_outcome": outcome,
            "last_error_type": error_type or "",
            "consecutive_errors": 0 if outcome == "success" else state.get("consecutive_errors", 0) + 1,
            "error_history": [error_record.model_dump(mode="json")] if error_record else [],
            "step_results": [step_result.model_dump()],
            "current_workflow_phase": WorkflowPhase.EVALUATION.value,
            "last_llm_error": "",
            "last_llm_error_code": None,
        }
        if backoff_until is not None:
            result["backoff_until"] = backoff_until

        token_count = int(state.get("current_token_count", 0) or 0)
        if should_compact_trajectory(
            current_token_count=token_count,
            token_threshold=agent_config.trajectory_compaction_token_threshold,
        ):
            summary_text = build_compaction_summary(
                task_input=state.get("task_input", ""),
                reasoning_trace=state.get("reasoning_trace", []),
                tool_results=state.get("tool_results", []),
                latest_output=content,
            )
            workflow_id_suffix = (state.get("workflow_id", "") or "wf")[-8:]
            offload_ref = f".agent_offload/trajectory_summary_{workflow_id_suffix}.md"
            result["files"] = {offload_ref: summary_text}
            result["reasoning_trace"] = [summary_text]
            result["truncation_applied"] = True

        updated_step_count = state.get("step_count", 0) + 1
        updated_cost = state.get("total_cost_usd", 0.0)
        has_pending_tool = bool(
            messages and isinstance(messages[-1], ToolMessage)
        )
        continuation = check_continuation(
            step_count=updated_step_count,
            total_cost_usd=updated_cost,
            last_outcome=outcome,
            last_error_type=error_type,
            agent_config=agent_config,
            has_pending_tool_result=has_pending_tool,
            backoff_until=backoff_until,
        )
        if continuation == "done":
            # I2: evaluate final answer against plan success_conditions
            plan_ref = state.get("plan_ref", "")
            plan_data: dict[str, Any] = {}
            if plan_ref:
                plan_json_str = (state.get("files") or {}).get(plan_ref, "")
                if plan_json_str:
                    try:
                        plan_data = json.loads(plan_json_str)
                    except (json.JSONDecodeError, TypeError):
                        pass

            plan_artifact = plan_data.get("artifact", {})
            success_conditions = plan_artifact.get("success_conditions", [])
            plan_steps = plan_artifact.get("ordered_steps", [])

            termination_reason = outcome
            if updated_step_count >= agent_config.max_steps:
                termination_reason = "max_steps"
            elif updated_cost >= agent_config.max_cost_usd:
                termination_reason = "budget_exceeded"
            else:
                # I2: loop-exhaustion / no-progress wrap-up is the Austin
                # symptom — a clean final_answer produced after the agent
                # thrashed. Mark it unclean so evaluate_task_outcome downgrades
                # success -> partial instead of scoring corrupt-success.
                repeats = _count_trailing_repeats(state.get("tool_results") or [])
                if (
                    state.get("no_progress_directive_sent")
                    or repeats >= agent_config.no_progress_repeat_threshold
                ):
                    termination_reason = "no_progress"

            task_outcome = evaluate_task_outcome(
                final_answer=content,
                success_conditions=success_conditions,
                plan_steps=plan_steps,
                termination_reason=termination_reason,
                tool_results=state.get("tool_results"),
            )

            # I2: overlay a task-adaptive LLM-as-judge verdict onto the goal
            # signals. The judge NEVER changes ``outcome`` (the deterministic
            # process floor owns that); it only replaces the fragile keyword
            # goal_met/criteria_met/unmet_conditions. Failures fall back to the
            # heuristic so the judge is best-effort, never load-bearing.
            downgrade_reason: str | None = None
            if goal_judge is not None and content:
                try:
                    verdict = await goal_judge.evaluate(
                        task_input=state.get("task_input", ""),
                        final_answer=content,
                        success_conditions=success_conditions,
                        evidence=state.get("tool_results") or [],
                    )
                    task_outcome = task_outcome.model_copy(
                        update={
                            "goal_met": verdict.goal_met,
                            "criteria_met": round(verdict.criteria_met, 3),
                            "unmet_conditions": verdict.unmet_conditions,
                        }
                    )

                    # Stage 2 downgrade gate (AP-5: thin wrapper — the
                    # decision ``verdict.goal_met`` was computed in L3). Reads
                    # ONLY goal_met; STRICTLY success->partial. ``would_downgrade``
                    # is the shadow signal: in Stage 0/1 (flag off) it records
                    # what the gate *would* do without mutating the outcome.
                    would_downgrade = (
                        verdict.goal_met is False
                        and task_outcome.outcome == "success"
                    )
                    if would_downgrade and getattr(
                        agent_config, "goal_judge_downgrade_enabled", False
                    ):
                        prev_outcome = task_outcome.outcome
                        if prev_outcome != "success":
                            raise RuntimeError(
                                f"goal_judge downgrade gate reached with non-success "
                                f"source {prev_outcome!r}; strict success->partial "
                                "invariant violated"
                            )
                        task_outcome = task_outcome.model_copy(
                            update={"outcome": "partial"}
                        )
                        downgrade_reason = "goal_judge"

                    from services import eval_capture

                    await eval_capture.record(
                        target="goal_judge",
                        ai_input={
                            "task_input": state.get("task_input", "")[:500],
                            "success_conditions": success_conditions,
                        },
                        ai_response={
                            **verdict.model_dump(),
                            "would_downgrade": would_downgrade,
                            "downgrade_applied": downgrade_reason is not None,
                        },
                        config=config,
                        step=updated_step_count,
                        model=goal_judge.model_name,
                    )
                except Exception as exc:
                    logger.warning(
                        "goal_judge failed; falling back to heuristic: %s: %s",
                        type(exc).__name__,
                        exc,
                    )

            effective_outcome = task_outcome.outcome

            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.TASK_COMPLETED,
                timestamp=datetime.now(UTC),
                step=updated_step_count,
                details={
                    "outcome": effective_outcome,
                    "step_count": updated_step_count,
                    "total_cost_usd": updated_cost,
                    "error_type": error_type,
                    "task_completion_score": task_outcome.score,
                    "criteria_met": task_outcome.criteria_met,
                    "branch_coverage": task_outcome.branch_coverage,
                    "unmet_conditions": task_outcome.unmet_conditions,
                    "termination_clean": task_outcome.termination_clean,
                    "termination_reason": task_outcome.termination_reason,
                    "goal_met": task_outcome.goal_met,
                    "downgrade_reason": downgrade_reason,
                },
            ))

        return result

    def _parse_response(state: AgentState) -> str:
        messages = state.get("messages", [])
        if not messages:
            return "final_answer"

        last_msg = messages[-1]

        total_cost = state.get("total_cost_usd", 0.0)
        configurable: dict = {}
        user_max_cost = configurable.get("user_max_cost_per_task")
        budget_limit = user_max_cost if user_max_cost is not None else agent_config.max_cost_usd
        if total_cost >= budget_limit:
            return "budget_exceeded"

        return parse_llm_response(last_msg)

    def _should_continue(state: AgentState) -> str:
        """Continue the loop when ToolMessage(s) need a follow-up LLM synthesis pass.

        Without this, ``check_continuation`` treats post-tool ``success`` as a
        terminal answer and the graph ends after ``execute_tool`` — only the
        tool-call preview is streamed, never the final model response.

        Also detects repeated tool calls (no-progress) and terminates the loop
        when the agent re-invokes the same tool with the same input or gets the
        same output more than ``no_progress_repeat_threshold`` times in a row.
        """
        messages = state.get("messages") or []
        has_pending_tool_result = bool(
            messages and isinstance(messages[-1], ToolMessage)
        )

        repeated_count = _count_trailing_repeats(state.get("tool_results") or [])

        result = check_continuation(
            step_count=state.get("step_count", 0),
            total_cost_usd=state.get("total_cost_usd", 0.0),
            last_outcome=state.get("last_outcome", ""),
            last_error_type=state.get("last_error_type", None),
            agent_config=agent_config,
            has_pending_tool_result=has_pending_tool_result,
            backoff_until=state.get("backoff_until"),
            repeated_tool_calls=repeated_count,
            no_progress_directive_sent=state.get("no_progress_directive_sent", False),
        )
        branch = "continue" if result == "continue" else "done"
        return branch

    builder = StateGraph(AgentState)

    builder.add_node("guard_input", guard_input_node)
    builder.add_node("route", route_node)
    builder.add_node("call_llm", call_llm_node)
    builder.add_node("execute_tool", execute_tool_node)
    builder.add_node("evaluate", evaluate_node)

    builder.add_edge(START, "guard_input")

    # Story 1.2: conditional edge for guard rejection
    builder.add_conditional_edges(
        "guard_input",
        _guard_routing,
        {"accepted": "route", "rejected": END},
    )

    builder.add_edge("route", "call_llm")

    if authorization_service is not None:
        builder.add_node("verify_authorize_log", verify_authorize_log_node)
        builder.add_conditional_edges(
            "call_llm",
            _parse_response,
            {"tool_call": "verify_authorize_log", "final_answer": "evaluate", "budget_exceeded": END},
        )
        builder.add_conditional_edges(
            "verify_authorize_log",
            _verify_authz_routing,
            {"authorized": "execute_tool", "denied": "evaluate"},
        )
    else:
        builder.add_conditional_edges(
            "call_llm",
            _parse_response,
            {"tool_call": "execute_tool", "final_answer": "evaluate", "budget_exceeded": END},
        )

    builder.add_edge("execute_tool", "evaluate")
    builder.add_conditional_edges(
        "evaluate",
        _should_continue,
        {"continue": "route", "done": END},
    )

    # Story 2.1: checkpointer support
    # Story 2.2: interrupt_before for non-cacheable tools (only with checkpointer)
    # STORY-412: optional telemetry instrumentation wraps the checkpointer
    # so put/get calls update FrameworkTelemetry counters.
    compile_kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        _ensure_checkpoint_saver_instance(checkpointer)
        if telemetry is not None:
            checkpointer = InstrumentedCheckpointer(checkpointer, telemetry)
        compile_kwargs["checkpointer"] = checkpointer
        # Story 2.2: pause before tool side-effects when using checkpointers +
        # human-in-the-loop workflows. Dev middleware / streaming chat passes
        # interrupt_before_execute_tool=False so tool nodes run to completion
        # and the assistant can stream a final answer after tools complete.
        if interrupt_before_execute_tool:
            compile_kwargs["interrupt_before"] = ["execute_tool"]

    return builder.compile(**compile_kwargs)
