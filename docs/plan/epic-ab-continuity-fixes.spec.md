---
title: 'Epic A/B continuity fixes — session resume, miss refresh, mastery label (FLAG-1/4/6)'
type: spec
status: Validated
date: 2026-07-10
owner: Rajnish Khatri
related:
  - docs/plan/epic-a-b-manual-validation-report.md
  - docs/plan/epic-a-b-post-merge-review.md
  - docs/plan/preact-parity-B-coach-pass.spec.md
  - docs/plan/preact-parity-A0-correct-record.spec.md
  - docs/plan/preact-parity-sprint-board-C.md
  - docs/plan/preact-english-coach-ui.spec.md
  - docs/adr/0011-subject-coach-engine-learner-read-port.md
  - frontend/e2e/learn/validate_continuity_fixes.spec.ts
  - frontend/scripts/validate_continuity_fixes_ui.md
  - frontend/e2e/learn/validate_epic_ab.spec.ts
  - frontend/scripts/validate_epic_ab_ui.md
governs:
  - frontend/app/(coach)/learn/quiz/page.tsx
  - frontend/components/coach/CoachPanel.tsx
  - frontend/app/(coach)/learn/coach/page.tsx
  - frontend/components/quiz/quiz_session_store.ts
  - frontend/components/summary/SummaryView.tsx
  - frontend/components/quiz/QuizView.tsx
---

# Epic A/B continuity fixes — session resume, miss refresh, mastery label

> **What / why split.** This spec is the *what* (testable acceptance criteria). Small
> non-obvious choices land in `docs/adr/decisions.md`. No new graph node / trust type /
> horizontal service expected → no ADR unless clarify expands the store into a new
> abstraction that fails G1.

**Status:** Validated — 2026-07-10 (manual Steps 1–6 + `pnpm test:e2e:continuity` 4/4;
FLAG-6 mastery *value* honesty remains an open note; FLAG-5 → Epic C0)
**Owner:** Rajnish Khatri
**Related:** [manual validation report](epic-a-b-manual-validation-report.md) ·
[continuity UI walk](../../frontend/scripts/validate_continuity_fixes_ui.md) ·
[B-coach-pass C2](preact-parity-B-coach-pass.spec.md) · [A0 correct-record](preact-parity-A0-correct-record.spec.md) ·
[Epic C sprint board](preact-parity-sprint-board-C.md) (owns FLAG-5)

---

## 1. Goal

Close the session-continuity gaps found in the Epic A/B manual walkthrough so a learner
who leaves Quiz for Coach keeps an honest place in their session: miss counts refresh,
Back resumes the item they left, and the summary mastery tile is not misread as absolute
mastery.

**FLAG-5 (Wrap up → `?session=`)** is **out of scope** — owned by Epic C sprint **C0**
([sprint board](preact-parity-sprint-board-C.md) D0 fold). This sprint must not re-spec or
re-implement Wrap-up wiring.

## 2. Context

PR #140 / #141 shipped A1 Reveal and Epic B chrome. Manual Steps 1–15
([epic-a-b-manual-validation-report.md](epic-a-b-manual-validation-report.md)) confirmed
core FRs and filed:

| ID | Severity | Defect | This sprint? |
|---|---|---|---|
| **FLAG-1** | Medium | Coach miss-count `useEffect` deps = `[pin?.skillId]` only → stale N on same skill | **In** |
| **FLAG-4** | Medium | Coach ← Back remounts Quiz → unconditional `openSession` → Q1 | **In** |
| **FLAG-5** | Medium | Coach Wrap up → `/learn/summary` without `?session=` | **Out → Epic C0** |
| **FLAG-6** | Low | Summary tile labeled "Mastery" shows signed delta (often `+0%`) | **In** |
| **Polish** | Low | Enabled Reveal stays `text-muted`; opener cites item label for skill-scoped N | Reveal color **in**; opener copy **out** |
| **A0** | High (docs) | Sprint A0 never landed | **Out →** [A0 spec](preact-parity-A0-correct-record.spec.md) |

FLAG-4 was **out of** B-coach-pass C2 scope (nav only); this sprint elevates resume to a
product requirement. Epic C brainstorm explicitly left FLAG-4 and FLAG-6 outside C; FLAG-5
stays with C0.

Regression guards already exist as `test.fail()` in
`frontend/e2e/learn/validate_epic_ab.spec.ts` (FLAG-1 / FLAG-4 / FLAG-5). This sprint flips
FLAG-1 and FLAG-4 only; FLAG-5 remains `test.fail` until C0.

### 2.1 Clarify (locked 2026-07-10)

| # | Ambiguity | Decision | Status |
|---|---|---|---|
| C1 | **FLAG-4 resume depth** | **Option B — active-session stash + remount resume:** extend `quiz_session_store` with an in-tab `activeQuiz` pointer `{ sessionId, questionId, position, phase }` written by Quiz while live; on Quiz remount, IF active exists THEN resume that session/item (no new `openSession`); ELSE open fresh. Reject URL `?session=` for Back (keeps heap pattern; no deep-link resume this pass). | **accepted (option B)** · 2026-07-10 |
| C2 | ~~FLAG-5 cold Wrap up~~ | **Withdrawn** — FLAG-5 owned by Epic C0. | **withdrawn** · 2026-07-10 |
| C3 | ~~FLAG-5 close semantics~~ | **Withdrawn** — FLAG-5 owned by Epic C0. | **withdrawn** · 2026-07-10 |
| C4 | **FLAG-6 tile copy** | Relabel **"Mastery" → "Mastery change"**; keep signed delta / `"—"` semantics (FR-G1 + ADR-0011 §4). No absolute mastery % this pass. | **accepted (option A)** · 2026-07-10 |
| C5 | **Scope of Polish + A0** | **In scope:** Reveal enabled text color (`text-fg` when submittable). **Out of scope:** opener skill-name copy; A0; **FLAG-5 Wrap-up**. | **accepted (option A)** · 2026-07-10 *(FLAG-5 carve-out added)* |

---

## 3. Functional requirements (EARS)

Failure paths first.

### Continuity substrate (FLAG-4)

- **FR-1.** WHEN a Quiz session is opened or advanced (new item / phase change) THE SYSTEM
  SHALL update an in-tab active-session pointer on `quiz_session_store` with at least
  `{ sessionId, questionId, position }` (phase optional per clarify C1).
- **FR-2.** WHEN the Quiz page unmounts without Finish close THE SYSTEM SHALL **retain**
  the active-session pointer (so Coach ← Back can resume). WHEN a session is closed
  (Quiz Finish) THE SYSTEM SHALL clear the active pointer (snapshot for summary may remain
  keyed by `sessionId` per ADR-0011). *(Epic C0 / Epic D `Q-8` End-session MUST also clear
  when they land — forward note, not this sprint's FR.)*

### FLAG-4 — Back resumes

- **FR-3.** WHEN the learner activates **"← Back"** on standalone `/learn/coach` and
  history returns them to `/learn/quiz` (or fallback push to quiz) AND an active-session
  pointer exists THEN THE SYSTEM SHALL resume that session at the stashed item —
  **not** call `openSession` for a new session that resets to Q1. WHEN the pointer
  `phase` is `feedback` (left from Feedback / Ask-the-coach) THEN THE SYSTEM SHALL
  restore **reviewing** at the same progress N (Next available). WHEN the pointer
  `phase` is `answering` (or omitted) THEN THE SYSTEM SHALL restore answering.
- **FR-4** (failure). IF the active pointer's `sessionId` cannot be loaded from the
  session repo THEN THE SYSTEM SHALL open a fresh session (honest recovery) and SHALL
  clear the stale pointer — never fabricate progress.

### FLAG-1 — Miss count refresh

- **FR-5.** WHEN `coach_thread_store.pin` changes to a different `questionId` (including
  same `skillId`) THE SYSTEM SHALL re-fetch `countMissesOnSkill` and update history /
  opener N on both standalone `/learn/coach` and iPad `CoachPanel`.
- **FR-6** (failure / honesty). IF pin is null OR the miss count is unavailable THEN
  THE SYSTEM SHALL keep honest-absent chrome (B-coach-pass FR-4 / FR-9) — no fabricated N.

### FLAG-6 — Mastery tile honesty

- **FR-7.** THE SYSTEM SHALL label the summary delta tile **"Mastery change"** (not
  "Mastery"). Value semantics unchanged: signed pct when snapshot known, `"—"` when
  unknown (ADR-0011 §4).

### Polish (in-scope subset)

- **FR-8.** WHILE "Reveal answer" is enabled (`submittable`) THE SYSTEM SHALL render it
  with foreground (or accent) text — not the same muted treatment as the disabled ghost.

### Explicit non-goals this sprint

- **FLAG-5** Wrap up → `?session=` / cold Wrap-up destinations (Epic C0 D0).
- A0 docs guard / FR-D5–D6 framing (see [A0 spec](preact-parity-A0-correct-record.spec.md)).
- Persisted cross-reload quiz resume (`sessionStorage` / server resume).
- Absolute mastery % on the summary tile.
- Opener copy that cites skill display name instead of `pin.label` (follow-up).

---

## 4. Data model / contracts

Extend `frontend/components/quiz/quiz_session_store.ts` (same module-level singleton
pattern; **not** a new abstraction — G1: enlarging the existing carrier avoids a second
heap store):

```ts
export type ActiveQuizPointer = {
  sessionId: string;
  questionId: string;
  position: number; // 1-based progress position shown in QuizProgress
  correct: number;
  total: number;
  phase?: "answering" | "feedback"; // feedback → resume reviewing; else answering
  // Present when phase === "feedback":
  verdict?: Verdict;
  answeredLetter?: string;
  usedHint?: boolean;
};

// New API (names illustrative):
setActiveQuiz(pointer: ActiveQuizPointer): void;
readActiveQuiz(): ActiveQuizPointer | null;
clearActiveQuiz(): void;
// Existing stashQuizSession / readQuizSessionSnapshot / clearQuizSession unchanged.
```

No trust-kernel types. No wire-shape change to `/api/coach/run/stream`.

**Note for Epic C0:** the active pointer's `sessionId` is the natural source for Wrap-up
`?session=` once C0 lands — prefer reading `readActiveQuiz()` over putting quiz session id
on `coach_thread_store`. That amendment belongs in the C0 spec, not here.

---

## 5. Invariants & security boundaries

| Invariant | How it holds |
|---|---|
| #1–#8 layering | Frontend-only; no orchestration / services / trust edits |
| No new horizontal service | Extends existing `quiz_session_store` |
| No live LLM in CI | E2E uses mocked stream / existing bypass auth |
| Honesty (C-4 / B FR-4) | FR-6 preserves absent chrome; FR-4 recovers without fake progress |

⚠️ Ask first: **none expected** if C1 stays "enlarge existing store." If clarify picks a
new peer store or URL-param resume protocol, raise G1 + `decisions.md` / ADR.

---

## 6. Edge cases

- Back with empty history → fallback `/learn/quiz` still honors FR-3 if pointer exists.
- Two tabs: in-tab heap only (same limitation as `coach_thread_store`); no cross-tab sync.
- Adaptive / endless sessions: `position` still advances; resume uses `questionId` as source of truth.
- Finish from Feedback already clears via close — active pointer must clear (FR-2).
- Miss count API failure → leave prior N or absent; never invent (FR-6).
- Wrap-up behavior unchanged this sprint (still broken until C0) — do not regress Finish → summary.

---

## 7. Non-functional requirements

- Deterministic L1 unit tests for store + effect deps; E2E guards already authored for FLAG-1/4.
- No new npm/Python dependencies.
- Resume path must not add perceptible double-fetch beyond one `sessionRepo.get` (or
  equivalent) on remount.

---

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1, FR-2 | `quiz_session_store` set/read/clear active pointer | L1 | yes |
| FR-3 | e2e FLAG-4 (remove `test.fail`) — Back restores left item | e2e | e2e |
| FR-4 | unit: stale session id → fresh open + clear pointer | L1 | yes |
| FR-5 | e2e FLAG-1 (remove `test.fail`) + unit effect-deps | L1 + e2e | yes / e2e |
| FR-6 | existing cold-honesty tests remain green | L1 | yes |
| FR-7 | `SummaryView` label = "Mastery change" | L1 | yes |
| FR-8 | `QuizView` enabled Reveal not `text-muted`-only | L1 | yes |
| — | FLAG-5 e2e stays `test.fail` until Epic C0 | e2e | n/a this sprint |

---

## 9. Definition of Done

- [x] All in-scope FRs implemented; each has a test that was seen to fail first.
- [x] `test.fail` removed from FLAG-1 / FLAG-4 in `validate_epic_ab.spec.ts`; those two green.
- [x] FLAG-5 e2e remains `test.fail` (owned by C0) — not flipped by this sprint.
- [x] `make check` green; `tests/architecture/` green.
- [x] Clarify table §2.1 locked; plan + tasks derived and human-gated.
- [x] A0 + FLAG-5 tracked on their owning boards (not blocking this DoD).
- [x] Actual command / e2e output pasted for verification claims.
