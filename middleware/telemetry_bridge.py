"""Domain-event telemetry bridge — maps DomainEvent to Langfuse export calls.

Pure mapping module. No SDK imports. Imports allowed:
  - stdlib
  - agent_ui_adapter.wire.domain_events (wire ring, framework-neutral)
  - middleware.ports.telemetry_exporter (port Protocol)

Architecture test ``test_middleware_layer.py::TestAppProdSdkIsolation``
enforces that this file never imports the ``langfuse`` SDK.

**Rule O1 (telemetry NEVER blocks):** all export calls are wrapped in
try/except. A broken exporter never aborts the agent run.
"""

from __future__ import annotations

import logging
from typing import Any

from agent_ui_adapter.wire.domain_events import (
    DomainEvent,
    LLMMessageEnded,
    LLMMessageStarted,
    LLMTokenEmitted,
    RunFinishedDomain,
    RunStartedDomain,
    StateMutated,
    ToolCallEnded,
    ToolCallStarted,
    ToolResultReceived,
)
from middleware.ports.telemetry_exporter import TelemetryExporter

logger = logging.getLogger("middleware.telemetry_bridge")

__all__ = ["emit_domain_event", "emit_run_finished"]

_MAX_FIELD_BYTES = 4096
_SKIPPED_TYPES = (LLMTokenEmitted, StateMutated, ToolCallEnded)


def _truncate(value: str, limit: int = _MAX_FIELD_BYTES) -> str:
    if len(value) <= limit:
        return value
    return value[:limit]


def _build_attributes(event: DomainEvent, subject: str | None) -> tuple[str, dict[str, Any]] | None:
    """Return (langfuse_name, attributes) or None if the event should be skipped."""
    if isinstance(event, _SKIPPED_TYPES):
        return None

    attrs: dict[str, Any] = {}

    if isinstance(event, RunStartedDomain):
        name = "run.started"
        attrs["run_id"] = event.run_id
        attrs["thread_id"] = event.thread_id

    elif isinstance(event, RunFinishedDomain):
        name = "run.finished"
        attrs["run_id"] = event.run_id
        attrs["thread_id"] = event.thread_id
        attrs["error"] = event.error
        attrs["__output"] = {"status": "error" if event.error else "success", "error": event.error}

    elif isinstance(event, ToolCallStarted):
        name = "tool.started"
        attrs["tool_name"] = event.tool_name
        attrs["tool_call_id"] = event.tool_call_id
        attrs["args_json"] = _truncate(event.args_json)

    elif isinstance(event, ToolResultReceived):
        name = "tool.finished"
        attrs["tool_call_id"] = event.tool_call_id
        attrs["result"] = _truncate(event.result)
        attrs["__output"] = {"result": _truncate(event.result)}

    elif isinstance(event, LLMMessageStarted):
        name = "llm.started"
        attrs["message_id"] = event.message_id

    elif isinstance(event, LLMMessageEnded):
        name = "llm.finished"
        attrs["message_id"] = event.message_id
        attrs["__output"] = {"status": "completed", "message_id": event.message_id}

    else:
        return None

    if subject is not None:
        attrs["subject"] = subject

    return name, attrs


def emit_domain_event(
    exporter: TelemetryExporter,
    domain_event: DomainEvent,
    *,
    subject: str | None = None,
) -> None:
    """Map a DomainEvent to a Langfuse export call via the TelemetryExporter port.

    Skipped events (LLMTokenEmitted, StateMutated, ToolCallEnded) produce
    zero export calls. On RunFinishedDomain, release_trace() is called to
    free in-memory handles.

    MUST NOT raise — per O1, telemetry failures are silent.
    """
    try:
        result = _build_attributes(domain_event, subject)
        if result is None:
            return

        name, attrs = result
        exporter.export_event(name=name, trace_id=domain_event.trace_id, attributes=attrs)

        if isinstance(domain_event, RunFinishedDomain):
            exporter.release_trace(domain_event.trace_id)
    except Exception as exc:
        logger.debug(
            "telemetry_bridge emit_domain_event swallowed: %s: %s",
            type(exc).__name__,
            exc,
        )


def emit_run_finished(
    exporter: TelemetryExporter,
    *,
    trace_id: str,
    run_id: str | None,
    thread_id: str,
    duration_ms: int,
    errored: bool,
    subject: str | None = None,
) -> None:
    """Emit a standalone run.finished event (safety-net for error paths).

    Used by app_prod.py's finally block when RunFinishedDomain was never
    received from the stream (e.g. the stream errored early). Calls
    release_trace() after emission.

    MUST NOT raise — per O1, telemetry failures are silent.
    """
    try:
        attrs: dict[str, Any] = {
            "run_id": run_id,
            "thread_id": thread_id,
            "duration_ms": duration_ms,
            "errored": errored,
        }
        if subject is not None:
            attrs["subject"] = subject

        exporter.export_event(name="run.finished", trace_id=trace_id, attributes=attrs)
        exporter.release_trace(trace_id)
    except Exception as exc:
        logger.debug(
            "telemetry_bridge emit_run_finished swallowed: %s: %s",
            type(exc).__name__,
            exc,
        )
