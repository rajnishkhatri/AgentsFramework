---
type: decision-record
title: 'ADR-0034: Coach session marker stays in-memory until the threads BFF Cloud SQL bind (D4 the closer)'
status: accepted
created: 2026-07-15
updated: 2026-07-15
owner: Rajnish Khatri
related: eng-coach-gcp-deploy.spec.md, eng-coach-gcp-deploy.brainstorm.md, 0012-subject-coach-context-contract-hint-ladder.md, 0013-subject-coach-test-mode.md
tags: [decision-record]
---

# ADR-0034: Coach session marker stays in-memory until the threads BFF Cloud SQL bind (D4 the closer)

**Status:** Proposed — 2026-07-15.
**Related:** [eng-coach-gcp-deploy.spec.md](../plan/eng-coach-gcp-deploy.spec.md) (FR-14/15), [brainstorm Q3 + D4/D5](../plan/eng-coach-gcp-deploy.brainstorm.md), ADR-0012 (the marker-on-BFF plane this defers durability on), ADR-0013 (the tripwire shape this tombstone mirrors), [decisions.md:594-595](decisions.md) (learner-identity "Rejected: durable store"), [`bff_cloudsql_thread_repo.plan.md`](../plans/bff_cloudsql_thread_repo.plan.md).
**Audience:** anyone reconsidering coach-marker durability, or landing the threads BFF Cloud SQL plane.

---

## Context

The durable submit-once coach marker (ADR-0012's 2026-07-02 Amendment — "a minimal
BFF coach-session marker") needs a server-visible store.
[`selectCoachMarkerRepo`](../../frontend/lib/adapters/coach_marker/marker_repo.ts)
returns `PgCoachMarkerRepo` when `DATABASE_URL` is set, else
`InMemoryCoachMarkerRepo`. The Cloud Run `agent-frontend` service binds **no**
`DATABASE_URL` (F-R9 / blast-radius: no Cloud SQL socket on the public frontend), and
the frontend has **no migration runner** ([`drizzle.config.ts:23-25`](../../frontend/drizzle.config.ts)
documents its own gap: `drizzle-kit` is not installed; nothing applies the
coach-marker migration
[`frontend/lib/adapters/thread_store/db/migrations/0001_coach_session_marker.sql`](../../frontend/lib/adapters/thread_store/db/migrations/0001_coach_session_marker.sql)
— a loose SQL file no script/Dockerfile/deploy phase runs; the drizzle-kit
`frontend/drizzle/` dir holds only unrelated test-item migrations). So the marker
runs in-memory: per-instance, non-durable, lost on cold start or across >1 instance.

Two facts bound the decision:
1. **This is a fresh, ratified decision on this branch.** The learner-identity slice
   already recorded **"Rejected: durable store"** + "Q-C3 in-memory"
   ([decisions.md:594-595](decisions.md)). Forcing durability now would reverse it.
2. **Threads are already walking to the BFF Cloud SQL plane** on the *same*
   `DATABASE_URL` switch ([`bff_cloudsql_thread_repo.plan.md`](../plans/bff_cloudsql_thread_repo.plan.md)).
   A second durability plane for the coach marker (D5, via the middleware) would stand
   up two planes for two tiny tables and amend ADR-0012.

## Decision

**Defer coach-marker durability: accept `InMemoryCoachMarkerRepo` for this deploy
slice, time-boxed to the threads BFF Cloud SQL bind.** When that bind lands, close
durability via **D4** (frontend `PgCoachMarkerRepo` on the *same* `DATABASE_URL` +
migrate path) — **not** D5 (middleware plane). The marker fails **closed** in-memory
(unknown state → strip answer fields; never a leak). The time-box is enforced by a
**mechanical tombstone** (spec FR-15), ADR-0013-shaped.

## Options considered & rejected

| Option | Why not (now) |
|---|---|
| **D5 — route the marker through the middleware** | Amends ADR-0012; stands up a *second* durability plane while threads already route to the BFF; extra hot-path hop. Two planes for two tiny tables. Highest cost, weakest "why now." |
| **D4 — finish the BFF Cloud SQL bind now** | Architecturally the right closer, but bundling it here reverses the just-ratified "Rejected: durable store" and expands this deploy slice into the full Piece-C Terraform bind. Correct **later**, on the threads switch — not in this slice. |
| **Prose-only deferral** | A prose "we'll do D4 later" rots (the ADR-0011/0012/0013 lesson). Rejected in favor of the mechanical tombstone. |
| **Red-in-CI-today reminder test** | Fights `make check` and is a G8 smell. The tombstone must be **green today** (antecedent false) and red only on a conscious future change. |

## Rationale

Defer is **consistent with a decision already ratified on this branch**, keeps the
frontend credential-free (F-R9), and avoids inventing a second durability architecture
for a marker that threads' own plane will carry. The accepted cost is real but bounded:
known multi-instance / cold-start marker flapping, which fails *closed* — a submit-once
quality/UX gap, not a data-exposure one — survivable for a first usable `/learn`.

## Consequences

- **Accepted risk:** submit-once marker flapping across Cloud Run instances / cold
  starts. Mitigation: fails closed (strips answer fields under unknown state); bounded
  by the time-box.
- **The real forgot-D4 failure is named:** if TF later binds `DATABASE_URL` **without**
  a migration-apply path for `0001`, `PgCoachMarkerRepo` runs against a missing table
  and its fail-closed `catch` ([marker_repo.ts:101-105](../../frontend/lib/adapters/coach_marker/marker_repo.ts))
  strips answer fields **forever** — the same silent UX hole, harder to spot. Note
  this is *not* "URL present but repo still in-memory" (unreachable — the selector
  switches to Pg the instant the URL is set).
- **Tombstone (FR-15, ADR-0013-shaped):** an architecture test whose antecedent is
  false today (frontend binds no `DATABASE_URL`) → **green now**; goes **red** when
  `cloud-run-frontend.tf` gains a `DATABASE_URL` binding **without** a migrate path for
  `0001_coach_session_marker.sql`; **green again** once D4 (bind + migrate) lands. The
  conscious pairing cannot be skipped silently.
- **D4 is the named closer**, not a silent TODO — recorded here and pinned by the
  tombstone.

## Supersedes / related

Realizes [eng-coach-gcp-deploy.spec.md](../plan/eng-coach-gcp-deploy.spec.md) FR-14/15.
Defers durability on ADR-0012's marker plane; mirrors ADR-0013's tripwire mechanism;
consistent with [decisions.md:594-595](decisions.md). Pairs with ADR-0033 (D7 seed).
