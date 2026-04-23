"""Pyramid ReACT graph -- PR 1 walking skeleton.

PR 1 ships a single ``analyze`` node that asks the LLM to produce the
entire ``analysis_output`` JSON in one shot, plus a one-attempt parse
retry. PR 2 will split this into four phase nodes (decompose,
hypothesize, act, synthesize); PR 3 will add the synthesize -> decompose
back-edge driven by ``PyramidConfig.max_iterations``.

This module is the only file in the inner orchestration layer that
imports ``langgraph`` (``pyramid_state.py`` imports ``MessagesState``).
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from services import eval_capture
from services.base_config import AgentConfig, default_fast_profile
from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent
from services.governance.phase_logger import Decision, PhaseLogger, WorkflowPhase
from services.guardrails import InputGuardrail
from services.llm_config import LLMService
from services.prompt_service import PromptService
from services.tools.registry import ToolRegistry

from StructuredReasoning.components.pyramid_parser import (
    ParseError,
    build_retry_prompt,
    parse_analysis_output,
)
from StructuredReasoning.orchestration.pyramid_state import PyramidState
from StructuredReasoning.trust.pyramid_schema import AnalysisOutput

logger = logging.getLogger("StructuredReasoning.orchestration.pyramid_loop")

PYRAMID_SYSTEM_PROMPT = "StructuredReasoning/PyramidAgent_system_prompt"


def _tool_descriptions(tool_registry: ToolRegistry | None) -> list[dict[str, str]]:
    """Render the registered tools as a list the system prompt can iterate over."""
    if tool_registry is None:
        return []
    descriptions: list[dict[str, str]] = []
    for schema in tool_registry.get_schemas():
        descriptions.append({
            "name": schema["name"],
            "description": schema.get("description", "") or "(no description)",
        })
    return descriptions


def build_pyramid_graph(
    agent_config: AgentConfig,
    *,
    tool_registry: ToolRegistry | None = None,
    cache_dir: Path | str = Path("cache"),
    max_iterations: int = 3,
    checkpointer: Any | None = None,
) -> Any:
    """Build and compile the PR 1 walking-skeleton pyramid graph.

    The compiled graph runs:

        START -> guard_input -> analyze -> persist -> END

    ``analyze`` issues a single LLM call asking for the entire
    ``analysis_output`` JSON object. If parsing fails, ``analyze``
    issues exactly one retry with a corrective follow-up message before
    surfacing the failure in ``state['parse_error']`` and routing to
    persist.

    ``tool_registry`` is accepted for API parity with the outer
    ``orchestration.react_loop.build_graph``. PR 1 does not invoke tools
    -- only their names + descriptions are surfaced to the LLM via the
    system prompt's ``Available tools`` block. Pure-reasoning mode is
    selected by passing ``tool_registry=None`` (or an empty registry).
    """
    cache_dir = Path(cache_dir)

    llm_service = LLMService(config=agent_config)
    prompt_service = PromptService()
    black_box = BlackBoxRecorder(storage_dir=cache_dir / "pyramid" / "black_box_recordings")
    phase_logger = PhaseLogger(storage_dir=cache_dir / "pyramid" / "phase_logs")
    guardrail = InputGuardrail(
        name="pyramid_input",
        accept_condition="The input is a legitimate analysis problem statement",
        llm_service=llm_service,
        prompt_service=prompt_service,
        judge_profile=default_fast_profile(),
    )

    available_tool_descriptions = _tool_descriptions(tool_registry)

    def _render_system_prompt(*, iteration_count: int) -> str:
        return prompt_service.render_prompt(
            PYRAMID_SYSTEM_PROMPT,
            available_tools=available_tool_descriptions,
            max_iterations=max_iterations,
            iteration_count=iteration_count,
            prior_gaps="",
        )

    async def guard_input_node(state: PyramidState, config: RunnableConfig) -> dict:
        workflow_id = state.get("workflow_id", "")
        task_input = state.get("task_input", "")

        black_box.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.TASK_STARTED,
            timestamp=datetime.now(UTC),
            details={"task_input": task_input[:200], "agent": "pyramid"},
        ))

        try:
            accepted = await guardrail.is_acceptable(task_input)
        except Exception:
            accepted = True

        black_box.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.GUARDRAIL_CHECKED,
            timestamp=datetime.now(UTC),
            details={"accepted": accepted, "guardrail": "pyramid_input"},
        ))

        await eval_capture.record(
            target="pyramid_guardrail",
            ai_input={"prompt": task_input[:200]},
            ai_response={"accepted": accepted},
            config=config,
        )

        if not accepted:
            return {
                "last_outcome": "rejected",
                "iteration_count": 1,
                "max_iterations": max_iterations,
            }

        return {
            "last_outcome": "",
            "iteration_count": 1,
            "max_iterations": max_iterations,
        }

    def _guard_routing(state: PyramidState) -> str:
        return "rejected" if state.get("last_outcome") == "rejected" else "accepted"

    async def _invoke_llm(messages: list[Any], config: RunnableConfig, *, step: int) -> tuple[str, dict[str, Any]]:
        profile = llm_service.get_default_profile()
        start = time.time()
        response = await llm_service.invoke_with_tools(profile, messages, tool_schemas=None)
        latency_ms = (time.time() - start) * 1000

        usage = getattr(response, "usage_metadata", {}) or {}
        tokens_in = int(usage.get("input_tokens", 0))
        tokens_out = int(usage.get("output_tokens", 0))
        cost = (
            tokens_in * profile.cost_per_1k_input / 1000
            + tokens_out * profile.cost_per_1k_output / 1000
        )
        content = getattr(response, "content", "") or ""

        await eval_capture.record(
            target="pyramid_analyze",
            ai_input={"messages_len": len(messages)},
            ai_response=str(content)[:500],
            config=config,
            step=step,
            model=profile.name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            latency_ms=latency_ms,
        )

        return str(content), {
            "model": profile.name,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": cost,
            "latency_ms": latency_ms,
        }

    async def analyze_node(state: PyramidState, config: RunnableConfig) -> dict:
        workflow_id = state.get("workflow_id", "")
        iteration = state.get("iteration_count", 1) or 1
        system_prompt = _render_system_prompt(iteration_count=iteration)

        messages: list[Any] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=state.get("task_input", "")),
        ]

        total_cost = 0.0
        total_in = 0
        total_out = 0

        content, metrics = await _invoke_llm(messages, config, step=0)
        total_cost += metrics["cost_usd"]
        total_in += metrics["tokens_in"]
        total_out += metrics["tokens_out"]

        black_box.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.STEP_EXECUTED,
            timestamp=datetime.now(UTC),
            step=0,
            details={
                "node": "analyze",
                "attempt": 1,
                **metrics,
            },
        ))

        analysis: AnalysisOutput | None = None
        parse_error_msg = ""
        try:
            analysis = parse_analysis_output(content)
        except ParseError as exc:
            parse_error_msg = str(exc)
            messages.extend([
                AIMessage(content=content),
                HumanMessage(content=build_retry_prompt(exc)),
            ])
            retry_content, retry_metrics = await _invoke_llm(messages, config, step=1)
            total_cost += retry_metrics["cost_usd"]
            total_in += retry_metrics["tokens_in"]
            total_out += retry_metrics["tokens_out"]

            black_box.record(TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                event_type=EventType.STEP_EXECUTED,
                timestamp=datetime.now(UTC),
                step=1,
                details={
                    "node": "analyze",
                    "attempt": 2,
                    "parse_error": parse_error_msg,
                    **retry_metrics,
                },
            ))

            try:
                analysis = parse_analysis_output(retry_content)
                parse_error_msg = ""
            except ParseError as retry_exc:
                parse_error_msg = str(retry_exc)
                analysis = None

        outcome = "done" if analysis is not None else "parse_failed"
        decision = Decision(
            phase=WorkflowPhase.MODEL_INVOCATION,
            description=f"pyramid analyze outcome={outcome}",
            alternatives=["done", "parse_failed"],
            rationale=parse_error_msg or "single-shot analysis_output produced",
            confidence=0.9 if analysis is not None else 0.4,
        )
        phase_logger.log_decision(workflow_id, decision)

        result: dict[str, Any] = {
            "last_outcome": outcome,
            "parse_error": parse_error_msg,
            "total_cost_usd": total_cost,
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "phase_log": [{
                "phase": "analyze",
                "outcome": outcome,
                "model": metrics["model"],
                "iterations": iteration,
            }],
        }
        if analysis is not None:
            result["analysis_output_json"] = analysis.to_dict()
            result["reasoning_trace"] = [
                f"governing_thought: {analysis.governing_thought.statement}"
            ]
        return result

    async def persist_node(state: PyramidState, config: RunnableConfig) -> dict:
        """Write the final analysis_output to ``cache/pyramid/<wf>/analysis.json``.

        Persistence lives in a dedicated node so PR 3's per-iteration
        persistence (``analysis_iter<N>.json`` + ``final.json``) can
        slot in without touching the analyze node.
        """
        from StructuredReasoning.services.pyramid_persistence import write_analysis

        workflow_id = state.get("workflow_id", "")
        outcome = state.get("last_outcome", "")
        analysis_dict = state.get("analysis_output_json", {}) or {}

        if analysis_dict and outcome == "done":
            write_analysis(
                cache_dir=cache_dir,
                workflow_id=workflow_id,
                analysis_dict=analysis_dict,
            )

        black_box.record(TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.TASK_COMPLETED,
            timestamp=datetime.now(UTC),
            details={"outcome": outcome, "persisted": bool(analysis_dict)},
        ))
        return {}

    builder = StateGraph(PyramidState)
    builder.add_node("guard_input", guard_input_node)
    builder.add_node("analyze", analyze_node)
    builder.add_node("persist", persist_node)

    builder.add_edge(START, "guard_input")
    builder.add_conditional_edges(
        "guard_input",
        _guard_routing,
        {"accepted": "analyze", "rejected": END},
    )
    builder.add_edge("analyze", "persist")
    builder.add_edge("persist", END)

    compile_kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
    return builder.compile(**compile_kwargs)
