---
title: 'Sprint A1 — Resolve Reveal answer (D6+D1) · Plan + Tasks'
type: plan
status: Accepted
date: 2026-07-09
owner: Rajnish Khatri
epic: A
implements: docs/plan/preact-parity-A1-reveal.spec.md
related:
  - docs/plan/preact-parity-epic-A.brainstorm.md
  - docs/plan/preact-parity-sprint-board-A.md
  - docs/plan/preact-parity-A0-correct-record.spec.md
  - docs/adr/decisions.md
---

# Sprint A1 — Plan + Tasks

Implements [preact-parity-A1-reveal.spec.md](preact-parity-A1-reveal.spec.md).
Direction **D6+D1** (clarify UI FR-D6, then wire Reveal as gated submit alias).
No `⚠️ Ask first` → **no ADR** (`decisions.md` only, FR-6).

---

## 1. Architecture / approach

```
QuizView (answering)
  ├─ Get a hint  → onToggleHint  (unchanged)
  ├─ Reveal answer → onSubmit when canSubmit(selectedLetter); else disabled
  └─ Submit answer → onSubmit when canSubmit (unchanged)
         ↓
   page.tsx onSubmit → grade → reviewing / Feedback
```

No new reducer action, no `answerLetter` on `QuizItemVM`, no new props on `QuizView`
beyond reusing `onSubmit` + existing `selectedLetter` / `canSubmit` helper already
imported in the view.

**Docs half first (D6):** amend [preact-english-coach-ui.spec.md](preact-english-coach-ui.spec.md)
FR-D6 + add FR-D6a so implementation has an authoritative FR to cite. Then TDD the view.

## 2. File-level touchpoints

| # | File | Change | FR |
|---|---|---|---|
| T1 | [docs/plan/preact-english-coach-ui.spec.md](preact-english-coach-ui.spec.md) | Amend FR-D6; add FR-D6a (gated submit alias) | FR-5 |
| T2 | [frontend/components/quiz/QuizView.test.tsx](../../frontend/components/quiz/QuizView.test.tsx) | New describe for `quiz-reveal` — FR-1 + FR-3, red first | FR-1, FR-3, FR-7 |
| T3 | [frontend/components/quiz/QuizView.tsx](../../frontend/components/quiz/QuizView.tsx) | Wire `onClick={onSubmit}`, `disabled={!submittable}`, `data-enabled`, comment cites UI FR-D6/D6a | FR-1, FR-3, FR-4 |
| T4 | [docs/adr/decisions.md](../adr/decisions.md) | Newest-first A1 entry (submit alias; rejected in-place / remove) | FR-6 |
| T5 | [docs/plan/preact-parity-sprint-board-A.md](preact-parity-sprint-board-A.md) | Reframe A1 Options → D6+D1; strike Options 1/3 as lead | board sync |
| T6 | (optional same PR) A0 remainder: epics + VISUAL + A0 `decisions.md` bits | Per [A0 plan](preact-parity-A0-correct-record.plan.md) | A0 |

**Explicitly untouched:** `quiz_item_vm.ts`, `quiz_screen_reducer.ts`,
`quiz/page.tsx` (already passes `onSubmit`), Feedback stack.

## 3. Migration / sequencing

1. **A1-0** — amend UI spec (D6) so code comments have a real FR to cite.
2. **A1-1** — write Reveal tests → **must fail** (button has no handler today). Paste red.
3. **A1-2** — wire QuizView → tests green.
4. **A1-3** — `decisions.md` + board sync.
5. **A1-4** — `make check` / frontend test gate; paste green.

A0 remainder (T6) may land in the same PR or immediately prior; it does not block A1-1/A1-2.

## 4. Constitution check

- Invariants #1–#8: frontend-only presentational wire-up.
- F-R1 / T1: view presentational; VM unchanged.
- No Ask-first → no ADR.
- G8: adds tests only.

---

## 5. Task list (atomic, 1:1 to EARS)

### Task A1-0 — Clarify UI FR-D6 / add FR-D6a  `[FR-5]`
- **Do:** In [preact-english-coach-ui.spec.md](preact-english-coach-ui.spec.md) §D:
  - Keep FR-D6 as the **render** requirement (ghost control separate from hint).
  - Add **FR-D6a:** WHEN "Reveal answer" is activated AND a choice is selected THE
    SYSTEM SHALL follow the same path as "Submit answer" (route to Feedback with the
    selected letter). WHILE no choice is selected THE SYSTEM SHALL keep Reveal
    non-actionable.
  - Optionally one-line note under FR-D6 pointing at the prototype interaction table.
- **Verify:** grep shows `FR-D6a` and "Submit" / "non-actionable" wording present.
- **Pass/fail:** UI spec encodes D6+D1; no engine-spec edit.

### Task A1-1 — Author Reveal tests, seen red first  `[FR-1, FR-3, FR-7]`
- **Do:** In [QuizView.test.tsx](../../frontend/components/quiz/QuizView.test.tsx), add
  `describe("QuizView — Reveal answer (UI FR-D6 / FR-D6a)")`:
  1. `selectedLetter: null` → `quiz-reveal` has `disabled` (or `data-enabled="false"`);
     spy `onSubmit` not called on click attempt.
  2. `selectedLetter: "B"` → Reveal enabled; click calls `onSubmit` once.
  Mirror existing Submit / hint test style (`:93-119`).
- **Verify (red):** `cd frontend && npx vitest run components/quiz/QuizView.test.tsx`
  **FAILS** on current inert button. **Paste the failure.**
- **Pass/fail:** tests exist, non-vacuous (fail now).

### Task A1-2 — Wire `quiz-reveal` to gated submit  `[FR-1, FR-3, FR-4]`
- **Do:** In [QuizView.tsx](../../frontend/components/quiz/QuizView.tsx):
  - `onClick={onSubmit}`
  - `disabled={!submittable}` + `data-enabled={submittable ? "true" : "false"}`
  - disabled styling consistent with Submit (`opacity` / `pointer-events-none`)
  - Comment cites **UI** FR-D6 / FR-D6a (path-qualified); state gating decided in A1;
    no answer letter on this screen.
- **Verify:** A1-1 tests green; existing hint/submit tests still green.
- **Pass/fail:** FR-1 + FR-3 green; FR-2 holds (no VM change).

### Task A1-3 — Record decision + sync board  `[FR-6]`
- **Do:**
  1. Prepend `decisions.md` entry: Reveal = gated submit alias (prototype-aligned);
     rejected in-place letter reveal (board Options 1/3) and remove-button (D2) for
     this sprint; cite UI spec path; reference A0 FR-compatibility finding.
  2. Update sprint board A1 section: lead = D6+D1; Options 1/3 marked rejected /
     superseded by Stage-1 re-pose.
- **Verify:** `head -25 docs/adr/decisions.md` shows entry; board no longer recommends
  in-place VM letter as lead.
- **Pass/fail:** entry + board sync present.

### Task A1-4 — Green the gate  `[DoD]`
- **Do:** run frontend QuizView tests + `make check` (or the frontend subset the
  project uses in CI for this package).
- **Verify (pasted):** vitest green; `make check` green; architecture tests green.
- **Log line:** "A1 closed Q-6 via Reveal→submit alias; QuizItemVM still non-revealing."

---

## 6. Parallelization

- **A1-0 before A1-2** (comment/FR citation).
- **A1-1 before A1-2** (red-first).
- **A1-3** independent of A1-1/A1-2 (docs) — can draft in parallel, land after wire.
- **A1-4** barrier.
- **A2 (D3)** fully parallel — different screens; separate PR preferred.

## 7. What is explicitly NOT in A1

- In-place answer letter on Quiz / `revealed` reducer state (rejected Options 1/3).
- Removing the button (D2).
- Class-level dead-control ratchet (D5).
- A2 Summary time triage (D3) / `"<1 min"` copy (D7).
- A0 arch guard implementation (owned by A0 plan) — only optional docs co-landing.

---

## 8. Stage-4 Analyze (spec ↔ plan ↔ tasks ↔ constitution)

Cross-artifact check before implementation. Grounding probe: 2026-07-09.

| Check | Result |
|---|---|
| Every FR has a task | **OK** — FR-1/3/7→A1-1+A1-2; FR-2→untouched surfaces + A1-2 verify; FR-4→A1-2; FR-5→A1-0; FR-6→A1-3 |
| Every plan path exists | **OK** — QuizView.tsx/test.tsx, quiz_item_vm.ts (`canSubmit` @53), page.tsx, ui.spec.md, decisions.md, Prototype.dc.html, A0/A1 artifacts |
| Plan cites non-existent API | **OK** — reuses `onSubmit` / `canSubmit`; no `toggle_reveal` |
| New pyproject / npm dep | **OK** — none |
| Ask-first / ADR | **OK** — none; `decisions.md` only |
| Invariant stress | **OK** — F-R1 presentational wire; T1 VM unchanged |
| Zero-coverage FR | **OK** — none |
| Board Options 1/3 still lead? | **FIXED this pass** — board A1 section rewritten to D6+D1 |
| A0 prerequisite | **NOTE** — A0 docs remainder still open; does not block A1-1/A1-2; may co-land |
| Baseline green before impl | **DONE** — implement session: QuizView 12/12; `make check` 5277 passed; arch tests green |

**CRITICAL:** none. **A1 implement closed** — Q-6 via Reveal→submit alias; `QuizItemVM` still non-revealing. Next: Stage 7 **code-review**.
