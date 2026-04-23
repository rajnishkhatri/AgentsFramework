"""L2 Reproducible: tests for services/memory_backends/sqlite.py.

Sprint M-Phase2 swap proof: a backend swap that adds zero changes under
``agent_ui_adapter/`` and behaviourally matches the in-memory backend.

Failure paths first per AGENTS.md TAP-4. The conformance class
re-runs the same scenario over both ``InMemoryMemoryBackend`` and
``SqliteMemoryBackend`` so backwards-compat is enforced mechanically.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from services.long_term_memory import (
    InMemoryMemoryBackend,
    LongTermMemoryService,
    MemoryBackend,
    MemoryRecord,
)
from services.memory_backends.sqlite import SqliteMemoryBackend


# ─────────────────────────────────────────────────────────────────────
# Failure paths first
# ─────────────────────────────────────────────────────────────────────


class TestSqliteBackendInitErrors:
    def test_invalid_database_path_raises_sqlite_error(
        self, tmp_path: Path
    ) -> None:
        # A directory cannot be opened as a database file.
        with pytest.raises(sqlite3.OperationalError):
            SqliteMemoryBackend(database=str(tmp_path))


class TestGetMissingKey:
    def test_unknown_user_returns_none(self) -> None:
        with SqliteMemoryBackend(":memory:") as backend:
            assert backend.get(user_id="unknown", key="x") is None

    def test_unknown_key_for_known_user_returns_none(self) -> None:
        with SqliteMemoryBackend(":memory:") as backend:
            backend.put(
                MemoryRecord(
                    user_id="u1", key="other", payload={"a": 1}, metadata={}
                )
            )
            assert backend.get(user_id="u1", key="x") is None


class TestDeleteMissingKey:
    def test_delete_unknown_key_returns_false(self) -> None:
        with SqliteMemoryBackend(":memory:") as backend:
            assert backend.delete(user_id="u1", key="never") is False


# ─────────────────────────────────────────────────────────────────────
# Acceptance — basic CRUD
# ─────────────────────────────────────────────────────────────────────


class TestSqliteBackendCrud:
    def test_put_then_get_returns_record(self) -> None:
        with SqliteMemoryBackend(":memory:") as backend:
            record = MemoryRecord(
                user_id="u1",
                key="favourite_colour",
                payload={"value": "azure"},
                metadata={"source": "user"},
            )
            backend.put(record)
            fetched = backend.get(user_id="u1", key="favourite_colour")
            assert fetched is not None
            assert fetched.user_id == "u1"
            assert fetched.payload == {"value": "azure"}
            assert fetched.metadata == {"source": "user"}

    def test_put_overwrites_existing_key(self) -> None:
        with SqliteMemoryBackend(":memory:") as backend:
            backend.put(
                MemoryRecord(
                    user_id="u1", key="k", payload={"v": 1}, metadata={}
                )
            )
            backend.put(
                MemoryRecord(
                    user_id="u1", key="k", payload={"v": 2}, metadata={}
                )
            )
            assert backend.get(user_id="u1", key="k").payload == {"v": 2}

    def test_delete_returns_true_when_key_existed(self) -> None:
        with SqliteMemoryBackend(":memory:") as backend:
            backend.put(
                MemoryRecord(
                    user_id="u1", key="k", payload={"v": 1}, metadata={}
                )
            )
            assert backend.delete(user_id="u1", key="k") is True
            assert backend.get(user_id="u1", key="k") is None

    def test_two_users_are_isolated(self) -> None:
        with SqliteMemoryBackend(":memory:") as backend:
            backend.put(
                MemoryRecord(
                    user_id="alice", key="k", payload={"v": "a"}, metadata={}
                )
            )
            backend.put(
                MemoryRecord(
                    user_id="bob", key="k", payload={"v": "b"}, metadata={}
                )
            )
            assert backend.get(user_id="alice", key="k").payload == {"v": "a"}
            assert backend.get(user_id="bob", key="k").payload == {"v": "b"}

    def test_search_substring_match(self) -> None:
        with SqliteMemoryBackend(":memory:") as backend:
            for i, val in enumerate(["apricot", "banana", "blueberry"]):
                backend.put(
                    MemoryRecord(
                        user_id="u1",
                        key=f"k{i}",
                        payload={"fruit": val},
                        metadata={},
                    )
                )
            hits = backend.search(user_id="u1", query="berry", limit=10)
            assert len(hits) == 1
            assert hits[0].payload == {"fruit": "blueberry"}

    def test_search_respects_limit(self) -> None:
        with SqliteMemoryBackend(":memory:") as backend:
            for i in range(5):
                backend.put(
                    MemoryRecord(
                        user_id="u1",
                        key=f"k{i}",
                        payload={"tag": "match"},
                        metadata={},
                    )
                )
            assert len(backend.search("u1", "match", limit=3)) == 3


# ─────────────────────────────────────────────────────────────────────
# Acceptance — persistence across instances
# ─────────────────────────────────────────────────────────────────────


class TestSqliteBackendPersistence:
    def test_data_survives_backend_close_and_reopen(
        self, tmp_path: Path
    ) -> None:
        db = tmp_path / "ltm.sqlite3"
        with SqliteMemoryBackend(database=db) as backend1:
            backend1.put(
                MemoryRecord(
                    user_id="u1",
                    key="durable",
                    payload={"persisted": True},
                    metadata={},
                )
            )

        with SqliteMemoryBackend(database=db) as backend2:
            fetched = backend2.get(user_id="u1", key="durable")
            assert fetched is not None
            assert fetched.payload == {"persisted": True}


# ─────────────────────────────────────────────────────────────────────
# M-Phase2 conformance: parametrized scenario over both backends
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture(params=["in_memory", "sqlite"])
def backend(request) -> MemoryBackend:
    """Yield each MemoryBackend implementation so the same behavioural
    contract is enforced against both."""
    if request.param == "in_memory":
        yield InMemoryMemoryBackend()
    else:
        impl = SqliteMemoryBackend(":memory:")
        yield impl
        impl.close()


class TestBackendBehaviouralEquivalence:
    """Same scenario, two backends. If this class ever diverges between
    backends the M-Phase2 swap-radius claim is broken."""

    def test_protocol_conformance(self, backend: MemoryBackend) -> None:
        assert isinstance(backend, MemoryBackend)

    def test_round_trip_via_long_term_memory_service(
        self, backend: MemoryBackend
    ) -> None:
        service = LongTermMemoryService(backend=backend)
        service.store(
            user_id="u1",
            key="favourite_colour",
            payload={"value": "azure"},
            metadata={"source": "user"},
        )
        record = service.recall(user_id="u1", key="favourite_colour")
        assert record is not None
        assert record.payload == {"value": "azure"}
        assert record.metadata == {"source": "user"}

    def test_search_and_forget(self, backend: MemoryBackend) -> None:
        service = LongTermMemoryService(backend=backend)
        for i, fruit in enumerate(["apple", "banana", "blueberry"]):
            service.store(
                user_id="u1",
                key=f"k{i}",
                payload={"fruit": fruit},
                metadata={},
            )
        hits = service.search(user_id="u1", query="berry", limit=10)
        assert len(hits) == 1
        assert hits[0].payload == {"fruit": "blueberry"}

        assert service.forget(user_id="u1", key="k0") is True
        assert service.recall(user_id="u1", key="k0") is None

    def test_user_isolation(self, backend: MemoryBackend) -> None:
        service = LongTermMemoryService(backend=backend)
        service.store(user_id="alice", key="k", payload={"who": "a"}, metadata={})
        service.store(user_id="bob", key="k", payload={"who": "b"}, metadata={})
        assert service.recall("alice", "k").payload == {"who": "a"}
        assert service.recall("bob", "k").payload == {"who": "b"}
