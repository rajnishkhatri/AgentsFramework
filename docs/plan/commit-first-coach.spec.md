# Spec — Commit-first coach flow (v3) in the app quiz

**Status:** Approved — 2026-07-19 (clarify Q1–Q4 resolved; spec gate passed)
**Owner:** Rajnish Khatri
**Related:** [v3 prototype EARS spec](gen2-proto-handoff/03-ears-spec-gen2-coach-v3.md) (source of truth for the interaction design) · replan decision 2026-07-19 in `docs/adr/decisions.md` (supersedes the withdrawn [gen2-item-level-openers.spec.md](gen2-item-level-openers.spec.md)) · ADR-0035 (choice-keyed hint ladders) · ADR-0021 (bank-backed quiz)

---

## 1. Goal

Bring the approved v3 "commit-first" coaching flow to the real `/learn/quiz` surface:
a learner gets no help before committing to a choice; a wrong submit enters that
choice's 3-rung Socratic ladder (pump → hint → prompt) instead of instantly revealing
the answer; ladder exhaustion ends in a priced escape to the breakdown — never a
dead end, never an in-chat reveal.

## 2. Context (grounded 2026-07-19)

Current app behavior, verified live and in code:

- **No re-attempt exists.** `quiz_screen_reducer.ts:214-229` moves `answering →
  reviewing` on ANY graded submit; `FeedbackView` (banner, CORRECT ANSWER badge,
  why-correct/why-tempted/rule) renders immediately even on a wrong pick. The
  "coached" loop is a new concept for the reducer, not a modification.
- **"Reveal answer" is a submit alias.** `QuizView.tsx:248-262` — same `onSubmit`
  handler, ghost-styled. Deleting it removes a label, not a code path.
- **"Get a hint" shows rung 1 pre-submit** (`page.tsx:452-459`, `hintLadder[0]` or
  generic `socraticHint` fallback); the coach panel shows only rungs 2–3
  ("n of 2 used", `CoachPanel.tsx:123-129`, `HintLadderList.tsx:67-69`).
- **Ladder loading is already choice-keyed** (ADR-0035): `resolveHintChoiceLetter`
  + Effect 5 (`page.tsx:299-338`) load the Gen2 ladder for the picked wrong letter,
  falling back silently to the item-level (Gen1) ladder loaded at item-open.
- **Recording:** `AttemptRepo.record` (append-only: `correct`, `used_hint`,
  `chosen_letter`, `elapsed_ms`) then `scheduler.review(attempt)` (sole
  `skill_state` writer, FSRS) per submit — today exactly once per item.
- **Summary is aggregate-only** (`session_summary_vm.ts` reads stored
  `score_correct/score_total`); no per-item marks exist.
- **Three coach surfaces** (inline / drawer / fullscreen, `page.tsx:593-665`)
  share `use_quiz` + `quiz_screen_reducer` + `coach_thread_store`; flow logic must
  live there, never per-surface.

The v3 prototype spec (§0–§13) defines the target interaction; this spec translates
it to app seams and narrows it to what the app ships (see §10 exclusions).

**Clarified 2026-07-19** (Q1–Q4 in clarify pass): outcome persisted as a nullable
`resolution` field on the resolving attempt; session score becomes first-try-only
with outcome counts in summary; scheduler reviews only the first attempt per item;
ships behind a feature flag default-ON in dev, staged to prod.

## 3. Functional requirements (EARS)

Failure paths first.

- **FR-1 (no reveal before resolution — release blocker).** IF the current item is
  unresolved (not solved, not walked-through), THEN THE SYSTEM SHALL NOT render the
  correct letter, `why_correct_md`, `rule_md`, or any per-choice CORRECT-ANSWER
  marking on any surface, and no "Reveal answer" affordance shall exist anywhere.
- **FR-2 (no pre-commit help).** WHILE no letter has been submitted for the current
  item, THE SYSTEM SHALL show no hint affordance and no ladder content on any
  surface (item panel or coach panel); the coach panel shows idle copy in the
  spirit of "Commit to a choice — coaching starts from what you pick" and the
  free-text coach ask remains available.
- **FR-3 (wrong submit enters the ladder).** WHEN the learner submits a wrong
  letter L, THE SYSTEM SHALL stay in the answering loop (no feedback view), record
  the attempt, and present ladder rung 1 (pump) for L — resolved via
  `resolveHintChoiceLetter` (choice-keyed first; see FR-8 for fallbacks). Choices
  remain selectable for a re-pick.
- **FR-4 (learner-paced escalation, honest counter).** WHILE in the wrong-pick
  loop with rungs remaining, THE SYSTEM SHALL reveal the next rung only on
  explicit learner request, with an honest "n of 3" counter covering all three
  rungs (the pre-submit rung-1 display and the "n of 2" deeper-rung counter are
  retired together).
- **FR-5 (exhaustion offers exactly two actions).** IF all 3 rungs for the current
  wrong letter are revealed, THEN THE SYSTEM SHALL disable further nudges and
  offer exactly: "Let me try again" (clears the pick; rung count for that letter
  is retained) and the priced escape "Walk me through it" with adjacent cost copy
  ("The breakdown shows the answer — this one won't count as solved."). The
  escape SHALL NOT render in any other state.
- **FR-6 (priced escape resolves the item).** WHEN the learner activates the
  escape, THE SYSTEM SHALL resolve the item as `walked_through`, then render the
  feedback view in a visually distinct walked-through state (why-correct + rule +
  `why_tempted_md` for the last wrong letter); the coach conversation SHALL NOT
  contain the answer at any point in this transition.
- **FR-7 (letter switch restarts the ladder).** WHEN the learner submits a
  different wrong letter L2 after L1, THE SYSTEM SHALL load L2's ladder at rung 1
  with a fresh counter; resubmitting the SAME wrong letter SHALL be inert (no
  duplicate attempt row, ladder state unchanged).
- **FR-8 (ladder fallback, never a dead end).** IF no choice-keyed ladder exists
  for wrong letter L, THEN THE SYSTEM SHALL fall back to the item-level ladder;
  IF that is also absent, THEN to the generic Socratic fallback presented as a
  single-rung ladder whose exhaustion offers the same two FR-5 actions. Fallback
  is silent (no error surface) and never reveals.
- **FR-9 (correct submit resolves).** WHEN the learner submits the correct letter
  on any attempt, THE SYSTEM SHALL resolve the item (`first_try` if it was the
  first graded attempt, else `coached`) and render the feedback view with the
  matching result label ("Solved on first try" / "Worked through it with the
  coach" / walked-through per FR-6).
- **FR-10 (three-state outcome recording).** THE SYSTEM SHALL persist per item
  exactly one resolution ∈ {`first_try`, `coached`, `walked_through`} via a
  nullable `resolution` field on the resolving attempt record (additive; older
  rows stay null and read as legacy single-attempt semantics).
- **FR-11 (honest scoring).** THE SYSTEM SHALL count only `first_try` resolutions
  in the session score (`score_correct`); the summary SHALL show the three
  outcome counts with honest, non-judgmental labels; `walked_through` SHALL never
  be presented as solved.
- **FR-12 (mastery reviews first attempts only).** THE SYSTEM SHALL call
  `scheduler.review()` exactly once per item, on the FIRST graded attempt
  (unchanged signal semantics vs today); retry and escape events SHALL NOT
  produce additional reviews.
- **FR-13 (one flow, three surfaces).** THE SYSTEM SHALL implement the commit-first
  loop in the shared layer (`quiz_screen_reducer` / `use_quiz` /
  `coach_thread_store`) such that inline, drawer, and fullscreen coach surfaces
  render identical flow state with no per-surface behavioral forks.
- **FR-14 (feature flag).** WHERE the `commit_first_coach` flag is OFF, THE SYSTEM
  SHALL preserve current behavior byte-for-byte (instant feedback view, pre-submit
  hint, no retry loop); the flag defaults ON in dev/bypass and is staged to prod.

## 4. Data model / contracts

- **`Attempt` wire type gains `resolution?: "first_try" | "coached" | "walked_through" | null`**
  (additive, nullable — no migration; drizzle column + in-memory adapter parity).
  Not a trust-kernel type; no re-signing. Set only on the resolving attempt.
- **Escape resolution with no correct submission:** the escape records a resolving
  attempt row with `correct=false`, `resolution="walked_through"`,
  `chosen_letter` = last wrong letter (honest: the learner never produced the key).
- **Session score semantics change:** `score_correct` = count of `first_try`
  resolutions (was: count of correct submits — identical value for legacy
  single-attempt sessions, so no backfill).
- **No hint-bank change.** Served ladders, `_hint_bank.ts`, seed JSON, and the
  FR-E1 coverage ratchet are untouched.
- **Reducer contract:** `answering` phase gains coached-loop sub-state
  (`wrongLetters`, per-letter rungs revealed, `exhausted`); `reviewing` gains
  `resolution` for the three result labels.

## 5. Invariants & security boundaries

- Frontend Ring only — no `trust/`, `services/`, `components/` (Python), or
  `orchestration/` change; architecture invariants #1–#8 untouched.
- The Frontend Ring's own layering holds: ports (`hint_repo`, `attempt_repo`,
  `scheduler`) keep their interfaces except the additive `Attempt.resolution`;
  `scheduler.review` remains the sole `skill_state` writer.
- No new dependency; no live LLM in CI (ladder content is pre-authored bank data;
  the free-ask coach chat is the existing guarded SSE seam, unchanged).
- Leakage: ladder rungs are already leak-linted at generation (bank pipeline);
  this spec adds no new leak surface because no new content is generated.

## 6. Edge cases

- **Exhausted, then correct pick** → `coached` resolution; allowed and normal.
- **Escape after switching letters** → `why_tempted_md` keys off the LAST wrong
  letter (deterministic, matches v3 FBK-1).
- **Wrong letter with no Gen2 ladder AND no Gen1 ladder** → FR-8 single-rung
  generic fallback; exhaustion still reachable, escape still offered (never a
  dead end).
- **Resubmit of the same wrong letter** → inert (FR-7); no attempt-row spam, no
  scheduler noise.
- **Session resume mid-coached-loop** (tab close / route away): in-memory ladder
  state may reset to rung 0 for the current item; the attempt log keeps recorded
  attempts — acceptable loss, resolution semantics unaffected (first attempt
  already recorded ⇒ `first_try` no longer reachable for that item).
- **Timed test (`/learn/test`) and review mode:** timed test is out of scope
  (separate surface, no coach); review/drill/adaptive modes share the quiz page
  and get commit-first uniformly.
- **Legacy attempt rows** (`resolution=null`) → summaries derive outcomes with
  the legacy rule (one attempt per item, `correct` ⇒ first-try) — no fabricated
  outcomes (AP-6).

## 7. Non-functional requirements

- **Determinism:** all new logic is pure reducer/VM code — L1 vitest coverage;
  no live calls on any new path.
- **Reversibility:** flag OFF restores current behavior exactly (FR-14);
  `resolution` column is additive/nullable.
- **Latency:** ladder content is already client-loaded at item open + on pick
  (Effect 5); no new network round-trips.

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | reducer: wrong submit never yields `reviewing`; view: no correct-letter/why-correct render while unresolved; grep-level: no "Reveal answer" testid | L1 vitest | yes (frontend gate) |
| FR-2 | `QuizView` pre-submit renders no hint toggle; `CoachPanel` idle state shows no `HintLadderList` | L1 | yes |
| FR-3 | reducer `submitted(wrong)` → coached loop + ladder request for L; attempt recorded | L1 | yes |
| FR-4 | counter shows n of 3 across all rungs; rung reveal only on explicit action | L1 | yes |
| FR-5 | exhausted state: exactly two actions; escape absent at rungs 0–2 and pre-submit | L1 | yes |
| FR-6 | escape → `walked_through` resolution + feedback VM in walked-through state incl. `why_tempted_md`(last L) | L1 | yes |
| FR-7 | L1→L2 switch resets rung counter; same-letter resubmit is inert | L1 | yes |
| FR-8 | missing choice ladder → item-level; missing both → single-rung generic; exhaustion actions present | L1 | yes |
| FR-9/10 | resolution derivation: first-try / coached / walked-through; nullable legacy rows | L1 | yes |
| FR-11 | summary VM: score counts first_try only; three outcome counts present | L1 | yes |
| FR-12 | scheduler.review called once, on first attempt only, across retry + escape sequences | L1 | yes |
| FR-13 | shared-layer test: all three surfaces driven by identical reducer state (no per-surface branches on flow) | L1 | yes |
| FR-14 | flag OFF: reducer + views reproduce current snapshot behavior (regression suite still green un-forked) | L1 | yes |
| e2e | Playwright: commit → wrong → 3 nudges → escape → walked-through breakdown; and wrong → retry → coached solve | T1 (chromium smoke) | on-demand |

## 9. Definition of Done

- [ ] All FRs implemented; each test seen to fail first (red/green).
- [ ] Frontend gate green (`pnpm --dir frontend test` + typecheck) and `make check` green.
- [ ] Invariants §5 unbroken (`tests/architecture/` green — no Python surface touched).
- [ ] Flag OFF path verified byte-equivalent on the acceptance walkthrough.
- [ ] Live walkthrough on localhost matching v3 §12 steps 1–7 (app-scoped), screenshots pasted.
- [ ] `decisions.md` entry for the clarify choices (resolution field, first-try scoring, first-attempt review, flag).
- [ ] Actual command output pasted, not summarized.

## 10. Explicit exclusions (v3 prototype requirements NOT shipped in the app)

- **TRACE-1…4 ("Under the hood" annotation rail)** — prototype stakeholder
  artifact, not a product surface.
- **LEAK-1/2 runtime regex guard** — bank content is leak-linted at generation;
  the live coach chat keeps its existing server-side guardrails. No new client
  leak checker.
- **SUM-2 run-length chips** — summary ships outcome counts, not per-item chips
  (clarify Q2; chips are a later, separate slice if wanted).
- **SEQ-1 fixed 15-item `SESSION_ORDER`** — the app keeps its live scheduler
  (adaptive/drill/review); the prototype's fixed order was a demo constraint.
- **MOM-7 free-ask stub** — the app already has the real guarded coach chat.
