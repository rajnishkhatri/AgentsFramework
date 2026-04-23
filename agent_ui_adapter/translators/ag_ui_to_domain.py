"""Pure AG-UI → domain shape mapping (inbound side).

In v1, the only inbound AG-UI event we re-enter as a domain event is
``ToolResult`` (HITL approvals re-using the tool-call wire pattern per
plan §4.3 / S7). Other inbound events can be added when their use-cases
land -- this translator stays a closed dispatch that fails loudly on
unrecognized inputs (no silent fallback).

Trace_id is supplied by the caller -- the server holds it in session
context. The translator does not invent it.
"""

from __future__ import annotations

from agent_ui_adapter.wire.ag_ui_events import AGUIEvent, ToolResult
from agent_ui_adapter.wire.domain_events import ToolResultReceived


def to_domain(event: AGUIEvent, *, trace_id: str) -> ToolResultReceived:
    """Map an inbound AG-UI ``ToolResult`` to ``ToolResultReceived``.

    Args:
        event: an AG-UI event from the client. Must be a ``ToolResult``.
        trace_id: caller-supplied correlation id (server has it from the
            originating session/run context).

    Raises:
        TypeError: ``event`` is not a ``ToolResult`` (other inbound events
            are not yet supported in v1).
        ValueError: ``trace_id`` is missing or empty.
    """
    if not isinstance(event, ToolResult):
        raise TypeError(
            f"to_domain() v1 supports only ToolResult inbound events; "
            f"got {type(event).__name__}"
        )
    if not trace_id:
        raise ValueError("to_domain() requires a non-empty trace_id")

    return ToolResultReceived(
        trace_id=trace_id,
        tool_call_id=event.tool_call_id,
        result=event.content,
    )


__all__ = ["to_domain"]
