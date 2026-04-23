"""SQLite-backed ``MemoryBackend`` for ``services.long_term_memory``.

Sprint M-Phase2 swap proof per docs/plan/adapter/sprints/AGENT_UI_ADAPTER_SPRINTS.md:
this module exists alongside ``in_memory.py`` and conforms to the same
``MemoryBackend`` Protocol. Wiring it in by the composition root requires
zero changes under ``agent_ui_adapter/`` -- empirically validating plan
§10 swap-radius for long-term memory backends.

Implementation notes:

* Uses stdlib ``sqlite3`` only -- no new runtime dependency. The service
  contract is synchronous so an async driver (``aiosqlite``) would buy
  nothing here.
* Single table keyed by ``(user_id, key)``. Payload + metadata are
  serialised to JSON columns; this avoids leaking Python pickle into the
  on-disk format and keeps the column shape inspectable from the sqlite
  CLI.
* ``check_same_thread=False`` + a coarse ``threading.Lock`` lets the
  service be shared across the FastAPI thread pool without each request
  re-opening the connection. For high-throughput multi-worker deployments
  the right swap is ``services/memory_backends/postgres.py`` (future).
* ``search`` is a naive substring match on the JSON payload + metadata
  columns. It is *not* an embedding search; the LongTermMemoryService
  contract documents this as backend-defined behaviour.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from services.long_term_memory import MemoryBackend, MemoryRecord


_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory (
    user_id TEXT NOT NULL,
    key TEXT NOT NULL,
    payload TEXT NOT NULL,
    metadata TEXT NOT NULL,
    PRIMARY KEY (user_id, key)
);
"""


class SqliteMemoryBackend:
    """SQLite-backed implementation of ``services.long_term_memory.MemoryBackend``.

    ``database`` may be ``":memory:"`` for tests / single-process dev, or
    a filesystem path for persistent storage.
    """

    def __init__(self, database: str | Path = ":memory:") -> None:
        self._database = str(database)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            self._database, check_same_thread=False, isolation_level=None
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)

    # ── MemoryBackend Protocol ─────────────────────────────────────

    def put(self, record: MemoryRecord) -> None:
        payload_json = json.dumps(record.payload, sort_keys=True, default=str)
        metadata_json = json.dumps(record.metadata, sort_keys=True, default=str)
        with self._lock:
            self._conn.execute(
                "INSERT INTO memory(user_id, key, payload, metadata) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(user_id, key) DO UPDATE SET "
                "payload = excluded.payload, "
                "metadata = excluded.metadata",
                (record.user_id, record.key, payload_json, metadata_json),
            )

    def get(self, user_id: str, key: str) -> MemoryRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload, metadata FROM memory "
                "WHERE user_id = ? AND key = ?",
                (user_id, key),
            ).fetchone()
        if row is None:
            return None
        payload_json, metadata_json = row
        return MemoryRecord(
            user_id=user_id,
            key=key,
            payload=json.loads(payload_json),
            metadata=json.loads(metadata_json),
        )

    def search(
        self, user_id: str, query: str, limit: int = 10
    ) -> list[MemoryRecord]:
        like = f"%{query}%"
        with self._lock:
            rows = self._conn.execute(
                "SELECT key, payload, metadata FROM memory "
                "WHERE user_id = ? AND (payload LIKE ? OR metadata LIKE ?) "
                "LIMIT ?",
                (user_id, like, like, limit),
            ).fetchall()
        results: list[MemoryRecord] = []
        for key, payload_json, metadata_json in rows:
            results.append(
                MemoryRecord(
                    user_id=user_id,
                    key=key,
                    payload=json.loads(payload_json),
                    metadata=json.loads(metadata_json),
                )
            )
        return results

    def delete(self, user_id: str, key: str) -> bool:
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM memory WHERE user_id = ? AND key = ?",
                (user_id, key),
            )
            return cursor.rowcount > 0

    # ── Lifecycle helpers (for tests + clean shutdown) ─────────────

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "SqliteMemoryBackend":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


# Re-export the Protocol for convenience so callers can write a single
# ``from services.memory_backends.sqlite import SqliteMemoryBackend``.
__all__ = ["MemoryBackend", "SqliteMemoryBackend"]
