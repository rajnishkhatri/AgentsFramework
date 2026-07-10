---
title: 'PreAct Parity — Sprint C1: Dashboard rail + greeting · TASKS'
type: tasks
sprint: C1
epic: C
date: 2026-07-10
status: Draft
owner: Rajnish Khatri
derives_from:
  - docs/plan/preact-parity-C1-dashboard-rail.spec.md
  - docs/plan/preact-parity-C1-dashboard-rail.plan.md
  - docs/adr/0026-session-repo-list-by-learner.md
---

# Sprint C1 — Task list

Each task is atomic (one commit-shaped unit of work), file-specific, and
verifies against exactly the spec §3 FR(s) named in "Verifies". Dependencies
(`deps:`) are hard — a task cannot start until its deps are green. `[P]` =
parallelizable with other same-`[P]` tasks in the same block. TDD is
watched-red: every task with a `red-then-green` marker MUST commit the red
step before the green step (spec §9 DoD).

Convention: `T{n}.{n}` = task; `red` = watched-red-first; `L1`/`L2`/`e2e` =
test layer.

## Block 0 — Baseline (must be green before any T1.x)

- **T0.1** — Run baseline gates on `main`.
  - Cmd: `make check && cd frontend && pnpm test && pnpm tsc --noEmit && cd .. && pytest tests/architecture/ -q`
  - Verifies: [plan §6](preact-parity-C1-dashboard-rail.plan.md#6-baseline-must-be-green-before-implementation-starts).
  - Blocking: yes. If red, green the tree first — do NOT start Block 1.

## Block 1 — Port shape (dependency root)

- **T1.1** — Add `listByLearner()` method signature + JSDoc contract to `SessionRepo`.
  - File: [frontend/lib/ports/engine/session_repo.ts](../../frontend/lib/ports/engine/session_repo.ts).
  - Content: new method after `get()`; five numbered behavioral rules from spec §4.1 verbatim.
  - Verifies: **FR-12** (single-interface preserved).
  - deps: T0.1.
  - Expected: compiler goes red in T1.2/T1.3/T1.4 sites (intended).

- **T1.2** — Add `listClosedSessionsByLearner()` to the `EngineDb` row-level port.
  - File: [frontend/lib/adapters/engine/db/engine_db.ts](../../frontend/lib/adapters/engine/db/engine_db.ts).
  - Placement: inside the `// --- quiz_session ---` block, immediately after `patchSessionClose(...)`.
  - Verifies: spec §4.2 contract text.
  - deps: T1.1.

## Block 2 — Adapters (fake first, then live seam) — parallel after T1.2

- **T2.1 [P]** — Implement the fake in `InMemoryEngineDb`.
  - File: [frontend/lib/adapters/engine/db/in_memory_engine_db.ts](../../frontend/lib/adapters/engine/db/in_memory_engine_db.ts).
  - Impl: filter `this.sessions.values()` by subject + learner_id + `ended_at != null` + optional `>= sinceISO`; sort `ended_at DESC`, then `id ASC`; return **copies** (spread each row) to preserve fake purity.
  - Verifies: FR-13 (behavioral fake).
  - deps: T1.2.

- **T2.2 [P]** — Implement the live seam in `drizzleEngineDb`.
  - File: [frontend/lib/adapters/engine/db/drizzle_engine_db.ts](../../frontend/lib/adapters/engine/db/drizzle_engine_db.ts).
  - Impl: Drizzle query on `quiz_session` with `WHERE subject = ? AND learner_id = ? AND ended_at IS NOT NULL AND (sinceISO IS NULL OR ended_at >= sinceISO) ORDER BY ended_at DESC, id ASC`. Row-map each result → wire `QuizSession` via the existing row-map helper. **No vendor type escapes** (Rule A4/F-R8).
  - Verifies: FR-13 (live seam).
  - deps: T1.2.

- **T2.3** — Wire `DrizzleSessionRepo.listByLearner`.
  - File: [frontend/lib/adapters/engine/repos/drizzle_session_repo.ts](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts).
  - Impl: one-liner `try { return await this.db.listClosedSessionsByLearner(subject, learnerId, options); } catch (err) { throw translate("listByLearner", err); }` — mirrors the existing `close()` / `get()` shape.
  - Verifies: FR-13 (repo error translation preserved, no vendor noise).
  - deps: T2.1, T2.2. Compilation now green.

- **T2.4 [red]** — Author conformance rows in `engine_repos.test.ts` — FAILURE PATHS FIRST.
  - File: [frontend/lib/adapters/engine/repos/engine_repos.test.ts](../../frontend/lib/adapters/engine/repos/engine_repos.test.ts).
  - Rows (in this order):
    1. `sessionRepo_listByLearner_rejects_translated_to_EngineRepoError` — `rejectingDb()` (existing helper) → assert `.rejects.toBeInstanceOf(EngineRepoError)` (matches DrizzleSkillTaxonomy pattern at line 80).
    2. `sessionRepo_listByLearner_empty_returns_empty_array` — no sessions seeded → `[]`.
    3. `sessionRepo_listByLearner_excludes_inflight` — seed one closed + one open (`ended_at: null`) → only the closed one returned.
    4. `sessionRepo_listByLearner_newest_first_with_id_tiebreak` — seed three closed at identical `ended_at` → assert `id ASC` tiebreak.
    5. `sessionRepo_listByLearner_sinceISO_inclusive_lower_bound` — seed rows straddling the boundary → assert inclusivity.
    6. `sessionRepo_listByLearner_subject_scoped` — seed rows across two subjects with same learner_id → only the queried subject returned.
  - Watched-red first (commit red step), THEN wire T2.1/T2.2 to green.
  - Verifies: FR-13 (parametrized conformance).
  - deps: T2.3.

## Block 3 — Translators (three parallel pipelines, each red-first)

### 3a — `greeting_vm.ts`

- **T3a.1 [red]** — Author `greeting_vm.test.ts` — boundary rows FIRST.
  - File: **NEW** `frontend/lib/translators/greeting_vm.test.ts`.
  - Rows: `time_of_day_boundaries` — table-driven `[05:00 → morning, 11:59 → morning, 12:00 → afternoon, 17:59 → afternoon, 18:00 → evening, 04:59 → evening]`; `subline_uses_intl_datetime` — assert format contains weekday + month + day (locale-agnostic pattern match); `title_case_id_maya_becomes_Maya`.
  - Verifies: **FR-9, FR-10, FR-11**.
  - deps: T0.1. Watched-red.

- **T3a.2** — Implement `greeting_vm.ts` to green T3a.1.
  - File: **NEW** `frontend/lib/translators/greeting_vm.ts`.
  - Pattern: mirror `today_focus_vm.ts` (imports only from `"../wire/engine_entities"` or none; pure function).
  - deps: T3a.1 red.

### 3b — `streak_vm.ts`

- **T3b.1 [red]** — Author `streak_vm.test.ts` — failure/edge rows FIRST.
  - File: **NEW** `frontend/lib/translators/streak_vm.test.ts`.
  - Rows: `empty_input_present_false` (FR-2); `stale_sessions_return_present_false` (all `ended_at` older than 48h → present:false) (FR-3); `inflight_session_excluded` (row with `ended_at: null` in input — belt-and-suspenders since port filters — verify no throw + not counted) (FR-4); `midnight_boundary_deterministic` (nowISO at 00:00:00 local — earlier session belongs to previous day) (FR-6); `one_session_today_equals_one_day_streak` (Q4 clarify decision) (FR-7); `three_day_consecutive_returns_three` (FR-7); `three_days_with_gap_stops_at_first_gap` (FR-7).
  - Verifies: **FR-2, FR-3, FR-4, FR-6, FR-7, FR-11**.
  - deps: T0.1. Watched-red.

- **T3b.2** — Implement `streak_vm.ts` to green T3b.1.
  - File: **NEW** `frontend/lib/translators/streak_vm.ts`.
  - Impl: bucket each session's `ended_at` to `YYYY-MM-DD` in the `nowISO` local timezone (use `Intl.DateTimeFormat` `en-CA` for ISO date format); walk backwards from today, incrementing while a bucket exists, stopping at first gap; day-1 counts as `{present: true, days: 1}` (Q4).
  - deps: T3b.1 red.

### 3c — `weekly_sessions_vm.ts`

- **T3c.1 [red]** — Author `weekly_sessions_vm.test.ts` — failure/edge rows FIRST.
  - File: **NEW** `frontend/lib/translators/weekly_sessions_vm.test.ts`.
  - Rows: `empty_input_zero_of_three` (FR-2); `monday_start_week_math` (a Sunday `ended_at` belongs to the PREVIOUS week, not the current; ISO 8601 boundary); `count_greater_than_target_label_caps_at_three_but_count_stays_real` (count=5 → label "3 / 3", vm.count=5); `sinceMonday_inclusive` (a session at exactly 00:00:00 local Monday → counted).
  - Verifies: **FR-2, FR-8, FR-11**.
  - deps: T0.1. Watched-red.

- **T3c.2** — Implement `weekly_sessions_vm.ts` to green T3c.1.
  - File: **NEW** `frontend/lib/translators/weekly_sessions_vm.ts`.
  - Impl: compute Monday-of-week-containing-`nowISO` at 00:00 local; count sessions whose `ended_at` falls in `[monday00 .. nowISO]`; `label = min(count, target) + " / " + target + " sessions"`; return `{count, target, label}`.
  - deps: T3c.1 red.

## Block 4 — Hook growth

- **T4.1** — Grow `DashboardVM` + `RailVM` interfaces.
  - File: [frontend/components/dashboard/use_dashboard.ts](../../frontend/components/dashboard/use_dashboard.ts).
  - Change: add `greeting: GreetingVM` + `rail: RailVM` fields to `DashboardVM`; export `RailVM` interface with `{status: "ok" | "unavailable", streak: StreakVM, weekly: WeeklySessionsVM}`.
  - Expected: this breaks existing `DashboardVM` consumers in tests — those get updated in T4.4.
  - deps: T3a.2, T3b.2, T3c.2.

- **T4.2** — Extend `loadDashboard`'s `Promise.all` to four concurrent reads.
  - File: [frontend/components/dashboard/use_dashboard.ts](../../frontend/components/dashboard/use_dashboard.ts) at the `Promise.all([...])` at line 58.
  - Change: add the 4th read: `ports.sessionRepo.listByLearner(subject, learnerId, { sinceISO: computeSinceISO(nowISO, 30) }).catch(() => "rail-unavailable")`. Add a private `computeSinceISO(nowISO, days)` helper (pure; no `Date.now()`).
  - Verifies: **FR-15**.
  - deps: T4.1.

- **T4.3** — Compose `greeting` + `rail` in `loadDashboard`'s return.
  - File: same.
  - Change: after the `Promise.all` resolves, compose `greeting = toGreetingVM(nowISO, learnerId)`; branch on the 4th result — if `"rail-unavailable"` sentinel → `rail = {status:"unavailable", streak:{present:false,days:0}, weekly:{count:0,target:3,label:"—"}}`; else → `rail = {status:"ok", streak: toStreakVM(sessions, nowISO), weekly: toWeeklySessionsVM(sessions, nowISO)}`.
  - Verifies: **FR-1, FR-2**.
  - deps: T4.2.

- **T4.4 [red]** — Extend `use_dashboard.test.ts`.
  - File: [frontend/components/dashboard/use_dashboard.test.ts](../../frontend/components/dashboard/use_dashboard.test.ts).
  - Rows: `rail_unavailable_on_listByLearner_reject` (inject a rejecting `sessionRepo`; assert VM has header + `Skill mastery` + `rail.status === "unavailable"`) (FR-1); `rail_read_fires_concurrently` (spy on all four reads; assert timing shows they resolve inside a single `Promise.all`, not serial) (FR-15); `cold_start_returns_zero_and_present_false` (empty sessions → rail.streak.present === false, weekly.count === 0) (FR-2).
  - Watched-red first.
  - deps: T4.3.

## Block 5 — View + tiles

- **T5.1** — Create `StreakTile.tsx` + `WeeklyTile.tsx` presentational components.
  - Files: **NEW** `frontend/components/dashboard/StreakTile.tsx`, **NEW** `frontend/components/dashboard/WeeklyTile.tsx`.
  - Impl: pure props-in components; StreakTile renders `"Start a streak"` when `!vm.present`, else `"N-day streak"`; WeeklyTile renders `vm.label`. Each has an `aria-label` describing state ("Streak: 3 days", "Weekly sessions: 2 of 3"). Uses semantic tokens only (Rule U8).
  - Verifies: **FR-2, FR-7, FR-8**.
  - deps: T4.1.

- **T5.2** — Grow `DashboardView` with `<header>`, `<aside>`, and `@container`.
  - File: [frontend/components/dashboard/DashboardView.tsx](../../frontend/components/dashboard/DashboardView.tsx).
  - Change:
    (a) Wrap the outer `<div>` (line 24) with `@container` class + `data-testid="dashboard-root"`.
    (b) Add `<header>` above the existing `TodayFocusBanner` block — renders `vm.greeting.headline` (h1) + `vm.greeting.subline` (muted).
    (c) Add `<aside aria-label="Trust rail">` in a grid cell — inside: single `aria-live="polite"` region containing `<StreakTile>`, `<WeeklyTile>`, and — when `vm.rail.status === "unavailable"` — a muted "Trust rail unavailable" `<span>` + a `<button>` "Retry" that calls the hook's `load()` again.
    (d) Layout: outer wrapper uses Tailwind v4 `@container` + `@lg:grid-cols-[1fr_320px]` (or equivalent) so at ≥ container-lg the rail becomes right-column; below → row-below-header.
  - Verifies: **FR-1, FR-5**.
  - deps: T5.1.

- **T5.3 [red]** — Extend `DashboardView.test.tsx`.
  - File: [frontend/components/dashboard/DashboardView.test.tsx](../../frontend/components/dashboard/DashboardView.test.tsx).
  - Rows: `rail_classes_include_container_query_variants` (assert JSX carries `@container` and `@lg:` class strings) (FR-5); `no_goal_or_note_tile_rendered` (negative-assertion — grep the rendered output for "goal" / "coach note" copy and assert absent) (FR-14); `unavailable_state_renders_retry_button` (render VM with `rail.status = "unavailable"`; assert `<button>Retry</button>` present, tiles absent, muted label present) (FR-1).
  - Watched-red first.
  - deps: T5.2.

## Block 6 — Architecture tests

- **T6.1** — Verify layering walker picks up new translators.
  - File: [frontend/tests/architecture/test_frontend_layering.ts](../../frontend/tests/architecture/test_frontend_layering.ts).
  - Change: if the walker enumerates translator files explicitly, add `greeting_vm.ts` / `streak_vm.ts` / `weekly_sessions_vm.ts`. Assert each imports only `zod` / `wire/` / stdlib.
  - Verifies: **FR-11**.
  - deps: T3a.2, T3b.2, T3c.2.

- **T6.2** — Verify `SessionRepo` still a single-interface module.
  - File: [frontend/tests/architecture/test_port_conformance.test.ts](../../frontend/tests/architecture/test_port_conformance.test.ts).
  - Change: none if the walker is generic; else add explicit row.
  - Verifies: **FR-12**.
  - deps: T1.1.

- **T6.3** — Verify `SessionRepo` method-set includes `listByLearner`.
  - File: [frontend/tests/architecture/test_engine_port_conformance.test.ts](../../frontend/tests/architecture/test_engine_port_conformance.test.ts).
  - Change: if it enumerates methods per port for structural conformance, add `listByLearner`.
  - Verifies: **FR-12** (structural).
  - deps: T1.1.

## Block 7 — E2E

- **T7.1** — Author `dashboard_rail.spec.ts`.
  - File: **NEW** `frontend/e2e/learn/dashboard_rail.spec.ts`.
  - Rows:
    1. `cold_start_renders_honest_empty_state` — dev-seed with 0 closed sessions → assert `"Start a streak"` visible + `"0 / 3 sessions"` visible.
    2. `returning_learner_shows_streak_and_weekly` — dev-seed with 3 closed sessions across 3 consecutive local-days (frozen clock via `page.clock.install()`) → assert `"3-day streak"` + `"3 / 3 sessions"`.
    3. `injected_clock_midnight_determinism` — install clock at 23:59:59 → advance to 00:00:00 next day → assert streak count unchanged (session-belongs-to-previous-day rule).
    4. `container_resize_moves_rail_from_row_to_aside` — resize the `[data-testid="dashboard-root"]` **element** (not the viewport) via `evaluate(el => el.style.maxWidth = '380px')` → assert rail is a row below header; then set to `1280px` → assert rail is right-column `<aside>`.
    5. `retry_button_re_fires_read_after_transient_error` — mock `sessionRepo.listByLearner` to reject once then succeed; assert Retry button clears the unavailable state.
  - Verifies: **FR-1, FR-2, FR-5, FR-6, FR-7, FR-8**.
  - deps: T5.3, T4.4.

## Block 8 — Docs, ADR, decisions.md — parallel with any post-T7 work

- **T8.1 [P]** — Add `decisions.md` entries.
  - File: [docs/adr/decisions.md](../adr/decisions.md).
  - Entries (append; 3–5 lines each): (a) H6 = 3-per-week ISO Monday-start + 7-dot-strip deferred with score-goal; (b) `sinceISO = nowISO - 30d` (Dashboard caller policy); (c) score-goal + coach-note deferred to Epic F alongside `projectedScore`; (d) responsive layout = Tailwind v4 `@container` (not `useSurface`); (e) streak floor = 1 day for first session today.
  - Verifies: spec §9 DoD (3 new `decisions.md` lines).
  - deps: T4.4 (once behavior is confirmed).

- **T8.2 [P]** — Add ADR-0026 to the OKF index + log.
  - Files: [docs/adr/index.md](../adr/index.md), [docs/adr/log.md](../adr/log.md).
  - Content: one-line index row (with description); newest-first log entry dated 2026-07-10 "ADR-0026 proposed: SessionRepo.listByLearner ...".
  - Verifies: OKF bundle discipline (see [ADR-0025 log entry](../adr/log.md) precedent).
  - deps: T0.1 (any time).

- **T8.3 [P]** — Update the parity report cells (D-1, D-5).
  - File: [docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md](preact-ui-prototype-parity-VISUAL-gap-report.md).
  - Change: mark D-1 🟩 with references to `greeting_vm.ts` + `DashboardView.tsx` header; mark D-5 🟨 (streak+weekly shipped; goal+note still open, deferred to Epic F).
  - Verifies: spec §9 DoD.
  - deps: T5.3.

## Block 9 — Ratchet + green + PR

- **T9.1** — Full local gate run.
  - Cmd: `make check && cd frontend && pnpm test && pnpm tsc --noEmit && pnpm playwright test frontend/e2e/learn/dashboard_rail.spec.ts && cd .. && pytest tests/architecture/ -q`.
  - Verifies: spec §9 DoD (all gates green).
  - Paste actual output into the commit + PR body (not summary — the honesty rule).
  - deps: T7.1, T6.1, T6.2, T6.3.

- **T9.2** — Human ratifies ADR-0026 to `Accepted`.
  - File: [docs/adr/0026-session-repo-list-by-learner.md](../adr/0026-session-repo-list-by-learner.md) — change status frontmatter + heading; append the [log.md](../adr/log.md) "ratified" line.
  - Verifies: [ADR-0026 §Status](../adr/0026-session-repo-list-by-learner.md).
  - deps: T9.1 (Accepted only when spec's DoD is proven met).

- **T9.3** — Cut PR.
  - Branch: `feat/preact-parity-c1-dashboard-rail`.
  - Body: summary + link the spec/plan/ADR + paste the T9.1 output.
  - deps: T9.2.

## FR → task crosswalk (Stage-4 check)

| FR | Owning task(s) |
|----|----------------|
| FR-1 | T4.3, T4.4, T5.2, T5.3, T7.1 |
| FR-2 | T3b.1, T3c.1, T4.4, T5.1, T7.1 |
| FR-3 | T3b.1, T3b.2 |
| FR-4 | T3b.1, T3b.2 |
| FR-5 | T5.2, T5.3, T7.1 |
| FR-6 | T3b.1, T3b.2, T7.1 |
| FR-7 | T3b.1, T3b.2, T5.1, T7.1 |
| FR-8 | T3c.1, T3c.2, T5.1, T7.1 |
| FR-9 | T3a.1, T3a.2 |
| FR-10 | T3a.1, T3a.2 |
| FR-11 | T3a.1, T3b.1, T3c.1, T6.1 |
| FR-12 | T1.1, T6.2, T6.3 |
| FR-13 | T2.1, T2.2, T2.3, T2.4 |
| FR-14 | T5.3 |
| FR-15 | T4.2, T4.4 |

Every FR maps to ≥ 1 task; every task cites the FR(s) it verifies. Zero-coverage
check clean.

## Parallelization envelope (for pace)

The blocks below can run concurrently once their `deps:` clear.

- Block 3 (three translator pipelines 3a / 3b / 3c) — fully parallel after T0.1.
- Block 2 T2.1 + T2.2 — parallel after T1.2.
- Block 8 (T8.1, T8.2, T8.3) — parallel with each other and with Block 7.

Serial spine: T0.1 → T1.1/T1.2 → T2.3/T2.4 → T4.1/T4.2/T4.3/T4.4 → T5.2/T5.3
→ T7.1 → T9.1 → T9.2 → T9.3.
