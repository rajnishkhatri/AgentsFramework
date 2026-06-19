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
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("services.long_term_memory")

# Backend over-fetch budget when a ``mem_type`` filter is applied: large
# enough that the post-filter trim to the caller's ``limit`` is not starved by
# off-type matches, bounded so a pathological store can't return unboundedly.
_OVERFETCH_LIMIT = 1000

# The conventional payload field salient text rides under (mirrors
# components.memory_context._TEXT_KEY — kept local so this service does not
# reach up into components, I-5). consolidate() dedups on it.
_TEXT_KEY = "text"
# The metadata field the typed-autocapture store writes the extractor's
# confidence under; consolidate() evicts lowest-salience first.
_SALIENCE_KEY = "salience"
# P2 #10: an explicit UTC store timestamp so consolidate()'s tie-break ("oldest
# out" among equal-salience records) is crisp instead of backend-insertion-order
# dependent (unreliable on Mem0's vector store). store() stamps it when absent.
_STORED_AT_KEY = "stored_at"


class MemoryRecord(BaseModel):
    user_id: str
    key: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=False)


class MemoryBackendError(Exception):
    """Typed wrapper around any backend-raised exception."""


@dataclass(frozen=True)
class ConsolidationOutcome:
    """What one ``consolidate`` pass did (counts only — never content).

    Frozen so it can ride a carrier/log line by value; the privacy invariant is
    structural (no field holds payload text).
    """

    kept: int = 0
    evicted: int = 0
    deduped: int = 0


@runtime_checkable
class MemoryBackend(Protocol):
    def put(self, record: MemoryRecord) -> None: ...
    def get(self, user_id: str, key: str) -> MemoryRecord | None: ...
    def search(self, user_id: str, query: str, limit: int = 10) -> list[MemoryRecord]: ...
    def delete(self, user_id: str, key: str) -> bool: ...
    # Optional capability (A1 budget/consolidation): list ALL of a user's
    # records (unbounded by a relevance query), needed to count and evict by
    # salience. Backends that can list cheaply implement it (InMemory, Mem0
    # ``get_all``, sqlite); the service detects it via ``hasattr`` and falls
    # back to an over-fetched empty-query ``search`` when it is absent, so this
    # method is NOT required for Protocol conformance (existing backends stay
    # valid). Declared here only to document the contract.
    # def list_all(self, user_id: str) -> list[MemoryRecord]: ...


def _require_user_id(user_id: str) -> None:
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("user_id must be a non-empty string")


def _require_key(key: Any) -> None:
    if not isinstance(key, str):
        raise TypeError(f"key must be a string, got {type(key).__name__}")
    if not key:
        raise ValueError("key must be a non-empty string")


def _norm_text(text: str) -> str:
    """Dedup key for consolidate(): case-insensitive, whitespace-collapsed.

    Mirrors components.memory_context._normalize so recall-side dedup (A2) and
    store-side consolidation (A1) agree on what "the same fact" means.
    """
    return " ".join(text.lower().split())


def _salience_of(record: MemoryRecord) -> float:
    """A record's salience for eviction ordering; missing/invalid → 0.0 (a
    record with no confidence sorts lowest, evicted first)."""
    value = (record.metadata or {}).get(_SALIENCE_KEY)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _stored_at_of(record: MemoryRecord) -> str:
    """A record's store timestamp for the equal-salience tie-break (P2 #10).

    Returns the ISO ``stored_at`` string, or '' when absent — '' sorts before
    any real timestamp, so a record with no timestamp is treated as oldest
    (evicted first among equals), matching the prior insertion-order intent."""
    value = (record.metadata or {}).get(_STORED_AT_KEY)
    return value if isinstance(value, str) else ""


class LongTermMemoryService:
    def __init__(
        self,
        backend: MemoryBackend,
        *,
        budgets: dict[str, int] | None = None,
        safety_floor: float | None = None,
    ) -> None:
        self._backend = backend
        # Hermes / memory-os adoption A1: per-type item budgets, injected at the
        # composition root (Checklist 2 — no module-level singleton). When a
        # record's type has a positive budget and the post-write count exceeds
        # it, ``store`` consolidates that type (dedup + evict lowest-salience).
        # Enforced for EVERY write — autocapture AND the /agent/memory CRUD route
        # / panel — so no writer can grow the store unbounded. Empty/absent map
        # = no caps (the original behavior; CI/dev stay byte-identical).
        self._budgets: dict[str, int] = dict(budgets or {})
        # P2 #8: an optional un-evictable safety floor. A record whose salience
        # is >= this floor is PINNED — consolidate() never evicts it to satisfy a
        # budget (a medical/safety fact must not be crowded out by higher-salience
        # facts). None = disabled (no pinning; today's behavior). Dedup still
        # applies to pinned facts (an exact-duplicate pinned fact still collapses).
        self._safety_floor: float | None = safety_floor

    def store(
        self,
        user_id: str,
        key: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> ConsolidationOutcome | None:
        """Store a record; consolidate its type on budget overflow.

        Returns the ``ConsolidationOutcome`` when a consolidation ran (so the
        caller can emit a governance carrier — the service stays carrier-free),
        else ``None``. Consolidation failures are swallowed (logged) so a write
        never fails on a best-effort prune.
        """
        _require_user_id(user_id)
        _require_key(key)
        if payload is None:
            raise ValueError("payload must not be None")
        meta = dict(metadata or {})
        # P2 #10: stamp an explicit UTC store time when the caller didn't supply
        # one, so consolidate()'s equal-salience tie-break is crisp. Caller-
        # supplied values are preserved (e.g. a re-imported fact's original time).
        if not meta.get(_STORED_AT_KEY):
            meta[_STORED_AT_KEY] = datetime.now(UTC).isoformat()
        record = MemoryRecord(
            user_id=user_id,
            key=key,
            payload=payload,
            metadata=meta,
        )
        try:
            self._backend.put(record)
        except Exception as exc:
            raise MemoryBackendError(
                f"backend failed during store(user_id={user_id!r}, key={key!r})"
            ) from exc
        logger.info("memory.store user_id=%s key=%s", user_id, key)
        return self._consolidate_on_overflow(user_id, meta.get("type"))

    def _consolidate_on_overflow(
        self, user_id: str, mem_type: Any
    ) -> ConsolidationOutcome | None:
        """A1: if ``mem_type`` has a positive budget and is now over it,
        consolidate. Best-effort — a failure here never fails the store."""
        if not isinstance(mem_type, str) or not mem_type:
            return None
        budget = self._budgets.get(mem_type, 0)
        if budget <= 0:
            return None
        try:
            if self.count(user_id, mem_type=mem_type) <= budget:
                return None
            outcome = self.consolidate(user_id, mem_type, budget=budget)
        except MemoryBackendError:
            logger.warning(
                "memory.store consolidate degraded user_id=%s type=%s",
                user_id,
                mem_type,
            )
            return None
        if outcome.evicted == 0 and outcome.deduped == 0:
            return None
        return outcome

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

    # ── A1 bounded budget + consolidation (Hermes/memory-os adoption) ──────
    #
    # docs/research/memory/hermes_adoptions_design.md. A per-(user_id, type)
    # item budget keeps the store from accumulating stale facts unboundedly:
    # on overflow, consolidate() dedups exact-duplicate text then evicts the
    # lowest-salience items until the count is at budget. Deterministic (no
    # LLM) — an LLM-merge consolidation is a future v1.5 seam here.

    def _list_all(self, user_id: str, mem_type: str | None) -> list[MemoryRecord]:
        """All of a user's records (optionally one type), unbounded by a query.

        Uses the backend's optional ``list_all`` when present (reliable for
        Mem0, whose vector ``search`` is unreliable for an empty query), else
        falls back to an over-fetched empty-query ``search`` (the substring
        backends match everything on ``""``). Type filtering is applied here so
        both paths agree.
        """
        list_all = getattr(self._backend, "list_all", None)
        try:
            if callable(list_all):
                records = list(list_all(user_id))
            else:
                records = self._backend.search(user_id, "", _OVERFETCH_LIMIT)
        except Exception as exc:
            raise MemoryBackendError(
                f"backend failed during list_all(user_id={user_id!r})"
            ) from exc
        if mem_type is not None:
            records = [r for r in records if r.metadata.get("type") == mem_type]
        return records

    def count(self, user_id: str, *, mem_type: str | None = None) -> int:
        """Number of stored records for ``user_id`` (optionally one type)."""
        _require_user_id(user_id)
        if mem_type is not None and not isinstance(mem_type, str):
            raise TypeError(
                f"mem_type must be a string or None, got {type(mem_type).__name__}"
            )
        n = len(self._list_all(user_id, mem_type))
        logger.debug(
            "memory.count user_id=%s type=%s n=%d", user_id, mem_type, n
        )
        return n

    def consolidate(
        self, user_id: str, mem_type: str, *, budget: int
    ) -> ConsolidationOutcome:
        """Bring ``(user_id, mem_type)`` down to ``budget`` records.

        Deterministic two-step (no LLM): (1) drop exact-duplicate ``text``,
        keeping the highest-salience copy of each; (2) if still over budget,
        evict the lowest-(salience, then implicit insertion order) records until
        the count equals ``budget``. Returns counts only (never content). A
        ``budget <= 0`` is a no-op guard (callers pass a positive per-type cap).
        """
        _require_user_id(user_id)
        if not isinstance(mem_type, str) or not mem_type:
            raise ValueError("mem_type must be a non-empty string")
        if not isinstance(budget, int) or isinstance(budget, bool):
            raise TypeError("budget must be an int")
        records = self._list_all(user_id, mem_type)
        if budget <= 0:
            return ConsolidationOutcome(kept=len(records), evicted=0, deduped=0)

        # Step 1: exact-text dedup. Group by normalized text; keep the
        # highest-salience record in each group, mark the rest for deletion.
        by_text: dict[str, list[MemoryRecord]] = {}
        for record in records:
            text = str((record.payload or {}).get(_TEXT_KEY, ""))
            by_text.setdefault(_norm_text(text), []).append(record)
        survivors: list[MemoryRecord] = []
        to_delete: list[str] = []
        deduped = 0
        for group in by_text.values():
            if len(group) == 1:
                survivors.append(group[0])
                continue
            group_sorted = sorted(group, key=_salience_of, reverse=True)
            survivors.append(group_sorted[0])
            for loser in group_sorted[1:]:
                to_delete.append(loser.key)
                deduped += 1

        # Step 2: budget eviction. Evict lowest-salience survivors until at
        # budget. P2 #8: records at/above the safety floor are PINNED and never
        # evicted (so a safety fact is never crowded out) — if the pinned set
        # alone exceeds budget, the store legitimately runs over rather than drop
        # one. P2 #10: among non-pinned survivors, sort by (salience DESC, then
        # stored_at DESC) so the lowest-salience and, on a tie, the OLDEST record
        # is evicted first (crisp recency tie-break, not backend order).
        evicted = 0
        floor = self._safety_floor
        if floor is None:
            pinned: list[MemoryRecord] = []
            evictable = survivors
        else:
            pinned = [r for r in survivors if _salience_of(r) >= floor]
            evictable = [r for r in survivors if _salience_of(r) < floor]
        room = budget - len(pinned)
        if room < 0:
            room = 0  # pinned alone exceed budget → evict ALL non-pinned
        if len(evictable) > room:
            evictable_sorted = sorted(
                evictable, key=lambda r: (_salience_of(r), _stored_at_of(r)), reverse=True
            )
            for loser in evictable_sorted[room:]:
                to_delete.append(loser.key)
                evicted += 1

        for key in to_delete:
            try:
                self._backend.delete(user_id, key)
            except Exception as exc:
                raise MemoryBackendError(
                    f"backend failed during consolidate(user_id={user_id!r})"
                ) from exc
        kept = len(survivors) - evicted
        logger.info(
            "memory.consolidate user_id=%s type=%s kept=%d evicted=%d deduped=%d",
            user_id,
            mem_type,
            kept,
            evicted,
            deduped,
        )
        return ConsolidationOutcome(kept=kept, evicted=evicted, deduped=deduped)


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

    def list_all(self, user_id: str) -> list[MemoryRecord]:
        """All records for ``user_id`` (A1 optional capability)."""
        return [r for (uid, _k), r in self._store.items() if uid == user_id]


__all__ = [
    "MemoryRecord",
    "MemoryBackend",
    "MemoryBackendError",
    "ConsolidationOutcome",
    "LongTermMemoryService",
    "InMemoryMemoryBackend",
]
