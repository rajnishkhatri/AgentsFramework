---
type: decision-record
title: 'ADR-0005: Subject-Coach engine home (Frontend-Ring local-first) + persistence substrate'
status: accepted
created: 2026-06-30
updated: 2026-06-30
owner: Rajnish Khatri
related: SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md, 0006-subject-coach-component-protocols.md, preact-english-coach-ui.spec.md, subject-coach-engine.brainstorm.md, 0001-native-shell-tauri-capacitor.md
tags: [decision-record]
---

# ADR-0005: Subject-Coach engine home + persistence substrate

**Status:** Accepted — 2026-06-30.
**Related:** [data & protocols design doc](../Architectures/SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md) · [ADR-0006 protocols](0006-subject-coach-component-protocols.md) · [UI spec](../plan/preact-english-coach-ui.spec.md) · [engine brainstorm](../plan/subject-coach-engine.brainstorm.md) · [ADR-0001 native shells](0001-native-shell-tauri-capacitor.md)
**Audience:** anyone reconsidering where the quiz/adaptivity engine runs or what database it uses.

---

## Context

The PreACT English Coach needs a persistence + adaptivity engine behind the prototype
(`Skill / Question / QuizSession / Attempt / SkillState / Tutorial`). Two coupled choices
must be made before any schema lands:

1. **Where does the engine live?** Backend Python four-layer, the Frontend-Ring, or a split.
2. **What substrate persists it?** The forces are non-negotiable and partly already decided:

- **The UI spec mandates local-first.** §7: *"quiz/drill/feedback/progress surfaces SHALL
  function on cached content (Capacitor local-first); only the live coach requires
  connectivity."* That is an acceptance criterion, not a preference.
- **ADR-0001 already ships native shells** (Tauri macOS + Capacitor iOS) wrapping one
  Next.js app. The engine runs *inside that WebView*, on-device.
- **Single learner, auth deferred** (spec §1) — no multi-tenant server need today.
- **The coach is already settled** as SSE-over-BFF (prior transport brainstorm); it is the
  *one* online dependency and is **not** part of this decision.
- **The repo's own law:** four-layer doc — *"introduce protocols only when the second
  consumer arrives; document future abstractions now, build on demand."* A centralized
  server engine with no second client today would violate this.

External research (2026):
- **FSRS is designed for client-side, offline execution** — *"runs entirely locally… no
  internet connection… protects privacy,"* with a maintained TypeScript port (`ts-fsrs`).
  ([awesome-fsrs](https://open-spaced-repetition.github.io/awesome-fsrs/), [ts-fsrs](https://open-spaced-repetition.github.io/ts-fsrs/))
- **Local-first is the 2026 norm for exactly this shape** — embedded client DB that the
  server syncs *in the background, off the critical path* (Ink & Switch definition).
  Mature Postgres↔SQLite sync layers exist (**PowerSync**, **ElectricSQL**, **sqlite-sync
  CRDT**) — meaning *"start local, add sync later"* is a supported, low-regret path, not a
  dead end. ([PowerSync v1](https://powersync.com/blog/introducing-powersync-v1-0-postgres-sqlite-sync-layer), [ElectricSQL](https://electric-sql.com/blog/2023/09/20/introducing-electricsql-v0.6), [sqlite-sync](https://github.com/sqliteai/sqlite-sync), [offline-first stack 2026](https://cssauthor.com/offline-first-tech-stack/))

---

## Decision

**Engine home — the SPLIT:** the **learner-facing engine** (schema, FSRS scheduler,
adaptivity, grading) runs in the **Frontend-Ring, local-first, on-device**, behind the
ports in ADR-0006. The **generation side** (LLM question/tutorial generation + the live
coach agent) runs in the **backend** — questions generated *offline* and gated, the coach
streamed *online* over the BFF. This is the hybrid the brainstorm leaned toward.

**Substrate — Drizzle, one schema, two dialect targets, Postgres-first:** author the schema
once in **Drizzle ORM** (already in `frontend/`). Target **Postgres/Neon** as the
canonical/online store (reusing the exact `thread_store` migration pattern + the IR-NEON-5
`tablesFilter` guard) and keep the schema **SQLite-compatible** so the on-device store can
be SQLite under Capacitor. **No sync engine is built now** — the local store is the
working store for the single learner; a Postgres↔SQLite sync adapter is added *only when a
second device or backup need is real* (the supported path above keeps that cheap).

---

## Options considered & rejected

### Engine home

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A. Backend Python four-layer** (engine as a horizontal service; UI reads via BFF) | Centralizes logic; reuses trust/governance; one codebase for adaptivity | **Breaks the spec's local-first §7** (every drill needs the network); adds a server on the critical path with *no second consumer*; violates the four-layer "build on the second consumer" rule | ❌ Rejected — fails a hard acceptance criterion |
| **B. Frontend-Ring, fully local-first** (everything on-device, incl. generation) | Maximally offline; simplest deployment | Question/tutorial **generation** needs an LLM + the verifier gate — that belongs server-side (no API keys in client, spec §5; no live LLM on CI hot path) | ❌ Rejected — generation can't safely live in the client |
| **C. SPLIT: data+adaptivity frontend, generation+coach backend** | Honors local-first for the learner loop; keeps LLM + secrets server-side; matches ADR-0001 shells; FSRS client-side is the researched best practice | Two homes to reason about; content must be *delivered* to the device | ✅ **Chosen** |

### Substrate

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **1. Drizzle + Postgres/Neon only** | Reuses the live stack exactly; zero new infra | A server DB is *not* local-first; offline drills would need a cache layer anyway | ➖ Half-measure — fine for online, misses §7 |
| **2. Drizzle, Postgres + SQLite (dialect-portable), no sync yet** | One schema, online canonical + on-device SQLite; FSRS runs against local SQLite; sync is a *future adapter*, not a rewrite | Dual-dialect care (avoid PG-only types in shared tables); a real sync engine is deferred work | ✅ **Chosen** |
| **3. Adopt a sync engine now** (PowerSync/Electric/CRDT) | Turnkey offline↔online convergence | CRDTs carry *"significant overhead and complexity"* (research); **no second device today** → speculative | ❌ Rejected now — revisit on multi-device (decision trigger below) |

---

## Rationale

The spec's local-first clause and ADR-0001's on-device shells make the learner loop a
**client** concern; FSRS being purpose-built for offline client execution removes the only
technical reason it would need a server. Generation and the coach are the genuine
server concerns (LLM, secrets, the verifier gate, no-live-LLM-in-CI) — so the split falls
out of the constraints rather than being imposed. Choosing one Drizzle schema with a
SQLite-compatible shape keeps a single source of truth while honoring §7, and the mature
2026 Postgres↔SQLite sync ecosystem means deferring the sync engine is **low-regret**: the
door is documented-open (the four-layer principle) without paying for a CRDT layer that has
no second replica to converge with yet.

---

## Consequences

**Commits us to:**
- Engine schema + FSRS + adaptivity + grading implemented under `frontend/lib/` behind the
  ADR-0006 ports; SDKs (Drizzle, ts-fsrs) confined to `frontend/lib/adapters/`.
- A **dialect-portability constraint** on shared tables: no Postgres-only column types in
  tables that also live in the on-device SQLite store (the design doc's types stay abstract
  for this reason). Drizzle config extends the **IR-NEON-5 `tablesFilter`** to whitelist the
  engine tables and keep excluding LangGraph checkpoint tables.
- A **content-delivery path**: backend-generated, `reviewed`-gated `question`/`tutorial`
  rows must reach the device (seed bundle now; a pull/sync adapter later).
- The coach agent fork from `reactLoop` remains a **separate ⚠️ Ask-first / new-graph-node
  ADR** (flagged in the UI spec §5) — out of scope here.

**Accepted risks / mitigations:**
- *Dual-dialect drift* → mitigated by authoring in Drizzle once + a schema conformance test
  across both targets; keep types in the abstract set from the design doc §2.1.
- *Deferred sync becomes urgent* → **decision trigger:** the moment a second device, shared
  progress, or server-authoritative backup is required, adopt a Postgres↔SQLite sync
  adapter (PowerSync/Electric/CRDT) behind the existing repos — file a follow-on ADR; do
  **not** retrofit sync ad hoc.
- *Generation/device skew* → the `reviewed` gate + provenance (`generated_by`) keep the
  delivered content auditable.

---

## Supersedes / related

Makes canonical the engine-home + substrate sections of
[SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md](../Architectures/SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md).
Pairs with [ADR-0006](0006-subject-coach-component-protocols.md) (the port signatures).
Consistent with [ADR-0001](0001-native-shell-tauri-capacitor.md) (on-device shells) and the
[engine brainstorm](../plan/subject-coach-engine.brainstorm.md) (English-concrete, seams only).
