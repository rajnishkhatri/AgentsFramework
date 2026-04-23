"""Heartbeat tests using a deterministic fake clock + fake sleep.

Per AGENT_UI_ADAPTER_SPRINTS.md S5 / US-5.2.
TDD Protocol B (contract-driven, fake clock, no real waits).

Design:
* ``_FakeClock`` exposes async ``sleep(s)`` and async ``time()``.
* ``sleep()`` does NOT auto-resolve; tests call ``advance(s)`` to move
  the virtual clock forward, which wakes any sleepers whose deadline
  has passed. This lets us assert that NO heartbeat fires unless we
  intentionally advance the clock.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest

from agent_ui_adapter.transport.heartbeat import (
    DEFAULT_INTERVAL_SECONDS,
    HEARTBEAT_BYTES,
    with_heartbeat,
)


# ─── fake clock helper ────────────────────────────────────────────────


class _FakeClock:
    def __init__(self) -> None:
        self.now: float = 0.0
        self._waiters: list[tuple[float, asyncio.Future]] = []

    async def time(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        deadline = self.now + seconds
        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        self._waiters.append((deadline, fut))
        try:
            await fut
        except asyncio.CancelledError:
            self._waiters = [w for w in self._waiters if w[1] is not fut]
            raise

    async def advance(self, seconds: float) -> None:
        self.now += seconds
        kept: list[tuple[float, asyncio.Future]] = []
        to_wake: list[asyncio.Future] = []
        for deadline, fut in self._waiters:
            if fut.done():
                continue
            if deadline <= self.now:
                to_wake.append(fut)
            else:
                kept.append((deadline, fut))
        self._waiters = kept
        for fut in to_wake:
            fut.set_result(None)
        # Yield to the event loop a couple of times so awakened tasks
        # propagate their results into the heartbeat queue before we
        # return control to the test.
        for _ in range(4):
            await asyncio.sleep(0)


# ─── source helpers ───────────────────────────────────────────────────


async def _hanging_source() -> AsyncIterator[bytes]:
    """A source that opens, never yields, and never closes."""
    fut: asyncio.Future = asyncio.get_event_loop().create_future()
    await fut
    yield b"unreachable"  # pragma: no cover


def _drainable_source(items: list[bytes]):
    async def _gen() -> AsyncIterator[bytes]:
        for it in items:
            yield it

    return _gen()


def _emit_at(clock: _FakeClock, schedule: list[tuple[float, bytes]]):
    """Build a source that yields each item after a relative ``sleep`` on
    the given fake clock. After the last item, the source closes."""

    async def _gen() -> AsyncIterator[bytes]:
        for delay, item in schedule:
            await clock.sleep(delay)
            yield item

    return _gen()


def _emit_then_hang(clock: _FakeClock, schedule: list[tuple[float, bytes]]):
    """Like ``_emit_at`` but never closes after the last item."""

    async def _gen() -> AsyncIterator[bytes]:
        for delay, item in schedule:
            await clock.sleep(delay)
            yield item
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        await fut
        yield b"unreachable"  # pragma: no cover

    return _gen()


# ─── tests ────────────────────────────────────────────────────────────


async def test_no_heartbeat_when_events_arrive_faster_than_interval() -> None:
    """10 events at t=0; clock never advances; no heartbeat must fire."""
    clock = _FakeClock()
    items = [f"event-{i}".encode() for i in range(10)]

    out: list[bytes] = []
    async for chunk in with_heartbeat(
        _drainable_source(items),
        interval=15.0,
        sleep=clock.sleep,
        clock=clock.time,
    ):
        out.append(chunk)

    assert out == items
    assert HEARTBEAT_BYTES not in out


async def test_two_heartbeats_emitted_after_30_seconds_idle() -> None:
    clock = _FakeClock()

    out: list[bytes] = []

    async def consume() -> None:
        async for chunk in with_heartbeat(
            _hanging_source(), interval=15.0, sleep=clock.sleep, clock=clock.time
        ):
            out.append(chunk)
            if len(out) == 2:
                return

    consumer = asyncio.create_task(consume())

    # Let the heartbeat ticker register its first sleep().
    for _ in range(8):
        await asyncio.sleep(0)

    await clock.advance(15.0)
    await clock.advance(15.0)

    await asyncio.wait_for(consumer, timeout=1.0)

    assert out == [HEARTBEAT_BYTES, HEARTBEAT_BYTES]


async def test_heartbeat_emitted_at_15s_when_event_at_5s() -> None:
    """Boundary case: an event at t=5s does NOT prevent the t=15s heartbeat."""
    clock = _FakeClock()
    payload = b"data: msg\n\n"

    out: list[bytes] = []

    async def consume() -> None:
        async for chunk in with_heartbeat(
            _emit_then_hang(clock, [(5.0, payload)]),
            interval=15.0,
            sleep=clock.sleep,
            clock=clock.time,
        ):
            out.append(chunk)
            if len(out) == 2:
                return

    consumer = asyncio.create_task(consume())

    for _ in range(8):
        await asyncio.sleep(0)

    await clock.advance(5.0)  # event at t=5
    await clock.advance(10.0)  # ticker fires at t=15

    await asyncio.wait_for(consumer, timeout=1.0)

    assert out == [payload, HEARTBEAT_BYTES]


async def test_heartbeat_does_not_emit_after_source_closes() -> None:
    """Source emits one item then closes; no heartbeat may follow."""
    clock = _FakeClock()
    payload = b"only-one"

    out: list[bytes] = []
    async for chunk in with_heartbeat(
        _drainable_source([payload]),
        interval=15.0,
        sleep=clock.sleep,
        clock=clock.time,
    ):
        out.append(chunk)

    # Even if we advance the clock now (after the iterator returned),
    # the heartbeat should never have appeared in the output.
    await clock.advance(60.0)
    assert out == [payload]
    assert HEARTBEAT_BYTES not in out


async def test_default_interval_constant_is_15_seconds() -> None:
    assert DEFAULT_INTERVAL_SECONDS == 15.0
    assert HEARTBEAT_BYTES == b": ping\n\n"


async def test_heartbeat_passes_through_arbitrary_bytes() -> None:
    """The heartbeat wrapper must not transform source payloads."""
    clock = _FakeClock()
    items = [b"\x00\x01raw", b"event: x\n\n"]

    out: list[bytes] = []
    async for chunk in with_heartbeat(
        _drainable_source(items),
        interval=99.0,
        sleep=clock.sleep,
        clock=clock.time,
    ):
        out.append(chunk)

    assert out == items
