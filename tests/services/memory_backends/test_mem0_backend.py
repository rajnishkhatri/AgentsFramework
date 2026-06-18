"""L2 Reproducible: tests for services/memory_backends/mem0.py.

Piece B of the memory live-infra wiring: the prod ``MemoryBackend`` that
delegates to the Mem0 SDK so long-term memory persists across Cloud Run
restarts (the in-memory + sqlite backends are dev/test only).

Failure paths first (AGENTS.md TAP-4). A ``_FakeMem0Sdk`` stands in for the
real ``mem0.MemoryClient`` — it records every call and stores rows keyed the
way the real cloud does (auto ``id`` + a ``metadata`` blob), so the adapter's
``(user_id, key)`` ↔ Mem0 mapping is exercised for real, not mocked away.

Privacy invariant: memory CONTENT must never appear in a log line — only
``user_id`` / ``key`` / counts. Asserted explicitly via caplog.
"""

from __future__ import annotations

import logging

import pytest

from services.long_term_memory import (
    MemoryBackend,
    MemoryBackendError,
    MemoryRecord,
)
from services.memory_backends.mem0 import Mem0MemoryBackend


def _flatten_meta(meta: dict) -> dict:
    """Mimic Mem0 Cloud's nested-metadata flattening.

    A nested ``dict`` value round-trips as ``"k.v"`` strings (a single string
    for one key, a list for several); a JSON STRING value is a flat scalar and
    survives verbatim. This is what makes the JSON-string encoding load-bearing.
    """
    out: dict = {}
    for k, v in meta.items():
        if isinstance(v, dict):
            flattened = [f"{ik}.{iv}" for ik, iv in v.items()]
            out[k] = flattened[0] if len(flattened) == 1 else flattened
        else:
            out[k] = v
    return out


class _FakeMem0Sdk:
    """In-memory stand-in for ``mem0.MemoryClient`` (sync SDK surface, **v2.x**).

    Models the breaking v2 contract that the live smoke test surfaced
    (mem0ai 2.0.4):
      * ``get_all`` / ``search`` REJECT a top-level ``user_id`` kwarg
        (``ENTITY_PARAMS``) and require ``filters={"user_id": ...}``;
      * both return a **paginated dict** ``{"results": [...]}``, not a bare list;
      * ``search`` takes ``top_k`` (not ``limit``);
      * ``add`` still accepts ``user_id`` + ``metadata`` top-level.

    Rows carry ``id`` / ``memory`` / ``metadata`` like the cloud. Keeping the
    fake faithful to this shape is what makes the unit test catch a regression
    against the real SDK without a live call (TDD-review LOW #2 closed).
    """

    _ENTITY_PARAMS = frozenset({"user_id", "agent_id", "app_id", "run_id"})

    def __init__(self, *, raise_on: str | None = None) -> None:
        self.rows: list[dict] = []
        self._seq = 0
        self.calls: list[str] = []
        self.infer_seen: list[bool] = []
        self._raise_on = raise_on

    def _maybe_raise(self, op: str) -> None:
        if self._raise_on == op:
            raise RuntimeError(f"simulated mem0 {op} failure")

    @staticmethod
    def _user_from_filters(kwargs: dict) -> str | None:
        bad = _FakeMem0Sdk._ENTITY_PARAMS & set(kwargs)
        if bad:
            raise ValueError(
                f"Top-level entity parameters {bad} are not supported. "
                f"Use filters={{'user_id': '...'}} instead."
            )
        filters = kwargs.get("filters") or {}
        return filters.get("user_id")

    def add(self, messages, *, user_id, metadata=None, infer=True, **_kw):
        self.calls.append("add")
        self._maybe_raise("add")
        # Faithful to the live API: with the default LLM-inference path
        # (``infer=True``) the write is ASYNC + the text may be reworded or
        # dropped, so a keyed store cannot rely on verbatim read-back. The
        # backend MUST pass ``infer=False`` to get synchronous verbatim
        # storage — model that here so a regression that drops the flag fails.
        self.infer_seen.append(infer)
        if infer:
            return {"status": "PENDING"}
        self._seq += 1
        self.rows.append(
            {
                "id": f"m-{self._seq}",
                "memory": messages,
                "user_id": user_id,
                # Faithful to Mem0 Cloud: it FLATTENS nested metadata values (a
                # nested dict comes back as "k.v" strings, a list of them).
                # Only flat scalars (incl. JSON strings) survive intact. The
                # backend must therefore JSON-encode structured fields — model
                # the flattening so a regression to nested dicts fails.
                "metadata": _flatten_meta(metadata or {}),
            }
        )
        return {"status": "SUCCEEDED", "results": [self.rows[-1]]}

    def get_all(self, **kwargs):
        self.calls.append("get_all")
        self._maybe_raise("get_all")
        user_id = self._user_from_filters(kwargs)
        return {"results": [r for r in self.rows if r["user_id"] == user_id]}

    def search(self, query, *, top_k=10, **kwargs):
        self.calls.append("search")
        self._maybe_raise("search")
        user_id = self._user_from_filters(kwargs)
        hits = [
            r
            for r in self.rows
            if r["user_id"] == user_id and query in str(r["memory"])
        ]
        return {"results": hits[:top_k]}

    def delete(self, memory_id, **_kw):
        self.calls.append("delete")
        self._maybe_raise("delete")
        before = len(self.rows)
        self.rows = [r for r in self.rows if r["id"] != memory_id]
        return {"message": "deleted"} if len(self.rows) < before else {}


def _backend(sdk: _FakeMem0Sdk | None = None) -> Mem0MemoryBackend:
    return Mem0MemoryBackend(sdk_client=sdk or _FakeMem0Sdk())


# ─────────────────────────────────────────────────────────────────────
# Conformance: it IS a MemoryBackend (structural Protocol check)
# ─────────────────────────────────────────────────────────────────────


def test_satisfies_memory_backend_protocol() -> None:
    assert isinstance(_backend(), MemoryBackend)


# ─────────────────────────────────────────────────────────────────────
# Failure paths first
# ─────────────────────────────────────────────────────────────────────


class TestGetMissingKey:
    def test_unknown_user_returns_none(self) -> None:
        assert _backend().get(user_id="nobody", key="x") is None

    def test_unknown_key_for_known_user_returns_none(self) -> None:
        b = _backend()
        b.put(MemoryRecord(user_id="u1", key="other", payload={"text": "a"}))
        assert b.get(user_id="u1", key="missing") is None


class TestDeleteMissingKey:
    def test_delete_unknown_key_returns_false(self) -> None:
        assert _backend().delete(user_id="u1", key="never") is False


class TestBackendErrorsAreWrapped:
    def test_search_failure_raises_memory_backend_error(self) -> None:
        b = _backend(_FakeMem0Sdk(raise_on="search"))
        with pytest.raises(MemoryBackendError):
            b.search(user_id="u1", query="anything")

    def test_add_failure_raises_memory_backend_error(self) -> None:
        b = _backend(_FakeMem0Sdk(raise_on="add"))
        with pytest.raises(MemoryBackendError):
            b.put(MemoryRecord(user_id="u1", key="k", payload={"text": "x"}))


class TestConstructionGuards:
    def test_empty_api_key_without_sdk_raises(self) -> None:
        with pytest.raises(ValueError):
            Mem0MemoryBackend(api_key="")


# ─────────────────────────────────────────────────────────────────────
# Acceptance — CRUD round-trips through the (user_id, key) mapping
# ─────────────────────────────────────────────────────────────────────


class TestMem0BackendCrud:
    def test_put_then_get_returns_record(self) -> None:
        b = _backend()
        rec = MemoryRecord(
            user_id="u1",
            key="k1",
            payload={"text": "prefers metric units"},
            metadata={"type": "semantic"},
        )
        b.put(rec)
        got = b.get(user_id="u1", key="k1")
        assert got is not None
        assert got.user_id == "u1"
        assert got.key == "k1"
        assert got.payload["text"] == "prefers metric units"
        assert got.metadata["type"] == "semantic"

    def test_put_same_key_upserts_not_duplicates(self) -> None:
        sdk = _FakeMem0Sdk()
        b = _backend(sdk)
        b.put(MemoryRecord(user_id="u1", key="k1", payload={"text": "v1"}))
        b.put(MemoryRecord(user_id="u1", key="k1", payload={"text": "v2"}))
        got = b.get(user_id="u1", key="k1")
        assert got is not None and got.payload["text"] == "v2"
        # Exactly one row survives for that key (delete-then-add upsert).
        u1_rows = [r for r in sdk.rows if r["user_id"] == "u1"]
        assert len(u1_rows) == 1

    def test_search_is_user_scoped(self) -> None:
        b = _backend()
        b.put(MemoryRecord(user_id="alice", key="a", payload={"text": "secret-A"}))
        b.put(MemoryRecord(user_id="bob", key="b", payload={"text": "secret-B"}))
        alice_hits = b.search(user_id="alice", query="secret")
        assert [r.user_id for r in alice_hits] == ["alice"]
        assert all("secret-B" not in str(r.payload) for r in alice_hits)

    def test_search_respects_limit(self) -> None:
        b = _backend()
        for i in range(5):
            b.put(
                MemoryRecord(
                    user_id="u1", key=f"k{i}", payload={"text": f"note {i}"}
                )
            )
        assert len(b.search(user_id="u1", query="note", limit=2)) == 2

    def test_delete_existing_key_returns_true(self) -> None:
        b = _backend()
        b.put(MemoryRecord(user_id="u1", key="k1", payload={"text": "x"}))
        assert b.delete(user_id="u1", key="k1") is True
        assert b.get(user_id="u1", key="k1") is None

    def test_put_uses_infer_false_for_verbatim_synchronous_storage(self) -> None:
        # A keyed (user_id, key) store needs deterministic verbatim storage;
        # Mem0's default infer=True is async + may reword/drop the text. The
        # live smoke test surfaced this — pin it.
        sdk = _FakeMem0Sdk()
        _backend(sdk).put(
            MemoryRecord(user_id="u1", key="k1", payload={"text": "x"})
        )
        assert sdk.infer_seen and all(v is False for v in sdk.infer_seen)


# ─────────────────────────────────────────────────────────────────────
# Privacy invariant — content never logged
# ─────────────────────────────────────────────────────────────────────


class TestPrivacyInvariant:
    def test_content_never_appears_in_logs(self, caplog) -> None:
        secret = "MAGIC-SECRET-PAYLOAD-9f3a"
        b = _backend()
        with caplog.at_level(logging.DEBUG):
            b.put(MemoryRecord(user_id="u1", key="k1", payload={"text": secret}))
            b.get(user_id="u1", key="k1")
            b.search(user_id="u1", query="MAGIC")
            b.delete(user_id="u1", key="k1")
        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert secret not in joined
