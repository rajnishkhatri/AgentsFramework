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
    ReasoningSummarized,
    RunFinishedDomain,
    RunStartedDomain,
    StateMutated,
    StepProgressed,
    ToolCallEnded,
    ToolCallStarted,
    ToolResultReceived,
)
from middleware.ports.telemetry_exporter import TelemetryExporter
from services.governance.black_box_publisher import redact_text

logger = logging.getLogger("middleware.telemetry_bridge")


__all__ = ["emit_domain_event", "emit_run_finished"]

_MAX_FIELD_BYTES = 4096
# ``LLMTokenEmitted`` is intercepted earlier in ``emit_domain_event`` (its deltas
# are buffered and folded into the matching ``llm.finished`` export), so it never
# produces a direct observation — it belongs in the skipped set alongside the
# events that are dropped outright.
# StepProgressed is a UI step-meter affordance; Langfuse already carries
# per-lap tool/llm observations, so exporting it would only add noise.
# ReasoningSummarized likewise: the recap's own LLM call is already exported
# as an llm observation; the domain event is a pure UI affordance.
_SKIPPED_TYPES = (
    LLMTokenEmitted,
    ReasoningSummarized,
    StateMutated,
    StepProgressed,
    ToolCallEnded,
)
_llm_token_buffers: dict[tuple[str, str], list[str]] = {}


def _truncate(value: str, limit: int = _MAX_FIELD_BYTES) -> str:
    if len(value) <= limit:
        return value
    return value[:limit]


def _redact_and_truncate(value: str, limit: int = _MAX_FIELD_BYTES) -> str:
    return _truncate(redact_text(value, max_len=limit), limit)


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
        attrs["args_json"] = _redact_and_truncate(event.args_json)

    elif isinstance(event, ToolResultReceived):
        name = "tool.finished"
        attrs["tool_call_id"] = event.tool_call_id
        attrs["result"] = _redact_and_truncate(event.result)
        attrs["__output"] = {"result": _redact_and_truncate(event.result)}

    elif isinstance(event, LLMMessageStarted):
        name = "llm.started"
        attrs["message_id"] = event.message_id
        if event.input_text:
            attrs["input_text"] = _redact_and_truncate(event.input_text)

    elif isinstance(event, LLMMessageEnded):
        name = "llm.finished"
        attrs["message_id"] = event.message_id
        key = (event.trace_id, event.message_id)
        buffered = "".join(_llm_token_buffers.pop(key, []))
        content = event.output_text or buffered or None
        output: dict[str, Any] = {
            "status": "completed",
            "message_id": event.message_id,
        }
        if content:
            output["content"] = _redact_and_truncate(content)
        attrs["__output"] = output

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
    release_on_finish: bool = True,
) -> None:
    """Map a DomainEvent to a Langfuse export call via the TelemetryExporter port.

    ``LLMTokenEmitted`` events are buffered and folded into the matching
    ``llm.finished`` export. Skipped events (``StateMutated``, ``ToolCallEnded``)
    produce zero export calls. On RunFinishedDomain, release_trace() is called
    to free in-memory handles.

    ``release_on_finish`` (I6): when ``False``, ``release_trace`` is **not**
    called on ``RunFinishedDomain``. The SSE ``finally`` in ``app_prod`` sets
    this so it can own teardown ordering — drain the BlackBox relay tail
    *before* closing step spans. Releasing eagerly here would close every
    ``step.N`` span before the relay's late events are exported, so the late
    events would recreate fresh spans and the trace tree shape would differ run
    to run (the I6 nondeterministic-nesting symptom).

    MUST NOT raise — per O1, telemetry failures are silent.
    """
    try:
        if isinstance(domain_event, LLMTokenEmitted):
            key = (domain_event.trace_id, domain_event.message_id)
            _llm_token_buffers.setdefault(key, []).append(domain_event.delta)
            return

        result = _build_attributes(domain_event, subject)
        if result is None:
            return

        name, attrs = result
        exporter.export_event(name=name, trace_id=domain_event.trace_id, attributes=attrs)

        if isinstance(domain_event, RunFinishedDomain) and release_on_finish:
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
    release: bool = True,
) -> None:
    """Emit a standalone run.finished event (safety-net for error paths).

    Used by app_prod.py's finally block when RunFinishedDomain was never
    received from the stream (e.g. the stream errored early). Calls
    release_trace() after emission.

    ``release`` (I6): when ``False`` the caller owns teardown ordering and is
    responsible for calling ``release_trace`` *after* the relay tail is drained.

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
        if release:
            exporter.release_trace(trace_id)
    except Exception as exc:
        logger.debug(
            "telemetry_bridge emit_run_finished swallowed: %s: %s",
            type(exc).__name__,
            exc,
        )
