"""Langfuse-backed EvalTelemetrySink — E1 eval.goal_judge observations."""

from __future__ import annotations

import logging
from typing import Any

from middleware.ports.telemetry_exporter import TelemetryExporter
from services.eval_telemetry import observation_name_for_target, serialize_ai_response

logger = logging.getLogger("middleware.adapters.observability")


class LangfuseEvalTelemetrySink:
    """Maps goal_judge eval_capture rows to Langfuse observations."""

    def __init__(self, exporter: TelemetryExporter) -> None:
        self._exporter = exporter

    def publish_goal_judge(
        self,
        *,
        trace_id: str,
        user_id: str,
        task_id: str,
        ai_input: dict[str, Any],
        ai_response: dict[str, Any],
        step: int,
        model: str | None,
    ) -> None:
        try:
            self._exporter.export_event(
                name=observation_name_for_target("goal_judge"),
                trace_id=trace_id,
                attributes={
                    "target": "goal_judge",
                    "task_id": task_id,
                    "user_id": user_id,
                    "step": step,
                    "model": model or "",
                    "subject": user_id,
                    "task_input": ai_input.get("task_input", ""),
                    "success_conditions": ai_input.get("success_conditions", []),
                    # Stage 4 Phase E.1 (Tier 2) — audit-trail fields the judge saw.
                    "final_answer": ai_input.get("final_answer", ""),
                    "evidence_digest": ai_input.get("evidence_digest", ""),
                    "tool_calls_summary": ai_input.get("tool_calls_summary", []),
                    "plan_steps": ai_input.get("plan_steps", 0),
                    # Stage 5 Tier 3 Phase 2.5 — pipeline-dimension labels.
                    # D1, D3, D4, D6 from the Tier 3 assembly plan §"The
                    # pipeline dimension space". Surfacing them as first-class
                    # Langfuse attributes lets Stage 6 slice judge metrics by
                    # dimension without joining other traces.
                    "planning_depth": ai_input.get("planning_depth", ""),
                    "routing_reason": ai_input.get("routing_reason", ""),
                    "model_tier": ai_input.get("model_tier", ""),
                    "cost_fraction": ai_input.get("cost_fraction", 0.0),
                    # task_understanding plan §4.7 — stratify verdicts by
                    # condition provenance without trace re-joins.
                    "conditions_source": ai_input.get("conditions_source", ""),
                    "restated_intent": ai_input.get("restated_intent", ""),
                    "__output": serialize_ai_response(ai_response),
                    "__bb_observation_type": "evaluator",
                },
            )
        except Exception:
            logger.warning(
                "LangfuseEvalTelemetrySink.publish_goal_judge failed (swallowed)",
                exc_info=True,
            )

    def publish_task_understanding(
        self,
        *,
        trace_id: str,
        user_id: str,
        task_id: str,
        ai_input: dict[str, Any],
        ai_response: dict[str, Any],
        step: int,
        model: str | None,
    ) -> None:
        """task_understanding plan §4.7 — eval.task_understanding observation."""
        try:
            self._exporter.export_event(
                name=observation_name_for_target("task_understanding"),
                trace_id=trace_id,
                attributes={
                    "target": "task_understanding",
                    "task_id": task_id,
                    "user_id": user_id,
                    "step": step,
                    "model": model or "",
                    "subject": user_id,
                    "task_input": ai_input.get("task_input", ""),
                    "conditions_source": ai_response.get("source", ""),
                    "fallback_reason": ai_response.get("fallback_reason", ""),
                    "__output": serialize_ai_response(ai_response),
                    "__bb_observation_type": "evaluator",
                },
            )
        except Exception:
            logger.warning(
                "LangfuseEvalTelemetrySink.publish_task_understanding failed (swallowed)",
                exc_info=True,
            )
