"""SSE encoder + sentinel session tests.

Per AGENT_UI_ADAPTER_SPRINTS.md S5 / US-5.1.
TDD Protocol B (contract-driven, mock client, no real network).
Failure paths first per AGENTS.md TAP-4.
"""

from __future__ import annotations

from typing import AsyncIterator

import pytest

from agent_ui_adapter.transport.sse import (
    PROXY_HEADERS,
    SENTINEL_LINE,
    encode_error,
    encode_event,
    stream_with_sentinel,
)
from agent_ui_adapter.wire.ag_ui_events import (
    AGUIEvent,
    RunStarted,
    TextMessageContent,
)


def _run_started() -> RunStarted:
    return RunStarted(run_id="r1", thread_id="t1")


# ─── failure paths first ──────────────────────────────────────────────


def test_encode_error_emits_event_error_line() -> None:
    out = encode_error("boom", code="downstream")
    assert b"event: error\n" in out
    assert b"boom" in out
    assert b"downstream" in out
    assert out.endswith(b"\n\n")


async def test_stream_with_sentinel_emits_error_then_sentinel_on_exception() -> None:
    async def bad_source() -> AsyncIterator[AGUIEvent]:
        yield _run_started()
        raise RuntimeError("source blew up")

    chunks: list[bytes] = []
    async for chunk in stream_with_sentinel(bad_source()):
        chunks.append(chunk)

    assert any(b"event: RUN_STARTED\n" in c for c in chunks)
    assert any(b"event: error\n" in c for c in chunks)
    assert any(b"source blew up" in c for c in chunks)
    assert chunks[-1] == SENTINEL_LINE
    error_index = next(i for i, c in enumerate(chunks) if b"event: error\n" in c)
    sentinel_index = chunks.index(SENTINEL_LINE)
    assert error_index < sentinel_index


def test_proxy_headers_include_x_accel_buffering() -> None:
    assert PROXY_HEADERS["X-Accel-Buffering"] == "no"
    assert PROXY_HEADERS["Cache-Control"] == "no-cache"
    assert PROXY_HEADERS["Content-Type"] == "text/event-stream"


# ─── acceptance tests ─────────────────────────────────────────────────


def test_encode_event_format_has_event_and_data_lines() -> None:
    out = encode_event(_run_started())
    assert b"event: RUN_STARTED\n" in out
    assert b"data: {" in out
    assert out.endswith(b"\n\n")


def test_encode_event_with_id_includes_id_line() -> None:
    out = encode_event(_run_started(), event_id="evt-42")
    assert out.startswith(b"id: evt-42\n")
    # ID line must appear before the event line
    id_pos = out.index(b"id: evt-42\n")
    event_pos = out.index(b"event: RUN_STARTED\n")
    assert id_pos < event_pos


def test_encode_event_omits_id_line_when_no_id_provided() -> None:
    out = encode_event(_run_started())
    assert not out.startswith(b"id:")
    assert b"\nid:" not in out


async def test_stream_with_sentinel_emits_sentinel_after_normal_completion() -> None:
    async def good_source() -> AsyncIterator[AGUIEvent]:
        yield _run_started()
        yield TextMessageContent(message_id="m1", delta="hi")

    chunks: list[bytes] = []
    async for chunk in stream_with_sentinel(good_source()):
        chunks.append(chunk)

    assert chunks[-1] == SENTINEL_LINE
    assert any(b"event: RUN_STARTED\n" in c for c in chunks)
    assert any(b"event: TEXT_MESSAGE_CONTENT\n" in c for c in chunks)


async def test_stream_with_sentinel_emits_only_sentinel_for_empty_source() -> None:
    async def empty_source() -> AsyncIterator[AGUIEvent]:
        return
        yield  # pragma: no cover -- unreachable

    chunks: list[bytes] = []
    async for chunk in stream_with_sentinel(empty_source()):
        chunks.append(chunk)

    assert chunks == [SENTINEL_LINE]


def test_each_message_ends_with_double_newline() -> None:
    out = encode_event(_run_started(), event_id="abc")
    assert out.endswith(b"\n\n")
    err = encode_error("nope")
    assert err.endswith(b"\n\n")
    assert SENTINEL_LINE.endswith(b"\n\n")


async def test_stream_with_sentinel_uses_id_provider() -> None:
    counter = {"n": 0}

    def provider() -> str:
        counter["n"] += 1
        return f"id-{counter['n']}"

    async def src() -> AsyncIterator[AGUIEvent]:
        yield _run_started()
        yield _run_started()

    chunks: list[bytes] = []
    async for chunk in stream_with_sentinel(src(), id_provider=provider):
        chunks.append(chunk)

    assert chunks[0].startswith(b"id: id-1\n")
    assert chunks[1].startswith(b"id: id-2\n")
    assert chunks[-1] == SENTINEL_LINE


def test_encode_error_data_is_single_line_json() -> None:
    out = encode_error("bad\nthings", code="X")
    # The data: line itself must not contain embedded raw newlines except
    # the trailing ones that terminate the SSE message.
    body = out[: out.rindex(b"\n\n")]
    lines = body.split(b"\n")
    data_lines = [l for l in lines if l.startswith(b"data: ")]
    assert len(data_lines) == 1


@pytest.mark.parametrize(
    "event_id,expected_first_byte",
    [
        ("xyz", b"i"),  # "id: ..."
        (None, b"e"),  # "event: ..."
    ],
)
def test_encode_event_starts_correctly(event_id: str | None, expected_first_byte: bytes) -> None:
    out = encode_event(_run_started(), event_id=event_id)
    assert out[:1] == expected_first_byte
