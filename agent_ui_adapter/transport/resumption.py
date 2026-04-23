"""Per-thread Last-Event-ID cursor for SSE resumption.

Per AGENT_UI_ADAPTER_SPRINTS.md S5 / US-5.3.

In-memory ring buffer of ``(event_id, encoded_bytes)`` per thread.
Production deployments swap this for a Redis-backed implementation
behind the same shape; v1 ships in-memory.

Boundary: stdlib only (per plan §15.2).
"""

from __future__ import annotations

from collections import deque
from typing import Deque


__all__ = [
    "EventBuffer",
    "UnknownCursorError",
]


class UnknownCursorError(Exception):
    """Raised when ``replay_after`` is called with an event_id that the
    buffer has never seen for the given thread (or that has already been
    evicted by the ring-buffer eviction policy)."""


class EventBuffer:
    """In-memory ring buffer of ``(event_id, encoded_bytes)`` per thread.

    Invariants:
    * Per-thread storage is bounded by ``max_per_thread``; oldest entries
      are evicted FIFO.
    * Evicted IDs are remembered in a small companion set so we can
      raise ``UnknownCursorError`` (instead of returning a wrong slice)
      when a client tries to resume from a now-gone cursor.
    * Different ``thread_id`` values are fully isolated.
    """

    def __init__(self, max_per_thread: int = 1024) -> None:
        if max_per_thread < 1:
            raise ValueError("max_per_thread must be >= 1")
        self._max = max_per_thread
        self._buffers: dict[str, Deque[tuple[str, bytes]]] = {}
        self._evicted_ids: dict[str, set[str]] = {}

    def append(self, thread_id: str, event_id: str, payload: bytes) -> None:
        buf = self._buffers.setdefault(thread_id, deque())
        buf.append((event_id, payload))
        while len(buf) > self._max:
            evicted_id, _ = buf.popleft()
            self._evicted_ids.setdefault(thread_id, set()).add(evicted_id)

    def replay_after(self, thread_id: str, last_event_id: str) -> list[bytes]:
        """Return all events appended *after* ``last_event_id`` for the
        given thread. Raise :class:`UnknownCursorError` if the cursor is
        unknown or has been evicted.
        """
        buf = self._buffers.get(thread_id)
        if buf is None:
            raise UnknownCursorError(
                f"thread {thread_id!r} has no buffered events"
            )

        snapshot = list(buf)
        for index, (eid, _) in enumerate(snapshot):
            if eid == last_event_id:
                return [payload for _, payload in snapshot[index + 1 :]]

        if last_event_id in self._evicted_ids.get(thread_id, set()):
            raise UnknownCursorError(
                f"event_id {last_event_id!r} for thread {thread_id!r} "
                "has been evicted"
            )
        raise UnknownCursorError(
            f"event_id {last_event_id!r} unknown for thread {thread_id!r}"
        )

    def has(self, thread_id: str, event_id: str) -> bool:
        buf = self._buffers.get(thread_id)
        if buf is None:
            return False
        return any(eid == event_id for eid, _ in buf)
