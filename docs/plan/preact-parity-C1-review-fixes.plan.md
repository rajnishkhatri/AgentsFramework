# Plan — C1 review fixes (dashboard rail + greeting hardening)

**Status:** Draft — 2026-07-10
**Owner:** Rajnish Khatri
**Realizes:** [preact-parity-C1-review-fixes.spec.md](preact-parity-C1-review-fixes.spec.md)
**Amends:** [preact-parity-C1-dashboard-rail.plan.md](preact-parity-C1-dashboard-rail.plan.md) — post-merge hardening.
**Related:** [ADR-0026](../adr/0026-session-repo-list-by-learner.md) (unchanged; no port shape change).

---

## 1. Architecture

Fourteen FRs, one branch. Every change is **inside** the C1 layer boundaries
— no new port, no new adapter *family*, no wire shape change. The three
edited seams:

```
  ┌────────────────────────────────────────────────────────────┐
  │  frontend/app/(coach)/learn/page.tsx                       │
  │    two useEffects instead of one — greeting/buckets group  │
  │    stable across rail retry; rail effect drives the        │
  │    unavailable → ok transition alone. (FR-8)               │
  └───────────────┬────────────────────────────────────────────┘
                  │
  ┌───────────────▼────────────────────────────────────────────┐
  │  frontend/components/dashboard/                            │
  │    use_dashboard.ts                                        │
  │      RailResult discriminated union (FR-6),                │
  │      speculative focus prefetch in Promise.all (FR-4/5),   │
  │      NO window.__PREACT_E2E_* (FR-2).                      │
  │    DashboardView.tsx                                       │
  │      aria-live moved to <aside>; single content shell      │
  │      swaps only text nodes; retry rail-scoped (FR-7/8).    │
  └───────────────┬────────────────────────────────────────────┘
                  │
  ┌───────────────▼────────────────────────────────────────────┐
  │  frontend/lib/translators/                                 │
  │    greeting_vm.ts   — (nowISO, displayName?) → GreetingVM  │
  │                        no learner_id guess (FR-11)         │
  │    weekly_sessions_vm.ts — noon-of-day Monday build (FR-10)│
  │    streak_vm.ts     — unchanged (FR-9 = new test row only) │
  └───────────────┬────────────────────────────────────────────┘
                  │
  ┌───────────────▼────────────────────────────────────────────┐
  │  frontend/lib/composition_engine_browser.ts                │
  │    NEXT_PUBLIC_PREACT_E2E_HOOKS gate wraps                 │
  │    sessionRepo.listByLearner with a failOnceDecorator.     │
  │    Zero domain-code branch anywhere else.  (FR-2/FR-3)     │
  └────────────────────────────────────────────────────────────┘
```

The port + adapter + wire shapes are untouched. The change surface is
exactly:

- **1 hook** (`use_dashboard.ts`) — union + concurrency fan-out shape,
  backdoor removed.
- **1 view** (`DashboardView.tsx`) — live-region hoist + content shell.
- **1 page** (`page.tsx`) — effect split.
- **1 composition root** (`composition_engine_browser.ts`) — env-gated
  decorator (FR-2 seam).
- **3 translators** (`greeting_vm.ts` sig + `weekly_sessions_vm.ts` math;
  `streak_vm.ts` unchanged).
- **1 arch test** (new grep-based rule in
  `tests/architecture/test_frontend_layering.test.ts`).
- **1 e2e file** (`dashboard_rail.spec.ts`) — three rows rewritten,
  every row gets axe.
- **1 devDep** (`@axe-core/playwright`) + one `decisions.md` line.
- **1 hygiene fix** (`docs/adr/decisions.md` trailing newline).

No ADR: G1 does not fire (§5 of the spec).

## 2. File-level touchpoints

Numbered so tasks can reference exactly. `[edit]` = modify, `[add]` = new
file, `[del]` = deletion, `[test-add]` = new test row(s) inside an
existing file.

### 2.1 Ports (unchanged)

None. ADR-0026's `listByLearner(subject, learnerId, options?)` shape
stands.

### 2.2 Adapters (unchanged)

None. `DrizzleSessionRepo` and `InMemoryEngineDb` untouched.

### 2.3 Composition roots

- **2.3.1 [edit] `frontend/lib/composition_engine_browser.ts`** — read
  `process.env.NEXT_PUBLIC_PREACT_E2E_HOOKS === "1"` (composition-root
  read = Rule C4/C5 legal), and when on, wrap the returned
  `sessionRepo.listByLearner` in a `failOnceDecorator` co-located inline
  (private helper). Wrapper state (`hasFailedOnce = false`) is a module
  singleton scoped to the browser bag. Semantics: first call rejects
  with `EngineRepoError("e2e forced rail failure")`, subsequent calls
  delegate. Reset semantics: page reload constructs a new bag; refresh
  clears the flag naturally.

### 2.4 Translators

- **2.4.1 [edit] `frontend/lib/translators/greeting_vm.ts`** — signature
  becomes `toGreetingVM(nowISO: string, displayName?: string)`; when
  `displayName` is absent, `headline = "Good <time>"` (no comma).
  Delete `titleCaseId` (FR-11).
- **2.4.2 [edit] `frontend/lib/translators/weekly_sessions_vm.ts`** — in
  `mondayStartLocal`, construct at noon-of-day (mirror
  `streak_vm.ts:31-32`). Behavior on non-DST inputs unchanged
  (FR-10).
- **2.4.3 [test-add] `frontend/lib/translators/streak_vm.test.ts`** —
  add the `one_gap_resets_streak_beyond_gap` row (FR-9). No translator
  edit.
- **2.4.4 [test-add] `frontend/lib/translators/greeting_vm.test.ts`** —
  add: `no_display_name_omits_name_from_headline`,
  `non_latin_display_name_passthrough`,
  `time_of_day_boundaries_0459_0500_1159_1200_1759_1800` (FR-11/12).
- **2.4.5 [test-add] `frontend/lib/translators/weekly_sessions_vm.test.ts`**
  — add: `dst_spring_forward_monday_stable`,
  `dst_fall_back_monday_stable`, `target_clamp_when_count_gt_target`,
  `sunday_2359_vs_monday_0000` (FR-10/12).

### 2.5 Hook + View + Page

- **2.5.1 [edit] `frontend/components/dashboard/use_dashboard.ts`** —
  five changes, one commit each preferred:
  - **a.** Remove the `window.__PREACT_E2E_RAIL_FAIL_ONCE__` branch and
    the `RAIL_UNAVAILABLE` sentinel (FR-2, FR-6).
  - **b.** Introduce local `type RailResult = {ok:true; sessions:
    readonly QuizSession[]} | {ok:false};` (FR-6).
  - **c.** Widen `Promise.all` from four reads to five: prefetch
    `nextReviewed` for the tentative focus skill computed from a
    speculative `pickFocusSkillId` over a *cached zero-mastery seed*.
    The real pick reconciles after; if it differs, issue a targeted
    read (FR-4). See §2.5.1a below.
  - **d.** Update the caller to pass `displayName` (or omit) —
    `useDashboard` remains React-context glue; the loader accepts a
    new optional `LoadDashboardArgs.displayName`.
  - **e.** Narrow rail rendering via the discriminant, no cast.

  **§2.5.1a — Speculative fan-out sketch.**
  `pickFocusSkillId` takes `skillStates` + `nowISO`. We don't have
  states yet at fan-out time, so speculation is: prefetch the FIRST
  skill's `nextReviewed` question (skills are ordered; the tentative
  pick is likely order-1). Reconcile: if the real pick equals the
  speculative pick → use it (one saved RTT). If not → drop and issue
  a targeted read. Cost of miss: one wasted DB call.

- **2.5.2 [edit] `frontend/components/dashboard/DashboardView.tsx`** —
  three changes:
  - **a.** Move `aria-live="polite"` from the inner `<div>` (line 43)
    to the `<aside>` (FR-7).
  - **b.** Replace the ternary with a stable content shell: one child
    element that always exists; its inner text/children change based
    on `vm.rail.status`. Landmark identity preserved.
  - **c.** Add `data-testid="dashboard-greeting"` to the `<h1>` so FR-8
    Playwright + jsdom rows can hold a stable node handle across
    retry.

- **2.5.3 [edit] `frontend/app/(coach)/learn/page.tsx`** — split the
  single `useEffect` into two:
  - **Effect A** (deps: `[load]`): fires ONCE per mount; loads
    skills/states/misses/focus + greeting. Sets a `baseVm` state.
  - **Effect B** (deps: `[load, reloadToken]`): fires on mount AND on
    Retry; loads rail only (a new `loadRail(ports, args)` helper OR
    the same `load()` with a `railOnly: true` flag). Sets a `rail`
    state.
  - `DashboardView` composes `vm = { ...baseVm, rail }`. FR-8 satisfied.

  **Note:** the simplest path is a `loadRail` helper alongside
  `loadDashboard` — it re-uses the same `sessionRepo.listByLearner`
  wrapper (the `RailResult` union) and returns `RailVM`. Keeps
  `loadDashboard` pure; splits responsibility cleanly.

### 2.6 Architecture tests

- **2.6.1 [test-add] `frontend/tests/architecture/test_frontend_layering.test.ts`**
  — add a grep-based rule: no file under `frontend/components/**` or
  `frontend/lib/**` may contain the substring `__PREACT_E2E_`, except
  for the explicit allowlist `[frontend/lib/composition_engine_browser.ts]`
  (FR-3). Existing arch test file; add one describe block.

### 2.7 E2E

- **2.7.1 [edit] `frontend/e2e/learn/dashboard_rail.spec.ts`** —
  rewrites, all five rows:
  - **`container_resize_moves_rail_from_row_to_aside`** — assert
    `container-type: inline-size` present on `dashboard-root`;
    at narrow (`maxWidth = 380px`) assert `rail.rect.top >
    buckets.rect.top` (row layout, rail sits below); at wide
    (`maxWidth = 1280px`) assert `rail.rect.left > buckets.rect.left`
    (aside layout, rail sits right). Delete the tautology disjunction.
    (FR-1)
  - **`retry_button_re_fires_read_after_transient_error`** — drive
    fail-once via env `NEXT_PUBLIC_PREACT_E2E_HOOKS=1` (Playwright
    project env), not `page.addInitScript`. (FR-2)
  - **`retry_button_is_rail_scoped`** — new row: capture the greeting
    `<h1>` node via `dashboard-greeting` testid, click Retry, assert
    the same node is still attached (`await expect(node).toBeVisible()`
    + a DOM-identity check via `evaluate((el) => el.isConnected)`).
    (FR-8)
  - All five rows gain a leading
    `const results = await new AxeBuilder({page}).withTags(["wcag2a",
    "wcag2aa"]).analyze(); expect(results.violations).toHaveLength(0);`
    (FR-13)
- **2.7.2 [edit] `frontend/playwright.config.ts`** — pass the env
  `NEXT_PUBLIC_PREACT_E2E_HOOKS=1` to the dev-server run (so the C1
  e2e rows can drive the composition-root failOnce decorator).

### 2.8 Package + hygiene

- **2.8.1 [edit] `frontend/package.json`** — add
  `"@axe-core/playwright": "^4.x"` to `devDependencies`. Run
  `pnpm install`; commit lockfile.
- **2.8.2 [edit] `docs/adr/decisions.md`** — append the five
  decisions ledger lines from spec §13 AND add the trailing newline
  (FR-14).
- **2.8.3 [test-add] Existing hook + view tests** — jsdom rows for
  FR-7 (`aria_live_region_landmark_stable_across_ok_unavailable`) and
  FR-8 (`retry_does_not_rerender_greeting_or_buckets`) land in
  `use_dashboard.test.ts` and `DashboardView.test.tsx` respectively.

## 3. Migration sequence (11 steps, watched-red)

Each step commits a `[red]` step first when a `[red]` row exists, then
the `[green]` fix in the next commit. Some steps are pure refactor
(no `[red]` needed).

1. **CI unblock.** Fix `docs/adr/decisions.md` trailing newline
   (FR-14). Push → CI green baseline restored on the branch.
2. **DevDep.** Add `@axe-core/playwright` to `frontend/package.json`;
   `pnpm install`; commit lockfile.
3. **Translator tests first (all `[red]`).** Add FR-9 streak row,
   FR-10 weekly rows (spring/fall), FR-11 greeting rows, FR-12
   remaining rows — watch them fail (streak FR-9 will fail — no gap
   test exists; weekly FR-10 will fail — no DST test; greeting FR-11
   will fail — current `toGreetingVM` still returns "Maya" for
   `learner_id="maya"`).
4. **Translator green.** Land `greeting_vm.ts` signature change +
   `weekly_sessions_vm.ts` DST-safe Monday. Update *only* the
   translator; hook wiring stays broken (page.tsx passes learner_id
   → will need §2.5.3 edit next).
5. **Hook — RailResult union + backdoor removal.** Add the
   `RailResult` type in `use_dashboard.ts`. Delete the
   `window.__PREACT_E2E_*` block and the `RAIL_UNAVAILABLE` sentinel.
   Narrow via the discriminant. Rewire the `page.tsx` caller to pass
   `displayName = "Maya"` (constant sibling to `LEARNER_ID`).
6. **Hook — speculative concurrency.** Widen the
   `Promise.all` to five reads (FR-4). Update the concurrency test
   to five entries (FR-5).
7. **Composition-root fail-once decorator.** Add the
   `NEXT_PUBLIC_PREACT_E2E_HOOKS` gate in
   `composition_engine_browser.ts`. Add
   `playwright.config.ts` env plumbing.
8. **View — ARIA hoist + stable shell.** Move `aria-live` to
   `<aside>`; introduce single content shell; add
   `data-testid="dashboard-greeting"`. Add jsdom FR-7 + FR-8 rows.
9. **Page — effect split.** Split the single `useEffect` into
   `Effect A` (base VM) + `Effect B` (rail). Add `loadRail` helper
   (or `railOnly` flag). Compose in the render.
10. **E2E rewrite + axe.** Rewrite container-resize; add
    `retry_button_is_rail_scoped`; migrate fail-once to env; every
    row gets AxeBuilder. Run locally with a live server.
11. **Arch test grep.** Add the `__PREACT_E2E_` forbidden-substring
    rule to `test_frontend_layering.test.ts` (FR-3). Land LAST — it's
    the load-bearing enforcement.

## 4. Constitution touchpoints

Spec §5 already maps invariants. This table is the *plan-level*
crosswalk showing which step in §3 discharges each rule:

| Rule                                                 | Discharged in step | Notes |
|------------------------------------------------------|--------------------|-------|
| **#1** deps flow downward                            | Preserved throughout | No cross-layer imports added. |
| **F-R1** no domain logic in components               | Step 8             | View gains no logic; only content shell + testid. |
| **F-R4** Route Handlers = composition adapters       | Step 7             | Fail-once seam moves to composition root. |
| **F-R9 / M2** BFF holds no cloud creds               | Preserved          | `NEXT_PUBLIC_*` is public by design. |
| **Rule C1/C4** single profile switch, env-in-root    | Step 7             | The one new env read is inside the composition root. |
| **Rule W3** discriminated unions                     | Step 5             | `RailResult` union replaces sentinel. |
| **Rule U4** stable ARIA live region                  | Step 8             | Single shell; identity preserved. |
| **Rule T1** translator purity                        | Steps 3/4          | `greeting_vm` + `weekly_sessions_vm` stay pure. |
| **§14** no parallel client store                     | Preserved          | Rail effect writes React state only. |
| **G1** new-abstraction gate                          | N/A                | No new port/family — no ADR. |
| **C-4 honesty (Epic B)**                             | Steps 4, 8         | Bare greeting; honest-absent live region. |
| **§20 axe on every route**                           | Steps 2, 10        | Test dep + per-row AxeBuilder. |
| **§22 no-console outside adapters (O2)**             | Preserved          | Retry-miss branch logs nothing. |

## 5. Non-goals

Anything C1 already shipped or C2 defers:

- No new port method beyond ADR-0026's `listByLearner`.
- No new shape in `wire/engine_entities.ts`.
- No score-goal or coach-note tile.
- No real `display_name` field on `SkillState` / `QuizSession`.
- No SSR for the Dashboard.
- No sprint C2 work.
- No changes to the FSRS scheduler, session lifecycle, or attempt
  path.
- No new architecture invariants; no new pattern family (F, W, P, A,
  T, X, C, B, U, S, O). This spec is entirely within existing rules.

## 6. Baseline gates before implementation

- [ ] `pre-commit run --all-files` — green (verify FR-14 fix landed
      first).
- [ ] `pnpm exec vitest run` — the pre-fix baseline (expected: green
      on the merged C1 branch as of PR #143).
- [ ] `pnpm exec vitest run tests/architecture/test_frontend_layering.test.ts`
      — pre-fix baseline.
- [ ] `pnpm exec playwright test e2e/learn/dashboard_rail.spec.ts`
      — pre-fix baseline (currently GREEN despite defective
      assertions — this is the point of FR-1).
- [ ] `pytest tests/architecture/ -q` — green baseline.

## 7. Ready-to-branch checklist

- [ ] Human ratifies the four Q recommendations (done — user "yes").
- [ ] Branch: `feat/preact-parity-c1-review-fixes` cut from the
      merged C1 branch (or from `main` after C1 merges — either is
      valid; branch name is the same).
- [ ] Advance to `sdd-implement`.
