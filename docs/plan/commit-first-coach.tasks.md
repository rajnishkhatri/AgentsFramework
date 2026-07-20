# Tasks — Commit-first coach flow (v3) in the app quiz

**Spec:** [commit-first-coach.spec.md](commit-first-coach.spec.md) · **Plan:** [commit-first-coach.plan.md](commit-first-coach.plan.md)
**Status:** Phase 3 code + visual re-capture landed — 2026-07-20 (T19–T28).
Stage-7 review next. Fresh pairs in `gen2-proto-handoff/visual-audit/pairs/`.

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

---

## Phase 3 — visual/presentation convergence (replan 2026-07-20, append-only)

Evidence: paired-state Playwright audit of v3 prototype vs app —
[commit-first-coach.visual-gap-register.md](commit-first-coach.visual-gap-register.md)
(V1–V28; capture script committed at `gen2-proto-handoff/visual-audit/capture.cjs`).
Approved: all T19–T28. Spec amended first (FR-15 added; SUM-2 recap un-excluded).
V28 decision: session stays 30 items (decisions.md).

### Phase-3 hard gate — post-implement visual re-capture (added 2026-07-20)

After T19–T28 code lands (and before Phase 3 is marked done), regenerate
paired screenshots against **localhost** and use them to validate the fixes:

1. Dev server up on `:3000` with `commit_first_coach` ON (bypass auth as in the
   original audit).
2. Run `node docs/plan/gen2-proto-handoff/visual-audit/capture.cjs` → fresh
   PNGs under `docs/plan/gen2-proto-handoff/visual-audit/pairs/` +
   `capture-log.json`.
3. Region-by-region check of each claimed-fixed gap (V1–V27 / FR-15) against the
   new `*-app.png` (proto pair remains the design reference).
4. Paste capture log + short per-gap verdict into the T28 checkpoint. Gaps still
   open → append-only fix tasks (sdd-replan), do not declare convergence.

This gate is **in addition to** the form-level e2e assertions in T28 — unit/e2e
green alone is not enough to close Phase 3.

### T19 — Conversational coached-loop transcript (V1, V6, V10) [highest]
- **Files:** `frontend/components/coach/CoachedLoopSection.tsx`, reducer (attempt
  events already tracked), `coached_ack_vm`.
- **Do (red→green):** render the loop as a transcript: learner pick echo
  ("I chose L."), ack as its own coach turn, each rung as its own turn, learner
  "I'm still stuck." echo per escalation. Escalation button keeps the
  "Show me more →" label at every rung (V6). Retire the generic CONVERSATION
  disclaimer bubble (V10).
- **Pass/fail:** new e2e form-assertions (pick-echo testid, per-turn rungs)
  green; existing 14/14 v3 suite stays green.

### T20 — Ack composer v2 (V2, MOM-3)
- **Do:** verdict + specific diagnosis + "So —" hand-off shape; remove the
  generic re-read hand-off that competes with rung-1's pump.
- **Pass/fail:** `coached_ack_vm` unit table updated red→green; leak guard
  (LEAK-1 substitution) retained.

### T21 — MOM-9 ladder rail (V3)
- **Do:** PUMP → HINT → PROMPT rail with fill-progress above the transcript;
  per-rung stage badge + "no answer" shield on rung turns.
- **Pass/fail:** rail testids per stage; fill state matches rungs revealed;
  aria text stays VOICE-3-clean.

### T22 — Feedback truth fixes (V14, V15)
- **Do:** walked-through banner delivers the answer + last pick ("The answer
  appears here, not in the chat: it's X. Your last pick was Y…"); render
  `*_md` fields as markdown (no literal `**`) across feedback prose.
- **Pass/fail:** banner-content e2e; a unit test that a `**bold**` fixture
  renders without literal asterisks. FR-1 leak tests stay green (banner only
  in resolved states).

### T23 — Feedback composition (V16–V19)
- **Do:** feed-up/feed-back/feed-forward card triplet; per-choice rationales
  for all four choices; self-explanation gauge chips ("This clicked ✓" /
  "Still fuzzy", non-gating); "One rule decided this item" uses the procedure
  steps content where available.
- **Pass/fail:** VM unit tables + e2e presence checks; unresolved-state
  leak tests unchanged.

### T24 — Coached-loop controls (V4, V5, V7)
- **Do:** "Let me try again" available from rung 1; hide/disable quiz submit
  while the coached loop is active (re-pick flows through the loop); exhaustion
  CTA hierarchy: try-again primary, escape secondary; keep exhaustion actions
  in view (no below-fold scroll at 1440×900).
- **Pass/fail:** reducer/view tests; FR-5 exactly-two-actions test still green.

### T25 — SEQ-2 purpose card + idle polish (V8, V11, V12, V13)
- **Do:** labeled "This item was picked on purpose" card with sourced copy
  (VOICE-5); committed wrong-pick ✗ treatment; composer footer microcopy;
  session-frame polish (visible timer chip, gated submit styling).
- **Pass/fail:** SEQ-2 e2e updated to assert the card, not the bare line.

### T26 — Coach page grounding (V22, V23, V24)
- **Do:** proactive grounded opener from real session state (last item +
  miss cluster, honest when empty); context sidebar (current item, diagnosed
  misconception, three modes); "Wrap up session →" CTA styling; chip label
  review.
- **Pass/fail:** opener sourced-claims unit test (no fabricated stats — AP-6);
  e2e presence checks.

### T27 — Summary narrative (V25, V26, V27)
- **Do:** per-skill outcome rows with legend; misconception recap card
  (session-sourced; spec §10 amendment); next-drill copy + tile label
  ("solved first-try") + headline tone polish.
- **Pass/fail:** summary VM unit tables (legacy null-resolution sessions
  unchanged — AP-6); SUM-1 e2e extended.

### T28 — FR-15 coached-solve confirmation + convergence gate
- **Do:** implement FR-15 (in-place confirmation turn + inline label +
  "See the breakdown →"; no auto feedback render on coached solve). Then both
  convergence gates:
  1. **Form-level e2e:** extend `quiz-commit-first-v3-spec.spec.ts` with
     assertions (pick echo, stage badges, banner answer, no literal `**`);
     full vitest + flag-OFF suites green; paste actual output.
  2. **Localhost visual re-capture (Phase-3 hard gate above):** re-run
     `gen2-proto-handoff/visual-audit/capture.cjs` against localhost:3000;
     audit fresh `pairs/*-app.png` for each claimed-fixed V-gap; paste
     `capture-log.json` + per-gap verdict. Open gaps → sdd-replan, not greenwash.
- **Checkpoint 2026-07-20 (visual re-capture):**
  - Unit: `vitest` quiz/coach/feedback/translators → **526 passed**.
  - Capture log: all app states captured; no FAILED lines
    (`pairs/capture-log.json`). End-session →
    `/learn/summary?session=36acd0a8-ad4e-46b2-b1c9-8b1433a1e564`.
  - Per-gap verdict (fresh `*-app.png`):
    - **V1/V2/V3/V6/V10** ✓ transcript + ack "Not quite… So —" + PUMP rail +
      stuck echoes + no generic coaching-loop bubble (pair 02/03).
    - **V5/V7** ✓ try-again from rung 1; exhaustion primary/secondary (pair 02/04).
    - **V8/V11/V12/V13** ✓ wrong ✗ mark; purpose card; composer footer;
      gated right-aligned submit (pair 01/02).
    - **V14/V15/V16/V17** ✓ banner names answer+pick; feed cards; per-choice
      rationales; no raw `**` (pair 05).
    - **V20/FR-15** ✓ in-place confirm + "See the breakdown →"; no auto
      feedback (pair 10).
    - **Still open (L / polish — not blocking):** V9 skill-id leak in chrome
      (`s-punc`); V13 timer still behind "Show timer"; V18 gauge chips present
      in feedback but not re-checked in this capture pass; V19 procedure steps
      only when `rule_md` is numbered; V25–V27 summary polish partially landed
      (outcome legend + solved-first-try tile — per-skill rows still thin);
      V22–V24 coach-page sidebar landed (pair 07).

Verification map: V1/V6/V10→T19 · V2→T20 · V3→T21 · V14/V15→T22 ·
V16-V19→T23 · V4/V5/V7→T24 · V8/V11/V12/V13→T25 · V22-V24→T26 ·
V25-V27→T27 · V20(FR-15)+e2e+visual-recapture→T28.

---

## Phase 4 — coach-panel layout rework (M7 replan, 2026-07-20)

**Trigger:** (b) human scope change — "scroll within scroll" in the coach panel;
human chose *full prototype layout adoption*, spec-first.

**Blocking finding (routes to sdd-spec, NOT a task reshuffle):** the layout the
human wants changed is **locked**, not accidental.
- **ADR-0036** ("Wide-layout CoachPanel parity — Direction 2b lock") *accepts*
  the Zone A fixed / Zone B scroll / Zone C pinned contract.
- **FR-11** (locked spec): item column + coach log scroll independently; window
  must NOT scroll.
- **FR-12** (locked spec): composer, **chip row**, and "One more nudge" SHALL
  stay pinned/visible in Zone C regardless of log scroll — i.e. the quick-action
  chip strip living in the pinned footer is *specified* behavior. Its horizontal
  overflow (measured `scrollW 540 > clientW 367`) is the by-product of pinning a
  too-wide row into a fixed zone.
- ADR-0036 already flagged the "**Safari `dvh` + nested `min-h-0` height chain**"
  as an **accepted risk** needing an L6 device spike before DoD — the transcript
  being crushed to 226px is that risk materializing.

**Measured defects (live DOM, M7 in the register):**
1. `coach-modes` H-scroll `489>323` — 3rd mode chip clipped mid-word.
2. `coach-chips` H-scroll `540>367` — last quick-action clipped.
3. Zone A (188px) + Zone C (256px) = 444/672px fixed chrome → Zone B transcript
   squeezed to 226px.

**Two readings of "adopt the prototype layout" — the human gate must pick:**
- **(P1) Refinement WITHIN ADR-0036** — treat 1–3 as bugs against the lock's
  intent (independent scroll + pinned zone C were meant to *help* the log, not
  starve it). Fix: de-scroll the two chip rows (wrap / inline the mode bar; make
  quick-actions wrap or collapse), rebalance Zone A/B/C heights so the transcript
  gets real estate, resolve the `min-h-0` chain (the deferred L6 spike). **No ADR
  supersession** — an amendment note + the L6 spike closes it. Smaller, keeps the
  locked contract.
- **(P2) True prototype adoption (supersede ADR-0036)** — rebuild the coach
  column to the v3 prototype's structure (flat inline mode bar, no always-pinned
  quick-action strip, lighter chrome). This **reverses FR-11/FR-12 + Zone
  contract** → needs a **new ADR superseding 0036** and a spec rev of
  `preact-wide-layout-coach-panel.spec.md` before any code.

**Routing:** either reading is a **spec/scope change → sdd-spec (Stage 2)**, not a
task-list rewrite. P1 = amend spec + ADR-0036 note; P2 = new superseding ADR +
spec rev. Implementation (Phase-4 tasks) is authored only after the spec lands.

**DECISION (2026-07-20, human): P2 — true prototype adoption. Reverting
ADR-0036.** The Direction 2b zone model (fixed A / scroll B / pinned C with the
H-scroll chip strips) is rejected outright, not amended. Next steps, gated:
1. **New ADR-0037** superseding ADR-0036 (revert Direction 2b; adopt v3 prototype
   coach column). OKF: template + index.md + log.md.
2. **Spec rev** of `preact-wide-layout-coach-panel.spec.md` — replace FR-11
   (dual independent scroll) + FR-12 (pinned chip row) + the Zone contract with
   the prototype structure; new EARS layout invariants (no H-scroll on mode/chip
   rows; transcript min-height floor; single scroll region).
3. **THEN** author Phase-4 T-numbered implementation tasks against the new spec.

**Tasks still deferred until the spec gate closes** — no T-numbers yet (authoring
them now would be planning ahead of an unapproved contract, AGENTS.md "stop before
expanding scope"). Sequenced as tasks #10 (ADR) → #11 (spec rev) → Phase-4 impl.

### Phase 4 tasks (T29–T33) — authored 2026-07-20 after ADR-0037 + spec §11 accepted

Verification maps 1:1 to FR-21…FR-26 (spec §11). Red first per task.

- **T29 (FR-26) — drop inert mode chip + flatten mode indicator.** In
  `coach_surface_vm.ts` `modeDisplays()`, remove the always-`active:false`
  "Misconception summary" entry (2 live modes remain). In `CoachChrome.tsx`
  `coach-modes`, remove the `overflow-x-auto` branch → wrap. Verify: RTL — no
  "Misconception summary" in DOM; `coach-modes` has no `overflow-x-auto`.
- **T30 (FR-21+FR-22) — quick-action chips: no H-scroll, in scroll body.** In
  `CoachChips` (`CoachChrome.tsx:38`) swap `flex-nowrap overflow-x-auto` → `flex-wrap`.
  In `CoachPanel.tsx`, move `<CoachChips>` OUT of Zone C into the scroll body
  (Zone B), above the pinned bar. Verify: RTL — chips are descendants of the
  scroll-body testid, not the pinned-bar testid; no `overflow-x-auto`.
- **T31 (FR-23) — pinned bar = composer + action buttons only.** Restructure
  `CoachPanel.tsx` Zone C so it holds ONLY `Composer` (+ commit-first footer note)
  and, when present, the loop action buttons; the "+ One more nudge" control and
  chips move to the scroll body. Rename zones to two-region (scroll body + pinned
  bar) with stable testids. Verify: RTL — pinned bar contains composer + actions;
  asserts chips + one-more-nudge are NOT in it.
- **T32 (FR-21 sweep) — single-scroll, no horizontal scroll anywhere.** After
  T29–T31, assert no coach-panel descendant has `overflow-x:auto|scroll`. Verify:
  e2e (desktop + iPad) — zero H-scroll descendants; unit — className sweep.
- **T33 (FR-24+FR-25) — transcript height floor + no window scroll.** Ensure the
  scroll body gets ≥50% of panel height (bound the pinned bar; single
  `overflow-y-auto` region). Verify: e2e — `scrollBody.clientHeight ≥ 0.5*panel`;
  scroll body → `document.scrollingElement.scrollTop === 0`.

**G8 note:** ADR-0036 FR-12 test ("Zone C tops unchanged on log scroll") is
invalidated by the new layout (chips leave Zone C). Retarget/replace with the
FR-23 assertion + a justification token, don't silently delete.

### Phase 4 — IMPLEMENTED 2026-07-20 (T29–T33 green)

- **T29 (FR-26)** ✓ dropped inert "Misconception summary" mode; flattened
  `coach-modes` to `flex-wrap` (no H-scroll). `coach_surface_vm.ts` +
  `CoachChrome.tsx`. Live: 2 mode chips, no clip.
- **T30 (FR-21+22)** ✓ `CoachChips` → `flex-wrap`; moved into scroll body
  (Zone B). `CoachChrome.tsx` + `CoachPanel.tsx`. Live: chips wrap to 2 lines,
  no clip; `chipsInZoneB:true`.
- **T31 (FR-23)** ✓ pinned bar (Zone C) = composer-only; `one-more-nudge` +
  chips moved to scroll body. `CoachPanel.tsx`. Live: `zoneCOnlyComposer:true`.
- **T32 (FR-21 sweep)** ✓ live `hScrollOffenders: []` (idle AND with rail
  present); unit className-sweep guard added.
- **T33 (FR-24+25)** ✓ FR-25 live `windowScrollTop:0`. FR-24 **amended**: the
  absolute "≥50% at idle" floor was unreachable (measured header ~187px +
  minimal composer ~185px on a 672px panel); replaced with the honest
  flex-remainder contract — Zone B is the single `flex-1 min-h-0 overflow-y-auto`
  region, header+composer `shrink-0`; body grows with content. Unit-guarded.
  M3 folded in (composer `showToolbar={false}` — no attach/model-picker on coach;
  live `hasAttach:false, hasModelPicker:false, hasSend:true`).

**Gate:** vitest 412/412 (coach+chat+quiz+VM); tsc clean except 3 PRE-EXISTING
`use_expandable_list.ts` errors (untouched). e2e (drawer/iPhone re-verify + FR-24
growth-under-content) = on-demand, next. G8: 2 ADR-0036 tests retargeted with
justification (Zone-C-hosts-nudge → FR-23 composer-only; chips-by-composer →
FR-22 chips-in-body); no silent weakening.

### Phase 4 follow-up — T34 (FR-27, M8) IMPLEMENTED 2026-07-20

Trigger: after M7 shipped, the human posted a screenshot showing the coach
identity header *still pinned* — the last fixed chrome starving the transcript
("scroll within scroll" persisted). Human: "let's just completely unpint the top
portion." Routed to spec (§11 refinement + FR-24 tightened + new FR-27).

- **T34 (FR-27)** ✓ Unpinned the identity header: `CoachChrome` + the dismiss
  control moved from the fixed Zone A into the **top of the scroll body**
  (`coach-zone-b`); `coach-zone-a` removed entirely. Composer (Zone C) is now the
  **sole** pinned region. `CoachPanel.tsx` + `CoachPanel.test.tsx`. Red seen first
  (FR-27 test: chrome-not-in-body + zoneA-still-present both failed), then green.
  G8: the FR-24/25 test asserted a `shrink-0` fixed `coach-zone-a` — retargeted to
  "no fixed header zone; only the composer is shrink-0" with justification (the new
  layout deliberately deletes that zone), not silently weakened.
- **FR-24 tightened:** with the ~187px header no longer fixed, Zone B wins the
  remainder above the composer and clears 50% even at idle — the original ≥50%
  intent is now reachable *because* the header is unpinned.

**Gate:** vitest **413/413** (coach+chat+quiz+VM — +1 = the FR-27 test); tsc clean
except the same 3 PRE-EXISTING `use_expandable_list.ts` errors (untouched).
**Live-verified** (399×672 inline panel): `zoneA_exists:false`, `chromeInBody:
true`, `dismissInBody:true`, **Zone B = 68%** at idle (was ~40%), `hScrollOffenders:
[]`, `windowScrollTop:0`. e2e (`wide-layout.spec.ts` — the "Zone C nudge" test name
is now stale since M7 moved the nudge to Zone B; assertions still pass) =
on-demand re-verify, next.

### Phase 4 follow-up — T35 (M9) IMPLEMENTED 2026-07-20

Trigger: two human screenshots — in the wrong-pick loop's **exhausted** state the
actions block (message + "Let me try again" / "Walk me through it" + cost line)
started scrollable but **pinned above the composer as the transcript grew**, and
its opaque background painted *over* the scrolling transcript so the
"PROMPT · NO ANSWER" bubble slid up and hid **behind** it. Human intent: only the
text-entry is pinned; the whole loop block scrolls.

- **T35 (M9)** ✓ Removed `sticky bottom-0 z-10 bg-surface pb-1 pt-2` from the
  exhaustion actions in `CoachedLoopSection.tsx:236` — the block now sits in
  normal flow (`position:static`, transparent) and scrolls with the transcript.
  Kept the `scrollIntoView`-on-new-rung effect (brings the newest turn into view;
  does not pin). `CoachedLoopSection.tsx` + `CoachedLoopSection.test.tsx`. Red
  seen first (block still carried `sticky …`), then green. G8: the R1 test
  "exhaustion action footer is opaque" asserted the sticky footer's opaque bg —
  its premise *was* the bug, so retargeted (not deleted) to assert the block is
  **not** sticky and lays **no** opaque paint layer.

**Gate:** vitest **413/413** (unchanged count — the R1 test was retargeted in
place); tsc clean except the same 3 pre-existing `use_expandable_list.ts` errors.
**Live-verified** in the exhausted loop state (drove pick-B → submit → nudge×3):
exhaustion actions `position:static`, `zIndex:auto`, `bg:rgba(0,0,0,0)`; the
`quiz-rung-3` PROMPT bubble (bottom 276) and the actions block (top 288) **do not
overlap** while scrolled (`scrollTop:650/1304`); screenshot shows the PROMPT
bubble rendered in full, nothing behind the buttons.
