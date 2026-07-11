---
title: 'D3 — Session-length decision (Q-1b) · Tasks'
type: tasks
sprint: D3
epic: D
status: Ready — 2026-07-11 (Phase 1 always; Phase 2 gated on human answer)
owner: Rajnish Khatri
derives_from: docs/plan/preact-parity-D3-session-length.plan.md
related:
  - docs/plan/preact-parity-D3-session-length.spec.md
---

# D3 — Session-length decision (Q-1b) · Tasks

Phase 1 fires unconditionally. Phase 2 fires **iff** the human answer flips
`30 → N`.

## Design (before decision)

- **T-DES-D3 [blocks T-D0]. Framing review — Q-1b options + amend anatomy.**
  Two things captured before the human picks:
  1. **Options framing.** Write a two-column "keep 30 vs move to N" table in
     the D3 impl trace (or a scratch note) with these axes: adaptive-loop
     mastery signal, session length UX, coverage-ratchet + no-repeat impact
     on thin skills, prototype fidelity (the design-spec's `10` narrative),
     migration cost (test literal count). This is the framing the human
     reads at T-D1 — the recommendation stays "keep 30" per spec §2, but
     the human sees both sides.
  2. **ADR amend anatomy (only relevant if flip).** Confirm the shape of
     the Phase-2 `## Amendment` section (plan §3): NEW default `N`, rejected
     alternative, source citation `PreAct/UI-Design/design-spec.md:143`,
     cross-links to `decisions.md` line + D3 spec. This is the design of
     the amend, not its content — content depends on the human's answer at
     T-D1.
  **FR:** informs FR-1, FR-4.
  **Verification:** the two-column framing paragraph exists (in
  `docs/plan/preact-parity-D3-session-length.impl.md` OR as a comment in
  T-D0's `decisions.md` draft entry).

## Phase 1 — Decision (always)

- **T-D0. Draft `decisions.md` framing entry.**
  Prepend to [`docs/adr/decisions.md`](../adr/decisions.md) a placeholder line
  presenting both candidates verbatim:
  > `- Q-1b (2026-07-DD, DRAFT): DEFAULT_TARGET_COUNT resolution PENDING. Candidate A: keep 30 (rationale: ADR-0023 adaptive mastery signal; PreAct/UI-Design/design-spec.md:143's "10" appears only in a narrative sample session, not acceptance criteria). Candidate B: move to N (rationale: matches prototype narrative; enables 30-item drills across current thin-skill bank without waiting on S3-pre bank growth). REJECTED: (fill in on decision).`
  **FR:** FR-1 (framing).
  **Verification:** the line appears; no other file changes.

- **T-D1 [blocks T-D2]. Human answer.**
  Present the two candidates. Answer required: `keep 30` OR `move to <N>`
  with a one-sentence rationale.
  **FR:** FR-1 (resolution).
  **Verification:** answer captured verbatim.

- **T-D2 [blocks T-D3]. Convert placeholder to final entry.**
  Rewrite the T-D0 line to the confirmed outcome + rationale + rejected
  alternative. Drop the `(DRAFT)` marker.
  **FR:** FR-1.
  **Verification:** grep `docs/adr/decisions.md` for `Q-1b` → returns the
  final line only; no `DRAFT` marker remains.

- **T-D3 [parallel with T-D4]. Flip sprint-board.**
  [`preact-parity-sprint-board-D.md`](preact-parity-sprint-board-D.md) — D3
  status Draft → Implemented; brief `## Implementation evidence` block
  including the outcome + link to `decisions.md`.

- **T-D4 [parallel with T-D3]. Update parity report §Q-1b.**
  [`preact-ui-prototype-parity-VISUAL-gap-report.md`](preact-ui-prototype-parity-VISUAL-gap-report.md) —
  §Q-1b → Resolved, with the outcome and citation to `decisions.md`.

- **T-D5. Branch decision.**
  If outcome = `keep 30` → sprint COMPLETE; `make check` green trivially;
  go to T-Z (final gate).
  If outcome = `move to N` → proceed to Phase 2.

## Phase 2 — Code (only if flip to N)

### Red bar (failing tests first)

- **T-P0 [parallel-safe with T-P1..T-P4]. Prove-the-pin test.**
  Edit ONE test literal — recommend `use_quiz.test.ts:563`:
  ```
  expect(result.session.target_count).toBe(30)  →  .toBe(N)
  ```
  Run `pnpm exec vitest run components/quiz/use_quiz.test.ts` → SEEN RED
  (code still returns 30). Paste the red output.
  **FR:** FR-3.

- **T-P1 [parallel with T-P0, T-P2..T-P4].** Bulk-update
  `engine_repos.test.ts` at :544, :547, :555, :560, :568, :576, :580, :601
  from `30 → N`. Seen red first.
  **FR:** FR-2, FR-3.

- **T-P2 [parallel].** Bulk-update `engine_entities.test.ts` at :31, :108, :109.
  **FR:** FR-3.

- **T-P3 [parallel].** Update `weekly_sessions_vm.test.ts:20` and
  `streak_vm.test.ts:20`.
  **FR:** FR-3.

- **T-P4 [parallel].** Update `scripts/validate_s3_bounded_session.ts` at
  :142, :150, :152, :207, :208, :465 (both fixture values and human-readable
  strings that mention "30").
  **FR:** FR-3.

### Green bar

- **T-P5 [blocks T-P6, T-P7]. Flip the const.**
  Edit [`drizzle_session_repo.ts:26`](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:26):
  `const DEFAULT_TARGET_COUNT = 30 → = N`.
  **FR:** FR-2.
  **Verification:** T-P0..T-P4 all turn green together.

- **T-P6 [parallel with T-P7]. E2E literals.**
  Update `e2e/learn/validate_s5_done_state.spec.ts:32` (comment/expectation)
  and `e2e/learn/quiz-progress.spec.ts:6,7,30` (comment + expectation).
  **FR:** FR-3.
  **Verification:** `pnpm exec playwright test e2e/learn/validate_s5_done_state.spec.ts e2e/learn/quiz-progress.spec.ts --project chromium`
  → green.

- **T-P7 [parallel with T-P6]. Re-run 60-Q no-repeat validator.**
  `pnpm exec playwright test e2e/learn/quiz-no-repeat-60.spec.ts --project chromium`.
  If red: surface — the count is a legit product problem, not a test problem.
  **FR:** FR-3 (regression guard).

### ADR amendment

- **T-P8 [blocks T-Z]. Amend ADR-0023.**
  Append to [`docs/adr/0023-quiz-bounded-session-target-count.md`](../adr/0023-quiz-bounded-session-target-count.md)
  a new section:
  ```
  ## Amendment — YYYY-MM-DD (Q-1b resolved)

  Status: amendment, accepted YYYY-MM-DD.

  New default: DEFAULT_TARGET_COUNT = N (was 30).

  Rejected alternative: keep 30. Rationale for rejection: <copied from decisions.md>.

  Source citation: PreAct/UI-Design/design-spec.md:143.

  Cross-links: docs/plan/preact-parity-D3-session-length.spec.md; docs/adr/decisions.md (Q-1b line).
  ```
  Header frontmatter `updated:` field bumped.
  **FR:** FR-4.

## Validation (post-implementation UI walk)

Mirrors D1's paired `validate_d1_quiz_frame_ui.md` + `quiz-frame.spec.ts` pattern
([`frontend/scripts/validate_d1_quiz_frame_ui.md`](../../frontend/scripts/validate_d1_quiz_frame_ui.md), [`frontend/e2e/learn/quiz-frame.spec.ts`](../../frontend/e2e/learn/quiz-frame.spec.ts)).

**Phase 1 outcome ("keep 30"):** validation is docs-only (no runtime behaviour
changed). Skip T-VAL-D3b/T-VAL-D3c; T-VAL-D3a shrinks to a docs-verify
runbook (Part 6 only from D1's shape).

**Phase 2 outcome (flip to N):** full walk applies.

- **T-VAL-D3a [blocks T-VAL-D3b, T-VAL-D3c].** Author manual runbook:
  `frontend/scripts/validate_d3_session_length_ui.md`.
  Mirror `validate_d1_quiz_frame_ui.md`:
  - **Header table**: Spec / Plan / Tasks / ADR-0023 (amended) / `decisions.md`
    line / Board / L4 suite (D3).
  - **What you should expect to SEE**: quiz progress reads `Question 1 of N`
    on a fresh session (was 30); dashboard weekly/streak fixtures reflect the
    new count.
  - **Part 0 — boot**: same middleware + branch checkout + hard-refresh
    warning D1 has.
  - **Part 1 — Fresh session opens at N**: open `/learn/quiz` cold;
    `quiz-progress` reads exactly `Question 1 of N`; answer a few items;
    progress ticks correctly (`Question 2 of N`, …).
  - **Part 2 — Per-mode policy override still wins (FR-5 regression guard)**:
    with a `session.target_count.drill = 30` policy row present (or use the
    test seed that already stores it, per
    [`engine_repos.test.ts:544`](../../frontend/lib/adapters/engine/repos/engine_repos.test.ts:544)),
    open a drill session and confirm `Question 1 of 30`. This proves only
    the seed-floor moved, not the policy path.
  - **Part 3 — No-repeat 60-Q validator**: run
    `pnpm exec playwright test e2e/learn/quiz-no-repeat-60.spec.ts --project chromium`
    manually; still green at the new count (deduplication holds).
  - **Part 4 — Regression walk**: D1 frame chrome still renders; D2 dots +
    labels (if landed by then) still render; Finish → `/learn/summary` still
    works; End → `/learn` still works.
  - **Part 5 — Docs spot-check**: ADR-0023 has `## Amendment` section with
    date + new default + rejected alternative + citation; `decisions.md`
    line records outcome; parity report §Q-1b marked Resolved.
  - **Part 6 — Console hygiene**: no red errors.
  - **§A automated proof**: exact `pnpm exec vitest run` + Playwright
    commands from T-P0..T-P7.
  - **Pass/fail summary table**: mirror D1's.
  **FR:** covers FR-2, FR-3, FR-4, FR-5 as a manual sanity net.
  **Verification:** file exists; FR map covers every FR.

- **T-VAL-D3b [parallel with T-VAL-D3c]. Playwright validation suite.**
  Author `frontend/e2e/learn/validate_d3_session_length.spec.ts`.
  - `session opens at N by default`: fresh open of `/learn/quiz` — assert
    `page.getByTestId('quiz-progress').textContent()` contains `Question 1 of ${N}`.
  - `per-mode policy override still wins`: seed a policy row
    `session.target_count.drill = 30` before opening `/learn/quiz?focus=<skillId>`;
    assert progress reads `Question 1 of 30` (FR-5 regression guard).
  - `no-repeat holds across ceil(60/N) sessions`: mirror the shape of
    `quiz-no-repeat-60.spec.ts` — but parameterised on `N`; runs
    `Math.ceil(60/N)` sessions and asserts no duplicate prompt+choices key
    across them.
  **FR:** FR-2, FR-3, FR-5 — automated mirror of the manual walk.
  **Verification:** SEEN RED on pre-D3 tree if code changes are staged (Phase
  2); SEEN GREEN post-D3. Paste actual output.

- **T-VAL-D3c [parallel with T-VAL-D3b]. Human runbook walk.**
  Run T-VAL-D3a end-to-end in a browser; every checkbox ticked. Failures
  captured with step id + URL + screenshot.
  **FR:** all D3 FRs.
  **Verification:** ticked runbook; summary line in D3 impl trace
  (`docs/plan/preact-parity-D3-session-length.impl.md`).

## Final gate (both phases)

- **T-Z [blocks merge].** Run `make check` + `pytest tests/architecture/ -q` +
  `pnpm exec vitest run` + (Phase 2 only) `pnpm exec playwright test e2e/learn/ --project chromium`.
  Paste actual output — no summaries.

## FR-to-task coverage matrix

| FR | Task(s) | Layer |
|----|---------|-------|
| FR-1 | T-DES-D3, T-D0, T-D1, T-D2, T-D3, T-D4 | docs |
| FR-2 | T-P1, T-P5, T-VAL-D3b | L1 + L4 |
| FR-3 | T-P0..T-P4, T-P6, T-P7, T-VAL-D3b, T-VAL-D3c | L1 + L4 + manual |
| FR-4 | T-DES-D3 (amend anatomy), T-P8 | docs (ADR) |
| FR-5 | T-VAL-D3a Part 2, T-VAL-D3b (per-mode override case) | L4 |
| design | T-DES-D3 | intent locked pre-decision |
| runbook | T-VAL-D3a, T-VAL-D3c | manual walk |

## Parallel groupings

```
Phase 1:  T-DES-D3 → T-D0 → T-D1 → T-D2 → { T-D3 ‖ T-D4 } → T-D5

Phase 2 (iff flip):
  { T-P0 ‖ T-P1 ‖ T-P2 ‖ T-P3 ‖ T-P4 }              (red bar authored in parallel)
  → T-P5                                             (green — the const)
  → { T-P6 ‖ T-P7 }                                  (E2E + 60-Q validator)
  → T-P8                                             (ADR amend)
  → T-VAL-D3a → { T-VAL-D3b ‖ T-VAL-D3c }            (validation runbook + suite + walk)
  → T-Z                                              (final gate)
```
