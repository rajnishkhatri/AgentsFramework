---
title: 'D4 — Skills nav via comingSoon (PreAct parity Epic D — ALTERNATE)'
type: spec
sprint: D4
epic: D
status: Draft — 2026-07-11 (ALTERNATE — default posture defers to Epic E; this spec only fires if human flips posture)
owner: Rajnish Khatri
derives_from: docs/plan/preact-parity-sprint-board-D.md
governs:
  - docs/plan/preact-parity-D4-skills-nav.plan.md   # only written if human picks D4
  - docs/plan/preact-parity-D4-skills-nav.tasks.md  # only written if human picks D4
related:
  - docs/plan/preact-parity-sprint-board-D.md   # ladder; D4 is the alternate slot
  - docs/plan/preact-parity-epic-D.brainstorm.md  # §7-Q1 human gate
  - docs/plan/preact-parity-epic-A.brainstorm.md   # Q-6 trust-bug class D4 must not regress
---

# D4 — Skills nav via `comingSoon`

**Report finding:** `D-8` — Sidebar missing a `Skills` nav entry.

## 1. Goal

Ship the `Skills` nav entry as a **visible, non-clickable, `comingSoon`** item —
so the taxonomy is *legible* in the shell — without a live route that 404s.
Reuses the pattern
[`nav_model.ts:75`](../../frontend/components/shell/nav_model.ts:75) and
[`AppNav.tsx:52`](../../frontend/components/shell/AppNav.tsx:52) already use for
`progress` and `skill` in the catalog.

**This is the ALTERNATE path** and only exists if the human overrides the board's
**default posture (defer to Epic E)** at Stage-1 §7-Q1. Rationale for the default
below (§2). Board explicitly warns adding to `NAV_MEMBERSHIP` without a live
route is the same class as Q-6 — the trust bug Epic A just closed.

## 2. Context

Stage-1 P14 refuted the epics-doc premise "safe one-liner: add `skill` to
`NAV_MEMBERSHIP`":
- `screen("skill")` already exists in
  [`nav_model.ts:75`](../../frontend/components/shell/nav_model.ts:75) with
  `comingSoon: true`.
- Route `/learn/skill` does **not** exist under
  `frontend/app/(coach)/learn/` (audit 2026-07-11 shows only `page.tsx`,
  `quiz`, `summary`, `test` — no `skill/`).
- Adding to `NAV_MEMBERSHIP` at
  [`nav_model.ts:103-107`](../../frontend/components/shell/nav_model.ts:103)
  without either the route existing OR a robust `comingSoon` render is a
  Q-6-class trust bug.

**Default posture (board §D4 line 361):** defer D-8 to Epic E's board (which
naturally lands the target route + the nav entry together). This spec only
lives to be picked-or-declined.

## Clarify resolutions (2026-07-11)

- **Alternate-path only.** This spec does **not** land unless the human explicitly
  picks D4 at the Stage-1 §7-Q1 gate. Default action after the human declines is
  a single line in `decisions.md`: "D-8 deferred to Epic E per D4 alternate
  gate."
- **`AppNav` already handles `disabled` / `comingSoon`.** Audit at
  [`AppNav.tsx:52`](../../frontend/components/shell/AppNav.tsx:52) confirms the
  `disabled` branch renders `aria-disabled="true"` and non-clickable — no new
  render logic required. Same treatment `progress` gets today.
- **Optional stub route** (`app/(coach)/learn/skill/page.tsx`, 10 lines "Coming
  soon" + link back to Dashboard) is **out-of-scope for D4**. The reveal is
  the sidebar entry; the route is Epic E's floor. `comingSoon: true` on a
  nav item is already non-clickable — no 404 is reachable from the nav.

## 3. Functional requirements (EARS)

- **FR-1 (unwanted).** IF `NAV_MEMBERSHIP` at
  [`nav_model.ts:103-107`](../../frontend/components/shell/nav_model.ts:103)
  includes `"skill"` on any surface AND `AppNav`'s `disabled`/`comingSoon`
  branch does NOT keep the item non-clickable, THEN the sprint MUST fail —
  because that resurrects Q-6 (a dead nav item that 404s on click). Test seen
  fail first with a hand-corrupted `AppNav` that drops the `disabled` guard.
- **FR-2.** THE SYSTEM SHALL add `"skill"` to `NAV_MEMBERSHIP` for
  `desktop` and `ipad` **only** — matching how the design-spec surfaces show
  Skills (§4 below). `iphone`'s 3-tab supersede stays intact
  (Home / Practice / Progress).
- **FR-3.** WHEN a Skills nav item renders on desktop or iPad, THE SYSTEM SHALL
  present it as `disabled` + `comingSoon` (both `true`), with `href = ""`
  (per [`nav_model.ts:110-115`](../../frontend/components/shell/nav_model.ts:110)'s
  `toNavItem()` — a coming-soon control has no destination).
- **FR-4.** WHEN a user clicks the Skills nav item, THE SYSTEM SHALL NOT
  navigate (no route change; no 404). This is the anti-Q-6 gate.
- **FR-5.** THE SYSTEM SHALL NOT create `frontend/app/(coach)/learn/skill/`
  (route creation is Epic E's floor).
- **FR-6.** THE SYSTEM SHALL leave the `screen("skill")` catalog entry
  ([`nav_model.ts:75`](../../frontend/components/shell/nav_model.ts:75))
  unchanged (`comingSoon: true`, `route: /learn/skill`, `isFocusScreen: false`).

## 4. Data model / contracts

No wire change; no VM change. `NAV_MEMBERSHIP` is a local
`Record<Surface, readonly ScreenId[]>` at
[`nav_model.ts:103`](../../frontend/components/shell/nav_model.ts:103). Adding
`"skill"` to `desktop` and `ipad` arrays is a 1-line edit each (or single
combined change).

## 5. Invariants & security boundaries

- **F-R2 / F-R5 / F-R7** — untouched.
- **AGENTS.md #6 (thin orchestration wrappers)** — untouched (no reducer, no
  dispatch).
- **Q-6-class trust boundary** — the whole point of this spec. Trust bug Epic A
  just closed by removing dead nav items ("Sidebar shows Practice but click
  404s"). D4 relies on `AppNav`'s existing `disabled` guard at
  [`AppNav.tsx:52`](../../frontend/components/shell/AppNav.tsx:52) to keep the
  Skills entry visibly-but-not-clickable, avoiding the same class of bug.

## 6. Edge cases

- **iPhone surface** — Skills does NOT appear (FR-2; iPhone's 3-tab supersede is
  intentional and Skills is contextual, not global).
- **`AppNav` future refactor drops the `disabled` guard** — the FR-1 seen-fail
  test catches this. It IS the safety net Q-6 depended on.
- **Keyboard navigation** — `aria-disabled="true"` (per
  [`AppNav.tsx:59`](../../frontend/components/shell/AppNav.tsx:59)) removes the
  item from tab order semantically; screen readers announce "dimmed / not
  available".

## 7. Non-functional requirements

- **Latency / cost:** none.
- **Determinism:** L1 deterministic (pure config + pure render).
- **Reversibility:** trivial (revert 1 line each in `desktop` and `ipad`
  arrays).

## 8. Test plan

Failure paths first (TAP-4).

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `components/shell/AppNav.test.tsx::skill_item_is_not_clickable` — mock a `screen("skill")` NavItem into props, click it, assert `router.push` was NOT called AND `aria-disabled="true"`. | L1 | yes |
| FR-1 | `components/shell/nav_model.test.ts::skill_hydrates_as_disabled` — hydrate `NAV_MEMBERSHIP.desktop` into NavItems via `toNavItem`, find `"skill"`, assert `disabled === true`, `href === ""`, `comingSoon === true`. | L1 | yes |
| FR-2 | `components/shell/nav_model.test.ts::skill_membership_desktop_ipad_only` — asserts `NAV_MEMBERSHIP.desktop` includes `"skill"`, `NAV_MEMBERSHIP.ipad` includes `"skill"`, `NAV_MEMBERSHIP.iphone` does NOT. | L1 | yes |
| FR-3, FR-4 | `e2e/learn/nav-skills-coming-soon.spec.ts` — Playwright walks desktop + iPad surfaces, asserts (a) Skills item visible in sidebar, (b) has `aria-disabled="true"`, (c) clicking it does NOT change `page.url()`, (d) network shows no `/learn/skill` fetch attempted. Seen red on pre-D4 tree (no Skills item exists). | L4 | yes |
| FR-5 | `frontend/tests/architecture/test_no_dead_skill_route.ts` — asserts `frontend/app/(coach)/learn/skill/` directory does NOT exist. If Epic E later creates it, this test flips to failing, forcing D4's `comingSoon` posture to be reconsidered. | L1 (arch) | yes |
| FR-6 | Snapshot test on the `screen("skill")` result — asserts the 4 fields are unchanged from today. | L1 | yes |

## 9. Definition of Done

- [ ] `NAV_MEMBERSHIP` desktop + ipad arrays include `"skill"`; iphone does not.
- [ ] Skills entry renders in sidebar on desktop + iPad with `aria-disabled="true"`,
      empty `href`, `comingSoon` state visible (dimmed styling per existing
      `progress` treatment).
- [ ] No route created at `frontend/app/(coach)/learn/skill/` — asserted by
      arch test (FR-5).
- [ ] Clicking Skills does NOT navigate (verified in E2E).
- [ ] `make check` green; `pnpm exec playwright test e2e/learn/nav-skills-coming-soon.spec.ts` green.
- [ ] `decisions.md` line: `D-8 shipped via D4 alternate (comingSoon-gated); Skills nav item lands visible-but-not-clickable on desktop+ipad. Live /learn/skill route remains Epic E's floor.`
- [ ] Parity report §D-8 updated: entry visible; route deferred to Epic E.

## 10. Gates

- **⚠️ Ask first (blocks spec entering plan)** — this spec only lands if the
  human overrides the board's default (defer to Epic E). If the human sticks
  with default, this spec is filed as an authored-but-declined alternate; the
  action is a `decisions.md` line and Epic E owns the follow-up.
- **G1 (new-abstraction gate)** — no new abstraction (reuses existing
  `NavItem`, existing `comingSoon` render).
- **G7 (architecture gate)** — no new architecture; no ADR.
- **`decisions.md` line** records the "gated ship vs defer" choice regardless
  of outcome — even a "declined" alternate leaves a durable marker of the
  question having been asked.
