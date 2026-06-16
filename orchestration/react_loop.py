"""StateGraph definition: nodes, edges, compilation (TOPOLOGY ONLY).

Every node function is a thin wrapper that delegates to
framework-agnostic logic in components/ and services/.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send  # T3 fan-out: the one new langgraph surface

from components.evaluator import (
    build_step_result,
    check_continuation,
    classify_no_progress,
    classify_outcome,
    count_trailing_repeats as _count_trailing_repeats,
    evaluate_task_outcome,
    parse_llm_response,
)
from components.reflexion import decide_reentry, generate_reflection
from components.goal_judge import GoalJudge, _summarize_evidence, summarize_tool_calls
from components.plan_builder import build_planning_instructions
from components.plan_builder import build_plan_artifact
from components.plan_builder import build_plan_artifact_llm
from components.plan_builder import PlanArtifact
from components.plan_builder import compute_plan_fingerprint
from components.plan_builder import plan_is_stale
from components.plan_builder import validate_plan_mece
from components.plan_generator import PlanGenerator
from components.schemas import ErrorRecord, TaskUnderstanding
from components.task_understanding import (
    TaskUnderstandingGenerator,
    TaskUnderstandingValidationError,
)
from components.router import decide_escalation
from components.router import select_model
from components.router import select_planning_depth
from components.routing_config import RoutingConfig
from components.synthesis_validator import validate_synthesis
from components.supervisor_plan import plan_delegations
from orchestration.state import AgentState
from services.base_config import AgentConfig, ModelProfile, default_fast_profile
from services.goal_judge_runtime_config import (
    GoalJudgeRuntimeConfigReader,
    InMemoryGoalJudgeConfigReader,
)
from services.governance.agent_facts_registry import AgentFactsRegistry
from services.governance.black_box import (
    BUNDLE_SCHEMA_VERSION,
    BlackBoxRecorder,
    EventType,
    TraceEvent,
)
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
from services.observability import FrameworkTelemetry
from orchestration.checkpointer_wrapper import InstrumentedCheckpointer
from services.prompt_service import PromptService
from services.summarizer import (
    build_compaction_summary,
    should_compact_trajectory,
)
from services.tools.delegation_dispatcher import LocalLLMDelegationDispatcher
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
                details={"tool": tool_name, "args": tool_args, "cached": True, "tool_call_id": tool_id},
            ))
            results.append(ToolMessage(content=message_output, tool_call_id=tool_id))
            tool_results.append({
                "record_id": f"{state.get('step_count', 0)}:{tool_id}",
                "step_id": state.get("step_count", 0),
                "task_id": state.get("task_id", ""),
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
            details={"tool": tool_name, "args": tool_args, "cached": False, "tool_call_id": tool_id},
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
            "task_id": state.get("task_id", ""),
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


async def _reasoning_recap_impl(
    state: dict[str, Any],
    *,
    llm_service: Any,
    prompt_service: Any,
    agent_config: AgentConfig,
) -> dict[str, Any]:
    """F10 Tier-2 reasoning recap: one cheap-tier completion per run.

    Cost guard: 0–1-tool runs are skipped (Tier-1 narration already covers
    them for $0). The ``reasoning_recap`` tag lets the UI runtime suppress
    the call's chat-model events so recap tokens never leak into the
    answer stream. The recap is a UI affordance — any failure returns ``{}``
    and never breaks the run.
    """
    tool_results = state.get("tool_results") or []
    if len(tool_results) < 2:
        return {}
    try:
        final_answer = ""
        for msg in reversed(state.get("messages") or []):
            content = getattr(msg, "content", "")
            if content and not getattr(msg, "tool_calls", []):
                final_answer = str(content)
                break
        tool_steps = [
            {
                "tool_name": str(rec.get("tool_name", "")),
                "tool_input": rec.get("tool_input", {}),
                "ok": bool(rec.get("ok", True)),
                "error": rec.get("error") or "",
            }
            for rec in tool_results
            if isinstance(rec, dict)
        ]
        prompt = prompt_service.render_prompt(
            "reasoning_recap",
            task_input=str(state.get("task_input", "")),
            tool_steps=tool_steps,
            final_answer=final_answer,
        )
        profile = next(
            (m for m in agent_config.models if m.tier == "fast"),
            default_fast_profile(),
        )
        response = await llm_service.invoke(
            profile,
            [{"role": "user", "content": prompt}],
            config={"tags": ["reasoning_recap"]},
        )
        text = str(getattr(response, "content", "") or "").strip()
        if not text:
            return {}
        return {"reasoning_summary": text}
    except Exception:
        logger.exception("reasoning recap failed; run continues without it")
        return {}


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
    goal_judge_config_reader: GoalJudgeRuntimeConfigReader
    | InMemoryGoalJudgeConfigReader
    | None = None,
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
    _completion_emitted: set[str] = set()

    async def _emit_completion_once(
        workflow_id: str,
        step_count: int,
        outcome: str,
    ) -> None:
        """Record COMPLETION exactly once per workflow (three terminal TASK_COMPLETED sites)."""
        if not workflow_id or workflow_id in _completion_emitted:
            return
        _completion_emitted.add(workflow_id)
        async with phase_logger.phase(
            workflow_id,
            WorkflowPhase.COMPLETION,
            step_count,
            outcome=outcome,
        ):
            pass

    def _emit_delegation_trace(
        *,
        workflow_id: str,
        event_type: str,
        outcome: str,
        details: dict[str, Any],
    ) -> None:
        """Emit a per-branch ``delegation_*`` carrier (T3, GTP-1).

        Reuses the SAME event names and the SAME trace_service.emit path that
        task_tool's delegation carriers ride (react_loop tool-execution loop) —
        no new event vocabulary. Falls back to the BlackBox recorder when no
        trace_service is wired, so a carrier always lands (a delegation_* fact
        with zero carriers is the GTP zero-carrier defect).
        """
        if trace_service is not None:
            try:
                from trust.models import TrustTraceRecord

                trace_service.emit(TrustTraceRecord(
                    event_id=str(uuid.uuid4()),
                    timestamp=datetime.now(UTC),
                    trace_id=workflow_id,
                    agent_id="fanout-supervisor",
                    source_agent_id="fanout-supervisor",
                    layer="L4",
                    event_type=event_type,
                    details=dict(details),
                    outcome=outcome,
                ))
                return
            except Exception:
                logger.exception("failed to emit fan-out delegation trace event")
        # Fallback: still record the carrier on the BlackBox trace.
        black_box.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.TOOL_CALLED,
            timestamp=datetime.now(UTC),
            step=int(details.get("step_count", 0) or 0),
            details={"delegation_event": event_type, "outcome": outcome, **details},
        ))

    guardrail = InputGuardrail(
        name="prompt_injection",
        accept_condition="The input is a legitimate user query",
        llm_service=llm_service,
        prompt_service=prompt_service,
        judge_profile=default_fast_profile(),
        classifier=InjectionClassifier.maybe_load(),
    )
    output_validator = GuardRailValidator(pii_rules() + api_key_rules())

    # I2: task-adaptive goal judge — always constructed (cheap; no LLM until
    # evaluate()). Per-run enable/downgrade flags come from the injected reader.
    judge_profile = next(
        (m for m in agent_config.models if m.tier == "fast"),
        default_fast_profile(),
    )
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
    gj_reader = goal_judge_config_reader or GoalJudgeRuntimeConfigReader.from_env(
        defaults_enabled=agent_config.goal_judge_enabled,
        defaults_downgrade=agent_config.goal_judge_downgrade_enabled,
    )

    # task_understanding plan §4.5: plan-time intent restatement + checklist,
    # same fast-tier profile as the judge (H2). Cheap to construct; no LLM
    # call until generate(), and only when the success_conditions_source flag
    # is "shadow" or "generated".
    tu_generator = TaskUnderstandingGenerator(
        llm_service=llm_service,
        prompt_service=prompt_service,
        profile=judge_profile,
    )

    # Phase 1 (T1 plan-and-execute): fast-tier LLM plan decomposition. Same
    # shadow-first discipline as task_understanding — no LLM call until the
    # plan_source flag is "shadow"/"generated" and only at step 0 (route_node
    # memoizes the depth per task, so the plan is built once per task).
    plan_generator = PlanGenerator(
        llm_service=llm_service,
        prompt_service=prompt_service,
        profile=judge_profile,
    )

    tool_schemas = tool_registry.get_schemas() if tool_registry else []

    # ── Story 1.2 + 1.4: guard_input_node with rejection branching + AgentFacts ──

    async def guard_input_node(state: AgentState, config: RunnableConfig) -> dict:
        step_count = state.get("step_count", 0)
        if step_count > 0:
            return {}

        workflow_id = state.get("workflow_id", "")
        task_input = state.get("task_input", "")

        # E9 (Identity pillar): resolve the agent id before the first event so
        # TASK_STARTED can answer "who did it?". agent_name/agent_version are
        # config-sourced (always present, no registry round-trip); agent_facts_id
        # is the resolved registered id.
        registered_agent_id = (
            config.get("configurable", {}).get("registered_agent_id")
            or state.get("registered_agent_id", "")
        )

        async with phase_logger.phase(workflow_id, WorkflowPhase.INITIALIZATION, step_count):
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.TASK_STARTED,
                timestamp=datetime.now(UTC),
                details={
                    "task_input": task_input[:200],
                    "agent_name": agent_config.agent_name,
                    "agent_version": agent_config.agent_version,
                    "agent_facts_id": registered_agent_id,
                },
            ))

        # Story 1.4: AgentFacts identity verification
        agent_facts_verified = True
        agent_capabilities: list[str] = []
        rejection_payload: dict[str, Any] | None = None
        if agent_facts_registry is not None:
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
                            "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
                            "outcome": "rejected",
                            "reason": "agent_facts_verification_failed",
                            "step_count": step_count,
                            "total_cost_usd": 0.0,
                        },
                    ))
                    rejection_payload = {
                        "agent_facts_verified": False,
                        "agent_capabilities": [],
                        "last_outcome": "rejected",
                        "current_workflow_phase": WorkflowPhase.INPUT_VALIDATION.value,
                    }

        if rejection_payload is None:
            # Story 1.2: guardrail with rejection branching. decide() also returns
            # the cascade stage that owned the verdict so the trace can prove which
            # rail fired (G2 input rationale), not just the accept/reject bit.
            try:
                accepted, decision_stage = await guardrail.decide(task_input)
            except Exception:
                accepted, decision_stage = True, "error"

            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.GUARDRAIL_CHECKED,
                timestamp=datetime.now(UTC),
                details={
                    "guardrail": "prompt_injection",
                    "accepted": accepted,
                    "decision_stage": decision_stage,
                },
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
                        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
                        "outcome": "rejected",
                        "reason": "guardrail_rejected",
                        "step_count": step_count,
                        "total_cost_usd": 0.0,
                    },
                ))
                rejection_payload = {
                    "agent_facts_verified": agent_facts_verified,
                    "agent_capabilities": agent_capabilities,
                    "last_outcome": "rejected",
                    "current_workflow_phase": WorkflowPhase.INPUT_VALIDATION.value,
                }

        if rejection_payload is not None:
            async with phase_logger.phase(
                workflow_id,
                WorkflowPhase.INPUT_VALIDATION,
                step_count,
                outcome="rejected",
            ):
                await _emit_completion_once(workflow_id, step_count, "rejected")
                return rejection_payload

        async with phase_logger.phase(workflow_id, WorkflowPhase.INPUT_VALIDATION, step_count):
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
        step_count = state.get("step_count", 0)

        # Story 5.1: per-user budget check
        configurable = config.get("configurable", {})
        user_max_cost = configurable.get("user_max_cost_per_task")
        budget_limit = user_max_cost if user_max_cost is not None else agent_config.max_cost_usd
        total_cost = state.get("total_cost_usd", 0.0)
        if total_cost >= budget_limit:
            async with phase_logger.phase(
                workflow_id,
                WorkflowPhase.ROUTING,
                step_count,
                outcome="budget_exceeded",
            ):
                black_box.record(TraceEvent(
                    event_id=str(uuid.uuid4()),
                    workflow_id=workflow_id,
                    event_type=EventType.TASK_COMPLETED,
                    timestamp=datetime.now(UTC),
                    details={
                        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
                        "outcome": "budget_exceeded",
                        "step_count": step_count,
                        "total_cost_usd": total_cost,
                        "budget_limit": budget_limit,
                    },
                ))
                await _emit_completion_once(workflow_id, step_count, "budget_exceeded")
                return {
                    "last_outcome": "budget_exceeded",
                    "current_workflow_phase": WorkflowPhase.ROUTING.value,
                }

        async with phase_logger.phase(workflow_id, WorkflowPhase.ROUTING, step_count):
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

            current_task_id = state.get("task_id", "")
            # Memoize planning depth at step 0, per task. route_node re-runs
            # every evaluate→continue→route iteration; select_planning_depth
            # collapses to L0 once this task has produced a tool result
            # (post-tool-synthesis), so recomputing every pass would flip the
            # intended depth to L0 after the first tool call and cap the plan
            # at one step. Reuse the stored depth while the task is unchanged —
            # same memoize-on-task_id discipline as task_understanding.
            stored_depth = state.get("planning_depth", "")
            depth_is_fresh = (
                bool(stored_depth)
                and state.get("planning_depth_task_id", "") == current_task_id
            )
            if depth_is_fresh:
                planning_depth = stored_depth
                planning_depth_reason = state.get("planning_depth_reason", "")
            else:
                task_tool_results_count = sum(
                    1
                    for tr in (state.get("tool_results") or [])
                    if tr.get("task_id", "") == current_task_id
                )
                planning_depth, planning_depth_reason = select_planning_depth(
                    task_input=state.get("task_input", ""),
                    task_tool_results_count=task_tool_results_count,
                )

            # ── Phase 1 (T1): build / reuse / replan the plan artifact ──────
            # The plan is built once per task and memoized (mirroring depth).
            # On re-entry it is reused as-is UNLESS the latest tool result
            # invalidated it (plan_is_stale) — the replan gate (plan §2.2). A
            # rebuild after a surprising result re-decomposes from the task
            # rather than executing an already-wrong plan.
            plan_source = getattr(agent_config, "plan_source", "deterministic")
            stored_plan_raw = state.get("plan_artifact") or {}
            plan_is_fresh = (
                bool(stored_plan_raw)
                and state.get("plan_artifact_task_id", "") == current_task_id
            )
            task_tool_rows = [
                tr
                for tr in (state.get("tool_results") or [])
                if tr.get("task_id", "") == current_task_id
            ]
            last_tool_result = task_tool_rows[-1] if task_tool_rows else None
            replan_increment = 0
            plan_generated = False
            plan_gen_failure = ""

            if plan_is_fresh:
                try:
                    plan_artifact = PlanArtifact.model_validate(stored_plan_raw)
                except Exception:
                    plan_artifact = build_plan_artifact(
                        planning_depth, task_input=state.get("task_input", "")
                    )
                if plan_is_stale(plan_artifact, last_tool_result):
                    # Surprising tool result — re-plan from scratch (deterministic
                    # rebuild; the LLM re-plan would re-incur cost and the floor
                    # is the safe brittle-plan backstop). Counts as a replan.
                    plan_artifact = build_plan_artifact(
                        planning_depth, task_input=state.get("task_input", "")
                    )
                    replan_increment = 1
            else:
                # Step-0 build for this task. plan_source gates the LLM call:
                # "deterministic" never calls the model; "shadow" generates but
                # consumes the floor; "generated" consumes the LLM plan with the
                # floor as fallback. Shadow/generated both reach for the LLM here.
                plan_artifact = build_plan_artifact(
                    planning_depth, task_input=state.get("task_input", "")
                )
                if plan_source in ("shadow", "generated"):
                    raw_plan: dict[str, Any] | None = None
                    try:
                        raw_plan = await plan_generator.generate(
                            task_input=state.get("task_input", ""),
                            planning_depth=planning_depth,
                        )
                    except Exception as exc:
                        plan_gen_failure = f"{type(exc).__name__}: {exc}"
                    if raw_plan is not None:
                        # build_plan_artifact_llm owns parse/validate + floor.
                        generated_artifact = build_plan_artifact_llm(
                            planning_depth,
                            task_input=state.get("task_input", ""),
                            generate=lambda _t, _r=raw_plan: _r,
                        )
                        plan_generated = generated_artifact != build_plan_artifact(
                            planning_depth, task_input=state.get("task_input", "")
                        )
                        if plan_source == "generated":
                            plan_artifact = generated_artifact

            # task_understanding plan §4.5: generate the TaskUnderstanding
            # artifact once per run (memoized on the state key — route_node
            # re-enters every evaluate→continue→route iteration). Thin
            # wrapper (AP-5): one try/except; validation lives in components.
            understanding: dict[str, Any] = dict(state.get("task_understanding") or {})
            # Cross-turn staleness guard (governance audit 3921c61b): thread
            # state outlives the turn, task_id is minted per run. An artifact
            # bound to a previous turn's task is regenerated — including
            # user_edited ones (the edit blessed the OLD turn's criteria).
            # Within a run task_id is constant, so at-most-once memoization
            # per run is preserved.
            tu_stale = bool(understanding) and (
                state.get("task_understanding_task_id", "") != current_task_id
            )
            tu_decision_id = ""
            if not understanding or tu_stale:
                tu_mode = gj_reader.get().success_conditions_source
                generated_artifact: TaskUnderstanding | None = None
                tu_failure = ""
                # Per-attempt rejection trail (round 2): the generator retries
                # once on a gate rejection and calls back per rejected attempt.
                tu_rejections: list[dict[str, Any]] = []

                def _record_tu_rejection(
                    issues: list[str], attempt: int, conditions: list[str]
                ) -> None:
                    # Record-only (AP-5): one GUARDRAIL_CHECKED per rejected
                    # attempt; the retry policy lives in the component. The
                    # ``attempt`` key marks that a rejection no longer implies a
                    # fallback — attempt 0 may be followed by a recovered run.
                    # ``conditions`` is the rejected artifact TEXT (R3 bug #2):
                    # issue strings alone made round 2's failures un-replayable
                    # offline and its root-cause diagnosis wrong.
                    tu_rejections.append({
                        "attempt": attempt,
                        "issues": issues,
                        "conditions": conditions,
                    })
                    black_box.record(TraceEvent(
                        event_id=str(uuid.uuid4()),
                        workflow_id=workflow_id,
                        event_type=EventType.GUARDRAIL_CHECKED,
                        timestamp=datetime.now(UTC),
                        step=state.get("step_count", 0),
                        details={
                            "guardrail": "task_understanding_gates",
                            "passed": False,
                            "attempt": attempt,
                            "issues": issues,
                            "conditions": conditions,
                        },
                    ))

                tu_gate_exhausted = False
                if tu_mode in ("shadow", "generated"):
                    try:
                        generated_artifact = await tu_generator.generate(
                            task_input=state.get("task_input", ""),
                            on_gate_rejection=_record_tu_rejection,
                        )
                    except Exception as exc:
                        # Gate rejections are already recorded per attempt via
                        # the callback; this only captures the terminal failure
                        # class for the fallback rationale. Gate exhaustion
                        # (vs a parse/transport raise) drives the attempts
                        # accounting below.
                        tu_failure = f"{type(exc).__name__}: {exc}"
                        tu_gate_exhausted = isinstance(
                            exc, TaskUnderstandingValidationError
                        )
                consumed_generated = (
                    tu_mode == "generated" and generated_artifact is not None
                )
                if consumed_generated and generated_artifact is not None:
                    understanding = generated_artifact.model_dump(mode="json")
                else:
                    understanding = TaskUnderstanding(
                        restated_intent=state.get("task_input", "").strip()[:300],
                        success_conditions=list(plan_artifact.success_conditions),
                        source="deterministic",
                    ).model_dump(mode="json")

                # §4.7 Reasoning pillar: why THIS run uses generated vs
                # deterministic conditions. decision_id is the cross-pillar
                # join key (the MODEL_SELECTED idiom below).
                _retry_note = " after retry" if tu_rejections else ""
                if tu_mode == "deterministic":
                    tu_rationale = "flag deterministic: generation not attempted"
                elif generated_artifact is None:
                    tu_rationale = f"fallback to deterministic: {tu_failure}"
                elif consumed_generated:
                    tu_rationale = f"generated ok{_retry_note}"
                else:
                    tu_rationale = (
                        f"shadow: generated ok{_retry_note}, "
                        "judge consumes deterministic"
                    )
                if tu_stale:
                    tu_rationale += " (regenerated: new task on thread)"
                tu_decision = phase_logger.log_decision(workflow_id, Decision(
                    phase=WorkflowPhase.ROUTING,
                    description="success-conditions source",
                    alternatives=["generated", "deterministic-fallback"],
                    rationale=tu_rationale,
                    confidence=(
                        generated_artifact.confidence
                        if generated_artifact is not None
                        else 1.0
                    ),
                ))
                tu_decision_id = tu_decision.decision_id

                if tu_mode in ("shadow", "generated"):
                    from services import eval_capture, eval_telemetry

                    tu_ai_input = {
                        "task_input": eval_telemetry.clip_eval_text(
                            state.get("task_input", "")
                        ),
                    }
                    tu_ai_response = {
                        **(
                            generated_artifact.model_dump(mode="json")
                            if generated_artifact is not None
                            else {}
                        ),
                        "consumed": consumed_generated,
                        "fallback_reason": tu_failure,
                        "mode": tu_mode,
                        # Attempts actually MADE (R3 bug #1): on terminal gate
                        # exhaustion every attempt is in tu_rejections (the
                        # callback fired per attempt); any other outcome —
                        # success, or a parse/transport raise — adds the one
                        # attempt that ended without a rejection callback.
                        # rejected_conditions carries each attempt's full text
                        # (R3 bug #2) so rounds can be re-simulated offline.
                        "attempts": (
                            len(tu_rejections)
                            if tu_gate_exhausted
                            else len(tu_rejections) + 1
                        ),
                        "rejected_conditions": tu_rejections,
                    }
                    await eval_capture.record(
                        target="task_understanding",
                        ai_input=tu_ai_input,
                        ai_response=tu_ai_response,
                        config=config,
                        step=state.get("step_count", 0),
                        model=tu_generator.model_name,
                    )
                    _tu_trace = workflow_id or configurable.get("task_id", "")
                    await eval_telemetry.publish_task_understanding(
                        trace_id=_tu_trace,
                        user_id=configurable.get("user_id", "anonymous"),
                        task_id=configurable.get("task_id", _tu_trace),
                        ai_input=tu_ai_input,
                        ai_response=tu_ai_response,
                        step=state.get("step_count", 0),
                        model=tu_generator.model_name,
                    )

            plan_ref = f".agent_plans/{workflow_id or 'wf'}_step_{state.get('step_count', 0)}.json"

            # Phase 4 (E10): fingerprint the plan's identity and compare against
            # the last one. ``route_node`` re-runs every iteration, re-emitting
            # an identical plan; the fingerprint lets the relay suppress the
            # duplicate EXPORT while the JSONL row is still recorded with
            # ``plan_changed`` every iteration (canonical record stays complete).
            plan_fingerprint = compute_plan_fingerprint(planning_depth, plan_artifact)
            plan_changed = plan_fingerprint != state.get("last_plan_fingerprint")

            step_planned_details: dict[str, Any] = {
                "planning_depth": planning_depth,
                "plan_steps": len(plan_artifact.ordered_steps),
                "constraints": len(plan_artifact.constraints),
                "success_conditions": len(
                    understanding.get("success_conditions")
                    or plan_artifact.success_conditions
                ),
                # §4.7 Recording pillar: join keys, not content. The
                # artifact text lives in the plan payload and the
                # eval.task_understanding observation.
                "conditions_source": understanding.get("source", "deterministic"),
                "plan_ref": plan_ref,
                "decision_id": tu_decision_id,
                "plan_fingerprint": plan_fingerprint,
                "plan_changed": plan_changed,
                # Phase 1 (T1) provenance: how this plan was produced and
                # whether the replan gate fired this pass. plan_source is the
                # flag; plan_generated marks that an LLM plan was consumed (vs
                # the deterministic floor); replanned marks a mid-task rebuild
                # after a surprising tool result.
                "plan_source": plan_source,
                "plan_generated": plan_generated,
                "replanned": bool(replan_increment),
            }
            if plan_gen_failure:
                step_planned_details["plan_gen_failure"] = plan_gen_failure
            # E8 (Reasoning pillar): on a CHANGED plan, carry a capped summary of
            # the ordered-step titles so the trace shows WHAT was planned without
            # opening the plan payload. Unchanged re-emissions stay lean (the
            # relay suppresses them; repeating the summary would just be noise).
            if plan_changed:
                step_planned_details["plan_summary"] = [
                    (s.title or "")[:120]
                    for s in plan_artifact.ordered_steps[:5]
                ]

            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.STEP_PLANNED,
                timestamp=datetime.now(UTC),
                step=state.get("step_count", 0),
                details=step_planned_details,
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
            decision = phase_logger.log_decision(workflow_id, decision)

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
                    "decision_id": decision.decision_id,
                    # E7 (Reasoning pillar): mirror the PhaseLogger Decision's
                    # rationale + alternatives onto the event so the "why" of the
                    # model choice is answerable from the trace without joining
                    # to the phase log. Same data, two sinks.
                    "rationale": rationale,
                    "alternatives": alternatives,
                },
            ))

            plan_payload = {
                "planning_depth": planning_depth,
                "planning_depth_reason": planning_depth_reason,
                "artifact": plan_artifact.model_dump(mode="json"),
                "validation": plan_validation.model_dump(mode="json"),
                "task_understanding": understanding,
            }

            return {
                "task_understanding": understanding,
                "task_understanding_task_id": current_task_id,
                "selected_model": profile.name,
                "routing_reason": reason,
                "planning_depth": planning_depth,
                "planning_depth_reason": planning_depth_reason,
                "planning_depth_task_id": current_task_id,
                "plan_artifact": plan_artifact.model_dump(mode="json"),
                "plan_artifact_task_id": current_task_id,
                "replan_count": replan_increment,
                "files": {
                    plan_ref: json.dumps(plan_payload, sort_keys=True),
                },
                "plan_ref": plan_ref,
                "last_plan_fingerprint": plan_fingerprint,
                "model_history": [
                    {"step": state.get("step_count", 0), "model": profile.name, "tier": profile.tier, "reason": reason}
                ],
                "current_workflow_phase": WorkflowPhase.ROUTING.value,
            }

    # ── Story 1.1: call_llm_node with tool binding + multi-turn messages ──

    async def call_llm_node(state: AgentState, config: RunnableConfig) -> dict:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        workflow_id = state.get("workflow_id", "")
        step_count = state.get("step_count", 0)
        model_name = state.get("selected_model", agent_config.default_model)

        try:
            profile = llm_service.get_profile(model_name)
        except KeyError:
            profile = agent_config.models[0] if agent_config.models else default_fast_profile()

        # Phase 2 (T2): fold accumulated reflexion critiques into the planning
        # instructions on re-entry — the semantic gradient that steers the retry.
        # Append-only, so each loop pass sees every prior critique (arxiv
        # 2303.11366). No-op when reflexion is disabled or none have accrued.
        planning_instructions = build_planning_instructions(
            state.get("planning_depth", "L0"),
            task_input=state.get("task_input", ""),
        )
        reflections = state.get("reflections") or []
        if reflections:
            critiques = "\n".join(
                f"- {r.get('critique', '').strip()}"
                for r in reflections
                if r.get("critique", "").strip()
            )
            if critiques:
                planning_instructions += (
                    "\n\nPrior attempts fell short. Apply these critiques before "
                    f"answering:\n{critiques}"
                )

        system_prompt = prompt_service.render_prompt(
            "system_prompt",
            additional_instructions=planning_instructions,
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
                step=step_count,
                details={"no_progress": True, "repeats": repeats},
            ))

        phase_logger.start_phase(workflow_id, WorkflowPhase.MODEL_INVOCATION, step_count)
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
                step=step_count,
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
            step=step_count,
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
            step=step_count,
            model=profile.name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            latency_ms=latency_ms,
        )

        content = getattr(response, "content", "")
        tool_calls = getattr(response, "tool_calls", [])
        phase_logger.end_phase(
            workflow_id,
            WorkflowPhase.MODEL_INVOCATION,
            "error" if error is not None else "ok",
            step_count,
        )

        async with phase_logger.phase(workflow_id, WorkflowPhase.OUTPUT_VALIDATION, step_count):
            # G2: always emit an output-stage guardrail_checked event, even on a
            # clean pass. Previously the event only fired on block/redact, so a
            # clean scan left no record that the rail ran at all — the "guard who
            # showed up, did their job, and left no log entry" failure mode. A
            # single always-on event makes both the negative (blocked/redacted) and
            # the positive (checked, clean) outcomes provable in the trace.
            scan = output_guardrail_scan(str(content or ""), output_validator)
            redacted = (not scan.blocked) and (scan.sanitized_content != content)
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.GUARDRAIL_CHECKED,
                timestamp=datetime.now(UTC),
                step=step_count,
                details={
                    "stage": "output",
                    "guardrail": "output_scan",
                    "checked": True,
                    "blocked": scan.blocked,
                    "redacted": redacted,
                    "failed_rules": [
                        r.guardrail_name for r in scan.rule_results if not r.passed
                    ],
                },
            ))
            if scan.blocked:
                tool_calls = []
            content = scan.sanitized_content

            ai_msg = AIMessage(content=content, tool_calls=tool_calls)

            # Story 1.3: store error for propagation to evaluator
            result: dict[str, Any] = {
                "messages": [ai_msg],
                "total_cost_usd": cost,
                "total_input_tokens": tokens_in,
                "total_output_tokens": tokens_out,
                "current_token_count": tokens_in + tokens_out,
                "current_workflow_phase": WorkflowPhase.OUTPUT_VALIDATION.value,
            }
            if inject_wrapup:
                result["no_progress_directive_sent"] = True
            if error is not None:
                result["last_llm_error"] = str(error)
                result["last_llm_error_code"] = getattr(error, "status_code", None)
            return result

    # ── Story 1.3: execute_tool_node with error capture ──

    async def execute_tool_node(state: AgentState, config: RunnableConfig) -> dict:
        workflow_id = state.get("workflow_id", "")
        step_count = state.get("step_count", 0)
        async with phase_logger.phase(workflow_id, WorkflowPhase.TOOL_EXECUTION, step_count):
            return _execute_tools_impl(
                dict(state),
                tool_registry=tool_registry,
                black_box=black_box,
                agent_config=agent_config,
                trace_service=trace_service,
            )

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
                step_count = state.get("step_count", 0)
                async with phase_logger.phase(
                    workflow_id,
                    WorkflowPhase.TOOL_EXECUTION,
                    step_count,
                    outcome="denied",
                ):
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

    def _escalation_carrier(
        state: AgentState, effective_outcome: str, task_outcome: Any
    ) -> dict[str, Any]:
        """Step 0b: derive the escalation trace carrier (counts/enums only).

        Records WHY the loop did or didn't re-enter, mirroring the exact scalars
        ``_should_continue_or_escalate`` feeds ``decide_escalation`` so the trace
        agrees with the route. No content — the critique lives in ``reflections``.

        ``escalation_reason`` enum:
          - ``disabled``         reflexion off (the live prod default)
          - ``budget_exhausted`` ceiling hit; decide_escalation holds (no thrash)
          - ``verdict``          failed/partial under budget -> escalate (§5 primary)
          - ``prose_repeat``     D3 no-tool thrash on a clean verdict -> escalate
          - ``clean``            success / no signal -> hold (false-positive guard)
        """
        attempt = len(state.get("reflections") or [])
        max_attempts = agent_config.max_reflexion_attempts
        carrier: dict[str, Any] = {
            "reflexion_attempt": attempt,
            "max_reflexion_attempts": max_attempts,
        }
        if not agent_config.reflexion_enabled:
            carrier["escalation_decision"] = "done"
            carrier["escalation_reason"] = "disabled"
            return carrier

        recent_prose = [
            str(getattr(m, "content", ""))
            for m in (state.get("messages") or [])
            if isinstance(m, AIMessage)
        ]
        prose_kind = classify_no_progress(
            state.get("tool_results") or [],
            recent_prose,
            tool_threshold=agent_config.no_progress_repeat_threshold,
            prose_threshold=agent_config.no_progress_repeat_threshold,
        )
        decision = decide_escalation(
            goal_verdict=effective_outcome,
            unmet_conditions=list(task_outcome.unmet_conditions),
            prose_kind=prose_kind,
            attempt=attempt,
            max_attempts=max_attempts,
        )
        carrier["escalation_decision"] = "reflect" if decision == "escalate" else "done"
        if decision == "escalate":
            # decide_escalation escalates on verdict first, then prose_repeat.
            verdict_triggers = (
                decide_reentry(
                    attempt=attempt,
                    max_attempts=max_attempts,
                    last_verdict=effective_outcome,
                )
                == "reflect"
            )
            carrier["escalation_reason"] = "verdict" if verdict_triggers else "prose_repeat"
        elif attempt >= max_attempts:
            carrier["escalation_reason"] = "budget_exhausted"
        else:
            carrier["escalation_reason"] = "clean"
        return carrier

    # ── Story 1.3: evaluate_node with real error propagation ──

    async def evaluate_node(state: AgentState, config: RunnableConfig) -> dict:
        workflow_id = state.get("workflow_id", "")
        step_count = state.get("step_count", 0)

        async with phase_logger.phase(workflow_id, WorkflowPhase.EVALUATION, step_count):
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

                # task_understanding plan §4.5: the artifact owns the success
                # definition when present (generated or user_edited); the plan
                # artifact's deterministic floor is the fallback.
                understanding = state.get("task_understanding") or {}
                if understanding.get("success_conditions"):
                    success_conditions = list(understanding["success_conditions"])
                conditions_source = understanding.get("source", "deterministic")
                restated_intent = understanding.get("restated_intent", "")

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
                # Phase 1 (E1): shape-stable shadow signal. ``False`` whenever the
                # judge is skipped/failed so TASK_COMPLETED always carries it and a
                # reader sees the gate's would-fire intent without opening
                # eval.goal_judge. Set True below only in the genuine shadow case.
                would_downgrade = False
                gj_cfg = gj_reader.get()
                if gj_cfg.goal_judge_enabled and content:
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
                        if would_downgrade and gj_cfg.goal_judge_downgrade_enabled:
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

                        from services import eval_capture, eval_telemetry

                        gj_tool_results = state.get("tool_results") or []
                        # Stage 5 Tier 3 plan §"Phase 2.5" — pipeline-dimension
                        # labels (D1 planning_depth, D3 routing_reason, D4
                        # model_tier, D6 cost_fraction) on the input side so
                        # Stage 6 can slice judge metrics from Langfuse alone
                        # without re-joining other traces.
                        _gj_model_history = state.get("model_history", []) or []
                        _gj_model_tier = (
                            _gj_model_history[-1].get("tier", "")
                            if _gj_model_history
                            and isinstance(_gj_model_history[-1], dict)
                            else ""
                        )
                        _gj_max_cost = max(agent_config.max_cost_usd, 1e-9)
                        _gj_cost_fraction = round(
                            state.get("total_cost_usd", 0.0) / _gj_max_cost, 3
                        )
                        gj_ai_input = {
                            "task_input": eval_telemetry.clip_eval_text(
                                state.get("task_input", "")
                            ),
                            "success_conditions": success_conditions,
                            "final_answer": eval_telemetry.clip_eval_text(
                                content or ""
                            ),
                            "evidence_digest": _summarize_evidence(gj_tool_results),
                            "tool_calls_summary": summarize_tool_calls(gj_tool_results),
                            "plan_steps": len(plan_steps),
                            "planning_depth": state.get("planning_depth", "L0"),
                            "routing_reason": state.get("routing_reason", ""),
                            "model_tier": _gj_model_tier,
                            "cost_fraction": _gj_cost_fraction,
                            # task_understanding plan §4.7: judge verdicts are
                            # stratifiable by condition provenance from the
                            # Langfuse observation alone.
                            "conditions_source": conditions_source,
                            "restated_intent": restated_intent,
                        }
                        gj_ai_response = {
                            **verdict.model_dump(),
                            "would_downgrade": would_downgrade,
                            "downgrade_applied": downgrade_reason is not None,
                            "config_source": gj_cfg.source,
                            "config_updated_at": (
                                gj_cfg.updated_at.isoformat()
                                if gj_cfg.updated_at
                                else None
                            ),
                            "config_schema_version": gj_cfg.schema_version,
                        }
                        await eval_capture.record(
                            target="goal_judge",
                            ai_input=gj_ai_input,
                            ai_response=gj_ai_response,
                            config=config,
                            step=updated_step_count,
                            model=goal_judge.model_name,
                        )
                        _cfg = config.get("configurable", {})
                        _trace_id = state.get("workflow_id") or _cfg.get("task_id", "")
                        await eval_telemetry.publish_goal_judge(
                            trace_id=_trace_id,
                            user_id=_cfg.get("user_id", "anonymous"),
                            task_id=_cfg.get("task_id", _trace_id),
                            ai_input=gj_ai_input,
                            ai_response=gj_ai_response,
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

                # Phase 2 (T2): persist the routing carriers so the post-evaluate
                # reflect-vs-done decision (_should_continue_or_escalate) can read
                # the verdict without re-running the judge. Last-write-wins.
                result["last_task_outcome"] = effective_outcome
                result["last_unmet_conditions"] = list(task_outcome.unmet_conditions)
                result["last_final_answer"] = content or ""

                # Step 0b (e2e-stress plan §2.2): escalation-reason carrier.
                # evaluate_node owns the verdict, so it records the escalation
                # fact here for the trace; _should_continue_or_escalate re-derives
                # the SAME decision for the route (decide_escalation is pure +
                # idempotent — LP-2 keeps the routing fn from recording). Join
                # keys / enums only, never the critique text (§4.7 Recording).
                _esc = _escalation_carrier(state, effective_outcome, task_outcome)

                black_box.record(TraceEvent(
                    event_id=str(uuid.uuid4()),
                    workflow_id=workflow_id,
                    event_type=EventType.TASK_COMPLETED,
                    timestamp=datetime.now(UTC),
                    step=updated_step_count,
                    details={
                        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
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
                        "would_downgrade": would_downgrade,
                        "downgrade_reason": downgrade_reason,
                        # Step 0b: tiered-loops escalation carrier (Phase 2/3).
                        "escalation_decision": _esc["escalation_decision"],
                        "escalation_reason": _esc["escalation_reason"],
                        "reflexion_attempt": _esc["reflexion_attempt"],
                        "max_reflexion_attempts": _esc["max_reflexion_attempts"],
                    },
                ))
                await _emit_completion_once(workflow_id, updated_step_count, effective_outcome)

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

    async def reflect_node(state: AgentState, config: RunnableConfig) -> dict:
        """OBP-3 thin wrapper: build a critique and append it to ``reflections``.

        Unpacks the routing carriers evaluate_node persisted, calls the pure
        ``generate_reflection`` (the LLM is injected as a fast-tier callable),
        appends one entry, and returns the delta. No logic — the reflect-vs-stop
        decision was already made by ``_should_continue_or_escalate``.
        """
        attempt = len(state.get("reflections") or [])
        unmet = list(state.get("last_unmet_conditions") or [])
        last_answer = state.get("last_final_answer", "") or ""

        async def _critique(prompt: str) -> str:
            response = await llm_service.invoke(
                judge_profile, [{"role": "user", "content": prompt}]
            )
            return str(getattr(response, "content", response))

        # generate_reflection is sync (pure); run the injected async critique
        # eagerly and hand it the result via a closure, mirroring Phase 1's
        # build_plan_artifact_llm async boundary.
        try:
            critique_text = await _critique(
                "You are critiquing a failed task attempt to guide a retry. "
                "Unmet success conditions:\n"
                + "\n".join(f"- {c}" for c in unmet if c and c.strip())
                + "\n\nPrevious answer:\n"
                + last_answer.strip()
                + "\n\nWrite a brief, specific critique naming what to fix next."
            )
            critique = generate_reflection(
                unmet_conditions=unmet,
                last_answer=last_answer,
                generate=lambda _p, _c=critique_text: _c,
            )
        except Exception:
            critique = generate_reflection(
                unmet_conditions=unmet, last_answer=last_answer
            )

        # Step 0b (e2e-stress plan §2.2): reflexion-step carrier. Proves the
        # loop re-entered and the gradient carried, with counts only — the
        # critique text stays in ``reflections``/the prompt, never the trace
        # (§4.7 Recording). reflexion_attempt is the 0-based index BEFORE this
        # entry is appended, so it agrees with the escalation carrier's count.
        black_box.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=state.get("workflow_id", ""),
            event_type=EventType.STEP_PLANNED,
            timestamp=datetime.now(UTC),
            step=state.get("step_count", 0),
            details={
                "reflexion_attempt": attempt,
                "reflexion_unmet_count": len(unmet),
                "reflexion_critique_chars": len(critique or ""),
            },
        ))

        return {
            "reflections": [
                {
                    "step_id": state.get("step_count", 0),
                    "attempt": attempt,
                    "critique": critique,
                    "unmet_conditions": unmet,
                }
            ],
        }

    def _should_continue_or_escalate(state: AgentState) -> str:
        """Extend ``_should_continue`` with the Phase 2 reflect branch.

        Existing continue/done semantics are preserved exactly: the reflect
        branch is only ever taken when the base decision is ``done`` (a terminal
        turn) AND reflexion is enabled AND the budget has room. So an L0 task, a
        disabled-reflexion run, or a clean success takes the identical path it
        took before Phase 2.
        """
        base = _should_continue(state)
        if base == "continue":
            return "continue"
        if not agent_config.reflexion_enabled:
            return "done"

        attempt = len(state.get("reflections") or [])
        verdict = state.get("last_task_outcome", "")

        # Classify the no-tool prose thrash (D3) so the pure escalation predicate
        # sees a scalar. tool_repeat is intentionally NOT a reflexion trigger —
        # check_continuation already terminates it (it surfaced via ``base``).
        recent_prose = [
            str(getattr(m, "content", ""))
            for m in (state.get("messages") or [])
            if isinstance(m, AIMessage)
        ]
        prose_kind = classify_no_progress(
            state.get("tool_results") or [],
            recent_prose,
            tool_threshold=agent_config.no_progress_repeat_threshold,
            prose_threshold=agent_config.no_progress_repeat_threshold,
        )

        # Phase 3: the §5 trigger matrix lives in one pure predicate now. The
        # node only gathers the scalars; decide_escalation owns the priority
        # order and the budget ceiling (so it can never thrash).
        decision = decide_escalation(
            goal_verdict=verdict,
            unmet_conditions=list(state.get("last_unmet_conditions") or []),
            prose_kind=prose_kind,
            attempt=attempt,
            max_attempts=agent_config.max_reflexion_attempts,
        )
        return "reflect" if decision == "escalate" else "done"

    # ── Phase 4 (T3): supervisor / worker / join fan-out nodes ──────────────
    #
    # A thin map-reduce topology over the EXISTING delegation substrate
    # (FOUR_LAYER L159 — delegation lives in Services+Orchestration; single
    # supervisor, NOT the deferred peer-to-peer of L1078). All three nodes are
    # OBP-3 thin wrappers: the fan-out DECISION is in components/supervisor_plan,
    # the worker execution is the shipped dispatcher; orchestration only wires
    # them. The whole fork is gated by agent_config.t3_fanout_enabled (default
    # OFF) — when off, _route_to_supervisor always returns "direct" and the graph
    # is byte-identical to the pre-T3 spine.

    _fanout_dispatcher = LocalLLMDelegationDispatcher(agent_config)

    def _route_to_supervisor(state: AgentState) -> str:
        """Cheap pre-filter on the route→{supervisor|direct} fork (OBP-4, pure).

        Returns "supervisor" ONLY when the flag is on AND the task looks like a
        fan-out candidate (planning_depth >= L1 AND the T1 plan has >= 2 steps).
        The REAL decline decision happens in the supervisor component; this is
        only the cheap gate that keeps every non-candidate (and all of prod,
        flag-off) on the byte-identical "direct" → call_llm path.
        """
        if not agent_config.t3_fanout_enabled:
            return "direct"
        if state.get("planning_depth", "L0") == "L0":
            return "direct"
        plan_raw = state.get("plan_artifact") or {}
        steps = plan_raw.get("ordered_steps") or []
        return "supervisor" if len(steps) >= 2 else "direct"

    async def supervisor_node(state: AgentState, config: RunnableConfig) -> dict:
        """OBP-3: classify the existing T1 plan as fan_out|decline, no execution.

        Holds NO decompose logic — it calls ``plan_delegations`` (the pure
        component) with an injected LLM ``generate`` callable, then stashes the
        resulting SupervisorPlan on a transient state key for ``_route_fanout``
        to read. Emits one decision carrier (fan_out|decline + reason tag,
        joinable by ``decision_id``). Re-runnable on reflexion re-entry.
        """
        task_input = state.get("task_input", "")
        plan_artifact = state.get("plan_artifact") or {}
        planning_depth = state.get("planning_depth", "L0") or "L0"
        # Governance Recording: capture the decompose LLM call's usage so a
        # STEP_EXECUTED carrier is emitted below (the fan-out path bypasses
        # call_llm). Stays None when the run does not consult the LLM (decline
        # floor) — no LLM call means no token carrier, correctly.
        _sup_usage: dict | None = None

        async def _decompose(prompt: str) -> dict:
            nonlocal _sup_usage
            plan_steps = [
                str(s.get("goal", ""))
                for s in (plan_artifact.get("ordered_steps") or [])
                if isinstance(s, dict)
            ]
            system = prompt_service.render_prompt(
                "supervisor_decompose", plan_steps=plan_steps
            )
            profile = llm_service.get_profile(agent_config.default_model)
            response = await llm_service.invoke(
                profile,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            _usage = getattr(response, "usage_metadata", {}) or {}
            _ti = int(_usage.get("input_tokens", 0) or 0)
            _to = int(_usage.get("output_tokens", 0) or 0)
            _sup_usage = {
                "model": profile.name,
                "tokens_in": _ti,
                "tokens_out": _to,
                "cost_usd": (_ti * profile.cost_per_1k_input / 1000)
                + (_to * profile.cost_per_1k_output / 1000),
            }
            content = str(getattr(response, "content", response) or "")
            try:
                return json.loads(content)
            except Exception:
                return {}

        # Only consult the decompose LLM when the run is allowed to (same
        # shadow-first discipline as plan_source); otherwise the component's
        # deterministic floor declines (no-generator).
        generate = None
        if agent_config.plan_source in ("generated",):
            decomposed: dict = {}

            def _sync_generate(prompt: str, _box=decomposed) -> dict:
                return _box

            decomposed.update(await _decompose(task_input))
            generate = _sync_generate

        plan = plan_delegations(
            task_input=task_input,
            plan_artifact=plan_artifact,
            planning_depth=planning_depth,  # type: ignore[arg-type]
            generate=generate,
        )

        # Reasoning pillar (E7 idiom): log the fan_out|decline choice to the
        # PhaseLogger decisions sink AND mirror it on the black_box step.planned
        # carrier, joined by decision_id — "same data, two sinks" (mirrors the
        # MODEL_SELECTED pattern in call_llm). PhaseLogger assigns decision_id.
        supervisor_decision = phase_logger.log_decision(
            state.get("workflow_id", ""),
            Decision(
                phase=WorkflowPhase.ROUTING,
                description=f"supervisor: {plan.decision}",
                alternatives=["fan_out", "decline"],
                rationale=plan.reason,
                confidence=1.0 if plan.decision == "decline" else 0.9,
            ),
        )
        decision_id = supervisor_decision.decision_id or str(uuid.uuid4())
        black_box.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=state.get("workflow_id", ""),
            event_type=EventType.STEP_PLANNED,
            timestamp=datetime.now(UTC),
            step=state.get("step_count", 0),
            details={
                "supervisor_decision": plan.decision,
                "supervisor_reason": plan.reason,
                "supervisor_branch_count": len(plan.branches),
                "decision_id": decision_id,
            },
        ))

        # Governance Recording: STEP_EXECUTED for the decompose LLM call (only
        # when the LLM was actually consulted; the decline floor makes no call).
        if _sup_usage is not None:
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=state.get("workflow_id", ""),
                event_type=EventType.STEP_EXECUTED,
                timestamp=datetime.now(UTC),
                step=state.get("step_count", 0),
                details={
                    **_sup_usage,
                    "latency_ms": 0.0,
                    "source": "fanout_supervisor",
                    "decision_id": decision_id,
                    "error": None,
                },
            ))

        return {
            "fanout_decision": {
                "decision": plan.decision,
                "decision_id": decision_id,
                "branches": [b.model_dump() for b in plan.branches],
                "reason": plan.reason,
            }
        }

    def _route_fanout(state: AgentState):
        """Conditional edge: fan out via Send per branch, or fall to call_llm.

        Returning a ``list[Send]`` is the LangGraph parallel-superstep idiom —
        each Send carries a SMALL plain-dict payload (mapping onto
        DelegationDispatchRequest), NEVER AgentState (OBP-M1).
        """
        sup = state.get("fanout_decision") or {}
        if sup.get("decision") != "fan_out":
            return "call_llm"
        workflow_id = state.get("workflow_id", "")
        step_count = state.get("step_count", 0)
        sends = []
        for branch in sup.get("branches", []):
            bid = branch.get("branch_id")
            sends.append(Send("worker", {
                "branch_id": bid,
                "correlation_id": f"{workflow_id}:step:{step_count}:fanout:{bid}",
                "workflow_id": workflow_id,
                "step_count": step_count,
                "objective": branch.get("objective", ""),
                "subagent_type": branch.get("subagent_type", "general"),
                "constraints": branch.get("constraints", []),
                "expected_output_schema": branch.get("expected_output_schema", {}),
                "task_id": state.get("task_id", ""),
                "user_id": state.get("user_id", "anonymous"),
                "decision_id": sup.get("decision_id", ""),
            }))
        return sends or "call_llm"

    async def worker_node(state: dict, config: RunnableConfig) -> dict:
        """OBP-3 + OBP-M1: run ONE branch, append a result/sentinel.

        The Send payload arrives as ``state`` here (LangGraph passes the Send
        payload as the node input). MANDATORY try/except + per-branch
        ``asyncio.wait_for``: the dispatcher RE-RAISES on LLM failure, and one
        uncaught raise cancels the ENTIRE superstep — so a failure becomes a
        per-branch sentinel, never an erased survivor. Emits per-branch
        delegation_requested / delegation_completed (or delegation_denied)
        carriers with the BRANCH correlation_id (GTP-1), via the same
        trace_service path task_tool uses (no new event names).
        """
        payload = dict(state)
        branch_id = payload.get("branch_id")
        correlation_id = payload.get("correlation_id", "")
        workflow_id = payload.get("workflow_id", "")
        decision_id = payload.get("decision_id", "")

        _emit_delegation_trace(
            workflow_id=workflow_id,
            event_type="delegation_requested",
            outcome="pass",
            details={
                "correlation_id": correlation_id,
                "branch_id": branch_id,
                "subagent_type": payload.get("subagent_type", ""),
                "decision_id": decision_id,
            },
        )

        objective = str(payload.get("objective", ""))
        # Env-gated fault hook (corpus §4.3a) — OFF in prod. The magic objective
        # tokens exercise the timeout / straggler superstep paths.
        timeout_s = float(agent_config.fanout_branch_timeout_s)
        if agent_config.fanout_fault_inject:
            if "__FAULT_TIMEOUT__" in objective:
                timeout_s = 0.001  # force the wait_for timeout path

        request = {
            "correlation_id": correlation_id,
            "workflow_id": workflow_id,
            "step_count": int(payload.get("step_count", 0) or 0),
            "objective": objective or "Complete the delegated branch.",
            "subagent_type": payload.get("subagent_type", "general") or "general",
            "constraints": payload.get("constraints", []),
            "expected_output_schema": payload.get("expected_output_schema", {}),
            "task_id": payload.get("task_id", ""),
            "user_id": payload.get("user_id", "anonymous"),
        }

        try:
            if agent_config.fanout_fault_inject and "__FAULT_SLOW__" in objective:
                await asyncio.sleep(timeout_s + 1.0)  # straggler past the ceiling
            result = await asyncio.wait_for(
                _fanout_dispatcher.dispatch_async(request), timeout=timeout_s
            )
            entry = {
                "branch_id": branch_id,
                "status": result.get("status", "completed"),
                "output": result.get("output", ""),
                "error": result.get("error"),
                "correlation_id": correlation_id,
            }
            # Governance Recording pillar: one STEP_EXECUTED per branch carries
            # the worker LLM call's tokens/cost. The fan-out path bypasses
            # call_llm (the only other STEP_EXECUTED site), so without this each
            # branch's cost is invisible in the governance trace.
            _usage = result.get("usage") or {}
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.STEP_EXECUTED,
                timestamp=datetime.now(UTC),
                step=int(payload.get("step_count", 0) or 0),
                details={
                    "model": _usage.get("model", ""),
                    "tokens_in": int(_usage.get("tokens_in", 0) or 0),
                    "tokens_out": int(_usage.get("tokens_out", 0) or 0),
                    "cost_usd": float(_usage.get("cost_usd", 0.0) or 0.0),
                    "latency_ms": float(_usage.get("latency_ms", 0.0) or 0.0),
                    "source": "fanout_worker",
                    "branch_id": branch_id,
                    "decision_id": decision_id,
                    "error": None,
                },
            ))
            _emit_delegation_trace(
                workflow_id=workflow_id,
                event_type="delegation_completed",
                outcome="pass" if not entry["error"] else "alert",
                details={
                    "correlation_id": correlation_id,
                    "branch_id": branch_id,
                    "status": entry["status"],
                    "decision_id": decision_id,
                },
            )
        except (asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001 — sentinel
            # The survivors must not be erased; record a sentinel + an error
            # carrier (never a silent drop — Validation pillar / GTP).
            kind = "timeout" if isinstance(exc, asyncio.TimeoutError) else "error"
            entry = {
                "branch_id": branch_id,
                "status": "failed",
                "output": "",
                "error": f"{kind}: {exc}" if str(exc) else kind,
                "correlation_id": correlation_id,
            }
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.ERROR_OCCURRED,
                timestamp=datetime.now(UTC),
                step=int(payload.get("step_count", 0) or 0),
                details={
                    "source": "fanout_worker",
                    "branch_id": branch_id,
                    "error": entry["error"],
                    "decision_id": decision_id,
                },
            ))
            _emit_delegation_trace(
                workflow_id=workflow_id,
                event_type="delegation_completed",
                outcome="alert",
                details={
                    "correlation_id": correlation_id,
                    "branch_id": branch_id,
                    "status": "failed",
                    "decision_id": decision_id,
                },
            )

        return {"worker_results": [entry]}

    async def join_node(state: AgentState, config: RunnableConfig) -> dict:
        """OBP-3 + GTP-3: synthesize the merged worker_results into ONE answer.

        Edges to ``evaluate`` so GoalJudge scores the JOINED answer, never a
        fragment (the corrupt-success guard). A degraded join (some branches
        failed) is still a non-empty answer — the judge runs, and the partial
        is surfaced honestly by the prompt.
        """
        results = list(state.get("worker_results") or [])
        results.sort(key=lambda r: r.get("branch_id", 0))
        task_input = state.get("task_input", "")

        completed = [r for r in results if r.get("status") == "completed"]
        joined = ""
        # Governance Recording: capture the join LLM call's usage so a
        # STEP_EXECUTED carrier is emitted below. None when the join falls to the
        # deterministic floor (no LLM call) — correctly no token carrier then.
        _join_usage: dict | None = None
        if completed:
            try:
                prompt = prompt_service.render_prompt(
                    "fanout_join", task_input=task_input, results=results
                )
                profile = llm_service.get_profile(agent_config.default_model)
                response = await llm_service.invoke(
                    profile,
                    [{"role": "user", "content": prompt}],
                )
                joined = str(getattr(response, "content", response) or "").strip()
                _u = getattr(response, "usage_metadata", {}) or {}
                _ti = int(_u.get("input_tokens", 0) or 0)
                _to = int(_u.get("output_tokens", 0) or 0)
                _join_usage = {
                    "model": profile.name,
                    "tokens_in": _ti,
                    "tokens_out": _to,
                    "cost_usd": (_ti * profile.cost_per_1k_input / 1000)
                    + (_to * profile.cost_per_1k_output / 1000),
                }
            except Exception:
                joined = ""
        if not joined:
            # Deterministic floor: concat the survivors + note the gaps, so the
            # judge ALWAYS sees a non-empty joined answer (MAST-bounded).
            parts = [
                f"- {r.get('output', '')}" for r in completed if r.get("output")
            ]
            gaps = [
                f"- branch {r.get('branch_id')} did not complete ({r.get('error')})"
                for r in results
                if r.get("status") != "completed"
            ]
            joined = "\n".join(parts) or "No branch produced a result."
            if gaps:
                joined += "\n\nIncomplete branches:\n" + "\n".join(gaps)

        black_box.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=state.get("workflow_id", ""),
            event_type=EventType.STEP_PLANNED,
            timestamp=datetime.now(UTC),
            step=state.get("step_count", 0),
            details={
                "fanout_join": True,
                "branches_total": len(results),
                "branches_completed": len(completed),
                "join_chars": len(joined),
            },
        ))

        # Governance Recording: STEP_EXECUTED for the join LLM call (only when
        # the synthesis LLM was actually called; the floor makes no call).
        if _join_usage is not None:
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=state.get("workflow_id", ""),
                event_type=EventType.STEP_EXECUTED,
                timestamp=datetime.now(UTC),
                step=state.get("step_count", 0),
                details={
                    **_join_usage,
                    "latency_ms": 0.0,
                    "source": "fanout_join",
                    "error": None,
                },
            ))

        return {
            "messages": [AIMessage(content=joined)],
            "last_final_answer": joined,
        }

    builder = StateGraph(AgentState)

    builder.add_node("guard_input", guard_input_node)
    builder.add_node("route", route_node)
    builder.add_node("call_llm", call_llm_node)
    builder.add_node("execute_tool", execute_tool_node)
    builder.add_node("evaluate", evaluate_node)

    # F10 Tier-2: post-loop cheap recap; runs once on the "done" branch so
    # the summary is on the stream before RUN_FINISHED (eval captures are
    # settled). Budget-exceeded runs end at call_llm and skip it.
    async def reasoning_recap_node(state: AgentState, config: RunnableConfig) -> dict:
        return await _reasoning_recap_impl(
            dict(state),
            llm_service=llm_service,
            prompt_service=prompt_service,
            agent_config=agent_config,
        )

    builder.add_node("reasoning_recap", reasoning_recap_node)
    # Phase 2 (T2): the reflexion re-entry node. Edge wired below the evaluate
    # fork. Always added so the graph shape is stable; the routing predicate
    # gates whether it is ever reached (off unless reflexion_enabled).
    builder.add_node("reflect", reflect_node)
    # Phase 4 (T3): supervisor/worker/join nodes. Always added so the graph shape
    # is stable; the _route_to_supervisor predicate (and t3_fanout_enabled) gate
    # whether they are ever reached (off → byte-identical to the pre-T3 spine).
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("worker", worker_node)
    builder.add_node("join", join_node)

    builder.add_edge(START, "guard_input")

    # Story 1.2: conditional edge for guard rejection
    builder.add_conditional_edges(
        "guard_input",
        _guard_routing,
        {"accepted": "route", "rejected": END},
    )

    # Phase 4 (T3): the one invasive edit — the hard route→call_llm edge becomes
    # conditional so route can fork to the supervisor. When t3_fanout_enabled is
    # OFF, _route_to_supervisor always returns "direct" → this is byte-identical
    # to the old hard edge for every task (the regression canary is the Step 7
    # "decline → identical-to-today" topology sim).
    builder.add_conditional_edges(
        "route",
        _route_to_supervisor,
        {"supervisor": "supervisor", "direct": "call_llm"},
    )
    # supervisor → fan out via Send per branch, or decline to call_llm.
    builder.add_conditional_edges(
        "supervisor",
        _route_fanout,
        ["worker", "call_llm"],
    )
    builder.add_edge("worker", "join")
    # join → evaluate so GoalJudge scores the JOINED answer (corrupt-success
    # guard); a failed join re-enters reflexion exactly like any terminal turn.
    builder.add_edge("join", "evaluate")

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
        _should_continue_or_escalate,
        {
            "continue": "route",
            "reflect": "reflect",  # Phase 2: failed/partial+budget, or D3 prose thrash
            "done": "reasoning_recap",
        },
    )
    # Phase 2: re-enter the loop through shared state — the appended critique is
    # folded into the system prompt on the next call_llm pass.
    builder.add_edge("reflect", "route")
    builder.add_edge("reasoning_recap", END)

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
