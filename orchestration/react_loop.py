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

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from components.evaluator import (
    build_step_result,
    check_continuation,
    classify_outcome,
    parse_llm_response,
)
from components.router import select_model
from components.routing_config import RoutingConfig
from orchestration.state import AgentState
from services.base_config import AgentConfig, ModelProfile, default_fast_profile
from services.governance.agent_facts_registry import AgentFactsRegistry
from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent
from services.governance.guardrail_validator import (
    GuardRailValidator,
    api_key_rules,
    pii_rules,
)
from services.governance.phase_logger import Decision, PhaseLogger, WorkflowPhase
from services.guardrails import InputGuardrail, output_guardrail_scan
from services.llm_config import LLMService
from services.observability import FrameworkTelemetry, InstrumentedCheckpointer
from services.prompt_service import PromptService
from services.tools.registry import ToolRegistry

logger = logging.getLogger("orchestration.react_loop")


def _compute_tool_cache_key(tool_name: str, tool_args: dict[str, Any]) -> str:
    """Deterministic cache key from tool_name + sorted-JSON of args."""
    digest = hashlib.md5(json.dumps(tool_args, sort_keys=True).encode()).hexdigest()
    return f"{tool_name}:{digest}"


def _execute_tools_impl(
    state: dict[str, Any],
    *,
    tool_registry: ToolRegistry,
    black_box: BlackBoxRecorder,
) -> dict[str, Any]:
    """Pure-ish executor for tool calls with cache-aware dispatch.

    Contract: reads ``state['tool_cache']``, returns a dict with ``messages``
    (ToolMessage list), ``tool_cache`` (updated), and ``current_workflow_phase``.
    Cache hits skip registry dispatch and emit TOOL_CALLED with cached=True.
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

    for tc in tool_calls:
        tool_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
        tool_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
        tool_id = tc.get("id", str(uuid.uuid4())) if isinstance(tc, dict) else getattr(tc, "id", str(uuid.uuid4()))

        cache_key = _compute_tool_cache_key(tool_name, tool_args)
        cacheable = tool_registry.has(tool_name) and tool_registry.is_cacheable(tool_name)

        if cacheable and cache_key in updated_cache:
            output = updated_cache[cache_key]
            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.TOOL_CALLED,
                timestamp=datetime.now(UTC),
                step=state.get("step_count", 0),
                details={"tool": tool_name, "args": tool_args, "cached": True},
            ))
            results.append(ToolMessage(content=output, tool_call_id=tool_id))
            continue

        try:
            output = tool_registry.execute(tool_name, tool_args)
        except KeyError:
            output = f"Error: Unknown tool '{tool_name}'"
        except Exception as exc:
            output = f"Error: Tool '{tool_name}' failed: {exc}"

        black_box.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.TOOL_CALLED,
            timestamp=datetime.now(UTC),
            step=state.get("step_count", 0),
            details={"tool": tool_name, "args": tool_args, "cached": False},
        ))

        if cacheable:
            updated_cache[cache_key] = output

        results.append(ToolMessage(content=output, tool_call_id=tool_id))

    return {
        "messages": results,
        "tool_cache": updated_cache,
        "current_workflow_phase": WorkflowPhase.TOOL_EXECUTION.value,
    }


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
    )
    output_validator = GuardRailValidator(pii_rules() + api_key_rules())

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
        if agent_facts_registry is not None:
            registered_agent_id = (
                config.get("configurable", {}).get("registered_agent_id")
                or state.get("registered_agent_id", "")
            )
            if registered_agent_id:
                agent_facts_verified = agent_facts_registry.verify(registered_agent_id)
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
                    return {
                        "agent_facts_verified": False,
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
            return {
                "agent_facts_verified": agent_facts_verified,
                "last_outcome": "rejected",
                "current_workflow_phase": WorkflowPhase.INPUT_VALIDATION.value,
            }

        return {
            "agent_facts_verified": agent_facts_verified,
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
            details={"model": profile.name, "reason": reason},
        ))

        return {
            "selected_model": profile.name,
            "routing_reason": reason,
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
            additional_instructions="",
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

        start_time = time.time()
        error: Exception | None = None
        try:
            # Story 1.1: use invoke_with_tools for tool binding
            response = await llm_service.invoke_with_tools(
                profile,
                lc_messages,
                tool_schemas=tool_schemas or None,
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
            "current_workflow_phase": WorkflowPhase.MODEL_INVOCATION.value,
        }
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
        )
        return result

    # ── verify_authorize_log_node: per-tool-call PEP (opt-in) ──

    async def verify_authorize_log_node(state: AgentState, config: RunnableConfig) -> dict:
        """Per-action PEP per FOUR_LAYER_ARCHITECTURE.md §verify_authorize_log_node.

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
        result = check_continuation(
            step_count=state.get("step_count", 0),
            total_cost_usd=state.get("total_cost_usd", 0.0),
            last_outcome=state.get("last_outcome", ""),
            last_error_type=state.get("last_error_type", None),
            agent_config=agent_config,
            backoff_until=state.get("backoff_until"),
        )
        return "continue" if result == "continue" else "done"

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
        if telemetry is not None:
            checkpointer = InstrumentedCheckpointer(checkpointer, telemetry)
        compile_kwargs["checkpointer"] = checkpointer
        compile_kwargs["interrupt_before"] = ["execute_tool"]

    return builder.compile(**compile_kwargs)
