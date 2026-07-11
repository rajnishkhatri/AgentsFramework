---
title: 'D4 — Skills nav via comingSoon · Tasks'
type: tasks
sprint: D4
epic: D
status: Ready — 2026-07-11 (alternate; activates only on human override)
owner: Rajnish Khatri
derives_from: docs/plan/preact-parity-D4-skills-nav.plan.md
related:
  - docs/plan/preact-parity-D4-skills-nav.spec.md
---

# D4 — Skills nav via `comingSoon` · Tasks

D4 fires only if the human overrides the board's default (defer to Epic E).
If not overridden, only T-DEFER runs.

## Design (before human posture pick)

- **T-DES-D4 [blocks T-GATE]. Nav-order + surface-consistency design review.**
  Two artefacts locked before the human picks posture:
  1. **Placement in `NAV_MEMBERSHIP.desktop` and `.ipad`.** Plan §2 puts
     `"skill"` between `"coach"` and `"progress"`. Confirm against
     `PreAct/UI-Design/English Coach - Flow (iPad).html` and the same-family
     desktop mockup — cite where the prototype places Skills in the sidebar
     list order. If prototype puts Skills between `dashboard` and `quiz`,
     move it. Record the source citation in the T-DES-D4 note.
  2. **iPhone consistency call.** The design-spec at §8.1 supersedes with a
     3-tab bar (Home / Practice / Progress). Confirm Skills does NOT appear
     on iPhone (plan §2). If the prototype's iPhone flow adds Skills as a
     contextual overflow ("More" or long-press), that is out of D4 scope —
     note it as a follow-up for Epic E, do NOT ship it here.
  **FR:** informs FR-2, FR-3.
  **Verification:** a short note in `docs/plan/preact-parity-D4-skills-nav.impl.md`
  captures the two decisions with source citations to the prototype HTML
  files. This runs even if T-GATE picks Defer (the citations become part of
  the deferral rationale in `decisions.md`).

## Gate — human posture pick

- **T-GATE. Confirm posture.**
  Present the two options:
  - **Default (recommended):** defer to Epic E's board. → run T-DEFER, skip
    everything else.
  - **Alternate:** ship the `comingSoon` nav entry now. → run T-1..T-11.

## Deferral path (default)

- **T-DEFER. `decisions.md` line + parity report update.**
  Prepend to [`docs/adr/decisions.md`](../adr/decisions.md):
  > `- D-8 (2026-07-DD): deferred to Epic E per D4 alternate declined. Adding "skill" to NAV_MEMBERSHIP without a live /learn/skill route re-opens the Q-6 trust-bug class Epic A closed. Epic E will land route + membership together. Alternate spec preserved at docs/plan/preact-parity-D4-skills-nav.spec.md.`

  Then update [`preact-parity-sprint-board-D.md`](preact-parity-sprint-board-D.md)
  D4 status → **Declined** (with cite); update parity report §D-8 to
  "deferred to Epic E".
  **Verification:** grep for `D-8` in `decisions.md` → returns the line. No
  code changes.
  **DONE — sprint closes.**

## Ship path (alternate — only if T-GATE picks it)

### Red bar (failing tests first)

- **T-1 [parallel with T-2, T-3, T-4].** New arch test:
  `frontend/tests/architecture/test_no_dead_skill_route.ts`.
  Assert `fs.existsSync(path.join(__dirname, "../../frontend/app/(coach)/learn/skill"))
  === false`. Regression guard (green pre-D4; flips red when Epic E creates the
  route, forcing D4's posture to be reconsidered).
  **FR:** FR-5.
  **Verification:** SEEN GREEN pre-D4 (route absent).

- **T-2 [parallel with T-1, T-3, T-4].** Extend
  `frontend/components/shell/nav_model.test.ts`:
  - `skill_membership_desktop_ipad_only` — asserts membership as spec §FR-2.
  - `skill_hydrates_as_disabled` — hydrate the desktop nav via
    `navItemsForSurface("desktop")`, find `screenId === "skill"`, assert
    `disabled === true`, `href === ""`, `comingSoon === true`.
  **FR:** FR-2, FR-3.
  **Verification:** SEEN RED pre-D4 (membership does not include `"skill"`
  yet).

- **T-3 [parallel with T-1, T-2, T-4].** Extend
  `frontend/components/shell/AppNav.test.tsx`:
  Add `skill_item_is_not_clickable` — render `<AppNav surface="desktop" pathname="/learn" />`
  after membership includes `"skill"`; find the `[data-screen="skill"]` node;
  assert (a) it is a `<span>`, not an `<a>`; (b) `aria-disabled="true"`;
  (c) `title="Coming soon"`. This test is authored red and turns green after
  T-5 lands the membership.
  **FR:** FR-1, FR-3, FR-4.
  **Verification:** SEEN RED pre-T-5.

- **T-4 [parallel with T-1, T-2, T-3].** New Playwright:
  `frontend/e2e/learn/nav-skills-coming-soon.spec.ts`.
  Two scenarios: `desktop` and `ipad` (Playwright surface projects). For each:
  - Navigate to `/learn`.
  - Assert `[data-screen="skill"]` visible in the sidebar with
    `aria-disabled="true"`.
  - Attempt `page.locator('[data-screen="skill"]').click()`; assert
    `page.url()` unchanged after 500ms; assert no network request to
    `/learn/skill`.
  **FR:** FR-1, FR-3, FR-4.
  **Verification:** SEEN RED pre-D4.

### Green bar

- **T-5. `NAV_MEMBERSHIP` edit.**
  Edit [`nav_model.ts:103-107`](../../frontend/components/shell/nav_model.ts:103):
  ```ts
  desktop: ["dashboard", "quiz", "coach", "skill", "progress"],
  ipad:    ["dashboard", "quiz", "coach", "skill", "progress"],
  iphone:  ["dashboard", "quiz", "progress"],  // unchanged
  ```
  **FR:** FR-2.
  **Verification:** T-2 + T-3 turn green.

- **T-6. Snapshot check on `screen("skill")`.**
  Add `nav_model.test.ts::screen_skill_catalog_unchanged` — asserts the four
  fields of `screen("skill")` are unchanged from today (`route: "/learn/skill"`,
  `navLabel: "Skill"`, `comingSoon: true`, `isFocusScreen: false`).
  **FR:** FR-6.
  **Verification:** green immediately (defensive; catches future accidental
  edits).

### Full-bundle gate

- **T-7 [blocks T-8]. Arch-test full run.**
  `pnpm exec vitest run frontend/tests/architecture/` — including T-1 (no
  dead route) + all existing arch tests.
  **FR:** FR-5.

- **T-8 [parallel with T-9]. E2E green.**
  `pnpm exec playwright test e2e/learn/nav-skills-coming-soon.spec.ts --project chromium`
  (and iPad if that projection exists). Paste actual output.
  **FR:** FR-1, FR-3, FR-4.

- **T-9 [parallel with T-8]. Continuity re-run.**
  Re-run `frontend/components/shell/nav_model.test.ts` (existing cases) +
  `AppNav.test.tsx` (existing cases) — must remain green (regression guard
  for `progress` + `coach` handling).

### Docs

- **T-10 [parallel with T-11]. `decisions.md` line.**
  Prepend:
  > `- D-8 (2026-07-DD): shipped via D4 alternate posture (human override). Skills nav entry visible on desktop + iPad as comingSoon (non-clickable). iPhone unchanged (3-tab supersede). /learn/skill remains Epic E's floor; arch test test_no_dead_skill_route.ts flips red when Epic E creates the route (posture reconsider gate).`

- **T-11 [parallel with T-10]. Flip sprint-board + parity report.**
  [`preact-parity-sprint-board-D.md`](preact-parity-sprint-board-D.md) D4
  status → **Implemented (alternate posture)**; append `## Implementation
  evidence`. [`preact-ui-prototype-parity-VISUAL-gap-report.md`](preact-ui-prototype-parity-VISUAL-gap-report.md)
  §D-8 → "entry visible; route deferred to Epic E".

### Validation (post-implementation UI walk — ship path only)

Mirrors D1's paired `validate_d1_quiz_frame_ui.md` + `quiz-frame.spec.ts` pattern
([`frontend/scripts/validate_d1_quiz_frame_ui.md`](../../frontend/scripts/validate_d1_quiz_frame_ui.md), [`frontend/e2e/learn/quiz-frame.spec.ts`](../../frontend/e2e/learn/quiz-frame.spec.ts)).

If T-GATE picked Defer, skip this section entirely — T-DEFER is the closure.

- **T-VAL-D4a [blocks T-VAL-D4b, T-VAL-D4c].** Author manual runbook:
  `frontend/scripts/validate_d4_skills_nav_ui.md`.
  Mirror `validate_d1_quiz_frame_ui.md`:
  - **Header table**: Spec / Plan / Tasks / `decisions.md` line / Board /
    L4 suite (`nav-skills-coming-soon.spec.ts`).
  - **What you should expect to SEE**: `Skill` entry visible in desktop +
    iPad sidebar (dimmed / non-interactive); absent from iPhone bottom bar;
    clicking has no effect (no navigation, no network fetch to
    `/learn/skill`).
  - **Part 0 — boot**: same middleware + branch checkout + hard-refresh
    warning.
  - **Part 1 — Desktop cold open**: `/learn` in a desktop viewport
    (≥1280px); sidebar shows `Skill` in the expected order (per T-DES-D4);
    the Skill row is a `<span data-screen="skill" aria-disabled="true"
    title="Coming soon">` — NOT an `<a>`. DevTools snippet:
    `document.querySelector('[data-screen="skill"]').tagName` → `SPAN`.
  - **Part 2 — Click does not navigate**: click the Skill row; URL stays at
    `/learn`; open DevTools Network tab, filter `/learn/skill` — zero
    requests. Confirms FR-4.
  - **Part 3 — iPad cold open** (via responsive DevTools OR
    `preview_resize`): confirm Skill visible in the sidebar as a coming-soon
    item.
  - **Part 4 — iPhone cold open** (viewport ≤600px): confirm the bottom tab
    bar shows only Home / Practice / Progress. Skill MUST NOT be present
    (FR-2 negative case).
  - **Part 5 — Regression walk**: `Progress` still coming-soon on all three
    surfaces (baseline); `Coach` still active on desktop + iPad; navigation
    between Home / Practice / Coach still works and doesn't 404.
  - **Part 6 — Docs spot-check**: `decisions.md` newest line records the
    outcome (shipped alternate); sprint-board D4 flipped to Implemented
    (alternate); parity report §D-8 updated.
  - **Part 7 — Console hygiene**: no red errors during the walk.
  - **§A automated proof**: exact `pnpm exec vitest run components/shell/`
    + `pnpm exec playwright test e2e/learn/nav-skills-coming-soon.spec.ts`.
  - **Pass/fail summary**: mirror D1's.
  **FR:** covers FR-1, FR-2, FR-3, FR-4, FR-5 as a manual sanity net.
  **Verification:** file exists; FR map covers every FR.

- **T-VAL-D4b [parallel with T-VAL-D4c].** Ensure the Playwright suite
  authored at T-4 covers everything T-VAL-D4a walks manually.
  If gaps exist (e.g., iPhone negative case is not in T-4), extend
  `nav-skills-coming-soon.spec.ts` with:
  - `iphone: skill absent from tab bar` — Playwright iPhone project or
    `page.setViewportSize({ width: 375, height: 812 })`; asserts
    `page.locator('[data-screen="skill"]').count() === 0`.
  - `progress still coming-soon` (regression guard) — hydrate desktop nav;
    assert `[data-screen="progress"]` has `aria-disabled="true"`.
  **FR:** FR-1, FR-2 (iPhone negative case), FR-5 continuity.
  **Verification:** ` pnpm exec playwright test e2e/learn/nav-skills-coming-soon.spec.ts --project chromium`
  green including the new cases.

- **T-VAL-D4c [parallel with T-VAL-D4b]. Human runbook walk.**
  Run T-VAL-D4a end-to-end (three viewports: desktop, iPad, iPhone). Every
  checkbox ticked; failures captured per D1 convention.
  **FR:** all D4 FRs.
  **Verification:** ticked runbook; summary line in D4 impl trace.

### Final gate

- **T-Z [blocks merge].** `make check` + `pytest tests/architecture/ -q` +
  `pnpm exec vitest run components/shell/` + `pnpm exec playwright test e2e/learn/nav-skills-coming-soon.spec.ts --project chromium`.
  Paste actual output.

## Parallel groupings

```
T-DES-D4 → T-GATE

Defer path (default):     T-DEFER  → done.

Ship path (alternate):    { T-1 ‖ T-2 ‖ T-3 ‖ T-4 }              (red bar; parallel)
                          → T-5 → T-6                             (green bar + snapshot)
                          → T-7 → { T-8 ‖ T-9 }                   (arch + e2e + continuity)
                          → T-VAL-D4a → { T-VAL-D4b ‖ T-VAL-D4c } (validation runbook + suite + walk)
                          → { T-10 ‖ T-11 } → T-Z                 (docs then final gate)
```

## FR-to-task coverage matrix (ship path)

| FR | Task(s) | Layer |
|----|---------|-------|
| FR-1 | T-3, T-4, T-9, T-VAL-D4b, T-VAL-D4c | L1 + L4 + continuity + manual |
| FR-2 | T-2, T-5, T-VAL-D4a Part 4, T-VAL-D4b iPhone case | L1 + L4 + manual |
| FR-3 | T-2, T-3, T-4, T-VAL-D4c | L1 + L4 + manual |
| FR-4 | T-3, T-4, T-VAL-D4a Part 2 | L1 + L4 + manual |
| FR-5 | T-1, T-7 | L1 arch |
| FR-6 | T-6 | L1 snapshot |
| design | T-DES-D4 | intent locked pre-gate |
| runbook | T-VAL-D4a, T-VAL-D4c | manual walk |
