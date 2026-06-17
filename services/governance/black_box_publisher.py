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

__all__ = [
    "to_export_kwargs",
    "redact_details",
    "redact_text",
    "redact_compliance_bundle",
]

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
    # Phase 1 (E4): terminal/judge scores must stay numeric so Langfuse can
    # filter and aggregate them (the reviewed trace carried "criteria_met":
    # "0.0", "task_completion_score": "0.887" as strings — unfilterable).
    "criteria_met",
    "task_completion_score",
    "branch_coverage",
    "cost_fraction",
})

# Phase 1 (E4): boolean governance flags keep native ``bool`` so the trace
# carries true/false, not the strings "True"/"False" (which sort and filter
# wrong, and read as noise). Order-independent; values are passed through
# untouched (a bool is never PII and never oversized).
_SAFE_BOOL_KEYS: frozenset[str] = frozenset({
    "plan_valid",
    "checked",
    "blocked",
    "redacted",
    "goal_met",
    "termination_clean",
    "cached",
    "would_downgrade",
    "plan_changed",
})

_EVENT_TYPE_TO_OBSERVATION: dict[EventType, tuple[str, str]] = {
    EventType.TASK_STARTED: ("agent", "task.started"),
    EventType.TASK_COMPLETED: ("agent", "task.completed"),
    EventType.STEP_PLANNED: ("chain", "step.planned"),
    EventType.STEP_EXECUTED: ("span", "step.executed"),
    EventType.TOOL_CALLED: ("tool", "tool.called"),
    # E5: MODEL_SELECTED is a routing DECISION, not an LLM call — it carries no
    # usage/cost. Typed ``generation`` it polluted generation-level cost/latency
    # analytics and violated "a generation == one model call". The real LLM call
    # is the wire ``llm.call`` generation (Phase 3). Retyped to ``chain``.
    EventType.MODEL_SELECTED: ("chain", "model.selected"),
    EventType.GUARDRAIL_CHECKED: ("guardrail", "guardrail.checked"),
    EventType.PARAMETER_CHANGED: ("span", "parameter.changed"),
    EventType.ERROR_OCCURRED: ("span", "error.occurred"),
    # Phase 1 memory wiring: recall/store are activity events, not LLM
    # generations (no usage/cost) — typed ``span`` like parameter.changed. They
    # enrich the Recording pillar; the relay must export them so the four-pillar
    # audit can read "memory ran" from the trace. details carry user_id/key/count
    # — never content (the redaction pass below keeps the curated view clean).
    EventType.MEMORY_RECALLED: ("span", "memory.recalled"),
    EventType.MEMORY_STORED: ("span", "memory.stored"),
}

# Pre-compile redaction patterns from the guardrail rule factories.
# We only use the REDACT-action rules plus all rules (API keys are BLOCK
# but we redact them here rather than blocking the export).
_REDACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = []

for _rule in pii_rules() + api_key_rules():
    _REDACTION_PATTERNS.append(
        (re.compile(_rule.pattern, _rule.flags), _rule.match_redaction)
    )


def redact_text(text: str, *, max_len: int | None = _MAX_DETAIL_VALUE_LEN) -> str:
    """Apply PII/API-key scrubbing to a free-form string (relay + bridge)."""
    if max_len is not None and len(text) > max_len:
        text = text[:max_len]
    for pattern, replacement in _REDACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_details(details: dict[str, Any]) -> dict[str, Any]:
    """Redact PII / API keys and truncate string values, preserving native
    types for known-safe telemetry keys.

    Type handling (Phase 1 / E4 — stop stringifying everything):
      - ``None`` passes through as ``None`` (not the string ``"None"``).
      - Safe **bool** keys keep their native ``bool`` (true/false, not "True").
      - Safe **numeric** keys keep their native ``int``/``float`` when already
        numeric; a numeric key carrying a string is length-capped (defensive)
        but never regex-redacted (the credit-card pattern would corrupt it).
      - Every other value is coerced to ``str`` so PII/API-key redaction
        applies to arbitrary content and nested structures stay flat.

    Processing order for redacted strings: coerce → truncate → redact.
    Truncation before redaction caps a long PII-tailed string first (losing the
    tail is acceptable — better than leaking secrets).
    """
    result: dict[str, Any] = {}
    for key, value in details.items():
        if value is None:
            result[key] = None
            continue
        if key in _SAFE_BOOL_KEYS and isinstance(value, bool):
            result[key] = value
            continue
        if key in _SAFE_NUMERIC_KEYS:
            # Native numbers pass through untouched; a stringy numeric is only
            # length-capped, never regex-scrubbed.
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                result[key] = value
            else:
                text = str(value)
                if len(text) > _MAX_DETAIL_VALUE_LEN:
                    text = text[:_MAX_DETAIL_VALUE_LEN]
                result[key] = text
            continue
        result[key] = redact_text(str(value))
    return result


def _redact_phase_events(phase_events: list[Any]) -> list[Any]:
    """Redact free-text ``details`` on phase boundary records (same rules as events)."""
    redacted: list[Any] = []
    for record in phase_events:
        if isinstance(record, dict) and isinstance(record.get("details"), dict):
            record = {**record, "details": redact_details(record["details"])}
        redacted.append(record)
    return redacted


def redact_compliance_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Redact event and phase-event detail payloads before publishing a compliance bundle."""
    redacted = dict(bundle)
    events = redacted.get("events")
    if isinstance(events, list):
        new_events: list[Any] = []
        for ev in events:
            if isinstance(ev, dict) and isinstance(ev.get("details"), dict):
                ev = {**ev, "details": redact_details(ev["details"])}
            new_events.append(ev)
        redacted["events"] = new_events

    phase_events = redacted.get("phase_events")
    if isinstance(phase_events, list):
        redacted["phase_events"] = _redact_phase_events(phase_events)

    return redacted


def _level_for(event: TraceEvent) -> str:
    """Langfuse observation level (Phase 4).

    ``ERROR_OCCURRED`` → ``ERROR``. A ``GUARDRAIL_CHECKED`` that blocked,
    redacted, or has any failed rule → ``WARNING`` (a real signal worth
    surfacing); an otherwise-clean pass → ``DEBUG`` (filterable noise, but kept
    so demos can still show the provable negative). Everything else → ``DEFAULT``.

    Governance carrier gate (enforcement gate Phase 1, shadow): the gate reuses
    ``GUARDRAIL_CHECKED`` to record a missing-pillar gap, but a real gap sets
    ``outcome: "alert"`` / ``would_enforce: true`` WITHOUT any blocked/redacted/
    failed_rules. Without a special case it would relay at ``DEBUG`` —
    indistinguishable from a clean pass, defeating the gate's "never a silent
    skip" purpose. So a ``carrier_gate`` carrier whose outcome is ``alert`` (it
    found a gap) maps to ``WARNING``; a ``carrier_gate`` pass stays ``DEBUG``.
    """
    if event.event_type == EventType.ERROR_OCCURRED:
        return "ERROR"
    if event.event_type == EventType.GUARDRAIL_CHECKED:
        details = event.details or {}
        blocked = bool(details.get("blocked"))
        redacted = bool(details.get("redacted"))
        failed_rules = details.get("failed_rules") or []
        carrier_gate_alert = (
            details.get("source") == "carrier_gate"
            and (details.get("outcome") == "alert" or details.get("would_enforce"))
        )
        if blocked or redacted or failed_rules or carrier_gate_alert:
            return "WARNING"
        return "DEBUG"
    return "DEFAULT"


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

    level = _level_for(event)

    # D-0a (langfuse 4.7.1): the SDK offers no observation start-time backdating,
    # so the relayed Langfuse span is stamped at relay-export time (~0.9s late).
    # Surface the authoritative event instant first-class as ``event_time`` so a
    # reader can reconstruct true ordering. ``timestamp`` is retained verbatim for
    # back-compat. We deliberately emit NO ``start_time``/``end_time`` — a real
    # start with a backdated end would invert the span.
    event_time = event.timestamp.isoformat()
    attributes: dict[str, Any] = {
        "event_id": event.event_id,
        "workflow_id": event.workflow_id,
        "step": event.step,
        "event_time": event_time,
        "timestamp": event_time,
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

    # I5: Promote native generation fields. After E5 retyped MODEL_SELECTED to
    # ``chain``, no relay event maps to ``generation`` — the only event carrying
    # real LLM usage/cost is STEP_EXECUTED (a span that wraps the model call).
    # The wire ``llm.call`` generation (Phase 3) is the primary cost carrier;
    # STEP_EXECUTED remains the relay-side carrier until its export is suppressed
    # in the curated view (Phase 4).
    details = event.details
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
