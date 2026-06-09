"""Optional telemetry sink for eval_capture records (E1).

Orchestration calls ``publish_goal_judge`` after ``eval_capture.record`` so
full GoalJudge verdict axes reach Langfuse on the same ``trace_id``. The
middleware composition root registers a sink backed by ``TelemetryExporter``;
when no sink is registered (unit tests, bare CLI), publishing is a no-op.

Layering: this module lives in ``services/`` — no Langfuse SDK, no middleware
imports. Redaction reuses ``black_box_publisher.redact_text``.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol, runtime_checkable

from services.governance.black_box_publisher import redact_text

logger = logging.getLogger("services.eval_telemetry")

_EVAL_OBSERVATION_NAME = "eval.goal_judge"


@runtime_checkable
class EvalTelemetrySink(Protocol):
    """Port for exporting eval records to observability backends."""

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
        """Emit one goal_judge eval record. MUST NOT raise (O1)."""
        ...


_sink: EvalTelemetrySink | None = None


def set_sink(sink: EvalTelemetrySink | None) -> None:
    """Register or clear the global eval telemetry sink (composition root)."""
    global _sink
    _sink = sink


def get_sink() -> EvalTelemetrySink | None:
    return _sink


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _redact_value(v) for k, v in value.items()}
    return value


def _redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    return {str(k): _redact_value(v) for k, v in data.items()}


async def publish_goal_judge(
    *,
    trace_id: str,
    user_id: str,
    task_id: str,
    ai_input: dict[str, Any],
    ai_response: dict[str, Any],
    step: int,
    model: str | None,
) -> None:
    """Publish a goal_judge eval record when a sink is registered."""
    if _sink is None:
        return
    try:
        _sink.publish_goal_judge(
            trace_id=trace_id,
            user_id=user_id,
            task_id=task_id,
            ai_input=_redact_mapping(ai_input),
            ai_response=_redact_mapping(ai_response),
            step=step,
            model=model,
        )
    except Exception:
        logger.warning(
            "eval telemetry publish failed (swallowed)",
            exc_info=True,
        )


def observation_name_for_target(target: str) -> str:
    """Stable Langfuse observation name for an eval_capture target."""
    if target == "goal_judge":
        return _EVAL_OBSERVATION_NAME
    return f"eval.{target}"


def serialize_ai_response(ai_response: dict[str, Any]) -> dict[str, Any]:
    """JSON-safe copy for Langfuse output payloads."""
    return json.loads(json.dumps(ai_response, default=str))
