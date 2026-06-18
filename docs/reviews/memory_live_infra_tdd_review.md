# TDD Review — Memory Layer Live-Infra Wiring (Pieces A/B/C)

**Reviewed against:** [docs/TDD_AGENTS_MD_REVIEW.md](../TDD_AGENTS_MD_REVIEW.md) — the shipped TDD guidance in `AGENTS.md`: anti-patterns **TAP-1…TAP-4**, the **L1–L4 test-category-by-layer** map, the pytest-marker convention, and the test-dependency rule.
**Subject:** the three live-infra pieces on `feat/memory-layer-wiring` (uncommitted):
- **A** — prod CRUD routes in [middleware/app_prod.py](../../middleware/app_prod.py)
- **B** — [services/memory_backends/mem0.py](../../services/memory_backends/mem0.py) `Mem0MemoryBackend`
- **C** — [frontend/lib/adapters/thread_store/neon_thread_repo.ts](../../frontend/lib/adapters/thread_store/neon_thread_repo.ts) `NeonThreadRepo`

**Date:** 2026-06-18
**Verdict:** ✅ **PASS** — all four anti-patterns clear; layer mapping correct; one LOW-severity observation (no true blocker). Gates green (memory/app_prod/composition **62/62**; full both-ring sweep **3233 backend / 688 frontend** per the plan's last run).

---

## 1. Anti-pattern scan (TAP-1…TAP-4)

The four shipped anti-patterns are the document's highest-impact, "non-inferable from code" guidance. Each piece is scored against all four.

### TAP-1 — Tautological tests (reimplementing the algorithm in the test)

| Piece | Result | Evidence |
|---|---|---|
| **B** mem0 | ✅ Clear | The `_FakeMem0Sdk` mimics **Mem0's cloud row shape** (auto `id` + `metadata` blob), NOT the adapter's `(user_id,key)`→metadata mapping. The test never references the adapter's private `__ltm_key`/`__ltm_payload` fields (`grep __ltm_ → 0`); it asserts **behavior** (`put` then `get` returns the record; upsert leaves exactly one row; search is user-scoped). This is the correct "test against the collaborator's contract, not the unit's internals" shape. |
| **A** app_prod | ✅ Clear | CRUD tests drive the real HTTP surface via `TestClient` and assert response bodies/status — no route logic re-implemented. |
| **C** Neon | ✅ Clear | `makeFakeDb` is a **behavioral fake** of the drizzle query-builder slice (records + answers), and the test asserts repo behavior (owner-scoped, newest-first, archived hidden, cursor pagination). The keyset-pagination math is exercised, not duplicated. |

### TAP-2 — Mock addiction (>3 mocks ⇒ the test verifies mock config, not behavior)

| Piece | Mock count | Result | Evidence |
|---|---|---|---|
| **B** mem0 | **0** `MagicMock`/`patch` | ✅ Clear | Uses a hand-written behavioral fake, zero mocking library. Exemplary. |
| **C** Neon | **0** `vi.fn`/`vi.mock` | ✅ Clear | Behavioral `makeFakeDb` + `rejectingDb`. Zero mocks. |
| **A** app_prod | 54 `MagicMock` refs in-file | ✅ Clear **(defensible)** | The mocks are all at the **composition seam** — `GcsTraceSink`, GCS registry, `jwt_verifier`, `adapters`, `PostgresCheckpointer`, runtime — i.e. the *truly external systems* TAP-2 explicitly says to reserve mocks for. The two collaborators **under test** are **real in-memory implementations**: `_ThreadStore()` and `LongTermMemoryService(InMemoryMemoryBackend())` ([test_app_prod.py:232,410](../../tests/middleware/test_app_prod.py)). The owner-isolation test shares **one real backend** across two identities to prove scoping behaviorally — the in-memory-implementation strategy TAP-2 prescribes, not mock-config verification. |

> **Why A's count is not a violation:** TAP-2's detect-rule is ">3 mocks **of the unit's collaborators**." Here the unit-under-test's collaborators (thread store, memory service) are real; the mocks stand in for unbootstrappable infra (Cloud Run Postgres, GCS, WorkOS JWKS). Booting those for a route unit test would be the actual anti-pattern.

### TAP-3 — Determinism theater (asserting exact LLM output / `temperature=0`)

✅ **N/A across all three.** No piece invokes an LLM. The live-infra layer is pure I/O wiring — no model calls, so the anti-pattern's surface doesn't exist here. (The Phase-2 extractor is where this would bind, and it correctly asserts structure, not strings — out of scope for this review.)

### TAP-4 — Gap blindness (success tests outnumber failure tests; "write the rejection test first")

✅ **Clear — exemplary across all three.** Failure paths are written first and dominate:

- **B** mem0 — failure-first ordering is explicit in the file (`# Failure paths first`): missing-key→`None`, delete-missing→`False`, search-failure→`MemoryBackendError`, add-failure→`MemoryBackendError`, empty-api-key→`ValueError`. 18 failure/negative assertions.
- **A** app_prod — `TestAppProdThreadCrud` leads with missing-bearer→**401**; `TestAppProdMemoryCrud` leads with missing-bearer→**401** and memory-unavailable→**503**, plus the **owner-isolation** rejection (alice cannot see bob's memory). The security rejections precede the happy-path roundtrips.
- **C** Neon — the `describe("… — failure paths first")` block (findOne-miss→null, update-miss→null, db-rejection→`ThreadStoreError` for findOne/list/insert) is authored **above** the CRUD block.

This is the single most-emphasized rule in the review doc ("a gate that accepts everything is more dangerous than one that rejects everything"), and all three pieces honor it including the cross-user-leak rejection — the highest-stakes failure path for a memory feature.

---

## 2. Test categories by layer (L1–L4 map)

The review's R2 maps each layer to *what* to test. Each new test file lands in the right layer and covers that layer's prescribed categories:

| File | Layer | Prescribed categories (R2) | Covered? |
|---|---|---|---|
| `test_mem0_backend.py` | **L2 (services/)** | backend **contract** + record/replay fixtures | ✅ Protocol conformance (`isinstance(_backend(), MemoryBackend)`), CRUD contract, behavioral fake (record/replay-style), privacy invariant via `caplog`. The file header even self-labels "L2 Reproducible." |
| `test_app_prod.py` (CRUD) | **adapter/route** | authorization decision matrix + 401/403/404/503 contract | ✅ auth matrix (401/503/404), owner-isolation (the authz decision that matters), CRUD lifecycle. |
| `neon_thread_repo.test.ts` | **adapter (frontend L2-equiv)** | CRUD + lifecycle, error-translation contract, SDK-confinement | ✅ CRUD + pagination + owner-scope + soft-delete + error-translation + selector + end-to-end through `NeonFreeThreadStore`. |

**Test-dependency rule (R4):** ✅ holds. `tests/services/memory_backends/` imports only from `services/`; `tests/middleware/` imports `middleware`/`agent_ui_adapter`/`trust`/`services` (all at or below its layer). No upward import.

**pytest markers (R3):** these are L2/adapter tests that *should* run in CI by default, so the absence of `@slow`/`@simulation`/`@live_llm` markers is **correct** — they are fast, deterministic, no-LLM. (A note below flags the one place a `live_llm`-style guard belongs.)

---

## 3. Architecture invariants the tests mechanically enforce (the load-bearing part)

Beyond the doc's TAP/L-map, these tests double as the dependency-rule enforcement the review's spirit calls for:

- **F-R2 SDK confinement (C).** `test_frontend_layering.test.ts` now matches SDK **subpath** imports (`isSdkSpec` → exact OR `${pkg}/` prefix), closing the hole where `drizzle-orm/pg-core` dodged the exact-string check. The schema + migrations were relocated under `lib/adapters/thread_store/db/` so all drizzle/neon imports live inside the adapter ring. The adapter-conformance `PAIRS` row proves `NeonThreadRepo` implements `ThreadRepo` **and** confines the SDK.
- **I-10 SDK confinement (B).** `Mem0MemoryBackend` imports the `mem0` SDK lazily inside `_client()` (the architecture test checks top-level imports), keeping the SDK out of the service's import surface; the loop depends only on the sync `MemoryBackend` Protocol.
- **Privacy invariant (A + B).** `test_content_never_appears_in_logs` (caplog magic-string) for B; A logs only `subject`/`key` and returns content only to its owner. Verified, not assumed.
- **IR-NEON-5 (C).** `test_drizzle_config.test.ts` asserts the checkpoint tables are excluded and the schema/out paths point at the adapter ring; the migration omits the four checkpoint tables.

---

## 4. Observations (no blockers)

1. **LOW — `MemoryItem.type` mapping is unvalidated on read-back (A).** `list_memory` builds `MemoryItem(type=r.metadata.get("type"), …)`. If a memory was stored with no `type` (e.g. a pre-existing Mem0 row, or a v1 deterministic store that didn't set it), `type` is `None`. `MemoryItem.type` tolerates that, but it's worth a one-line test asserting a typeless stored memory still lists cleanly (currently the create-path always sets `type`, so the gap is only reachable via the durable backend with externally-created rows). *Not a correctness bug today; a robustness test for when the Mem0 backend goes live.*
2. **~~LOW~~ → RESOLVED 2026-06-18 — the live smoke test ran and caught 3 prod-breaking bugs.** This was the highest-value finding. `_client()`'s `from mem0 import MemoryClient` branch is never executed in CI, so the unit tests' fake had drifted from the real SDK (installed: **mem0ai 2.0.4**, fake modeled 1.x). Running `scripts/mem0_smoke.py` against live Mem0 Cloud surfaced three real defects the 13/13-green unit suite missed: (a) v2 `get_all`/`search` reject top-level `user_id` (need `filters={…}`) + return a `{"results":[…]}` envelope + `search` uses `top_k`; (b) `add` defaults to `infer=True` (async LLM rework/drop) when a keyed store needs `infer=False`; (c) Mem0 Cloud flattens nested metadata, requiring JSON-string encoding of structured fields. All three fixed TDD-style (corrected the fake to the real contract → red → fixed adapter → green → live 7/7). **Lesson for the doc's anti-pattern catalog:** a behavioral fake (TAP-2's prescribed alternative to mocks) is only as good as its fidelity to the SDK's *current* version — vendored SDKs whose surface CI mocks away need a non-CI live smoke. This is a real, generalizable gap in the "behavioral fake > mock" guidance and worth a one-line note in `AGENTS.md`'s TAP-2 entry.
3. **INFO — `neon_thread_repo.ts:20` docstring** still says the table is "defined in `lib/db/schema.ts`"; the file moved to `lib/adapters/thread_store/db/schema.ts`. Cosmetic stale reference.

---

## 5. Bottom line

The live-infra wiring is **test-first, anti-pattern-clean, and correctly layered**. The two pieces that own real logic (B's `(user_id,key)`↔Mem0 mapping, C's keyset pagination + error translation) are tested through **behavioral fakes** with failure paths first and **zero mocking-library use**. Piece A's mocking is confined to genuinely-external infra with the units-under-test kept real — the textbook TAP-2-compliant shape. The highest-stakes failure path for a memory feature — **cross-user leakage** — has an explicit rejection test in both the route layer (A) and is structurally impossible at the wire layer (owner-scoped, no client-supplied user_id). No change is required to merge; the two LOW items are robustness follow-ups for when the durable backends are switched on live.
