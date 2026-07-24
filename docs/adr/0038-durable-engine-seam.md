---
type: decision-record
title: 'ADR-0038: Durable engine seam — HttpEngineDb → BFF /api/engine/* → pgEngineDb (D1, Shape B)'
status: accepted
created: 2026-07-22
updated: 2026-07-22
owner: Rajnish Khatri
related: coach-v3-durable-progress.spec.md, coach-v3-durable-progress.plan.md, coach-v3-durable-progress.brainstorm.md
tags: [decision-record]
---

# ADR-0038: Durable engine seam — HttpEngineDb → BFF /api/engine/* → pgEngineDb (D1, Shape B)

**Status:** Accepted (Stage 2 human gate, Rajnish Khatri) — 2026-07-22.
**Related:** [spec](../plan/coach-v3-durable-progress.spec.md) · [plan](../plan/coach-v3-durable-progress.plan.md) · [design](../plan/coach-v3-durable-progress.brainstorm.md)
**Audience:** anyone touching the engine data plane, the BFF Route Handler family, or a later D2 (RSC/Server-Action) refactor.

---

## Context

The prod eng-coach V3 learner-facing quiz runs **entirely on an ephemeral `InMemoryEngineDb`**,
built fresh per page load (`composition_engine_browser.ts:96`, seeded at `:265`). Every attempt,
session, `skill_state`, and miss lives only in browser RAM and is lost on any reload — logout,
navigate-away, or a second device. The goal is **durable, cross-device** progress + resume, plus a
bounded-30 quiz, an enriched summary, and content-fresh eligibility (spec, ~58 FRs).

The full Postgres layer already exists — the `EngineDb` interface
(`engine_db.ts`, **29 methods** today → **31** after this change adds `setSessionCurrentQuestion` +
`getNewestOpenSession(subject, learnerId)` — the latter because no existing method finds an open
session by learner (`listClosedSessionsByLearner` excludes `ended_at IS NULL`); the pointer read is a
*field*, not a method), all 13 Drizzle repos, `pgEngineDb`
(`drizzle_engine_db.ts:269`), a 12-table `schema.pg.ts`, and migrations `0001–0003` — but is wired
only to the unused server root. The clean network seam is the single `EngineDb` interface for the
**write/row-level** paths: every repo and `use_quiz.ts` is written against it, and the browser builds
its whole `EnginePortBag` from **one** `db` instance, so replacing that instance swaps every
`useEngine()` screen's row-level path at once (atomic). **The read screens are the exception** — their
hooks call several repos and reach *coarse* endpoints that are not `EngineDb` methods, so they need a
separate coarse-client seam (see Consequences; review round 5, issue #1).

This change fires several `⚠️ Ask-first` triggers at once — a **new BFF route family**
(`/api/engine/*`), a **new abstraction** (`HttpEngineDb`, G1), **new schema columns + a migration**
(`0004`: two columns + a partial unique index, dual-dialect — plus the `0000` baseline the runner
needs, since no existing migration creates any table), and a **new content-seed mechanism** (Track
G). They are one coherent
"durable engine seam" decision, so they are bundled into this single ADR.

---

## Decision

Ship **D1**: implement the full `EngineDb` surface as an `HttpEngineDb` adapter that calls new BFF
`/api/engine/*` Route Handlers, which run the existing `pgEngineDb` server-side. Use **D6 Shape B**:
the BFF holds `DATABASE_URL` server-side and connects to Postgres directly — exactly the established
threads/coach-marker precedent (`server_composition.ts` → `selectThreadRepo`/`selectCoachMarkerRepo`).
Migration `0004` (both dialects) adds two things: the `quiz_session.current_question_id` served-pointer
column, and the `attempt.idempotency_key` column + a partial unique index that makes attempt-POST
retries an atomic DB no-op (FR-A9.1) — the client stamps one key per answer action, so `created_at`
stays server-assigned and the natural key / handler read-then-write alternatives are rejected (both
fail to dedup a server-timestamped retry; the latter also has a TOCTOU race). This adds one field to
the `AttemptInput` wire contract. Seed the reviewed content bank into Postgres via a SQL emitter
(Track G).

---

## Options considered & rejected

| Option | Why rejected |
|---|---|
| **D2 — direct RSC + Server-Action rewrite** (chosen for *later*) | ~11 `useEngine()` screens rewritten, centered on the hardest page (quiz = 33 hooks/effects + live reducer + streaming coach drawer that must stay client). Delays cross-device resume for a decoupling that D1 also achieves at the data layer. D1 preserves the `EngineDb` seam, so a later D2 moves call sites, not data. |
| **D3 — resume-snapshot only** | Persists just enough to resume position, not the append-only attempt history. Fails the "save all attempts/first-misses for future custom lessons" and content-fresh-eligibility goals (both need cross-session attempt history). |
| **D6 Shape A — proxy engine calls through the Python backend** | Python has **zero** engine REST surface today; this is 100% new FastAPI routes + porting the 12-table Drizzle schema to Python. Shape B reuses the exact threads precedent (`DATABASE_URL` already read server-side in the BFF). F-R9 forbids creds in the *browser/edge* bundle, not the Node Route Handler. |
| **Data-migration job for the seed** | Heavier than a repeatable SQL emitter reusing the `emit_test_item_bank.py` precedent. The emitter is **multi-source** (items + skills + hints + tutorials + content + blueprints) with **`ON CONFLICT DO UPDATE`** reconciliation + soft-retire — NOT `DO NOTHING`, which ignores changed content and fails FR-G2 (corrected, review rounds 5–6). |
| **Persist feedback-phase state in `0004`** | Would widen the migration with phase/verdict/answeredLetter. Deferred: v1 resume advances-to-next on mid-feedback abandonment (FR-B3-feedback), keeping the durable *pointer* a single column (the served-pointer `current_question_id`). `0004` still adds `attempt.idempotency_key` for FR-A9.1 — a separate, load-bearing column, not feedback state. |
| **Natural key / handler read-then-write for attempt idempotency** | Rejected in favor of a client `idempotency_key` + partial unique index. `created_at` is server-assigned (`AttemptInput` omits it), so a `(session, question, created_at)` natural key can't match a retried POST; a handler query-then-insert has a TOCTOU double-insert race on the exact path FR-A9.1 protects. The client key + atomic DB constraint is the correct guarantee (plan §6 decision 4). |
| **Quiz-only partial `EngineDb` surface** | The bag swap is atomic — a 15-method quiz subset leaves progress/summary/skill-detail hard-failing and the dashboard rail dark. The full surface is required (FR-A4). |

---

## Rationale

D1 gives the **same cross-device outcome as D2 at the data layer**, with a small diff that reuses a
proven repo pattern, and it keeps the `EngineDb` seam intact so the eventual D2 refactor is a
call-site move, not a data migration. Shape B is the established, lower-risk credential topology in
this repo. The atomic-swap property forces the full surface + a coarse client seam for the read
screens, but that is a one-time cost that also removes read-screen chattiness. The
`current_question_id` column is the minimum durable state that makes served-but-unsubmitted resume
correct (position is not derivable from
attempts alone).

---

## Consequences

- **Every `useEngine()` screen becomes network-backed at the swap** (atomic). Read screens
  (dashboard/summary/skill) must collapse to coarse single-call endpoints or their latency regresses
  visibly — this is a hard requirement of the swap, not an optimization.
- **A later D2 refactor moves call sites, not data** — the `EngineDb` seam is preserved (reversibility).
- **The served-pointer write is fire-and-forget** — its failure degrades to the FR-B8 scheduler-scoped
  NULL fallback, never an error state or a blocked serve.
- **`AttemptInput` gains a client-supplied `idempotency_key`** — an additive wire-contract change so a
  retried attempt-POST dedups atomically at the DB (partial unique index in `0004`). The idempotent
  insert is **`.onConflictDoNothing()` inside the DB adapter** returning a typed result — NOT a handler
  catch of a PG unique-violation, because `pgEngineDb` wraps errors opaquely (`drizzle_engine_db.ts:284`).
  `created_at` stays engine-assigned.
- **The read screens need a coarse client seam; FR-A6 is relaxed (review round 5, #1).** The coarse
  `/dashboard`/`/summary`/`/skill`/`/next` endpoints are not `EngineDb` methods, so swapping only the
  `db` instance leaves the read hooks fanning out per-repo (`use_summary` = 6 repos). A thin coarse
  client/loader is added and the 3 read hooks + scheduler entry are rewired to it — a real call-site
  change, so FR-A6's "all call sites unchanged" is narrowed to "EngineDb write consumers unchanged."
- **Running score is commit-first `first_try`-only (review round 5, #3).** Resume + close compute
  unique-`first_try`/unique-resolved server-side, matching the live reducer (`quiz_screen_reducer.ts:434`)
  — counting all resolving-correct would make the resumed score exceed the live score.
- **Seed is multi-source reconciliation (review round 5, #4).** The promoted JSON is items-only; the
  seed spans ≥5 sources and uses `ON CONFLICT DO UPDATE` (not `DO NOTHING`, which ignores changed
  content and fails FR-G2).
- **New durability-correctness obligations:** attempt-POST idempotency (retry ≠ double-count, via the
  client key above) and `HttpEngineDb` retry/timeout on idempotent reads (FR-A9); cross-learner read
  isolation scoped by
  the server-derived `learnerId` (FR-A2a).
- **Content seeding becomes a prerequisite** (Track G) — a fresh Postgres serves no questions until
  seeded; the empty-content guard (FR-G3) ships with Track A so a not-yet-seeded prod degrades
  honestly rather than presenting a broken quiz.
- **No `trust/` type change** → no re-sign. **No new dependency** (`pg`/Drizzle already in the tree).
  **No live LLM** on any path (pure data plumbing).

---

## Supersedes / related

Amends the ADR-0005 engine substrate direction (durable server path for the learner-facing quiz).
Consistent with ADR-0034 (BFF Cloud SQL bind for markers/threads — the same `DATABASE_URL` topology)
and ADR-0033 (prod content seeding). Realizes
[coach-v3-durable-progress.spec.md](../plan/coach-v3-durable-progress.spec.md) via
[coach-v3-durable-progress.plan.md](../plan/coach-v3-durable-progress.plan.md).
