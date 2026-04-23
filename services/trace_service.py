"""TraceService: horizontal emit + route service for TrustTraceRecord events.

Spec: docs/plan/services/TRACE_SERVICE_PLAN.md.

Horizontal service per AGENTS.md AP-2: receives sinks as parameters, never
imports other services. Validates the inbound record, then fans out to all
configured sinks with per-sink failure isolation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

from trust.models import TrustTraceRecord

logger = logging.getLogger("trust.trace")


class TraceServiceError(Exception):
    """Base typed exception for trace-service-level failures."""


@runtime_checkable
class TraceSink(Protocol):
    """Single-method sink contract; implement for any backend."""

    def emit(self, record: TrustTraceRecord) -> None: ...


class TraceService:
    def __init__(self, sinks: list[TraceSink]) -> None:
        self._sinks: list[TraceSink] = list(sinks)

    def add_sink(self, sink: TraceSink) -> None:
        self._sinks.append(sink)

    def emit(self, record: TrustTraceRecord) -> None:
        if not isinstance(record, TrustTraceRecord):
            raise TypeError(
                f"TraceService.emit requires a TrustTraceRecord, "
                f"got {type(record).__name__}"
            )
        for sink in self._sinks:
            try:
                sink.emit(record)
            except Exception as exc:
                sink_label = getattr(sink, "name", type(sink).__name__)
                logger.error(
                    "Trace sink %s failed: %s: %s",
                    sink_label,
                    type(exc).__name__,
                    exc,
                )


class InMemoryTraceSink:
    """Append-only in-memory sink, primarily for tests."""

    name = "in_memory"

    def __init__(self) -> None:
        self.records: list[TrustTraceRecord] = []

    def emit(self, record: TrustTraceRecord) -> None:
        self.records.append(record)


class JsonlFileTraceSink:
    """JSONL append sink. One serialized TrustTraceRecord per line."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self.name = f"jsonl:{self._path.name}"

    def emit(self, record: TrustTraceRecord) -> None:
        line = record.model_dump_json()
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


class LoggingTraceSink:
    """Sink that emits the record JSON via stdlib logging at INFO."""

    def __init__(self, logger_name: str = "trust.trace") -> None:
        self._logger = logging.getLogger(logger_name)
        self.name = f"logging:{logger_name}"

    def emit(self, record: TrustTraceRecord) -> None:
        self._logger.info(record.model_dump_json())


__all__ = [
    "TraceSink",
    "TraceService",
    "TraceServiceError",
    "InMemoryTraceSink",
    "JsonlFileTraceSink",
    "LoggingTraceSink",
]
