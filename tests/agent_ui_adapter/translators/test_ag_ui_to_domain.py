"""US-4.2 — inverse mapping for inbound AG-UI events.

In v1 only ``ToolResult`` is supported (HITL approval re-entry). All other
inbound events raise ``TypeError`` so unsupported flows fail loudly.
"""

from __future__ import annotations

import pytest

from agent_ui_adapter.translators.ag_ui_to_domain import to_domain
from agent_ui_adapter.wire.ag_ui_events import RunStarted, ToolResult
from agent_ui_adapter.wire.domain_events import ToolResultReceived


# ── Failure paths first ───────────────────────────────────────────────


def test_to_domain_rejects_non_tool_result() -> None:
    """A RunStarted is not a supported inbound event in v1."""
    event = RunStarted(run_id="r1", thread_id="t1")
    with pytest.raises(TypeError, match="ToolResult"):
        to_domain(event, trace_id="trace-1")


def test_to_domain_rejects_empty_trace_id() -> None:
    event = ToolResult(tool_call_id="tc1", content="ok", role="tool")
    with pytest.raises(ValueError, match="trace_id"):
        to_domain(event, trace_id="")


# ── Acceptance ────────────────────────────────────────────────────────


def test_to_domain_maps_tool_result_to_tool_result_received() -> None:
    event = ToolResult(tool_call_id="tc1", content="approved", role="tool")
    out = to_domain(event, trace_id="trace-xyz")
    assert isinstance(out, ToolResultReceived)
    assert out.tool_call_id == "tc1"
    assert out.result == "approved"


def test_to_domain_propagates_supplied_trace_id() -> None:
    event = ToolResult(tool_call_id="tc1", content="ok", role="tool")
    out = to_domain(event, trace_id="caller-supplied-trace")
    assert out.trace_id == "caller-supplied-trace"
