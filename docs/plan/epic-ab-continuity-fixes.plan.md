---
title: 'Epic A/B continuity fixes — Plan (FLAG-1/4/6 + Reveal polish)'
type: plan
status: Approved — 2026-07-10
date: 2026-07-10
owner: Rajnish Khatri
implements: docs/plan/epic-ab-continuity-fixes.spec.md
related:
  - docs/plan/epic-a-b-manual-validation-report.md
  - docs/plan/preact-parity-sprint-board-C.md
  - docs/adr/0011-subject-coach-engine-learner-read-port.md
  - frontend/e2e/learn/validate_epic_ab.spec.ts
---

# Epic A/B continuity fixes — Plan

Implements [epic-ab-continuity-fixes.spec.md](epic-ab-continuity-fixes.spec.md)
(**Approved** 2026-07-10). Clarify C1/C4/C5 locked; C2/C3 withdrawn (FLAG-5 → Epic C0).

**⚠️ Ask first:** none — enlarge existing `quiz_session_store` (G1: not a new abstraction).
Small choices → `docs/adr/decisions.md` if needed (e.g. resume defaults to `answering`).

**Out of scope:** FLAG-5 Wrap-up, A0, opener skill-name copy.

---

## 1. Architecture / approach

```
Quiz live loop                          Coach ← Back
  │                                       │
  │ setActiveQuiz({                       │ router.back() → remount /learn/quiz
  │   sessionId, questionId,              │
  │   position, score, phase? })          ▼
  ▼                               readActiveQuiz()?
quiz_session_store ──────────────────► yes: sessionRepo.get + questionRepo.get
  (existing mastery snapshot           + restore reducer (no openSession)
   + NEW active pointer)               no:  openSession (today)
```

| Concern | Rule |
|---|---|
| **Active pointer** | Module singleton on `quiz_session_store`. Written whenever Quiz has a live item (answering/reviewing). Cleared on Finish (`closeSession`). Retained across unmount (Coach nav). |
| **Resume** | Mount effect: IF pointer AND `sessionRepo.get(id)` non-null AND `questionRepo.get(questionId)` non-null THEN set session + dispatch restore into `answering` (default) with stashed score; ELSE clear stale pointer + `openSession`. |
| **Score** | Spec minimum is `{sessionId, questionId, position}`; plan **also stashes `{correct, total}`** so resume does not fabricate `0/0` (honest continuity). |
| **FLAG-1** | Add `pin?.questionId` to miss-count `useEffect` deps in `coach/page.tsx` **and** `CoachPanel.tsx`. |
| **FLAG-6** | Relabel Summary tile only — no math change. |
| **Reveal polish** | Enabled → `text-fg` (or accent); disabled stays muted + opacity. |
| **FLAG-5** | Untouched. C0 should later read `readActiveQuiz()?.sessionId` (note in store comment). |

No new ports, routes, npm deps, or trust types.

---

## 2. File-level touchpoints

| # | File | Change | FR |
|---|---|---|---|
| P1 | `frontend/components/quiz/quiz_session_store.ts` (+ `.test.ts`) | `ActiveQuizPointer` + `setActiveQuiz` / `readActiveQuiz` / `clearActiveQuiz`; isolate in `afterEach` | FR-1, FR-2 |
| P2 | `frontend/components/quiz/quiz_screen_reducer.ts` (+ test) | Add restore action (e.g. `resume_item`) → `answering` with item + score; optional reviewing later | FR-3, FR-4 |
| P3 | `frontend/components/quiz/use_quiz.ts` (or page-local) | Optional thin `resumeQuizSession(ports, sessionId, questionId)` → `{ session, item }` via `get` + `questionRepo.get` + `hintRepo.list`; null session → failure path | FR-3, FR-4 |
| P4 | `frontend/app/(coach)/learn/quiz/page.tsx` | Mount: resume-or-open; on item/phase: `setActiveQuiz`; Finish: `clearActiveQuiz` after close | FR-1…FR-4 |
| P5 | `frontend/app/(coach)/learn/coach/page.tsx` | Miss effect deps += `pin?.questionId` | FR-5, FR-6 |
| P6 | `frontend/components/coach/CoachPanel.tsx` | Same deps fix | FR-5, FR-6 |
| P7 | `frontend/components/summary/SummaryView.tsx` (+ test) | Label `"Mastery change"` | FR-7 |
| P8 | `frontend/components/quiz/QuizView.tsx` (+ test) | Enabled Reveal `text-fg` | FR-8 |
| P9 | `frontend/e2e/learn/validate_epic_ab.spec.ts` | Remove `test.fail` from FLAG-1 and FLAG-4 only; leave FLAG-5 | FR-3, FR-5 DoD |

**Explicitly untouched:** `coach_thread_store.ts`, coach Wrap-up `onWrapUp`, summary close path from Coach, A0 docs/tests, stream/BFF, Python.

---

## 3. Migration / sequencing

1. **Store + reducer (L1 red→green)** — P1, P2. No UI yet.
2. **Resume helper + quiz mount** — P3, P4. Manual: Q2 → Coach → Back → same stem.
3. **Miss refresh** — P5, P6. L1/e2e FLAG-1.
4. **Summary label + Reveal** — P7, P8 (parallelizable with 3).
5. **E2E flip** — P9: remove `test.fail` FLAG-1/4; confirm FLAG-5 still inverted.
6. **Gate** — `make check` + paste e2e evidence.

---

## 4. Constitution check

| Check | Result |
|---|---|
| Invariants #1–#8 | Frontend-only; no upward imports |
| G1 new abstraction | **No** — extend `quiz_session_store` |
| ⚠️ Ask first | None |
| AP-6 honesty | FR-4 clears stale pointer; FR-6 no fake miss N |
| Live LLM in CI | No — existing e2e bypass / mocks |
| G8 test weakening | Removing `test.fail` **strengthens** suite (assertions stay) |
| Epic C0 conflict | FLAG-5 left alone; store comment points C0 at `readActiveQuiz()` |

---

## 5. Risks / edge notes

| Risk | Mitigation |
|---|---|
| Resume without stashed score → `0/0` | Stash score on every pointer write |
| `sessionRepo.get` null (closed/GC) | FR-4: clear + fresh `openSession` |
| Resume into `reviewing` | Out of MVP: always restore `answering` with current item (e2e FLAG-4 only needs Q2 stem) |
| `?focus=` remount | Resume ignores focus param when pointer exists (same session continuity); fresh open still honors focus |
| Epic D `Q-8` End-session | Forward: must `clearActiveQuiz` — document in store JSDoc |

---

## 6. Plan gate

**Status:** Approved — 2026-07-10.

Task list: [epic-ab-continuity-fixes.tasks.md](epic-ab-continuity-fixes.tasks.md). Implement unlocked.
