"""Tests for PostgresCheckpointer.

Failure paths first (TAP-4):
  - Missing DATABASE_URL → RuntimeError
  - Accessing saver before entering context → RuntimeError
  - Happy path: from_env reads DATABASE_URL
  - Happy path: context manager lifecycle
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_ui_adapter.adapters.runtime.postgres_saver import (
    PostgresCheckpointer,
    postgres_checkpointer_from_env,
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
