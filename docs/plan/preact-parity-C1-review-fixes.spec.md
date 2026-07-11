# Spec — C1 review fixes (dashboard rail + greeting hardening)

**Status:** Draft — 2026-07-10
**Owner:** Rajnish Khatri
**Related:**
[C1 base spec](preact-parity-C1-dashboard-rail.spec.md),
[C1 plan](preact-parity-C1-dashboard-rail.plan.md),
[C1 tasks](preact-parity-C1-dashboard-rail.tasks.md),
[ADR-0026](../adr/0026-session-repo-list-by-learner.md),
[PR #143](https://github.com/rajnishkhatri/AgentsFramework/pull/143).
Consumes review of PR #143 (2026-07-10 turn).

---

## 1. Goal

Close the four blockers + significant gaps identified in the C1 code review so
PR #143 is honestly mergeable: **weak e2e assertions become falsifiable, the
production-path test backdoor is removed, retry becomes rail-scoped, the
unavailable sentinel becomes a typed discriminated union**, plus DST/greeting/
axe/CSP nits. The base C1 surfaces (streak, weekly, greeting, retry) stay
functionally intact — this spec hardens what shipped, it does not add features.

## 2. Context

PR #143 landed the C1 sprint (SessionRepo.listByLearner + rail + greeting)
against [C1 spec](preact-parity-C1-dashboard-rail.spec.md). Code review found
four blockers and seven significant gaps that survived the base spec's Stage-4
analyze pass — most because the base spec's test-plan rows described the
*shape* of a test, not the *falsifiability* of the assertion inside it. That
is a TAP-4 gap-blindness recurrence, and the review-fixes spec exists to close
the loop the base spec did not.

Every fix is grounded in a real defect in the merged code, not a stylistic
preference. The four blockers each block merge; the significant gaps each
block one honesty rule (Frontend-Ring F-R1/F-R4/C-4/U4/W3/O2) or ship a latent
bug (DST). This spec's FRs are the *fixes* — the failure modes they close are
the FR premises.

Forces:

1. **Falsifiability (TAP-4).** Every e2e assertion must fail if the seam
   under test is broken. The container-resize row in `dashboard_rail.spec.ts`
   passes even when `@container` is stripped — that's not a test, it's a
   placebo.
2. **F-R4 / Rule B6.** Production code (`use_dashboard.ts`) reads a
   test-only global (`window.__PREACT_E2E_RAIL_FAIL_ONCE__`). That is a
   composition-adapter violation: the domain path is not the test seam.
3. **W3 / discriminated unions.** The `RAIL_UNAVAILABLE` sentinel-string
   with a downstream `as QuizSession[]` cast lies to the type system. A
   discriminated union catches at compile-time what the current sentinel
   catches at runtime — sometimes.
4. **C-4 honesty (Epic B).** A wrong first name in the greeting is worse
   than a generic salutation; `titleCaseId("mc") = "Mc"` is a foreseeable
   wrong.

## 3. Functional requirements (EARS)

Failure paths first (TAP-4). One testable claim per FR.

### 3.1 Blockers

- **FR-1 (B1 — falsifiable container-resize).** IF the Dashboard root's
  `container-type: inline-size` computed style is absent OR the `@lg:`
  container variants do not resolve at the widened container width, THEN
  the container-resize e2e row (`dashboard_rail.spec.ts`) SHALL FAIL.
  Concretely: the narrow branch asserts the rail's `getBoundingClientRect()`
  places it *below* the mastery grid (row layout); the wide branch asserts
  it places it *right of* the mastery grid (aside layout). A tautology
  disjunction (`x === "none" || …`) is forbidden.

- **FR-2 (B2 — no domain backdoor).** THE SYSTEM SHALL contain zero reads
  of `window.__PREACT_E2E_*` inside `frontend/components/**` or
  `frontend/lib/**` (excluding `frontend/lib/adapters/**` and
  `frontend/lib/composition_engine_browser.ts`). The rail-failure e2e
  injection point SHALL live in a composition-root wire-up that decorates
  `SessionRepo.listByLearner` with a fail-once behavior — no test-hook code
  path may run inside `loadDashboard`.

- **FR-3 (B2 — arch test enforces FR-2).** WHEN
  `tests/architecture/test_frontend_layering.test.ts` runs, it SHALL fail
  the build if any file under `frontend/components/**` or `frontend/lib/**`
  (except the composition roots) references the substring
  `__PREACT_E2E_`.

- **FR-4 (B3 — FR-15 covers the focus-question resolution).** WHEN
  `loadDashboard` runs, the `questionRepo.nextReviewed` read for the
  today's-focus banner SHALL fire concurrently with the four existing reads
  (skills, states, misses, rail) — not serially after the `Promise.all`
  barrier. A speculative-then-reconcile pattern is acceptable: prefetch the
  focus-question for the tentatively-picked skill, and drop it if the
  reconciled pick differs.

- **FR-5 (B3 — concurrency proof widened).** WHEN the concurrency test in
  `use_dashboard.test.ts` runs, it SHALL prove FIVE reads started before
  any resolved (adding `nextReviewed`), not four. The current
  `expect(started.sort()).toEqual(["misses","rail","skills","states"])`
  becomes a five-entry set.

- **FR-6 (B4 — sentinel → discriminated union).** THE SYSTEM SHALL model
  the rail-read result as a discriminated union
  `{ok: true, sessions: QuizSession[]} | {ok: false}` (or a `Result<T,E>`),
  and the downstream branch that renders the rail SHALL narrow via the
  discriminant — no `as QuizSession[]` cast permitted. Rule W3 applies to
  the port-boundary return shape used by the hook.

### 3.2 Significant gaps

- **FR-7 (G1 — ARIA live region stability).** THE SYSTEM SHALL keep the
  `aria-live="polite"` region's DOM landmark identity stable across
  ok/unavailable state transitions — the same wrapping element persists,
  only its inner text nodes change. The current implementation replaces
  the child subtree (tiles vs. text+button) inside the region; a screen
  reader announces a landmark change on retry. Move `aria-live` to the
  `<aside>` and hold a single content shell that swaps only inner content.

- **FR-8 (G2 — rail-scoped retry).** WHEN the user clicks the rail Retry
  button, the SYSTEM SHALL re-fire only the `sessionRepo.listByLearner`
  read (and re-render the rail region) — it SHALL NOT clear or re-render
  the greeting, buckets, focus banner, or misses control. Concretely: the
  `useEffect` at `page.tsx` SHALL be split so `reloadToken` re-runs only
  the rail sub-load; the four other reads are cached across a retry.

- **FR-9 (G3 — streak gap coverage).** THE SYSTEM SHALL have a passing
  L1 test that seeds `[Jul 10, Jul 9, Jul 7]` with `nowISO=Jul 10` and
  asserts `days=2` — i.e., "one gap resets streak beyond the gap." This
  behavior is asserted in prose in `streak_vm.ts` but has no test row.

- **FR-10 (G4 — DST-safe Monday).** THE SYSTEM SHALL compute
  `mondayStartLocal` in `weekly_sessions_vm.ts` using the same noon-of-day
  construction the streak translator uses, so DST spring-forward/fall-back
  Sundays do not silently shift the week window. A test SHALL freeze
  `nowISO` on a US spring-forward Sunday
  (`2026-03-08T12:00:00-08:00` → `2026-03-08T19:00:00Z`) and assert the
  Monday is `2026-03-02T00:00:00-08:00`, unchanged by the DST edge.

- **FR-11 (G5 — greeting honesty).** THE SYSTEM SHALL NOT render a
  guessed first-name derivation from `learner_id`. Until a real
  `display_name` field lands, `toGreetingVM` SHALL render either
  `"Good <time>"` (no name) OR a caller-supplied `displayName` when
  present — never a `titleCaseId(learner_id)` guess. Migrating today's
  `LEARNER_ID = "maya"` constant to a `displayName = "Maya"` sibling is
  acceptable; the greeting stays honest.

- **FR-12 (G6 — greeting/weekly test coverage).** THE SYSTEM SHALL have
  passing L1 rows for: greeting time-of-day boundaries at 04:59/05:00,
  11:59/12:00, 17:59/18:00 local; weekly `target=3` clamp when `count=5`
  (label shows `3 / 3` but `vm.count === 5`); weekly count at Sunday 23:59
  vs Monday 00:00 local. If any row is currently absent the task list
  adds it under a `[red]` block. (Verification during Stage 4 grounding
  will confirm which exist — `greeting_vm.test.ts` and
  `weekly_sessions_vm.test.ts` files are present but coverage untested.)

- **FR-13 (G7 — axe on every dashboard-rail e2e row).** WHEN each row in
  `e2e/learn/dashboard_rail.spec.ts` runs, it SHALL call
  `new AxeBuilder({page}).analyze()` at least once, and the assertion
  SHALL fail on any `violations.length > 0`. The tag list is `["wcag2a",
  "wcag2aa"]`. This covers the new `Trust rail` landmark and the live
  region.

### 3.3 Hygiene (bundled with the above)

- **FR-14 (CI hygiene).** THE SYSTEM SHALL leave `docs/adr/decisions.md`
  with a trailing newline so the pre-commit `end-of-file-fixer` hook
  passes. The fix in the merged branch is a one-line append.

## 4. Data model / contracts

### 4.1 New / changed shapes

- **`RailResult` (new; typed union).** In `use_dashboard.ts`:

  ```ts
  export type RailResult =
    | { readonly ok: true; readonly sessions: readonly QuizSession[] }
    | { readonly ok: false };
  ```

  Replaces the `RAIL_UNAVAILABLE = "rail-unavailable"` sentinel + `as`
  cast. The `RailVM` output shape is unchanged (the union is an
  intermediate step inside the hook).

- **`GreetingVM` (unchanged shape; changed constructor signature).**

  ```ts
  export function toGreetingVM(nowISO: string, displayName?: string): GreetingVM;
  ```

  The parameter renames from `learnerId` to `displayName` and becomes
  optional. When absent, headline is `"Good <time>"` (no comma, no name).
  Callers that today pass `learner_id` SHALL be updated to pass a display
  name or omit.

### 4.2 New callers

- `page.tsx` splits its single `useEffect` into two — one drives the
  greeting/buckets/focus/misses group, one drives the rail. The
  `reloadToken` bumps only the rail effect (FR-8).

- The rail-fail-once test seam moves to
  `frontend/lib/composition_engine_browser.ts` behind a
  `NEXT_PUBLIC_PREACT_E2E_HOOKS === "1"` gate (dev/CI only). When on, the
  bag's `sessionRepo.listByLearner` is wrapped by a `failOnceDecorator`
  that rejects the first call and delegates thereafter. Zero
  application-code changes to `use_dashboard.ts` (FR-2).

### 4.3 Wire / port contracts

- **`SessionRepo.listByLearner` — unchanged.** ADR-0026 stands. The fix
  is entirely upstream of the port.
- **`EngineDb.listClosedSessionsByLearner` — unchanged.**

## 5. Invariants & security boundaries

Constitution touchpoints (root `AGENTS.md` §"Architecture Invariants" + frontend
Ring rules F-R#):

- **Invariant #1 (deps flow downward).** Preserved — the discriminated
  union lives in the hook; the port shape is unchanged.
- **F-R1 / F-R4 (no domain logic in read path outside adapters).** FR-2
  restores this; the current PR violates it. The decorator lives in the
  composition root (Rule C1/C2), which is the only site permitted to name
  concrete adapters and behavior wrappers.
- **F-R7 (trace_id).** Not touched.
- **F-R9 / Rule B6 (Route Handlers are composition adapters).** FR-2/FR-3
  keep production code free of test-only env branches.
- **Rule W3 (discriminated unions, not bare unions/sentinels).** FR-6
  enforces this at the read-result boundary.
- **Rule U4 (single persistent ARIA live region).** FR-7 restores the
  APG landmark-stability requirement the memory file cites.
- **Rule T1 (translator purity).** Preserved. FR-10 is an internal-math
  fix; DST-safe construction is a pure input→output change.
- **§14 (no parallel client store).** Preserved.
- **G1 (new-abstraction gate).** The `RailResult` discriminated union is
  *not* a new port and *not* a new abstraction beyond `wire/` idioms —
  no ADR required. The decorator in the composition root is a test-only
  wrapper, not a new port. G1 does not fire.

Trust-kernel touchpoints: none.

## 6. Edge cases

- **Retry mid-load.** User clicks Retry while the rail read is still
  in-flight; the second read must supersede the first (last-write-wins).
  Concretely: `reloadToken` bump aborts the pending rail promise via an
  `AbortController` scoped to the rail effect (FR-8).
- **Speculative focus-question wrong.** The prefetched focus question
  turns out to be for a different skill than the reconciled pick (FR-4);
  drop the prefetch and issue a targeted read. Log nothing (PII-free
  observability, Rule O2).
- **Container query never fires.** The dashboard is mounted inside a
  `display:contents` parent (memory-noted gotcha); FR-1's presence check
  catches this by asserting the computed `container-type` is
  `"inline-size"` on the Dashboard root at test time.
- **Non-Latin display name.** `toGreetingVM` with `displayName = "日 太郎"`
  passes through verbatim (no case coercion); FR-11 test row covers it.
- **DST fall-back.** `2026-11-01` Sunday in `America/Los_Angeles` has
  25 hours; the Monday-of-week for the following day must still be
  `2026-10-26`. FR-10 test row covers spring-forward; a companion
  row covers fall-back.
- **Rail Retry when rail is already ok.** No-op (idempotent): the
  Retry button is not rendered in the `ok` branch (FR-8's shell holds
  content only, not the button, in the `ok` case).

## 7. Non-functional requirements

- **Latency.** FR-4 removes one serial RTT from the critical path
  (roughly one `nextReviewedQuestion` DB round-trip); FR-8 avoids the
  full-page blank on retry.
- **Determinism.** All translator changes stay L1-pure (injected clock,
  no `Date.now`). DST fix is a construction change, not a behavior
  change on non-DST inputs.
- **Cost.** Zero LLM calls added. No CI hot-path additions beyond axe
  runs in Playwright (bounded at 5 rows).
- **Reversibility.** Every FR is a code-level change in files the C1 PR
  already touches. No schema, no migration, no ADR amendment.
- **Live-LLM budget.** None involved.

## 8. Test plan

Failure-path rows first. L1 = deterministic; L2 = reproducible (Playwright).

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-14 | `pre-commit run --all-files` — end-of-file-fixer on `docs/adr/decisions.md` | hygiene | yes |
| FR-3 | `tests/architecture/test_frontend_layering.test.ts::forbids_e2e_backdoor_outside_composition_root` | L1 arch | yes |
| FR-2 | `frontend/components/dashboard/use_dashboard.test.ts::does_not_reference_e2e_globals` (grep-based structural test) | L1 | yes |
| FR-6 | `frontend/components/dashboard/use_dashboard.test.ts::rail_result_is_discriminated_union_not_sentinel` — pattern: no `as QuizSession[]` in the module (ts-morph walker) | L1 | yes |
| FR-4 + FR-5 | `frontend/components/dashboard/use_dashboard.test.ts::rail_read_fires_concurrently` — widened to five reads | L1 | yes |
| FR-9 | `frontend/lib/translators/streak_vm.test.ts::one_gap_resets_streak_beyond_gap` | L1 | yes |
| FR-10 | `frontend/lib/translators/weekly_sessions_vm.test.ts::dst_spring_forward_monday_stable`, `..._fall_back_monday_stable` | L1 | yes |
| FR-11 | `frontend/lib/translators/greeting_vm.test.ts::no_display_name_omits_name_from_headline`, `..._non_latin_display_name_passthrough` | L1 | yes |
| FR-12 | `frontend/lib/translators/greeting_vm.test.ts::time_of_day_boundaries_0459_0500_1159_1200_1759_1800`; `weekly_sessions_vm.test.ts::target_clamp_when_count_gt_target`, `..._sunday_2359_vs_monday_0000` | L1 | yes |
| FR-7 | `frontend/components/dashboard/DashboardView.test.tsx::aria_live_region_landmark_stable_across_ok_unavailable` | L1 (jsdom) | yes |
| FR-8 | `frontend/components/dashboard/DashboardView.test.tsx::retry_does_not_rerender_greeting_or_buckets` — asserts the greeting/misses/buckets DOM nodes are `===` before and after retry (via re-render harness) | L1 | yes |
| FR-1 | `frontend/e2e/learn/dashboard_rail.spec.ts::container_resize_moves_rail_from_row_to_aside` — REWRITTEN to assert `container-type: inline-size` present AND `rail.rect.top > buckets.rect.top` at narrow, `rail.rect.left > buckets.rect.left` at wide | L2 Playwright | no (e2e job) |
| FR-8 | `frontend/e2e/learn/dashboard_rail.spec.ts::retry_button_is_rail_scoped` — asserts the greeting `<h1>` `data-testid="dashboard-greeting"` element identity survives the retry click (snapshot handle before/after) | L2 Playwright | no |
| FR-13 | Every row in `dashboard_rail.spec.ts` runs `AxeBuilder(...).analyze()`; fails on any violation. | L2 Playwright | no |
| FR-2 (integration) | `dashboard_rail.spec.ts::retry_button_re_fires_read_after_transient_error` — REWRITTEN to drive fail-once via `NEXT_PUBLIC_PREACT_E2E_HOOKS=1` env, NOT a `window.__PREACT_E2E_RAIL_FAIL_ONCE__` write | L2 Playwright | no |

### Watched-red evidence

Each `[red]` row above SHALL be commit-visible: the failing test lands
first, then the green fix. Commit message references the FR number.

## 9. Definition of Done

- [ ] All FRs implemented; each has a passing test that was seen to fail
      first (commit-visible red step).
- [ ] `pnpm exec vitest run` green (frontend unit + architecture).
- [ ] `pnpm exec playwright test e2e/learn/dashboard_rail.spec.ts` green
      locally; CI job green.
- [ ] `pre-commit run --all-files` green (FR-14 in particular).
- [ ] `pytest tests/architecture/ -q` green.
- [ ] `make check` green.
- [ ] Invariants in §5 unbroken; the layering arch test (FR-3) is the
      mechanical enforcement.
- [ ] No new ADR required (verified §5); no new `decisions.md` entry
      required beyond a one-liner recording the RailResult
      discriminated-union choice and the DST-safe Monday construction.
- [ ] PR #143 comment thread references each blocker+gap ID (B1–B4,
      G1–G7) and links to the FR that closes it.
- [ ] Actual command output pasted (not summarized) for the four
      Playwright rows and the widened concurrency test.

---

## 10. Out of scope

Explicitly deferred to a later PR / not addressed here:

- Any new UI surface beyond the rail + greeting shipped in C1.
- Score-goal tile, coach-note tile (C1 spec FR-14 stands).
- Real `display_name` provisioning (FR-11 accepts a constant sibling
  today).
- Sprint C2 (Summary payoff + FLAG-5).
- Server-side rail rendering / SSR mode for the Dashboard.
- Multi-learner Dashboard (Phase-1 constant `LEARNER_ID = "maya"` stays).

## 11. Ready-to-plan check

- [ ] Every FR traces to a review finding (B1–B4, G1–G7) OR to CI (FR-14).
- [ ] No FR overlaps a base C1 spec FR (this is additive hardening).
- [ ] No FR introduces an ⚠️ Ask-first trigger (§5 confirmed).
- [ ] Stage-2 clarify pass complete — ambiguity list in §12.

## 12. Clarify pass

Four ambiguities surfaced during authoring; recommended answer stated;
awaiting human ratification before Stage 3.

- **Q1 (FR-4 — how far does concurrency go?).** Do we fan-out
  `nextReviewed` speculatively (prefetch the tentative focus skill's
  question) or resolve `pickFocusSkillId` inside the fan-out and issue
  the question read afterward?
  **Recommended:** Speculative prefetch. Pick pass is cheap (in-memory
  sort over ≤6 skill_state rows); the DB round-trip is what we want to
  hide. If the reconciled pick differs, drop the prefetch — cost is one
  wasted read.

- **Q2 (FR-6 — where does the discriminated union live?).** Inside
  `use_dashboard.ts` only (local intermediate), or exported from a wire
  module (`wire/engine_entities.ts`) as `RailReadResult`?
  **Recommended:** Local. The union is a hook-internal shape, not a wire
  contract. Exporting it would freeze a shape the port never emits.

- **Q3 (FR-11 — greeting sans name = "Good morning" or "Good morning,
  learner"?).** No-name greeting: bare `"Good morning"` (no trailing
  comma/text) or a generic vocative `"Good morning, learner"`?
  **Recommended:** Bare `"Good morning"`. C-4 honesty: a generic vocative
  is a placeholder; absence is honest.

- **Q4 (FR-13 — where does axe-core come from?).** Add
  `@axe-core/playwright` to `frontend/package.json` (new dep, G1 gate) or
  use an existing helper?
  **Recommended:** Add the dep. It's a testing-only devDependency, is
  already prescribed by frontend style guide §20, and every fix in this
  spec is bounded by tests — no runtime footprint. Add under
  `devDependencies`. This is NOT an ADR trigger under root AGENTS.md
  ⚠️ Ask-first (devDep for a prescribed testing tool); a
  `decisions.md` line is sufficient.

## 13. Decisions ledger (bundle in the impl PR)

To be appended to `docs/adr/decisions.md` in the same PR that lands the
fixes:

- 2026-07-10 — **C1-fix rail read result = discriminated union (Q2).**
  Local `RailResult = {ok:true, sessions} | {ok:false}` inside
  `use_dashboard.ts`; no export. Kills the `RAIL_UNAVAILABLE` sentinel +
  `as QuizSession[]` cast. Rule W3 enforced at hook boundary.
- 2026-07-10 — **C1-fix greeting sans name = bare "Good morning" (Q3).**
  `toGreetingVM(nowISO, displayName?)`; missing name → no trailing
  vocative. C-4 honesty preferred over a placeholder.
- 2026-07-10 — **C1-fix DST-safe weekly Monday (FR-10).** Reuse the
  noon-of-day construction from `streak_vm.ts`. Pure translator internal
  change; no behavior delta on non-DST inputs.
- 2026-07-10 — **C1-fix concurrency includes speculative focus read
  (Q1).** `nextReviewed` for the tentative focus skill fans out with
  the four base reads; reconcile after `pickFocusSkillId`.
- 2026-07-10 — **C1-fix e2e rail-fail seam moves to composition root
  (FR-2).** `NEXT_PUBLIC_PREACT_E2E_HOOKS=1` gates a
  `failOnceDecorator` around `sessionRepo.listByLearner` in
  `composition_engine_browser.ts`. Zero test-hook code inside
  `use_dashboard.ts` (Rule F-R4 restored).
- 2026-07-10 — **C1-fix devDep add: @axe-core/playwright (Q4).**
  Testing-only; prescribed by frontend style guide §20. Not an ADR
  trigger.
