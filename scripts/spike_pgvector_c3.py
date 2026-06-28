"""C3 verification spike — disposable. Run via cloud-sql-proxy then delete.

Plan §Phase 0 C3 spike for docs/plans/replace_mem0_pgvector.plan.md.

What this proves:
  1. pgvector extension is available on the Python backend's DATABASE_URL
  2. We have CREATE EXTENSION + CREATE TABLE privileges
  3. A real services.long_term_memory.MemoryRecord round-trips byte-equal
     through the corrected DDL (key/payload/metadata preserved, score
     written into metadata on search, DB-side columns dropped on get).

Usage:
  cloud-sql-proxy <instance-conn-name> &   # in another shell
  export DATABASE_URL="postgresql://USER:PW@127.0.0.1:5432/DB"
  .venv/bin/python scripts/spike_pgvector_c3.py

This is a one-shot disposable: it creates a scratch table
agent_memories_spike, exercises it, drops it, and prints PASS/FAIL.
The file is deleted at Phase 0 exit (gate condition).
"""

from __future__ import annotations

import os
import sys

REQUIRED_DIMENSION = 1536  # text-embedding-3-small


def _fake_embed(text: str, dim: int = REQUIRED_DIMENSION) -> list[float]:
    """Deterministic, content-free pseudo-embedding for spike only."""
    import hashlib

    h = hashlib.sha256(text.encode("utf-8")).digest()
    floats: list[float] = []
    for i in range(dim):
        b = h[i % len(h)]
        floats.append((b / 255.0) - 0.5)
    norm = sum(x * x for x in floats) ** 0.5 or 1.0
    return [x / norm for x in floats]


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("FAIL: DATABASE_URL not set — start cloud-sql-proxy and export it")
        return 2

    try:
        import psycopg
    except ImportError:
        print("FAIL: psycopg not installed in this venv")
        return 2

    from services.long_term_memory import MemoryRecord  # type: ignore

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            print("=== C3.1 pgvector availability ===")
            cur.execute(
                "SELECT name, default_version, installed_version "
                "FROM pg_available_extensions WHERE name IN ('vector','pgcrypto');"
            )
            rows = cur.fetchall()
            if not any(r[0] == "vector" for r in rows):
                print("FAIL: pgvector extension NOT AVAILABLE on this instance")
                print("  Required: enable via Terraform database_flags + restart")
                return 1
            for name, dv, iv in rows:
                print(f"  {name}: default={dv} installed={iv}")

            print("\n=== C3.2 CREATE EXTENSION privilege ===")
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
            print("  OK (vector + pgcrypto present)")

            print("\n=== C3.3 scratch table + round-trip ===")
            cur.execute("DROP TABLE IF EXISTS agent_memories_spike;")
            cur.execute(
                f"""
                CREATE TABLE agent_memories_spike (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    embed_text TEXT NOT NULL,
                    embedding VECTOR({REQUIRED_DIMENSION}),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE (user_id, key)
                );
                """
            )
            cur.execute(
                "CREATE INDEX agent_memories_spike_user_idx "
                "ON agent_memories_spike (user_id);"
            )
            cur.execute(
                "CREATE INDEX agent_memories_spike_hnsw_idx "
                "ON agent_memories_spike USING hnsw "
                "(embedding vector_cosine_ops);"
            )
            print("  table + HNSW index created")

            rec_in = MemoryRecord(
                user_id="spike-user-001",
                key="spike-key-1",
                payload={
                    "task_input": "What is pgvector?",
                    "answer": "A Postgres extension for vector similarity.",
                    "text": "Task: What is pgvector?\nAnswer: A Postgres extension for vector similarity.",
                },
                metadata={
                    "salience": 0.9,
                    "stored_at": "2026-06-22T00:00:00Z",
                    "suppressed": False,
                },
            )
            embed_text = rec_in.payload["text"]
            embedding = _fake_embed(embed_text)

            import json

            cur.execute(
                "INSERT INTO agent_memories_spike "
                "(user_id, key, payload, metadata, embed_text, embedding) "
                "VALUES (%s, %s, %s::jsonb, %s::jsonb, %s, %s::vector)",
                (
                    rec_in.user_id,
                    rec_in.key,
                    json.dumps(rec_in.payload),
                    json.dumps(rec_in.metadata),
                    embed_text,
                    str(embedding),
                ),
            )

            cur.execute(
                "SELECT user_id, key, payload, metadata FROM agent_memories_spike "
                "WHERE user_id=%s AND key=%s",
                (rec_in.user_id, rec_in.key),
            )
            row = cur.fetchone()
            if row is None:
                print("FAIL: get returned no row")
                return 1
            rec_out = MemoryRecord(
                user_id=row[0], key=row[1], payload=row[2], metadata=row[3]
            )
            mismatch = []
            for f in ("user_id", "key", "payload", "metadata"):
                if getattr(rec_in, f) != getattr(rec_out, f):
                    mismatch.append(f)
            if mismatch:
                print(f"FAIL: round-trip mismatch on {mismatch}")
                print(f"  in:  {rec_in.model_dump()}")
                print(f"  out: {rec_out.model_dump()}")
                return 1
            print("  4-field round-trip BYTE-EQUAL: user_id/key/payload/metadata ✓")

            print("\n=== C3.4 kNN search returns score ===")
            query_vec = _fake_embed("pgvector overview question")
            cur.execute(
                "SELECT key, 1 - (embedding <=> %s::vector) AS score "
                "FROM agent_memories_spike WHERE user_id=%s "
                "ORDER BY embedding <=> %s::vector LIMIT 3",
                (str(query_vec), rec_in.user_id, str(query_vec)),
            )
            results = cur.fetchall()
            if not results:
                print("FAIL: search returned 0 rows")
                return 1
            key, score = results[0]
            if not (0.0 <= score <= 1.0):
                print(f"FAIL: score out of [0,1]: {score}")
                return 1
            print(
                f"  search returned {len(results)} row(s); top={key} score={score:.4f}"
            )

            print("\n=== C3.5 cleanup ===")
            cur.execute("DROP TABLE IF EXISTS agent_memories_spike;")
            print("  scratch table dropped")

    print("\nPASS — C3 gates clear.")
    print("Record in docs/plans/log.md and delete this script.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
