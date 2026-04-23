"""Periodic SSE keep-alive comments interleaved with the event stream.

Per AGENT_UI_ADAPTER_SPRINTS.md S5 / US-5.2.

Design contract:
* Heartbeats fire on a fixed schedule independent of source events
  (matches the spec acceptance "events arriving every 5s, then a
  heartbeat still emits at the 15s boundary"). Two coroutines feed a
  shared queue: a *reader* draining ``source`` and a *ticker* sleeping
  for ``interval`` seconds.
* When the source completes (or raises), the consumer returns
  immediately and the ticker is cancelled -- no heartbeat after close.
* ``sleep`` and ``clock`` are injectable so tests can drive deterministic
  timelines without real wall-clock waits.

Boundary: stdlib only (per plan §15.2).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Awaitable, Callable


__all__ = [
    "DEFAULT_INTERVAL_SECONDS",
    "HEARTBEAT_BYTES",
    "with_heartbeat",
]


_LOGGER = logging.getLogger("agent_ui_adapter.transport")


HEARTBEAT_BYTES: bytes = b": ping\n\n"
DEFAULT_INTERVAL_SECONDS: float = 15.0


_END_SENTINEL: object = object()
_TICK_SENTINEL: object = object()


async def with_heartbeat(
    source: AsyncIterator[bytes],
    *,
    interval: float = DEFAULT_INTERVAL_SECONDS,
    clock: Callable[[], Awaitable[float]] | None = None,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> AsyncIterator[bytes]:
    """Wrap a byte stream so a heartbeat is emitted whenever ``interval``
    seconds elapse on the (real or fake) sleep clock.

    The ``clock`` argument is accepted for forward compatibility with
    deadline-based variants; this implementation uses ``sleep`` only.
    """
    del clock  # currently unused; reserved for future deadline scheduling

    if sleep is None:
        sleep = asyncio.sleep

    queue: asyncio.Queue[Any] = asyncio.Queue()

    async def _reader() -> None:
        try:
            async for chunk in source:
                await queue.put(chunk)
        except Exception as exc:  # noqa: BLE001 -- surfaced as end-of-stream
            _LOGGER.exception("heartbeat source raised: %s", exc)
        finally:
            await queue.put(_END_SENTINEL)

    async def _ticker() -> None:
        try:
            while True:
                await sleep(interval)
                await queue.put(_TICK_SENTINEL)
        except asyncio.CancelledError:
            raise

    reader_task = asyncio.create_task(_reader())
    ticker_task = asyncio.create_task(_ticker())

    try:
        while True:
            item = await queue.get()
            if item is _END_SENTINEL:
                return
            if item is _TICK_SENTINEL:
                yield HEARTBEAT_BYTES
                continue
            yield item
    finally:
        ticker_task.cancel()
        if not reader_task.done():
            reader_task.cancel()
        for t in (ticker_task, reader_task):
            try:
                await t
            except (asyncio.CancelledError, BaseException):  # noqa: BLE001
                pass
