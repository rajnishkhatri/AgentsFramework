"""MockRuntime — scripted ``AgentRuntime`` for tests.

Per AGENT_UI_ADAPTER_SPRINTS.md US-3.2 / TDD §Pattern 6 (Mock Provider).
Every test that needs a runtime above S3 (translators, transport, server)
uses MockRuntime so we never depend on LangGraph, an LLM, or any I/O.

Behavior:

- ``run()`` yields a configured list of ``DomainEvent``s in order
- ``error_after=N`` — after N events, raise ``RuntimeError`` to exercise
  failure-path tests in higher layers
- ``cancel()`` records the run_id (idempotent, no-op for unknown ids)
- ``get_state()`` returns either a seeded ``ThreadState`` or a default
  empty one; ``strict_state=True`` raises ``KeyError`` for unknown threads
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, AsyncIterator

from agent_ui_adapter.wire.agent_protocol import ThreadState
from agent_ui_adapter.wire.domain_events import DomainEvent
from trust.models import AgentFacts


class MockRuntime:
    """Scripted ``AgentRuntime`` implementation for tests."""

    def __init__(
        self,
        events: list[DomainEvent],
        error_after: int | None = None,
        states: dict[str, ThreadState] | None = None,
        strict_state: bool = False,
    ) -> None:
        self._events = list(events)
        self._error_after = error_after
        self._states: dict[str, ThreadState] = dict(states or {})
        self._strict_state = strict_state
        self.cancelled_runs: set[str] = set()

    async def run(
        self,
        thread_id: str,
        input: dict[str, Any],
        identity: AgentFacts,
    ) -> AsyncIterator[DomainEvent]:
        for i, ev in enumerate(self._events):
            if self._error_after is not None and i >= self._error_after:
                raise RuntimeError("MockRuntime scripted error")
            yield ev

    async def cancel(self, run_id: str) -> None:
        self.cancelled_runs.add(run_id)

    async def get_state(self, thread_id: str) -> ThreadState:
        if thread_id in self._states:
            return self._states[thread_id]
        if self._strict_state:
            raise KeyError(f"unknown thread: {thread_id!r}")
        now = datetime.now(UTC)
        return ThreadState(
            thread_id=thread_id,
            user_id="mock-user",
            messages=[],
            created_at=now,
            updated_at=now,
        )


__all__ = ["MockRuntime"]
