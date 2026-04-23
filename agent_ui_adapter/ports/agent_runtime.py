"""The single application-contract port: ``AgentRuntime``.

Per AGENT_UI_ADAPTER_PLAN.md §5.1. This module defines exactly ONE
``Protocol`` subclass (rule R9). All other cross-cutting concerns (memory,
trace, identity, authorization, tools) are consumed from existing
horizontal services in ``services/`` and passed in by the composition root.

A runtime adapter satisfies this Protocol by providing three async
methods:

- ``run`` — yields the canonical ``DomainEvent`` stream for one run
- ``cancel`` — best-effort cancel of an in-flight run
- ``get_state`` — return the current ``ThreadState`` for a thread

The Protocol is ``@runtime_checkable`` so ``isinstance(impl, AgentRuntime)``
works at runtime; the conformance test bundle uses this.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Protocol, runtime_checkable

from agent_ui_adapter.wire.agent_protocol import ThreadState
from agent_ui_adapter.wire.domain_events import DomainEvent
from trust.models import AgentFacts


@runtime_checkable
class AgentRuntime(Protocol):
    """Application-contract port for the outer adapter ring.

    Implementations live under ``agent_ui_adapter/adapters/runtime/``.
    The composition root (``agent_ui_adapter/server.py``) wires concrete
    horizontal services into the chosen adapter at construction time.
    """

    async def run(
        self,
        thread_id: str,
        input: dict[str, Any],
        identity: AgentFacts,
    ) -> AsyncIterator[DomainEvent]:
        """Execute one run for ``thread_id`` and yield canonical events.

        The translator (``translators/domain_to_ag_ui``) maps the yielded
        events into AG-UI events at the wire boundary. Every yielded event
        MUST carry ``trace_id`` per plan §4.3 Option B.
        """
        ...

    async def cancel(self, run_id: str) -> None:
        """Best-effort cancel of an in-flight run.

        Should be idempotent: cancelling an unknown or already-finished
        run is not an error.
        """
        ...

    async def get_state(self, thread_id: str) -> ThreadState:
        """Return the current persisted state for the thread."""
        ...


__all__ = ["AgentRuntime"]
