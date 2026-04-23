"""Tests for the AgentRuntime port.

Per AGENT_UI_ADAPTER_SPRINTS.md US-3.1. TDD Protocol B (Contract-driven).
The port is a runtime-checkable Protocol; tests prove conformance + the
single-port shape (rule R9 enforcement).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import AsyncIterator

import pytest

from agent_ui_adapter.ports.agent_runtime import AgentRuntime
from agent_ui_adapter.wire.agent_protocol import ThreadState
from agent_ui_adapter.wire.domain_events import DomainEvent


PORTS_DIR = Path(__file__).resolve().parents[3] / "agent_ui_adapter" / "ports"


# ── R9: single-port shape (failure path first per TAP-4) ──────────────


class TestSinglePortInvariant:
    def test_only_one_protocol_subclass_in_ports_directory(self) -> None:
        """Rule R9: agent_ui_adapter/ports/ defines exactly one Protocol."""
        protocol_defs: list[str] = []
        for py in PORTS_DIR.rglob("*.py"):
            if py.name == "__init__.py":
                continue
            tree = ast.parse(py.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    base_names = {
                        b.id if isinstance(b, ast.Name)
                        else (b.attr if isinstance(b, ast.Attribute) else "")
                        for b in node.bases
                    }
                    if "Protocol" in base_names:
                        protocol_defs.append(f"{py.name}:{node.name}")
        assert len(protocol_defs) == 1, (
            f"R9 violation: ports/ must define exactly one Protocol; found:\n"
            + "\n".join(protocol_defs)
        )


# ── Conformance: positive + negative ──────────────────────────────────


class _CompleteImpl:
    """Implements all three required methods."""

    async def run(self, thread_id, input, identity) -> AsyncIterator[DomainEvent]:
        if False:
            yield  # pragma: no cover

    async def cancel(self, run_id: str) -> None:
        return None

    async def get_state(self, thread_id: str) -> ThreadState:  # type: ignore[empty-body]
        ...


class _MissingCancel:
    async def run(self, thread_id, input, identity) -> AsyncIterator[DomainEvent]:
        if False:
            yield

    async def get_state(self, thread_id: str) -> ThreadState:  # type: ignore[empty-body]
        ...


class _MissingRun:
    async def cancel(self, run_id: str) -> None:
        return None

    async def get_state(self, thread_id: str) -> ThreadState:  # type: ignore[empty-body]
        ...


class TestAgentRuntimeProtocolConformance:
    def test_class_with_all_methods_satisfies_protocol(self) -> None:
        assert isinstance(_CompleteImpl(), AgentRuntime)

    def test_class_missing_cancel_does_not_satisfy(self) -> None:
        assert not isinstance(_MissingCancel(), AgentRuntime)

    def test_class_missing_run_does_not_satisfy(self) -> None:
        assert not isinstance(_MissingRun(), AgentRuntime)

    def test_protocol_is_runtime_checkable(self) -> None:
        assert hasattr(AgentRuntime, "_is_runtime_protocol")
