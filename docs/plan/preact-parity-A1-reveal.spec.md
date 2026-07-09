---
title: 'Sprint A1 — Resolve the Reveal answer control (D6+D1) · Spec'
type: spec
status: Accepted
date: 2026-07-09
owner: Rajnish Khatri
epic: A
derives_from:
  - docs/plan/preact-parity-sprint-board-A.md
  - docs/plan/preact-parity-epic-A.brainstorm.md
related:
  - docs/plan/preact-parity-A0-correct-record.spec.md   # prerequisite record correction
  - docs/plan/preact-english-coach-ui.spec.md           # FR-D5 / FR-D6 (UI) — A1 amends FR-D6
  - docs/plan/preact-english-coach-engine.spec.md       # ID-collision caveat (cite UI by path)
  - PreAct/UI-Design/English Coach - Prototype.dc.html # Reveal = submit alias
  - PreAct/UI-Design/PreACT-English-Coach-Spec.md      # interaction table + nav map
  - docs/adr/decisions.md
governs:
  - frontend/components/quiz/QuizView.tsx
  - frontend/components/quiz/QuizView.test.tsx
  - docs/plan/preact-english-coach-ui.spec.md
---

# Sprint A1 — Resolve the "Reveal answer" control (D6+D1)

> **What / why split.** This spec is the *what*. Intent debt (why Reveal is a submit
> alias, not an in-place letter reveal) lands in `docs/adr/decisions.md` — no ADR
> (no ⚠️ Ask-first trigger). Direction chosen at Stage-1 gate:
> [`preact-parity-epic-A.brainstorm.md`](preact-parity-epic-A.brainstorm.md) → **D6+D1**.

---

## 1. Goal

Stop the Quiz screen's **"Reveal answer"** control from lying. Today
`data-testid="quiz-reveal"` renders a labelled button with **no `onClick`**. After A1,
the control is an honest, low-emphasis path to Feedback that matches the prototype:
same submit path as "Submit answer", gated on a selected choice. The correct answer
letter remains off the Quiz VM (FR-D5 / Feedback owns teaching).

## 2. Context

- **Trust bug `Q-6`:** dead control — [QuizView.tsx:105-111](../../frontend/components/quiz/QuizView.tsx).
- **Prior false framing (A0):** FR-D5 vs FR-D6 "contradiction" was **refuted**. UI FR-D5
  constrains the *hint*; UI FR-D6 only required the ghost control to *exist* and was
  silent on gating. A0 corrects the record; A1 spends the design latitude FR-D6 left open.
- **Prototype truth (Stage-1 re-pose):** Reveal is **not** an in-place letter reveal.
  In [Prototype.dc.html:114,242](../../PreAct/UI-Design/English%20Coach%20-%20Prototype.dc.html)
  it shares `submit` with Submit and navigates to Feedback when a choice is selected.
  Interaction table: "low-emphasis path to the answered/feedback state"
  ([PreACT-English-Coach-Spec.md:216](../../PreAct/UI-Design/PreACT-English-Coach-Spec.md)).
- **Feedback already teaches:** UI FR-E1/E4 + [`FeedbackView.tsx`](../../frontend/components/feedback/FeedbackView.tsx)
  show the correct letter post-submit — so A1 must **not** add `answerLetter` to `QuizItemVM`.
- **Rejected board Options 1/3:** in-place `revealed` state + gated VM letter invent
  non-prototype behavior and a second answer surface. Rejected at Stage-1 (P8/P9).

**Clarify resolutions (baked in — recommended defaults accepted for tasking):**

| # | Ambiguity | Resolution |
|---|---|---|
| C1 | Disable vs silent no-op when no selection? | **Disable** (with `aria-disabled` / same `data-enabled` pattern as Submit) — more honest than prototype's silent no-op. |
| C2 | Amend FR-D6 in place vs add FR-D6a? | **Amend FR-D6 + add FR-D6a** (render + behavior split) so the UI spec matches the interaction table. |
| C3 | Same `onSubmit` prop vs new `onReveal`? | **Reuse `onSubmit`** — zero new page/reducer surface (F-R1). |
| C4 | A0 must merge before A1 code? | **A0 docs half may land in the same PR as A1's UI-spec amend**; A0's arch guard (if not yet green) stays A0's DoD. A1 code does not depend on the guard. |
| C5 | Engine-spec FR-D6 collision? | Citations always say **UI** `preact-english-coach-ui.spec.md` by path (A0 caveat). |

## 3. Functional requirements (EARS)

Failure paths first.

- **FR-1** (failure-path / trust). WHILE no choice is selected THE SYSTEM SHALL keep
  "Reveal answer" non-actionable (disabled / `pointer-events-none`, matching the Submit
  gate pattern) and SHALL NOT navigate to Feedback or expose the correct answer letter
  on the Quiz screen.
- **FR-2** (failure-path / non-reveal). THE Quiz item view-model (`QuizItemVM`) SHALL
  continue to omit the correct answer letter. Activating Reveal SHALL NOT introduce an
  in-place answer reveal on the Quiz screen.
- **FR-3.** WHEN a choice is selected AND the learner activates "Reveal answer" THE
  SYSTEM SHALL invoke the same submit path as "Submit answer" (grade → Feedback /
  reviewing phase).
- **FR-4.** THE SYSTEM SHALL render "Reveal answer" as a visually distinct, low-emphasis
  (ghost) control separate from "Get a hint" (preserves the render half of UI FR-D6).
- **FR-5** (spec fidelity — D6). WHERE [preact-english-coach-ui.spec.md](preact-english-coach-ui.spec.md)
  FR-D6 currently only mandates rendering, THE SYSTEM SHALL amend it so FR-D6 states the
  ghost control's existence **and** FR-D6a states: WHEN Reveal is activated AND a choice
  is selected THE SYSTEM SHALL follow the Submit path to Feedback; WHILE no choice is
  selected Reveal SHALL remain non-actionable.
- **FR-6.** THE SYSTEM SHALL record in `docs/adr/decisions.md` (newest-first): Reveal is a
  **gated submit alias** (prototype-aligned); in-place letter reveal and remove-the-button
  were rejected; cite UI spec by path; note engine ID-collision caveat if not already in
  the A0 entry (append to A0 entry or add A1 entry — prefer one A1 entry that references A0).
- **FR-7.** THE SYSTEM SHALL prove FR-1 and FR-3 with tests that were **seen to fail first**
  (no prior `quiz-reveal` coverage exists).

## 4. Data model / contracts

No wire / schema / trust-kernel changes.

| Surface | Change |
|---|---|
| `QuizItemVM` | **unchanged** — still omits `answerLetter` |
| `quizScreenReducer` | **unchanged** — no `revealed` / `toggle_reveal` |
| `QuizView` props | **unchanged shape** — Reveal reuses existing `onSubmit` + `selectedLetter` / `canSubmit` |
| UI spec FR-D6 / FR-D6a | **amended** (docs) |

## 5. Invariants & security boundaries

- **Frontend F-R1:** `QuizView` stays presentational — wires `onClick={onSubmit}` /
  `disabled={!submittable}`; no domain logic, no SDK.
- **T1 translators:** `quiz_item_vm` stays pure and non-revealing (FR-2).
- **Architecture invariants #1–#8:** untouched (frontend-only, no new service/node/dep).
- **No ⚠️ Ask-first:** no ADR; `decisions.md` only (FR-6).
- **G8:** adds tests; does not weaken existing assertions.

## 6. Edge cases

- **No selection + click:** control disabled — no navigation (FR-1). Do not mirror
  prototype's silent no-op (clarify C1).
- **Hint open + Reveal:** orthogonal; Reveal does not close/open hint; submit path
  already records `usedHint` via existing reducer.
- **Double-activate:** same as Submit — existing submit/reviewing transition owns this;
  A1 adds no new race surface.
- **Reviewing phase:** Reveal is only rendered in the answering `QuizView`; Feedback
  replaces it — no Reveal on Feedback.
- **Bare "FR-D6" citations:** always path-qualify to the **UI** spec (engine collision).

## 7. Non-functional requirements

- Deterministic L1 unit tests in `make check` (frontend vitest via existing suite).
- No live LLM. No new dependency. Reversible (small view + docs diff).

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `QuizView.test.tsx` — Reveal disabled when `selectedLetter === null`; click does not call `onSubmit` | L1 | yes (frontend) |
| FR-3 | `QuizView.test.tsx` — Reveal enabled when selected; click invokes `onSubmit` once | L1 | yes |
| FR-2 | Existing FR-D5 hint tests remain green; assert `QuizItemVM` still has no `answerLetter` (existing translator tests / type) | L1 | yes |
| FR-4 | Render assertion: `quiz-reveal` present with ghost styling classes (smoke) | L1 | yes |
| FR-5 | Manual / grep: UI spec contains FR-D6a wording | doc | no |
| FR-6 | Manual: `decisions.md` head shows A1 entry | doc | no |
| FR-7 | Red-first: author FR-1/FR-3 tests, paste failure, then implement | process | — |

## 9. Definition of Done

- [x] UI spec FR-D6 amended + FR-D6a added (FR-5).
- [x] `quiz-reveal` wired to `onSubmit`, disabled when `!canSubmit` (FR-1, FR-3, FR-4).
- [x] `QuizItemVM` still omits answer letter; no reducer `revealed` state (FR-2).
- [x] FR-1 and FR-3 tests authored, **seen red first**, then green (FR-7).
- [x] `decisions.md` A1 entry recorded (FR-6).
- [x] Sprint board A1 section reframed away from Options 1/3 in-place reveal.
- [x] Frontend tests + `make check` green — **actual output pasted** (implement session).
- [x] Explicit log: A1 closed the trust bug via **submit alias**, not in-place reveal.
