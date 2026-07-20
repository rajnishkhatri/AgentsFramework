# Tasks — Commit-first coach flow (v3) in the app quiz

**Spec:** [commit-first-coach.spec.md](commit-first-coach.spec.md) · **Plan:** [commit-first-coach.plan.md](commit-first-coach.plan.md)
**Status:** Implemented — 2026-07-19 (T1–T12 landed; T13–T18 Phase 2 v3 convergence landed; Stage-7 review next)

**Stage-4 baseline (2026-07-19):** `pytest tests/architecture/ -q` → 221 passed, 3 skipped (green). Targeted frontend suites (quiz/coach/feedback/summary/translators) → 577/578; the 1 failure is a PRE-EXISTING flaky test (`use_summary.test.ts::derives_misconception_from_last_incorrect_attempt_on_recommended_skill`, 2/5 runs — same-ms `created_at` tie broken by random id order), unrelated to this change but in T10's blast radius. Fix spawned as a separate task; resolve it before or alongside T10 so gate runs are stable.

---

## Checklist — is every EARS criterion measurable?

| FR | Measurable? | Metric |
|----|-------------|--------|
| FR-1 no-reveal | ✅ | reducer never yields `reviewing` on wrong+ON; no `quiz-reveal` testid in DOM; FeedbackView absent while unresolved |
| FR-2 no pre-commit help | ✅ | pre-submit DOM has no hint toggle/ladder; CoachPanel idle copy present |
| FR-3 wrong→ladder | ✅ | state after `submitted(wrong)`: phase=answering, coachedLoop.activeLetter=L, rung 1 visible; attempt recorded |
| FR-4 n of 3 | ✅ | counter text derives from rungsRevealed/3; rung reveal only via `nudge_requested` |
| FR-5 exhaustion pair | ✅ | exhausted DOM: exactly 2 actions + cost line; escape absent at rungs 0–2 & pre-submit |
| FR-6 escape resolves | ✅ | `escape_taken` → reviewing + resolution=walked_through + FR-6 attempt row; transcript-free reveal (no coach turn contains key) |
| FR-7 switch/inert | ✅ | L1→L2 resets rungsRevealed[L2]=…rung1; same-letter resubmit: state deep-equal + no new repo call |
| FR-8 fallback chain | ✅ | choice→item-level→generic single-rung; exhaustion actions present in generic case |
| FR-9 correct resolves | ✅ | first attempt correct ⇒ first_try; later ⇒ coached; label matches |
| FR-10 persistence | ✅ | resolving attempt row carries resolution; non-resolving rows null; legacy null readable |
| FR-11 honest score | ✅ | score_correct == count(first_try); 3 counts rendered; walked_through never in "solved" |
| FR-12 review-once | ✅ | fake scheduler: review called exactly once (first attempt) across retry+escape sequences |
| FR-13 surface unity | ⚠️ partial | coached UI lives only in shared QuizView (grep: no coachedLoop reads in surface branches) — plus e2e on desktop; drawer/fullscreen visual parity is review-level |
| FR-14 flag OFF | ✅ | existing reducer/QuizView/page suites pass UNMODIFIED with flag OFF |

FR-13's cross-surface visual parity is human-review; its logic-level claim (single shared implementation) is grep/test-checkable.

## Tasks (atomic, file-level; [P]=parallelizable, →=depends on)

### T1 — Wire type + port: `Attempt.resolution` [P]
- **Files:** `frontend/lib/wire/engine_entities.ts`, `frontend/lib/ports/engine/attempt_repo.ts`
- **Do:** additive `resolution?: "first_try"|"coached"|"walked_through"|null`; record-payload accepts it; doc: set only on the resolving attempt.
- **Pass/fail:** typecheck green; in-memory round-trip test stores/returns it; omitting it stays valid (legacy). (FR-10)

### T2 — Adapter parity + drizzle column →T1
- **Files:** `frontend/lib/adapters/engine/repos/drizzle_attempt_repo.ts`, `frontend/lib/adapters/engine/db/schema.pg.ts` + `schema.sqlite.ts` (+ `schema.parity.test.ts` stays green), new `frontend/drizzle/000N_add_attempt_resolution.sql`, `frontend/lib/adapters/engine/db/in_memory_engine_db.ts`
- **Do:** nullable column; both adapters persist/return `resolution`; no backfill.
- **Pass/fail (red first):** adapter tests: row with resolution round-trips; legacy row reads null. (FR-10)

### T3 — `commit_first_coach` flag [P]
- **Files:** `frontend/lib/ports/feature_flag_provider.ts` (`FeatureFlagName` union + `EnvVarFlagsAdapter`) + wherever quiz reads flags
- **Do:** add `commit_first_coach` to the union; `NEXT_PUBLIC_FF_COMMIT_FIRST_COACH` env wiring, default ON when dev/bypass, OFF otherwise; expose via existing provider path.
- **Pass/fail:** provider test: ON in bypass env, OFF unset. (FR-14 precondition)

### T4 — Reducer coached loop, RED first →T3
- **File:** `frontend/components/quiz/quiz_screen_reducer.ts` (+ its test)
- **Do (red→green):** coachedLoop state; actions `nudge_requested`/`try_again`/`escape_taken`; `submitted` fork on flag+verdict; same-letter inert; rung cap 3; resolution derivation.
- **Pass/fail:** new cases seen red then green; **existing suite passes unmodified with flag OFF**. (FR-1/3/4/5-state/6-state/7/9/14)

### T5 — Orchestration: resolution + review-once + escape row →T1,T4
- **File:** `frontend/components/quiz/use_quiz.ts` (+ test, fake ports)
- **Do:** resolving attempt carries resolution; `scheduler.review` only on first graded attempt; escape records `correct=false, resolution=walked_through, chosen_letter=lastWrong`.
- **Pass/fail (red first):** sequences (wrong,wrong,correct), (wrong×N,escape), (correct): review called exactly once each, at first attempt; rows match. (FR-6/10/12)

### T6 — QuizView coached section [flag] →T4
- **File:** `frontend/components/quiz/QuizView.tsx` (+ test)
- **Do:** flag ON: remove "Get a hint"/"Reveal answer"/hint block; coached section under choices: revealed rung bodies, "n of 3", "Show me more →", exhaustion pair + cost copy. Flag OFF: untouched render.
- **Pass/fail (red first):** DOM assertions per FR-1/2/4/5; flag-OFF snapshot tests pass unmodified. (FR-1/2/4/5/14)

### T7 — Page wiring + ladder fallback chain →T4,T6
- **Files:** `frontend/app/(coach)/learn/quiz/page.tsx`
- **Do:** Effect 5 keys ladder load off submitted wrong letter; fallback choice→item-level→generic single-rung (FR-8); pass resolution to FeedbackView; wire escape.
- **Pass/fail:** fallback chain unit-tested at the seam that selects the ladder source; manual walkthrough renders rung 1 after wrong submit. (FR-3/8)

### T8 — FeedbackView 3-state + walked-through variant [P] →T1
- **Files:** `frontend/lib/translators/feedback_vm.ts`, `frontend/components/feedback/use_feedback.ts`, `FeedbackView.tsx` (+ tests)
- **Do:** result label per resolution; walked-through banner ("…won't count as solved"), why-tempted keyed to last wrong letter; visually distinct, non-punitive.
- **Pass/fail (red first):** VM tests for 3 labels + last-wrong-letter keying. (FR-6/9)

### T9 — CoachPanel idle + retire quiz-pin ladder [P] →T4
- **Files:** `frontend/components/coach/CoachPanel.tsx` (+ test; `HintLadderList` usage removed in quiz context)
- **Do:** flag ON: idle copy pre-submit; remove `HintLadderList` + "+ One more nudge" from quiz pin; free-ask untouched.
- **Pass/fail:** idle copy asserted pre-submit; no nudge button in quiz context; flag OFF unchanged. (FR-2)

### T10 — Summary: first-try score + outcome counts [P] →T1
- **Files:** `frontend/lib/translators/session_summary_vm.ts`, `frontend/components/summary/SummaryView.tsx` (+ tests)
- **Do:** scoreTile counts first_try only; outcome-counts row (3 honest labels; hide walked-through when 0); legacy null-resolution sessions render as today (AP-6 — no fabricated outcomes).
- **Pass/fail (red first):** VM tests incl. legacy session. (FR-11)

### T11 — E2E: the two journeys →T5–T9
- **File:** `frontend/e2e/learn/quiz-commit-first.spec.ts`
- **Do:** chromium, flag ON: (a) commit→wrong→3 nudges→escape→walked-through breakdown, no reveal in coach; (b) wrong→try again→correct→"Worked through it with the coach".
- **Pass/fail:** both pass locally; existing e2e untouched (they run flag OFF). (FR-1/5/6/9 end-to-end)

### T12 — Gates + decisions
- **Do:** `decisions.md` entry (ladder-in-quiz-card, clarify Q1–Q4); `pnpm --dir frontend test` + typecheck; `make check`; paste actual output.
- **Pass/fail:** all green; FR-14 evidenced by unmodified legacy suites passing. (spec §9 DoD)

## Dependency graph

```
T1 ─┬─ T2
    ├─ T5 ──┐
    ├─ T8   ├─ T11 ─ T12
T3 ─ T4 ─┬─ T6 ─ T7 ─┘
         ├─ T9
T1 ────── T10 (P)
```

Start immediately in parallel: T1, T3. Then T4 (the concentration point), then fan out T5/T6/T8/T9/T10.

## Verification map (1:1 EARS → task)

FR-1→T4/T6/T11 · FR-2→T6/T9 · FR-3→T4/T7 · FR-4→T4/T6 · FR-5→T4/T6/T11 · FR-6→T4/T5/T8/T11 · FR-7→T4 · FR-8→T7 · FR-9→T4/T8/T11 · FR-10→T1/T2/T5 · FR-11→T10 · FR-12→T5 · FR-13→T6(shared home)+review · FR-14→T3/T4/T6/T12.

---

## Phase 2 — v3-spec convergence (replan 2026-07-19, append-only)

Gap analysis: 16-test conformance suite derived from the design-agent spec
(`frontend/e2e/learn/quiz-commit-first-v3-spec.spec.ts`) — 12 green, 4 gaps —
plus a code-level FR audit. Approved: all T13–T18; End-session routes to
summary (decision in `docs/adr/decisions.md`).

**Phase 2 result (2026-07-19):** T13–T18 landed. The 4 red conformance tests
(MOM-3/VOICE-1, FBK-2, SEQ-2, SUM-1) now green; full v3 spec 14/14 green;
legacy flag-OFF `quiz-frame` 12/12 green; Phase 1 `quiz-commit-first` (flag ON)
2/2 green; full frontend vitest 1992/1992 green. Touched files typecheck-clean
(3 pre-existing errors remain in untouched `components/coach/use_expandable_list.ts`;
1 pre-existing e2e failure in `validate_e1b` lesson→coach pin flow — both fail on
the Phase-2-free baseline, unrelated). Decisions captured in `docs/adr/decisions.md`.

### T13 — Acknowledgment turn before the pump (G1, MOM-3/VOICE-1) [highest]
- **Files:** `frontend/components/coach/CoachedLoopSection.tsx` (+ a pure
  composer, e.g. `lib/translators/coached_ack_vm.ts`), reducer/page wiring.
- **Do (red→green):** compose shared-ground acknowledgment from the item's
  `misconception` + `per_choice_rationale[L]` for the picked letter; render as
  `data-testid="quiz-coached-ack"` above rung 1; VOICE-1 order (shared ground →
  trap → handoff), VOICE-3 vocabulary, never names the correct letter/key.
- **Pass/fail:** currently-failing MOM-3/VOICE-1 e2e goes green; VM unit test
  table over 2+ items/letters; no leak of correct answer text.

### T14 — End session routes to summary (G2, SUM-1 reachability)
- **Files:** `frontend/app/(coach)/learn/quiz/page.tsx` (end-session handler),
  session close path in `use_quiz.ts`.
- **Do:** ≥1 resolved item → close session and route to the summary view
  (score, outcome counts, misconception); 0 resolved → dashboard (today's
  behavior). Flag-OFF path unchanged.
- **Pass/fail:** currently-failing SUM-1 e2e goes green (walked-through count
  visible, first-try-only score); legacy end-session e2e (flag OFF) unchanged.

### T15 — Self-explanation input on feedback (G3, FBK-2)
- **Files:** `frontend/components/feedback/FeedbackView.tsx` (+ VM).
- **Do:** optional textarea "Saying it back makes it stick" —
  `data-testid="feedback-self-explanation"`; never gates progression; value
  not persisted in this slice (UI affordance parity only — note in code).
- **Pass/fail:** FBK-2 e2e green; advancing without typing stays possible.

### T16 — "Why this item" line (G4, SEQ-2)
- **Files:** `frontend/components/quiz/QuizView.tsx` (+ small VM helper).
- **Do:** honest line from skill + difficulty + position
  (`data-testid="quiz-why-item"`); copy never claims interleaving/ordering the
  scheduler doesn't guarantee (VOICE-5).
- **Pass/fail:** SEQ-2 e2e green; copy sourced from real session state.

### T17 — Polish batch (G5–G9)
- Distinct wrapper + `data-testid="feedback-why-tempted"` for the
  walked-through why-tempted block (G5).
- Aria announcement drops "rung" vocabulary (G6, VOICE-3).
- `used_hint` semantics under commit-first: decision note in `decisions.md`
  (G7) — currently any coached item is `used_hint=true`.
- Race-pinning test: rung bodies must match `coachedLoop.activeLetter` even
  with a slow `ladder_loaded` (G8).
- Remove dead branch in `countSessionOutcomes` (G9).
- **Pass/fail:** each has a test or decision-note artifact; no behavior change
  beyond the listed ones.

### T18 — Convergence gate
- **Do:** `pnpm vitest run` (touched suites) + full
  `quiz-commit-first-v3-spec.spec.ts` 16/16 green + legacy suites flag-OFF
  green; paste actual output; commit.

Verification map: G1→T13 · G2→T14 · G3→T15 · G4→T16 · G5-G9→T17 · gate→T18.
