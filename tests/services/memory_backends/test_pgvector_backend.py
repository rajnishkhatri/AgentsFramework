"""L2 contract-driven tests for ``services/memory_backends/pgvector.py``.

Per ``docs/plans/replace_mem0_pgvector.plan.md`` §Phase 2:

  * **Pyramid layer**: L2 Reproducible Reality — Protocol B (real
    pgvector Docker fixture + ``FakeEmbeddingClient``).
  * **Failure-paths-first** (AGENTS.md §Testing Rules / TAP-4):
    rejection tests precede acceptance tests. No live LLM in CI
    (we never call the real ``LiteLLMEmbeddingClient`` here).
  * **TAP-3 (determinism theater)**: assert ordering + bounds, NEVER
    exact float values.
  * **Consumer-driven contract** (Pattern 4): the conformance class
    re-runs core scenarios against both ``InMemoryMemoryBackend`` and
    ``PgVectorMemoryBackend`` — same Protocol, same behaviour. If a
    contract test fails on pgvector but passes on in-memory, the
    backend is wrong (do not patch the test).

## Docker fixture posture

The fixture connects to a pgvector container at
``localhost:55432`` (booted out-of-band by the implementing agent —
``docker run -d --name agentfw-pgvector-dev -p 55432:5432 ...``).
If the container is unreachable, the whole module is **skipped** —
this keeps the suite CI-friendly when Docker is not available.

Each test runs against a fresh table (``TRUNCATE`` between tests, not
``DROP TABLE``, so HNSW index survives — much faster across the suite).
"""

from __future__ import annotations

import os
from typing import Iterator

import pytest

from middleware.adapters.embedding.fake import FakeEmbeddingClient
from services.long_term_memory import (
    InMemoryMemoryBackend,
    MemoryBackend,
    MemoryBackendError,
    MemoryRecord,
)


# Default points at the agent's dev container. Override via env for CI.
PGVECTOR_DSN = os.environ.get(
    "PGVECTOR_TEST_DSN",
    "postgresql://postgres:test@localhost:55432/memdb",
)
EMBEDDING_DIM = 64  # Small; backend tolerates arbitrary dim per FakeEmbeddingClient.


def _docker_pgvector_reachable() -> bool:
    """One-shot connectivity probe; we don't want a network hang per test."""
    try:
        import psycopg
    except ImportError:
        return False
    try:
        with psycopg.connect(PGVECTOR_DSN, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"
                )
                if cur.fetchone() is None:
                    return False
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _docker_pgvector_reachable(),
    reason=(
        "pgvector Docker container not reachable at "
        f"{PGVECTOR_DSN}. Boot via: docker run -d --name agentfw-pgvector-dev "
        "-e POSTGRES_PASSWORD=test -e POSTGRES_DB=memdb -p 55432:5432 "
        "pgvector/pgvector:pg15"
    ),
)


@pytest.fixture(scope="session")
def _schema_applied() -> None:
    """Apply DDL once per session against the live container.

    Phase 4.5 (typed-memory superset): drop the table FIRST so cached
    Phase 2 schema (no ``mem_type``/``ts``, no GIN/B-tree-on-type indexes)
    from prior runs of the same Docker container doesn't make the
    ``CREATE TABLE IF NOT EXISTS`` no-op. TRUNCATE-between-tests
    (``truncated_table``) still keeps each test isolated — this drop fires
    once per session.
    """
    import psycopg

    from services.memory_backends.pgvector import DDL

    with psycopg.connect(PGVECTOR_DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS agent_memories;")
            cur.execute(DDL.format(dim=EMBEDDING_DIM))


@pytest.fixture
def truncated_table(_schema_applied: None) -> Iterator[None]:
    """Wipe rows before each test so cases are isolated."""
    import psycopg

    with psycopg.connect(PGVECTOR_DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE agent_memories;")
    yield


@pytest.fixture
def fake_embedder() -> FakeEmbeddingClient:
    return FakeEmbeddingClient(dimension=EMBEDDING_DIM)


@pytest.fixture
def backend(
    fake_embedder: FakeEmbeddingClient, truncated_table: None
) -> Iterator[object]:
    """A PgVectorMemoryBackend bound to the live Docker container."""
    from services.memory_backends.pgvector import PgVectorMemoryBackend

    with PgVectorMemoryBackend(
        embedding_client=fake_embedder, dsn=PGVECTOR_DSN
    ) as b:
        yield b


# ─────────────────────────────────────────────────────────────────────
# Rejection / failure-mode matrix (FIRST — failure-paths-first)
# ─────────────────────────────────────────────────────────────────────


class TestConstructorRejections:
    """Pattern 11: enumerate the ways the constructor must refuse."""

    def test_requires_exactly_one_of_dsn_or_pool(
        self, fake_embedder: FakeEmbeddingClient
    ) -> None:
        from services.memory_backends.pgvector import PgVectorMemoryBackend

        with pytest.raises(ValueError):
            PgVectorMemoryBackend(embedding_client=fake_embedder)

        with pytest.raises(ValueError):
            PgVectorMemoryBackend(
                embedding_client=fake_embedder,
                dsn=PGVECTOR_DSN,
                pool=object(),  # type: ignore[arg-type]
            )

    def test_rejects_zero_dim_embedding_client(self) -> None:
        from services.memory_backends.pgvector import PgVectorMemoryBackend

        class _ZeroDim:
            dimension = 0

            async def embed(self, *, texts: list[str]) -> list[list[float]]:
                return []

        with pytest.raises(ValueError):
            PgVectorMemoryBackend(
                embedding_client=_ZeroDim(),  # type: ignore[arg-type]
                dsn=PGVECTOR_DSN,
            )


class TestEmbeddingClientFailureTranslation:
    """A5/Pattern 11: embed errors come out as ``MemoryBackendError``."""

    def test_embed_raise_is_translated(
        self, truncated_table: None
    ) -> None:
        from middleware.ports.embedding_client import EmbeddingClientError
        from services.memory_backends.pgvector import PgVectorMemoryBackend

        class _Boom:
            dimension = EMBEDDING_DIM

            async def embed(self, *, texts: list[str]) -> list[list[float]]:
                raise EmbeddingClientError("simulated provider outage")

        backend = PgVectorMemoryBackend(
            embedding_client=_Boom(),  # type: ignore[arg-type]
            dsn=PGVECTOR_DSN,
        )
        try:
            with pytest.raises(MemoryBackendError) as excinfo:
                backend.put(
                    MemoryRecord(
                        user_id="u1",
                        key="k",
                        payload={"text": "x"},
                        metadata={},
                    )
                )
            assert "embedding client failed" in str(excinfo.value).lower()
        finally:
            backend.close()

    def test_dimension_mismatch_is_translated(
        self, truncated_table: None
    ) -> None:
        """An embed client whose actual output disagrees with its
        advertised ``dimension`` is caught at the boundary so we never
        write a malformed row.
        """
        from services.memory_backends.pgvector import PgVectorMemoryBackend

        class _LyingDim:
            dimension = EMBEDDING_DIM  # advertised

            async def embed(self, *, texts: list[str]) -> list[list[float]]:
                # Return a wrong-length vector.
                return [[0.0, 0.0, 0.0] for _ in texts]

        backend = PgVectorMemoryBackend(
            embedding_client=_LyingDim(),  # type: ignore[arg-type]
            dsn=PGVECTOR_DSN,
        )
        try:
            with pytest.raises(MemoryBackendError) as excinfo:
                backend.put(
                    MemoryRecord(
                        user_id="u1",
                        key="k",
                        payload={"text": "x"},
                        metadata={},
                    )
                )
            assert "dim" in str(excinfo.value).lower()
        finally:
            backend.close()


class TestMissingRecords:
    """Per the Protocol contract: ``get`` returns ``None`` and
    ``delete`` returns ``False`` for unknown rows — no exception."""

    def test_get_unknown_user_returns_none(self, backend: object) -> None:
        assert backend.get(user_id="nobody", key="x") is None  # type: ignore[attr-defined]

    def test_get_unknown_key_returns_none(self, backend: object) -> None:
        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="u1", key="present", payload={"text": "a"}, metadata={}
            )
        )
        assert backend.get(user_id="u1", key="absent") is None  # type: ignore[attr-defined]

    def test_delete_unknown_key_returns_false(self, backend: object) -> None:
        assert backend.delete(user_id="u1", key="never") is False  # type: ignore[attr-defined]


class TestSearchEdgeCases:
    def test_search_limit_zero_returns_empty(self, backend: object) -> None:
        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="u1", key="k", payload={"text": "anything"}, metadata={}
            )
        )
        assert backend.search(user_id="u1", query="anything", limit=0) == []  # type: ignore[attr-defined]

    def test_search_empty_corpus_returns_empty(self, backend: object) -> None:
        assert backend.search(user_id="u1", query="anything") == []  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────
# Acceptance — CRUD + 4-field round-trip + isolation
# ─────────────────────────────────────────────────────────────────────


class TestPgVectorBackendCrud:
    def test_put_then_get_four_field_round_trip(self, backend: object) -> None:
        rec = MemoryRecord(
            user_id="u1",
            key="favourite_colour",
            payload={
                "text": "I love azure",
                "task_input": "what colour?",
                "answer": "azure",
            },
            metadata={"source": "user", "salience": 0.9, "suppressed": False},
        )
        backend.put(rec)  # type: ignore[attr-defined]
        fetched = backend.get(user_id="u1", key="favourite_colour")  # type: ignore[attr-defined]
        assert fetched is not None
        assert fetched.user_id == "u1"
        assert fetched.key == "favourite_colour"
        # Four-field round-trip — payload + metadata preserved verbatim.
        assert fetched.payload == rec.payload
        assert fetched.metadata == rec.metadata

    def test_put_overwrites_existing_key(self, backend: object) -> None:
        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="u1", key="k", payload={"text": "first", "v": 1}, metadata={}
            )
        )
        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="u1", key="k", payload={"text": "second", "v": 2}, metadata={}
            )
        )
        got = backend.get(user_id="u1", key="k")  # type: ignore[attr-defined]
        assert got is not None
        assert got.payload["v"] == 2
        assert got.payload["text"] == "second"

    def test_delete_returns_true_then_get_returns_none(
        self, backend: object
    ) -> None:
        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="u1", key="k", payload={"text": "x"}, metadata={}
            )
        )
        assert backend.delete(user_id="u1", key="k") is True  # type: ignore[attr-defined]
        assert backend.get(user_id="u1", key="k") is None  # type: ignore[attr-defined]

    def test_two_users_are_isolated(self, backend: object) -> None:
        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="alice", key="k", payload={"text": "alice-secret"}, metadata={}
            )
        )
        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="bob", key="k", payload={"text": "bob-secret"}, metadata={}
            )
        )
        a = backend.get(user_id="alice", key="k")  # type: ignore[attr-defined]
        b = backend.get(user_id="bob", key="k")  # type: ignore[attr-defined]
        assert a is not None and b is not None
        assert a.payload["text"] == "alice-secret"
        assert b.payload["text"] == "bob-secret"
        # And cross-user search MUST NOT bleed: alice's query should
        # not return bob's row (search is user_id-scoped).
        hits_alice = backend.search(user_id="alice", query="bob-secret", limit=5)  # type: ignore[attr-defined]
        assert all(h.user_id == "alice" for h in hits_alice)


# ─────────────────────────────────────────────────────────────────────
# Acceptance — kNN search behaviour (TAP-3: ordering + bounds, not floats)
# ─────────────────────────────────────────────────────────────────────


class TestPgVectorSearch:
    def test_search_returns_score_in_bounds(self, backend: object) -> None:
        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="u1", key="k", payload={"text": "pgvector docs"}, metadata={}
            )
        )
        hits = backend.search(user_id="u1", query="pgvector docs", limit=3)  # type: ignore[attr-defined]
        assert len(hits) >= 1
        score = hits[0].metadata.get("score")
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_search_respects_limit(self, backend: object) -> None:
        for i in range(5):
            backend.put(  # type: ignore[attr-defined]
                MemoryRecord(
                    user_id="u1",
                    key=f"k{i}",
                    payload={"text": f"fact-{i}"},
                    metadata={},
                )
            )
        assert len(backend.search(user_id="u1", query="fact", limit=3)) == 3  # type: ignore[attr-defined]

    def test_search_orders_more_relevant_first(self, backend: object) -> None:
        """TAP-3: assert ORDERING — exact distance to ``apple`` < distance to
        ``zzzz`` for the deterministic SHA256-based fake; the relative
        ordering is determined by the fake's hash topology, not the
        natural-language meaning. (The real OpenAI client gives semantic
        ordering — covered by a manual smoke run, not CI.)"""
        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(user_id="u1", key="a", payload={"text": "apple"}, metadata={})
        )
        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(user_id="u1", key="z", payload={"text": "zzzz-far-away"}, metadata={})
        )
        hits = backend.search(user_id="u1", query="apple", limit=2)  # type: ignore[attr-defined]
        assert len(hits) == 2
        # The exact-match row MUST come first; score for an identical
        # vector is the cosine similarity of a vector with itself = 1.0.
        assert hits[0].key == "a"
        assert hits[0].metadata["score"] >= hits[1].metadata["score"]


# ─────────────────────────────────────────────────────────────────────
# Acceptance — list_all (optional capability)
# ─────────────────────────────────────────────────────────────────────


class TestPgVectorListAll:
    def test_list_all_returns_only_users_rows(self, backend: object) -> None:
        for i in range(3):
            backend.put(  # type: ignore[attr-defined]
                MemoryRecord(
                    user_id="alice", key=f"k{i}", payload={"text": f"a{i}"}, metadata={}
                )
            )
        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="bob", key="kb", payload={"text": "b"}, metadata={}
            )
        )
        alice_rows = backend.list_all("alice")  # type: ignore[attr-defined]
        assert {r.key for r in alice_rows} == {"k0", "k1", "k2"}
        bob_rows = backend.list_all("bob")  # type: ignore[attr-defined]
        assert [r.key for r in bob_rows] == ["kb"]


# ─────────────────────────────────────────────────────────────────────
# Pattern 4: consumer-driven contract
#
# The SAME scenario runs against InMemoryMemoryBackend and
# PgVectorMemoryBackend. Per the plan's Phase 2 gate: "If a contract
# test fails, the backend is wrong — do not patch the test."
# ─────────────────────────────────────────────────────────────────────


def _make_in_memory() -> MemoryBackend:
    return InMemoryMemoryBackend()


def _make_pgvector(fake: FakeEmbeddingClient) -> MemoryBackend:
    from services.memory_backends.pgvector import PgVectorMemoryBackend

    return PgVectorMemoryBackend(
        embedding_client=fake, dsn=PGVECTOR_DSN
    )


@pytest.fixture(
    params=["in_memory", "pgvector"],
    ids=["in_memory", "pgvector"],
)
def conformance_backend(
    request: pytest.FixtureRequest,
    fake_embedder: FakeEmbeddingClient,
    truncated_table: None,
) -> Iterator[MemoryBackend]:
    if request.param == "in_memory":
        yield _make_in_memory()
        return
    backend = _make_pgvector(fake_embedder)
    try:
        yield backend
    finally:
        backend.close()  # type: ignore[attr-defined]


class TestMemoryBackendConsumerContract:
    """Same suite, two backends — proves the swap is invisible to callers."""

    def test_get_missing_returns_none(
        self, conformance_backend: MemoryBackend
    ) -> None:
        assert conformance_backend.get(user_id="u1", key="absent") is None

    def test_put_then_get_round_trip(
        self, conformance_backend: MemoryBackend
    ) -> None:
        rec = MemoryRecord(
            user_id="u1",
            key="k",
            payload={"text": "hello world", "v": 42},
            metadata={"src": "test"},
        )
        conformance_backend.put(rec)
        got = conformance_backend.get(user_id="u1", key="k")
        assert got is not None
        assert got.payload == rec.payload
        assert got.metadata == rec.metadata

    def test_delete_missing_returns_false(
        self, conformance_backend: MemoryBackend
    ) -> None:
        assert conformance_backend.delete(user_id="u1", key="never") is False

    def test_delete_existing_returns_true(
        self, conformance_backend: MemoryBackend
    ) -> None:
        conformance_backend.put(
            MemoryRecord(
                user_id="u1", key="k", payload={"text": "x"}, metadata={}
            )
        )
        assert conformance_backend.delete(user_id="u1", key="k") is True
        assert conformance_backend.get(user_id="u1", key="k") is None

    def test_users_isolated(
        self, conformance_backend: MemoryBackend
    ) -> None:
        conformance_backend.put(
            MemoryRecord(
                user_id="alice", key="k", payload={"text": "A"}, metadata={}
            )
        )
        conformance_backend.put(
            MemoryRecord(
                user_id="bob", key="k", payload={"text": "B"}, metadata={}
            )
        )
        assert conformance_backend.get(user_id="alice", key="k").payload["text"] == "A"  # type: ignore[union-attr]
        assert conformance_backend.get(user_id="bob", key="k").payload["text"] == "B"  # type: ignore[union-attr]


# ─────────────────────────────────────────────────────────────────────
# Phase 4.5 — typed-memory forward-compatible schema (P0; schema-now/
# behavior-later). The DDL gains ``mem_type`` (write-derived shadow of
# ``metadata['type']``) and a generated ``ts`` tsvector for future R4;
# ``_embed_text_of`` gains a non-empty-``embed_text`` preference ahead
# of the existing non-empty-``text`` branch. Day-one observably inert
# for every consumer — the four-field ``MemoryRecord`` round-trip must
# survive byte-identical (the consumer-driven contract above already
# guards that; the tests below pin the new DB-side additions).
#
# Failure-paths-first per AGENTS.md §Testing Rules / TAP-4.
# ─────────────────────────────────────────────────────────────────────


class TestEmbedTextOfPrecedence:
    """``_embed_text_of`` (pgvector.py:229) is a pure static method —
    table-test it without the Docker container.

    Plan code-block (`replace_mem0_pgvector.plan.md` lines 601-612):
    non-empty str ``embed_text`` wins; empty/non-str ``embed_text``
    falls through to non-empty str ``text``; else ``repr(payload)``.
    """

    def test_non_empty_embed_text_wins(self) -> None:
        from services.memory_backends.pgvector import PgVectorMemoryBackend

        rec = MemoryRecord(
            user_id="u",
            key="k",
            payload={"embed_text": "EXPLICIT", "text": "fallback"},
            metadata={},
        )
        assert PgVectorMemoryBackend._embed_text_of(rec) == "EXPLICIT"

    def test_empty_string_embed_text_falls_through_to_text(self) -> None:
        """Empty is NOT authoritative (per plan §test case 2)."""
        from services.memory_backends.pgvector import PgVectorMemoryBackend

        rec = MemoryRecord(
            user_id="u",
            key="k",
            payload={"embed_text": "", "text": "fallback"},
            metadata={},
        )
        assert PgVectorMemoryBackend._embed_text_of(rec) == "fallback"

    def test_no_embed_text_uses_text(self) -> None:
        """The inert-day-one path: no writer emits ``embed_text`` yet."""
        from services.memory_backends.pgvector import PgVectorMemoryBackend

        rec = MemoryRecord(
            user_id="u",
            key="k",
            payload={"text": "fallback"},
            metadata={},
        )
        assert PgVectorMemoryBackend._embed_text_of(rec) == "fallback"

    def test_neither_field_falls_through_to_repr(self) -> None:
        from services.memory_backends.pgvector import PgVectorMemoryBackend

        rec = MemoryRecord(
            user_id="u",
            key="k",
            payload={"other": "data"},
            metadata={},
        )
        assert PgVectorMemoryBackend._embed_text_of(rec) == repr(
            {"other": "data"}
        )

    def test_non_str_embed_text_falls_through(self) -> None:
        """Type guard (``isinstance(x, str)``) defends against payloads where
        ``embed_text`` was deserialized as a list/dict by a malformed writer.
        """
        from services.memory_backends.pgvector import PgVectorMemoryBackend

        rec = MemoryRecord(
            user_id="u",
            key="k",
            payload={"embed_text": ["not", "a", "string"], "text": "fallback"},
            metadata={},
        )
        assert PgVectorMemoryBackend._embed_text_of(rec) == "fallback"


class TestMemTypeColumn:
    """The new ``mem_type`` column is write-derived from
    ``metadata['type']`` and NEVER read at runtime — recall composition
    keeps reading ``metadata['type']`` via ``LongTermMemoryService``.
    These tests assert that the column ends up populated correctly
    so a future R1 push-down can rely on its B-tree index.
    """

    def test_mem_type_defaults_to_semantic_when_absent(
        self, backend: object
    ) -> None:
        """No ``metadata['type']`` ⇒ DB stores ``'semantic'``."""
        import psycopg

        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="u1",
                key="k1",
                payload={"text": "no type set"},
                metadata={},
            )
        )
        with psycopg.connect(PGVECTOR_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT mem_type FROM agent_memories "
                    "WHERE user_id=%s AND key=%s",
                    ("u1", "k1"),
                )
                row = cur.fetchone()
        assert row is not None
        assert row[0] == "semantic"

    @pytest.mark.parametrize(
        "type_value", ["semantic", "episodic", "procedural"]
    )
    def test_mem_type_is_derived_verbatim_from_metadata(
        self, backend: object, type_value: str
    ) -> None:
        import psycopg

        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="u1",
                key=f"k-{type_value}",
                payload={"text": "x"},
                metadata={"type": type_value},
            )
        )
        with psycopg.connect(PGVECTOR_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT mem_type FROM agent_memories "
                    "WHERE user_id=%s AND key=%s",
                    ("u1", f"k-{type_value}"),
                )
                row = cur.fetchone()
        assert row is not None
        assert row[0] == type_value

    def test_mem_type_updates_on_upsert(self, backend: object) -> None:
        """Re-``put``ing under the same (user_id, key) flips ``mem_type``
        to the new value — the column tracks the latest write."""
        import psycopg

        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="u1",
                key="k1",
                payload={"text": "x"},
                metadata={"type": "semantic"},
            )
        )
        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="u1",
                key="k1",
                payload={"text": "x"},
                metadata={"type": "procedural"},
            )
        )
        with psycopg.connect(PGVECTOR_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT mem_type FROM agent_memories "
                    "WHERE user_id=%s AND key=%s",
                    ("u1", "k1"),
                )
                row = cur.fetchone()
        assert row is not None
        assert row[0] == "procedural"


class TestSchemaFoldFourFieldRoundTripPreserved:
    """``get`` and ``search`` must still reconstruct the four-field
    ``MemoryRecord`` byte-identical to the input. ``mem_type``, ``ts``,
    ``id``, ``embed_text``, and ``created_at`` stay DB-side-only.
    """

    def test_get_does_not_expose_mem_type_or_ts(
        self, backend: object
    ) -> None:
        original = MemoryRecord(
            user_id="u1",
            key="k1",
            payload={"text": "hello"},
            metadata={"type": "episodic", "salience": 0.7},
        )
        backend.put(original)  # type: ignore[attr-defined]
        rec = backend.get(user_id="u1", key="k1")  # type: ignore[attr-defined]
        assert rec is not None
        # The four fields round-trip; nothing else leaks.
        assert rec.user_id == original.user_id
        assert rec.key == original.key
        assert rec.payload == original.payload
        assert rec.metadata == original.metadata
        # No DB-side columns appear on the record dict.
        as_dict = rec.model_dump()
        for forbidden in ("mem_type", "ts", "id", "embed_text", "created_at"):
            assert forbidden not in as_dict, (
                f"{forbidden} must stay DB-side, not leak into MemoryRecord"
            )

    def test_search_does_not_expose_mem_type_or_ts(
        self, backend: object
    ) -> None:
        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="u1",
                key="k1",
                payload={"text": "apple"},
                metadata={"type": "semantic"},
            )
        )
        hits = backend.search(  # type: ignore[attr-defined]
            user_id="u1", query="apple", limit=5
        )
        assert len(hits) == 1
        rec = hits[0]
        as_dict = rec.model_dump()
        for forbidden in ("mem_type", "ts", "id", "embed_text", "created_at"):
            assert forbidden not in as_dict


class TestProceduralStillEmbeddedAndRetrievable:
    """G1 correctness gate (design §5.1): the procedural embedding
    bypass is **deferred** to R2. A ``procedural``-typed record MUST
    still be embedded by ``put`` and kNN-retrievable by ``search``
    today — otherwise this phase would be a behavior change disguised
    as a schema change.
    """

    def test_procedural_record_is_embedded_and_kNN_retrievable(
        self, backend: object
    ) -> None:
        import psycopg

        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="u1",
                key="proc-1",
                payload={"text": "alpha bravo charlie"},
                metadata={"type": "procedural"},
            )
        )
        # 1. DB-side: embedding column is non-NULL.
        with psycopg.connect(PGVECTOR_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT embedding IS NOT NULL FROM agent_memories "
                    "WHERE user_id=%s AND key=%s",
                    ("u1", "proc-1"),
                )
                row = cur.fetchone()
        assert row is not None
        assert row[0] is True, "procedural rows MUST be embedded at P0"
        # 2. App-side: search still returns the row (P0 = no type bypass).
        hits = backend.search(  # type: ignore[attr-defined]
            user_id="u1", query="alpha bravo charlie", limit=5
        )
        assert len(hits) == 1
        assert hits[0].key == "proc-1"


class TestGeneratedTsColumn:
    """The generated ``ts`` tsvector is the future R4 hybrid-lexical
    side. P0 only requires that it auto-populates correctly and is
    NULL-safe (design H7): a row whose payload lacks ``text`` must NOT
    produce a NULL ``ts`` (the ``COALESCE(payload->>'text','')`` in the
    GENERATED expression is the load-bearing guard).
    """

    def test_ts_populated_when_payload_text_present(
        self, backend: object
    ) -> None:
        import psycopg

        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="u1",
                key="k1",
                payload={"text": "the quick brown fox"},
                metadata={},
            )
        )
        with psycopg.connect(PGVECTOR_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ts::text, ts IS NULL FROM agent_memories "
                    "WHERE user_id=%s AND key=%s",
                    ("u1", "k1"),
                )
                row = cur.fetchone()
        assert row is not None
        ts_text, is_null = row
        assert is_null is False
        # tsvector ``::text`` lists stems; at least one of our tokens shows up.
        assert "quick" in ts_text or "brown" in ts_text or "fox" in ts_text

    def test_ts_is_empty_not_null_when_text_absent(
        self, backend: object
    ) -> None:
        """``COALESCE(payload->>'text','')`` guards against NULL — the column
        is ``tsvector GENERATED ALWAYS AS (...) STORED``, and on a payload
        without ``text`` we get an empty-but-non-NULL tsvector.
        """
        import psycopg

        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="u1",
                key="k1",
                payload={"other": "no text key"},
                metadata={},
            )
        )
        with psycopg.connect(PGVECTOR_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ts IS NULL, ts::text FROM agent_memories "
                    "WHERE user_id=%s AND key=%s",
                    ("u1", "k1"),
                )
                row = cur.fetchone()
        assert row is not None
        is_null, ts_text = row
        assert is_null is False, "ts must NEVER be NULL (design H7)"
        assert ts_text == "", "ts must be empty when payload has no text"


class TestSchemaShape:
    """Pin the DDL surface so a future drift removing ``mem_type``,
    ``ts``, or their indexes is caught. Reads ``information_schema``,
    not application code — this is a true schema regression guard.
    """

    def test_mem_type_column_exists_with_default_semantic(
        self, _schema_applied: None
    ) -> None:
        import psycopg

        with psycopg.connect(PGVECTOR_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT data_type, column_default, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_name='agent_memories' "
                    "AND column_name='mem_type'"
                )
                row = cur.fetchone()
        assert row is not None
        data_type, default, is_nullable = row
        assert data_type == "text"
        assert default is not None and "semantic" in default
        assert is_nullable == "NO"

    def test_ts_column_is_generated_tsvector(
        self, _schema_applied: None
    ) -> None:
        import psycopg

        with psycopg.connect(PGVECTOR_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT data_type, is_generated "
                    "FROM information_schema.columns "
                    "WHERE table_name='agent_memories' "
                    "AND column_name='ts'"
                )
                row = cur.fetchone()
        assert row is not None
        data_type, is_generated = row
        assert data_type == "tsvector"
        # Postgres returns 'ALWAYS' for GENERATED ALWAYS columns.
        assert is_generated == "ALWAYS"

    def test_required_indexes_exist(self, _schema_applied: None) -> None:
        import psycopg

        with psycopg.connect(PGVECTOR_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename='agent_memories'"
                )
                names = {r[0] for r in cur.fetchall()}
        assert "agent_memories_user_type_idx" in names  # B-tree on (user_id, mem_type)
        assert "agent_memories_ts_idx" in names         # GIN on ts
        assert "agent_memories_hnsw_idx" in names       # pre-existing
        assert "agent_memories_user_idx" in names       # pre-existing


# ─────────────────────────────────────────────────────────────────────
# Phase 5 hotfix — running-event-loop safety (failure-paths-first)
# ─────────────────────────────────────────────────────────────────────
#
# The graph-side recall/store path calls the sync backend from a sync
# context (LangGraph node). asyncio.run() works there. But the BFF
# /agent/memory CRUD route is `async def` (FastAPI), so the same
# backend.put() / backend.search() call runs inside a running event
# loop — at which point asyncio.run() raises
# ``RuntimeError: asyncio.run() cannot be called from a running event
# loop``. This was the live 500 on POST /api/memory observed 2026-06-22
# on agent-backend-combined (Hermes crud-seed cases in MEM_SMOKE).
#
# These tests assert the backend works in BOTH contexts.


class TestRunningEventLoopSafety:
    """Phase 5 hotfix: backend MUST work when called from a running loop.

    The chat path is sync-from-outside (LangGraph node), so today's
    ``asyncio.run`` bridge is fine. The BFF /agent/memory CRUD path is
    async-from-outside (FastAPI). The backend MUST handle both.
    """

    def test_put_works_when_called_from_running_event_loop(
        self, backend: object, fake_embedder: FakeEmbeddingClient
    ) -> None:
        """RED before fix: ``asyncio.run`` inside a running loop raises
        ``RuntimeError: asyncio.run() cannot be called from a running event loop``.
        After the fix, put() must succeed and the row must round-trip.
        """
        import asyncio
        from services.long_term_memory import MemoryRecord

        async def _put_in_loop() -> object:
            record = MemoryRecord(
                user_id="u-loop",
                key="k-1",
                payload={"text": "stored from inside a running loop"},
                metadata={"type": "semantic"},
            )
            backend.put(record)  # type: ignore[attr-defined]
            return backend.get("u-loop", "k-1")  # type: ignore[attr-defined]

        got = asyncio.run(_put_in_loop())
        assert got is not None
        assert got.payload["text"] == "stored from inside a running loop"

    def test_search_works_when_called_from_running_event_loop(
        self, backend: object, fake_embedder: FakeEmbeddingClient
    ) -> None:
        """``search`` also embeds (the query), so it has the same trap.
        Exercising the path independently catches regression in either site.
        """
        import asyncio
        from services.long_term_memory import MemoryRecord

        # Seed one row from a sync context (proves the sync path is unaffected).
        backend.put(  # type: ignore[attr-defined]
            MemoryRecord(
                user_id="u-loop-search",
                key="seed",
                payload={"text": "seed from sync"},
                metadata={"type": "semantic"},
            )
        )

        async def _search_in_loop() -> list:
            return backend.search("u-loop-search", "seed", limit=5)  # type: ignore[attr-defined]

        records = asyncio.run(_search_in_loop())
        assert isinstance(records, list)
        assert any(r.key == "seed" for r in records)
