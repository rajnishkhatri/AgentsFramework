"""Human-in-the-loop (HITL) virtual tool: ``request_approval``.

Per AGENT_UI_ADAPTER_PLAN.md §4.3 (Special conventions) and SPRINTS US-7.1.

The HITL convention re-uses the AG-UI tool-call wire pattern instead of
inventing a new event type:

1. The agent decides it needs human approval and emits a ``ToolCallStarted``
   for the virtual tool ``request_approval`` with ``{action, justification}``.
2. The translator maps that to AG-UI ``TOOL_CALL_START`` / ``TOOL_CALL_ARGS``
   / ``TOOL_CALL_END`` and the frontend renders an approval prompt.
3. The user clicks Approve or Deny; the frontend POSTs an AG-UI
   ``TOOL_RESULT`` with ``content="approved"`` or ``content="denied"``.
4. The adapter maps that back via ``ag_ui_to_domain.to_domain()`` to a
   ``ToolResultReceived`` and feeds it into the runtime as the tool result.

The tool is *virtual*: the executor must NEVER run server-side. Results
arrive from the frontend over the wire. Calling the executor is a
programming error and raises ``NotImplementedError`` so a misconfigured
runtime fails loud, not silently auto-approves.

Per AGENTS.md the file lives under ``services/tools/`` (a horizontal
service tool, like ``shell.py`` and ``file_io.py``) so the runtime can
register it via ``ToolRegistry`` without any new abstraction.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from services.tools.registry import ToolDefinition

REQUEST_APPROVAL_TOOL_NAME: str = "request_approval"

APPROVED_RESULT: str = "approved"
DENIED_RESULT: str = "denied"


class RequestApprovalInput(BaseModel):
    """Schema for the ``request_approval`` virtual tool.

    Both fields are required and non-empty: an empty ``action`` would give
    the user nothing to approve; an empty ``justification`` would defeat
    the purpose of an audit trail.
    """

    action: str = Field(
        description="Short label for the action requiring human approval.",
    )
    justification: str = Field(
        description="Why the agent believes this action is needed; shown to the user.",
    )

    @field_validator("action", "justification")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be a non-empty string")
        return v


def execute_request_approval(args: dict[str, Any]) -> str:
    """Virtual executor — MUST NOT run server-side.

    The HITL contract is: the result of ``request_approval`` arrives from
    the user via an AG-UI ``TOOL_RESULT`` event, never from server-side
    execution. If a runtime calls this executor it has skipped the wire
    hop, which would silently auto-approve and bypass the human gate.
    Failing loud here protects the trust boundary.
    """
    raise NotImplementedError(
        f"{REQUEST_APPROVAL_TOOL_NAME!r} is a virtual tool: results arrive "
        "from the user via AG-UI TOOL_RESULT, not from server-side execution. "
        "Configure your runtime to route this tool back over the wire."
    )


def request_approval_tool() -> ToolDefinition:
    """Factory for registering ``request_approval`` in a ``ToolRegistry``.

    Usage::

        registry = ToolRegistry({
            REQUEST_APPROVAL_TOOL_NAME: request_approval_tool(),
            # ...other tools...
        })
    """
    return ToolDefinition(
        executor=execute_request_approval,
        schema=RequestApprovalInput,
        cacheable=False,
    )


__all__ = [
    "APPROVED_RESULT",
    "DENIED_RESULT",
    "REQUEST_APPROVAL_TOOL_NAME",
    "RequestApprovalInput",
    "execute_request_approval",
    "request_approval_tool",
]
