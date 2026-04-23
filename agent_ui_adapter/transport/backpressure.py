"""Bounded ``asyncio.Queue`` + producer/consumer pairing for backpressure.

Per AGENT_UI_ADAPTER_SPRINTS.md S5 / US-5.4.

Boundary: stdlib only (per plan §15.2).
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator


__all__ = ["BoundedEventStream"]


_LOGGER = logging.getLogger("agent_ui_adapter.transport")


class BoundedEventStream:
    """Producer puts events; consumer drains.

    A full queue causes the producer's ``put`` to *await* until the
    consumer drains -- it never raises ``QueueFull``. ``close()`` signals
    end-of-stream; once closed and drained the consumer iteration ends.
    """

    def __init__(self, maxsize: int = 1024) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=maxsize)
        self._maxsize = maxsize
        self._close_event = asyncio.Event()

    async def put(self, item: bytes) -> None:
        """Enqueue ``item``, blocking when the queue is full."""
        if self._close_event.is_set():
            raise RuntimeError("put() called on a closed BoundedEventStream")
        await self._queue.put(item)

    async def get(self) -> bytes:
        """Dequeue the next item (awaiting if empty)."""
        return await self._queue.get()

    def qsize(self) -> int:
        return self._queue.qsize()

    def maxsize(self) -> int:
        return self._maxsize

    def close(self) -> None:
        """Signal end-of-stream; consumer iteration will end after drain."""
        self._close_event.set()

    @property
    def closed(self) -> bool:
        return self._close_event.is_set()

    async def __aiter__(self) -> AsyncIterator[bytes]:
        """Yield queued items until ``close()`` is called and the queue
        has been drained."""
        loop = asyncio.get_event_loop()
        while True:
            if self._queue.empty() and self._close_event.is_set():
                return

            get_task = loop.create_task(self._queue.get())
            close_task = loop.create_task(self._close_event.wait())

            try:
                done, _pending = await asyncio.wait(
                    {get_task, close_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
            except BaseException:
                get_task.cancel()
                close_task.cancel()
                raise

            if get_task in done:
                if not close_task.done():
                    close_task.cancel()
                    try:
                        await close_task
                    except asyncio.CancelledError:
                        pass
                yield get_task.result()
                continue

            # close_task fired first -> drain remaining items then end
            if not get_task.done():
                get_task.cancel()
                try:
                    await get_task
                except asyncio.CancelledError:
                    pass
                except BaseException:  # noqa: BLE001 -- defensive cleanup
                    _LOGGER.exception("error draining cancelled get task")
            else:
                yield get_task.result()
            while not self._queue.empty():
                yield self._queue.get_nowait()
            return
