---
title: 'D4 — Skills nav via comingSoon · Plan'
type: plan
sprint: D4
epic: D
status: Draft — 2026-07-11 (ALTERNATE — activates only if human overrides default to defer)
owner: Rajnish Khatri
derives_from: docs/plan/preact-parity-D4-skills-nav.spec.md
governs:
  - docs/plan/preact-parity-D4-skills-nav.tasks.md
related:
  - docs/plan/preact-parity-sprint-board-D.md
  - docs/plan/preact-parity-epic-A.brainstorm.md   # Q-6 trust bug class
---

# D4 — Skills nav via `comingSoon` · Plan

Derived from `preact-parity-D4-skills-nav.spec.md` (6 FRs). D4 is the alternate
path — the board's default is defer to Epic E. If the human sticks with the
default, this plan is filed alongside the spec but never executes; a single
`decisions.md` line captures the deferral.

## 1. Architecture posture

- **Layer:** shell config edit (one line in `NAV_MEMBERSHIP`) + one arch guard.
- **What already exists:** `screen("skill", route: "/learn/skill", comingSoon: true)`
  at [`nav_model.ts:75`](../../frontend/components/shell/nav_model.ts:75); AppNav's
  `disabled` branch at [`AppNav.tsx:52-60`](../../frontend/components/shell/AppNav.tsx:52)
  already renders `<span data-coming-soon="true" aria-disabled="true">` for
  coming-soon items. This is the reused pattern.
- **What is NOT introduced:** no `/learn/skill` route (Epic E's floor), no new
  nav abstraction, no new ADR, no new CSS.

## 2. Shape call

- **`NAV_MEMBERSHIP` change (surgical).** At
  [`nav_model.ts:103-107`](../../frontend/components/shell/nav_model.ts:103):
  ```ts
  const NAV_MEMBERSHIP: Readonly<Record<Surface, readonly ScreenId[]>> = {
    desktop: ["dashboard", "quiz", "coach", "skill", "progress"],  // +skill
    ipad:    ["dashboard", "quiz", "coach", "skill", "progress"],  // +skill
    iphone:  ["dashboard", "quiz", "progress"],                    // unchanged
  };
  ```
- **Placement rationale (between `coach` and `progress`):** the design-spec
  positions Skills as the "drill into one bucket" surface — semantically it
  sits between the conversational coach and the aggregate progress view.
  Same order the design-spec's sidebar mockups use ([`design-spec.md:155`](../../PreAct/UI-Design/design-spec.md:155)
  et al).
- **iPhone left alone.** The 3-tab supersede (§8.1 in the design-spec)
  intentionally keeps Skills contextual on iPhone, not global.
- **No `AppNav.tsx` change.** The `disabled` branch already exists; adding
  `"skill"` to `NAV_MEMBERSHIP` reaches it automatically via
  `toNavItem()` at [`nav_model.ts:110-115`](../../frontend/components/shell/nav_model.ts:110)
  (a coming-soon screen produces `disabled: true, href: ""`).
- **No route created.** FR-5 asserts the absence.

## 3. File-level touchpoints

| File | Change |
|------|--------|
| [`frontend/components/shell/nav_model.ts:103-107`](../../frontend/components/shell/nav_model.ts:103) | Add `"skill"` to `desktop` and `ipad` arrays, positioned between `"coach"` and `"progress"`. |
| [`frontend/components/shell/nav_model.test.ts`](../../frontend/components/shell/nav_model.test.ts) | Add three assertions: (a) `NAV_MEMBERSHIP.desktop.includes("skill")`, (b) `NAV_MEMBERSHIP.ipad.includes("skill")`, (c) `NAV_MEMBERSHIP.iphone.includes("skill") === false`. Add hydration test asserting the hydrated NavItem has `disabled: true`, `href: ""`, `comingSoon: true`. |
| [`frontend/components/shell/AppNav.test.tsx`](../../frontend/components/shell/AppNav.test.tsx) | Add `skill_item_is_not_clickable` test. |
| [`frontend/tests/architecture/test_no_dead_skill_route.ts`](../../frontend/tests/architecture/test_no_dead_skill_route.ts) *(new)* | Assert `frontend/app/(coach)/learn/skill/` directory does NOT exist. Flips to red when Epic E creates the route (forcing D4's posture to be reconsidered). |
| [`frontend/e2e/learn/nav-skills-coming-soon.spec.ts`](../../frontend/e2e/learn/nav-skills-coming-soon.spec.ts) *(new)* | Playwright walk asserting item visible on desktop + iPad, `aria-disabled="true"`, click does not navigate. |
| [`docs/adr/decisions.md`](../adr/decisions.md) | Prepend newest-first line recording the outcome (shipped or deferred). |
| [`docs/plan/preact-parity-sprint-board-D.md`](preact-parity-sprint-board-D.md) | Flip D4 status (Implemented or Declined). |
| [`docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md`](preact-ui-prototype-parity-VISUAL-gap-report.md) | §D-8 updated: either "entry visible, route deferred to Epic E" (shipped) or "deferred to Epic E per D4 alternate declined" (default). |

## 4. Execution order (TDD)

1. **Red bar.** Author the four new tests (`nav_model.test.ts` extension +
   `AppNav.test.tsx` extension + `test_no_dead_skill_route.ts` + the
   Playwright spec). Watch:
   - `test_no_dead_skill_route.ts` — GREEN pre-D4 (route does not exist —
     regression guard, not seen-red).
   - `nav_model.test.ts` new cases — RED pre-D4 (membership does not include
     `"skill"`).
   - `AppNav.test.tsx` new case — cannot be run yet (item does not appear in
     rendered nav on desktop/ipad). Author, mark `.todo()`; convert to full
     test post-membership.
   - Playwright — RED pre-D4 (item not present).
2. **Membership edit.** Add `"skill"` to `desktop` + `ipad` in
   `NAV_MEMBERSHIP`. Re-run L1 — `nav_model.test.ts` new cases green;
   `AppNav.test.tsx` new case now runnable → green.
3. **E2E.** Run `nav-skills-coming-soon.spec.ts` (chromium) — green.
4. **Continuity.** Re-run existing `AppNav.test.tsx` + any surface-based
   nav tests to confirm no regression to `progress` / `coach` handling.
5. **Docs.** Append `decisions.md` line; flip sprint-board; update parity
   report §D-8.
6. **Full gate.** `make check` + `pytest tests/architecture/ -q` +
   `pnpm exec vitest run components/shell/` + Playwright smoke. Paste actual
   output.

## 5. Gates + risks

- **⚠️ Ask first (SPEC-LEVEL, not code-level).** This spec exists only
  because the human overrode the default. Once overridden, the mechanical
  execution is small.
- **G1 (new-abstraction gate)** — DOES NOT FIRE. Reuses existing `NavItem` +
  `disabled` render + `comingSoon` state.
- **Q-6-class regression** — this is the real risk. Two guards:
  (a) FR-5 arch test asserts no `/learn/skill/` directory;
  (b) FR-1 test asserts the item is non-clickable AND `router.push` is not
      called on click. If `AppNav`'s `disabled` branch is ever refactored
      away, both tests fail loudly.
- **Risk: mobile-vs-desktop consistency confusion.** Users may wonder why
  Skills isn't on iPhone. The `title="Coming soon"` on desktop/iPad and the
  3-tab supersede's absence on iPhone are both intentional. Documented in
  the `decisions.md` line for future readers.

## 6. Independence

D4 has no dependency on D2 or D3 and can merge to `main` alone (given the
human override). Epic E, when it lands, updates
`nav_model.ts:75`'s `comingSoon: true → false` and drops the arch guard at
`test_no_dead_skill_route.ts`. That is Epic E's move, not D4's.
