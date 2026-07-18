---
title: 'Wide-layout & CoachPanel parity — Spec (Direction 2b locked)'
type: spec
status: Accepted
date: 2026-07-16
owner: Rajnish Khatri
related:
  - docs/plan/preact-wide-layout-coach-panel.plan.md
  - docs/plan/preact-wide-layout-coach-panel.tasks.md
  - docs/adr/0036-wide-layout-coach-panel-parity.md
  - docs/width-design-ui-session-artifacts/locked-spec-artifacts/PreACT-English-Coach-LOCKED-Spec.md
  - docs/width-design-ui-session-artifacts/locked-spec-artifacts/README.md
  - docs/width-design-ui-session-artifacts/locked-spec-artifacts/Coach Layout Options - Locked Design + Redlines (standalone).html
governs:
  - frontend/components/shell/use_surface.ts
  - frontend/components/shell/shell_layout_store.ts
  - frontend/components/shell/AppNav.tsx
  - frontend/app/(coach)/learn/layout.tsx
  - frontend/app/(coach)/learn/quiz/page.tsx
  - frontend/components/coach/CoachPanel.tsx
  - frontend/components/coach/CoachView.tsx
  - frontend/components/coach/CoachWorkspace.tsx
  - frontend/components/coach/CoachChrome.tsx
  - frontend/components/coach/CollapsibleCoachAnswer.tsx
  - frontend/components/coach/use_expandable_list.ts
  - frontend/components/coach/HintLadderList.tsx
  - frontend/components/coach/CoachDrawer.tsx
  - frontend/components/coach/CoachTriggerPill.tsx
---

# Wide-layout & CoachPanel parity (Direction 2b)

> **What / why split.** This spec is the *what*. Intent debt for shell store,
> expandable-list hook, CoachDrawer, and `coachMode` lives in
> [ADR-0036](../adr/0036-wide-layout-coach-panel-parity.md) (G1 / ⚠️ Ask first),
> amended for the Direction 2b lock.
>
> **Product source of truth:**
> [`locked-spec-artifacts/PreACT-English-Coach-LOCKED-Spec.md`](../width-design-ui-session-artifacts/locked-spec-artifacts/PreACT-English-Coach-LOCKED-Spec.md)
> (+ HTML Turn 5 redlines). That file **supersedes** the earlier draft
> Implementation Spec and the prior Accepted FR-1…16 set where they disagree.
> FR-n ≡ locked AC-n (1:1).

**Status:** Accepted — 2026-07-16 (re-Accepted after Direction 2b lock;
clarify CLOSED — Q-C1…Q-C5 below). Plan:
[`preact-wide-layout-coach-panel.plan.md`](preact-wide-layout-coach-panel.plan.md).
Tasks: [`preact-wide-layout-coach-panel.tasks.md`](preact-wide-layout-coach-panel.tasks.md)
(Stage 3 Accepted — L0–L6; Stage 4 PASSED 2026-07-16). Human Accept →
Stage 6 (`sdd-implement`).

---

## Clarify locks (CLOSED 2026-07-16)

| ID | Question | Decision |
|----|----------|----------|
| **Q-C1** | Nudge control zone (§4.2 narrative vs AC-12 pin) | **Zone C** — `"+ One more nudge"` pinned with chips/composer; ladder rows only in Zone B |
| **Q-C2** | ADR for Sheet → CoachDrawer reversal | **Amend ADR-0036** + `decisions.md` note (lock supersession) |
| **Q-C3** | Content-screen sidebar state home | **Layout-local** boolean (init `true`, in-memory toggle); store owns Home/Progress `localStorage` + `panelDismissed` only; **drop** `sidebarUserPinned` |
| **Q-C4** | Reuse Sheet chrome for drawer? | New **`CoachDrawer.tsx`** per lock §5; may reuse in-tree focus-trap/dialog primitives, **not** Sheet visual chrome or edge-tab |
| **Q-C5** | Hook migration | Replace `use_collapsible_thread` with **`use_expandable_list`**; delete old hook + retarget tests (G8 justify removals) |

---

## 1. Goal

Desktop and iPad get quiz + live coach under one content-width rule (≥900px →
inline split; else overlay drawer), a **64px** icon-rail nav on content screens,
and a Direction **2b** coach column (hint ladder + conversation) with pinned
Zone C and collapsible prior answers. iPhone stays fullscreen Coach route only
— no inline panel, no drawer.

## 2. Context

- **Locked UX:** Direction 2b artifacts under
  [`docs/width-design-ui-session-artifacts/locked-spec-artifacts/`](../width-design-ui-session-artifacts/locked-spec-artifacts/).
- **Prior draft Stage 6** shipped a partial approximation (56px rail, session pin,
  Sheet drawer, bubble nudges, `use_collapsible_thread`). Stage 5 replan fired;
  this re-Accepted spec is the new source of truth before further product code.
- **Surfaces unchanged:** `iphone` ≤480 / `ipad` 481–1024 / `desktop` >1024
  (`use_surface.ts`).
- **One mode rule:**
  `coachMode(surface, viewportWidth, sidebarWidth)` →
  `iphone` → `fullscreen`; else
  `(viewportWidth - sidebarWidth) >= 900` → `inline`; else `drawer`.

## 3. Functional requirements (EARS)

Failure / edge paths first. **FR-n ≡ locked AC-n.**

- **FR-1.** IF content width is below 900px, THEN THE SYSTEM SHALL NOT render the
  coach inline; it SHALL render as an overlay drawer opened via a pinned "Coach"
  control.
- **FR-2.** WHILE the drawer is open, THE SYSTEM SHALL trap focus within it,
  close it on Escape or a scrim click, and return focus to the trigger control on
  close.
- **FR-3.** WHILE a coach reply is streaming, THE SYSTEM SHALL force that answer
  expanded and SHALL NOT allow it to be collapsed until the stream completes.
- **FR-4.** IF a coach turn is in an error state, THEN THE SYSTEM SHALL keep it
  expanded, exclude it from auto-collapse, and keep Retry reachable.
- **FR-5.** WHEN all ladder rungs for the current item are exhausted, THEN THE
  SYSTEM SHALL disable "One more nudge" with an accessible reason, without moving
  or hiding the composer.
- **FR-6.** WHILE the sidebar is collapsed, THE SYSTEM SHALL keep the theme toggle
  reachable in the icon rail.
- **FR-7.** WHEN the learner collapses or expands a coach answer, THE SYSTEM SHALL
  NOT move keyboard focus and SHALL NOT re-announce prior content through the live
  region.
- **FR-8.** IF `prefers-reduced-motion` is set, THEN THE SYSTEM SHALL apply all
  sidebar, answer, and drawer transitions instantly, with no animation.
- **FR-9.** WHEN the learner navigates to Quiz, Coach, Skill, or Test, THE SYSTEM
  SHALL always mount the sidebar collapsed to the **64px** icon rail, regardless
  of prior session state.

Nominal behavior.

- **FR-10.** WHERE the surface is desktop or iPad AND content width is at least
  900px, THE SYSTEM SHALL render the quiz item and the live coach panel
  side-by-side sharing one coach thread.
- **FR-11.** WHILE on the inline split, THE SYSTEM SHALL scroll the item column
  and the coach log independently and SHALL NOT scroll the browser window.
- **FR-12.** THE SYSTEM SHALL keep the composer, chip row, and "One more nudge"
  control pinned and visible regardless of coach-log scroll position (Zone C;
  Q-C1).
- **FR-13.** WHEN a coach reply completes, THE SYSTEM SHALL collapse all prior
  non-error answers and keep only the newest expanded.
- **FR-14.** WHEN a new nudge is revealed, THE SYSTEM SHALL auto-expand that
  ladder row and leave every other ladder row in its current state.
- **FR-15.** THE SYSTEM SHALL render the coach composer with a minimum input
  height of two text lines (**58px**) at all times, growing further as typed
  content wraps.
- **FR-16.** WHEN the learner activates "Ask the coach about this" on a wide,
  inline-mode surface, THE SYSTEM SHALL pin the item context and move focus to
  the coach composer without navigating.
- **FR-17.** WHEN the learner activates "Ask the coach about this" while content
  width is below 900px, THE SYSTEM SHALL open the coach drawer, pin the item
  context, and move focus to the composer once the open transition completes
  (220ms, or instant under reduced-motion).
- **FR-18.** WHERE the surface is iPhone, THE SYSTEM SHALL NOT render an inline
  coach panel or a drawer; Coach SHALL be reachable only as a full-screen route,
  and Skill SHALL NOT appear in its tab bar.
- **FR-19.** WHEN the learner dismisses the inline coach panel, THE SYSTEM SHALL
  preserve the coach thread and keep it reachable from the Coach nav item.
- **FR-20.** THE SYSTEM SHALL render a collapsed coach answer as a chevron, the
  label "Coach", and a single-line truncated first sentence, with no timestamp.

## 4. Data model / contracts

All client-side; no backend types; no new npm deps.

| State | Type | Lives in | Persistence |
|---|---|---|---|
| `sidebarCollapsed` (content screens) | `boolean` | layout-local | **none** — always init `true` on mount (Q-C3) |
| `sidebarCollapsed` (Home/Progress) | `boolean` | `shell_layout_store` | `localStorage["preact.shell.sidebar"]`, default `"expanded"` |
| `panelDismissed` | `boolean` | `shell_layout_store` | `sessionStorage["preact.shell.panelDismissed"]` (inline only) |
| `drawerOpen` | `boolean` | quiz page / host | none — ephemeral |
| `revealed` (nudge count) | `number` | CoachPanel local | none — resets per item |
| ladder / conversation expand maps | derived | `use_expandable_list` (two instances) | none |
| thread · pin · mode | store snapshot | `coach_thread_store` | unchanged |

**Dropped:** `sidebarUserPinned` / `sessionStorage["preact.shell.sidebarPinned"]`.

**Predicates / constants:**

- `RAIL_EXPANDED = 224`, `RAIL_COLLAPSED = 64`, `SPLIT_MIN_CONTENT_WIDTH = 900`.
- `coachMode(surface, viewportWidth, sidebarWidth)` as in §2.
- `isWideSurface(s) = s !== "iphone"` may remain for nav helpers; **quiz layout
  decisions use `coachMode`**, not a two-step pin-aware ladder.
- Surface labels and `surfaceForWidth` unchanged.

**Zone contract (Direction 2b):** Zone A fixed header; Zone B scroll =
`HintLadderList` + separator + conversation (`role="log"` on conversation only);
Zone C pinned = nudge + chips + composer (Q-C1). Same stack in inline, drawer,
and iPhone fullscreen (outer chrome/width only differs).

## 5. Invariants & security boundaries

- Frontend-only; no new graph node, py dep, or trust-kernel type → **no re-signing**.
- Architecture Invariants #1–#8 untouched.
- iPhone tab bar / focus-mode chrome: unchanged beyond lock §6 confirmation.
- Hint non-reveal pedagogy and coach LLM behavior unchanged.
- No new npm dependencies.
- G1 abstractions (ADR-0036 amended): `shell_layout_store` (narrowed),
  `use_expandable_list`, `CollapsibleCoachAnswer`, `HintLadderList`,
  `CoachDrawer`, `CoachTriggerPill`.

## 6. Edge cases

- Content width &lt; 900 → drawer + pill; never stack coach under item (FR-1).
- Drawer open → focus trap; Escape/scrim/✕ close; focus returns to pill (FR-2).
- Streaming / error turns ignore manual collapse and auto-collapse (FR-3/4).
- Exhausted ladder → nudge `aria-disabled` + tooltip
  `"You've used all available nudges for this item"`; composer stays pinned (FR-5).
- Content remount / navigate Quiz|Coach|Skill|Test → rail always 64px (FR-9);
  mid-session expand is in-memory only (Q-C3).
- Feedback bridge: iPhone navigates; drawer opens then focuses after 220ms;
  inline clears dismiss + rAF focus (FR-16/17).
- `prefers-reduced-motion` → instant sidebar / answer / drawer motion (FR-8).
- Home / Progress under `h-dvh` shell must still page-scroll where needed.

## 7. Non-functional requirements

- Deterministic L1 unit tests for `coachMode`, store, `use_expandable_list`.
- Component/RTL for ladder, collapsible answer, composer 58px, a11y.
- Playwright viewports per locked §12 (on-demand); iPhone negative tests.
- No live LLM in CI.
- Safari/`dvh` + nested `min-h-0` height chain validated on real device before DoD.

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | e2e 768×1024: no `coach-panel-inline`; `coach-trigger-pill` visible | L4 | on-demand |
| FR-2 | e2e Escape closes drawer; focus returns to pill; Tab trapped | L4 | on-demand |
| FR-3 | RTL streaming → expanded, toggle disabled/absent | L2 | yes |
| FR-4 | RTL error → expanded + Retry after auto-collapse event | L2 | yes |
| FR-5 | RTL exhausted → `aria-disabled`; composer position stable | L2 | yes |
| FR-6 | e2e collapsed rail ThemeToggle toggles theme | L4 | on-demand |
| FR-7 | RTL + axe: focus unchanged; no live-region rewrite | L2 | yes |
| FR-8 | e2e reduced-motion → transition-duration 0s | L4 | on-demand |
| FR-9 | e2e Home→Quiz → sidebar width 64px on mount | L4 | on-demand |
| FR-10 | e2e 1440×900 + 1024×768: item + `coach-panel-inline` | L4 | on-demand |
| FR-11 | e2e dual scroll; `document.scrollingElement.scrollTop === 0` | L4 | on-demand |
| FR-12 | e2e scroll log → Zone C tops unchanged | L4 | on-demand |
| FR-13 | unit `use_expandable_list` completion → newest only | L1 | yes |
| FR-14 | unit ladder reveal → latest auto-open; priors retain | L1 | yes |
| FR-15 | component composer-input min-height 58px | L2 | yes |
| FR-16 | e2e ask-coach inline: no navigate; composer focused | L4 | on-demand |
| FR-17 | e2e ask-coach drawer: open + composer focused post-transition | L4 | on-demand |
| FR-18 | e2e 390×844: no inline/drawer; 4 tabs, no Skill | L4 | on-demand |
| FR-19 | e2e dismiss → `/learn/coach` still has prior turns | L4 | on-demand |
| FR-20 | RTL collapsed answer: chevron + Coach + truncated span; no time | L2 | yes |

## 9. Definition of Done

- [ ] All FR-1…FR-20 implemented; each has a passing test that was *seen to fail first*.
- [ ] `make check` green; frontend learn unit + targeted e2e green.
- [ ] iPhone quiz/coach behavior matches FR-18 (regression suite).
- [ ] ADR-0036 amended for Direction 2b; design folder cited as Related only.
- [ ] Safari/`dvh` height-chain spike signed off (or residual risk recorded).
- [ ] Actual command output pasted for verification claims.

## 10. Non-goals

iPhone tab/focus redesign beyond lock §6; bank/hints/LLM; auth/WorkOS; new npm
deps; Dashboard/Summary/Skill/Progress/Test **internals** beyond shell chrome;
theme tokens/palette inventing.
