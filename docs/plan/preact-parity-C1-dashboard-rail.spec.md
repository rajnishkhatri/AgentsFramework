---
title: 'PreAct Parity — Sprint C1: Dashboard rail + greeting'
type: spec
sprint: C1
epic: C
date: 2026-07-10
status: Draft
owner: Rajnish Khatri
derives_from:
  - docs/plan/preact-parity-sprint-board-C.md          # sprint board (Stage-1 CLOSED)
  - docs/plan/preact-parity-epic-C.brainstorm.md       # Stage-1 brainstorm (audit + directions)
  - docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md  # findings D-1, D-5
governs:
  - docs/plan/preact-parity-C1-dashboard-rail.plan.md  # to author at plan gate
  - docs/plan/preact-parity-C1-dashboard-rail.tasks.md # to author at tasks gate
adr_required:
  - docs/adr/00XX-session-repo-list-by-learner.md      # G1: new derivation path on existing port
findings_in_scope:
  - D-1   # Dashboard greeting ("Let's get you to 28, Maya." + day/time)
  - D-5   # Dashboard rail — streak + weekly (goal/note explicitly deferred)
findings_deferred:
  - D-5-goal   # score-goal tile — no honest engine source; revisit Epic F
  - D-5-note   # coach-note tile — no honest engine source; revisit Epic F
---

# Sprint C1 — Dashboard rail + greeting

## 1. Goal

Restore the two "coach who knows you" surfaces on the Dashboard that make the
app feel personal on first sight, with **only honest content**: a greeting that
uses the injected clock + learner id, and a right rail that renders **streak**
and **weekly sessions** from a real engine read. Tiles with no honest source
today (**score-goal**, **coach-note**) are explicitly not rendered — no
placeholders, no fake numbers. C-4 honesty rule (from Epic B) governs every
tile.

The outcome is a Dashboard that increases trust before the learner touches a
single question, and a durable engine read (`SessionRepo.listByLearner`) that
the rest of Epic C+F can consume without inventing a new port.

## 2. Context

The Stage-1 brainstorm audit ([preact-parity-epic-C.brainstorm.md](preact-parity-epic-C.brainstorm.md))
verified two premises and **refuted a third**:

- **P6/P7 verified.** Today's Dashboard renders `TodayFocusBanner` → `Skill
  mastery` → secondary actions ([DashboardView.tsx](../../frontend/components/dashboard/DashboardView.tsx)).
  There is no `<header>` with a greeting, no `<aside>` with a trust rail, and
  `DashboardVM` has three fields: `buckets`, `todayFocus`, `reviewMissesCount`
  ([use_dashboard.ts:32-39](../../frontend/components/dashboard/use_dashboard.ts:32)).
- **P8 REFUTED.** Streak and weekly-sessions are **not** derivable from
  existing engine reads. `SessionRepo` today exposes `open`/`close`/`get` only
  ([session_repo.ts:39-58](../../frontend/lib/ports/engine/session_repo.ts:39)).
  A new read method is required.
- **P9/P11 REFUTED.** Score-goal and coach-note **have no honest engine source
  today.** Rendering them with placeholders would violate the C-4 honesty rule.

The sprint board ([preact-parity-sprint-board-C.md](preact-parity-sprint-board-C.md))
chose composition **D2 → D4** across two sprints. C1 owns D2 (this spec). D3
(`LearnerStatsRepo` as a new horizontal port) was deferred to Epic F under the
abstraction-introduction rule — only build the port when a second consumer
arrives.

**Why now.** Epic C is the trust-relationship increment. C1 lands the smallest
honest step: two rail tiles + a greeting derived from a new (small) engine
read. It is independently releasable and unblocks Epic F's future work by
planting the read seam under `SessionRepo` instead of a new port.

## 3. Functional requirements (EARS)

Failure paths first (TAP-4). Each FR maps to a test row in §8.

### Failure / edge (write first, watch fail)

- **FR-1.** IF the engine port list-by-learner method rejects with an
  `EngineRepoError` THEN the Dashboard SHALL still render the greeting header
  and the `Skill mastery` grid, and the rail region SHALL render **inline**
  with a subdued muted-text label `"Trust rail unavailable"` **and** a
  retry link (renders as a `<button>` that re-fires the read; not a page
  reload). The failure is announced to screen readers via a stable
  `aria-live="polite"` region owned by the rail (SAME live region used for
  streak/weekly, so landmark identity is preserved). No toast, no banner, no
  page crash, no blank rail.
- **FR-2.** IF `listByLearner` returns `[]` (cold start — no closed sessions)
  THEN the streak tile SHALL render the copy `"Start a streak"` and the weekly
  tile SHALL render `"0 / 3 sessions"` (real zero from real read, not a
  placeholder), and neither tile SHALL show `"—"`, `"?"`, or a fake N > 0.
- **FR-3.** IF `listByLearner` returns closed sessions that are **all older
  than 48h from `nowISO`** THEN the streak tile SHALL render the copy `"Start
  a streak"` (streak = 0), never `"1-day streak"`.
- **FR-4.** IF `listByLearner` returns a session whose `ended_at` is `null`
  (in-flight, never closed) THEN the streak translator SHALL exclude it from
  the count and SHALL NOT throw.
- **FR-5.** THE SYSTEM SHALL render the Dashboard responsive layout via
  Tailwind v4 **container queries** (`@container` on the Dashboard root; rail
  region uses `@lg:` variants to flip from below-header row → right-side
  `<aside>`), NOT via the `useSurface` hook nor via viewport-scoped `lg:`
  breakpoints. The same JSX renders in both modes (single ARIA tree, single
  aria-live region); CSS moves the rail's grid-column. The rail's parent
  MUST set `container-type: inline-size` — a validated arrangement (Playwright
  container-resize assertion, not viewport-resize). Reason: hydration-safe
  (no SSR two-pass), zero JS bundle add, correct if a future sidebar narrows
  the Dashboard's effective width. `useSurface` remains valid for *behavioral*
  branches (touch handlers, iPad-only CoachPanel per Phase-4) but is the
  wrong tool for layout here.
- **FR-6.** IF `nowISO` crosses a local-date midnight boundary between two
  session `ended_at` values THEN the streak translator SHALL treat the earlier
  session's date as the previous local-date bucket (no off-by-one at
  midnight), given the same injected `nowISO`.

### Event-driven (happy paths)

- **FR-7.** WHEN the Dashboard loads for a learner with ≥ 1 closed session in
  the last `nowISO`-local-24h THEN the streak tile SHALL render `"N-day
  streak"` where `N` is the count of consecutive local-date buckets (up to and
  including today) with ≥ 1 closed session.
- **FR-8.** WHEN the Dashboard loads THEN the weekly tile SHALL render `"K /
  3 sessions"` where `K` is the count of closed sessions with `ended_at` in
  the interval `[Monday-00:00-local-of-week-containing-nowISO .. nowISO]`,
  capped display at `3` (the tile shows `"3 / 3 sessions"` when `K ≥ 3`, but
  the underlying number is not clamped — see §4).
- **FR-9.** WHEN the Dashboard loads THEN the header SHALL render the copy
  `"<time-of-day-greeting>, <display-name>"` where:
  - `time-of-day-greeting` ∈ {`"Good morning"`, `"Good afternoon"`, `"Good
    evening"`} chosen deterministically from `nowISO` local hours:
    `[05:00..12:00)` → morning; `[12:00..18:00)` → afternoon; else → evening.
  - `display-name` is the `LEARNER_ID` constant title-cased
    ([quiz/page.tsx:46](../../frontend/app/(coach)/learn/quiz/page.tsx:46) —
    Phase-1 single-learner surface).
- **FR-10.** WHEN the Dashboard loads THEN the header SHALL render a
  secondary line with the current local weekday + date derived from `nowISO`
  via `Intl.DateTimeFormat` (e.g., `"Friday, July 10"`). No hardcoded locale;
  default browser locale honored.

### Ubiquitous invariants

- **FR-11.** THE SYSTEM SHALL derive `greeting`, `streak`, and
  `weeklySessions` in pure translators (T1) with an injected clock (`nowISO`)
  and injected input (`QuizSession[]` + display id). No translator SHALL
  reference `Date.now()`, `new Date()`, `Math.random()`, `localStorage`,
  `fetch`, `document`, `window`, or any React import.
- **FR-12.** THE SYSTEM SHALL keep `SessionRepo` a single interface per
  module (P1 preserved). The new capability SHALL be a new **method** on the
  existing `SessionRepo` interface, NOT a new port.
- **FR-13.** THE SYSTEM SHALL implement `SessionRepo.listByLearner` on both
  the live Drizzle adapter and the in-memory behavioral fake; the conformance
  suite `engine_repos.test.ts` SHALL parametrize the same behavioral
  assertions across both.
- **FR-14.** THE SYSTEM SHALL NOT render a "score goal" tile nor a "coach
  note" tile in C1. When product decides to add them later, they land in
  their own sprint (Epic F).
- **FR-15.** THE Dashboard SHALL fire the rail read concurrently with the
  three existing reads (`skillTaxonomy.list`, `learnerRead.listSkillState`,
  `attemptRepo.misses`) in a single `Promise.all` — no serial waterfall.

## 4. Data model / contracts

### 4.1 New port method — `SessionRepo.listByLearner`

Signature added to [frontend/lib/ports/engine/session_repo.ts:39-58](../../frontend/lib/ports/engine/session_repo.ts:39):

```typescript
export interface SessionRepo {
  open(...): Promise<QuizSession>;
  close(...): Promise<QuizSession>;
  get(...): Promise<QuizSession | null>;

  /**
   * Closed sessions for a learner, newest-first (by `ended_at DESC`), for
   * derived signals like streak and weekly-session counts (FR-C1 rail).
   *
   * Behavioral contract:
   *   1. RETURNS CLOSED SESSIONS ONLY (`ended_at != null`). In-flight sessions
   *      are excluded — the caller reasons over completed work, not intent.
   *   2. `sinceISO` (optional) — inclusive lower bound on `ended_at`. Omitted
   *      → no lower bound (all closed sessions). Callers pass the earliest
   *      timestamp they need so the read stays bounded (e.g. 8 days back for
   *      "this week + a 1-day streak-continuity check").
   *   3. Ordering is deterministic (`ended_at DESC`, then `id ASC` as a
   *      tiebreaker for same-instant ends).
   *   4. Empty result → `[]`, never `null`, never throw.
   *   5. Returned rows are `wire/engine_entities.QuizSession` shapes (Rule A4
   *      / F-R8: no vendor type escapes the adapter).
   *
   * @throws EngineRepoError on persistence failure.
   */
  listByLearner(
    subject: string,
    learnerId: string,
    options?: { sinceISO?: string },
  ): Promise<QuizSession[]>;
}
```

**Dashboard's `sinceISO` policy (decided at clarify time):** the Dashboard
computes `sinceISO = 30 days back from nowISO` when calling `listByLearner`.
Rationale: covers the weekly-count window (this ISO week) + streak
continuity (≤2-day gaps read cleanly) with a bounded read that stays cheap
as multi-learner history accumulates. This 30-day value is the *caller's*
choice; the port itself remains window-agnostic. `decisions.md` entry
required. Revisit if a future consumer (Epic F Progress screen) needs a
longer window — extend the caller, not the port.

### 4.2 New row on the narrow `EngineDb` port

`frontend/lib/adapters/engine/db/engine_db.ts` grows:

```typescript
/** Closed sessions for a learner, newest-first by ended_at; optional lower
 *  bound. Excludes rows where ended_at IS NULL. */
listClosedSessionsByLearner(
  subject: string,
  learnerId: string,
  options?: { sinceISO?: string },
): Promise<QuizSession[]>;
```

Both implementations gain a matching method:
- `InMemoryEngineDb` — filter + sort in-memory (deterministic for L1 tests).
- `drizzleEngineDb(...)` — Drizzle query `WHERE learner_id = ? AND subject = ?
  AND ended_at IS NOT NULL AND (sinceISO IS NULL OR ended_at >= sinceISO)
  ORDER BY ended_at DESC, id ASC`.

### 4.3 New pure translators

Three new files under `frontend/lib/translators/`, each mirroring the
existing `today_focus_vm.ts` shape (T1, imports only `wire/` + stdlib):

**`greeting_vm.ts`**
```typescript
export interface GreetingVM {
  readonly headline: string;   // "Good afternoon, Maya"
  readonly subline: string;    // "Friday, July 10"
}
export function toGreetingVM(nowISO: string, learnerId: string): GreetingVM;
```

**`streak_vm.ts`**
```typescript
export interface StreakVM {
  readonly present: boolean;   // false → render "Start a streak" copy
  readonly days: number;       // 0 when present=false
}
export function toStreakVM(
  closedSessions: readonly QuizSession[],
  nowISO: string,
): StreakVM;
```
Bucketing rule: for each session, take `ended_at`'s local YYYY-MM-DD.
Consecutive days from the `nowISO` local-date going backwards; stop at the
first gap. **A single closed session TODAY counts as `days = 1`** (day-1
celebrated, not gated — decided at clarify time; matches the trust-
relationship epic tone). `present = days > 0`.

**`weekly_sessions_vm.ts`**
```typescript
export interface WeeklySessionsVM {
  readonly count: number;      // real count (never clamped)
  readonly target: number;     // 3 (see §"decisions" H6)
  readonly label: string;      // "K / 3 sessions" (K = min(count, target) for display)
}
export function toWeeklySessionsVM(
  closedSessions: readonly QuizSession[],
  nowISO: string,
  target?: number,             // defaults to 3
): WeeklySessionsVM;
```
Week rule: closed sessions whose `ended_at` falls in
`[Monday-of-week-containing-nowISO 00:00 local .. nowISO]`. Monday is index-0
by ISO 8601 week (universal, not locale-dependent).

### 4.4 `DashboardVM` growth

[use_dashboard.ts:32-39](../../frontend/components/dashboard/use_dashboard.ts:32)
grows two fields (additive; no rename):

```typescript
export interface DashboardVM {
  readonly buckets: readonly BucketCardVM[];
  readonly todayFocus: TodayFocusVM;
  readonly reviewMissesCount: number;
  readonly greeting: GreetingVM;          // NEW
  readonly rail: RailVM;                  // NEW
}
export interface RailVM {
  readonly status: "ok" | "unavailable";  // "unavailable" on FR-1 error path
  readonly streak: StreakVM;
  readonly weekly: WeeklySessionsVM;
}
```

`loadDashboard` grows the 4th concurrent read (`ports.sessionRepo.listByLearner`)
in the same `Promise.all` (FR-15). The rail failure isolates: `listByLearner`
rejection is caught inside `loadDashboard` (not surfaced to the outer
`Promise.all`), and the rail is set to `{status: "unavailable", streak:
{present:false, days:0}, weekly: {count:0, target:3, label: "—"}}`.

### 4.5 View changes

[DashboardView.tsx](../../frontend/components/dashboard/DashboardView.tsx)
grows a `<header>` and an `<aside aria-label="Trust rail">`. Layout responds
to viewport per FR-5.

### 4.6 Contracts NOT changed

- `wire/engine_entities.ts` — no schema change; `QuizSession` already carries
  `learner_id`, `ended_at`, and `subject`.
- `SessionRepo.open/close/get` — unchanged.
- Trust kernel — unchanged (Invariant #2).
- BFF Route Handlers — unchanged.
- CSP / auth — unchanged.

## 4.7 Clarify-record (Stage-2 clarify pass, 2026-07-10)

Four questions the first draft left open. Answers now load-bearing on §3
FRs and §9 DoD.

| # | Question | Decision | Why (short) |
|---|----------|----------|-------------|
| Q1 | Responsive-layout implementation for FR-5 | **Tailwind v4 `@container` queries** | Same JSX, zero JS, hydration-safe, single ARIA tree, container-aware if a future sidebar narrows the Dashboard. `useSurface` reserved for behavioral branches. |
| Q2 | Dashboard-side `sinceISO` window when calling `listByLearner` | **30 days back from `nowISO`** | Bounded read that survives multi-learner history; covers weekly + streak continuity even across ≤2-day gaps. |
| Q3 | Rail failure mode when `listByLearner` rejects (FR-1) | **Subdued inline "Trust rail unavailable" + retry `<button>` in the same aria-live region** | Honest, not alarming; preserves landmark identity; header + mastery grid unaffected. |
| Q4 | Streak floor — does 1 session today = 1-day streak? | **Yes, `days = 1` after a single closed session today** | Matches trust-relationship epic tone (day-1 celebrated, not gated). |

Design tasks surfaced (each mapped to a §3 FR):

- **DT-1 (Q1 → FR-5).** Set `container-type: inline-size` (or Tailwind
  `@container` utility) on the Dashboard root; use `@lg:` variants on the
  rail region to flip from row → aside. Validate via Playwright
  container-resize (resize the element, not the viewport).
- **DT-2 (Q2 → §4.1 caller policy).** `loadDashboard` passes
  `sinceISO = <nowISO - 30 days>` when calling `sessionRepo.listByLearner`.
  Documented in `decisions.md`; port stays window-agnostic.
- **DT-3 (Q3 → FR-1).** Rail failure state renders inline "Trust rail
  unavailable" with a retry `<button>` in the SAME `aria-live="polite"`
  region as the tiles (landmark stability). No toast, no banner.
- **DT-4 (Q4 → FR-7 + `streak_vm.ts`).** Streak translator counts today's
  session as `days = 1`; unit-test asserts `{days: 1, present: true}` for a
  single-session-today input.

## 5. Invariants & security boundaries

- **Invariant #7** (services must not import from components) — preserved.
  The new method sits under `frontend/lib/ports/engine/` (a port); the
  translator files sit under `frontend/lib/translators/`. Neither imports
  React or a component.
- **Invariant #1** (dependency direction: adapters → ports → wire) —
  preserved. `DrizzleSessionRepo` implements the port; the translator layer
  reads only wire shapes.
- **F-R1** (no domain logic in components) — the `DashboardView` receives
  `RailVM` as a pre-composed VM; it never derives a streak inline.
- **F-R3 / P1** (one interface per port module) — preserved. Adding a method
  to an existing interface is not a new interface.
- **F-R7 / trace_id** — not touched. This is engine-read UI territory; no
  agent stream.
- **T1** (pure translator) — enforced by explicit constructor-style function
  signatures with all state passed in.
- **C-4 honesty** (from Epic B) — enforced by the deferral rules (no
  score-goal / coach-note tile) and by FR-2 (real zero, never placeholder).
- **F-R9 / BFF holds no cloud creds** — not touched. This work is
  Drizzle-side, server-only.

## 6. Edge cases

- **Cold start (never opened a session).** `listByLearner` returns `[]`. FR-2
  path. Both tiles render honest empty state.
- **Session opened but never closed (in-flight).** Row has `ended_at = null`.
  `listByLearner` excludes it (contract #1). FR-4 confirms translator is
  unaffected.
- **Session ended exactly at midnight local.** Bucketing uses `ended_at`
  local-date; a session ending at 00:00:00 belongs to the new day, not the
  previous. FR-6 test asserts this.
- **Nine consecutive days with sessions, then a gap.** Streak = 9 (not the
  full history); the translator stops at the first gap.
- **All sessions in `[Sunday..Saturday]` weeks vs `[Monday..Sunday]`.** We
  pick **Monday-start** (ISO 8601), documented in `decisions.md`. FR-8.
- **Weekly count > 3.** `count = 5`, `target = 3`; label shows `"3 / 3
  sessions"` (display cap), but `count` on the VM remains `5` so downstream
  future consumers (Epic F) can read it truthfully.
- **`sinceISO` older than any row.** Same as `sinceISO` omitted — all closed
  sessions returned.
- **DB adapter throws mid-load.** `loadDashboard` catches → rail
  `status: "unavailable"`; header + `Skill mastery` still render (FR-1). No
  page crash, no toast (rail speaks for itself with a subdued "Trust rail
  unavailable" label; visible on iPad + desktop; screen-reader announced).
- **Multi-year gap.** Streak stops at the first empty day; result is bounded
  by the read window (`sinceISO`). Callers use a conservative `sinceISO` (see
  §4.1 note) so the returned list stays small.

## 7. Non-functional requirements

- **Latency.** The rail read is one bounded query (`WHERE learner_id AND
  subject AND ended_at IS NOT NULL AND ended_at >= sinceISO`) with a small
  result (weeks, not years). Adds one round-trip; fits in the existing
  `Promise.all` so wall-clock ≈ max, not sum.
- **Determinism.** L1 (`greeting_vm`, `streak_vm`, `weekly_sessions_vm`
  translator tests) MUST be fully deterministic — injected `nowISO`, injected
  learner id, injected `QuizSession[]`. No `Date.now()`.
- **Reversibility.** The port change is additive; a follow-up sprint can
  remove `listByLearner` without breaking any existing caller if the rail is
  first removed from `DashboardVM`.
- **Cost.** No LLM call, no agent stream. Zero token cost.
- **CI hot path.** No live-LLM anywhere in this sprint. Fully offline.
- **Accessibility.** Rail is `<aside role="complementary" aria-label="Trust
  rail">`. Every tile has an accessible label ("Streak: 3 days", "Weekly
  sessions: 2 of 3"). Screen reader announces state changes on the "Trust
  rail unavailable" fallback via `aria-live="polite"`. Meets WCAG 2.2 AA.

## 8. Test plan

Failure paths **first** (TAP-4 gap-blindness); each row includes the file the
test will live in.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `frontend/components/dashboard/use_dashboard.test.ts::rail_unavailable_on_listByLearner_reject` — inject a rejecting `sessionRepo`; assert VM shape + `rail.status === "unavailable"` + `buckets` still present | L1 | yes |
| FR-2 | `frontend/lib/translators/streak_vm.test.ts::empty_input_present_false` + `weekly_sessions_vm.test.ts::empty_input_zero_of_three` | L1 | yes |
| FR-3 | `frontend/lib/translators/streak_vm.test.ts::stale_sessions_return_present_false` | L1 | yes |
| FR-4 | `frontend/lib/translators/streak_vm.test.ts::inflight_session_excluded` (feed a row with `ended_at: null`; verify it's not counted; verify no throw) — belt-and-suspenders since the port contract already filters | L1 | yes |
| FR-5 | `frontend/components/dashboard/DashboardView.test.tsx::rail_classes_include_container_query_variants` — RTL asserts the JSX carries `@lg:` / `@container` class strings (no matchMedia mock needed). Full layout switch validated in Playwright by resizing the CONTAINER element, not the viewport (`page.locator('[data-dashboard-root]').boundingBox()` + JS-set width). | L1 + e2e | yes |
| FR-6 | `frontend/lib/translators/streak_vm.test.ts::midnight_boundary_deterministic` | L1 | yes |
| FR-7 | `frontend/lib/translators/streak_vm.test.ts::three_day_consecutive_returns_three` | L1 | yes |
| FR-8 | `frontend/lib/translators/weekly_sessions_vm.test.ts::monday_start_week_math` (assert Monday 00:00 local is the boundary; not Sunday) | L1 | yes |
| FR-9 | `frontend/lib/translators/greeting_vm.test.ts::time_of_day_boundaries` (05:00/12:00/18:00 case rows) | L1 | yes |
| FR-10 | `frontend/lib/translators/greeting_vm.test.ts::subline_uses_intl_datetime` | L1 | yes |
| FR-11 | `tests/architecture/test_frontend_layering.ts::translators_stay_pure` — extend the existing walker to assert the three new translator files import only `wire/` + stdlib | L1 (architecture) | yes |
| FR-12 | `tests/architecture/test_port_conformance.test.ts::session_repo_single_interface` — assert `frontend/lib/ports/engine/session_repo.ts` still exports exactly one `interface` | L1 (architecture) | yes |
| FR-13 | `frontend/lib/adapters/engine/repos/engine_repos.test.ts::sessionRepo_listByLearner` — parametrized row (excludes in-flight; newest-first; `sinceISO` filter; empty → `[]`; rejecting-db → `EngineRepoError`) | L2 (conformance) | yes |
| FR-14 | `frontend/components/dashboard/DashboardView.test.tsx::no_goal_or_note_tile_rendered` — negative-assertion test to make the deferral load-bearing | L1 | yes |
| FR-15 | `frontend/components/dashboard/use_dashboard.test.ts::rail_read_fires_concurrently` — spy on `sessionRepo.listByLearner` and the three existing reads; assert all four resolve inside a single `Promise.all` (not serial) | L1 | yes |
| e2e — cold | `frontend/e2e/learn/dashboard_rail.spec.ts::cold_start_renders_honest_empty_state` | e2e (Playwright) | yes (Chromium smoke) |
| e2e — returning | `frontend/e2e/learn/dashboard_rail.spec.ts::returning_learner_shows_streak_and_weekly` | e2e (Playwright) | yes (Chromium smoke) |
| e2e — midnight | `frontend/e2e/learn/dashboard_rail.spec.ts::injected_clock_midnight_determinism` — Playwright with `page.clock.install()` or a `?now=` test-only query param the dev seed honors | e2e (Playwright) | yes (Chromium smoke) |

**TDD order per §8.1 (TAP-4 first).** Author FR-1 → FR-2 → FR-3 → FR-4 → FR-6
(all failure/edge translator + hook tests) BEFORE FR-7 → FR-8 → FR-9 → FR-10
(happy-path tests). Watch each one fail before implementing. The port + view
tests (FR-11 → FR-15) follow the translator layer.

## 9. Definition of Done

- [ ] All FRs implemented; each has a passing test that was **seen to fail
      first** (commit sequence shows the red step for each failure-path FR).
- [ ] `make check` green (lint + format-check + pyright + test + hygiene).
- [ ] Frontend `pnpm test` green (Vitest); `pnpm tsc --noEmit` green.
- [ ] `pnpm playwright test frontend/e2e/learn/dashboard_rail.spec.ts` green
      on Chromium (cold + returning + injected-clock rows).
- [ ] Invariants in §5 unbroken; new architecture tests (FR-11, FR-12) pass.
- [ ] **ADR appended and Accepted:**
      `docs/adr/00XX-session-repo-list-by-learner.md`. Rejected alternatives
      documented (client-side session cache; `LearnerStatsRepo` as new port;
      leave rail out until Epic F).
- [ ] `decisions.md` entry for **H6** (weekly rule = 3-per-week, ISO
      Monday-start; visual 7-dot-strip deferred with the score-goal tile).
- [ ] `decisions.md` entry for **score-goal + coach-note deferral** with a
      pointer to Epic F.
- [ ] `decisions.md` entry for **`sinceISO` = 30 days back** (§4.1 Dashboard
      caller policy; Q2 clarify decision).
- [ ] `decisions.md` entry for **responsive-layout = Tailwind v4
      `@container`** (Q1 clarify decision; `useSurface` NOT used for
      layout).
- [ ] `decisions.md` entry for **streak day-1 floor = 1** (Q4 clarify
      decision).
- [ ] `preact-ui-prototype-parity-VISUAL-gap-report.md` row for **D-1**
      marked 🟩 and **D-5** marked 🟨 (streak + weekly shipped; goal + note
      still open, pointing to Epic F).
- [ ] Actual command output pasted (not summarized) for `make check`,
      `pnpm tsc --noEmit`, `pnpm test`, and the Playwright run.

## 10. Cross-artifact readiness (for Stage 4 analyze)

- **Grounded file paths.** All paths in this spec were probed against the
  current tree at author time (2026-07-10) — [session_repo.ts:39-58](../../frontend/lib/ports/engine/session_repo.ts:39),
  [use_dashboard.ts:32-39](../../frontend/components/dashboard/use_dashboard.ts:32),
  [DashboardView.tsx](../../frontend/components/dashboard/DashboardView.tsx),
  [drizzle_session_repo.ts](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts),
  [engine_db.ts:99-102](../../frontend/lib/adapters/engine/db/engine_db.ts:99),
  [engine_repos.test.ts](../../frontend/lib/adapters/engine/repos/engine_repos.test.ts),
  [nav_model.ts:65](../../frontend/components/shell/nav_model.ts:65),
  [today_focus_vm.ts](../../frontend/lib/translators/today_focus_vm.ts),
  [quiz/page.tsx:46](../../frontend/app/(coach)/learn/quiz/page.tsx:46).
- **No new dependency in `package.json`.** All work uses TypeScript, Zod,
  Drizzle, Vitest, RTL, Playwright — already installed.
- **Constitution touchpoints declared.** Invariants #1, #2, #7, and F-R1,
  F-R3, F-R9 are addressed in §5. No trust-kernel change (⚠️ Ask-first not
  triggered on `trust/models.py`).
- **ADR trigger.** G1 (new derivation path — streak/weekly are new derived
  channels). ⚠️ Ask-first #6 (new horizontal service? — no; extending an
  existing port). The ADR documents G1 fully, cites §5, and links this spec.
