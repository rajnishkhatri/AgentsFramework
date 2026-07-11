# Tasks — C1 review fixes (dashboard rail + greeting hardening)

**Status:** Draft — 2026-07-10
**Owner:** Rajnish Khatri
**Realizes:** [preact-parity-C1-review-fixes.spec.md](preact-parity-C1-review-fixes.spec.md)
**Executes:** [preact-parity-C1-review-fixes.plan.md](preact-parity-C1-review-fixes.plan.md)

Tags:
- `[red]` — watched-red step. Commit the failing test before the fix.
- `[green]` — the fix that turns the previous `[red]` green.
- `[P]` — parallelizable with peers under the same block.
- FR-# — the spec FR this task discharges.

---

## Block 0 — Baseline

- **T0.1** — Ensure branch is `feat/preact-parity-c1-review-fixes` from
  the merged C1 tip (or the current PR #143 head). Run the six baseline
  gates in plan §6. Paste output.

## Block 1 — CI unblock (FR-14)

- **T1.1 [green]** — Append a trailing newline to
  `docs/adr/decisions.md`. Run `pre-commit run --all-files`; paste
  green output.

## Block 2 — Test devDep (Q4)

- **T2.1** — Add `"@axe-core/playwright": "^4.x"` to
  `frontend/package.json` `devDependencies`. `pnpm install`. Commit
  lockfile.
- **T2.2** — Append one line to `docs/adr/decisions.md`: the Q4
  decision (see spec §13, bullet 5).

## Block 3 — Translator tests [red] (FR-9/10/11/12)

All four tasks are `[P]` — independent files.

- **T3.1 [red][P]** — `frontend/lib/translators/streak_vm.test.ts` —
  add `one_gap_resets_streak_beyond_gap` (FR-9). Watch fail.
- **T3.2 [red][P]** — `frontend/lib/translators/weekly_sessions_vm.test.ts`
  — add `dst_spring_forward_monday_stable`,
  `dst_fall_back_monday_stable`,
  `target_clamp_when_count_gt_target`,
  `sunday_2359_vs_monday_0000` (FR-10/12). Watch fail on the DST rows.
- **T3.3 [red][P]** — `frontend/lib/translators/greeting_vm.test.ts` —
  add `no_display_name_omits_name_from_headline`,
  `non_latin_display_name_passthrough`,
  `time_of_day_boundaries_0459_0500_1159_1200_1759_1800`
  (FR-11/12). Watch fail on FR-11 rows (current impl derives from
  `learner_id`).
- **T3.4** — Commit all four `[red]` files in one commit titled
  `test(dashboard): C1-fix — watched-red translator rows for FR-9/10/11/12`.

## Block 4 — Translator green (FR-10, FR-11)

- **T4.1 [green]** — Rewrite `weekly_sessions_vm.ts` `mondayStartLocal`
  to construct at noon-of-day (FR-10). All Block-3 weekly rows green.
- **T4.2 [green]** — Change `toGreetingVM` signature to
  `(nowISO: string, displayName?: string)`; drop `titleCaseId`; when
  `displayName` absent, headline = `"Good <time>"` (no comma) (FR-11).
  All Block-3 greeting rows green.
- **T4.3** — `streak_vm.ts` untouched; T3.1 will already be green
  under existing impl (verify — the FR-9 test is a coverage add, not
  a bug find).

## Block 5 — Hook `[red]` + `[green]` (FR-2, FR-6, FR-4/5)

- **T5.1 [red]** — `use_dashboard.test.ts` — add
  `does_not_reference_e2e_globals` (grep or ts-morph): asserts the
  module source contains no `__PREACT_E2E_` occurrence (FR-2). Watch
  fail.
- **T5.2 [red]** — `use_dashboard.test.ts` — add
  `rail_result_is_discriminated_union_not_sentinel` (ts-morph or
  regex): asserts no `as QuizSession[]` cast in `use_dashboard.ts`
  (FR-6). Watch fail.
- **T5.3 [red]** — Widen the existing `rail_read_fires_concurrently`
  test to expect FIVE started reads
  (`["focus_question","misses","rail","skills","states"]`) (FR-4/5).
  Watch fail.
- **T5.4** — Commit T5.1–T5.3 as one red-step commit.
- **T5.5 [green]** — Refactor `use_dashboard.ts`:
  - Define local `type RailResult = {ok:true; sessions: readonly
    QuizSession[]} | {ok:false}` (FR-6).
  - Remove the `window.__PREACT_E2E_RAIL_FAIL_ONCE__` branch and the
    `RAIL_UNAVAILABLE` string sentinel (FR-2).
  - Widen `Promise.all` to include a speculative `nextReviewed` on
    the tentative focus skill (skills[0] or a heuristic); reconcile
    after `pickFocusSkillId`; if pick differs, issue a targeted
    read (FR-4).
  - Narrow rail rendering via the discriminant; no `as` casts.
  - Extend `LoadDashboardArgs` with optional `displayName`; thread
    through to `toGreetingVM` (FR-11).
  - Update `page.tsx` call site to pass `displayName = "Maya"` (new
    sibling constant to `LEARNER_ID`).
- **T5.6** — Verify T5.1–T5.3 green; commit `[green]`.

## Block 6 — Composition-root fail-once (FR-2/FR-3)

- **T6.1 [green]** — `composition_engine_browser.ts` — add a
  `NEXT_PUBLIC_PREACT_E2E_HOOKS === "1"` gate that wraps
  `sessionRepo.listByLearner` with an inline `failOnceDecorator`
  (module-scoped `hasFailedOnce = false`). Preserve normal path
  when the flag is off.
- **T6.2** — `playwright.config.ts` — pass
  `NEXT_PUBLIC_PREACT_E2E_HOOKS=1` to the dev-server run.

## Block 7 — View + Page [red] + [green] (FR-7, FR-8)

- **T7.1 [red]** — `DashboardView.test.tsx` — add
  `aria_live_region_landmark_stable_across_ok_unavailable`: render ok
  → capture the aria-live host node; render unavailable → assert the
  aria-live host is the SAME landmark (same `aria-label`, same
  element tag); FR-7.
- **T7.2 [red]** — `DashboardView.test.tsx` — add
  `retry_does_not_rerender_greeting_or_buckets`: mount view, snapshot
  the `dashboard-greeting` node and the first bucket node's
  `.outerHTML`; simulate a rail state swap; assert those two
  snapshots unchanged (FR-8).
- **T7.3** — Commit T7.1–T7.2 as red-step.
- **T7.4 [green]** — Edit `DashboardView.tsx`:
  - Move `aria-live="polite"` from the inner `<div>` (currently
    line 43) to the `<aside>` (FR-7).
  - Replace the ternary with a single content shell; swap only
    inner children based on `vm.rail.status`. Landmark identity
    preserved.
  - Add `data-testid="dashboard-greeting"` to the `<h1>` (FR-8).
- **T7.5 [green]** — Edit `frontend/app/(coach)/learn/page.tsx`:
  - Add `LEARNER_DISPLAY_NAME = "Maya"` sibling constant.
  - Add a `loadRail(ports, args): Promise<RailVM>` helper (or a
    `railOnly` param on `loadDashboard`); expose it via `useDashboard`.
  - Split the existing `useEffect` into:
    - Effect A: `[load]` — loads greeting/buckets/focus/misses into
      `baseVm` (once per mount).
    - Effect B: `[loadRail, reloadToken]` — loads rail into `rail`
      state (mount + retry).
  - Compose `<DashboardView vm={{ ...baseVm, rail }} onRetryRail={...} />`.
- **T7.6** — Verify T7.1–T7.2 green; commit `[green]`.

## Block 8 — E2E rewrite (FR-1, FR-2 integration, FR-8, FR-13)

- **T8.1 [red]** — `e2e/learn/dashboard_rail.spec.ts` — REWRITE
  `container_resize_moves_rail_from_row_to_aside`:
  - Assert `getComputedStyle(dashboard-root)["container-type"] ===
    "inline-size"`.
  - At narrow (`maxWidth = 380px`): `expect(rail.rect.top).toBeGreaterThan(buckets.rect.top)`.
  - At wide (`maxWidth = 1280px`): `expect(rail.rect.left).toBeGreaterThan(buckets.rect.left)`.
  - Delete tautology disjunction (FR-1). Watch fail on the merged
    C1 branch (or a diagnostic mutation — strip `@container` — to
    prove falsifiability if it happens to pass unfixed).
- **T8.2** — REWRITE `retry_button_re_fires_read_after_transient_error`:
  drive fail-once via `NEXT_PUBLIC_PREACT_E2E_HOOKS=1` env (already
  in Playwright config from T6.2); remove the `page.addInitScript`
  that sets `window.__PREACT_E2E_RAIL_FAIL_ONCE__`. Assert unavailable
  → Retry → ok (FR-2).
- **T8.3 [red]** — Add row `retry_button_is_rail_scoped`: capture
  `dashboard-greeting` handle, click Retry, assert
  `await handle.evaluate(el => el.isConnected)` is `true` AND
  `handle` still resolves to the same element (FR-8). Watch fail on
  the pre-fix build.
- **T8.4** — In every one of the five rows, add:
  ```ts
  const axe = await new AxeBuilder({page})
    .withTags(["wcag2a","wcag2aa"])
    .analyze();
  expect(axe.violations).toEqual([]);
  ```
  (FR-13)
- **T8.5** — Run Playwright locally with dev-server env
  `NEXT_PUBLIC_PREACT_E2E_HOOKS=1`; paste actual output.

## Block 9 — Architecture test grep (FR-3)

- **T9.1 [red]** — `frontend/tests/architecture/test_frontend_layering.test.ts`
  — add a describe block:
  ```
  forbids_e2e_backdoor_outside_composition_root:
    for every file under frontend/components/** and frontend/lib/**
    except [frontend/lib/composition_engine_browser.ts],
    assert source does NOT contain `__PREACT_E2E_`.
  ```
  Watch fail against pre-fix `use_dashboard.ts` if Block 5 hasn't
  landed yet.
- **T9.2 [green]** — Land LAST (after Block 5 removes the reference).
  Verify green.

## Block 10 — Decisions ledger + PR

- **T10.1** — Append the five decisions ledger lines from spec §13
  (Q1–Q4 + FR-10) to `docs/adr/decisions.md`. Include the Q4 dep
  line from T2.2.
- **T10.2** — Open PR `feat/preact-parity-c1-review-fixes → main`.
  Body cites each of B1–B4 + G1–G7 with the FR that closes it.

---

## FR → task crosswalk

Every FR maps to at least one task with the fix, and a `[red]`
watched-red anchor where behavior changed.

| FR    | Discharged by                                     |
|-------|---------------------------------------------------|
| FR-1  | T8.1                                              |
| FR-2  | T5.1 [red], T5.5 [green], T6.1, T8.2, T9.1/T9.2   |
| FR-3  | T9.1 [red], T9.2 [green]                          |
| FR-4  | T5.3 [red] (concurrency widened), T5.5 [green]    |
| FR-5  | T5.3, T5.5                                        |
| FR-6  | T5.2 [red], T5.5 [green]                          |
| FR-7  | T7.1 [red], T7.4 [green]                          |
| FR-8  | T7.2 [red], T7.5 [green], T8.3 [red]              |
| FR-9  | T3.1 [red] (coverage-only; T4.3 confirms already-green under existing impl) |
| FR-10 | T3.2 [red], T4.1 [green]                          |
| FR-11 | T3.3 [red], T4.2 [green], T5.5 (caller update)    |
| FR-12 | T3.2, T3.3 (bundled rows)                         |
| FR-13 | T2.1 (devDep), T8.4                               |
| FR-14 | T1.1                                              |

---

## Parallelization envelope

- **Block 3** T3.1/T3.2/T3.3 fully `[P]` — independent test files.
- **Block 5** T5.1/T5.2/T5.3 `[P]` — three independent test additions
  in one file (merge into one PR commit as T5.4).
- **Block 7** T7.1/T7.2 `[P]` — independent test rows.
- **Block 8** T8.1/T8.3/T8.4 all inside one file; commit sequentially.
- **Block 9** MUST land last — T9.2's green depends on T5.5.

Steps 1–2 (CI + devDep) are trivially serial.

## Definition of Done (mechanical)

- [ ] Every FR in spec §3 has at least one green task in the
      crosswalk above.
- [ ] Every `[red]` task has a companion `[green]` OR is a
      coverage-only add (FR-9 case, called out in the crosswalk).
- [ ] Every `[green]` task shows commit-visible red first.
- [ ] All Block 0 baseline gates run green post-implementation.
- [ ] PR body links each of B1–B4 + G1–G7 to its FR.
- [ ] Actual command output pasted for the widened concurrency test
      and the four Playwright rows (per spec §9).
