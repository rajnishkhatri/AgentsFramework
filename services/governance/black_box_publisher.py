"""BlackBoxPublisher: pure mapping from BlackBox TraceEvent to Langfuse export kwargs.

Sprint A of the BlackBox→Langfuse plan.

This module contains ZERO SDK imports. It lives in the services layer and is
consumed by the relay sidecar (middleware layer) which calls the
TelemetryExporter port.

Invariants enforced by tests/services/governance/test_black_box_publisher.py
and tests/architecture/test_middleware_layer.py:
  - No ``langfuse`` imports.
  - No ``langgraph`` / ``langchain`` imports.
  - All 9 EventTypes produce a valid mapping.
  - PII and API keys are redacted before leaving this module.
  - Detail values are capped at 200 characters.
"""

from __future__ import annotations

import re
from typing import Any

from services.governance.black_box import EventType, TraceEvent
from services.governance.guardrail_validator import (
    GuardRailValidator,
    api_key_rules,
    pii_rules,
)

__all__ = ["to_export_kwargs", "redact_details"]

_MAX_DETAIL_VALUE_LEN = 200

_SAFE_NUMERIC_KEYS: frozenset[str] = frozenset({
    "latency_ms",
    "cost_usd",
    "total_cost_usd",
    "tokens_in",
    "tokens_out",
    "step_count",
    "step",
    "input_tokens",
    "output_tokens",
    "budget_limit",
    "total_tokens",
})

_EVENT_TYPE_TO_OBSERVATION: dict[EventType, tuple[str, str]] = {
    EventType.TASK_STARTED: ("agent", "task.started"),
    EventType.TASK_COMPLETED: ("agent", "task.completed"),
    EventType.STEP_PLANNED: ("chain", "step.planned"),
    EventType.STEP_EXECUTED: ("span", "step.executed"),
    EventType.TOOL_CALLED: ("tool", "tool.called"),
    EventType.MODEL_SELECTED: ("generation", "model.selected"),
    EventType.GUARDRAIL_CHECKED: ("guardrail", "guardrail.checked"),
    EventType.PARAMETER_CHANGED: ("span", "parameter.changed"),
    EventType.ERROR_OCCURRED: ("span", "error.occurred"),
}

# Pre-compile redaction patterns from the guardrail rule factories.
# We only use the REDACT-action rules plus all rules (API keys are BLOCK
# but we redact them here rather than blocking the export).
_REDACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = []

for _rule in pii_rules() + api_key_rules():
    _REDACTION_PATTERNS.append(
        (re.compile(_rule.pattern, _rule.flags), _rule.match_redaction)
    )


def redact_details(details: dict[str, Any]) -> dict[str, str]:
    """Redact PII, API keys, and truncate values to ``_MAX_DETAIL_VALUE_LEN``.

    Every value is coerced to ``str`` before processing so the relay can
    safely serialize the result without type surprises.

    Known-safe numeric keys (latency_ms, cost_usd, tokens_in, etc.) are
    exempt from regex redaction to prevent false-positive corruption of
    telemetry data by the credit-card pattern.

    Processing order: coerce → truncate → redact.  Truncation before
    redaction ensures that a long string ending with PII gets capped first
    (the PII may be cut off by truncation, which is acceptable — it's
    better to lose the tail than to leak secrets).
    """
    result: dict[str, str] = {}
    for key, value in details.items():
        text = str(value)

        if len(text) > _MAX_DETAIL_VALUE_LEN:
            text = text[:_MAX_DETAIL_VALUE_LEN]

        if key not in _SAFE_NUMERIC_KEYS:
            for pattern, replacement in _REDACTION_PATTERNS:
                text = pattern.sub(replacement, text)

        result[key] = text
    return result


def to_export_kwargs(event: TraceEvent) -> dict[str, Any]:
    """Map a ``TraceEvent`` to keyword arguments for ``TelemetryExporter.export_event``.

    Returns a dict with keys:
      - ``name``: Langfuse observation name (e.g. ``"task.started"``).
      - ``observation_type``: Langfuse observation type (``"agent"``, ``"span"``, etc.).
      - ``trace_id``: equals ``event.workflow_id`` per design decision §2.2.
      - ``observation_id``: equals ``event.event_id`` for idempotent retries.
      - ``level``: ``"ERROR"`` for error events, ``"DEFAULT"`` otherwise.
      - ``attributes``: dict of redacted, truncated event metadata.
      - ``parent_observation_id``: step-span parent for hierarchical nesting (I6).
      - ``model``: native Langfuse model field for GENERATION observations (I5).
      - ``usage``: native Langfuse usage dict for GENERATION observations (I5).
      - ``cost``: native Langfuse cost for GENERATION observations (I5).
    """
    obs_type, name = _EVENT_TYPE_TO_OBSERVATION[event.event_type]

    level = "ERROR" if event.event_type == EventType.ERROR_OCCURRED else "DEFAULT"

    attributes: dict[str, Any] = {
        "event_id": event.event_id,
        "workflow_id": event.workflow_id,
        "step": event.step,
        "timestamp": event.timestamp.isoformat(),
        "integrity_hash": event.integrity_hash,
        "details": redact_details(event.details),
    }

    result: dict[str, Any] = {
        "name": name,
        "observation_type": obs_type,
        "trace_id": event.workflow_id,
        "observation_id": event.event_id,
        "level": level,
        "attributes": attributes,
    }

    # I6: Parent observation hierarchy — step-based nesting.
    # Task-level events (TASK_STARTED, TASK_COMPLETED) are root spans.
    # All other events nest under a synthetic per-step span ID.
    if event.step is not None and event.event_type not in (
        EventType.TASK_STARTED,
        EventType.TASK_COMPLETED,
    ):
        result["parent_observation_id"] = f"{event.workflow_id}:step:{event.step}"

    # I5: Promote native generation fields for GENERATION-typed observations.
    details = event.details
    if obs_type == "generation":
        model_name = details.get("model")
        if model_name:
            result["model"] = model_name

        tokens_in = details.get("tokens_in") or details.get("input_tokens")
        tokens_out = details.get("tokens_out") or details.get("output_tokens")
        if tokens_in is not None or tokens_out is not None:
            result["usage"] = {}
            if tokens_in is not None:
                result["usage"]["input"] = int(tokens_in)
            if tokens_out is not None:
                result["usage"]["output"] = int(tokens_out)
            total = (int(tokens_in or 0)) + (int(tokens_out or 0))
            if total:
                result["usage"]["total"] = total

        cost_usd = details.get("cost_usd")
        if cost_usd is not None:
            result["cost"] = float(cost_usd)

    # For STEP_EXECUTED (span type but carries generation-like data), also promote.
    if event.event_type == EventType.STEP_EXECUTED:
        model_name = details.get("model")
        if model_name:
            result["model"] = model_name

        tokens_in = details.get("tokens_in")
        tokens_out = details.get("tokens_out")
        if tokens_in is not None or tokens_out is not None:
            result["usage"] = {}
            if tokens_in is not None:
                result["usage"]["input"] = int(tokens_in)
            if tokens_out is not None:
                result["usage"]["output"] = int(tokens_out)
            total = (int(tokens_in or 0)) + (int(tokens_out or 0))
            if total:
                result["usage"]["total"] = total

        cost_usd = details.get("cost_usd")
        if cost_usd is not None:
            result["cost"] = float(cost_usd)

    return result
