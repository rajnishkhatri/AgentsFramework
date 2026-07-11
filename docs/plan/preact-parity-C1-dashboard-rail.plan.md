---
title: 'PreAct Parity — Sprint C1: Dashboard rail + greeting · IMPLEMENTATION PLAN'
type: plan
sprint: C1
epic: C
date: 2026-07-10
status: Draft
owner: Rajnish Khatri
derives_from:
  - docs/plan/preact-parity-C1-dashboard-rail.spec.md
  - docs/adr/0026-session-repo-list-by-learner.md
governs:
  - docs/plan/preact-parity-C1-dashboard-rail.tasks.md   # atomic task list, this file's sibling
---

# Sprint C1 — Implementation Plan

## 0. Reading order

1. [spec.md](preact-parity-C1-dashboard-rail.spec.md) (the *what*)
2. [ADR-0026](../adr/0026-session-repo-list-by-learner.md) (the *why*)
3. This file (the *where in code* + *in what order*)
4. [tasks.md](preact-parity-C1-dashboard-rail.tasks.md) (executable, mapped 1:1 to FRs)

## 1. Architecture — where each spec field lands

Dependency arrows point inward toward `wire/` (root [AGENTS.md](../../AGENTS.md) §Architecture Invariants):

```
                   ┌────────────────────────────────────────────────┐
                   │ DashboardView.tsx                              │ presentational (F-R1)
                   │ + <header>          (greeting)                 │ Tailwind v4 @container
                   │ + <aside>           (rail: tiles + fallback)   │ single aria-live region
                   └──────────────────────┬─────────────────────────┘
                                          │ VM
                   ┌──────────────────────┴─────────────────────────┐
                   │ use_dashboard.ts / loadDashboard               │ hook + async gather
                   │ + Promise.all([...three existing, listByLearner]) │ FR-15 concurrent
                   │ + rail-scoped try/catch (FR-1 unavailable path) │
                   └──────────────────────┬─────────────────────────┘
                                          │ QuizSession[]  +  nowISO  +  LEARNER_ID
                   ┌──────────────────────┴─────────────────────────┐
                   │ translators/ (three new pure T1)               │ imports only wire/
                   │   greeting_vm.ts                               │
                   │   streak_vm.ts                                 │
                   │   weekly_sessions_vm.ts                        │
                   └──────────────────────┬─────────────────────────┘
                                          │ port method
                   ┌──────────────────────┴─────────────────────────┐
                   │ ports/engine/session_repo.ts                   │ + listByLearner(...)
                   └──────────────────────┬─────────────────────────┘
                                          │ implements
                   ┌──────────────────────┴─────────────────────────┐
                   │ adapters/engine/repos/drizzle_session_repo.ts  │ + listByLearner via db
                   │ adapters/engine/db/engine_db.ts (port)         │ + listClosedSessionsByLearner
                   │ adapters/engine/db/in_memory_engine_db.ts      │   fake impl
                   │ adapters/engine/db/drizzle_engine_db.ts        │   live pg/sqlite impl
                   └────────────────────────────────────────────────┘
```

Nothing above `translators/` imports Drizzle. Nothing outside `adapters/`
imports an SDK. `translators/` are pure T1 (Rule T1 + T2). The rail failure
path is scoped inside `loadDashboard`; the outer `Promise.all` never sees
the rejection — the header + mastery grid stay honest (FR-1).

## 2. File-level touchpoints (grouped by layer, dependency-ordered)

### 2.1 Ports (touch first — everything downstream depends on the shape)

| File | Change | FR / spec ref |
|------|--------|---------------|
| [frontend/lib/ports/engine/session_repo.ts](../../frontend/lib/ports/engine/session_repo.ts) | **Add** `listByLearner(subject, learnerId, options?): Promise<QuizSession[]>` to the interface + full JSDoc contract (five numbered rules from spec §4.1). One interface only (P1). | FR-12 · spec §4.1 |
| [frontend/lib/adapters/engine/db/engine_db.ts](../../frontend/lib/adapters/engine/db/engine_db.ts) | **Add** `listClosedSessionsByLearner(subject, learnerId, options?): Promise<QuizSession[]>` to the narrow `EngineDb` port under the `// --- quiz_session ---` block. | spec §4.2 |

### 2.2 Adapters (implement the ports)

| File | Change | FR / spec ref |
|------|--------|---------------|
| [frontend/lib/adapters/engine/repos/drizzle_session_repo.ts](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts) | **Add** `listByLearner()` method — one-liner delegating to `this.db.listClosedSessionsByLearner(...)`, wrapped in `try/catch` → `translate("listByLearner", err)` (matches the existing pattern at lines 84-88 / 121-123 / 132-135). | FR-13 · spec §4.1 |
| [frontend/lib/adapters/engine/db/in_memory_engine_db.ts](../../frontend/lib/adapters/engine/db/in_memory_engine_db.ts) | **Add** `listClosedSessionsByLearner()`: filter `this.sessions.values()` by `subject === s && learner_id === l && ended_at != null && (sinceISO == null || ended_at >= sinceISO)`; sort by `ended_at DESC, id ASC`. Return copies (not references). | FR-13 · spec §4.2 |
| [frontend/lib/adapters/engine/db/drizzle_engine_db.ts](../../frontend/lib/adapters/engine/db/drizzle_engine_db.ts) | **Add** `listClosedSessionsByLearner()`: Drizzle query `SELECT ... WHERE subject = ? AND learner_id = ? AND ended_at IS NOT NULL AND (sinceISO IS NULL OR ended_at >= sinceISO) ORDER BY ended_at DESC, id ASC`. Map each Drizzle row → wire `QuizSession` via existing row-map helper. **A4 / F-R8:** no Drizzle row type escapes. | FR-13 · spec §4.2 |
| [frontend/lib/adapters/engine/repos/engine_repos.test.ts](../../frontend/lib/adapters/engine/repos/engine_repos.test.ts) | **Add** a parametrized block for `DrizzleSessionRepo.listByLearner`: rejecting-db → `EngineRepoError`; empty → `[]`; excludes in-flight (`ended_at: null`); newest-first ordering; `sinceISO` inclusive lower-bound filter; subject-scoped (never crosses subjects). Failure paths first (TAP-4). | FR-13 · spec §8 |

### 2.3 Translators (three new pure files, unit-tested first)

Each file mirrors the shape of [today_focus_vm.ts](../../frontend/lib/translators/today_focus_vm.ts) — pure function, imports only `wire/` + stdlib, no `Date.now()` / `Math.random()` / React.

| File | Purpose | FR |
|------|---------|-----|
| **NEW** `frontend/lib/translators/greeting_vm.ts` | `toGreetingVM(nowISO, learnerId): GreetingVM` — time-of-day + title-cased id + `Intl.DateTimeFormat` subline. | FR-9, FR-10, FR-11 |
| **NEW** `frontend/lib/translators/streak_vm.ts` | `toStreakVM(closedSessions, nowISO): StreakVM` — consecutive-day count from `nowISO` local-date backwards, stopping at first gap; **1 session today = 1-day streak** (Q4). | FR-3, FR-4, FR-6, FR-7, FR-11 |
| **NEW** `frontend/lib/translators/weekly_sessions_vm.ts` | `toWeeklySessionsVM(closedSessions, nowISO, target?)` — ISO 8601 Monday-of-week boundary; target defaults to 3 (H6); `count` not clamped; label = `"K / 3 sessions"` with `K = min(count, target)`. | FR-8, FR-11 |
| **NEW** `frontend/lib/translators/greeting_vm.test.ts` · `streak_vm.test.ts` · `weekly_sessions_vm.test.ts` | Table-driven Vitest (T4) — failure/edge rows FIRST, watched-red before green. | §8 test plan |

### 2.4 Hook + view (compose the VM; render the surface)

| File | Change | FR |
|------|--------|-----|
| [frontend/components/dashboard/use_dashboard.ts](../../frontend/components/dashboard/use_dashboard.ts) | (a) Grow `DashboardVM` with `greeting: GreetingVM` + `rail: RailVM` (additive, no rename). (b) Extend `Promise.all` at line 58 to 4 concurrent reads — 4th = `ports.sessionRepo.listByLearner(subject, LEARNER_ID_from_args, { sinceISO: <nowISO - 30d> }).catch(_ => "rail-unavailable" sentinel)`. (c) Compose `RailVM` from the result: `status: "ok" | "unavailable"`; on error → `{status:"unavailable", streak:{present:false,days:0}, weekly:{count:0,target:3,label:"—"}}`. (d) `greeting` composed from `toGreetingVM(nowISO, learnerId)`. | FR-1, FR-2, FR-15 · spec §4.4 |
| [frontend/components/dashboard/use_dashboard.test.ts](../../frontend/components/dashboard/use_dashboard.test.ts) | **Add** three cases: (i) rail_unavailable_on_reject; (ii) rail_read_fires_concurrently (spy on all four reads); (iii) cold_start_returns_zero_and_present_false. | FR-1, FR-2, FR-15 |
| [frontend/components/dashboard/DashboardView.tsx](../../frontend/components/dashboard/DashboardView.tsx) | (a) Add outer wrapper with `@container` (Tailwind v4 utility) + `data-testid="dashboard-root"` for Playwright container-resize. (b) Add `<header>` above the existing `Skill mastery` section — renders `vm.greeting.headline` + subline. (c) Add `<aside aria-label="Trust rail">` containing `<StreakTile vm={vm.rail.streak}>`, `<WeeklyTile vm={vm.rail.weekly}>`, and — when `vm.rail.status === "unavailable"` — a subdued muted-text placeholder + `<button>` "Retry" (fires a re-load through the hook's `load()` again). (d) Layout: outer grid uses `@lg:` variants — below the container's `lg` threshold the rail renders as a horizontally-scrollable row below the header; above → right-column `<aside>` next to the mastery grid. (e) Single `aria-live="polite"` region owned by the rail; both tiles + the unavailable-label share it (no landmark churn). | FR-5, FR-1 · Q1 clarify |
| [frontend/components/dashboard/DashboardView.test.tsx](../../frontend/components/dashboard/DashboardView.test.tsx) | **Add** (i) rail_classes_include_container_query_variants — assert `@container` and `@lg:` class strings are present in the JSX; (ii) no_goal_or_note_tile_rendered — negative-assertion (FR-14); (iii) unavailable_state_renders_retry_button. | FR-5, FR-14, FR-1 |
| **NEW** `frontend/components/dashboard/StreakTile.tsx` · `WeeklyTile.tsx` | Presentational per-tile subcomponents (F-R1). Each renders from a VM prop; no port import. Cold-state copy live here. Storybook stories co-located under `frontend/tests/stories/` if a story exists for other tiles; otherwise deferred. | FR-2, FR-7, FR-8 |

### 2.5 E2E

| File | Change | FR |
|------|--------|-----|
| **NEW** `frontend/e2e/learn/dashboard_rail.spec.ts` | Three rows: (i) cold_start_renders_honest_empty_state — no closed sessions in dev seed → assert "Start a streak" + "0 / 3 sessions"; (ii) returning_learner_shows_streak_and_weekly — seed N closed sessions across consecutive days → assert `"N-day streak"` + `"M / 3 sessions"`; (iii) injected_clock_midnight_determinism — use Playwright `page.clock.install()` (or `?now=` dev-seed query param) to freeze `nowISO`; assert same streak count regardless of wall-clock. **Container-resize row** — resize the `[data-testid="dashboard-root"]` element, not the viewport, and assert the rail moves from below-header to right-aside. | §8 test plan, spec §4.7 DT-1 |

### 2.6 Architecture tests

| File | Change | FR |
|------|--------|-----|
| [frontend/tests/architecture/test_frontend_layering.ts](../../frontend/tests/architecture/test_frontend_layering.ts) *(existing walker)* | Confirm the three new `_vm.ts` translator files import ONLY `zod` / `wire/` / stdlib. Extend the walker's translator glob if it doesn't already pick up the new filenames. | FR-11 |
| [frontend/tests/architecture/test_port_conformance.test.ts](../../frontend/tests/architecture/test_port_conformance.test.ts) | Confirm `session_repo.ts` still exports exactly one `interface` after the addition. | FR-12 |
| [frontend/tests/architecture/test_engine_port_conformance.test.ts](../../frontend/tests/architecture/test_engine_port_conformance.test.ts) | If it enumerates port methods for structural conformance, add `listByLearner` to the enumerated set for `SessionRepo`. | FR-12 |

### 2.7 Docs, ADR, decisions.md

| File | Change |
|------|--------|
| [docs/adr/0026-session-repo-list-by-learner.md](../adr/0026-session-repo-list-by-learner.md) | **NEW (Proposed → Accepted at tasks→implement gate)** — this plan's why. |
| [docs/adr/index.md](../adr/index.md) | Append one-line entry for ADR-0026 (OKF bundle discipline). |
| [docs/adr/log.md](../adr/log.md) | Append 2026-07-10 log entry: `ADR-0026 proposed: SessionRepo.listByLearner ...`. |
| [docs/adr/decisions.md](../adr/decisions.md) | Append small non-obvious decisions (3–5 lines each): (a) H6 = 3-per-week ISO Monday-start + 7-dot-strip deferred with score-goal; (b) `sinceISO = nowISO - 30d` (Dashboard caller policy); (c) score-goal + coach-note deferred to Epic F alongside `projectedScore`; (d) responsive layout = Tailwind v4 `@container` (not `useSurface`); (e) streak floor = 1 day for first session today. |
| [docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md](preact-ui-prototype-parity-VISUAL-gap-report.md) | On merge: mark D-1 🟩 and D-5 🟨 with references. |

## 3. Migration steps (execution order)

Each step is a green build. The order is dependency-forced: ports before
adapters; translators (with tests) before hooks; hooks before views;
architecture tests before merge.

1. **Port shape (fail-first).** Add the JSDoc contract + method signature on
   `SessionRepo` and `EngineDb`; do NOT implement yet. Compilation goes red
   in the two adapters and the conformance test — the intended red step.
2. **Fake adapter first (green the compiler locally).** Implement
   `InMemoryEngineDb.listClosedSessionsByLearner`; implement
   `DrizzleSessionRepo.listByLearner`. Compilation goes green.
3. **Add the conformance rows (watched red).** Add the parametrized rows to
   `engine_repos.test.ts` — failure paths first. Run; watch red. Then wire
   the live `drizzleEngineDb.listClosedSessionsByLearner` query. Run; green.
4. **Translators (watched red per FR).** Author `streak_vm.test.ts` first
   with the failure/edge rows (FR-3, FR-4, FR-6) BEFORE the happy-path row
   (FR-7). Implement `streak_vm.ts`. Repeat for `weekly_sessions_vm` and
   `greeting_vm`.
5. **Hook growth.** Grow `DashboardVM` + `loadDashboard`; add the fourth
   concurrent read with rail-scoped `catch`. Update `use_dashboard.test.ts`
   with the three new cases. Green.
6. **View + tiles.** Add `<header>` + `<aside>` + two tile components +
   `@container` wrapper. Update `DashboardView.test.tsx` (three new cases,
   including the negative `no_goal_or_note_tile_rendered` assertion for
   FR-14). Green.
7. **Architecture tests.** Confirm the layering walker + port conformance
   suite pass; extend enumeration lists if needed.
8. **E2E.** Author `dashboard_rail.spec.ts` (three rows + container-resize).
   Run Playwright locally against the dev seed. Fix any container-query
   parent that's `display:contents` or `width:max-content` (the researched
   gotcha).
9. **ADR + decisions.md + index/log + gap-report.** Update the OKF bundle.
   Update the parity report cells for D-1 / D-5.
10. **`make check` + `pytest tests/architecture/ -q` + `pnpm test` +
    `pnpm playwright test` — all green.**
11. **Commit sequence.** One commit per step 1-9 with red-then-green tags
    visible in messages (satisfies the "seen to fail first" DoD).

## 4. Constitution touchpoints (Stage-4 analyze crosswalk)

Every invariant that could be broken, and how it holds.

| Invariant / rule | Touched by | How it stays green |
|------------------|------------|---------------------|
| **#1** dependency direction (adapters → ports → wire) | port addition | New method on `SessionRepo` returns wire `QuizSession[]`; adapter imports port + wire only. Verified by import-graph walker. |
| **#2** trust kernel unchanged | none | The port is not a trust type; no signing, no re-sign, no `trust/models.py` edit. |
| **#7** services must not import from components | none | Port sits under `frontend/lib/ports/engine/`; translators sit under `frontend/lib/translators/`. Neither imports a component. |
| **F-R1** no domain logic in components | view growth | Streak/weekly derivations live in translators. `DashboardView` receives `RailVM` composed; no `.reduce()` inline. |
| **F-R2** SDK imports only in adapters | port + translator work | The three new translator files import only `wire/` + stdlib; the port imports only `wire/` types. |
| **F-R3 / P1** one interface per port module | port addition | `session_repo.ts` still exports exactly one `interface`. Test: `test_port_conformance.test.ts`. |
| **F-R7** trace_id propagation | none | This is engine-read UI territory; no agent stream. |
| **F-R9** BFF holds no cloud creds | none | Work is Drizzle-side, server-only, no new env var. |
| **T1** pure translators | 3 new files | Each function signature accepts all state as parameters; no `Date.now()`, no `Math.random()`, no I/O. Architecture walker asserts (FR-11). |
| **G1 (new abstraction gate)** | port addition | ADR-0026 written, rejected alternatives documented, published as "Proposed" before implementation; Accepted at tasks→implement gate. |
| **C-4 honesty (Epic B)** | rail rendering | FR-2 (real zero, not placeholder); FR-14 (no score-goal / coach-note tile); FR-1 (subdued "unavailable" — never a fake number on error). |
| **Rule U4 (a11y streaming)** | rail rendering | Single `aria-live="polite"` region owned by the rail; both tiles + the unavailable-label share it. No aria-live churn. |
| **Rule U8 (Tailwind v4 `@theme`)** | responsive layout | `@container` variants; no viewport-scoped `lg:` on the rail. Layout is CSS-first, style-guide-aligned. |
| **Frontend Ring §14 rule against parallel client stores** | none | No new store. Session data is read fresh via `sessionRepo`; no in-memory cache mirroring. |

## 5. Explicit non-goals (to keep the sprint scoped)

- Score-goal tile · coach-note tile · `LearnerStatsRepo` port lift · Progress screen · FLAG-5 Wrap-up wire · anything C2 · multi-learner display-name lookup · new BFF env var · new dependency in `package.json`.

## 6. Baseline (must be green before implementation starts)

- `make check` on the current tree.
- `pnpm test` in `frontend/`.
- `pnpm tsc --noEmit` in `frontend/`.
- `pytest tests/architecture/ -q`.

If any of these are red at baseline, the "red-then-green" TDD signal is
noisy. Green the tree first.

## 7. Ready-to-branch checklist (for the human tasks→implement gate)

- [ ] Spec Approved (this plan's basis).
- [ ] ADR-0026 published as `Proposed`.
- [ ] Baseline gates green.
- [ ] Tasks file authored ([tasks.md](preact-parity-C1-dashboard-rail.tasks.md)) mapping 1:1 to §8 FRs.
- [ ] Human ratifies ADR-0026 as `Accepted` at the tasks→implement gate.
- [ ] Branch cut: `feat/preact-parity-c1-dashboard-rail`.
