---
title: 'CoachPanel real-estate + Zone-B scroll — Spec'
type: spec
status: Draft
date: 2026-07-16
owner: Rajnish Khatri
related:
  - docs/plan/preact-wide-layout-coach-panel.spec.md
  - docs/plan/preact-wide-layout-coach-panel.plan.md
  - docs/plan/preact-wide-layout-coach-panel.tasks.md
  - docs/adr/0036-wide-layout-coach-panel-parity.md
  - docs/width-design-ui-session-artifacts/PreACT-English-Coach-v2-Wide-Layout-CoachPanel-Implementation-Spec.md
governs:
  - frontend/components/coach/CoachPanel.tsx
  - frontend/components/coach/CoachView.tsx
  - frontend/components/coach/CoachChrome.tsx
  - frontend/app/(coach)/learn/quiz/page.tsx
  - frontend/e2e/learn/wide-layout.spec.ts
---

# CoachPanel real-estate + Zone-B scroll

> **What / why split.** This spec is the *what* for residual UX gaps found in the
> W9 iPad device pass. Parent [wide-layout spec](preact-wide-layout-coach-panel.spec.md)
> FR-9/FR-10 already require dual-column scroll + pinned Zone C; this delta makes
> those criteria *true for revealed nudges* and raises the coach-column width
> floor so chips/modes are usable. Intent debt for any width-token change vs
> design F3 lands in `docs/adr/decisions.md` (no new abstraction → no ADR unless
> clarify invents a shared layout constant module that fails G1).

**Status:** Draft — 2026-07-16 · clarify OPEN · plan/tasks deferred until Accept.
**Owner:** Rajnish Khatri
**Related:** parent [wide-layout spec](preact-wide-layout-coach-panel.spec.md) ·
[ADR-0036](../adr/0036-wide-layout-coach-panel-parity.md) · W9 device screenshots
(coach column cramped; Nudge 2 clipped by Zone C).

---

## 1. Goal

On wide Quiz (`ipad` / `desktop`), the live coach column has enough horizontal
room for chrome + chips, and the middle band (revealed nudges + coach answers)
scrolls inside Zone B so Zone C never clips content.

## 2. Context

### 2.1 Device evidence (2026-07-16 iPad pass)

| Symptom | Evidence |
|---|---|
| Coach real-estate too narrow | Modes tab ("answer deep-dive") clipped on the left; chip "Give me a similar item" truncated on the right |
| Middle portion not scrollable | Nudge 2 cut off by the Zone C divider; no scrollbar / no way to reveal remainder |
| Coach answers not usable | Same Zone B starvation — when nudges consume height, the log region collapses and answers cannot scroll into view |

### 2.2 Code evidence (grounded)

| Seam | Current behavior | Gap vs parent FR-9/10 |
|---|---|---|
| `CoachPanel.tsx` width | Desktop: `clamp(340px, 32%, 460px)`; iPad: `w-80` (320px) | Design F3; screenshots show 320–340px floor is insufficient for stacked chrome + chip labels |
| `CoachPanel.tsx` Zone B | Nudges rendered as `shrink-0` **siblings above** `CoachView`; Zone B is `overflow-hidden` | Nudges are **outside** `data-testid="coach-log"` (`overflow-y-auto`) → clipped, not scrolled |
| Drawer host (`quiz/page.tsx`) | `SheetContent` `max-w-md` (448px) | Mid-width drawer inherits the same cramped width |

Parent FR-9/10 remain the governing scroll contract; this delta closes the
implementation hole that left revealed nudges outside the scrollport.

### 2.3 Clarify (OPEN)

| # | Ambiguity | Recommended | Status |
|---|---|---|---|
| C1 | Coach column width target (inline + drawer) | **Option A** — unify wide inline to `clamp(400px, 40%, 560px)` on both `ipad` and `desktop` (drop `w-80`); drawer `max-w-lg` (512px). Reject equal 50/50 split (starves item stem). Reject leaving `w-80`. | **OPEN** |
| C2 | Single vs dual scroll inside Zone B | **Option A** — one scrollport: revealed nudges + coach turns share Zone B / `coach-log` scroll; Zone A + Zone C stay fixed. Reject separate nudge-only scroller (two nested scroll areas confuse touch). | **OPEN** |
| C3 | Expanded long coach answer overflow | **Option A** — whole answer scrolls with Zone B (no per-bubble max-height). Reject capping each bubble (hides content behind a second scroll). | **OPEN** |
| C4 | Scope vs parent W9 | **In:** width + Zone-B scroll for nudges/answers. **Out:** Safari/`dvh` toolbar sign-off (stays on parent W9 checklist); icon-rail / Feedback bridge / collapsible auto-collapse (parent, already landed). | **OPEN** |

---

## 3. Functional requirements (EARS)

Failure / edge paths first.

- **FR-1.** IF revealed nudges plus coach turns exceed Zone B height THEN THE
  SYSTEM SHALL scroll that content inside Zone B and SHALL NOT clip it behind
  Zone C (composer / chips / "One more nudge").
- **FR-2.** IF the coach column is shown inline on a wide Quiz surface THEN THE
  SYSTEM SHALL size it to at least the clarified minimum width (C1) and SHALL
  NOT use the `w-80` (320px) fixed width on `ipad`.
- **FR-3.** IF chip or mode labels exceed the panel's inner width THEN THE
  SYSTEM SHALL keep them reachable via horizontal scroll within their row and
  SHALL NOT wrap them into extra vertical rows that steal Zone B height.
- **FR-4.** WHILE Zone B is scrolling THEN THE SYSTEM SHALL keep Zone A (chrome)
  and Zone C (nudge control + chips + composer) pinned and fully visible
  (inherits parent FR-10).
- **FR-5.** WHEN the learner expands a prior coach answer whose body is taller
  than the remaining Zone B viewport THEN THE SYSTEM SHALL allow that content
  to be reached by scrolling Zone B (C3); the browser window SHALL NOT scroll
  (inherits parent FR-9).
- **FR-6.** IF the coach panel is presented as the overlay drawer THEN THE
  SYSTEM SHALL apply the clarified drawer max-width (C1) so the same scroll
  contract holds inside the Sheet.
- **FR-7.** THE SYSTEM SHALL keep the quiz item column as `flex-1 min-w-0` and
  SHALL NEVER stack the coach below the item (inherits parent FR-1/8).

---

## 4. Data model / contracts

None. Client CSS / DOM structure only. No new wire types, ports, or npm deps.

Optional (plan-time, not required by FRs): a named width token constant next to
`SPLIT_MIN_CONTENT_WIDTH` in `use_surface.ts` — only if it avoids magic numbers
in two call sites; otherwise inline `clamp(...)` in `CoachPanel` is enough (G1:
no new module).

## 5. Invariants & security boundaries

- Frontend Ring only — no `orchestration/` / `services/` / `trust/` changes.
- No new graph node, horizontal service, or trust type → no ADR ratchet unless
  C1 invents a shared abstraction that fails G1 (then decisions.md or ADR).
- Parent Architecture Invariants #1–#8 untouched.

## 6. Edge cases

- Zero revealed nudges → Zone B is turns/opener only; still scrolls when tall.
- Many nudges (full ladder) + long expanded answer → single Zone B scroll reaches
  both; Zone C never leaves the viewport.
- Streaming turn → stays expanded (parent FR-3); scroll position may follow the
  newest content (existing CoachView behavior; do not regress).
- `prefers-reduced-motion` → width/collapse transitions remain instant (parent
  FR-16); scroll behavior unchanged.
- Drawer open at mid-width → same Zone B contract; dismiss/edge-tab unchanged.

## 7. Non-functional requirements

- L1/L2 unit + L4 Playwright only; no live LLM in CI.
- Touch: Zone B uses `overscroll-contain` so nested scroll does not chain to the
  page (parent height-chain).
- Reversibility: CSS/class changes only; one-PR revert safe.

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | Playwright: reveal ≥2 nudges → Zone B/`coach-log` `scrollHeight > clientHeight`; Nudge N not covered by Zone C bounding box after scroll | L4 | on-demand e2e |
| FR-2 | Component/unit: `coach-panel` computed/min width ≥ clarified floor on `ipad` and `desktop`; assert no `w-80` class on wide inline | L1/L2 | yes |
| FR-3 | Component: stacked modes/chips use nowrap + overflow-x (regression of W9 preflight) | L2 | yes |
| FR-4 | Playwright/component: Zone C `getBoundingClientRect` intersects viewport while Zone B scrolled to end | L2/L4 | unit yes; e2e on-demand |
| FR-5 | Playwright: inject tall expanded answer → Zone B scrolls; `window.scrollY === 0` | L4 | on-demand |
| FR-6 | Component/e2e: drawer `SheetContent` max-width matches C1 | L2/L4 | unit yes |
| FR-7 | Existing wide-layout split e2e (no stack) remains green | L4 | on-demand |

## 9. Definition of Done

- [ ] Clarify C1–C4 closed; this spec status → Accepted.
- [ ] Plan + tasks authored; Stage-4 grounding green.
- [ ] All FR-1…FR-7 implemented; each has a passing test that was *seen to fail first*.
- [ ] Parent W9 Safari/`dvh` checklist still tracked separately (out of scope here).
- [ ] Actual command output pasted for verification claims.
- [ ] `decisions.md` note if C1 changes design F3 width tokens.

---

## 10. Out of scope

- Parent W9 manual Safari toolbar / focus-trap sign-off.
- Changing the 900px content-width degrade ladder or icon-rail behavior.
- Equal-width item/coach split, or coach-below-item stacking.
- Backend / prompt / ladder content changes.
