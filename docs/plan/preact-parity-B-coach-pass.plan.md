---
title: 'Epic B — Coach full pass (B1.5 + B2 + B3) · Plan + Tasks'
type: plan
status: Accepted
date: 2026-07-09
owner: Rajnish Khatri
epic: B
implements: docs/plan/preact-parity-B-coach-pass.spec.md
related:
  - docs/plan/preact-parity-sprint-board-B.md
  - docs/plan/preact-parity-epic-B.brainstorm.md
  - docs/plan/preact-parity-B1-coach-chrome.spec.md
  - docs/adr/0025-coach-surface-vm.md
  - docs/adr/0012-subject-coach-context-contract-hint-ladder.md
  - docs/adr/decisions.md
  - Eng-coach-ui-design/PreACT-English-Coach-Spec.md
---

# Epic B — Coach full pass · Plan + Tasks

Implements [preact-parity-B-coach-pass.spec.md](preact-parity-B-coach-pass.spec.md)
(**Accepted** 2026-07-09). Clarify C1–C5 locked. Tracks: **B1.5 → B2 → B3**.

**No new numbered ADR expected** — pin extends existing FR-J3 `coach_thread_store`
(C1); wire shape already in design §4.1 / ADR-0012. Small choices already in
`decisions.md` (C1a, C3, C4/C5).

**Integration premise:** B1 chrome slots + stream stack exist. This pass closes
prototype layout, Feedback bridge + pin, and client `coach_context` assembly.

---

## 1. Architecture / approach

```
Feedback (desktop)                    Quiz iPad CoachPanel
  Ask the coach ──setCoachPin──┐         setCoachPin(live item)
  green-span recap (F-4)       │              │
                               ▼              ▼
                     coach_thread_store { turns, busy, pin }
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
   CoachChrome (rail/strip)   CoachView          sendCoachAsk
   layout by surface          (+ chips near      → uiInputToAgentRequest
   (desktop rail /             composer)           + coach_context (§4.2)
    iPad header-strip /
    panel stacked)
```

| Track | Concern | Rule |
|---|---|---|
| **B1.5** | Layout | Desktop: left rail / right chat. iPad standalone: header-strip. Panel: stacked. Chips leave rail → composer column (FR-1…3). Header Back/Wrap-up (C2). |
| **B2** | Pin + Feedback | `setCoachPin` from Ask-the-coach; chrome reads store pin; `FeedbackVM` recap from `context_html` `<u>`→success (C5). |
| **B3** | Wire + opener | Pin → assemble `coach_context` (ids + Question + optional misses/mastery); no `window`; opener only if pin+misses+empty (C4). |

---

## 2. File-level touchpoints

### B1.5 — Layout + header

| # | File | Change | FR |
|---|---|---|---|
| L1 | `CoachChrome.tsx` (+ test) | Split **rail region** vs **chips**; props/layout variants: `layout: "rail" \| "strip" \| "stacked"` (or host composition). Chips optional render slot / omit when host places them. | FR-1,3 |
| L2 | `CoachView.tsx` (+ test) | Accept optional chips above composer (or sibling slot). | FR-3 |
| L3 | `coach/page.tsx` | Desktop two-column; header Back + Wrap-up; compose chrome+view. | FR-2,3 |
| L4 | `CoachPanel.tsx` | `layout="stacked"`; chips with composer path; no desktop rail. | FR-1 |

### B2 — Pin + Feedback

| # | File | Change | FR |
|---|---|---|---|
| P1 | `coach_thread_store.ts` (+ test) | Add `pin`; `setCoachPin`; `resetCoachThread` clears pin. | FR-4,5,6 |
| P2 | `coach/page.tsx` + Panel | Read pin from store → surface VM; Panel keeps writing pin for live item. | FR-6 |
| P3 | `feedback_vm.ts` (+ test) | Recap fields from `context_html` (C5). | FR-7 |
| P4 | `FeedbackView.tsx` (+ test) | Render recap; optional `onAskCoach` action. | FR-5,7 |
| P5 | `quiz/page.tsx` | Desktop Ask-the-coach → `setCoachPin` + `router.push(/learn/coach)`; keep Next/Finish. | FR-5,8 |

### B3 — Wire context + opener

| # | File | Change | FR |
|---|---|---|---|
| W1 | `ui_input_to_agent_request.ts` (+ test) | Optional `coach_context` on `input`. | FR-10 |
| W2 | New T1 `assemble_coach_context.ts` (+ test) — or fold into use_coach helper | pin + Question + misses + mastery → wire shape §4.2; omit dishonest fields. | FR-9,10 |
| W3 | `use_coach.ts` (+ test) | On ask with pin: load question/misses/mastery; attach context; advisory mode. | FR-10,11 |
| W4 | Opener helper + page/Panel | Once when pin+misses+empty transcript (C4). | FR-12 |
| W5 | Mocked e2e / L1 body assert | Prove `coach_context` on ask when pinned. | FR-13 |

**Untouched contracts:** BFF sanitizer strip/mode rules; ADR-0012 taxonomy; Python
formatter may ignore aggregate/mastery until a later prompt pass (wire still ships).

---

## 3. Migration / sequencing

1. **BP-0** — Spec Accepted status + board umbrella links (docs only).
2. **BP-1.5** — Layout + header (L1–L4) — red-first where new structure.
3. **BP-2** — Store pin + Feedback bridge + recap (P1–P5).
4. **BP-3** — Wire assembly + opener + proof (W1–W5).
5. **BP-4** — Green gate (`make check` + arch); board exit checkboxes; paste evidence.

Tracks are independently mergeable; prefer one PR per track if review load is high.

---

## 4. Constitution check

- Invariants #1–#8: frontend-only; no new service / graph node / pyproject dep.
- F-R1 / T1 / F-R2: views presentational; assemblers pure; SDK in adapters.
- ADR-0012: client mode advisory; BFF overwrite unchanged (FR-11).
- AP-6: no fabricated misses/window/mastery/opener (FR-4,9,12).
- G1: store extension ≠ new abstraction (C1 recorded); no new ADR unless analyze finds one.
- G8: add tests; do not weaken Feedback/coach stream asserts.

---

## 5. Task list (atomic, 1:1 to EARS)

### Task BP-0 — Docs sync  `[meta]`
- **Do:** Spec status Accepted (done at gate); point board umbrella + plan path;
  ensure C1–C5 / C1a already in `decisions.md`.
- **Verify:** Spec frontmatter `status: Accepted`; board links
  `preact-parity-B-coach-pass.spec.md` + `.plan.md`.
- **Pass/fail:** Docs consistent; no code.

### Task BP-1.5a — CoachChrome layout variants (red first)  `[FR-1, FR-3]`
- **Do:** Tests for `layout="rail"|"strip"|"stacked"`; chips renderable separately
  (prop `showChips?: boolean` default true, or `chipsSlot`). Implement so desktop rail
  omits chips when page places them by composer.
- **Verify:** vitest structure/testid; Panel stacked still has chrome without left-rail
  column class.
- **Pass/fail:** FR-1/3 structure green after seen-red.

### Task BP-1.5b — Coach page two-column + header  `[FR-2, FR-3]`
- **Do:** `/learn/coach` desktop: header Back (`router.back()` → fallback `/learn/quiz`)
  + Wrap up (`/learn/summary`, `?session=` if known); left `CoachChrome layout=rail`
  (no chips); right `CoachView` + chips. iPad width: prefer strip (media or
  `layout=strip`).
- **Verify:** L1/jsdom or RTL for Back/Wrap-up testids; rail+chat columns present.
- **Pass/fail:** FR-2/3.

### Task BP-1.5c — CoachPanel stacked + chips placement  `[FR-1]`
- **Do:** Panel uses stacked chrome; chips with composer (not duplicating rail chips if
  chrome `showChips=false`).
- **Verify:** existing Panel tests + chip→onAsk still hold.
- **Pass/fail:** FR-1; no quiz-column regression.

### Task BP-2a — Store pin API (red first)  `[FR-4, FR-5, FR-6]`
- **Do:** `pin` on `CoachThreadState`; `setCoachPin`; reset clears pin; tests.
- **Verify:** store unit tests.
- **Pass/fail:** C1/C1a behavior.

### Task BP-2b — Wire pin into chrome hosts  `[FR-4, FR-6]`
- **Do:** Coach page + Panel subscribe to store pin → `toCoachSurfaceVM`; Panel
  `setCoachPin` on item change; cold open pin null → absent lines.
- **Verify:** page/Panel tests.
- **Pass/fail:** FR-4/6.

### Task BP-2c — Feedback recap VM + view (red first)  `[FR-7]`
- **Do:** `toFeedbackVM` builds recap from `context_html`; `<u>` → success markup;
  no `<u>` → plain. `FeedbackView` renders `data-testid="feedback-recap"`.
- **Verify:** feedback_vm + FeedbackView tests.
- **Pass/fail:** FR-7 / C5.

### Task BP-2d — Desktop Ask-the-coach  `[FR-5, FR-8]`
- **Do:** Quiz reviewing actions: Ask the coach → `setCoachPin({…askCoachContext,
  label})` + navigate `/learn/coach`; Next/Finish unchanged; iPad panel unregressed.
- **Verify:** quiz page / Feedback action tests.
- **Pass/fail:** FR-5/8.

### Task BP-3a — `uiInputToAgentRequest` + assemble (red first)  `[FR-9, FR-10]`
- **Do:** Optional `coach_context` on input; pure assembler from pin+question+misses+
  mastery per §4.2 (omit window; omit empty optionals).
- **Verify:** translator unit tests (no pin → no context; pin+miss → aggregate; no fake
  window; mastery when SkillState present).
- **Pass/fail:** FR-9/10.

### Task BP-3b — `sendCoachAsk` attaches context  `[FR-10, FR-11]`
- **Do:** When store pin set, load Question + misses + mastery via engine ports;
  advisory mode; attach assembled context. Sanitizer tests remain green (mode overwrite).
- **Verify:** use_coach / send path tests with fake runtime capturing body.
- **Pass/fail:** FR-10/11.

### Task BP-3c — Honest opener (C4)  `[FR-12]`
- **Do:** If pin + real misses + empty turns → one coach-side opener bubble (store or
  view seed); never re-seed; never invent window.
- **Verify:** unit test for gate conditions.
- **Pass/fail:** FR-12.

### Task BP-3d — Proof + green gate  `[FR-13, DoD]`
- **Do:** Mocked e2e or L1 body assert; `make check` + `pytest tests/architecture/ -q`;
  update board exit checkboxes; paste evidence.
- **Verify:** evidence in implement log / PR.
- **Pass/fail:** DoD §9.

---

## 6. Stage-4 analyze (pre-implement)

### 6.1 Spec ↔ plan ↔ tasks coverage

| FR | Task(s) | Covered? |
|----|---------|----------|
| FR-1 | BP-1.5a, BP-1.5c | yes |
| FR-2 | BP-1.5b | yes |
| FR-3 | BP-1.5a, BP-1.5b | yes |
| FR-4 | BP-2a, BP-2b | yes |
| FR-5 | BP-2a, BP-2d | yes |
| FR-6 | BP-2a, BP-2b | yes |
| FR-7 | BP-2c | yes |
| FR-8 | BP-2d | yes |
| FR-9 | BP-3a | yes |
| FR-10 | BP-3a, BP-3b | yes |
| FR-11 | BP-3b (+ existing sanitizer) | yes |
| FR-12 | BP-3c | yes |
| FR-13 | BP-3d | yes |
| FR-14 | inherited B1 (no change task) | yes |

### 6.2 Grounding (paths exist)

| Path | Status |
|---|---|
| `frontend/components/coach/coach_thread_store.ts` | exists — extend |
| `frontend/components/coach/CoachChrome.tsx` | exists — layout variants |
| `frontend/components/coach/CoachView.tsx` | exists — chips slot |
| `frontend/app/(coach)/learn/coach/page.tsx` | exists — compose |
| `frontend/app/(coach)/learn/quiz/page.tsx` | exists — Ask-the-coach action |
| `frontend/components/feedback/use_feedback.ts` | exists — `askCoachContext` |
| `frontend/lib/translators/feedback_vm.ts` | exists — add recap |
| `frontend/lib/translators/ui_input_to_agent_request.ts` | exists — optional context |
| `frontend/lib/ports/engine/learner_read_repo.ts` | exists — `listSkillState` → mastery |
| `frontend/lib/translators/coach_context_sanitizer.ts` | exists — unchanged |
| `frontend/components/coach/use_coach_surface.ts` | exists — reuse misses |
| New `assemble_coach_context.ts` | **to create** (T1) |

### 6.3 Constitution / Ask-first

- No pyproject / trust / orchestration / new horizontal service.
- G1: store pin field — **not** a new abstraction (C1); assembler is a pure T1 helper
  sibling to existing translators (same pattern as B1 surface VM — if treated as new
  named abstraction, fold into `use_coach` private helper **or** one-line
  `decisions.md` note; prefer private/pure module without numbered ADR).
- CRITICAL blockers: **none** found.

### 6.4 Baseline

Run before implement: `make check` + `pytest tests/architecture/ -q` (must be green
from B1). Re-confirm at BP-3d.

---

## 7. Human gates

1. **Spec → plan:** clarified spec Accepted (2026-07-09).
2. **Plan → tasks:** Accepted 2026-07-09 — **sdd-implement** in progress (BP-1.5 → BP-2 → BP-3).
