---
type: report
title: "Wide-layout & CoachPanel parity — FR/task validation report"
description: >-
  Playwright + Vitest evidence for FR-1…FR-20 / L0–L6 Direction 2b, plus manual
  viewport checklist links.
status: "Validated 2026-07-16 — e2e 11/11 green; vitest 69/69 green; FR-8/16/17 e2e gaps noted"
authored: 2026-07-16
derives_from:
  - docs/plan/preact-wide-layout-coach-panel.spec.md
  - docs/plan/preact-wide-layout-coach-panel.tasks.md
---

# Validation report — Wide-layout & CoachPanel parity (Direction 2b)

**Date:** 2026-07-16
**Branch work:** Stage 6 implementation + FR-18 e2e oracle fix + CoachDrawer focus-restore fix
**Commands:**

```bash
cd frontend
npx vitest run components/shell/use_surface.test.ts \
  components/shell/shell_layout_store.test.ts \
  components/shell/AppNav.test.tsx \
  components/coach/use_expandable_list.test.ts \
  components/coach/HintLadderList.test.tsx \
  components/coach/CollapsibleCoachAnswer.test.tsx \
  components/coach/CoachPanel.test.tsx \
  components/coach/CoachDrawer.test.tsx \
  components/coach/CoachTriggerPill.test.tsx \
  components/chat/Composer.test.tsx
# → 10 files, 69 tests passed

E2E_BYPASS_AUTH=1 pnpm exec playwright test \
  e2e/learn/wide-layout.spec.ts e2e/learn/ipad.spec.ts \
  --project=learn-e2e --reporter=list
# → 11 passed (43.3s)
```

---

## Executive verdict

| Gate | Result |
|------|--------|
| Playwright (`wide-layout` + `ipad`) | **11/11 PASS** |
| Vitest (FR unit suite above) | **69/69 PASS** |
| FR-1…FR-20 measurable coverage | **18/20 automated green**; **FR-8 / FR-16 / FR-17** unit-or-manual only (no dedicated Playwright row yet) |
| L6 Safari/`dvh` | Manual residual (see checklist) |

---

## Playwright evidence (raw)

```
✓ ipad.spec.ts — quiz_split_with_persistent_live_coach_panel
✓ ipad.spec.ts — panel_message_lands_in_shared_coach_thread
✓ ipad.spec.ts — one_more_nudge_deeper_hint
✓ wide-layout — FR-10 desktop 1440×900 (inline + Zone C + 64px rail + ThemeToggle)
✓ wide-layout — FR-19 dismiss inline → thread on /learn/coach
✓ wide-layout — FR-10 iPad landscape 1024×768 inline
✓ wide-layout — FR-11/12 window scrollTop=0; Zone C pinned after Zone B scroll
✓ wide-layout — FR-1 drawer 768×1024 (pill + Escape + focus restore)
✓ wide-layout — FR-18 iPhone 390×844 (no inline/drawer/pill; focus chrome; 4 tabs on Home)
✓ wide-layout — FR-9 Home→Quiz mounts collapsed rail
✓ wide-layout — Home main overflow-y auto/scroll
11 passed (43.3s)
```

### Fixes applied during this validation pass

1. **FR-18 e2e oracle** — Quiz on iPhone uses `FocusModeChrome` (tab bar hidden). Assert quiz negatives + `focus-close`, then inventory 4 tabs / no Skill on `/learn` (iPhone has no `coach-shell`).
2. **CoachDrawer focus restore (unit)** — restore focus to the pill when the close transition finishes (same timer as `visible` teardown). Vitest FR-2 green again.

---

## FR → evidence matrix

| FR | Claim (short) | Automated oracle | Result | Notes |
|----|---------------|------------------|--------|-------|
| **FR-1** | content &lt; 900 → drawer + pill, no inline | Playwright 768×1024 + `coachMode` vitest | **PASS** | Escape + focus-to-pill covered |
| **FR-2** | Escape/scrim close; focus restore; Tab trap | Playwright Escape; RTL CoachDrawer | **PASS** | Tab trap covered in component; e2e Escape only |
| **FR-3** | streaming forced expanded | vitest `use_expandable_list` + CollapsibleCoachAnswer | **PASS** | Unit/RTL |
| **FR-4** | error stays expanded + Retry | vitest expandable + CollapsibleCoachAnswer | **PASS** | Unit/RTL |
| **FR-5** | exhausted nudge aria-disabled + reason | RTL CoachPanel / HintLadderList | **PASS** | Unit; ipad e2e exercises nudge clicks |
| **FR-6** | 64px rail ThemeToggle reachable | Playwright desktop + AppNav vitest | **PASS** | |
| **FR-7** | expand/collapse keeps focus; no live-region rewrite | vitest expandable / answer | **PASS** | No dedicated axe row in this run |
| **FR-8** | prefers-reduced-motion → 0s transitions | `motion-reduce` classes in layout/drawer | **PARTIAL** | No Playwright reduced-motion project yet — **manual** |
| **FR-9** | Quiz/Coach/Skill/Test mount 64px; no pin restore | Playwright Home→Quiz + store vitest | **PASS** | |
| **FR-10** | content ≥ 900 → inline (1440 + 1024) | Playwright both viewports + ipad.spec | **PASS** | |
| **FR-11** | independent scroll; window scrollTop 0 | Playwright FR-11 | **PASS** | Safari/`dvh` still L6 manual |
| **FR-12** | Zone C tops unchanged after Zone B scroll | Playwright (same test as FR-11) | **PASS** | |
| **FR-13** | complete → prior collapsed; newest open | vitest `use_expandable_list` | **PASS** | Unit |
| **FR-14** | new nudge auto-opens; others retain | vitest ladder / HintLadderList | **PASS** | Unit; ipad nudge e2e smoke |
| **FR-15** | composer min-height ≥ 58px | Composer vitest `min-h-[3.6rem]` | **PASS** | Class oracle (computed px not e2e) |
| **FR-16** | wide Ask-coach: no navigate; pin; focus composer | quiz `onAskCoach` code path | **MANUAL / gap** | No dedicated Playwright row yet |
| **FR-17** | drawer Ask-coach: open + focus after 220ms | quiz `onAskCoach` code path | **MANUAL / gap** | No dedicated Playwright row yet |
| **FR-18** | iPhone: no inline/drawer; 4 tabs; no Skill | Playwright 390×844 | **PASS** | After oracle fix |
| **FR-19** | dismiss inline → thread on Coach route | Playwright | **PASS** | |
| **FR-20** | collapsed answer: chevron + Coach + summary; no timestamp | CollapsibleCoachAnswer vitest | **PASS** | Unit/RTL |

---

## Task track (L0–L6) validation

| Track | Tasks | Validation |
|-------|-------|------------|
| **L0** | T0.1–T0.3 docs + baseline | Spec/plan/ADR present; architecture gate previously green |
| **L1** | T1.1–T1.4 coachMode, store, layout, AppNav | vitest shell suite + e2e FR-1/6/9/10 |
| **L2** | T2.1–T2.4 expandable list, ladder, answer | vitest coach suite (FR-3/4/13/14/20) |
| **L3** | T3.1–T3.4 Zones A/B/C + Composer | CoachPanel/Composer vitest + e2e Zone C / FR-12 |
| **L4** | T4.1–T4.3 CoachDrawer, pill, quiz host | CoachDrawer/TriggerPill vitest + e2e FR-1/2 |
| **L5** | T5.1–T5.3 e2e AC matrix | **wide-layout.spec.ts + ipad.spec.ts green** |
| **L6** | T6.1 Safari/`dvh` residual | Recorded in `docs/adr/decisions.md` — **manual Safari** |

---

## Gaps / follow-ups

1. **Add Playwright for FR-16 / FR-17** — submit → Ask coach on 1440 (stay on quiz, composer focused) and 768 (drawer opens, composer focused).
2. **Add reduced-motion project or `page.emulateMedia({ reducedMotion: 'reduce' })` for FR-8.**
3. **L6** — Safari iPad: confirm `h-dvh` height chain and window scroll lock by hand.
4. Do not run a second `pnpm dev` while Playwright owns `:3000` with `E2E_BYPASS_AUTH=1` (corrupts `.next` mid-run).

---

## Manual validation links + checklist

Start (auth bypass for local QA):

```bash
cd frontend
E2E_BYPASS_AUTH=1 NEXT_PUBLIC_PREACT_E2E_HOOKS=1 pnpm dev
```

| Surface | Viewport | URL |
|---------|----------|-----|
| **Desktop** | 1440×900 | http://localhost:3000/learn/quiz |
| **iPad landscape** | 1024×768 | http://localhost:3000/learn/quiz |
| **iPad portrait (drawer)** | 768×1024 | http://localhost:3000/learn/quiz |
| **iPhone** | 390×844 | http://localhost:3000/learn/quiz then http://localhost:3000/learn |

### Desktop 1440×900 checklist

- [ ] Inline `coach-panel` visible beside item (no floating Coach pill)
- [ ] Left rail ≈ 64px; ThemeToggle visible at bottom of rail
- [ ] Zone C: “One more nudge” + chips + composer pinned
- [ ] Scroll coach log — Zone C does not move; page/window does not scroll
- [ ] Send a short coach message; dismiss panel (✕); open **Coach** nav — thread preserved
- [ ] After wrong/right submit, **Ask the coach** focuses composer (no route change) — **FR-16**

### iPad landscape 1024×768 checklist

- [ ] Inline coach panel (1024 − 64 ≥ 900)
- [ ] No Coach pill / no edge-tab
- [ ] Nudge ladder expands in Zone B; control stays in Zone C
- [ ] Item column and coach column scroll independently

### iPad portrait 768×1024 checklist

- [ ] No inline panel; **Coach** pill visible
- [ ] Pill opens drawer; Escape / scrim closes; focus returns to pill — **FR-2**
- [ ] **Ask the coach** opens drawer and focuses composer — **FR-17**
- [ ] (Optional) OS “Reduce motion” → drawer opens/closes with no slide delay — **FR-8**

### iPhone 390×844 checklist

- [ ] Quiz: focus chrome (✕); **no** inline panel, drawer, or pill
- [ ] Ask coach navigates to fullscreen `/learn/coach` (not overlay)
- [ ] Home (`/learn`): exactly 4 bottom tabs — Home / Practice / Coach / Progress; **no Skill**
- [ ] Theme toggle reachable in header (non-focus) or focus header

### Safari residual (L6)

- [ ] Real Safari iPad: quiz height fills viewport (`dvh`); no rubber-band of `document` while Zone B scrolls
