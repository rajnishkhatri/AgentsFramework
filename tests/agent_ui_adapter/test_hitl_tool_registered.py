"""US-7.1 — verify the virtual ``request_approval`` tool is registrable.

Failure paths first per AGENTS.md TAP-4:
- Schema rejects missing/empty fields BEFORE accepting valid ones
- The virtual executor raises BEFORE asserting the registry shape

Acceptance:
- Factory produces a ``ToolDefinition`` keyed by ``request_approval``
- A ``ToolRegistry`` containing it reports the tool as present and
  surfaces the expected JSON schema for ``bind_tools()`` consumers.

Per the S7 ownership convention: this story is configuration-only --
NO new translator code. The architecture-level wire hookup is covered
by ``test_hitl_round_trip.py`` (US-7.2) and the architecture test T7.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.tools.hitl import (
    APPROVED_RESULT,
    DENIED_RESULT,
    REQUEST_APPROVAL_TOOL_NAME,
    RequestApprovalInput,
    execute_request_approval,
    request_approval_tool,
)
from services.tools.registry import ToolDefinition, ToolRegistry


# ── Failure paths first ───────────────────────────────────────────────


class TestRequestApprovalInputRejections:
    """Failure paths: invalid schema constructions are rejected loud."""

    def test_rejects_missing_action(self) -> None:
        with pytest.raises(ValidationError):
            RequestApprovalInput(justification="why")  # type: ignore[call-arg]

    def test_rejects_missing_justification(self) -> None:
        with pytest.raises(ValidationError):
            RequestApprovalInput(action="delete-files")  # type: ignore[call-arg]

    def test_rejects_empty_action(self) -> None:
        with pytest.raises(ValidationError, match="non-empty"):
            RequestApprovalInput(action="", justification="why")

    def test_rejects_whitespace_action(self) -> None:
        with pytest.raises(ValidationError, match="non-empty"):
            RequestApprovalInput(action="   ", justification="why")

    def test_rejects_empty_justification(self) -> None:
        with pytest.raises(ValidationError, match="non-empty"):
            RequestApprovalInput(action="delete-files", justification="")


def test_virtual_executor_raises_when_invoked_directly() -> None:
    """The HITL trust boundary fails loud, never silent-auto-approves."""
    with pytest.raises(NotImplementedError, match="virtual tool"):
        execute_request_approval(
            {"action": "delete-files", "justification": "cleanup"}
        )


# ── Acceptance ────────────────────────────────────────────────────────


def test_tool_name_constant_is_request_approval() -> None:
    """Plan §4.3 fixes the wire name; constant must match exactly."""
    assert REQUEST_APPROVAL_TOOL_NAME == "request_approval"


def test_factory_returns_tool_definition() -> None:
    defn = request_approval_tool()
    assert isinstance(defn, ToolDefinition)
    assert defn.schema is RequestApprovalInput
    assert defn.cacheable is False  # never cache a human decision


def test_registry_can_register_request_approval() -> None:
    registry = ToolRegistry(
        {REQUEST_APPROVAL_TOOL_NAME: request_approval_tool()}
    )
    assert registry.has(REQUEST_APPROVAL_TOOL_NAME)


def test_registry_schema_advertises_action_and_justification() -> None:
    """``get_schemas()`` is what ``bind_tools()`` consumers see."""
    registry = ToolRegistry(
        {REQUEST_APPROVAL_TOOL_NAME: request_approval_tool()}
    )
    schemas = registry.get_schemas()
    assert len(schemas) == 1
    schema = schemas[0]
    assert schema["name"] == REQUEST_APPROVAL_TOOL_NAME
    properties = schema["parameters"]["properties"]
    assert "action" in properties
    assert "justification" in properties
    required = set(schema["parameters"].get("required", []))
    assert {"action", "justification"}.issubset(required)


def test_accepts_valid_input() -> None:
    """Sanity: with both fields present and non-empty, validation passes."""
    parsed = RequestApprovalInput(
        action="delete-files",
        justification="user requested cleanup of /tmp",
    )
    assert parsed.action == "delete-files"
    assert parsed.justification.startswith("user requested")


def test_result_constants_are_stable() -> None:
    """The wire vocabulary frontend and adapter agree on."""
    assert APPROVED_RESULT == "approved"
    assert DENIED_RESULT == "denied"
