"""L2 Reproducible: Tests for services/long_term_memory.py.

Contract-driven TDD per Protocol B. Failure paths first (TAP-4).

Spec: docs/plan/services/LONG_TERM_MEMORY_PLAN.md.
"""

from __future__ import annotations

import asyncio
import logging

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _service(backend=None):
    from services.long_term_memory import LongTermMemoryService
    from services.memory_backends.in_memory import InMemoryMemoryBackend

    return LongTermMemoryService(backend=backend or InMemoryMemoryBackend())


# ─────────────────────────────────────────────────────────────────────
# 3.1 Failure path tests (FIRST)
# ─────────────────────────────────────────────────────────────────────


class TestLongTermMemoryFailures:
    def test_store_rejects_empty_user_id(self):
        service = _service()
        with pytest.raises(ValueError):
            service.store("", "k", {"v": 1})

    def test_store_rejects_none_payload(self):
        service = _service()
        with pytest.raises(ValueError):
            service.store("user-1", "k", None)  # type: ignore[arg-type]

    def test_store_rejects_non_string_key(self):
        service = _service()
        with pytest.raises(TypeError):
            service.store("user-1", 123, {"v": 1})  # type: ignore[arg-type]

    def test_recall_rejects_empty_user_id(self):
        service = _service()
        with pytest.raises(ValueError):
            service.recall("", "k")

    def test_search_rejects_negative_limit(self):
        service = _service()
        with pytest.raises(ValueError):
            service.search("user-1", "q", limit=-1)

    def test_backend_exception_is_typed_not_raw(self):
        from services.long_term_memory import (
            LongTermMemoryService,
            MemoryBackendError,
            MemoryRecord,
        )

        class ExplodingBackend:
            def put(self, record: MemoryRecord) -> None:
                raise RuntimeError("backend exploded")

            def get(self, user_id, key):
                raise RuntimeError("backend exploded")

            def search(self, user_id, query, limit=10):
                raise RuntimeError("backend exploded")

            def delete(self, user_id, key) -> bool:
                raise RuntimeError("backend exploded")

        service = LongTermMemoryService(backend=ExplodingBackend())
        with pytest.raises(MemoryBackendError):
            service.store("user-1", "k", {"v": 1})
        with pytest.raises(MemoryBackendError):
            service.recall("user-1", "k")
        with pytest.raises(MemoryBackendError):
            service.search("user-1", "q")
        with pytest.raises(MemoryBackendError):
            service.forget("user-1", "k")

    def test_forget_returns_false_for_unknown_key(self):
        service = _service()
        assert service.forget("user-1", "absent") is False


# ─────────────────────────────────────────────────────────────────────
# 3.2 Acceptance path tests
# ─────────────────────────────────────────────────────────────────────


class TestLongTermMemoryAcceptance:
    def test_store_then_recall_returns_payload(self):
        service = _service()
        service.store("u", "k", {"hello": "world"})
        record = service.recall("u", "k")
        assert record is not None
        assert record.payload == {"hello": "world"}
        assert record.user_id == "u"
        assert record.key == "k"

    def test_recall_unknown_key_returns_none(self):
        service = _service()
        assert service.recall("u", "missing") is None

    def test_user_isolation(self):
        service = _service()
        service.store("alice", "favorite", {"color": "blue"})
        assert service.recall("bob", "favorite") is None

    def test_search_finds_substring_match(self):
        service = _service()
        service.store("u", "key1", {"text": "the quick brown fox"})
        service.store("u", "key2", {"text": "lazy dog"})
        service.store("u", "key3", {"text": "another fox jumps"})
        results = service.search("u", "fox")
        assert len(results) == 2
        keys = {r.key for r in results}
        assert keys == {"key1", "key3"}

    def test_search_respects_limit(self):
        service = _service()
        for i in range(20):
            service.store("u", f"k{i}", {"text": "match-me"})
        results = service.search("u", "match-me", limit=5)
        assert len(results) == 5

    def test_forget_removes_record(self):
        service = _service()
        service.store("u", "k", {"v": 1})
        assert service.forget("u", "k") is True
        assert service.recall("u", "k") is None

    def test_metadata_round_trips(self):
        service = _service()
        service.store("u", "k", {"v": 1}, metadata={"source": "explicit"})
        record = service.recall("u", "k")
        assert record is not None
        assert record.metadata == {"source": "explicit"}


# ─────────────────────────────────────────────────────────────────────
# 3.3 Concurrency tests
# ─────────────────────────────────────────────────────────────────────


class TestLongTermMemoryConcurrency:
    async def test_concurrent_recall_same_key(self):
        service = _service()
        service.store("u", "k", {"v": 42})

        async def call() -> object:
            return service.recall("u", "k")

        results = await asyncio.gather(*(call() for _ in range(10)))
        assert all(r is not None and r.payload == {"v": 42} for r in results)

    async def test_concurrent_store_different_keys(self):
        service = _service()

        async def call(i: int) -> None:
            service.store("u", f"key-{i}", {"i": i})

        await asyncio.gather(*(call(i) for i in range(10)))
        for i in range(10):
            record = service.recall("u", f"key-{i}")
            assert record is not None
            assert record.payload == {"i": i}


# ─────────────────────────────────────────────────────────────────────
# 3.4 Architecture-level test (also covered in tests/architecture/)
# ─────────────────────────────────────────────────────────────────────
# The architecture tests live in tests/architecture/test_service_isolation.py.


# ─────────────────────────────────────────────────────────────────────
# 3.5 Property-based test
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.property
class TestLongTermMemoryProperty:
    @settings(max_examples=25, deadline=None)
    @given(
        user_id=st.text(min_size=1, max_size=20).filter(bool),
        key=st.text(min_size=1, max_size=20).filter(bool),
        payload=st.dictionaries(
            keys=st.text(min_size=1, max_size=10),
            values=st.one_of(st.text(max_size=20), st.integers(), st.booleans()),
            min_size=1,
            max_size=4,
        ),
    )
    def test_store_recall_round_trip(self, user_id, key, payload):
        service = _service()
        service.store(user_id, key, payload)
        record = service.recall(user_id, key)
        assert record is not None
        assert record.payload == payload


# ─────────────────────────────────────────────────────────────────────
# §4 Privacy invariant
# ─────────────────────────────────────────────────────────────────────


class TestLongTermMemoryPrivacy:
    """Payload values MUST never appear in log lines."""

    def test_payload_never_logged(self):
        service = _service()
        secret_value = "TOP-SECRET-PAYLOAD-MAGIC"

        target = logging.getLogger("services.long_term_memory")
        captured: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(record)

        handler = _Capture(level=logging.DEBUG)
        target.addHandler(handler)
        original_level = target.level
        target.setLevel(logging.DEBUG)
        try:
            service.store("u", "k", {"secret": secret_value})
            service.recall("u", "k")
            service.search("u", "anything")
            service.forget("u", "k")
        finally:
            target.removeHandler(handler)
            target.setLevel(original_level)

        for record in captured:
            assert secret_value not in record.getMessage(), (
                f"Privacy invariant violated: payload value {secret_value!r} "
                f"appeared in log message {record.getMessage()!r}"
            )
