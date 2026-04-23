"""Parametrized conformance test for every AgentRuntime implementation.

Per AGENT_UI_ADAPTER_SPRINTS.md US-3.4. Pattern 4 (Consumer-Driven
Contract): every implementation under adapters/runtime/ must satisfy the
AgentRuntime Protocol AND complete a minimal happy-path script without
raising.
"""

from __future__ import annotations

import pytest

from agent_ui_adapter.adapters.runtime.langgraph_runtime import LangGraphRuntime
from agent_ui_adapter.adapters.runtime.mock_runtime import MockRuntime
from agent_ui_adapter.ports.agent_runtime import AgentRuntime
from agent_ui_adapter.wire.domain_events import (
    RunFinishedDomain,
    RunStartedDomain,
)
from trust.models import AgentFacts


def _facts() -> AgentFacts:
    return AgentFacts(
        agent_id="a1", agent_name="Bot", owner="team", version="1.0.0"
    )


def _make_mock() -> AgentRuntime:
    return MockRuntime(
        events=[
            RunStartedDomain(trace_id="t", run_id="r", thread_id="th"),
            RunFinishedDomain(trace_id="t", run_id="r", thread_id="th"),
        ]
    )


def _make_langgraph() -> AgentRuntime:
    class _EmptyGraph:
        async def astream_events(self, input, config=None, version="v2"):
            if False:
                yield  # pragma: no cover

        async def aget_state(self, config):
            return None

    return LangGraphRuntime(graph=_EmptyGraph())


@pytest.mark.parametrize(
    "make_runtime",
    [_make_mock, _make_langgraph],
    ids=["MockRuntime", "LangGraphRuntime"],
)
class TestAgentRuntimeConformance:
    def test_satisfies_protocol(self, make_runtime) -> None:
        assert isinstance(make_runtime(), AgentRuntime)

    @pytest.mark.asyncio
    async def test_happy_path_run_completes_without_raising(
        self, make_runtime
    ) -> None:
        rt = make_runtime()
        out = []
        async for ev in rt.run(thread_id="t1", input={}, identity=_facts()):
            out.append(ev)
        # Conformance: every implementation MUST end with RunFinishedDomain.
        assert isinstance(out[-1], RunFinishedDomain) or out == [], (
            "Conformance: a runtime that yields anything must end with "
            "RunFinishedDomain (mock may yield empty list as edge case)."
        )

    @pytest.mark.asyncio
    async def test_cancel_does_not_raise(self, make_runtime) -> None:
        await make_runtime().cancel(run_id="r1")
