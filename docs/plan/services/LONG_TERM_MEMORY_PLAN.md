# LONG_TERM_MEMORY_PLAN.md — `services/long_term_memory.py` Implementation Plan

> **Status**: design sub-plan for sprint S1 of [AGENT_UI_ADAPTER_SPRINTS.md](../adapter/sprints/AGENT_UI_ADAPTER_SPRINTS.md). Implements pattern H6 from [docs/STYLE_GUIDE_PATTERNS.md](../../STYLE_GUIDE_PATTERNS.md) lines 465–537.
>
> **TDD Protocol**: B (Contract-driven) per [research/tdd_agentic_systems_prompt.md](../../../research/tdd_agentic_systems_prompt.md) §Protocol B. L2 reproducible, <30s test budget.
>
> **Boundary**: horizontal service per [AGENTS.md](../../../AGENTS.md). Backend-agnostic. No imports from `components/`, `orchestration/`, or other `services/*`.

---

## 1. Purpose & Boundaries

### 1.1 What it does

A horizontal store/recall service for **per-user long-term memory**: facts about the user that should persist across sessions and runs. Backend-agnostic via a `MemoryBackend` Protocol. Receives `(user_id, key, payload)` and `(user_id, query)` as parameters.

### 1.2 What it does NOT do

- **Does not embed text** — embeddings are a backend concern (Mem0, pgvector, etc.); the service exposes raw store/recall and lets the backend decide
- **Does not own short-term memory** (conversation buffer) — that lives in `orchestration/state.py`
- **Does not classify what is worth remembering** — that's an upstream component decision
- **Does not import from other services** (AP-2)
- **Does not couple to a backend SDK in the public API** — the SDK is hidden behind `MemoryBackend`

### 1.3 Why it exists

[AGENT_UI_ADAPTER_PLAN.md](../adapter/AGENT_UI_ADAPTER_PLAN.md) §10 promises that swapping memory backend (Mem0 cloud → self-hosted) requires only one file change. That promise needs a backend-Protocol seam, which this service provides. Without it, the LangGraph node would import the SDK directly and the swap-radius claim would be false.

---

## 2. Public Interface

```python
# services/long_term_memory.py

from typing import Protocol, runtime_checkable
from pydantic import BaseModel

class MemoryRecord(BaseModel):
    user_id: str
    key: str
    payload: dict
    metadata: dict = {}

@runtime_checkable
class MemoryBackend(Protocol):
    """Backend swap surface. Implement for Mem0, in-memory, SQLite, pgvector, etc."""
    def put(self, record: MemoryRecord) -> None: ...
    def get(self, user_id: str, key: str) -> MemoryRecord | None: ...
    def search(self, user_id: str, query: str, limit: int = 10) -> list[MemoryRecord]: ...
    def delete(self, user_id: str, key: str) -> bool: ...


class LongTermMemoryService:
    def __init__(self, backend: MemoryBackend) -> None:
        """Backend is injected; service never imports a specific backend module."""
        ...

    def store(self, user_id: str, key: str, payload: dict, metadata: dict | None = None) -> None:
        """Validate inputs, construct MemoryRecord, hand to backend."""
        ...

    def recall(self, user_id: str, key: str) -> MemoryRecord | None:
        """Strict-key lookup. Returns None if absent."""
        ...

    def search(self, user_id: str, query: str, limit: int = 10) -> list[MemoryRecord]:
        """Backend-defined search semantics (substring, vector, etc.)."""
        ...

    def forget(self, user_id: str, key: str) -> bool:
        """Returns True if the record was present and removed; False otherwise."""
        ...
```

### 2.1 Built-in backend (in same file or `services/memory_backends/`)

- `InMemoryMemoryBackend` — `dict[(user_id, key), MemoryRecord]`. For tests and dev.

External backends (Mem0Backend, SqliteBackend, PgvectorBackend) live in `services/memory_backends/<name>.py` and are wired in by the composition root.

---

## 3. Test Plan (failure paths first)

Per Protocol B. Test file: `tests/services/test_long_term_memory.py`.

### 3.1 Failure path tests (write FIRST)

- `test_store_rejects_empty_user_id` — `service.store("", "k", {})` raises `ValueError`
- `test_store_rejects_none_payload` — `service.store("u", "k", None)` raises `ValueError`
- `test_store_rejects_non_string_key` — `service.store("u", 123, {})` raises `TypeError`
- `test_recall_rejects_empty_user_id` — raises `ValueError`
- `test_search_rejects_negative_limit` — raises `ValueError`
- `test_backend_exception_is_typed_not_raw` — given a backend that raises `RuntimeError("backend exploded")`, `service.store()` re-raises as a typed `MemoryBackendError` (defined in the module) so callers can `except` cleanly
- `test_forget_returns_false_for_unknown_key` — does NOT raise

### 3.2 Acceptance path tests

- `test_store_then_recall_returns_payload` — round-trip with `InMemoryMemoryBackend`
- `test_recall_unknown_key_returns_none` — never raises for absent
- `test_user_isolation` — user A stores; user B's `recall` returns `None` for the same key
- `test_search_finds_substring_match` — using `InMemoryMemoryBackend`'s naive substring search
- `test_search_respects_limit` — backend has 20 matches; `search(limit=5)` returns 5
- `test_forget_removes_record` — `forget(u, k)` then `recall(u, k)` returns `None`
- `test_metadata_round_trips` — store with `metadata={"source": "explicit"}`; recall returns it

### 3.3 Concurrency tests (asyncio variants for parallel dispatch)

- `test_concurrent_recall_same_key` — 10 parallel `recall()` calls for the same key all succeed (no shared mutable state in service or backend)
- `test_concurrent_store_different_keys` — 10 parallel `store()` calls; all 10 records present afterward

### 3.4 Architecture test

- `test_long_term_memory_does_not_import_other_services` — AST scan; assert only `trust.*`, stdlib, and `pydantic` imports

### 3.5 Property-based test (Hypothesis, `@pytest.mark.property`)

- `test_store_recall_round_trip` — Hypothesis generates `(user_id, key, payload)` tuples; stored record always recallable

### 3.6 Test budget

Full file <10s with `InMemoryMemoryBackend`. External backends get their own test files in `tests/services/memory_backends/<name>_test.py` (those may be slower; gated by markers).

---

## 4. Logging

Add to [logging.json](../../../logging.json):

```json
"services.long_term_memory": {
  "handlers": ["console", "long_term_memory_file"],
  "level": "INFO",
  "propagate": false
}
```

Logs at INFO: store/forget operations (with user_id, key — never payload). At DEBUG: recall results' presence/absence (never the payload itself; payload may contain PII).

**Privacy invariant**: payload contents NEVER appear in logs. Verified by a test that asserts no log line contains the magic-string payload values used in tests.

---

## 5. Dependencies

- **Internal**: `trust/` only (no `TrustTraceRecord` use here; it's pure data store)
- **External**: stdlib + `pydantic` (already a dep)
- **Test deps**: `pytest`, `pytest-asyncio` (already), `hypothesis`

NO new `pyproject.toml` dependencies for the in-memory backend. Mem0/SQLite/pgvector backends in `services/memory_backends/` will declare their own deps **at the time they are added** (per AGENTS.md "Ask first").

---

## 6. Open Questions / Deferred

- **Q-M1**: Should the service emit a `TrustTraceRecord` on every store/recall? Defer to v1.5; if needed, the composition root wraps the service with a `TracingMemoryService` decorator. Keeps the v1 service single-purpose.
- **Q-M2**: Per-user encryption at rest — backend-specific, deferred.
- **Q-M3**: TTL / forgetting policy — out of scope for v1. Backends MAY implement TTL; the service does not impose one.
- **Q-M4**: Schema-versioned `payload` — for v1, `payload: dict` is opaque. If schema enforcement becomes useful, add a `payload_schema` parameter to `store()` later.

---

## 7. Acceptance Sign-Off

S1 sprint considers US-1.2 done when:

- All tests in §3 are green
- `tests/services/test_long_term_memory.py` runs in <10s
- Privacy invariant in §4 is verified by a test
- `logging.json` updated
- `services/memory_backends/` directory exists with at least the in-memory backend; future backends drop in cleanly
- The traceability row in [AGENT_UI_ADAPTER_SPRINTS.md](../adapter/sprints/AGENT_UI_ADAPTER_SPRINTS.md) §5 for US-1.2 is updated with the commit SHA
