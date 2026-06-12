"""L2 Contract: LangGraphRuntime.run resume mode (Phase 4).

The soft-gate edit round trip needs the stream path to continue a paused
thread: ``input={"_resume": True}`` must replay from the checkpoint via
``astream_events(None, config)`` with the run's ORIGINAL trace_id recovered
from the checkpoint (F-R7: a trace_id is minted exactly once per run).
Failure paths first (TAP-4): no checkpoint, completed run, unseeded state.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from agent_ui_adapter.adapters.runtime.langgraph_runtime import LangGraphRuntime
from agent_ui_adapter.wire.domain_events import (
    RunFinishedDomain,
    RunStartedDomain,
    TaskUnderstood,
)
from trust.models import AgentFacts


class _FakeResumableGraph:
    """Fake compiled app recording the resume invocation."""

    def __init__(self, *, snapshot: Any, scripted: list[dict] | None = None) -> None:
        self._snapshot = snapshot
        self._scripted = scripted or []
        self.stream_calls: list[tuple[Any, dict]] = []

    async def astream_events(self, input, config=None, version="v2"):
        self.stream_calls.append((input, config or {}))
        for ev in self._scripted:
            yield ev

    async def aget_state(self, config):
        return self._snapshot


def _facts() -> AgentFacts:
    return AgentFacts(
        agent_id="a1", agent_name="Bot", owner="team", version="1.0.0"
    )


def _snapshot(
    *,
    workflow_id: str = "trace-original",
    task_id: str = "task-original",
    next_nodes: tuple = ("execute_tool",),
) -> Any:
    return SimpleNamespace(
        values={"workflow_id": workflow_id, "task_id": task_id},
        next=next_nodes,
    )


async def _drain(rt: LangGraphRuntime, *, thread_id: str = "t1") -> list:
    return [
        ev
        async for ev in rt.run(
            thread_id=thread_id, input={"_resume": True}, identity=_facts()
        )
    ]


class TestRunResumeFailures:
    @pytest.mark.asyncio
    async def test_no_checkpoint_raises_key_error(self):
        rt = LangGraphRuntime(graph=_FakeResumableGraph(snapshot=None))
        with pytest.raises(KeyError):
            await _drain(rt)

    @pytest.mark.asyncio
    async def test_completed_run_raises_runtime_error(self):
        """Resuming a finished thread is an explicit error, not a rerun."""
        rt = LangGraphRuntime(
            graph=_FakeResumableGraph(snapshot=_snapshot(next_nodes=()))
        )
        with pytest.raises(RuntimeError, match="completed"):
            await _drain(rt)

    @pytest.mark.asyncio
    async def test_checkpoint_without_workflow_id_raises_value_error(self):
        """A checkpoint the runtime never seeded has no trace to continue."""
        snapshot = SimpleNamespace(values={"messages": []}, next=("route",))
        rt = LangGraphRuntime(graph=_FakeResumableGraph(snapshot=snapshot))
        with pytest.raises(ValueError, match="workflow_id"):
            await _drain(rt)


class TestRunResumeHappyPath:
    @pytest.mark.asyncio
    async def test_streams_none_input_with_recovered_trace_id(self):
        graph = _FakeResumableGraph(snapshot=_snapshot())
        rt = LangGraphRuntime(graph=graph)
        out = await _drain(rt)

        assert isinstance(out[0], RunStartedDomain)
        # F-R7: the resumed stream carries the run's ORIGINAL trace_id.
        assert out[0].trace_id == "trace-original"
        assert isinstance(out[-1], RunFinishedDomain)
        assert out[-1].error is None
        assert out[-1].trace_id == "trace-original"

        # Canonical checkpoint resume: graph input is None, not a dict.
        assert len(graph.stream_calls) == 1
        graph_input, config = graph.stream_calls[0]
        assert graph_input is None
        configurable = config["configurable"]
        assert configurable["thread_id"] == "t1"
        assert configurable["trace_id"] == "trace-original"
        assert configurable["task_id"] == "task-original"

    @pytest.mark.asyncio
    async def test_resume_reemits_edited_understanding_card(self):
        """The per-run dedupe cache resets, so the user_edited artifact
        re-emits on the first post-resume route pass (the card re-renders
        with the edited content)."""
        edited = {
            "restated_intent": "Corrected intent.",
            "success_conditions": ["edited condition a", "edited condition b"],
            "confidence": 0.9,
            "source": "user_edited",
            "model": "gpt-4o-mini",
        }
        scripted = [
            {
                "event": "on_chain_end",
                "name": "route",
                "run_id": "lc-1",
                "data": {"output": {"task_understanding": edited}},
            }
        ]
        graph = _FakeResumableGraph(snapshot=_snapshot(), scripted=scripted)
        rt = LangGraphRuntime(graph=graph)
        # Simulate stale dedupe state from the paused run.
        rt._last_task_understanding = edited

        out = await _drain(rt)
        cards = [ev for ev in out if isinstance(ev, TaskUnderstood)]
        assert len(cards) == 1
        assert cards[0].source == "user_edited"
        assert cards[0].success_conditions == [
            "edited condition a",
            "edited condition b",
        ]

    @pytest.mark.asyncio
    async def test_resume_sentinel_never_reaches_graph_input(self):
        """``_resume`` is adapter-internal; in non-resume runs it must not
        leak into graph state either."""
        graph = _FakeResumableGraph(snapshot=_snapshot())
        rt = LangGraphRuntime(graph=graph)
        async for _ in rt.run(
            thread_id="t1", input={"task_input": "hi", "_resume": False},
            identity=_facts(),
        ):
            pass
        graph_input, _config = graph.stream_calls[0]
        assert isinstance(graph_input, dict)
        assert "_resume" not in graph_input
