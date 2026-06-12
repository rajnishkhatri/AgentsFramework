"""PostgresCheckpointer: async Postgres-backed LangGraph checkpointer wrapper.

Shared adapter for cloud deployments (GCP Cloud SQL, AWS RDS, Azure
Flexible Server). Wraps ``langgraph-checkpoint-postgres``'s
``AsyncPostgresSaver`` with connection-pool lifecycle and a one-shot
``setup()`` migration helper.

The composition root selects this over ``AsyncSqliteSaver`` when
``GCP_EXECUTION_ENV`` (or equivalent cloud env var) is set.

Connections are managed by a ``psycopg_pool.AsyncConnectionPool`` with
``check=AsyncConnectionPool.check_connection``: Cloud SQL (and its Auth
Proxy) can reset idle TCP connections at any time, and a single
long-lived ``AsyncConnection`` never recovers from that — every
subsequent run fails with ``OperationalError: the connection is
closed``. The checkout health check discards dead connections and opens
fresh ones transparently.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

logger = logging.getLogger("agent_ui_adapter.adapters.runtime.postgres_saver")


class PostgresCheckpointer:
    """Manages an ``AsyncPostgresSaver`` lifecycle for Cloud Run.

    Usage in composition root::

        async with PostgresCheckpointer.from_env() as checkpointer:
            graph = build_graph(checkpointer=checkpointer.saver)
    """

    def __init__(self, connection_string: str) -> None:
        self._connection_string = connection_string
        self._saver = None
        self._pool = None

    @property
    def saver(self):
        """The underlying AsyncPostgresSaver instance (available after __aenter__)."""
        if self._saver is None:
            raise RuntimeError(
                "PostgresCheckpointer must be used as an async context manager"
            )
        return self._saver

    @classmethod
    def from_env(cls) -> PostgresCheckpointer:
        """Build from DATABASE_URL environment variable."""
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError(
                "DATABASE_URL environment variable is required for "
                "PostgresCheckpointer"
            )
        return cls(url)

    async def __aenter__(self) -> PostgresCheckpointer:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        # Connection kwargs mirror AsyncPostgresSaver.from_conn_string:
        # autocommit + prepare_threshold=0 are required by the saver's
        # migration/query code, dict_row by its row handling.
        self._pool = AsyncConnectionPool(
            self._connection_string,
            min_size=1,
            max_size=4,
            open=False,
            check=AsyncConnectionPool.check_connection,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
        )
        await self._pool.open(wait=True)
        self._saver = AsyncPostgresSaver(self._pool)
        await self._saver.setup()
        logger.info("PostgresCheckpointer: pool opened and migrations applied")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
        elif self._saver is not None:
            # Defensive cleanup for a saver attached without the pool
            # (e.g. injected directly in tests): close any connection it
            # holds. The normal path delegates closing to ``_pool``.
            conn = getattr(self._saver, "conn", None)
            if conn is not None:
                await conn.close()
        self._saver = None
        logger.info("PostgresCheckpointer: connection pool closed")


@asynccontextmanager
async def postgres_checkpointer_from_env() -> AsyncIterator[PostgresCheckpointer]:
    """Convenience async context manager for composition roots."""
    cp = PostgresCheckpointer.from_env()
    async with cp as instance:
        yield instance


__all__ = ["PostgresCheckpointer", "postgres_checkpointer_from_env"]
