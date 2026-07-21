# Plan — Commit-first coach flow (v3) in the app quiz

**Spec:** [commit-first-coach.spec.md](commit-first-coach.spec.md)
**Status:** Approved — 2026-07-19 (plan gate passed; Stage-4 analyze green with one flagged pre-existing flake, see tasks §baseline)
**Constitution check:** Frontend Ring only; Python invariants #1–#8 untouched; no ⚠️ Ask-first trigger (no new dep, no trust type, no new service/node/abstraction — see G1 note below).

---

## A1 — Simplest thing that satisfies the criteria

Extend the three seams that already own this flow — `quiz_screen_reducer` (phase
machine), `use_quiz` (orchestration), and the existing view components — rather
than introducing any new state machine, store, or service. Reuse every existing
seam:

| Need | Existing seam (grounded) | Change |
|---|---|---|
| Phase machine | `quiz_screen_reducer.ts` `answering→reviewing` | Add coached-loop sub-state inside `answering`; `reviewing` gains `resolution` |
| Ladder load per wrong letter | Effect 5 + `resolveHintChoiceLetter` (ADR-0035) | Unchanged mechanism; now driven by submitted (not selected) letter |
| Ladder render | `HintLadderList` (counter UI exists) | Re-home into the quiz card; counter "n of 3" (was "n of 2") |
| Feedback screen | `FeedbackView` + `feedback_vm` (why-correct/why-tempted/rule all exist) | Add 3-state result label + walked-through banner variant |
| Attempt truth | `AttemptRepo.record` (append-only) | Additive nullable `resolution` field |
| Mastery writer | `scheduler.review` call in `runQuizSubmit` | Gate to first graded attempt per item |
| Summary | `session_summary_vm` + `SummaryView` | First-try score + three outcome counts |
| Flag | `FeatureFlagProvider` port (exists) | New `commit_first_coach` flag, no new mechanism |

**G1 note (no new abstraction):** the coached-loop state is fields on the existing
reducer state, not a second state machine; the rejected alternative — a standalone
"coaching moment" store/machine mirroring the prototype's moments — buys nothing
the reducer doesn't already give and would create a second source of truth next to
`quiz_screen_reducer` (the exact dual-truth smell ADR-0035's moment router avoided).

## UI composition decision (→ decisions.md at implementation)

The ladder UI moves INTO the quiz card (rendered under the choices while in the
coached loop). Reason: the fullscreen (iPhone) surface has no `CoachPanel` on the
quiz page, so panel-homed ladder UI would fork behavior per surface and violate
FR-13. One shared `QuizView` coached section serves all three surfaces; the
`CoachPanel` keeps idle copy + conversation (free-ask) and drops its quiz-context
`HintLadderList` + "+ One more nudge" (both were the "n of 2" deeper-rung UI this
change retires).

## File-level touchpoints

Ordered roughly by dependency; [flag] = behavior forked by `commit_first_coach`.

1. **`frontend/lib/wire/engine_entities.ts`** — `Attempt.resolution?:
   "first_try" | "coached" | "walked_through" | null` (additive).
2. **`frontend/lib/ports/engine/attempt_repo.ts`** — record payload accepts
   `resolution`; doc comment: set only on the resolving attempt.
3. **Adapters:** `drizzle_attempt_repo.ts` (+ nullable column in the drizzle
   schema + generated migration) and `in_memory_engine_db.ts` — parity.
4. **`frontend/components/quiz/quiz_screen_reducer.ts`** [flag] — new fields on
   `answering`: `coachedLoop: { attempts: Letter[], activeLetter: Letter|null,
   rungsRevealed: Record<Letter, number>, exhausted: boolean } | null`.
   New actions: `nudge_requested`, `escape_taken`, `try_again`. `submitted`:
   wrong + flag ON → stay `answering` (populate coachedLoop, inert on repeat
   letter); correct → `reviewing` with `resolution` derived; flag OFF →
   current transitions untouched.
5. **`frontend/components/quiz/use_quiz.ts`** — `runQuizSubmit`: pass
   `resolution` on resolving attempts; call `scheduler.review` only when
   `attempts.length === 0` for the item (first graded attempt); escape path
   records the FR-6 resolving row (`correct=false`, `resolution="walked_through"`).
6. **`frontend/components/quiz/QuizView.tsx`** [flag] — delete "Get a hint" +
   "Reveal answer" (and `toggle_hint`/`hintOpen` when flag ON); render the
   coached section under the choices: rung bodies (rungs ≤ revealed), honest
   "n of 3" counter, "Show me more" nudge button, exhaustion pair
   ("Let me try again" / "Walk me through it" + cost line).
7. **`frontend/app/(coach)/learn/quiz/page.tsx`** [flag] — Effect 5 keys ladder
   load off the *submitted* wrong letter; `reviewing` branch passes `resolution`
   to `FeedbackView`; wire `escape_taken` → resolve + transition.
8. **`frontend/components/feedback/feedback_vm.ts` + `use_feedback.ts` +
   `FeedbackView.tsx`** — result label 3-state; walked-through variant: distinct
   banner ("The breakdown takes it from here — this one won't count as solved."),
   why-tempted keyed to last wrong letter.
9. **`frontend/components/coach/CoachPanel.tsx`** [flag] — idle copy pre-submit
   ("Commit to a choice — coaching starts from what you pick."); remove quiz-pin
   `HintLadderList` + "+ One more nudge"; free-ask untouched.
10. **`frontend/lib/translators/session_summary_vm.ts` + `SummaryView.tsx`** —
    `scoreTile` = first_try count (legacy sessions: unchanged value by
    construction); add outcome-counts row (hide walked-through count when 0;
    legacy null-resolution sessions render exactly as today — AP-6).
11. **Flag wiring** — `commit_first_coach` in the flags adapter; default ON when
    `E2E_BYPASS_AUTH=1`/dev, OFF in prod until staged.
12. **Tests** — new/changed vitest suites for 4–10 (red first); existing quiz
    suites run flag-OFF and must stay green unmodified (FR-14 regression);
    one new Playwright spec (commit→wrong→3 nudges→escape; wrong→retry→coached).

## Migration & rollout

- Drizzle: one additive nullable column; no backfill (legacy rows null ⇒ legacy
  read rule). Reversible by ignoring the column.
- Rollout: dev soak with flag ON → prod flag flip (no deploy coupling) →
  flag removal is a later cleanup slice once prod-stable (not this scope).

## Risks

- **R1 — reducer regression risk** is the concentration point (one file forks two
  flows). Mitigation: FR-14 keeps the entire existing reducer test suite green
  un-forked; new behavior tested only via new cases.
- **R2 — e2e drift:** existing Playwright specs assume instant reveal; they run
  flag-OFF (default prod parity). New spec covers flag-ON.
- **R3 — fullscreen surface** has no panel; ladder-in-quiz-card composition
  (decision above) is the guard against a per-surface fork.
- **R4 — same-letter resubmit** must be inert at the reducer level (not view
  level) or attempt spam reaches the repo (FR-7 test pins this).
