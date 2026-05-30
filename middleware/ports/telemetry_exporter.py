"""TelemetryExporter port -- vendor-neutral observability contract.

Per Sprint 1 §S1.1.2: composition wires a telemetry exporter behind
this port. v3 default = ``LangfuseCloudExporter``. v2 graduation =
``SelfHostedLangfuseExporter`` or ``CloudTraceExporter``.

**Rule O1 (telemetry never blocks SSE):** every implementation MUST
swallow failures silently -- raising in the exporter must NEVER abort
the agent run. Callers expect this contract and do not wrap exporter
calls in try/except.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable


__all__ = ["TelemetryExporter"]


@runtime_checkable
class TelemetryExporter(Protocol):
    """Application-contract port for telemetry export."""

    def export_event(
        self,
        *,
        name: str,
        trace_id: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> bool:
        """Emit a single observability event.

        MUST NOT raise -- per O1, telemetry failures are silent.

        Returns ``True`` when the event was handed to the backend (or was an
        intentional no-op, e.g. the exporter is disabled), and ``False`` when a
        genuine export error was swallowed. Callers may use the return value to
        dead-letter swallowed failures, but MUST treat a missing/ ``None``
        return as success for backward compatibility.
        """
        ...

    def release_trace(self, trace_id: str) -> None:
        """Drop in-memory handle for a completed trace.

        Called by the telemetry bridge after ``run.finished`` to prevent
        unbounded growth of trace handles.  MUST NOT raise.
        """
        ...

    def shutdown(self) -> None:
        """Flush buffered events. MUST NOT raise."""
        ...

    def flush(self) -> None:
        """Send buffered events. MUST NOT raise."""
        ...
