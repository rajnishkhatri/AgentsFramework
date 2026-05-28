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

    return {
        "name": name,
        "observation_type": obs_type,
        "trace_id": event.workflow_id,
        "observation_id": event.event_id,
        "level": level,
        "attributes": attributes,
    }
