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
import os
from typing import Any, Protocol, runtime_checkable

from services.governance.black_box_publisher import redact_text

logger = logging.getLogger("services.eval_telemetry")

_EVAL_OBSERVATION_NAME = "eval.goal_judge"

# Phase 0 cap lift (task_understanding plan §5, Stage 6 audit §2): eval.*
# observations are exempt from the publisher's 200-char detail cap — the
# wave-1 corpus lost every judge input past 200 chars. The exemption is a
# larger bound, not unbounded; PII redaction still applies (redact ≠ truncate).
# Applies ONLY to this publish path; BlackBox relay events keep the 200 cap.
_DEFAULT_EVAL_MAX_VALUE_LEN = 8192


def eval_value_max_len() -> int:
    """Per-value char bound for eval.* observation attributes."""
    raw = os.environ.get("EVAL_TELEMETRY_MAX_VALUE_LEN", "")
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_EVAL_MAX_VALUE_LEN
    return value if value > 0 else _DEFAULT_EVAL_MAX_VALUE_LEN


def clip_eval_text(text: str) -> str:
    """Clip eval payload text to the configured bound (replaces ad-hoc slices)."""
    return text[: eval_value_max_len()]


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
        """Emit one task_understanding eval record. MUST NOT raise (O1)."""
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
        return redact_text(value, max_len=eval_value_max_len())
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


async def publish_task_understanding(
    *,
    trace_id: str,
    user_id: str,
    task_id: str,
    ai_input: dict[str, Any],
    ai_response: dict[str, Any],
    step: int,
    model: str | None,
) -> None:
    """Publish a task_understanding eval record when a sink is registered.

    Mirrors ``publish_goal_judge`` (task_understanding plan §4.7): full
    restated_intent + conditions + provenance reach Langfuse uncapped (the
    Phase 0 exemption) while PII redaction still applies.
    """
    if _sink is None:
        return
    publish = getattr(_sink, "publish_task_understanding", None)
    if publish is None:
        return
    try:
        publish(
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
