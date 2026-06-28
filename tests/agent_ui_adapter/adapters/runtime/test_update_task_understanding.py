"""L2 Contract: LangGraphRuntime.update_task_understanding (Phase 4).

The edit seam: validate thread + trace echo, write the user_edited artifact
via ``aupdate_state``, return (old, new) for the caller's PARAMETER_CHANGED
hashes. Failure paths first (TAP-4): unknown thread, trace mismatch,
completed run.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from agent_ui_adapter.adapters.runtime.langgraph_runtime import LangGraphRuntime


class _FakeGraph:
    def __init__(self, *, snapshot: Any) -> None:
        self._snapshot = snapshot
        self.updates: list[tuple[dict, dict]] = []

    async def aget_state(self, config: dict) -> Any:
        return self._snapshot

    async def aupdate_state(self, config: dict, values: dict) -> None:
        self.updates.append((config, values))


def _snapshot(
    *,
    workflow_id: str = "tr-1",
    next_nodes: tuple = ("execute_tool",),
    understanding: dict | None = None,
) -> Any:
    return SimpleNamespace(
        values={
            "workflow_id": workflow_id,
            "task_understanding": understanding
            or {
                "restated_intent": "old intent",
                "success_conditions": ["old condition a", "old condition b"],
                "confidence": 0.7,
                "source": "generated",
                "model": "gpt-4o-mini",
            },
        },
        next=next_nodes,
    )


_EDIT = {
    "restated_intent": "Create the file and verify it.",
    "success_conditions": ["file exists", "contents verified"],
}


class TestUpdateTaskUnderstanding:
    @pytest.mark.asyncio
    async def test_unknown_thread_raises_key_error(self):
        rt = LangGraphRuntime(graph=_FakeGraph(snapshot=None))
        with pytest.raises(KeyError):
            await rt.update_task_understanding(
                thread_id="missing", trace_id="tr-1", **_EDIT
            )

    @pytest.mark.asyncio
    async def test_trace_id_mismatch_raises_value_error(self):
        """F-R7: the edit must echo the run's trace_id verbatim."""
        rt = LangGraphRuntime(graph=_FakeGraph(snapshot=_snapshot(workflow_id="tr-1")))
        with pytest.raises(ValueError, match="trace_id"):
            await rt.update_task_understanding(
                thread_id="t1", trace_id="tr-WRONG", **_EDIT
            )

    @pytest.mark.asyncio
    async def test_completed_run_raises_runtime_error(self):
        """Edit after completion is a no-op with an explicit error."""
        rt = LangGraphRuntime(graph=_FakeGraph(snapshot=_snapshot(next_nodes=())))
        with pytest.raises(RuntimeError, match="completed"):
            await rt.update_task_understanding(thread_id="t1", trace_id="tr-1", **_EDIT)

    @pytest.mark.asyncio
    async def test_happy_path_writes_user_edited_and_returns_old_new(self):
        graph = _FakeGraph(snapshot=_snapshot())
        rt = LangGraphRuntime(graph=graph)
        old, new = await rt.update_task_understanding(
            thread_id="t1", trace_id="tr-1", **_EDIT
        )
        assert old["source"] == "generated"
        assert old["success_conditions"] == ["old condition a", "old condition b"]
        assert new["source"] == "user_edited"
        assert new["success_conditions"] == ["file exists", "contents verified"]
        assert new["restated_intent"] == "Create the file and verify it."
        # The write went through aupdate_state on the right thread.
        assert len(graph.updates) == 1
        config, values = graph.updates[0]
        assert config["configurable"]["thread_id"] == "t1"
        assert values["task_understanding"]["source"] == "user_edited"
