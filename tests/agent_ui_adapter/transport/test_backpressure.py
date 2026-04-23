"""BoundedEventStream backpressure tests.

Per AGENT_UI_ADAPTER_SPRINTS.md S5 / US-5.4.
TDD Protocol B; failure paths first per AGENTS.md TAP-4.
"""

from __future__ import annotations

import asyncio

import pytest

from agent_ui_adapter.transport.backpressure import BoundedEventStream


# ─── failure paths first ──────────────────────────────────────────────


async def test_put_blocks_when_queue_full_until_consumer_drains() -> None:
    stream = BoundedEventStream(maxsize=2)
    await stream.put(b"a")
    await stream.put(b"b")
    assert stream.qsize() == 2

    pending = asyncio.create_task(stream.put(b"c"))

    # Yield repeatedly; the put must remain pending while queue is full.
    for _ in range(10):
        await asyncio.sleep(0)
    assert not pending.done(), "put() should block when queue is full"

    drained = await stream.get()
    assert drained == b"a"

    await asyncio.wait_for(pending, timeout=1.0)
    assert pending.done()
    assert stream.qsize() == 2


async def test_put_never_raises_queuefull() -> None:
    """Even under stress, put must await rather than raise QueueFull."""
    stream = BoundedEventStream(maxsize=4)

    async def producer() -> None:
        for i in range(50):
            await stream.put(f"x{i}".encode())

    async def consumer() -> list[bytes]:
        out: list[bytes] = []
        for _ in range(50):
            out.append(await stream.get())
        return out

    prod = asyncio.create_task(producer())
    out = await asyncio.wait_for(consumer(), timeout=2.0)
    await asyncio.wait_for(prod, timeout=2.0)

    assert len(out) == 50
    assert out == [f"x{i}".encode() for i in range(50)]


async def test_put_after_close_raises_runtime_error() -> None:
    stream = BoundedEventStream(maxsize=2)
    stream.close()
    with pytest.raises(RuntimeError):
        await stream.put(b"x")


def test_invalid_maxsize_raises() -> None:
    with pytest.raises(ValueError):
        BoundedEventStream(maxsize=0)


# ─── acceptance ───────────────────────────────────────────────────────


async def test_qsize_never_exceeds_maxsize() -> None:
    maxsize = 4
    stream = BoundedEventStream(maxsize=maxsize)
    observed: list[int] = []

    async def producer() -> None:
        for i in range(100):
            await stream.put(f"i{i}".encode())

    async def watcher() -> None:
        for _ in range(50):
            observed.append(stream.qsize())
            await asyncio.sleep(0)

    async def consumer() -> int:
        n = 0
        for _ in range(100):
            await stream.get()
            n += 1
            await asyncio.sleep(0)
        return n

    prod = asyncio.create_task(producer())
    watch = asyncio.create_task(watcher())
    cons = asyncio.create_task(consumer())

    await asyncio.wait_for(prod, timeout=2.0)
    await asyncio.wait_for(cons, timeout=2.0)
    await asyncio.wait_for(watch, timeout=2.0)

    assert max(observed) <= maxsize
    assert stream.maxsize() == maxsize


async def test_close_signals_end_to_consumer_iteration() -> None:
    stream = BoundedEventStream(maxsize=4)
    await stream.put(b"a")
    await stream.put(b"b")

    received: list[bytes] = []

    async def consume() -> None:
        async for item in stream:
            received.append(item)

    consumer = asyncio.create_task(consume())
    for _ in range(5):
        await asyncio.sleep(0)
    assert not consumer.done()

    stream.close()
    await asyncio.wait_for(consumer, timeout=1.0)

    assert received == [b"a", b"b"]


async def test_aiter_yields_in_order() -> None:
    stream = BoundedEventStream(maxsize=8)
    items = [f"item-{i}".encode() for i in range(8)]
    for it in items:
        await stream.put(it)
    stream.close()

    received: list[bytes] = []
    async for chunk in stream:
        received.append(chunk)

    assert received == items


async def test_close_drains_remaining_items_before_ending() -> None:
    stream = BoundedEventStream(maxsize=4)
    await stream.put(b"a")
    await stream.put(b"b")
    stream.close()

    received: list[bytes] = []
    async for chunk in stream:
        received.append(chunk)
    assert received == [b"a", b"b"]


async def test_maxsize_property_is_immutable_after_construction() -> None:
    stream = BoundedEventStream(maxsize=7)
    assert stream.maxsize() == 7
    await stream.put(b"x")
    assert stream.maxsize() == 7
