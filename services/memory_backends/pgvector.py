"""pgvector-backed ``MemoryBackend`` for ``services.long_term_memory``.

Phase 2 of ``docs/plans/replace_mem0_pgvector.plan.md``. Replaces the
Mem0 backend with a first-party Postgres + pgvector implementation.

## Layering (plan §Architecture & TDD compliance)

* **Layer**: horizontal service (L2). Same slot the in-memory + mem0
  backends occupy.
* **AP-2 (horizontal-to-horizontal coupling)**: this backend does NOT
  import any other ``services/*`` module. It depends on
  ``services.long_term_memory`` for the Protocol types it implements,
  and on ``middleware.ports.embedding_client.EmbeddingClient`` —
  injected by constructor from the composition root. Per the plan,
  ports are framework-agnostic Protocols; services may consume them.
* **No langgraph/langchain** (AGENTS.md rule 4).
* **psycopg confinement** (architecture test, Phase 2.6): ``psycopg``
  may live in ``services/`` only under this file and the BFF thread
  store.

## Concurrency / pool kwargs (plan §Phase 0 R6)

We use a sync ``psycopg_pool.ConnectionPool`` with:
  * ``min_size=1, max_size=4`` — matches the BFF thread store sizing.
  * ``check=ConnectionPool.check_connection`` — REQUIRED on Cloud SQL
    Auth Proxy because idle connections silently reset after the
    proxy's keepalive window; the check reconnects before handing
    the conn to the caller.
  * ``autocommit=False`` — pgvector backend opens explicit transactions
    for upsert-then-embed; the BFF checkpointer keeps its own pool with
    ``autocommit=True`` (different transactional model).

The backend either receives a ready-made pool (tests) or builds its
own from the injected DSN. The pool is opened lazily on first use so
construction is side-effect-free.

## (user_id, key) ↔ row mapping

Schema:

    CREATE TABLE agent_memories (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id     TEXT NOT NULL,
        key         TEXT NOT NULL,
        payload     JSONB NOT NULL,
        metadata    JSONB NOT NULL,
        embed_text  TEXT NOT NULL,
        embedding   VECTOR(<dim>),
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (user_id, key)
    );

* ``put`` is upsert by ``(user_id, key)`` — embeds ``payload["text"]``
  (mirrors mem0/sqlite convention; if ``text`` is absent the payload's
  ``repr`` is embedded so search still works).
* ``get`` returns the four-field ``MemoryRecord`` — DB-side columns
  (``id``/``embedding``/``embed_text``/``created_at``) are dropped.
* ``search`` runs an HNSW kNN over the user's rows; the cosine score
  is written into the returned record's ``metadata["score"]`` (mirrors
  what ``LongTermMemoryService`` expects from the Mem0 backend).
* ``delete`` returns True iff a row matched.
* ``list_all`` returns all of a user's rows (A1 optional capability,
  used by consolidation/budget).

## Privacy invariant

Per ``services/long_term_memory.py:10``: payload **values** never appear
in log lines. This module logs only ``user_id`` / ``key`` / counts.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import psycopg
from psycopg_pool import ConnectionPool

from middleware.ports.embedding_client import (
    EmbeddingClient,
    EmbeddingClientError,
)
from services.long_term_memory import MemoryBackendError, MemoryRecord


logger = logging.getLogger("services.memory_backends.pgvector")


__all__ = ["PgVectorMemoryBackend", "DDL"]


# DDL is exposed as a constant so Phase 5's migration can import it
# instead of duplicating the column list. The ``{dim}`` placeholder is
# substituted from the embedding client's dimension at install time.
#
# Phase 4.5 (typed-memory P0 — schema-now / behavior-later, see
# ``docs/plans/typed_memory_searchability.design.md``): the DDL gains
# ``mem_type`` (write-derived shadow of ``metadata['type']``; indexed
# for R1 push-down) and a generated ``ts`` tsvector (NULL-safe via
# COALESCE, for future R4 hybrid lexical search). ``embedding`` stays
# nullable (schema-now for the deferred R2 procedural bypass), but
# ``put`` still embeds EVERY type — bypass is bound to R2.
DDL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS agent_memories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     TEXT NOT NULL,
    key         TEXT NOT NULL,
    mem_type    TEXT NOT NULL DEFAULT 'semantic',
    payload     JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    metadata    JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    embed_text  TEXT NOT NULL,
    embedding   VECTOR({dim}),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ts          tsvector GENERATED ALWAYS AS
                (to_tsvector('english', COALESCE(payload->>'text', '')))
                STORED,
    UNIQUE (user_id, key)
);

CREATE INDEX IF NOT EXISTS agent_memories_user_idx
    ON agent_memories (user_id);

CREATE INDEX IF NOT EXISTS agent_memories_user_type_idx
    ON agent_memories (user_id, mem_type);

CREATE INDEX IF NOT EXISTS agent_memories_hnsw_idx
    ON agent_memories USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS agent_memories_ts_idx
    ON agent_memories USING gin (ts);
"""


class PgVectorMemoryBackend:
    """``MemoryBackend`` Protocol implementation over Postgres + pgvector.

    Args:
        embedding_client: vendor-neutral embedding port. Its
            ``dimension`` MUST match the column type — a mismatch is
            detected at ``put`` time and raised as
            ``MemoryBackendError``.
        dsn: Postgres connection string. Mutually exclusive with
            ``pool``; tests typically pass ``pool``.
        pool: pre-built ``ConnectionPool``. Tests pass this for fast
            startup. Production passes ``dsn`` and lets the backend
            build the pool with the verified Cloud-SQL-proxy-safe
            kwargs.
        ensure_schema: when True (the default for tests via the Docker
            fixture), apply ``DDL`` on first use. In prod the SQL
            migration runs out-of-band — leave this False.
    """

    def __init__(
        self,
        *,
        embedding_client: EmbeddingClient,
        dsn: str | None = None,
        pool: ConnectionPool | None = None,
        ensure_schema: bool = False,
    ) -> None:
        if (dsn is None) == (pool is None):
            raise ValueError(
                "PgVectorMemoryBackend requires exactly one of dsn=... or pool=..."
            )
        if embedding_client.dimension <= 0:
            raise ValueError(
                f"embedding dimension must be positive, got {embedding_client.dimension}"
            )
        self._embedding_client = embedding_client
        self._dimension = embedding_client.dimension
        self._owns_pool = pool is None
        self._pool: ConnectionPool | None = pool
        self._dsn = dsn
        self._schema_applied = False
        self._ensure_schema = ensure_schema

    # ── infrastructure ───────────────────────────────────────────────

    def _get_pool(self) -> ConnectionPool:
        if self._pool is None:
            assert self._dsn is not None  # invariant from __init__
            # Pool kwargs per plan §Phase 0 R6 (verified against
            # agent_ui_adapter/adapters/runtime/postgres_saver.py:67-83).
            self._pool = ConnectionPool(
                self._dsn,
                min_size=1,
                max_size=4,
                check=ConnectionPool.check_connection,
                kwargs={"autocommit": False},
                open=True,
            )
        if self._ensure_schema and not self._schema_applied:
            self._apply_schema()
        return self._pool

    def _apply_schema(self) -> None:
        ddl = DDL.format(dim=self._dimension)
        assert self._pool is not None
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                # CREATE EXTENSION requires autocommit; flip per-conn.
                conn.autocommit = True
                cur.execute(ddl)
                conn.autocommit = False
        self._schema_applied = True

    def close(self) -> None:
        """Close the underlying pool if we own it. Idempotent."""
        if self._owns_pool and self._pool is not None:
            self._pool.close()
            self._pool = None

    # ── embedding helper ─────────────────────────────────────────────

    def _embed_sync(self, text: str) -> list[float]:
        """Run the (async) EmbeddingClient from a sync context.

        Two call contexts must both work:
          (a) Graph-side recall/store — invoked from a sync LangGraph
              node, no running event loop. ``asyncio.run`` is fine.
          (b) BFF /agent/memory CRUD — invoked from an ``async def``
              FastAPI handler, INSIDE a running event loop. There
              ``asyncio.run`` raises ``RuntimeError: asyncio.run()
              cannot be called from a running event loop``.

        The bridge detects a running loop and, if present, dispatches
        the coroutine factory to a worker thread that owns its own
        loop. The coroutine is constructed inside the worker (not in
        the caller's loop) so any internal awaitables bind to the
        worker's loop, not the caller's — eliminating the cross-loop
        trap entirely.
        """
        import asyncio
        import concurrent.futures

        def _runner() -> list[list[float]]:
            return asyncio.run(self._embedding_client.embed(texts=[text]))

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No running loop — sync caller (the graph node path).
            try:
                vectors = _runner()
            except EmbeddingClientError as exc:
                raise MemoryBackendError(
                    f"pgvector backend: embedding client failed ({exc})"
                ) from exc
        else:
            # We're inside a running loop (the BFF async route path).
            # Run the embed in a dedicated worker thread that owns its
            # own asyncio loop; .result() blocks until done. Single-use
            # executor so we never share loops across calls.
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                try:
                    vectors = ex.submit(_runner).result()
                except EmbeddingClientError as exc:
                    raise MemoryBackendError(
                        f"pgvector backend: embedding client failed ({exc})"
                    ) from exc
        if not vectors:
            raise MemoryBackendError(
                "pgvector backend: embedding client returned no vectors"
            )
        vec = vectors[0]
        if len(vec) != self._dimension:
            raise MemoryBackendError(
                f"pgvector backend: embed dim {len(vec)} != column dim {self._dimension}"
            )
        return vec

    @staticmethod
    def _embed_text_of(record: MemoryRecord) -> str:
        """The string we embed.

        Phase 4.5 (typed-memory P0) precedence — non-empty str
        ``embed_text`` wins (the future R3 writer will populate it),
        else non-empty str ``text``, else ``repr(payload)``. Empty
        strings or non-``str`` values at either field fall through;
        this mirrors the prior type-guard on ``text`` so ``embed_text``
        is NOT treated as authoritative when empty. Inert day one — no
        writer emits ``embed_text`` yet, so today this always resolves
        to ``text`` (or the repr fallback), byte-identical with Phase 2.
        """
        payload = record.payload or {}
        explicit = payload.get("embed_text")
        if isinstance(explicit, str) and explicit:
            return explicit
        text = payload.get("text")
        if isinstance(text, str) and text:
            return text
        return repr(payload)

    @staticmethod
    def _vec_literal(vec: list[float]) -> str:
        """pgvector wire format: ``'[0.1,0.2,...]'`` as a string the
        ``::vector`` cast accepts. Avoids the need for a SQLAlchemy
        type adapter — we stay on raw psycopg.
        """
        return "[" + ",".join(format(x, ".7g") for x in vec) + "]"

    # ── MemoryBackend Protocol ───────────────────────────────────────

    def put(self, record: MemoryRecord) -> None:
        embed_text = self._embed_text_of(record)
        embedding = self._embed_sync(embed_text)
        # Phase 4.5 (P0): write-derived shadow of ``metadata['type']`` into
        # the indexed ``mem_type`` column. Default ``'semantic'`` matches
        # the column default; never read at runtime (recall composition
        # still reads ``metadata['type']`` through LongTermMemoryService).
        metadata_dict = dict(record.metadata or {})
        mem_type_raw = metadata_dict.get("type", "semantic")
        mem_type = (
            mem_type_raw if isinstance(mem_type_raw, str) and mem_type_raw
            else "semantic"
        )
        pool = self._get_pool()
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO agent_memories
                            (user_id, key, mem_type, payload, metadata, embed_text, embedding)
                        VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::vector)
                        ON CONFLICT (user_id, key) DO UPDATE SET
                            mem_type   = EXCLUDED.mem_type,
                            payload    = EXCLUDED.payload,
                            metadata   = EXCLUDED.metadata,
                            embed_text = EXCLUDED.embed_text,
                            embedding  = EXCLUDED.embedding
                        """,
                        (
                            record.user_id,
                            record.key,
                            mem_type,
                            json.dumps(dict(record.payload or {})),
                            json.dumps(metadata_dict),
                            embed_text,
                            self._vec_literal(embedding),
                        ),
                    )
                conn.commit()
        except psycopg.Error as exc:
            raise MemoryBackendError(
                f"pgvector backend failed during put("
                f"user_id={record.user_id!r}, key={record.key!r})"
            ) from exc
        logger.info(
            "memory.backend.put user_id=%s key=%s", record.user_id, record.key
        )

    def get(self, user_id: str, key: str) -> MemoryRecord | None:
        pool = self._get_pool()
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT payload, metadata FROM agent_memories "
                        "WHERE user_id = %s AND key = %s",
                        (user_id, key),
                    )
                    row = cur.fetchone()
        except psycopg.Error as exc:
            raise MemoryBackendError(
                f"pgvector backend failed during get("
                f"user_id={user_id!r}, key={key!r})"
            ) from exc
        if row is None:
            return None
        payload, metadata = row
        return MemoryRecord(
            user_id=user_id,
            key=key,
            payload=payload or {},
            metadata=metadata or {},
        )

    def search(
        self, user_id: str, query: str, limit: int = 10
    ) -> list[MemoryRecord]:
        if limit <= 0:
            return []
        embedding = self._embed_sync(query)
        vec_lit = self._vec_literal(embedding)
        pool = self._get_pool()
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT key, payload, metadata,
                               1 - (embedding <=> %s::vector) AS score
                        FROM agent_memories
                        WHERE user_id = %s
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (vec_lit, user_id, vec_lit, limit),
                    )
                    rows = cur.fetchall()
        except psycopg.Error as exc:
            raise MemoryBackendError(
                f"pgvector backend failed during search(user_id={user_id!r})"
            ) from exc
        records: list[MemoryRecord] = []
        for key, payload, metadata, score in rows:
            # Cosine distance in pgvector is in [0,2]; score = 1 - dist
            # is in [-1,1]. Clamp to [0,1] for the MemoryClient/LongTermMemoryService
            # contract; identical vectors get score=1.0, orthogonal 0.5 etc.
            clamped = max(0.0, min(1.0, float(score)))
            meta = dict(metadata or {})
            meta["score"] = clamped
            records.append(
                MemoryRecord(
                    user_id=user_id,
                    key=key,
                    payload=payload or {},
                    metadata=meta,
                )
            )
        logger.debug(
            "memory.backend.search user_id=%s count=%d", user_id, len(records)
        )
        return records

    def delete(self, user_id: str, key: str) -> bool:
        pool = self._get_pool()
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM agent_memories "
                        "WHERE user_id = %s AND key = %s RETURNING id",
                        (user_id, key),
                    )
                    row = cur.fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise MemoryBackendError(
                f"pgvector backend failed during delete("
                f"user_id={user_id!r}, key={key!r})"
            ) from exc
        deleted = row is not None
        if deleted:
            logger.info(
                "memory.backend.delete user_id=%s key=%s", user_id, key
            )
        return deleted

    def list_all(self, user_id: str) -> list[MemoryRecord]:
        """All records for ``user_id`` (A1 optional capability)."""
        pool = self._get_pool()
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT key, payload, metadata FROM agent_memories "
                        "WHERE user_id = %s ORDER BY created_at",
                        (user_id,),
                    )
                    rows = cur.fetchall()
        except psycopg.Error as exc:
            raise MemoryBackendError(
                f"pgvector backend failed during list_all(user_id={user_id!r})"
            ) from exc
        return [
            MemoryRecord(
                user_id=user_id,
                key=key,
                payload=payload or {},
                metadata=metadata or {},
            )
            for key, payload, metadata in rows
        ]

    # ── context-manager ergonomics (matches SqliteMemoryBackend) ─────

    def __enter__(self) -> PgVectorMemoryBackend:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()
