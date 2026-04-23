"""JsonlTraceSink: durable JSONL file sink for TrustTraceRecord events.

M-Phase2 second swap proof. Implements the ``TraceSink`` Protocol from
``services.trace_service`` without importing or modifying any
``agent_ui_adapter/`` code.

Compared to the inline ``JsonlFileTraceSink`` in ``trace_service.py``,
this implementation adds:
  - ``os.fsync`` on every emit for crash-safe durability
  - Parent-directory validation at construction time
  - Round-trip verification helpers (``read_all``)
"""

from __future__ import annotations

import os
from pathlib import Path

from trust.models import TrustTraceRecord


class JsonlTraceSink:
    """Append-only JSONL sink with fsync-on-emit.

    Raises ``FileNotFoundError`` at construction if the parent directory
    does not exist (fail-fast, not fail-on-first-emit).
    """

    name: str

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        if not self._path.parent.exists():
            raise FileNotFoundError(
                f"Parent directory does not exist: {self._path.parent}"
            )
        self.name = f"jsonl_durable:{self._path.name}"

    def emit(self, record: TrustTraceRecord) -> None:
        if not isinstance(record, TrustTraceRecord):
            raise TypeError(
                f"JsonlTraceSink.emit requires a TrustTraceRecord, "
                f"got {type(record).__name__}"
            )
        line = record.model_dump_json()
        fd = os.open(str(self._path), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        try:
            os.write(fd, (line + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    def read_all(self) -> list[TrustTraceRecord]:
        """Read back all records from the JSONL file (for testing)."""
        if not self._path.exists():
            return []
        records: list[TrustTraceRecord] = []
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(TrustTraceRecord.model_validate_json(line))
        return records


__all__ = ["JsonlTraceSink"]
