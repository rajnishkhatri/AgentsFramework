"""Checkpoint wiring regressions: ``build_graph(checkpointer=...)``.

Tracks the production bug where ``AsyncSqliteSaver.from_conn_string(...)`` was
passed to ``build_graph`` without entering its ``async with`` block, producing
the runtime error::

    AttributeError: '_AsyncGeneratorContextManager' object has no attribute
                    'get_next_version'

The fix in ``orchestration.react_loop._ensure_checkpoint_saver_instance``
short-circuits with a clear ``TypeError`` instead of letting LangGraph's
internals fail far from the cause.

Test layout (D3 / TAP-4 -- balance rejection and acceptance tests):

* ``TestEnsureCheckpointSaverInstance`` -- pure unit tests against the helper.
* ``TestBuildGraphRejectsBareContextManager`` -- regression rejection tests.
* ``TestBuildGraphAcceptsValidCheckpointers`` -- acceptance baseline so the
  validator can never grow stricter than the public LangGraph savers and our
  own ``InstrumentedCheckpointer`` wrapper.
* ``TestErrorMessageActionability`` -- the ``TypeError`` text must name both
  saver classes and show the correct ``async with`` / ``with`` syntax.
"""

from __future__ import annotations

from typing import Any

import pytest
from langgraph.checkpoint.memory import MemorySaver
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
except ModuleNotFoundError:  # optional dependency in some local envs
    SqliteSaver = None  # type: ignore[assignment]
try:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
except ModuleNotFoundError:  # optional dependency in some local envs
    AsyncSqliteSaver = None  # type: ignore[assignment]

from orchestration.react_loop import (
    _ensure_checkpoint_saver_instance,
    build_graph,
)
from services.base_config import AgentConfig, ModelProfile
from services.observability import FrameworkTelemetry
from orchestration.checkpointer_wrapper import InstrumentedCheckpointer


# ── Shared fixtures ───────────────────────────────────────────────────


def _minimal_agent_config() -> AgentConfig:
    return AgentConfig(
        default_model="gpt-4o-mini",
        models=[
            ModelProfile(
                name="gpt-4o-mini",
                litellm_id="openai/gpt-4o-mini",
                tier="fast",
                context_window=128000,
                cost_per_1k_input=0.00015,
                cost_per_1k_output=0.0006,
            )
        ],
    )


class _SaverStub:
    """Minimal duck-type that satisfies ``_ensure_checkpoint_saver_instance``.

    LangGraph's pregel loop only requires ``get_next_version`` to be callable
    on the checkpointer object before compile; the helper checks exactly that.
    """

    def get_next_version(self, *args: Any, **kwargs: Any) -> int:
        return 1


# ── Helper unit tests (fast, no LangGraph compilation) ────────────────


class TestEnsureCheckpointSaverInstance:
    """Pure unit tests for ``_ensure_checkpoint_saver_instance``."""

    def test_passes_for_memory_saver(self) -> None:
        _ensure_checkpoint_saver_instance(MemorySaver())

    def test_passes_for_instrumented_wrapper(self) -> None:
        wrapper = InstrumentedCheckpointer(MemorySaver(), FrameworkTelemetry())
        _ensure_checkpoint_saver_instance(wrapper)

    def test_passes_for_duck_typed_saver(self) -> None:
        _ensure_checkpoint_saver_instance(_SaverStub())

    @pytest.mark.skipif(
        AsyncSqliteSaver is None,
        reason="langgraph sqlite checkpointer extras not installed",
    )
    def test_rejects_unentered_async_sqlite_context_manager(
        self, tmp_path
    ) -> None:
        cm = AsyncSqliteSaver.from_conn_string(str(tmp_path / "a.db"))
        with pytest.raises(TypeError):
            _ensure_checkpoint_saver_instance(cm)

    @pytest.mark.skipif(
        SqliteSaver is None,
        reason="langgraph sqlite checkpointer extras not installed",
    )
    def test_rejects_unentered_sync_sqlite_context_manager(
        self, tmp_path
    ) -> None:
        cm = SqliteSaver.from_conn_string(str(tmp_path / "s.db"))
        with pytest.raises(TypeError):
            _ensure_checkpoint_saver_instance(cm)

    def test_rejects_arbitrary_object_without_get_next_version(self) -> None:
        with pytest.raises(TypeError):
            _ensure_checkpoint_saver_instance(object())

    def test_rejects_object_where_attribute_is_not_callable(self) -> None:
        class NotCallable:
            get_next_version = "not a function"

        with pytest.raises(TypeError):
            _ensure_checkpoint_saver_instance(NotCallable())


# ── build_graph rejection regressions ─────────────────────────────────


class TestBuildGraphRejectsBareContextManager:
    """The original production bug: bare ``from_conn_string(...)`` reached
    LangGraph and crashed with ``AttributeError: ... get_next_version``.
    """

    @pytest.mark.skipif(
        AsyncSqliteSaver is None,
        reason="langgraph sqlite checkpointer extras not installed",
    )
    def test_rejects_unentered_async_sqlite_saver(self, tmp_path) -> None:
        cm = AsyncSqliteSaver.from_conn_string(str(tmp_path / "c.db"))
        with pytest.raises(TypeError, match="async with AsyncSqliteSaver"):
            build_graph(
                agent_config=_minimal_agent_config(),
                cache_dir=tmp_path / "cache",
                checkpointer=cm,
            )

    @pytest.mark.skipif(
        SqliteSaver is None,
        reason="langgraph sqlite checkpointer extras not installed",
    )
    def test_rejects_unentered_sync_sqlite_saver(self, tmp_path) -> None:
        cm = SqliteSaver.from_conn_string(str(tmp_path / "s.db"))
        with pytest.raises(TypeError, match="with SqliteSaver"):
            build_graph(
                agent_config=_minimal_agent_config(),
                cache_dir=tmp_path / "cache",
                checkpointer=cm,
            )


# ── build_graph acceptance baseline ───────────────────────────────────


class TestBuildGraphAcceptsValidCheckpointers:
    """TAP-4 (Gap Blindness): pin the positive path so the validator can
    never grow stricter than the public LangGraph savers + our wrapper.
    """

    def test_accepts_none_checkpointer(self, tmp_path) -> None:
        graph = build_graph(
            agent_config=_minimal_agent_config(),
            cache_dir=tmp_path / "cache",
            checkpointer=None,
        )
        assert graph is not None

    def test_accepts_memory_saver(self, tmp_path) -> None:
        graph = build_graph(
            agent_config=_minimal_agent_config(),
            cache_dir=tmp_path / "cache",
            checkpointer=MemorySaver(),
        )
        assert graph is not None

    @pytest.mark.skipif(
        SqliteSaver is None,
        reason="langgraph sqlite checkpointer extras not installed",
    )
    def test_accepts_entered_sync_sqlite_saver(self, tmp_path) -> None:
        with SqliteSaver.from_conn_string(str(tmp_path / "ok.db")) as saver:
            graph = build_graph(
                agent_config=_minimal_agent_config(),
                cache_dir=tmp_path / "cache",
                checkpointer=saver,
            )
            assert graph is not None

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        AsyncSqliteSaver is None,
        reason="langgraph sqlite checkpointer extras not installed",
    )
    async def test_accepts_entered_async_sqlite_saver(self, tmp_path) -> None:
        async with AsyncSqliteSaver.from_conn_string(
            str(tmp_path / "ok-async.db")
        ) as saver:
            graph = build_graph(
                agent_config=_minimal_agent_config(),
                cache_dir=tmp_path / "cache",
                checkpointer=saver,
            )
            assert graph is not None

    def test_accepts_instrumented_checkpointer_wrapper(self, tmp_path) -> None:
        wrapper = InstrumentedCheckpointer(MemorySaver(), FrameworkTelemetry())
        graph = build_graph(
            agent_config=_minimal_agent_config(),
            cache_dir=tmp_path / "cache",
            checkpointer=wrapper,
        )
        assert graph is not None

    def test_interrupt_before_execute_tool_false_still_compiles(self, tmp_path) -> None:
        """Dev middleware passes this so tool nodes run instead of pausing (HITL)."""
        graph = build_graph(
            agent_config=_minimal_agent_config(),
            cache_dir=tmp_path / "cache",
            checkpointer=MemorySaver(),
            interrupt_before_execute_tool=False,
        )
        assert graph is not None


# ── Error-message actionability ───────────────────────────────────────


class TestErrorMessageActionability:
    """The error message must point users at the fix without further reading.

    A buried "no attribute 'get_next_version'" message would re-introduce the
    original support burden.
    """

    @pytest.mark.skipif(
        AsyncSqliteSaver is None,
        reason="langgraph sqlite checkpointer extras not installed",
    )
    def test_message_mentions_async_with_syntax(self, tmp_path) -> None:
        cm = AsyncSqliteSaver.from_conn_string(str(tmp_path / "x.db"))
        with pytest.raises(TypeError) as excinfo:
            _ensure_checkpoint_saver_instance(cm)
        msg = str(excinfo.value)
        assert "async with AsyncSqliteSaver.from_conn_string" in msg
        assert "as saver" in msg

    @pytest.mark.skipif(
        SqliteSaver is None,
        reason="langgraph sqlite checkpointer extras not installed",
    )
    def test_message_mentions_sync_with_syntax(self, tmp_path) -> None:
        cm = SqliteSaver.from_conn_string(str(tmp_path / "y.db"))
        with pytest.raises(TypeError) as excinfo:
            _ensure_checkpoint_saver_instance(cm)
        msg = str(excinfo.value)
        assert "with SqliteSaver.from_conn_string" in msg
        assert "as saver" in msg

    @pytest.mark.skipif(
        AsyncSqliteSaver is None,
        reason="langgraph sqlite checkpointer extras not installed",
    )
    def test_message_calls_out_unentered_context_manager(
        self, tmp_path
    ) -> None:
        cm = AsyncSqliteSaver.from_conn_string(str(tmp_path / "z.db"))
        with pytest.raises(TypeError) as excinfo:
            _ensure_checkpoint_saver_instance(cm)
        assert "unentered" in str(excinfo.value)
