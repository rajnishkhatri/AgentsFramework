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
import time
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
    TaskUnderstood,
    ToolCallEnded,
    ToolCallStarted,
    ToolResultReceived,
)
from middleware.ports.telemetry_exporter import TelemetryExporter
from services.governance.black_box_publisher import redact_text

logger = logging.getLogger("middleware.telemetry_bridge")


__all__ = ["emit_domain_event", "emit_run_finished"]

_MAX_FIELD_BYTES = 4096
# Phase 3: ``LLMMessageStarted``/``ToolCallStarted``/``LLMTokenEmitted`` are
# BUFFERED (folded into the merged terminal observation), not skipped — they are
# intercepted in ``emit_domain_event`` before ``_build_attributes`` and so never
# reach ``_SKIPPED_TYPES``.
# StepProgressed is a UI step-meter affordance; Langfuse already carries
# per-lap tool/llm observations, so exporting it would only add noise.
# ReasoningSummarized likewise: the recap's own LLM call is already exported
# as an llm observation; the domain event is a pure UI affordance.
# TaskUnderstood likewise: the artifact is already exported as the
# eval.task_understanding observation and joined via STEP_PLANNED; the
# domain event only feeds the soft-gate card.
_SKIPPED_TYPES = (
    ReasoningSummarized,
    StateMutated,
    StepProgressed,
    TaskUnderstood,
    ToolCallEnded,
)

# Per-trace buffers, keyed ``(trace_id, key)``. Cleared on RunFinishedDomain.
# ``_llm_token_buffers``: streamed output deltas, folded into the merged llm.call.
# ``_llm_start_buffers``: (input attrs, monotonic start) from LLMMessageStarted.
# ``_tool_start_buffers``: (start attrs, monotonic start) from ToolCallStarted.
_llm_token_buffers: dict[tuple[str, str], list[str]] = {}
_llm_start_buffers: dict[tuple[str, str], tuple[dict[str, Any], float]] = {}
_tool_start_buffers: dict[tuple[str, str], tuple[dict[str, Any], float]] = {}


def _truncate(value: str, limit: int = _MAX_FIELD_BYTES) -> str:
    if len(value) <= limit:
        return value
    return value[:limit]


def _redact_and_truncate(value: str, limit: int = _MAX_FIELD_BYTES) -> str:
    return _truncate(redact_text(value, max_len=limit), limit)


def _clear_trace_buffers(trace_id: str) -> None:
    """Drop every per-trace buffer entry for ``trace_id`` (Phase 3 hygiene).

    Started-but-never-finished LLM/tool calls would otherwise linger in the
    buffer maps after a run ends; clearing on RunFinishedDomain bounds memory
    and prevents cross-run leakage. Other traces are untouched.
    """
    for buf in (_llm_token_buffers, _llm_start_buffers, _tool_start_buffers):
        for key in [k for k in buf if k[0] == trace_id]:
            del buf[key]


def _derive_step_from_tool_call_id(tool_call_id: str | None) -> int | None:
    """Recover the loop step from a ``"{step}:{tool_id}"`` tool_call_id.

    Phase 2 (E2 join): the replay/fallback runtime path uses the relay
    ``record_id`` (``"{step}:{tool_id}"``) as the wire ``tool_call_id``, so the
    step is recoverable from its prefix. The live-stream path uses a bare
    LangChain id (e.g. ``call_abc123``) with no step prefix — there the step is
    not cheaply knowable (D-2a), so it is simply omitted. A malformed or
    missing prefix MUST NOT raise (O1).
    """
    if not tool_call_id:
        return None
    prefix, sep, _ = tool_call_id.partition(":")
    if not sep or not prefix.isdigit():
        # ``isdigit`` rejects empty, negative ("-1"), and non-numeric prefixes.
        return None
    return int(prefix)


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

    elif isinstance(event, ToolResultReceived):
        # Phase 3: merge the buffered ToolCallStarted into ONE tool.{name} obs.
        key = (event.trace_id, event.tool_call_id)
        start_attrs, start_ts = _tool_start_buffers.pop(key, ({}, None))
        tool_name = start_attrs.get("tool_name") or "unknown"
        name = f"tool.{tool_name}"
        attrs["tool_call_id"] = event.tool_call_id
        if "tool_name" in start_attrs:
            attrs["tool_name"] = start_attrs["tool_name"]
        if "args_json" in start_attrs:
            attrs["args_json"] = start_attrs["args_json"]
        step = _derive_step_from_tool_call_id(event.tool_call_id)
        if step is not None:
            attrs["step"] = step
        if start_ts is not None:
            attrs["latency_ms"] = (time.monotonic() - start_ts) * 1000.0
        attrs["result"] = _redact_and_truncate(event.result)
        attrs["__output"] = {"result": _redact_and_truncate(event.result)}

    elif isinstance(event, LLMMessageEnded):
        # Phase 3: merge the buffered LLMMessageStarted + token deltas into ONE
        # llm.call generation carrying input, output, model, usage, cost, latency.
        name = "llm.call"
        attrs["message_id"] = event.message_id
        key = (event.trace_id, event.message_id)
        start_attrs, start_ts = _llm_start_buffers.pop(key, ({}, None))
        if "input_text" in start_attrs:
            attrs["input_text"] = start_attrs["input_text"]
        buffered = "".join(_llm_token_buffers.pop(key, []))
        content = event.output_text or buffered or None
        output: dict[str, Any] = {
            "status": "completed",
            "message_id": event.message_id,
        }
        if content:
            output["content"] = _redact_and_truncate(content)
        attrs["__output"] = output
        if start_ts is not None:
            attrs["latency_ms"] = (time.monotonic() - start_ts) * 1000.0
        if event.model is not None:
            attrs["__bb_model"] = event.model
        if event.tokens_in is not None or event.tokens_out is not None:
            ti = event.tokens_in or 0
            to = event.tokens_out or 0
            attrs["__bb_usage"] = {"input": ti, "output": to, "total": ti + to}
        if event.cost_usd is not None:
            attrs["__bb_cost"] = event.cost_usd

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

    Phase 3: ``LLMMessageStarted``/``ToolCallStarted``/``LLMTokenEmitted`` are
    buffered and folded into the single merged terminal observation
    (``llm.call`` on ``LLMMessageEnded``; ``tool.{tool_name}`` on
    ``ToolResultReceived``) carrying input + output + model/usage/cost +
    ``latency_ms``. Skipped events (``StateMutated``, ``ToolCallEnded``) produce
    zero export calls. On RunFinishedDomain, per-trace buffers are cleared and
    release_trace() frees in-memory handles.

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
        # ── Phase 3: buffer the start/streaming events; the terminal event
        #    (LLMMessageEnded / ToolResultReceived) folds them into one obs. ──
        if isinstance(domain_event, LLMTokenEmitted):
            key = (domain_event.trace_id, domain_event.message_id)
            _llm_token_buffers.setdefault(key, []).append(domain_event.delta)
            return

        if isinstance(domain_event, LLMMessageStarted):
            key = (domain_event.trace_id, domain_event.message_id)
            start_attrs: dict[str, Any] = {}
            if domain_event.input_text:
                start_attrs["input_text"] = _redact_and_truncate(domain_event.input_text)
            _llm_start_buffers[key] = (start_attrs, time.monotonic())
            return

        if isinstance(domain_event, ToolCallStarted):
            key = (domain_event.trace_id, domain_event.tool_call_id)
            _tool_start_buffers[key] = (
                {
                    "tool_name": domain_event.tool_name,
                    "args_json": _redact_and_truncate(domain_event.args_json),
                },
                time.monotonic(),
            )
            return

        result = _build_attributes(domain_event, subject)
        if result is None:
            return

        name, attrs = result
        exporter.export_event(name=name, trace_id=domain_event.trace_id, attributes=attrs)

        if isinstance(domain_event, RunFinishedDomain):
            # Clear bridge-owned buffers on every run-finish (independent of the
            # exporter trace-handle lifecycle) so started-but-never-finished
            # calls never leak across runs.
            _clear_trace_buffers(domain_event.trace_id)
            if release_on_finish:
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
