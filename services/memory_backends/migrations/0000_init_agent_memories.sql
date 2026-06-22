-- 0000_init_agent_memories.sql — initial schema for PgVectorMemoryBackend.
--
-- Mirrors the Phase 4.5 typed-memory superset DDL constant in
-- ``services/memory_backends/pgvector.py`` (the ``DDL`` module-level string).
-- That constant is the source of truth used by tests (Docker fixture applies
-- it on session startup); this file is the production-apply equivalent for
-- Cloud SQL via cloud-sql-proxy + psql.
--
-- Apply path (see docs/plans/replace_mem0_pgvector.plan.md §Phase 5 S1):
--   1) cloud-sql-proxy --port 5433 <INSTANCE_CONNECTION_NAME>
--   2) psql "postgresql://<USER>:<PASS>@127.0.0.1:5433/<DB>" -f \
--        services/memory_backends/migrations/0000_init_agent_memories.sql
--
-- Phase 4.5 (schema-now / behavior-later, per
-- ``docs/plans/typed_memory_searchability.design.md``):
--   * ``mem_type`` is the write-derived shadow of ``metadata['type']``,
--     indexed for future R1 type-filtered push-down. Default 'semantic'.
--   * ``ts`` is a generated tsvector (NULL-safe via COALESCE) for future R4
--     hybrid lexical search. Index is created but no reader is wired yet.
--   * ``embedding`` is nullable: schema-now affordance for the deferred R2
--     procedural-embedding bypass. ``put`` still embeds EVERY record today.
--   * ``embed_text`` is the text actually fed to the embedding client at
--     write time (precedence: payload.embed_text > payload.text > repr).
--
-- Dimension: 1536 matches the default OpenAI text-embedding-3-small via the
-- ``LiteLLMEmbeddingClient`` adapter; ``EMBEDDING_DIMENSION`` env in
-- composition root MUST match this column type. Changing models = re-embed
-- every row + column type change (a future re-migration, not handled here).
--
-- Idempotence: ``CREATE … IF NOT EXISTS`` throughout — re-running this file
-- against an already-migrated database is a no-op. The unique constraint
-- ``(user_id, key)`` is the upsert key for ``PgVectorMemoryBackend.put``.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS agent_memories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     TEXT NOT NULL,
    key         TEXT NOT NULL,
    mem_type    TEXT NOT NULL DEFAULT 'semantic',
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    embed_text  TEXT NOT NULL,
    embedding   VECTOR(1536),
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
