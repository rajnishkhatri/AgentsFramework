---

## type: tasks
title: "Wide-layout & CoachPanel parity — tasks (Direction 2b)"
description: >-
  Stage 3 atomic L0–L6 tasks for preact-wide-layout-coach-panel. Measurability
  checklist + file-level pass/fail mapped 1:1 to FR-1…FR-20 ≡ locked AC-1…20.
  Clarify locks Q-C1…Q-C5 CLOSED. Draft W0–W9 invalidated — do not implement
  from Sheet / 56px / sidebarUserPinned / use_collapsible_thread oracles.
status: "Stage 6 IN PROGRESS 2026-07-16 — L0–L5 product code landed; L6 residual recorded; → sdd-converge / code-review"
authored: 2026-07-16
derives_from:
  - docs/plan/preact-wide-layout-coach-panel.spec.md
  - docs/plan/preact-wide-layout-coach-panel.plan.md
  - docs/adr/0035-wide-layout-coach-panel-parity.md
  - docs/width-design-ui-session-artifacts/locked-spec-artifacts/PreACT-English-Coach-LOCKED-Spec.md

# Tasks — Wide-layout & CoachPanel parity (Direction 2b)

**Spec:** [preact-wide-layout-coach-panel.spec.md](preact-wide-layout-coach-panel.spec.md) ·
**Plan:** [preact-wide-layout-coach-panel.plan.md](preact-wide-layout-coach-panel.plan.md) ·
**ADR:** [0035-wide-layout-coach-panel-parity.md](../adr/0035-wide-layout-coach-panel-parity.md) ·
**Lock:** [locked-spec-artifacts/](../width-design-ui-session-artifacts/locked-spec-artifacts/)

**Status:** Stage 4 PASSED — 2026-07-16. Baseline green. Human Accept →
`sdd-implement` on L-track only. Draft W0–W9 board removed (superseded).

Convention: `L{n}` = track; `T{n}.{m}` = task; `[P]` = parallelizable with other
same-block `[P]` tasks; `[red]` = watched failure first; each task names
**Verifies** FR(s) and explicit **Pass / Fail**.

**Clarify locks (do not re-litigate):** Q-C1 Zone C nudge · Q-C2 amend ADR-0035 ·
Q-C3 layout-local content rail · Q-C4 CoachDrawer (not Sheet chrome) ·
Q-C5 `use_expandable_list` replaces `use_collapsible_thread`.

**Branch posture:** implement on a feature branch off current tip after Stage 4.
Do not weaken iPhone FR-18 oracles. No new npm deps.

---

## Checklist — every FR collapses to a measurable claim (Stage 3 gate)


| FR    | Measurable claim                                                                         | Oracle / evidence                                       |
| ----- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| FR-1  | content width < 900 → no `coach-panel-inline`; `coach-trigger-pill` visible              | Unit `coachMode` + e2e 768×1024                         |
| FR-2  | Escape/scrim closes drawer; focus returns to pill; Tab trapped inside                    | e2e (+ RTL trap if unitable)                            |
| FR-3  | streaming answer forced expanded; collapse ignored until complete                        | Unit/RTL `use_expandable_list` + CollapsibleCoachAnswer |
| FR-4  | error answer stays expanded + Retry; excluded from auto-collapse                         | RTL                                                     |
| FR-5  | exhausted nudge `aria-disabled` + reason string; composer still in Zone C                | RTL CoachPanel / HintLadderList                         |
| FR-6  | collapsed 64px rail contains reachable ThemeToggle                                       | AppNav test / e2e                                       |
| FR-7  | expand/collapse: `document.activeElement` unchanged; no live-region body rewrite         | RTL + axe                                               |
| FR-8  | `prefers-reduced-motion` → transition-duration 0s (sidebar / answer / drawer)            | e2e / component                                         |
| FR-9  | navigate Quiz|Coach|Skill|Test → sidebar width 64 on mount; no pin restore               | Unit store + e2e Home→Quiz                              |
| FR-10 | content ≥ 900 → item + `coach-panel-inline` (1440×900 and 1024×768)                      | e2e                                                     |
| FR-11 | item column + Zone B scroll independently; `document.scrollingElement.scrollTop === 0`   | e2e + L6                                                |
| FR-12 | scroll Zone B → Zone C (nudge + chips + composer) tops unchanged                         | e2e                                                     |
| FR-13 | on complete: prior non-error collapsed; newest expanded                                  | Unit `use_expandable_list`                              |
| FR-14 | new nudge reveal → that row auto-open; other rows retain state                           | Unit ladder / HintLadderList                            |
| FR-15 | composer input computed `min-height` ≥ 58px                                              | Component Composer                                      |
| FR-16 | wide inline Ask-coach: no `router.push`; pin set; composer focused                       | e2e                                                     |
| FR-17 | drawer Ask-coach: drawer open + composer focused after 220ms (or instant reduced-motion) | e2e                                                     |
| FR-18 | 390×844: no inline/drawer; 4 tabs; no Skill                                              | e2e                                                     |
| FR-19 | dismiss inline → thread still on `/learn/coach`                                          | e2e                                                     |
| FR-20 | collapsed answer: chevron + "Coach" + truncated first-sentence span; no timestamp        | RTL                                                     |


All twenty collapse to L1/L2 vitest or on-demand Playwright / L6 → **no
unmeasurable criterion**; proceed after Stage 4.

### FR → primary task coverage


| FR    | Primary tasks                |
| ----- | ---------------------------- |
| FR-1  | T1.1, T4.1, T4.2, T4.3, T5.1 |
| FR-2  | T4.1, T4.2, T5.1             |
| FR-3  | T2.1, T2.3, T3.2             |
| FR-4  | T2.1, T2.3, T3.2             |
| FR-5  | T2.2, T3.1                   |
| FR-6  | T1.4, T5.1                   |
| FR-7  | T2.1, T2.3                   |
| FR-8  | T1.3, T1.4, T4.1, T5.1       |
| FR-9  | T1.1, T1.2, T1.3, T1.4, T5.1 |
| FR-10 | T1.1, T3.1, T4.3, T5.1       |
| FR-11 | T1.3, T3.1, T5.1, T6.1       |
| FR-12 | T3.1, T4.3, T5.1             |
| FR-13 | T2.1, T2.4, T3.2             |
| FR-14 | T2.1, T2.2                   |
| FR-15 | T3.1, T3.4                   |
| FR-16 | T4.3, T5.1                   |
| FR-17 | T4.1, T4.3, T5.1             |
| FR-18 | T3.3, T5.3                   |
| FR-19 | T1.2, T4.3, T5.1             |
| FR-20 | T2.3, T3.1                   |


---

## L0 — Docs Accepted + baseline

- **T0.1** — Spec / plan / ADR-0035 re-Accepted for Direction 2b + OKF index/log.
  - Files: `docs/plan/preact-wide-layout-coach-panel.{spec,plan,tasks}.md`,
  `docs/adr/0035-wide-layout-coach-panel-parity.md`,
  `docs/plan/index.md`, `docs/plan/log.md`, `docs/adr/index.md`,
  `docs/adr/log.md`, `docs/adr/decisions.md`.
  - Verifies: Stage 2 artifacts exist; clarify Q-C1…Q-C5 recorded.
  - Pass: paths present; frontmatter `status: Accepted` on spec/plan; ADR amended.
  Fail: missing ADR or draft FR-1…16 still authoritative.
  - deps: none. (**Done** as of Stage 2 close — confirm at Stage 4 grounding.)
- **T0.2** — This Stage 3 tasks board (L0–L6) Accepted; index/log cite L-track.
  - Files: this file; `docs/plan/index.md`; `docs/plan/log.md`.
  - Verifies: implement gate has atomic FR→task map; W-track gone.
  - Pass: frontmatter `Stage 3 Accepted`; no W0–W9 implement instructions.
  Fail: implementer still pointed at Sheet / 56px / pin tasks.
  - deps: T0.1.
- **T0.3** — Baseline green before L1 product code.
  - Cmd: `make check` (or scoped frontend vitest + `pytest tests/architecture/ -q` if agreed).
  - Verifies: no pre-existing red.
  - Pass: paste green output at Stage 4 close. Fail: start L1 on red baseline.
  - deps: T0.2.

---

## L1 — Shell: `coachMode` + 64px + store + AppNav `[P]` with L2

- **T1.1 [red]** — `coachMode` + `RAIL_COLLAPSED = 64` + tests.
  - File: `frontend/components/shell/use_surface.ts`
  - File: `frontend/components/shell/use_surface.test.ts`
  - Behaviors:
    1. `RAIL_COLLAPSED === 64`; keep `RAIL_EXPANDED = 224`, `SPLIT_MIN_CONTENT_WIDTH = 900`.
    2. `coachMode(surface, viewportWidth, sidebarWidth)` →
      `iphone` → `"fullscreen"`; else
       `(viewportWidth - sidebarWidth) >= 900` → `"inline"`; else `"drawer"`.
    3. Quiz layout decisions use `coachMode`, not pin-aware degrade ladder.
    4. `isWideSurface` may remain for nav helpers only.
  - Red first: assert `coachMode("ipad", 1024, 64) === "inline"` (960 ≥ 900);
  `coachMode("ipad", 768, 64) === "drawer"`; `coachMode("iphone", …) === "fullscreen"`;
  `RAIL_COLLAPSED === 64` (watch 56 fail).
  - Verifies: **FR-1, FR-9, FR-10** (and FR-8 consumer of rail constant).
  - Pass: vitest green with fail→pass paste. Fail: 56px or pin-aware ladder remains.
  - deps: T0.3.
- **T1.2 [red][P]** — Narrow `shell_layout_store`; drop session pin.
  - File: `frontend/components/shell/shell_layout_store.ts`
  - File: `frontend/components/shell/shell_layout_store.test.ts`
  - Behaviors:
    1. **Remove** `sidebarUserPinned` / `sessionStorage["preact.shell.sidebarPinned"]`.
    2. Home/Progress: `sidebarCollapsed` ↔ `localStorage["preact.shell.sidebar"]`
      (default expanded).
    3. Keep `panelDismissed` ↔ `sessionStorage["preact.shell.panelDismissed"]`.
    4. Content-screen collapse is **not** owned here (Q-C3 → layout-local).
  - Red first: pin key absent; content-screen APIs that force-unless-pinned removed.
  - Verifies: **FR-9, FR-19**.
  - Pass: unit green; no pin symbol in store. Fail: pin restores expanded content rail.
  - deps: T0.3.
- **T1.3** — Learn layout: content always-collapsed local + height chain.
  - File: `frontend/app/(coach)/learn/layout.tsx`
  - Behaviors:
    1. On Quiz/Coach/Skill/Test: layout-local `sidebarCollapsed` init `true`;
      mid-session toggle in-memory only (no LS write for content screens).
    2. Home/Progress: use store persistence.
    3. Wide shell height chain per plan §3 (`h-dvh`, `main` `min-h-0`, etc.).
    4. Wire AppNav collapse width to `RAIL_COLLAPSED` (64).
  - Verifies: **FR-8, FR-9, FR-11**.
  - Pass: remount Quiz → rail 64; Home may expand from LS. Fail: content remount
  restores expanded from prior pin/LS.
  - deps: T1.1, T1.2.
- **T1.4 [red]** — AppNav icon rail redlines.
  - File: `frontend/components/shell/AppNav.tsx`
  - File: `frontend/components/shell/AppNav.test.tsx`
  - Behaviors:
    1. Collapsed rail width **64px**.
    2. Nav buttons **38×38** circular (not `min-h-11` / 44).
    3. ThemeToggle always last item in rail; reachable when collapsed (**FR-6**).
    4. `[` toggles collapse; transition 180ms `cubic-bezier(0.4,0,0.2,1)`;
      `prefers-reduced-motion` → instant (**FR-8**).
  - Red first: assert collapsed width 64; ThemeToggle present when collapsed.
  - Verifies: **FR-6, FR-8, FR-9**.
  - Pass: AppNav tests green. Fail: 56px rail or ThemeToggle missing when collapsed.
  - deps: T1.1, T1.3.

---

## L2 — Expandable list + ladder + answer `[P]` with L1

- **T2.1 [red]** — `use_expandable_list` generic hook + tests.
  - File **NEW:** `frontend/components/coach/use_expandable_list.ts`
  - File **NEW:** `frontend/components/coach/use_expandable_list.test.ts`
  - API sketch (exact names may match lock §8; keep pure + testable):
    ```ts
    // Two instances: ladder rows + conversation turns
    useExpandableList(opts: {
      ids: string[];
      // force-open for streaming / error (conversation)
      forceExpandedIds?: ReadonlySet<string>;
      // on complete: collapse all prior non-error; keep newest open
      autoCollapseOnComplete?: boolean;
      // on new id: auto-expand that id only; leave others
      autoExpandNewest?: boolean;
    })
    ```
  - Behaviors:
    1. Completion path → newest expanded; prior non-error collapsed (**FR-13**).
    2. Streaming / error in `forceExpandedIds` → expanded; toggle ignored (**FR-3, FR-4**).
    3. New id with `autoExpandNewest` → that row opens; others retain (**FR-14**).
    4. Manual toggle does not steal focus semantics (consumer FR-7).
  - Red first: write FR-13/14/3/4 cases; watch fail before implement.
  - Verifies: **FR-3, FR-4, FR-7, FR-13, FR-14**.
  - Pass: vitest green with fail→pass paste. Fail: two divergent expand hooks remain.
  - deps: T0.3.
- **T2.2 [red][P]** — `HintLadderList` + tests.
  - File **NEW:** `frontend/components/coach/HintLadderList.tsx`
  - File **NEW:** `frontend/components/coach/HintLadderList.test.tsx`
  - Behaviors:
    1. Renders revealed rungs as expandable rows via `use_expandable_list`.
    2. New reveal auto-expands that row; priors retain (**FR-14**).
    3. Exhausted state surfaces disabled reason for parent nudge (**FR-5** consumer).
    4. Appropriate polite announce for new reveal (no conversation live-region rewrite).
  - Verifies: **FR-5, FR-14**.
  - Pass: RTL green. Fail: bubble-only nudge UI without expandable ladder rows.
  - deps: T2.1.
- **T2.3 [red]** — Migrate `CollapsibleCoachAnswer` to expandable list + AC-20 chrome.
  - File: `frontend/components/coach/CollapsibleCoachAnswer.tsx`
  - File: `frontend/components/coach/CollapsibleCoachAnswer.test.tsx`
  - Behaviors:
    1. Consumes expand state from `use_expandable_list` (not `use_collapsible_thread`).
    2. Streaming / error force-expand; Retry reachable on error (**FR-3, FR-4**).
    3. Collapsed chrome: chevron + label `"Coach"` + single-line truncated first
      sentence; **no timestamp** (**FR-20**).
    4. Toggle leaves focus; does not rewrite conversation live region (**FR-7**).
  - Red first: assert no timestamp node; collapsed label structure.
  - Verifies: **FR-3, FR-4, FR-7, FR-20**.
  - Pass: RTL green. Fail: timestamp or old hook still imported.
  - deps: T2.1.
- **T2.4** — Delete `use_collapsible_thread` (+ tests); G8 justify.
  - Files **DELETE:** `frontend/components/coach/use_collapsible_thread.ts`,
  `frontend/components/coach/use_collapsible_thread.test.ts`
  - Retarget any remaining imports to `use_expandable_list`.
  - G8: removed `test_`* are replaced by T2.1 suite covering same FR-3/4/13 claims;
  document one-line justification in PR/commit if ratchet fires.
  - Verifies: **FR-13** (Q-C5).
  - Pass: `rg use_collapsible_thread frontend/` empty; vitest green.
  Fail: dual hooks coexist.
  - deps: T2.1, T2.3, T3.2.

---

## L3 — Zone A/B/C Direction 2b + composer (after L2)

- **T3.1 [red]** — CoachPanel Zones A/B/C + widths + Zone C nudge.
  - File: `frontend/components/coach/CoachPanel.tsx`
  - File: `frontend/components/coach/CoachPanel.test.tsx`
  - Behaviors:
    1. Zone A fixed header (status / mode copy per lock).
    2. Zone B scroll = `HintLadderList` + separator + conversation
      (`role="log"` on conversation only).
    3. Zone C pinned = **"+ One more nudge"** + chips + composer (**Q-C1 / FR-12**).
    4. Exhausted nudge: `aria-disabled` + tooltip
      `"You've used all available nudges for this item"`; composer stays (**FR-5**).
    5. Widths: desktop `clamp(400px, 30vw, 480px)`; iPad fixed `360px`
      (drop `w-80` / draft `clamp(340px, 32%, 460px)`).
    6. Inline host testid `coach-panel-inline`.
  - Verifies: **FR-5, FR-10, FR-11, FR-12, FR-15, FR-20**.
  - Pass: RTL green; Zone C contains nudge. Fail: nudge scrolls away in Zone B.
  - deps: T2.2, T2.3.
- **T3.2** — CoachView conversation instance of expandable list.
  - File: `frontend/components/coach/CoachView.tsx`
  - Wire conversation turns through `use_expandable_list` + `CollapsibleCoachAnswer`.
  - Verifies: **FR-3, FR-4, FR-7, FR-13**.
  - Pass: CoachView tests green; no `use_collapsible_thread` import.
  - deps: T2.1, T2.3.
  - Unblocks: T2.4.
- **T3.3 [P]** — CoachWorkspace / CoachChrome same Zone stack.
  - Files: `frontend/components/coach/CoachWorkspace.tsx`,
  `frontend/components/coach/CoachChrome.tsx`
  - Same Zone A/B/C contract; outer chrome/width only differs for fullscreen
  (iPhone FR-18 path).
  - Verifies: **FR-10–FR-15, FR-18** (fullscreen host only).
  - Pass: workspace tests / smoke still green. Fail: divergent Zone C on fullscreen.
  - deps: T3.1.
- **T3.4 [red][P]** — Composer min-height 58px.
  - File: `frontend/components/chat/Composer.tsx`
  - File: existing or new Composer test under `frontend/components/chat/`
  - Behavior: coach composer input `min-height: 58px` (two text lines); grows on wrap.
  - Verifies: **FR-15**.
  - Pass: computed style / class assertion ≥ 58. Fail: single-line default height.
  - deps: T0.3.

---

## L4 — CoachDrawer + pill + quiz host (after L1 + L3)

- **T4.1 [red]** — `CoachDrawer` overlay chrome + focus trap.
  - File **NEW:** `frontend/components/coach/CoachDrawer.tsx`
  - File **NEW:** `frontend/components/coach/CoachDrawer.test.tsx` (RTL trap / Escape)
  - Behaviors (lock §5; Q-C4):
    1. Width `min(430px, 92vw)`; scrim; ✕ / Escape / scrim close.
    2. Focus trap while open; restore focus to trigger on close (**FR-2**).
    3. Open/close 220ms (or 180ms per lock timing); `prefers-reduced-motion` → instant (**FR-8**).
    4. May reuse in-tree focus-trap/dialog primitives; **must not** use Sheet visual
      chrome or edge-tab.
    5. Hosts same Zone A/B/C CoachPanel stack.
  - Verifies: **FR-1, FR-2, FR-8, FR-17**.
  - Pass: RTL Escape + focus return. Fail: Sheet still product drawer.
  - deps: T1.1, T3.1.
- **T4.2 [red][P]** — `CoachTriggerPill`.
  - File **NEW:** `frontend/components/coach/CoachTriggerPill.tsx`
  - File **NEW:** `frontend/components/coach/CoachTriggerPill.test.tsx` (optional light)
  - Behaviors: floating "Coach" control; `data-testid="coach-trigger-pill"`;
  opens drawer; receives focus restore target.
  - Verifies: **FR-1, FR-2**.
  - Pass: pill renders in drawer mode. Fail: `coach-edge-tab` still the trigger.
  - deps: T4.1 (or parallel if pill is presentational-only; wire in T4.3).
- **T4.3 [red]** — Quiz page: `coachMode` switch + bridge; remove Sheet / edge-tab.
  - File: `frontend/app/(coach)/learn/quiz/page.tsx`
  - Behaviors:
    1. Switch on `coachMode(surface, viewportWidth, sidebarWidth)`:
      `inline` | `drawer` | `fullscreen` (iphone → no panel/drawer).
    2. Inline: item + CoachPanel; dismiss → `panelDismissed`; no edge-tab (**FR-19**).
    3. Drawer: CoachTriggerPill + CoachDrawer; never stack coach under item (**FR-1**).
    4. Item column max-width 720/560; 1px divider; no gap (**FR-10–12**).
    5. Feedback "Ask the coach about this":
      - inline → pin + rAF focus composer; no navigate (**FR-16**);
      - drawer → open drawer then focus composer after 220ms (**FR-17**);
      - iphone → navigate (existing).
    6. **Remove** shadcn Sheet path and `coach-edge-tab`.
  - Verifies: **FR-1, FR-2, FR-10, FR-11, FR-12, FR-16, FR-17, FR-18, FR-19**.
  - Pass: quiz host uses drawer/pill; Sheet imports gone from quiz page.
  Fail: `sidebarUserPinned` or Sheet still gates layout.
  - deps: T1.1, T1.2, T1.4, T3.1, T4.1, T4.2.

---

## L5 — E2E AC matrix (after L4)

- **T5.1 [red]** — Rewrite `wide-layout.spec.ts` to locked §12 / FR matrix.
  - File: `frontend/e2e/learn/wide-layout.spec.ts`
  - Cover on-demand (not necessarily all in `make check`):
  FR-1, FR-2, FR-6, FR-8, FR-9, FR-10, FR-11, FR-12, FR-16, FR-17, FR-19
  per spec §8 test plan (viewports 768×1024, 1440×900, 1024×768, reduced-motion).
  - Drop oracles for: 56px rail, `sidebarUserPinned`, Sheet, `coach-edge-tab`,
  draft FR renumbering.
  - Verifies: **FR-1, FR-2, FR-6, FR-8, FR-9, FR-10, FR-11, FR-12, FR-16, FR-17, FR-19**.
  - Pass: targeted Playwright green with paste. Fail: draft oracles still assert Sheet.
  - deps: T4.3.
- **T5.2** — Retarget `ipad.spec.ts`.
  - File: `frontend/e2e/learn/ipad.spec.ts`
  - Align with `coachMode` + drawer/pill; remove pin / Sheet / edge-tab assumptions.
  - Verifies: iPad subset of FR-1/10/18 host behavior.
  - Pass: ipad suite green or intentionally scoped. Fail: broken imports/selectors.
  - deps: T4.3.
- **T5.3 [P]** — iPhone FR-18 negatives.
  - File: `frontend/e2e/learn/wide-layout.spec.ts` and/or existing iphone learn specs
  - Viewport 390×844: no `coach-panel-inline`; no `coach-trigger-pill` / drawer;
  4 tabs; Skill absent from tab bar.
  - Verifies: **FR-18**.
  - Pass: e2e green. Fail: drawer/pill on iphone.
  - deps: T4.3.

---

## L6 — Safari / `dvh` device sign-off (after L3; ‖ L4/L5)

- **T6.1** — Manual height-chain checklist on real Safari iPad (or recorded residual).
  - Checklist:
    1. Wide Quiz: browser window scrollTop stays 0; item + Zone B scroll.
    2. Zone C (nudge + chips + composer) remains visible after long log scroll.
    3. `dvh` shell does not clip Zone C under browser chrome.
    4. Home/Progress still page-scroll where needed.
  - Verifies: **FR-11** (+ residual FR-12).
  - Pass: notes pasted in PR/task close **or** residual risk recorded in
  `docs/adr/decisions.md` / converge. Fail: silent skip of DoD.
  - deps: T3.1.

---

## Sequencing summary

```
L0 (T0.1–T0.3)
 ├─ L1 ‖ L2
 │   L1: T1.1 → T1.2[P] → T1.3 → T1.4
 │   L2: T2.1 → T2.2[P] → T2.3 → (T2.4 after T3.2)
 ├─ L3: T3.1 → T3.2 → T3.3[P] ‖ T3.4[P]
 ├─ L4: T4.1 ‖ T4.2 → T4.3
 ├─ L5: T5.1 → T5.2 ‖ T5.3
 └─ L6: T6.1 (after T3.1; parallel L4/L5)
```

**Explicitly out of scope:** trust/, services/, orchestration/, bank/hints/LLM,
iPhone tab redesign beyond FR-18, auth/WorkOS, new npm deps,
Dashboard/Summary/Skill/Progress/Test internals beyond shell chrome.

---

## Stage 4 analyze — PASSED 2026-07-16

### Cross-artifact (spec ↔ plan ↔ tasks ↔ constitution)


| Check                                | Result                                                                       |
| ------------------------------------ | ---------------------------------------------------------------------------- |
| FR-1…20 each measurable + ≥1 task    | PASS — checklist + FR→task table; no zero-coverage FR                        |
| Plan T1–T17 ↔ task files             | PASS — same seams; L-track atomicizes plan §5                                |
| Clarify Q-C1…Q-C5                    | PASS — locked in spec; tasks refuse re-litigation                            |
| ADR-0035 amended (G1)                | PASS — 64px, no pin, CoachDrawer, `use_expandable_list`                      |
| New npm / py deps                    | PASS — none; no Ask-first dep trigger                                        |
| Layering (AGENTS.md #1–#8)           | PASS — frontend shell/components only                                        |
| Trust / orchestration / bank         | PASS — explicitly untouched                                                  |
| Draft seams scheduled for retirement | PASS — Sheet, edge-tab, pin, collapsible hook, 56px still in tree (expected) |


**CRITICAL:** none.

**Non-CRITICAL note (implement alias):** tree today uses
`SIDEBAR_COLLAPSED_PX = 56` in `use_surface.ts`; plan/tasks name
`RAIL_COLLAPSED = 64`. T1.1 renames/aliases to 64 — not a missing path.

Sibling draft `[preact-coach-panel-real-estate.spec.md](preact-coach-panel-real-estate.spec.md)`
(width / Zone-B scroll) is **out of this board**; Direction 2b widths in T3.1
likely subsume it — do not implement that draft in parallel without replan.

### Grounding pass

All cited existing paths exist. Expected NEW absent:
`use_expandable_list.ts`, `HintLadderList.tsx`, `CoachDrawer.tsx`,
`CoachTriggerPill.tsx` (+ tests). DELETE targets present:
`use_collapsible_thread.ts` (+ test). Lock folder + e2e specs exist.
Composer test file exists for T3.4. No MISSING CRITICAL paths.

### Baseline (T0.3) — green evidence

```text
make check  (2026-07-16)
  ruff check: All checks passed
  ruff format --check: 813 files already formatted
  pyright: 0 errors, 0 warnings, 0 informations
  cite_lint: clean
  hygiene hooks: Passed
  pytest: 5320 passed, 52 skipped, 72 deselected, 2 warnings in 185.13s

frontend scoped vitest (shell + coach + Composer.test.tsx):
  Test Files  16 passed (16)
  Tests       129 passed (129)
```

### Gate

Stage 4 **PASSED**. Proceed to `sdd-implement` after human Accept — L0 confirm
then L1 ‖ L2; no free-run outside this task board.