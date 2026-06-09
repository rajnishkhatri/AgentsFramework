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
                    "final_answer": ai_input.get("final_answer", ""),
                    "evidence_digest": ai_input.get("evidence_digest", ""),
                    "tool_calls_summary": ai_input.get("tool_calls_summary", []),
                    "plan_steps": ai_input.get("plan_steps", 0),
                    "__output": serialize_ai_response(ai_response),
                    "__bb_observation_type": "evaluator",
                },
            )
        except Exception:
            logger.warning(
                "LangfuseEvalTelemetrySink.publish_goal_judge failed (swallowed)",
                exc_info=True,
            )
