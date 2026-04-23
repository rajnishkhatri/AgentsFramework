"""Pure-asyncio SSE encoder + per-stream session.

NOT FastAPI-coupled. The S6 server will adapt this to FastAPI's
``StreamingResponse`` later. Until then this module returns async
iterators of bytes that any ASGI framework can consume.

Per AGENT_UI_ADAPTER_SPRINTS.md S5 / US-5.1.
Per plan §15.2 boundary: ``transport/`` may import only stdlib +
``agent_ui_adapter.wire.*``; nothing else.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Callable, Mapping

from agent_ui_adapter.wire.ag_ui_events import AGUIEvent


__all__ = [
    "PROXY_HEADERS",
    "SENTINEL_LINE",
    "encode_error",
    "encode_event",
    "stream_with_sentinel",
]


_LOGGER = logging.getLogger("agent_ui_adapter.transport")


SENTINEL_LINE: bytes = b"event: done\ndata: [DONE]\n\n"

PROXY_HEADERS: Mapping[str, str] = {
    "X-Accel-Buffering": "no",
    "Cache-Control": "no-cache",
    "Content-Type": "text/event-stream",
}


def _event_type_str(event: AGUIEvent) -> str:
    """Return the SSE ``event:`` line value for an AG-UI event.

    AGUIEvent is a discriminated union; ``.type`` is an ``EventType`` enum
    member whose ``.value`` is the upper-snake-case spec string.
    """
    type_field = event.type
    return getattr(type_field, "value", str(type_field))


def encode_event(event: AGUIEvent, *, event_id: str | None = None) -> bytes:
    """Encode one AG-UI event as a single SSE message.

    Format::

        id: <event_id>\\n           (only if event_id provided)
        event: <type>\\n
        data: <model_dump_json>\\n
        \\n
    """
    payload_json = event.model_dump_json()
    type_name = _event_type_str(event)

    parts: list[str] = []
    if event_id is not None:
        parts.append(f"id: {event_id}\n")
    parts.append(f"event: {type_name}\n")
    parts.append(f"data: {payload_json}\n")
    parts.append("\n")
    return "".join(parts).encode("utf-8")


def encode_error(message: str, *, code: str | None = None) -> bytes:
    """Encode an ``event: error`` SSE line.

    The data payload is a JSON object so downstream clients can parse it
    uniformly. We use ``json.dumps`` with ``separators=(",", ":")`` to
    keep the line single-line (no internal newlines).
    """
    body: dict[str, str] = {"message": message}
    if code is not None:
        body["code"] = code
    data = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    return f"event: error\ndata: {data}\n\n".encode("utf-8")


async def stream_with_sentinel(
    source: AsyncIterator[AGUIEvent],
    *,
    id_provider: Callable[[], str] | None = None,
) -> AsyncIterator[bytes]:
    """Yield encoded events, then ``SENTINEL_LINE`` on normal completion.

    Failure semantics (per US-5.1 acceptance, failure-paths-first):
    on exception from ``source``, an ``event: error`` line is yielded
    followed by ``SENTINEL_LINE``; the exception is logged via the module
    logger and *swallowed* (the consumer sees a graceful close instead of
    a torn connection).
    """
    try:
        async for event in source:
            event_id = id_provider() if id_provider is not None else None
            yield encode_event(event, event_id=event_id)
    except Exception as exc:  # noqa: BLE001 -- we re-emit as SSE error line
        _LOGGER.exception("SSE source raised: %s", exc)
        yield encode_error(str(exc) or exc.__class__.__name__)
    yield SENTINEL_LINE
