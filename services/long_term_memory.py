"""LongTermMemoryService: backend-agnostic per-user long-term memory store.

Spec: docs/plan/services/LONG_TERM_MEMORY_PLAN.md.

Horizontal service per AGENTS.md AP-2: receives a `MemoryBackend` as a
parameter, never imports a specific backend. Validates inputs, hands work
to the backend, and re-raises any backend exception as a typed
`MemoryBackendError` so callers can `except` cleanly.

Privacy invariant: payload values NEVER appear in log lines. Only operation
metadata (user_id + key) is logged.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("services.long_term_memory")

# Backend over-fetch budget when a ``mem_type`` filter is applied: large
# enough that the post-filter trim to the caller's ``limit`` is not starved by
# off-type matches, bounded so a pathological store can't return unboundedly.
_OVERFETCH_LIMIT = 1000


class MemoryRecord(BaseModel):
    user_id: str
    key: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=False)


class MemoryBackendError(Exception):
    """Typed wrapper around any backend-raised exception."""


@runtime_checkable
class MemoryBackend(Protocol):
    def put(self, record: MemoryRecord) -> None: ...
    def get(self, user_id: str, key: str) -> MemoryRecord | None: ...
    def search(self, user_id: str, query: str, limit: int = 10) -> list[MemoryRecord]: ...
    def delete(self, user_id: str, key: str) -> bool: ...


def _require_user_id(user_id: str) -> None:
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("user_id must be a non-empty string")


def _require_key(key: Any) -> None:
    if not isinstance(key, str):
        raise TypeError(f"key must be a string, got {type(key).__name__}")
    if not key:
        raise ValueError("key must be a non-empty string")


class LongTermMemoryService:
    def __init__(self, backend: MemoryBackend) -> None:
        self._backend = backend

    def store(
        self,
        user_id: str,
        key: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        _require_user_id(user_id)
        _require_key(key)
        if payload is None:
            raise ValueError("payload must not be None")
        record = MemoryRecord(
            user_id=user_id,
            key=key,
            payload=payload,
            metadata=dict(metadata or {}),
        )
        try:
            self._backend.put(record)
        except Exception as exc:
            raise MemoryBackendError(
                f"backend failed during store(user_id={user_id!r}, key={key!r})"
            ) from exc
        logger.info("memory.store user_id=%s key=%s", user_id, key)

    def recall(self, user_id: str, key: str) -> MemoryRecord | None:
        _require_user_id(user_id)
        _require_key(key)
        try:
            record = self._backend.get(user_id, key)
        except Exception as exc:
            raise MemoryBackendError(
                f"backend failed during recall(user_id={user_id!r}, key={key!r})"
            ) from exc
        logger.debug(
            "memory.recall user_id=%s key=%s present=%s",
            user_id,
            key,
            record is not None,
        )
        return record

    def search(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        *,
        mem_type: str | None = None,
    ) -> list[MemoryRecord]:
        """Substring search scoped to ``user_id``.

        ``mem_type`` (Phase 2, additive/backward-compatible) optionally keeps
        only records whose ``metadata["type"]`` matches — the typed-recall
        filter. It is applied AFTER the backend search and BEFORE ``limit`` so
        a type query returns up to ``limit`` matching items even when off-type
        records would otherwise have consumed the budget (the backend is
        over-fetched in that case). Omitting it preserves the original
        all-types behavior exactly.
        """
        _require_user_id(user_id)
        if not isinstance(query, str):
            raise TypeError(f"query must be a string, got {type(query).__name__}")
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise TypeError("limit must be an int")
        if limit < 0:
            raise ValueError("limit must be >= 0")
        if mem_type is not None and not isinstance(mem_type, str):
            raise TypeError(
                f"mem_type must be a string or None, got {type(mem_type).__name__}"
            )
        # When filtering by type, off-type matches must not consume the limit:
        # over-fetch from the backend, then filter, then trim to ``limit``.
        backend_limit = _OVERFETCH_LIMIT if mem_type is not None else limit
        try:
            results = self._backend.search(user_id, query, backend_limit)
        except Exception as exc:
            raise MemoryBackendError(
                f"backend failed during search(user_id={user_id!r})"
            ) from exc
        if mem_type is not None:
            results = [
                r for r in results if r.metadata.get("type") == mem_type
            ][:limit]
        logger.debug(
            "memory.search user_id=%s limit=%s type=%s results=%d",
            user_id,
            limit,
            mem_type,
            len(results),
        )
        return results

    def forget(self, user_id: str, key: str) -> bool:
        _require_user_id(user_id)
        _require_key(key)
        try:
            removed = self._backend.delete(user_id, key)
        except Exception as exc:
            raise MemoryBackendError(
                f"backend failed during forget(user_id={user_id!r}, key={key!r})"
            ) from exc
        logger.info(
            "memory.forget user_id=%s key=%s removed=%s", user_id, key, removed
        )
        return removed


class InMemoryMemoryBackend:
    """Dict-backed in-memory backend for tests and dev.

    Naive substring search over `payload` and `metadata` JSON
    representations, scoped per `user_id`.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], MemoryRecord] = {}

    def put(self, record: MemoryRecord) -> None:
        self._store[(record.user_id, record.key)] = record

    def get(self, user_id: str, key: str) -> MemoryRecord | None:
        return self._store.get((user_id, key))

    def search(
        self, user_id: str, query: str, limit: int = 10
    ) -> list[MemoryRecord]:
        results: list[MemoryRecord] = []
        for (uid, _key), record in self._store.items():
            if uid != user_id:
                continue
            haystack = repr(record.payload) + " " + repr(record.metadata)
            if query in haystack:
                results.append(record)
                if len(results) >= limit:
                    break
        return results

    def delete(self, user_id: str, key: str) -> bool:
        return self._store.pop((user_id, key), None) is not None


__all__ = [
    "MemoryRecord",
    "MemoryBackend",
    "MemoryBackendError",
    "LongTermMemoryService",
    "InMemoryMemoryBackend",
]
