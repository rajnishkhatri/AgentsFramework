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

    # ── Phase 2: optional type filter (additive, backward-compatible) ──

    def test_search_without_type_filter_returns_all_types(self):
        # Regression guard: the default (no mem_type) path is unchanged.
        service = _service()
        service.store("u", "k1", {"text": "match"}, metadata={"type": "semantic"})
        service.store("u", "k2", {"text": "match"}, metadata={"type": "episodic"})
        service.store("u", "k3", {"text": "match"})  # no type metadata
        results = service.search("u", "match")
        assert len(results) == 3

    def test_search_type_filter_keeps_only_matching_type(self):
        service = _service()
        service.store("u", "k1", {"text": "match"}, metadata={"type": "semantic"})
        service.store("u", "k2", {"text": "match"}, metadata={"type": "episodic"})
        results = service.search("u", "match", mem_type="semantic")
        assert [r.key for r in results] == ["k1"]

    def test_search_type_filter_excludes_untyped_records(self):
        service = _service()
        service.store("u", "k1", {"text": "match"}, metadata={"type": "semantic"})
        service.store("u", "k2", {"text": "match"})  # no type
        results = service.search("u", "match", mem_type="semantic")
        assert [r.key for r in results] == ["k1"]

    def test_search_type_filter_applies_limit_after_filtering(self):
        # The limit must bound the FILTERED result, not be consumed by
        # off-type records the caller never sees (else a type query can come
        # back short even when enough matches exist).
        service = _service()
        for i in range(5):
            service.store(
                "u", f"ep{i}", {"text": "match"}, metadata={"type": "episodic"}
            )
        for i in range(5):
            service.store(
                "u", f"se{i}", {"text": "match"}, metadata={"type": "semantic"}
            )
        results = service.search("u", "match", limit=3, mem_type="semantic")
        assert len(results) == 3
        assert all(r.metadata.get("type") == "semantic" for r in results)

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
        # Caller metadata round-trips; store() also stamps a stored_at (P2 #10).
        assert record.metadata["source"] == "explicit"
        assert "stored_at" in record.metadata


# ─────────────────────────────────────────────────────────────────────
# 3.2b Soft-suppress (chat-persistence Phase B, D5)
# ─────────────────────────────────────────────────────────────────────


class TestSuppress:
    def test_suppress_missing_key_returns_false(self):
        """Failure path first: suppressing a non-existent key is a no-op
        (False), not an error — mirrors forget()'s boolean."""
        service = _service()
        assert service.suppress("u", "nope") is False

    def test_suppress_blank_key_raises(self):
        """Failure path: a blank key is a programmer error (typed)."""
        service = _service()
        with pytest.raises(ValueError):
            service.suppress("u", "")

    def test_suppress_sets_flag_and_retains_row(self):
        """Reject = soft-suppress: the flag is written but the ROW IS RETAINED
        (distinct from forget's hard delete) — the owner can still see/restore."""
        service = _service()
        service.store("u", "k", {"text": "prefers metric"})
        assert service.suppress("u", "k") is True
        record = service.recall("u", "k")
        assert record is not None, "the row must be retained (audit)"
        assert record.metadata.get("suppressed") is True
        # The payload is untouched (only metadata flips).
        assert record.payload["text"] == "prefers metric"

    def test_un_suppress_clears_flag(self):
        """Reversible (D5): suppressed=False removes the flag entirely."""
        service = _service()
        service.store("u", "k", {"text": "x"})
        service.suppress("u", "k", suppressed=True)
        assert service.suppress("u", "k", suppressed=False) is True
        record = service.recall("u", "k")
        assert record is not None
        assert "suppressed" not in record.metadata

    def test_suppress_preserves_other_metadata(self):
        """The flag must not clobber salience / stored_at / type."""
        service = _service()
        service.store(
            "u", "k", {"text": "x"}, metadata={"salience": 0.9, "type": "semantic"}
        )
        service.suppress("u", "k")
        record = service.recall("u", "k")
        assert record is not None
        assert record.metadata["salience"] == 0.9
        assert record.metadata["type"] == "semantic"
        assert "stored_at" in record.metadata
        assert record.metadata["suppressed"] is True

    def test_suppress_scoped_to_user(self):
        """Cross-user guard: suppressing u's key never touches another user's
        same-named key."""
        service = _service()
        service.store("u", "k", {"text": "mine"})
        service.store("other", "k", {"text": "theirs"})
        service.suppress("u", "k")
        other = service.recall("other", "k")
        assert other is not None
        assert "suppressed" not in other.metadata


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


# ─────────────────────────────────────────────────────────────────────
# A1 — bounded budget + consolidation (Hermes/memory-os adoption)
# docs/research/memory/hermes_adoptions_design.md. Failure paths first;
# behavior-only assertions (TAP-1 — never re-derive the evict ordering).
# ─────────────────────────────────────────────────────────────────────


def _store(service, user_id, key, text, *, mem_type="semantic", salience=0.5):
    service.store(
        user_id, key, {"text": text}, metadata={"type": mem_type, "salience": salience}
    )


class TestCount:
    def test_count_rejects_empty_user_id(self):
        with pytest.raises(ValueError):
            _service().count("")

    def test_count_rejects_non_string_type(self):
        with pytest.raises(TypeError):
            _service().count("u", mem_type=3)  # type: ignore[arg-type]

    def test_count_zero_for_empty_store(self):
        assert _service().count("u") == 0

    def test_count_is_scoped_by_user(self):
        s = _service()
        _store(s, "u1", "k1", "a")
        _store(s, "u2", "k2", "b")
        assert s.count("u1") == 1

    def test_count_filters_by_type(self):
        s = _service()
        _store(s, "u", "k1", "a", mem_type="semantic")
        _store(s, "u", "k2", "b", mem_type="episodic")
        assert s.count("u", mem_type="semantic") == 1
        assert s.count("u") == 2


class TestConsolidate:
    def test_consolidate_rejects_empty_type(self):
        with pytest.raises(ValueError):
            _service().consolidate("u", "", budget=5)

    def test_under_budget_evicts_nothing(self):
        s = _service()
        for i in range(3):
            _store(s, "u", f"k{i}", f"fact {i}")
        outcome = s.consolidate("u", "semantic", budget=5)
        assert outcome.evicted == 0
        assert outcome.deduped == 0
        assert s.count("u", mem_type="semantic") == 3

    def test_over_budget_evicts_lowest_salience_first(self):
        s = _service()
        # Distinct text so dedup does not fire; salience is the eviction key.
        _store(s, "u", "hi", "high salience fact", salience=0.9)
        _store(s, "u", "mid", "mid salience fact", salience=0.5)
        _store(s, "u", "lo", "low salience fact", salience=0.1)
        outcome = s.consolidate("u", "semantic", budget=2)
        assert outcome.evicted == 1
        # The lowest-salience record is the one removed; the two strongest stay.
        assert s.recall("u", "lo") is None
        assert s.recall("u", "hi") is not None
        assert s.recall("u", "mid") is not None

    def test_exact_duplicate_text_is_deduped_keeping_highest_salience(self):
        s = _service()
        _store(s, "u", "weak", "prefers metric units", salience=0.2)
        _store(s, "u", "strong", "Prefers   Metric Units", salience=0.8)  # variant
        outcome = s.consolidate("u", "semantic", budget=10)
        assert outcome.deduped == 1
        # The higher-salience copy survives; the weaker duplicate is removed.
        assert s.recall("u", "strong") is not None
        assert s.recall("u", "weak") is None

    def test_dedup_and_evict_combine(self):
        s = _service()
        _store(s, "u", "dupA", "same fact", salience=0.3)
        _store(s, "u", "dupB", "same fact", salience=0.6)  # dup of dupA
        _store(s, "u", "other", "different fact", salience=0.9)
        _store(s, "u", "third", "third fact", salience=0.1)
        # After dedup: {same fact(0.6), different(0.9), third(0.1)} = 3; budget 2
        # evicts the lowest survivor (third, 0.1).
        outcome = s.consolidate("u", "semantic", budget=2)
        assert outcome.deduped == 1
        assert outcome.evicted == 1
        assert s.count("u", mem_type="semantic") == 2
        assert s.recall("u", "third") is None

    def test_consolidate_only_touches_its_type(self):
        s = _service()
        for i in range(4):
            _store(s, "u", f"sem{i}", f"semantic {i}", mem_type="semantic", salience=0.1 * i)
        _store(s, "u", "ep", "an episode", mem_type="episodic", salience=0.5)
        s.consolidate("u", "semantic", budget=2)
        # The episodic record is untouched by a semantic consolidation.
        assert s.recall("u", "ep") is not None
        assert s.count("u", mem_type="episodic") == 1


class TestStoreBudgetEnforcement:
    """A1: the SERVICE store path consolidates on overflow (so every writer —
    autocapture, the CRUD route, the panel — is bounded, not just autocapture)."""

    def _budgeted(self, budget):
        from services.long_term_memory import (
            InMemoryMemoryBackend,
            LongTermMemoryService,
        )

        return LongTermMemoryService(InMemoryMemoryBackend(), budgets={"semantic": budget})

    def test_store_returns_none_when_no_budget_configured(self):
        # Default service (no budgets) → store never consolidates, returns None.
        s = _service()
        assert s.store("u", "k", {"text": "a fact"}, metadata={"type": "semantic"}) is None

    def test_store_returns_none_under_budget(self):
        s = self._budgeted(5)
        out = s.store("u", "k1", {"text": "fact one"}, metadata={"type": "semantic", "salience": 0.5})
        assert out is None
        assert s.count("u", mem_type="semantic") == 1

    def test_store_consolidates_on_overflow_and_returns_outcome(self):
        s = self._budgeted(2)
        for i in range(3):
            out = s.store(
                "u", f"k{i}", {"text": f"fact {i}"},
                metadata={"type": "semantic", "salience": 0.1 * (i + 1)},
            )
        # The third write overflows budget 2 → consolidation runs, returns outcome.
        assert out is not None
        assert out.evicted == 1
        assert s.count("u", mem_type="semantic") == 2
        # Lowest-salience (k0, 0.1) evicted; the two strongest survive.
        assert s.recall("u", "k0") is None

    def test_store_untyped_record_is_never_consolidated(self):
        # The v1 deterministic store writes no type → no budget applies → None.
        s = self._budgeted(1)
        assert s.store("u", "k", {"text": "untyped"}) is None
        assert s.store("u", "k2", {"text": "also untyped"}) is None
        assert s.count("u") == 2  # uncapped (no type → no budget key)


# ─────────────────────────────────────────────────────────────────────
# P2 #8 — un-evictable SAFETY FLOOR (hermes_adoptions_design §10.5).
# A record at/above the safety floor must NEVER be evicted to satisfy a
# budget, even if higher-salience records exist. Failure-paths-first: the
# "safety fact survives overflow" guarantee is asserted before the rates.
# ─────────────────────────────────────────────────────────────────────


def _floored(floor):
    """A consolidate-only service (no store-path budget) with a safety floor, so
    the explicit consolidate() call is the sole eviction point — the
    outcome.evicted assertions stay meaningful."""
    from services.long_term_memory import (
        InMemoryMemoryBackend,
        LongTermMemoryService,
    )

    return LongTermMemoryService(InMemoryMemoryBackend(), safety_floor=floor)


class TestSafetyFloor:
    def test_safety_fact_is_never_evicted_even_over_budget(self):
        """A salience-1.0 safety fact survives a budget=1 consolidation where
        strong-but-non-safety facts would otherwise crowd it out. Safety beats
        budget."""
        s = _floored(floor=0.95)
        _store(s, "u", "safety", "EpiPen in the top drawer", salience=1.0)
        _store(s, "u", "pref1", "likes dark mode", salience=0.6)
        _store(s, "u", "pref2", "likes metric", salience=0.7)
        s.consolidate("u", "semantic", budget=1)
        # The safety fact must still be there; only non-pinned facts were evicted.
        assert s.recall("u", "safety") is not None

    def test_pinned_facts_may_exceed_budget(self):
        """If the pinned (>= floor) facts alone exceed budget, ALL of them stay —
        the store legitimately runs over budget rather than drop a safety fact."""
        s = _floored(floor=0.9)
        _store(s, "u", "s1", "safety one", salience=0.95)
        _store(s, "u", "s2", "safety two", salience=0.99)
        _store(s, "u", "weak", "a weak preference", salience=0.2)
        outcome = s.consolidate("u", "semantic", budget=1)
        # Both safety facts survive (2 > budget 1); the weak one is evicted.
        assert s.recall("u", "s1") is not None
        assert s.recall("u", "s2") is not None
        assert s.recall("u", "weak") is None
        assert outcome.evicted == 1

    def test_no_floor_configured_evicts_normally(self):
        """Default (floor=None) is byte-identical to today: highest-salience
        wins, no pinning."""
        s = _floored(floor=None)
        _store(s, "u", "hi", "high", salience=0.9)
        _store(s, "u", "lo", "low", salience=0.1)
        s.consolidate("u", "semantic", budget=1)
        assert s.recall("u", "hi") is not None
        assert s.recall("u", "lo") is None


# ─────────────────────────────────────────────────────────────────────
# P2 #10 — explicit recency tie-break. store() stamps a UTC ``stored_at``;
# consolidate() breaks salience TIES by evicting the oldest first (instead
# of backend insertion order, which is unreliable on Mem0).
# ─────────────────────────────────────────────────────────────────────


class TestRecencyTieBreak:
    def test_store_stamps_stored_at_when_absent(self):
        s = self._budgeted_none()
        s.store("u", "k", {"text": "a fact"}, metadata={"type": "semantic"})
        rec = s.recall("u", "k")
        assert rec is not None
        assert "stored_at" in rec.metadata and rec.metadata["stored_at"]

    def test_store_preserves_caller_supplied_stored_at(self):
        s = self._budgeted_none()
        s.store(
            "u", "k",
            {"text": "a fact"},
            metadata={"type": "semantic", "stored_at": "2020-01-01T00:00:00+00:00"},
        )
        rec = s.recall("u", "k")
        assert rec is not None
        assert rec.metadata["stored_at"] == "2020-01-01T00:00:00+00:00"

    def test_equal_salience_evicts_oldest_first(self):
        """Two equal-salience facts, distinct text; budget 1 keeps the NEWER one
        (the older stored_at is evicted)."""
        s = self._budgeted_none()
        s.store(
            "u", "old", {"text": "older fact"},
            metadata={"type": "semantic", "salience": 0.5, "stored_at": "2020-01-01T00:00:00+00:00"},
        )
        s.store(
            "u", "new", {"text": "newer fact"},
            metadata={"type": "semantic", "salience": 0.5, "stored_at": "2026-01-01T00:00:00+00:00"},
        )
        s.consolidate("u", "semantic", budget=1)
        assert s.recall("u", "new") is not None
        assert s.recall("u", "old") is None

    def _budgeted_none(self):
        from services.long_term_memory import (
            InMemoryMemoryBackend,
            LongTermMemoryService,
        )

        return LongTermMemoryService(InMemoryMemoryBackend())
