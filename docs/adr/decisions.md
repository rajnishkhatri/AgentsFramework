---
type: log
title: 'Lightweight decision log (intent debt, long tail)'
---

# Lightweight decision log

> Append-only, newest first. 2–4 lines per **small** decision: what was decided,
> the alternative rejected, and why. This is the low-friction sibling of the full
> ADRs — use a numbered ADR (`0000-template.md`) for big/structural decisions that
> need Context/Options/Rationale/Consequences; use this for the long tail of
> non-obvious-but-small choices that would otherwise go uncaptured. Lower the bar,
> capture more intent debt. (Playbook: Comprehension-Debt runbook, Part B.)

- 2026-07-13 — **Epic F: honest accuracy-trend Progress screen; projected score self-omits (D4 deferred).** Ship `/learn/progress` via one T1 translator (`progress_screen_vm`) + inline SVG `TrendChart` + horizontal mastery bar-rows; trend y = per-session accuracy from `listByLearner` (not `progressRepo`). Rejected: consuming orphaned `ProgressRepo.projected_score` (no honest write path — same gating risk as Epic E Tutorial). No ADR (pure composition). Spec/plan: [preact-parity-epic-F.spec.md](../plan/preact-parity-epic-F.spec.md) · [preact-parity-epic-F.plan.md](../plan/preact-parity-epic-F.plan.md) · brainstorm: [preact-parity-epic-F.brainstorm.md](../plan/preact-parity-epic-F.brainstorm.md).

- D-8 (2026-07-11): deferred to Epic E per D4 alternate declined. Adding "skill" to NAV_MEMBERSHIP without a live /learn/skill route re-opens the Q-6 trust-bug class Epic A closed. Epic E will land route + membership together. Alternate spec preserved at docs/plan/preact-parity-D4-skills-nav.spec.md. T-DES-D4 locked placement (coach→skill→progress; iPhone unchanged) in docs/plan/preact-parity-D4-skills-nav.impl.md for when E lands.

- 2026-07-11 — **D2 taxonomy: 6 canonical bucket labels.** Rhetoric · Usage · Punctuation · Organization · Sentence Structure · Conciseness. Source: `PreAct/UI-Design/design-spec.md:62-69`. Renamed display `name` only: Grammar & Usage → Usage, Rhetorical Skills → Rhetoric, Style → Conciseness in `_dev_seed.ts` + e2e fixtures. Dashboard `BucketCard` gains a leading 11×11 rounded-square dot (`border-radius:4px`, prototype exact) tinted by existing `--accent` — not the plan's 8px circle. CSS token ids stay `--color-bucket-*`. No ADR (content + view). Spec: [preact-parity-D2-taxonomy.spec.md](../plan/preact-parity-D2-taxonomy.spec.md).

- Q-1b (2026-07-11): DEFAULT_TARGET_COUNT stays at 30. Rationale: ADR-0023 locked 30 as the adaptive-loop mastery signal; PreAct/UI-Design/design-spec.md:143's "Session = 10 items" is a sample-session narrative, not an acceptance criterion; FR-11 end-early-on-exhaustion already keeps thin-skill drills correct. Rejected alternative: move to 10 (prototype fidelity + full drills on today's thin bank without S3-pre). Docs-only — no code, no ADR-0023 amend. Framing: [preact-parity-D3-session-length.impl.md](../plan/preact-parity-D3-session-length.impl.md). Spec: [preact-parity-D3-session-length.spec.md](../plan/preact-parity-D3-session-length.spec.md).

- 2026-07-10 — **Sprint D1: extend QuizItemVM instead of introducing QuizFrameVM.**
  D1 (Quiz session-frame chrome, Q-7/Q-8/Q-9) extends `QuizItemVM` with two
  nullable fields (`skillName`, `accentVar`) rather than introducing a new
  `QuizFrameVM` translator + view slot. Why: two nullable fields is not a new
  abstraction; the frame's only cross-cutting derived data (Q-7's skill join) is
  per-item, so its home is the item VM. Q-8 (tally) and Q-9 (`started_at`) are
  read directly from React state (page-owned), so they need no VM. No G1 gate;
  this log is the correct weight (per root AGENTS.md). Rejected alternative: a
  separate `QuizFrameVM` mirroring ADR-0025's coach surface VM — deferred until
  the item VM crosses ~8 fields (would need its own G1 ADR at that point).
  Spec/plan: [preact-parity-D1-quiz-frame.spec.md](../plan/preact-parity-D1-quiz-frame.spec.md).

- 2026-07-10 — **Epic D — Stage-1 premise audit corrections (Sprint D0).** Five epics-doc / VISUAL-report framings were **refuted** against the working tree; D0 corrects the record (docs-only) before D1/D2/D3 enter `sdd-spec`. Spec/plan: [preact-parity-D0-correct-record.spec.md](../plan/preact-parity-D0-correct-record.spec.md); board: [preact-parity-sprint-board-D.md](../plan/preact-parity-sprint-board-D.md); audit: [preact-parity-epic-D.brainstorm.md](../plan/preact-parity-epic-D.brainstorm.md).
  - **P3 (Q-7):** not a view-only chip — wire `Question` has no `skill_name`/`accent_var` ([`engine_entities.ts:61-64`](../../frontend/lib/wire/engine_entities.ts:61)); those live on `Skill` ([`:34-44`](../../frontend/lib/wire/engine_entities.ts:34)). Fix = hook + translator + view.
  - **P8 (Q-9):** "dismissible timer" misleads — no clock renders today (`components/quiz/` timer/Clock/elapsed = 0 UI hits). Reframe = *collapsible / off-by-default*; `elapsed_ms` capture already correct ([`session_summary_vm.ts:60-65`](../../frontend/lib/translators/session_summary_vm.ts:60) / A2 triage).
  - **P10 (Q-1b):** not a code sprint by default — parity report §Q-1b leaves "is 30 intended for adaptive?" open. D3 = decision-first via this log; upgrades to code + ADR-0023 amend iff `DEFAULT_TARGET_COUNT` changes.
  - **P14 (D-8):** not a free `NAV_MEMBERSHIP` add — `screen("skill", …, comingSoon: true)` already at [`nav_model.ts:75`](../../frontend/components/shell/nav_model.ts:75) but `/learn/skill` 404s (Epic E). Pre-E enable = dead nav item (Q-6 class). **Default = defer to Epic E**; alternate = optional D4 `comingSoon`-gated add.
  - **P15 (X-4):** not an independent sprint — same 6-name list as `D-3b` (parity report §X-4 says "see D-3b"). **Absorbed into D2.**
  - **Ladder:** `D0 → { D1, D2, D3 }` (parallel-independent); **D4 optional**. D-8 defaults to deferred to Epic E.
  - **Rejected:** (i) Q-7 as view-only chip render; (ii) Q-9 as dismissible-clock UI; (iii) Q-1b as a code sprint by default; (iv) D-8 as a free `NAV_MEMBERSHIP` add; (v) X-4 as an independent sprint.

- 2026-07-10 — **C2 misconception field lives on the `Question` wire (D4 direction).** Not on `Skill`, not on `Attempt`, not derived at render. Rejects D5 (Coach-runtime marker) and any Summary-time LLM synthesis. Authored on the `test_item` bank row; mapped through `TestItemQuestionRepo`. ADR-0027. Spec: [preact-parity-C2-summary-payoff.spec.md](../plan/preact-parity-C2-summary-payoff.spec.md).

- 2026-07-10 — **C2 misconception seed-count = probe-based (K = 47).** Content pass authored 47 rows where existing `why_tempted_md` already implied a one-line misconception; remaining bank rows emit `misconception: null`. Spec §12 Q2 / §13 #4.

- 2026-07-10 — **C2 FLAG-5 wire deferred until continuity-fixes lands `readActiveQuiz`.** Substrate export count was 0 at implement; no interim shim; `coach/page.tsx` untouched; no `validate_epic_ab.spec.ts` edit. Soft-gate arch test locks the absent-import posture. Spec §12 Q1 / §13 #3.

- 2026-07-10 — **C2 self-correction signal = attempt-index half-split.** First-half incorrect + second-half correct + no second-half incorrect on the recommended skill. Derived from `misses` ∩ `servedQuestionIds` + `served \ misses` (no new port). Spec §12 Q4 / §13 #2.

- 2026-07-10 — **C2 framed-title threshold = 0.6.** Score ratio at which the neutral title flips to "Nice work — you found the pattern." Hardcoded `SUMMARY_FRAMED_TITLE_RATIO` in `session_summary_vm.ts`. Prototype §5.5 uses 7/10 (0.7); 0.6 is a deliberate undercut to avoid over-praise. Spec §12 Q3 / §13 #1.

- 2026-07-10 — **Drill `?focus=` pins item draw to that skill (FR-A5).** Session stored `skill_focus` but `openQuizItem` still called adaptive `scheduler.next`, so after missing skill A, a skill-B bucket drill kept serving A — Home “misses” looked like only the first skill. **Decision:** drill mode draws via `QuestionRepo.nextReviewed(subject, skill_focus, servedIds)` only. **Rejected:** leave the documented “honest gap”; filter misses by last session skill.

- 2026-07-10 — **Outstanding misses = latest attempt incorrect (clears on later correct).** After review 3/5 correct, Home still showed 5 — `misses()` returned every historical incorrect row. **Decision:** `listMisses` projects outstanding only (latest attempt per `question_id` is wrong); later correct clears from badge + review pool. Append-only history unchanged. **Rejected:** keep lifetime miss history on the badge.

- 2026-07-10 — **Review complete: hide Keep practising (no miss-pool over-run).** After the last miss, Keep practising called `openQuizItem` and threw “no unserved missed questions”. **Decision:** when `mode=review` and `progressVm.complete`, hide quiz-next; promote See summary to the primary CTA. Adaptive/drill still over-run via Keep practising (S5 FR-7). **Rejected:** fall through to FSRS adaptive; route Home automatically.

- 2026-07-10 — **Dashboard Review misses (N) = unique question ids (match review pool).** Badge used `misses.length` (raw attempts) while review `target_count` used unique ids → “Review my misses (4)” then “1 of 3”. **Decision:** `reviewMissesCount = uniqueMissQuestionIds(misses).length`. **Rejected:** inflate review target to raw attempt count (would re-serve the same item).

- 2026-07-10 — **Review my misses → `?mode=review` miss pool (FR-A6/C5).** Dashboard linked to plain `/learn/quiz` (adaptive 30) while the count was real. **Decision:** link `/learn/quiz?mode=review`; `resolveQuizOpenMode`; `openQuizSession` sets `target_count` to unique miss count; `openQuizItem` draws from `AttemptRepo.misses` (not FSRS `next`) for review sessions. Deep-link clears resume pointer. **Rejected:** leave as known gap only.

- 2026-07-10 — **Coach pin questionId change ⇒ fresh LangGraph thread + clear turns.** Manual walk: Ask on Q2 worked; after Next→Q3, chip “Give me a similar item” got a cold-start reply while chrome showed Q3 — same `thread_id` kept Q2 message history and the vague chip read as plain chat. **Decision:** `setCoachPin` when `questionId` changes resets `threadId`+`turns` (next ask mints a new server thread with current `coach_context`). Same-item pin/mode updates still keep the thread (FR-J3 panel↔screen). **Rejected:** keep one session-long thread with only a system-prompt preamble (history still dominates vague chips).

- 2026-07-10 — **Desktop Quiz syncs coach pin on every item (sidebar Coach ≠ cold/stale).** Ask-the-coach already called `setCoachPin`; sidebar Coach did not, so first open was cold or stuck on Q1. **Decision:** desktop quiz page writes the same live-item pin/mode as iPad `CoachPanel` (via `toQuizCoachPin`) whenever answering/reviewing. Cold `/learn/coach` with no quiz still honest-absent. **Rejected:** hydrate only on coach mount from `readActiveQuiz` (pointer lacked skillId; quiz-side sync matches panel).

- 2026-07-10 — **Epic A/B continuity: Back from Feedback resumes reviewing (same N), not answering.** Manual FLAG-4 walk: Ask-the-coach leaves Feedback with a post-grade tally; remounting into answering made progress `gradedTotal+1` (Q3→Q4) and risked re-submit. **Decision:** stash `verdict`+`answeredLetter` on the active pointer when `phase=feedback`; `resume_item` restores **reviewing** so Question N and Next stay. Answering-only leave still resumes answering. **Supersedes** same-day “always → answering” note. Spec: [epic-ab-continuity-fixes.spec.md](../plan/epic-ab-continuity-fixes.spec.md).

- 2026-07-10 — **Epic A/B continuity: resume always → answering; stash score on active pointer.** FLAG-4 remount restores the left `questionId` into `answering` (not reviewing) so e2e/Back only need the stem. Active pointer also stores `{correct,total}` so resume never fabricates `0/0`. **Rejected:** resume into reviewing; URL `?session=` for Back (clarify C1 option B). Spec: [epic-ab-continuity-fixes.spec.md](../plan/epic-ab-continuity-fixes.spec.md). **Superseded** by feedback-resume decision above.

- 2026-07-09 — **Coach-pass C4/C5: honest opener + green-span from `<u>`.** C4 option A — one opener only when pin + real misses + empty transcript (cite `N`, never “of last 5”); else empty until ask. C5 option A — Feedback recap = `context_html` with `<u>` → success color (FR-A7); no `<u>` → plain sentence, no invented highlight. Spec: [preact-parity-B-coach-pass.spec.md](../plan/preact-parity-B-coach-pass.spec.md).

- 2026-07-09 — **Coach-pass C3 layout = prototype surface variants (desktop rail ≠ iPad).** Spec §5.4/§9 + iPad flow: desktop `/learn/coach` = left context rail + right chat/chips/composer; iPad standalone Coach = **header-strip** context (no left rail), centered ≤600px; iPad Quiz = existing **split** right `CoachPanel` (stacked chrome + nudges + composer, same thread). Chips stay with composer. **Rejected:** one stacked layout everywhere; forcing desktop two-column onto the quiz panel. Spec: [preact-parity-B-coach-pass.spec.md](../plan/preact-parity-B-coach-pass.spec.md); prototype: [PreACT-English-Coach-Spec.md](../../Eng-coach-ui-design/PreACT-English-Coach-Spec.md).

- 2026-07-09 — **Coach-pass C1/C1a: pin on `coach_thread_store`; wire = design `coach_context`.** Pin transport = **option C** — extend existing FR-J3 singleton with `pin: {questionId, skillId, label} | null` (not URL / not sessionStorage). Full `Question` loaded at ask via `QuestionRepo.get`. Wire keeps design §4.1 shape: advisory `mode` + ids + `question` + optional `misses_aggregate{skill_id,missed}` (**omit `window`**) + optional `mastery_snapshot` from `LearnerReadRepo`. `resetCoachThread` clears pin. Label stays chrome-only (never prompt paste). **Rejected:** URL pin; storing full Question on the store; inventing a window denominator. Spec §4: [preact-parity-B-coach-pass.spec.md](../plan/preact-parity-B-coach-pass.spec.md).

- 2026-07-09 — **Coach-pass: store advisory `mode` beside pin (not on C1a pin schema).** Feedback→Coach and Panel write `setCoachPin(pin, mode)`; standalone `/learn/coach` reads `snap.mode` for chrome D5a + `useCoach({ mode })` / `sendCoachAsk` default. Keeps pin `{questionId, skillId, label}` unchanged; clearing pin resets mode to `pre_submit`. BFF still overwrites (ADR-0012). **Rejected:** hardcoding `pre_submit` on the coach page after Ask-the-coach; stuffing `mode` into the pin object (would reopen C1a).

- 2026-07-09 — **Epic B Stage-5 replan: Option C full Coach pass + one umbrella spec.** After B1 shipped slots-only chrome, parity report still showed empty-shell Coach vs prototype two-column workspace. **Decision:** finish Coach in one remaining pass — **B1.5** (left rail + right chat + C-1 Back/Wrap-up) → **B2** (Ask-the-coach + green-span; pin fills C-3/C-4) → **B3** (`coach_context` + honest opener; **required**, no longer slip-default). Spec as one umbrella [`preact-parity-B-coach-pass.spec.md`](../plan/preact-parity-B-coach-pass.spec.md); cold `/learn/coach` keeps honest-absent pin; C-5 stays D5a. **Rejected:** A layout-only then wait; B jump-to-B2 and defer layout; separate B2/B3 specs. Board: [preact-parity-sprint-board-B.md](../plan/preact-parity-sprint-board-B.md).

- 2026-07-09 — **Sprint B0 (Epic B): D5a — coach mode UI is display-only 3→2, never a free learner switcher.** Prototype C-5 shows three labels (In-drill Socratic / Post-answer deep-dive / Misconception summary); runtime has two marker-derived modes (`pre_submit` / `post_feedback` via `deriveCoachMode` — ADR-0012; client `mode` is advisory and never trusted by the sanitizer). **Decision:** map the three labels onto the two derived modes for chrome only (`pre_submit`→Socratic active; `post_feedback`→deep-dive active; Misconception always inactive in B1). Activating a non-authoritative label MUST NOT change derived mode, run-body `mode`, or BFF sanitizer behavior. **Rejected:** D5b free 3-way switcher (fights ADR-0012); inventing a third derived mode now. Spec: [preact-parity-B1-coach-chrome.spec.md](../plan/preact-parity-B1-coach-chrome.spec.md); board: [preact-parity-sprint-board-B.md](../plan/preact-parity-sprint-board-B.md).

- 2026-07-09 — **Sprint B0 (Epic B): C-4 history line is a trust signal — real skill-scoped misses or honestly absent; never placeholder "3 of last 5".** When a current item (with `skillId`) is pinned, count unique miss `question_id`s whose `Question.skill_id` matches (via `AttemptRepo.misses` + `QuestionRepo.get` join — Attempt has no `skill_id`). Copy like `Sees your history: N misses on <skill>`. No pin / load failure / empty → omit the line (honest absent). **Rejected:** fabricated demo counts; a fake "of last 5" window without a real computed window. AP-6. Spec: [preact-parity-B1-coach-chrome.spec.md](../plan/preact-parity-B1-coach-chrome.spec.md).

- 2026-07-09 — **Sprint A1 (Q-6): "Reveal answer" = gated submit alias (D6+D1), not an in-place letter reveal.** Prototype Reveal shares `submit` and routes to Feedback ([Prototype.dc.html:114,242](../../PreAct/UI-Design/English%20Coach%20-%20Prototype.dc.html)); Feedback already teaches the letter (UI FR-E1/E4). **Decision:** amend [preact-english-coach-ui.spec.md](../plan/preact-english-coach-ui.spec.md) FR-D6 + add FR-D6a; wire `quiz-reveal` → same `onSubmit` as Submit, disabled when no selection; `QuizItemVM` stays non-revealing (no `answerLetter`, no reducer `revealed`). Cite the **UI** spec by path — engine FR-D6 is a different requirement (A0 ID-collision caveat). **Rejected:** board Options 1/3 (in-place post-submit letter + VM field — non-prototype, second answer surface); D2 remove-the-button (deferred). Spec/plan: [preact-parity-A1-reveal.spec.md](../plan/preact-parity-A1-reveal.spec.md).

- 2026-07-08 — **S3 (bounded-session) clarify: the "30 unique per session, no repeat" answer REFUTED the "just store a count" premise → enlarge S3 to field + within-session uniqueness; keep the visible done-state in S5; flat-30 is gated on bank growth.** The clarify answers ("all questions unique … must not review the same question twice per session") turned S3 from a nullable-field add into a **new scheduler capability**: `FsrsScheduler.next` → `QuestionRepo.nextReviewed(subject, skillId)` takes **no exclusion set** ([question_repo.ts:27](../../frontend/lib/ports/engine/question_repo.ts)), so a session re-serves the same item today. **Decision (user-gated): (1) enlarge S3** to ship the `target_count` field AND a served-ids exclusion seam (`excludeIds?` on `nextReviewed`/`EngineDb.nextReviewedQuestion`, `servedIds?` on `Scheduler.next`, all optional → backward-compatible) in one spec + ADR-0023; the *visible* "review is finished" terminal + retake stay S5. **(2) default = flat 30 for every mode**, stored as `content_string` rows (policy-as-data, reusing the ADR-0022 plane, not a new table). **(3) gate on data:** a 30-unique **drill** is impossible for thin skills today (s-sent 23, s-org 24 reviewed items < 30), so S3's implement phase is **blocked by S3-pre** — generate + cascade-promote +19 items (rhet +2/style +4/org +6/sent +7 → every skill ≥ 30) and raise the ADR-0022 coverage floor to 30. **Rejected:** (A) keep S3 = field-only + a separate S3b for uniqueness (cleaner sprints, but a bounded session still repeats until S3b — the user wanted the coherent no-repeat unit now); (B) fold S5's done-state in too (largest single sprint, delays any gate); (C) drill = min(30, items available) per-skill cap (honors no-repeat without a bank dependency, but the user chose a flat 30 everywhere over a variable drill length); (D) smaller drill target (10) to fit the thin banks (sidesteps growth but puts 30-unique-drill off the table by design). Served-ids are **ephemeral + caller-owned** (derived from the session's `attempt` rows, passed per `next()` call) and NEVER written to `skill_state` — the adaptivity source of truth stays pure (FR-A2). See [preact-quiz-target-count.spec.md](../plan/preact-quiz-target-count.spec.md) §2.1.

- 2026-07-08 — **T8 hint gaps on atomic items: reword the ITEM (not a waiver, not a hand-authored rung) — and the last stubborn gap traced to `why_correct_md` seeding a recital leak.** After live hint generation, 4 of 171 items couldn't get a full 1-2-3 ladder: their missing rung leaked the answer because the item is atomic (a single irregular-verb swap gives a rung-1 probe nothing to anchor on but the answer verb; a bare cause-effect pair makes the rung-2 concept name the key). **Decision: reword the item so a non-leaking rung is authorable; keep zero waivers.** Two false starts recorded as intent debt: (a) editing `context_html` did nothing — `_row_id` hashes `subject|stem|answer` only, so the id (and the generator's leak) didn't move; the leak is anchored on the STEM's framing, so the fix is a stem reframe (e.g. "which verb form is correct" → "which choice fits the time the sentence describes", giving rung 1 a timeframe anchor instead of the verb); reworded items re-promote through the T7 key gate (new ids, 0 quarantined). (b) hand-authoring the one un-generatable rung-2 and stamping it `claude-session-authored@leakage-gate-verified` PASSES the frontend provenance regex `/^[^@\s]+@[^@\s]+$/` but SUBVERTS its intent (FR-B2 = "never a hand-edit marker" — the `@` is meant to prove a real cascade run) → reverted. The real fix: the transition item's rung-2 leaked because `why_correct_md` **stated the relationship** ("the second sentence is the result of the first"), and the generator recited it (the why-correct-recital leak class in `check_rung_leakage`). Reframing `why_correct` to METHOD-language ("read what the second sentence does to the first, then match the transition") — `why_correct` is not hashed, so the id is stable — produced a clean, genuinely cascade-earned ladder. **Also surfaced a latent contradiction in the pre-existing hint tests (commit `07a7dd5`):** the FR-E1 `ladderGaps` ratchet HONORS `{question_id, rung, reason}` waivers, but the FR-C1 serving test asserts every item serves exactly `[1,2,3]` with NO waiver awareness — so a *served* bank effectively cannot use a hint waiver; a real rung must exist. This is why reword-not-waive was the only path that satisfies both gates. **Rejected:** an FR-A3 waiver (fails the FR-C1 serving assert); hand-authored rung with honest `@`-form provenance (still a hand-edit wearing cascade clothing; and it would need the serving test relaxed); relaxing/patching the FR-C1 serving test (not mine to weaken — a security-adjacent guard I didn't write).

- 2026-07-08 — **T7 floor recovery: fix genuinely-broken items, then re-solve the rest on the CAPABLE tier — never dumb items down to satisfy a weak solver.** After the tier fix, run-2 promoted 161/192 (< the 170 floor), shortfall now in d2/d3. Triaged all 31 quarantines by live re-solve + open coding: **~23 were fast-tier FALSE-NEGATIVES on correct items** (gpt-4o-mini is weak at mid-difficulty parallelism/agreement/modifier/register and gets distracted by the deliberately-seeded errors elsewhere in a passage), 3 genuine defects, ~4 ambiguous, 1 nondeterministic. **Decision (per user): fix the 6 real defects/ambiguities, then re-promote at `--capable-difficulty 2`** so every d2+ item is graded by gpt-4o in-cascade and the good items promote honestly. Run-3: **171 promoted, 21 quarantined, 176 capable calls**, 32/32 standards preserved. Establishes **d2 as the honest fast-tier ceiling** for this bank (gpt-4o-mini caps out below d2 on these skills). The 6 fixes were real bugs, not solver-appeasement: a stem that said "plural subject" over a singular subject; a NO-CHANGE item with no correct answer (re-keyed); a muddled cause-vs-concession key; and 3 ambiguous items where a distractor was a second defensible answer. **Rejected:** rewording the ~23 clean items to match the weak fast solver (that WEAKENS the bank — teaches to a bad oracle; the items are right, the solver is wrong); raising `--capable-difficulty` globally to 2 on the *whole* corpus without triage (heavier spend, and it doesn't fix the genuine defects — a bad item stays bad on any tier); accepting 161 and amending the floor (leaves real defects shipped and 23 good items wrongly quarantined). Fold method chosen: one clean full re-run (not manual row-splicing of the 17 recovered rows) so all rows share one coherent `<model>@<run_id>` provenance and the promoted file is a single artifact.

- 2026-07-08 — **T3 tiered-solver defect: the `--capable-difficulty` knob was DEAD CODE because `_solver_view` strips `difficulty` — fixed route-before-view (the cascade hands the solver the FULL item; the solver projects).** The knob routed on `item.get("difficulty")` in `_make_tiered_solver`, but the cascade called `solver(_solver_view(raw_item))`, and `_solver_view` returns only `context_html`/`stem_md`/`choices` (answer-blindness) — so difficulty was always `None`, the `isinstance(difficulty, int)` guard never held, and **all 82 d>=4 items ran on the fast tier** (T7 run-1 log: 384 fast / 0 capable). The unit tests passed the whole time because they called `_make_tiered_solver` directly with a dict that *had* difficulty — the defect lived entirely in the cascade→solver integration the units never exercised. **Decision (user-chosen among two): route on the raw item BEFORE the view.** The `Solver` protocol now receives the full item; `run_test_item_cascade` calls `solver(raw_item)`; each real solver applies `_solver_view` itself before `render_prompt`. The router sees difficulty; the MODEL still never sees the key/rationale (answer-blindness moved to `_solver_view`, its true boundary). Three answer-blindness tests re-pointed from the incidental call-arg onto `_solver_view` directly (STRONGER — pins the projection function), plus a new `test_cascade_hands_solver_the_full_item_for_tier_routing` that closes the exact unit/integration gap that let this ship. **Rejected:** adding `difficulty` to `_solver_view` (simplest, one line, but widens what the independent solver's VIEW carries — a purity concession on the ADR-0012 "solver sees stem+choices only" rule, even though difficulty isn't answer-bearing; route-before-view keeps the view minimal). Twin-defect lesson recorded: a knob unit-tested in isolation with hand-built inputs can be dead in production if the real caller reshapes the input first — the integration test is the one that matters.

- 2026-07-08 — **Bank verified against the DECIDED coach rules (ADR-sourced), not an ad-hoc checklist — found + fixed 3 answer-revealing stems; codified a stem-leak guard.** The deterministic `code-review` skill cannot see item pedagogy (bank JSON = `language=other`), so the bank was checked against a 10-rule checklist extracted from the governing records: ADR-0015 (cascade contract: schema-parse → independent-solver answer-key gate → duplicate; `reviewed` earned only in-cascade), ADR-0008 (answer-leakage is a FIRST-CLASS penalized axis; per-criterion justification), ADR-0012 (the four answer-bearing fields `{answer_letter, per_choice_rationale, why_correct_md, why_tempted_md}`; pre-submit = no letter/label reveal; the repo's deterministic predicate `components.hint_leakage.check_rung_leakage` defines the four literal leak classes), ADR-0022 (standard_id∈1..32, band-legal, skill==app_skill), Phase B FR-8/9 (full payload every row, matrix). **9/10 rules passed; R4 failed:** 3 stems named their own correct answer — row 69 ('...word for two **coaches** correctly?' key 'coaches'), row 148 ('...expresses **honoring**...' key 'honor'), row 153 ('...most **precise** single word...' key 'precise') — a pre-reveal that hands the learner the key before reasoning. **Detection reused the repo's own leak predicate** (run over each stem as if it were a pre-submit rung) PLUS a lexical key-in-stem scan that caught row 148 outside the predicate's ±25/45-char keyword window. Fix: reworded each stem to describe the task without naming the answer (post-fix assertion: key label absent from stem). **Guard:** new pre-flight `test_stem_does_not_reveal_the_answer` applies both nets to every row, proven non-vacuous. Rejected: writing my own leak heuristic (the repo already has the ADR-0012-blessed one — reuse keeps ONE definition of "leak"); treating stem-reveal as acceptable because stems aren't hint rungs (the no-reveal principle is about the LEARNER seeing the answer early, which a self-revealing stem does regardless of channel).

- 2026-07-08 — **Phase B bank review response: 2 s-org transition items rewritten for redundancy; `rule_type` taxonomy deferred to a D5 spec (no field yet on this branch).** External review of the 164-row Phase B bank raised three points; adjudicated against the data. **(1) Alleged broken key on the "Ella … In contrast … best time ever" item (ans B "As a result") — REFUTED:** key, `why_correct_md` ("the second sentence is the **result**"), and per-choice rationale ("cause and effect") are internally consistent and correct; the reviewer likely conflated it with the "…; consequently, → nevertheless" concession item. No change. **(2) Item-level redundancy — CONFIRMED + fixed:** 3 s-org items shared the rotating rule "Name the [real/actual] relationship (…) before picking a transition", differing only in which relationship was the answer (time/contrast/result). Kept the d2 canonical exemplar; rewrote the two d1 items to distinct sub-skills — redundant-connector (transition wrong because the clause already states the cause) and additive-position/register (sentence-initial "also" vs a full "in addition" opener). Both stay std 1 / d1 / s-org, so the bucket holds at 25 and matrix floors are untouched (commit `bb12315`). **(3) `rule_md` type-inconsistency (fact vs procedure vs meta) — CONFIRMED, the load-bearing point:** the rule field is a genuine strength (a worked heuristic most banks lack) but its type is only implicit in prose, and the types cluster by skill (s-punc→fact, s-rhet→meta, s-style→procedure). That type determines *when* a coach surfaces the rule (fact → after a wrong answer; procedure → at the decision point; meta → before reading choices). **Decision: spec it as D5 ([act-english-rule-taxonomy.spec.md](../plan/act-english-rule-taxonomy.spec.md)), do NOT implement mid-T6.** Adding a typed `rule_type` enum touches the wire schema and overlaps D4's emitter reopening, so it rides D4 (emitter grows `standard_id` + `rule_type` once, not twice). **Rejected:** folding the field into T6 now (schema change outside the current spec, bloats the authoring diff); logging taxonomy as authoring-guidance-only with no machine field (loses the coach-routing signal the whole point depends on); letting the cascade Jaccard gate absorb the redundancy at T7 (fires too late + doesn't fix the shared-rule pedagogy, only surface overlap).

- 2026-07-06 — **Item-bank Feature A pivots generate-mode → Claude-authored seed through the EXISTING `--import-seed` promotion; solver = repo fast-tier** ([ADR-0021](0021-bank-backed-practice-scheduler.md) increment; [spec](../plan/coach-item-bank-live.spec.md) FR-A*). The user asked to substitute in-session Claude reasoning for the live generator run. **Split the roles:** Claude authors the item *content* (12–18 items, all 6 skills, full teaching fields) as a committed `reviewed=false` seed — but `reviewed=true` stays cascade-earned (ADR-0015 clause 5): the seed rides the test01-importer precedent (`generate_test_items.py --import-seed` → `promote_seed`), where the only live step is the independent answer-key solver (~1 short fast-tier call/item, cents; key + rationale withheld per FR-C3). **Rejected:** Claude self-certifying its own keys (self-asserted review — the exact defect the gate exists for; in-session "withholding" is impossible); a fresh-subagent solver (zero API keys but same-family author+solver = ADR-0015's shared-misconception risk at max, plus a new replay driver); human blind-solve (most independent, but ~15min user effort + a provenance stretch). Consequences: the `--skill` driver flag and the `test_item_generator.j2` teaching-fields emission are **deferred** to a future real-generation increment (import mode renders no generator prompt; a future generate run without the .j2 update fails closed at the schema stage). Promoted rows carry the promoting run's `<model>@<run_id>` stamp (the test01 precedent); authorship lineage = the committed authored seed + `.impl.md` evidence.

- 2026-07-06 — **Coach golden-regression gate (Phase-5 task 5.3): floor+zero-flip on the COMMITTED runs, reuse the certified evaluator, `meta/` home, no new ADR.** The gate (`meta/coach_regression_gate.py` + `scripts/coach_regression_gate.py`) recomputes the ADR-0019 floor from the 3 committed `recert_labels_fw_run{1,2,3}.jsonl` and fails on floor breach / cross-run flip / malformed artifact. **Decision A — reuse `evaluate_coach_enable_gates` per run** (the certified floor logic verbatim) rather than re-wire `coach_confusion`→`tnr`/`≥`; keeps ONE source of truth and dodged a `*_min` threshold-key trap (Analyze finding). **Decision B — the ADR-0019 floors ARE the reference; no pinned-baseline 2σ delta** (`meta/drift.py detect_performance_drift` is the drop-in when live traffic gives a distribution — a later task; the 3-run sample can't support a variance model). **Decision C — abstention handling (FR-5b, surfaced by the gate itself):** run3's `R-CLEAN-29` has `judge_leak=null`/`confusion="abstain"`; it is DROPPED from the confusion denominator + the flip check exactly as the cert scored it (46/47, still ENABLE), not treated as malformed. **Decision D — no CI/Makefile change:** the always-on pytest test rides `pytest tests/` (both `make check` and CI), and `eval_regression_gate.py` (the mirrored pattern) has no dedicated CI step either, so a coach-only step would be an inconsistent one-off. **No new ADR** — the gate ENFORCES the existing ADR-0019 decision (references it), adds no abstraction. Rejected: extending `eval_regression_gate.py` (its substring-pass-rate model ≠ verdict-confusion; G1 — a shared base earns nothing). Bundle: `docs/plan/coach-regression-gate.{spec,plan,tasks}.md`.

- 2026-07-06 — **Coach re-cert judge host REVERSED: glm-5.2 on Z.ai → glm-5.2 on Fireworks AI** (structural; full record in [ADR-0019](0019-fireworks-host-adapter.md)). The line below (2026-07-06 "(2) Re-cert model = glm-5.2 … reads `GLM_API_KEY`") chose glm-5.2 on Z.ai; the model choice stands, but the **host** moves to Fireworks because Z.ai's serving stalls (>180s hangs on random rows) break the FR-9 zero-flip requirement — a serving problem, not a model problem (external research + five-probe scoreboard in [ADR-0019](0019-fireworks-host-adapter.md)). Z.ai stays a registered host; only the certified coach judge moves. Operator runbook updates to `MODEL_PROFILE_SET=fireworks COACH_JUDGE_MODEL=glm-5.2-fireworks FIREWORKS_API_KEY=… python -m scripts.run_coach_calibration …`.

- 2026-07-06 — **PedagogyJudge/GraderJudge retry transient provider errors (bounded, 3 attempts); parse failures are NOT retried; AP-6 still holds** (coach C1 re-cert abstain fix; `components/subject_coach_judges.py`). The first working-key glm-5.2 re-cert abstained on 5/47 rows with `provider error; verdict undecidable`, yet a 20-call diagnostic at the same 90s timeout was **20/20 ok (max 8.6s)** — so the failure is an **intermittent per-call exception on the heavy thinking-mode judge call**, not a rate-limit or fixed-timeout cutoff (timeout/pacing had nothing to act on; the user's first instinct to raise those was evidence-ruled-out by the probe). Wrapped **only** the provider `invoke` in a retry-with-backoff (0.5s·2^n, `_MAX_ATTEMPTS=3`); the JSON parse is deterministic so a malformed verdict is **not** retried (would just burn calls). Fail-closed invariant preserved: exhausted retries → `None`, never a fabricated verdict / defaulted `answer_leakage=False` (AP-6). `_sleep` is an injected param (default `asyncio.sleep`) so the 3 red-first L1 tests (recover-after-1-fail, exhaust→None, parse-not-retried) run without waiting and with zero live calls (TAP-2/TAP-4). Rejected `tenacity` (a new dep = ⚠️ Ask-first, for a 6-line loop) and rejected retrying the whole `_verdict` incl. parse (masks deterministic schema bugs as flakiness). Motivated by the [ADR-0018](0018-subject-coach-rubric-specificity-revision.md) exit bar: abstain-noise makes the FR-9 zero-flip TNR non-comparable across replays (each run scored a different clean subset), so near-zero abstains are a prerequisite to *reading* the re-cert, not a metric change.

- 2026-07-06 — **Coach re-cert freeze exposes a per-build `--row-floor`; the α gate (not the 200-row heuristic) is the non-provisional guarantee for a fresh authored split** (fresh-recert [spec](../plan/coach-fresh-recert-split.spec.md) FR-3/FR-7; Task B4-pre). `scripts/assemble_coach_goldset.py` had two seams dormant through round-1 (E6): `--rubric-version` was parsed but never threaded into `build_coach_goldset_manifest` (would silently stamp `coach_rubric_v1_revised` → FR-7 fail), and `row_floor` was hardcoded at 200 in the manifest builder, so the 47-row recert split was forced `provisional=true` → the cert short-circuits `REFUSE_PROVISIONAL` (FR-3 fail). Threaded `rubric_version` + `row_floor` through `build_rows → build_coach_goldset_manifest` and added a `--row-floor` CLI arg; the recert freeze uses `--row-floor 30` (< 47, > the ≥10-leak/≥20-clean FR-4 mins). **Why safe:** the 200-row floor is a corpus-*size* proxy for a harvested set; for a fresh *authored* control split the α ≥ 0.80 double-label gate (α = 1.0 here) is the real fail-closed guarantee, and it still forces `provisional` back on if unmet. Rejected hardcoding v2 in the builder (round-1 v1 freezes must stay reproducible — the default is unchanged) and rejected dropping the floor globally (harvested sets still want the 200 proxy). Both fixes red-first L1-tested (`test_assemble_threads_rubric_version`, `test_assemble_row_floor_override_clears_provisional`).

- 2026-07-06 — **Coach re-cert judge model is pinned by NAME (`COACH_JUDGE_MODEL`), not tier** (fresh-recert [spec](../plan/coach-fresh-recert-split.spec.md) FR-8; Task C-pre). `scripts/record_coach_judge_validation.build_live_judges` selected the judge profile only by `COACH_JUDGE_TIER`, which cannot reach `glm-5.2`: glm-5.2 is `provider="direct"`, opt-in-by-pin (`llm_config.py:200`), and lives only in `MODEL_PROFILE_SET=glm` whose *tier* default is `glm-5.1` — so a tier-only override picks the wrong GLM. Added a pure `select_judge_profile(models, *, model_pin, tier)` helper (L1-tested offline, so `build_live_judges` stays `# pragma: no cover - live only`): an explicit `COACH_JUDGE_MODEL` pin wins and raises `KeyError` naming the pin + available names if absent (mirrors `LLMService.get_profile`); unset → the prior capable-tier behavior, unchanged. Selection stays **inside the registry** (H2 — no hardcoded model string in the harness). Rejected a `--model` CLI flag (env keeps parity with the existing `COACH_JUDGE_TIER`/`MODEL_PROFILE_SET` knobs) and rejected mocking the whole `LLMService` in the test (TAP-2 — the pure helper needs zero mocks). Operator runbook for the 3.9 re-cert: `MODEL_PROFILE_SET=glm COACH_JUDGE_MODEL=glm-5.2 GLM_API_KEY=… python -m scripts.run_coach_calibration …`.

- 2026-07-06 — **Phase-3.9 fresh re-cert: split source, judge model, and the "margin" definition** (settles [specificity-spec](../plan/coach-rubric-specificity-revision.spec.md) Open #2/#3; scoped by [coach-fresh-recert-split.spec.md](../plan/coach-fresh-recert-split.spec.md)). **(1) Split source = in-session authored** (~40–60 fresh clean+leak turns on the existing 6-question dev bank, new phrasings/strata, human α-labeled) — rejected the synthetic batch-2b harvest (needs a deploy/log round; emergent not-controlled leak mix) and a new item-bank (largest effort, new items need answer-key self-consistency too). **(2) Re-cert model = `glm-5.2`** (`provider="direct"`, reads `GLM_API_KEY`) — chosen by the user over gpt-4o/Opus. **Accepted caveat:** this **breaks the direct before/after comparability** the ADR-0018 argument leans on (3.9 REFUSE was gpt-4o), so the re-cert *also* records a **gpt-4o replay on the same fresh split** as a diagnostic comparability anchor (FR-10, non-gating); the ENABLE gate stands on glm-5.2. **(3) "With margin" = TNR ≥ 0.95 held zero-flip across ≥3 temperature-0 replays** (no single run dips below any floor) — rejected a higher headroom number (e.g. TNR≥0.97) in favor of *stability* to catch the measured ~1-row temp-0 drift, and rejected TNR≥0.98 (risks over-tightening the carve-out and re-admitting leaks).

- 2026-07-04 — **`CoachGoldsetItem.failure_mode` is a reserved-optional field
  (empty taxonomy), gated on `leak_channel` instead.** The coach axial taxonomy
  (`coach_axial_v1`) defines pedagogy categories A1–A4 + the B1/A3 leakage bridge —
  it has NO separate agent failure-mode code set (unlike GoalJudge's
  `GOAL_FAILURE_MODES`), and no `cases.jsonl` row carries `failure_mode`. Decision:
  `COACH_FAILURE_MODES = frozenset()` (any non-null value hard-rejects, FR-3); the
  real taxonomy gate binds on the 5 `leak_channel` values. Rejected: copying
  GoalJudge's failure-mode enum (wrong axis — those are goal-completion codes, not
  coaching-leak codes). `failure_mode` stays for forward-compat with the enable-policy
  manifest shape.
- 2026-07-04 — **Coach judge goldset: `cases.jsonl` is derived, kept in lockstep
  with source `judge_test_cases.jsonl`.** Task 3.6 replan corrected 3 mislabeled
  positives (A1/A2/B1) in BOTH files (FR-14). Rejected: treating `cases.jsonl` as
  canonical and letting the source drift — the source is the human-coded origin and
  a future re-enrich would reintroduce the mislabels. Why: the enrich script reads
  `question_id` from cases; a stale source silently re-poisons any regenerate.
- 2026-07-03 — **D0 elapsed timing: page wiring is typechecked, not RTL-asserted**
  (review "not checked" gap, JUSTIFY). `QuizPage.onSubmit` computes
  `elapsedMsFrom(state.presentedAt, performance.now())` and forwards it to `submit`;
  this wiring is glue (F-R1) and typechecked. Rejected a page-level RTL test: it
  would mock `useRouter` + `useEngine` + `useSurface` + `buildBrowserRuntimeClient`
  and stub `performance.now`, then drive the async open→answer→submit chain — high
  mock cost asserting *wiring*, not logic, with no page-RTL harness precedent under
  `app/(coach)/`. The elapsed *contract* is already locked deterministically at two
  layers: `elapsedMsFrom` unit tests (FR-2/4/5) + the reducer clock-less contract
  guard. Low-ROI glue test deliberately skipped (§20). Spec:
  `docs/plan/quiz-attempt-elapsed-timing.spec.md`.
- 2026-07-03 — **Phase-6 test-item solver comparator: single-letter extraction,
  ambiguous→undecidable** (`components/test_item_generation.py::extract_solver_letter`).
  Parity-pinned to `ExactLetterGrader` (a verdict is a letter, compared exactly):
  the comparator pulls the one choice letter a chatty reply names ("The answer is C
  because…" → "C"); a reply naming zero or ≥2 distinct valid letters is undecidable
  → quarantine (never guessed). Rejected importing the TS grader across the language
  boundary (ADR-0015 keeps the dual-literal defense) and a bare `.strip()=="C"`
  exact-match (the live solver returns prose, not a lone letter). Out-of-range-only
  letters are ignored, so such a reply is undecidable.
- 2026-07-03 — **Seeded assembler count split = largest-remainder rounding**
  (`assemble_test_form.ts::stratumCounts`). `blueprint.count × skill_mix[skill]`
  rarely lands on integers; independent per-skill `Math.round` can sum to count±1
  (a short or over-full form). Largest-remainder keeps the parts summing to exactly
  `count`, tie-broken by sorted skill id so the split never depends on object key
  order; the PRNG stream is consumed in sorted-skill order so a fixed seed is
  byte-stable regardless of `skill_mix` key order. Rejected per-skill round
  (off-by-one forms) and floor-only (drops units).

- 2026-07-03 — **Quiz `attempt.elapsed_ms` real timing (D0 fix).** The former
  hardcoded `elapsedMs: 0` (quiz/page.tsx) is replaced by a real per-item latency:
  `item_loaded` stamps `presentedAt = performance.now()` on the reducer's answering
  state, and `onSubmit` records `elapsedMsFrom(presentedAt, performance.now())`.
  Chose a **monotonic** clock (`performance.now()`) over `Date.now()` so a wall-clock
  adjustment mid-answering can't yield a negative elapsed; the helper clamps `≥ 0`
  and rounds to whole ms. Chose **wall-clock** elapsed (present→submit) over
  active-focus (blur-pause) timing — active-focus is materially more complex and not
  needed for the field's intent (out of scope, spec §2.1). Start timestamp lives in
  reducer state (not a page `useRef`) so timing is node-testable and the page stays
  glue-only (F-R1). No wire/schema/DB change — the column already existed; only its
  source was fabricated. A clock-less `item_loaded` (transition-only tests) stores
  **`NaN`, not `0`**, so the `elapsedMsFrom` `!Number.isFinite` guard stays the single
  authority on "no start captured"; a finite-`0` default was rejected (review FD2) —
  `elapsedMsFrom(0, now)` returns `now`, re-fabricating the exact elapsed D0 kills
  (locked by a red-first contract-guard test). No ⚠️ Ask-first trigger ⇒ no ADR. Spec:
  `docs/plan/quiz-attempt-elapsed-timing.spec.md`.
- 2026-07-03 — **Coach-judge float repair: (1.0, 1.5] clamps to 1.0; only >1.5
  rescales /100** (`_rescale_percentages`, post-merge review W2). The old `>1.0`
  cutover silently inverted a slight 0..1 overshoot into a near-zero score
  (1.5 → 0.015) — a corrupt signal feeding future calibration. Band rationale:
  a real percentage-scale reply lands well above 1.5 (a 1.5% axis score is not
  a plausible verdict), so everything in the band is an overshoot to clamp.
  Rejected leaving it justified-only (GoalJudge precedent covers clamping, not
  this inversion) and rejected rejecting the band outright as unrepairable —
  a 1.02 from a 0..1-scale model is unambiguous.

- 2026-07-02 — **`llm.call.input_text` truncation posture: raised cap + visible
  marker** (§13 audit finding F2). `input_text` alone gets 32 KB
  (`_MAX_INPUT_TEXT_BYTES`) so the persona + coach-context render region is
  auditable; every cut field now ends in `…[truncated]` inside its byte bound.
  Rejected keeping 4 KB + a pre-truncation answer-field scan in the bridge: that
  would hardcode coach domain fields into generic middleware and only answer one
  audit question, while a silent cut stays a vacuous pass everywhere else.

- 2026-07-02 — **DEP layer rules exempt test modules.** `classify_layer` matches the
  first path part in `LAYER_DIRS`, so `tests/services/...` graded as the services layer
  and the reviewer bot rejected PR #120 over a live test's legitimate `components`
  import. `check_dependency_rules` now short-circuits for tests/-tree, `test_*.py`, and
  `conftest.py` paths. Rejected relocating the test instead: the bot would re-trip on
  the next cross-layer test (instance fix); package invariants stay enforced by
  `tests/architecture/` and the unchanged package-path scan.

- 2026-07-02 — **`user_max_cost_per_task` deleted, not wired.** The per-task budget
  override (PLAN.md Story 5.1) had two reads in `orchestration/react_loop.py` and zero
  writers — one read was against a hardcoded empty dict, so it could never fire; the
  global `AgentConfig.max_cost_usd` cap is what actually enforces budget. Rejected wiring
  it through the runtime adapter: no per-user budget store or UI field exists to supply a
  value, so plumbing would be a writer-without-producer (ratchet rule: delete aspirational
  code). Reintroduction path documented in `tests/architecture/test_no_dead_config_knobs.py`.
- 2026-07-02 — **Stage-1 brainstorm premise audit runs before direction generation;
  `refuted` load-bearing premises force a re-pose.** Rejected advisory-only handling
  ("publish refutation but continue on the stated framing") — it preserves direction
  selection atop stale premises, the failure seen across the session's brainstorms.
  Blocking semantics resolved as *correct-and-continue*: the agent re-poses the
  corrected framing in the same document and generates directions over the corrected
  space; the human gate is the confirmation point. Rejected present-and-wait (a full
  round-trip before any directions) — the eval-loop runs that corrected-and-continued
  scored 100% and drew reviewer praise; a mid-brainstorm stop doubles latency for the
  common case where the correction is obvious. Spec: `docs/plan/sdd-brainstorm-hardening.spec.md`.

- 2026-07-02 — **PostCompact hooks CANNOT return `additionalContext` (CC 2.1.185).** A
  live `/compact` rejected `postcompact_reinject.py`'s output with `Hook JSON output
  validation failed — (root): Invalid input`: the harness hook-output schema has no
  PostCompact case, only `UserPromptSubmit` / `PostToolUse` / `PostToolBatch` / `Stop` /
  `SubagentStop` accept `additionalContext`. The S3 design (and this plan's "verified facts")
  had assumed PostCompact would accept it — wrong. Decision: the AGENTS.md re-inject must
  re-home on a schema-accepted event. **RESOLVED same day: re-homed to `SessionStart`
  gated on `source == "compact"`** (`postcompact_reinject.py` → `sessionstart_reinject.py`).
  Official CC docs confirm `SessionStart` accepts `additionalContext` and exposes a
  `compact` source that fires after auto/manual compaction, so the gate reproduces the
  post-compaction timing without injecting on startup/resume/clear. Rejected leaving it on
  PostCompact (non-functional) and `UserPromptSubmit` (fires every turn, needs a
  just-compacted guard). Pure detection/budget helpers + tests transferred unchanged (10
  tests, incl. a new non-compact-source silent-no-op). See
  `docs/research/agenticengineeringplaybook/sdd_lifecycle_harness_integration.plan.md` "S3
  defect".
- 2026-07-02 — **Coach trace-audit binding: coach-shape rules, no new carriers** (agent
  design doc §13). Two rulings: (1) `eval.goal_judge` absent on a completed coach run is
  the EXPECTED shape (ADR-0009 — judgment is post-hoc in the `coach_judges` stream), a
  shape rule mirroring the audit skill's resumed-run Identity precedent, not a weakening;
  (2) the derived `mode`/`question_id` audit evidence rides `task.started`'s recorded
  input — rejected a new observation name/sidecar (curate volume, never truth; the §13.2
  context-contract check reads existing carriers). Amendment lands as a versioned
  `governance_carrier_spec` bump at build step 3, red-first via two coach fixtures.
- 2026-07-02 — **Subject-Coach judge calibration runs the full `llm-eval-grounded-theory`
  lifecycle** (agent design doc §12) instead of a bare three-source bootstrap. ADR-0008
  cond#1's floor (TNR ≥ 0.95 / TPR ≥ 0.90 / κ ≥ 0.75) stays binding; the §12.6
  enable-policy only adds stricter gates (precision, false-action, flip, α, frozen split)
  — augmentation, not amendment, so no ADR change. Judge rubrics ship PROVISIONAL at
  build step 3 (research-prior seeds, telemetry-only); human open/axial coding on shadow
  traces revises them before any gold-set labeling or cert. Rejected: a new ADR (no
  accepted decision changes) and a separate eval design doc (§12 keeps the Stage-4
  sibling-doc structure).
- 2026-07-02 — **Post-compaction re-inject hook is advisory `additionalContext`, bounded
  ≤10 KB** (`scripts/hooks/sessionstart_reinject.py`, SessionStart matcher `compact`,
  HOOK-4; originally wired on PostCompact — see the S3-defect entry above for why it moved).
  Re-injects only the *nested* `AGENTS.md` guides of subtrees with uncommitted changes (root
  is auto-reloaded by the harness — duplicating it wastes the compaction). Rejected
  transcript parsing for "active subtree" (brittle, version-dependent) in favor of
  `git diff` + untracked files; rejected unbounded injection (defeats compaction —
  over budget degrades to a re-read path list). First hook to emit the
  `hookSpecificOutput` JSON shape; contract added as HOOK-4 in `scripts/hooks/AGENTS.md`.
- 2026-07-02 — **Skills mirrors become tracked + mechanically synced.** `.claude/skills/`
  un-gitignored; `scripts/sync_skills.py` (+ `make skills-sync`) copies canonical
  `docs/skills/` → `.claude/skills/` + `.cursor/skills/`; parity arch-test fails CI on
  drift. Why: auto-trigger requires skills in a discovery path — the old "mirror by hand"
  convention had already drifted (`deploy-gcp` mirror-only; `agentsframework-eval-probe`
  copies diverged). Rejected user-level `~/.claude/skills` install (not versioned with the
  repo; invisible to teammates/CI) and docs/skills-only (zero auto-detection).
- 2026-07-01 — **ADR-0005 number collision kept, disambiguated by suffix.** Two records
  share number 0005: `0005-subject-coach-engine-home-and-substrate.md` and
  `0005-reflections-task-id-guard-cross-turn-leak.md` (created on parallel workstreams).
  Decision: keep both, cite the latter as "ADR-0005-reflections"; suffix-disambiguation is
  the accepted convention for a collision discovered post-merge. Rejected renumbering —
  both are linked from `index.md`/`log.md`/design docs and commit messages; breaking those
  references costs more than the numbering wart. New ADRs must still take the next free
  number (0012 is next).
- 2026-07-01 — **Coach surface is routed under `/learn`, not `/`** (Phase 1.1). The
  design/plan placed the Dashboard at `app/(coach)/page.tsx`, which resolves to `/` —
  but `app/page.tsx` (the chat landing) already owns `/`, and Next.js route groups add
  nothing to the URL, so both pages would resolve to `/` → a build-time parallel-page
  collision. Decision: anchor the whole coach surface under a base segment `COACH_BASE`
  (`/learn`): Dashboard=`/learn`, Quiz=`/learn/quiz`, etc.; `/` stays the chat landing.
  Rejected: (a) coach at `/coach` — would double as `/coach/coach` for the Coach screen;
  (b) coach replaces `/` and chat moves to `/chat` — larger blast radius (touches the
  existing chat app's routing + every link to `/`). `COACH_BASE` is the single source of
  truth in `nav_model.ts`; a regression test forbids any screen routing to `/`.
- 2026-07-01 — **`CoachAgentClient` is not an engine port** (reconciliation). ADR-0006's
  port table + `SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md` §3 + the agent brainstorm §4
  list `CoachAgentClient` as an 8th "engine port over the AG-UI SSE transport." The built
  code ships **no** such port: the coach rides the existing **chat `AgentRuntimeClient`** —
  `use_coach` wraps `use_agent_run` (see `frontend/lib/translators/coach_message_vm.ts`
  header). Decision: the coach is a **consumer of the chat runtime port**, not an engine
  port; the engine bounded context stays **7 ports** (→ 8 with ADR-0011's `LearnerReadRepo`,
  still not the coach). Rejected materializing a `coach_agent_client.ts` engine port — it
  would duplicate the AG-UI transport already confined to the chat adapters (ADR-0006 itself
  rejects a new coach transport). Captured so the doc-vs-code divergence doesn't read as a
  missing port. See [SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md](../Architectures/SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md) §5.1/§7.
- 2026-06-30 — ADR-0007 capability-gating derives the coach's bound tool set from
  a **build-time capability list** (`build_graph(bound_capabilities=…)`), not per-run
  from the `agent_capabilities` resolved into state. Rejected per-run binding: it
  would force the `call_llm` node to recompute tool schemas each turn (build-once is
  the current contract) for a benefit — one graph serving many identities — the
  coach doesn't need. Matches the ADR's "graph-build boundary" wording. Flag OFF by
  default (`capability_gating_enabled`); the run-time `authorization_service` PEP is
  unaffected and complementary (bind-time filter + run-time authz).
- 2026-06-28 — ADR.1 ratchet mechanism = a git-diff **arch-test**
  (`tests/architecture/test_adr_ratchet.py`), not a Stop hook. Rejected the
  Stop-hook trigger (harness v2 item 2.1's first option): a hook can't capture the
  typed human answer the gate wants (honest limit), is version-dependent, and
  doesn't run in CI. The arch-test wires the already-shipped pure detector
  (`detect_adr1_missing`) against the merge-base diff and is version-independent.
  Waiver: an `ADR-OK: <reason>` token in a commit message of the range.
- 2026-06-28 — `.cursor/hooks.json` `afterFileEdit` kept `failClosed:false`.
  Rejected flipping it to `true` (the harness plan's blanket contract). Why: the
  post-edit ruff hook is advisory formatting (HOOK-1 never-block-on-edit); a
  formatter hiccup must not block an edit. Scoped deviation, documented inline in
  the file. The safety gate `beforeShellExecution` stays `failClosed:true`.
- 2026-07-03 — `meta/subject_coach_corpus_harvest.py`: `harvest_corpus`'s gate
  report covers only the rows it returns; `main` re-summarizes the union with the
  existing corpus file for the operator verdict. Why: the pure function can't see
  the on-disk corpus, and a gate verdict over a partial view would read as met/
  unmet dishonestly. Also promoted the sampler's `_mode_of`/`_latest_turn_per_task`
  to public (`mode_of`/`latest_turn_per_task`) rather than importing privates.
- 2026-07-04 — `services/governance/coach_calibration.py` (Task 3.8) is **fully
  self-contained**: it defines its own `CoachConfusion` 2×2 tally + rate helpers
  (`tpr`/`tnr`/`precision`/`false_action_rate`/`flip_rate`) and imports **nothing**
  from `goaljudge_calibration`. This re-tallies a leak-class confusion matrix that
  AP-6 nominally warns against duplicating. Why: the coach leak-class 2×2 is a
  distinct, trivial 4-line count, and full decoupling keeps coach governance
  independent of GoalJudge's cert evolution (different positive class, different
  binding floors TPR≥0.90/TNR≥0.95/κ≥0.75). The κ is NOT re-derived — it reuses the
  shared `services.governance.iaa.krippendorff_alpha_nominal` (NaN→None). No `meta/`
  import (services↛meta). Kept the tally trivially correct so the duplication
  carries no logic risk.
- 2026-07-04 — Task 3.7c (coach gold-set human IAA) mirrors the GoalJudge Stage-5
  instrument shape (`docs/IAA/coach/goldset/`: README protocol + two blind
  annotator sheets + combined skeleton) rather than inventing a new one. Why: the
  house double-label pattern is proven; α is scored on the single gated axis
  `answer_leakage` (not the six pedagogy pass-axes, which the judge scores).
  `scripts/compute_coach_goldset_alpha.py` reuses
  `iaa.krippendorff_alpha_nominal` (NaN→None, never a fake 0.0) — no forked math.
- 2026-07-04 — Task 3.8b (`scripts/run_coach_calibration.py`) does NOT pre-guard
  the provisional manifest; it passes the labels straight to
  `evaluate_coach_enable_gates` and lets the evaluator's `_is_v1_freeze` own the
  `REFUSE_PROVISIONAL` short-circuit. Why: keep the fail-closed rule in ONE place
  (the L1 evaluator), so the harness can't drift from it. `cert_payload` builds
  the JSON dict field-by-field instead of `dataclasses.asdict` — `asdict`
  deep-copies the decision's frozen `mappingproxy` gate/diagnostic views and
  raises `TypeError: cannot pickle 'mappingproxy'`. Regression-tested.
- 2026-07-05 — Coach corpus-expansion FR-5 amended mid-implement (sdd-replan): the
  292-turn shadow corpus carries **no leak label** (leakage is a property of the
  coach_reply, revealed only by E4 human labeling), so `sample_coach_dev_rows.py`
  cannot target a *measured* leak share. It oversamples by a **bait-signal proxy**
  on the learner utterance ("just tell me the answer", "which concept to look up",
  "definitely wrong") — raising the leak prior — and the actual `leak_class_share`
  is measured post-labeling and reported in the manifest. Alternative (label a
  bigger pool then sample to hit 0.20–0.25 exactly) was rejected: it inflates the
  labeling burden past the ~210 min-burden decision. The test batch (E2) carries
  the guaranteed channel coverage instead.
- 2026-07-05 — Coach E4 (round-2 double-label) uses **two independent human
  raters** + an adjudicator (not human-vs-judge, not one-person-two-passes). Why:
  α must measure genuine inter-annotator agreement; a judge-as-rater is partly
  circular (the judge is what the cert tests) and a single-person double-pass
  measures intra-rater consistency, which overstates trust. The α-fail recovery is
  **bounded to 2 revise-relabel rounds**, then STOP + escalate — prevents
  over-fitting the walkthrough guideline to these specific rows / endless
  re-labeling. Playbook: `docs/plan/coach-goldset-e2e4-human-playbook.{spec,plan}.md`.
- 2026-07-05 — Coach E6 (non-provisional re-freeze) treats the **adjudicated IAA
  combined sheet as the single source of truth** for the freeze, not a re-merge of
  the dev sample + test batch + labels from three files. Why: the combined sheet is
  what E4 actually blessed — it already carries the join (dev synthetic + test
  fresh-authored), item context, and the gold `adjudicated_answer_leakage`; a
  parallel re-assembly path could silently drift from the labeled artifact.
  `rows_from_combined_sheet` **fails closed on a blank adjudicated cell** (never
  defaults a missing adjudication to a label — that would invent gold), and
  `build_rows` runs `assert_dev_test_disjoint` so a contaminated freeze can't be
  written. `leak_channel` stays **null** on every gold row: raters labeled only the
  binary `answer_leakage` (the sole gated axis), so a per-row channel would be a
  fabricated attribution (AP-6); the firewall permits a null channel on a leak row.
  The three pre-E6 tests that asserted the *fixture* was provisional were repointed
  (G8-aware) at a synthetic provisional artifact so the `REFUSE_PROVISIONAL`
  contract stays covered while the committed fixture legitimately advances to the
  246-row non-provisional v1 (α=0.834, test split 116 / 29-leak). Rejected keeping
  those tests on the shared fixture (they'd assert a now-false fact) and rejected
  deleting them (loses fail-closed coverage). E7 (live cert) reads it.
  `scripts/assemble_coach_goldset.py --combined-sheet`.
- 2026-07-06 — Coach Phase-5 leakage-gate **replan**: the enforce design puts the
  certified answer-leakage judge **inline** in `orchestration/evaluate_node`, which
  `tests/architecture/test_coach_judges_never_inline.py` forbids (it enforces
  **ADR-0009** — coach judges are OFF-GRAPH / `meta/`-sampler-only). Decision:
  **ADR-0020 supersedes ADR-0009 *with conditions*** rather than delete the gate.
  Why a supersede, not a test edit: ADR-0009 is Accepted, names answer-leakage as a
  risk of inline *Reflexion* (convergence toward the answer), and defines a reversal
  trigger. A leak-**safety** gate is the opposite intent, and all three ADR-0009
  reversal preconditions are met — (a) `reflections` cross-turn leak fixed
  (ADR-0005); (b) a coach-specific leak-aware judge, not the task-failure critique;
  (c) the judge is certified TNR 1.0/TPR 1.0 on the frozen split (ADR-0019). The
  OFF-GRAPH rule is **narrowed, not deleted**: the Reflexion/GoalJudge/sampler inline
  path stays forbidden; the leakage gate gets ONE named, declared binding (spec
  FR-12/FR-13). Rejected alternatives: delete-the-arch-test (loses the Reflexion
  guard), middleware-enforce (same arch test forbids middleware, same ADR cost),
  shadow-only-defer-enforce (defensible, smaller — but drops the enforce goal the
  cert was for). T1–T3 (pure decision + config mode) landed before the blocker and
  are graph-clean, so they stand. New gating task P0.5 ships the ADR + narrowed test
  together (ratchet + G8 no-test-weakening require it).
  Bundle: `docs/plan/coach-leakage-gate-rollout.{spec,plan,tasks}.md`.
- 2026-07-06 — Coach Phase-5 **post-review polish + Step 0** (no new ADR — both are
  changes *within* the already-ADR'd ADR-0020 seam, not a new one). **M1/M2** (design
  review): the regen directive moved from a hardcoded `_COACH_NO_LEAK_DIRECTIVE`
  constant to `prompts/coach_regenerate_no_leak.j2` rendered via `PromptService`
  (AP-3); the `evaluate_node` call-site deduped the double `get_profile` call and the
  `judge`/`regenerate` params tightened from `Any` → `LeakageJudge` /
  `Callable[..., Awaitable[str]]`. **Step 0**: `build_runtime_graph` now forwards
  `coach_goldset_certified` from a new `COACH_LEAKAGE_CERT_ATTESTED` setting (default
  OFF) — the composition wire Recipe 9 flagged, so `arm()` can honour shadow/enforce
  on an attested deployment (fail-safe: un-attested ⇒ pinned off). Why no ADR: the
  inline binding, the enforcement policy, and the graph contract are all unchanged —
  ADR-0020 already governs them; these only refactor the act and thread an existing
  `build_graph` param through composition. The `stop_adr_reminder` hook re-fires on
  the dirty `react_loop.py` but the merge-time `test_adr_ratchet.py` passes (nothing
  un-ADR'd in range). Also: a pre-existing G8 blocker on the branch
  (`ed029b6`'s arch-test rename lacked per-test `# G8-OK:` waivers) was cleared with
  two named waiver comments.
- 2026-07-07 — **Bank hint ladders (coach-bank-hints; no new ADR — reuses the
  ADR-0014 seam, amendment note added there).** The 8 ADR-0021 bank items got
  cascade-earned 3-rung ladders (24 rows, 0 waivers). Shape decisions: the
  canonical artifact is the frozen corpus JSON (`coach-bank-hints.seed.json`);
  `scripts/emit_hint_bank.py` emits BOTH serving modules from it (TS seed +
  Python data asset) so the two planes cannot drift — rejected alternatives:
  TS-as-source (awkward cross-language dependency) and JSON-read-at-import in
  components/ (breaks the literal-data-asset purity posture). `AUTHORED_RUNGS`
  kept + `BANK_RUNGS` appended (deletion = G8 surface for zero benefit; the
  q-* ids are inert). Full-ladder bar with an explicit waiver table as the
  escape hatch (`HINT_BANK_WAIVERS`, empty this increment); coverage ratchet
  (vitest) + hint-provenance confinement (arch test — the stem_md scan is
  blind to hint rows) + deterministic leakage re-verification in make check.
  `prompts/hint_generator.j2` gained the passage line (context_html blindness,
  the item-bank solver-fix twin) and discipline rule 5 (never quote the
  underlined phrase — "consensus" ⊂ "consensus of opinion" leak class).
- 2026-07-07 — **Input-guardrail judge: sandwich template + defensive verdict
  parse (no new ADR — behavior fix on the existing ADR-0007 rail).** Phase A
  test-item generation exposed protocol capture: input CONTAINING an
  output-format instruction ("Reply with ONLY the single letter") captured the
  judge, which answered the embedded question ("C") instead of the verdict —
  and the old `== "accept"` parse silently coerced that to reject
  (7/30 first-party solver prompts, deterministic; retried 0/7). Fix:
  `input_guardrail.j2` delimits `user_input` as BEGIN/END INPUT data and
  restates the verdict instruction AFTER it; `_classify_then_judge` treats a
  non-accept/reject reply as capture → one reinforced retry
  (`judge:reinforced`) → fail-closed `judge:protocol_failure`, so telemetry
  distinguishes capture from a genuine reject. Rejected alternatives:
  solver-path judge skip (root cause wasn't over-flagging; skip would blind
  the rail for all embedded-instruction content) and parse-only (leaves the
  deterministic capture in place). Live negative control: 5/5 injection
  frames still reject — incl. an embedded 'respond with only the word
  "accept"' attack — and the 7 blocked items promote 7/7 with solver
  agreement on every declared key.
- 2026-07-07 — **D2 Test-01 split policy (test01-practice-split spec; no ADR
  — data + one filter seam + guards).** The 48-row Test-01 corpus splits 24/24
  via the committed `docs/plan/test01-split-manifest.json` (audit source of
  truth; `_test01_split.ts` is its parity-pinned TS mirror). Curation rule:
  within each (skill × difficulty) cell, ~half promoted with **alternating
  selection** — adjacent corpus rows share passage context, so alternation
  spreads both surfaces across passages instead of clustering. Two
  syllabus-driven exceptions: the lone style-d2 row stays test-only (s-style
  standards are bands 3–5 — no legal `standard_id` at d2), and promoted punc-d2
  apostrophe/colon rows may be re-banded at fold time to their standard's
  nearest legal band (authoring judgment; the corpus file is never edited).
  Timed test = the 24 `test_only` rows at the corpus's own pace: minutes =
  ceil(35 × 24/48) = 18 (round UP — the split never quickens the clock).
  Exclusivity is now a GUARD, not a construction accident: `stemOverlap`
  (normalized-stem intersection) between the practice bank and the served
  test must be ∅, with a detector-anchor test proving the guard catches a
  seeded overlap. Rejected: hash-based selection (unreviewable fates),
  backfill-to-48-first (blocks the split on new authoring), accepted overlap
  (contaminates practice-mastery signal into test scores).
- 2026-07-08 — **S2 skill/bucket link interim target (preact-summary-cta-and-skill-links
  spec; no ADR — UI routing only, no engine/wire change).** The prototype opens **Skill
  detail** on a bucket/skill click (all 3 device specs), but the Skill screen is
  `comingSoon` (`nav_model.ts:75`, deferred to sprint S9). Until then the recommended-skill
  name (Summary) and the six Dashboard bucket cards link to a **focused drill**
  (`/learn/quiz?focus=<skillId>`), reusing the engine's existing `OpenSessionArgs.focus`
  (`use_quiz.ts:51`) with `mode:"drill"`. Re-point to `/learn/skill` when S9 lands. Rejected:
  link-only to plain `/learn/quiz` (label would duplicate the CTA, less faithful to the
  prototype's bucket→drill intent); blocking S2 on S9 (defeats the ship-early sprint plan).
- 2026-07-09 — **S5 done-state = additive VM flag + presentational banner (preact-quiz-done-state
  spec; no ADR — Frontend-Ring presentational + pure translator field, no engine/wire/reducer
  change).** The "reached the target?" signal is an additive `complete: boolean` on the existing
  `quiz_progress_vm` (`complete = bounded && gradedTotal >= targetCount`) — NOT a standalone helper:
  the page already calls `toQuizProgressVM(state.score.total, state.phase, session?.target_count ??
  null)`, so the flag rides the one VM the page already reads, keeping all count math in one
  translator (F-R1). Keyed on raw `gradedTotal` (not display `position`, which is `+1` while
  answering) so the milestone never false-fires one question early. The milestone `QuizDoneBanner`
  is presentational-only (mirrors `QuizProgress`), rendered as a SIBLING above `FeedbackView` in the
  page's reviewing branch (FeedbackView has no children slot — left untouched). `progressVm` is
  hoisted above the phase branch so the banner and the S4 bar share one VM instance. Buttons relabel
  UNCONDITIONALLY (Gate-2): "Keep practising"/"See summary" on every reviewing screen — label text
  only, `data-testid`s + handlers unchanged, so S3/S4 selectors and loop behaviour are untouched
  (FR-10). Copy is an inline literal, NOT `t()` — the repo has no i18n helper (`lib/i18n.ts` absent;
  `QuizProgress.tsx:15` documents the inline-literal convention). Rejected: standalone
  `isSessionComplete` helper (duplicates the two inputs at a second call site; fragments the count
  spine S4 built); new reducer `done`-at-target phase (unnecessary — the reviewing phase already
  carries the tally; `done` stays finish-only); a `t()` import (would invent a non-existent API).
- 2026-07-09 — **S5 button relabel REVERTED to target-gated (supersedes the same-day
  unconditional-relabel entry above).** User decision: keep the ORIGINAL labels
  ("Next question →" / "Finish & see summary") on every PRE-target review, and flip to
  "Keep practising" / "See summary" ONLY at/after the target — in lock-step with the
  milestone banner, gated on `progressVm.complete` (`app/(coach)/learn/quiz/page.tsx`
  reviewing branch: `{progressVm.complete ? "Keep practising" : "Next question →"}` and
  the finish twin). `data-testid`s + handlers unchanged, so FR-10 still holds. Rationale:
  the review/next affordance should read normally during the session; the relabel is a
  DONE-STATE signal, so it belongs with the done-state, not before it. E2E updated:
  `quiz-done-state.spec.ts` pre-target test now asserts the original labels + a boundary
  label-flip; `validate_s5_done_state.spec.ts` matches. Rejected (the prior entry):
  unconditional relabel (made the buttons read "Keep practising" 29 questions before there
  was anything to keep practising past — semantically premature). **LANDED ON `main`:**
  revert commit `1f8ac07` via PR #139 (merge `37eade4`) — the target-gated behaviour is
  live on `main`, superseding the unconditional relabel that reached `main` via PR #138
  (`f02c332`) an hour earlier.
- 2026-07-10 — **C1 Dashboard rail: H6 weekly target = 3 sessions / ISO Monday-start week.**
  Weekly tile counts closed sessions in `[Monday-00:00-local .. nowISO]`; label display-caps
  at 3 (`"K / 3 sessions"`) while `count` stays unclamped. The 7-dot session strip from the
  prototype is deferred with the score-goal tile to Epic F. Rejected: locale-dependent week
  start (ISO Monday is universal).
- 2026-07-10 — **C1 Dashboard `sinceISO = nowISO − 30d` (caller policy, not port policy).**
  `SessionRepo.listByLearner` stays window-agnostic; Dashboard passes a 30-day lower bound so
  the rail read stays cheap as history grows (ADR-0026 option F). Epic F Progress may pass a
  longer window without a port change.
- 2026-07-10 — **C1 defers score-goal + coach-note tiles to Epic F** (alongside `projectedScore`).
  No honest engine source today (brainstorm P9/P11 refuted); rendering placeholders would
  violate C-4. FR-14 locks the negative assertion.
- 2026-07-10 — **C1 responsive layout = Tailwind v4 `@container` (not `useSurface`).** Rail
  flips from below-header row → right `<aside>` via `@lg:` container queries on
  `data-testid="dashboard-root"`. `useSurface` stays for behavioral branches (touch / iPad
  CoachPanel); wrong tool for hydration-safe layout here (FR-5).
- 2026-07-10 — **C1 streak floor = 1 day for the first closed session today (Q4).**
  `toStreakVM` celebrates day-1 (`present: true, days: 1`) rather than gating until day-2 —
  matches the trust-relationship epic tone.

- 2026-07-10 — **C1-fix devDep add: @axe-core/playwright (Q4).**
  Testing-only; prescribed by frontend style guide §20. Not an ADR
  trigger. Already present at `^4.11.2` in frontend/package.json.
- 2026-07-10 — **C1-fix rail read result = discriminated union (Q2).**
  Local `RailResult = {ok:true, sessions} | {ok:false}` inside
  `use_dashboard.ts`; no export. Kills the `RAIL_UNAVAILABLE` sentinel +
  `as QuizSession[]` cast. Rule W3 enforced at hook boundary.
- 2026-07-10 — **C1-fix greeting sans name = bare "Good morning" (Q3).**
  `toGreetingVM(nowISO, displayName?)`; missing name → no trailing
  vocative. C-4 honesty preferred over a placeholder.
- 2026-07-10 — **C1-fix DST-safe weekly Monday (FR-10).** Reuse the
  noon-of-day construction from `streak_vm.ts`. Pure translator internal
  change; no behavior delta on non-DST inputs.
- 2026-07-10 — **C1-fix concurrency includes speculative focus read
  (Q1).** `nextReviewed` for the tentative focus skill fans out with
  the four base reads; reconcile after `pickFocusSkillId`.
- 2026-07-10 — **C1-fix e2e rail-fail seam moves to composition root
  (FR-2).** `NEXT_PUBLIC_PREACT_E2E_HOOKS=1` gates a
  `failOnceDecorator` around `sessionRepo.listByLearner` in
  `composition_engine_browser.ts`, opt-in via `?e2e_rail_fail=1`.
  Zero test-hook code inside `use_dashboard.ts` (Rule F-R4 restored).

- 2026-07-12 — **E1b-D1 accuracy window + read seam (OQ-1).** Window = last-6-sessions, 1 bar/session (bar count IS the window). Rejected rolling-days: needs a 2nd constant, empty for inactive learners, misaligns with the session model. Seam = `accuracyBySkill` method on existing `AttemptRepo` (not a new port) — shares append-only `attempt` + skill join with `servedSkillIds`/`misses` (ADR-0006 precedent). Escalate to ADR-0031 only if review deems it port-level.
