"""Tests for PostgresCheckpointer.

Failure paths first (TAP-4):
  - Missing DATABASE_URL → RuntimeError
  - Accessing saver before entering context → RuntimeError
  - Happy path: from_env reads DATABASE_URL
  - Happy path: context manager lifecycle
  - Resilience: pool checkout health check discards server-closed
    connections (Cloud SQL "connection reset by peer" → OperationalError)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_ui_adapter.adapters.runtime.postgres_saver import (
    PostgresCheckpointer,
)


class TestPostgresCheckpointerFailurePaths:
    def test_from_env_missing_database_url_raises(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(RuntimeError, match="DATABASE_URL"):
                PostgresCheckpointer.from_env()

    def test_saver_before_context_raises(self) -> None:
        cp = PostgresCheckpointer("postgresql://localhost/test")
        with pytest.raises(RuntimeError, match="async context manager"):
            _ = cp.saver


class TestPostgresCheckpointerHappyPath:
    def test_from_env_reads_database_url(self) -> None:
        url = "postgresql://user:pass@host:5432/db"
        with patch.dict("os.environ", {"DATABASE_URL": url}):
            cp = PostgresCheckpointer.from_env()
        assert cp._connection_string == url

    @pytest.mark.asyncio
    async def test_context_manager_calls_setup(self) -> None:
        mock_saver = AsyncMock()
        mock_saver.setup = AsyncMock()
        mock_saver.conn = None

        with patch(
            "agent_ui_adapter.adapters.runtime.postgres_saver.PostgresCheckpointer.__aenter__"
        ) as mock_enter:
            cp = PostgresCheckpointer("postgresql://localhost/test")
            cp._saver = mock_saver

            # Verify saver is accessible after manual _saver assignment
            assert cp.saver is mock_saver

    @pytest.mark.asyncio
    async def test_exit_clears_saver(self) -> None:
        cp = PostgresCheckpointer("postgresql://localhost/test")
        cp._saver = MagicMock()
        cp._saver.conn = None

        await cp.__aexit__(None, None, None)
        assert cp._saver is None

    @pytest.mark.asyncio
    async def test_exit_closes_connection_if_present(self) -> None:
        cp = PostgresCheckpointer("postgresql://localhost/test")
        mock_conn = AsyncMock()
        cp._saver = MagicMock()
        cp._saver.conn = mock_conn

        await cp.__aexit__(None, None, None)
        mock_conn.close.assert_called_once()


class TestPostgresCheckpointerPoolResilience:
    """The checkpointer must survive Cloud SQL resetting connections.

    Observed in prod (2026-06-12): the Auth Proxy logged "connection reset
    by peer" and every subsequent run failed with OperationalError until
    the Cloud Run instance recycled. The fix is a connection pool with a
    checkout health check instead of one process-lifetime connection.
    """

    @pytest.mark.asyncio
    async def test_aenter_builds_pool_with_checkout_health_check(self) -> None:
        pool_cls = MagicMock()
        pool = AsyncMock()
        pool_cls.return_value = pool
        saver_cls = MagicMock()
        saver_cls.return_value.setup = AsyncMock()

        with (
            patch("psycopg_pool.AsyncConnectionPool", pool_cls),
            patch("langgraph.checkpoint.postgres.aio.AsyncPostgresSaver", saver_cls),
        ):
            cp = PostgresCheckpointer("postgresql://localhost/test")
            await cp.__aenter__()

        args, kwargs = pool_cls.call_args
        assert args == ("postgresql://localhost/test",)
        # The health check is the actual fix: without it a dead connection
        # is handed out forever.
        assert kwargs["check"] is pool_cls.check_connection
        assert kwargs["open"] is False
        # AsyncPostgresSaver requires these connection settings.
        assert kwargs["kwargs"]["autocommit"] is True
        assert kwargs["kwargs"]["prepare_threshold"] == 0
        pool.open.assert_awaited_once_with(wait=True)
        saver_cls.assert_called_once_with(pool)
        saver_cls.return_value.setup.assert_awaited_once()
        assert cp.saver is saver_cls.return_value

    @pytest.mark.asyncio
    async def test_aexit_closes_pool(self) -> None:
        cp = PostgresCheckpointer("postgresql://localhost/test")
        pool = AsyncMock()
        cp._pool = pool
        cp._saver = MagicMock()

        await cp.__aexit__(None, None, None)

        pool.close.assert_awaited_once()
        assert cp._pool is None
        assert cp._saver is None

    @pytest.mark.asyncio
    async def test_health_check_rejects_server_closed_connection(self) -> None:
        """check_connection must raise for a connection Cloud SQL reset,
        so the pool discards it instead of handing it to a run."""
        import psycopg
        from psycopg_pool import AsyncConnectionPool

        dead_conn = AsyncMock()
        dead_conn.autocommit = True
        dead_conn.execute.side_effect = psycopg.OperationalError(
            "the connection is closed"
        )

        with pytest.raises(psycopg.OperationalError):
            await AsyncConnectionPool.check_connection(dead_conn)

    @pytest.mark.asyncio
    async def test_health_check_passes_live_connection(self) -> None:
        from psycopg_pool import AsyncConnectionPool

        live_conn = AsyncMock()
        live_conn.autocommit = True
        live_conn.execute.return_value = None

        await AsyncConnectionPool.check_connection(live_conn)
        live_conn.execute.assert_awaited_once()
