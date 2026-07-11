---
title: 'D3 — Session-length decision (Q-1b) · Plan'
type: plan
sprint: D3
epic: D
status: Draft — 2026-07-11 (Phase-1 only; Phase-2 activates iff decision flips)
owner: Rajnish Khatri
derives_from: docs/plan/preact-parity-D3-session-length.spec.md
governs:
  - docs/plan/preact-parity-D3-session-length.tasks.md
related:
  - docs/adr/0023-quiz-bounded-session-target-count.md
---

# D3 — Session-length decision (Q-1b) · Plan

Derived from `preact-parity-D3-session-length.spec.md` (5 FRs; Phase 1 always,
Phase 2 conditional). This plan encodes the branch: docs-only if the human keeps
30; TDD code path + ADR-0023 amend if the human flips to `N`.

## 1. Architecture posture

- **Phase 1 (always):** docs-only. Nothing under `frontend/` moves.
- **Phase 2 (conditional):** one-const change on the seed-floor default in
  [`drizzle_session_repo.ts:26`](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:26)
  + a batch of literal-30 test-fixture updates. The per-mode policy override
  path at [`drizzle_session_repo.ts:94-110`](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:94)
  is **out of scope** — only the fallback default moves. `QuizSession.target_count`
  wire shape (nullable positive int at [`engine_entities.ts:213`](../../frontend/lib/wire/engine_entities.ts:213))
  is untouched.
- **What is NOT introduced:** no wire change, no new abstraction, no new ADR
  (Phase 2 amends ADR-0023 in place).

## 2. Shape call — Phase 1 (decision)

- **Author `decisions.md` entry framing the question** (spec's recommended
  answer: keep 30). Present the entry to the human for confirm/flip. Do NOT
  branch until the human answers.
- **Human answer states two facts:** (a) `keep 30` or `move to N`;
  (b) the rejected alternative's rationale. Both go verbatim into the same
  `decisions.md` line.

## 3. Shape call — Phase 2 (only if flip to N)

- **The const.** `const DEFAULT_TARGET_COUNT = 30` at
  [`drizzle_session_repo.ts:26`](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:26)
  becomes `= N`. Nothing else in this file changes.
- **Test literals.** ~17 known sites pin the old `30` (grep in spec §8). Each
  is updated to `N` in the SAME PR. Every test is seen fail first (asserts
  `N`, code says `30`), then flipped green by T-B.
- **ADR-0023 amendment.** Append (do not rewrite) a `## Amendment — YYYY-MM-DD (Q-1b resolved)`
  section to [`docs/adr/0023-quiz-bounded-session-target-count.md`](../adr/0023-quiz-bounded-session-target-count.md).
  Include: new default `N`, rejected alternative (keeping 30), source
  citation `PreAct/UI-Design/design-spec.md:143`, cross-link to the
  `decisions.md` line and this spec.
- **No-repeat 60-Q validator re-run.** [[preact-no-repeat-60-audit-passage-sharing]]
  ran 60 questions as 2 sessions of 30. At `N`, it becomes
  `ceil(60/N)` sessions. Re-run must remain green — no dedup regression, no
  passage-sharing false positive.

## 4. File-level touchpoints

### Phase 1 (always)

| File | Change |
|------|--------|
| [`docs/adr/decisions.md`](../adr/decisions.md) | Prepend newest-first line: outcome + rationale + rejected alternative + citation `PreAct/UI-Design/design-spec.md:143`. |
| [`docs/plan/preact-parity-sprint-board-D.md`](preact-parity-sprint-board-D.md) | Flip D3 status Draft → Implemented (with the outcome). |
| [`docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md`](preact-ui-prototype-parity-VISUAL-gap-report.md) | §Q-1b → Resolved, with reference to the `decisions.md` line. |

### Phase 2 (only if flip)

| File | Change |
|------|--------|
| [`frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:26`](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:26) | `30 → N`. |
| [`frontend/lib/adapters/engine/repos/engine_repos.test.ts`](../../frontend/lib/adapters/engine/repos/engine_repos.test.ts) | Update 8 literal-30 sites (:544, :547, :555, :560, :568, :576, :580, :601). |
| [`frontend/components/quiz/use_quiz.test.ts:563`](../../frontend/components/quiz/use_quiz.test.ts) | Update `expect(...target_count).toBe(30)` → `.toBe(N)`. |
| [`frontend/lib/wire/engine_entities.test.ts`](../../frontend/lib/wire/engine_entities.test.ts) | Update :31, :108, :109. |
| [`frontend/lib/translators/weekly_sessions_vm.test.ts:20`](../../frontend/lib/translators/weekly_sessions_vm.test.ts) | Update fixture `target_count`. |
| [`frontend/lib/translators/streak_vm.test.ts:20`](../../frontend/lib/translators/streak_vm.test.ts) | Update fixture `target_count`. |
| [`frontend/scripts/validate_s3_bounded_session.ts`](../../frontend/scripts/validate_s3_bounded_session.ts) | Update :142, :150, :152, :207, :208, :465 (labels + defaults). |
| [`frontend/e2e/learn/validate_s5_done_state.spec.ts:32`](../../frontend/e2e/learn/validate_s5_done_state.spec.ts) | Update the "seed floor: DEFAULT_TARGET_COUNT" comment/expectation. |
| [`frontend/e2e/learn/quiz-progress.spec.ts`](../../frontend/e2e/learn/quiz-progress.spec.ts) | Update :6, :7, :30 (comment + expectation). |
| [`docs/adr/0023-quiz-bounded-session-target-count.md`](../adr/0023-quiz-bounded-session-target-count.md) | Append `## Amendment — YYYY-MM-DD` section. |

## 5. Execution order

### Phase 1

1. Draft the framing paragraph in `decisions.md` (BOTH candidate outcomes
   spelled out so the human's answer is one word: `keep` or `move to N`).
2. Human answers.
3. Convert the placeholder line to the confirmed outcome; commit docs-only.
4. Flip sprint-board + parity report status.

### Phase 2 (only if flip to N)

1. **Red bar first.** Rewrite ONE test literal (say `use_quiz.test.ts:563`) to
   `.toBe(N)`, run it, watch it fail. Capture the red output as proof the
   test really pins to `N`. Then rewrite the remaining literals in bulk
   (they're all mechanical value-substitutions of the same shape).
2. **The const.** Change `DEFAULT_TARGET_COUNT` to `N`. All previously-red
   tests turn green in one go.
3. **Re-run 60-Q validator.** Confirm dedup + passage-sharing still passes
   at the new count. If not: the count is a legit product problem, not a
   test problem — surface and re-gate.
4. **ADR amend.** Append the `## Amendment` section to ADR-0023.
5. **Final gate.** `make check` + `pytest tests/architecture/ -q` +
   `pnpm exec vitest run` + `pnpm exec playwright test e2e/learn/` (chromium).
   Paste actual output.

## 6. Gates + risks

- **⚠️ Ask first (Phase 1)** — this is the whole point: get a human product
  answer before touching code.
- **⚠️ Ask first (Phase 2)** — a change to a shipped ADR IS the amend. Do
  not create ADR-0028; append to ADR-0023 (ratchet discipline).
- **G8 (test-mass-rewrite gate)** — Phase 2 rewrites ~17 test literals.
  Justification recorded in the spec §10: each rewrite is a **value
  substitution**, not an assertion weakening. Every rewritten test still
  asserts an exact number; the seen-fail-first evidence in T-P1 confirms the
  new value is actually pinned (not accidentally deleted).
- **Risk: `N` too small for adaptive-loop mastery signal.** If the answer is
  `10`, mastery convergence per session may take more sessions. Not a code
  bug — a product truth to note in the `decisions.md` rationale.
- **Risk: `N` too small for coverage-ratchet on thin skills.** Currently
  `s-sent = 23` reviewed items; a `N=10` drill fits comfortably. At `N=30`
  the FR-11 end-early-on-exhaustion path handles it. Either count works.

## 7. Independence

D3 has no dependency on D2 or D4 and can merge to `main` alone. It touches
neither `_dev_seed.ts` (D2) nor `nav_model.ts` (D4).
