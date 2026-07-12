# PreAct `/learn` — manual-test follow-ups (HARDENING-SPRINT backlog)

> **Status: PARKED.** These are deferred to a dedicated **hardening sprint** run
> **after all currently-planned sprints are done** (user decision 2026-07-09). Do
> NOT pull any item into an in-flight sprint — this is the consolidation bucket for
> `/learn` manual-test findings; add new ones here rather than acting on them ad hoc.
> When the hardening sprint opens, each item below is spec-ready (grounded with
> file:line), and the sequencing note at the bottom is the intended order.

Findings from the S4 manual walkthrough (2026-07-09), each verified against the
working tree so a future spec/ADR starts from fact, not the raw observation.
Ordered worst-first.

Source of the observations: user manual test of the S4 progress bar on the dev-seed
`/learn` quiz (learner **Maya**, 171-item ACT-English bank). Related shipped work:
S1–S4 (progress bar) on PR [#137](https://github.com/rajnishkhatri/AgentsFramework/pull/137);
S5 (done-state, item F4 below) is the still-unbuilt other half of the "infinite loop" gap.

---

## F1 (🔴 correctness) — Dashboard shows ~100% mastery after all-wrong answers

> *"I completed Style skill, attempted 30 questions, all were wrong. Dashboard shows
> 100% mastery. Need to fix dashboard to show accurate progress."*

**This is a real bug, and it is NOT a display bug — the dashboard renders faithfully.**
Root cause is in the FSRS write path.

**The chain (verified + reproduced):**
- Every submit calls `scheduler.review(attempt)` live during the session
  ([`components/quiz/use_quiz.ts:209`](../../frontend/components/quiz/use_quiz.ts:209)) — this
  writes `skill_state` on **every grade**, right or wrong
  ([`fsrs_scheduler.ts:194`](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts:194),
  "the SOLE skill_state write").
- **Root cause:** `review()` sets
  `mastery = this.retrievability(card, reviewedAt)`
  ([`fsrs_scheduler.ts:299`](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts:299)).
  It evaluates FSRS forgetting-curve **retrievability at the review instant itself**
  (elapsed time ≈ 0). By definition retrievability is **~1.0 at zero elapsed time**,
  no matter how far `stability` has collapsed — so every grade overwrites
  `mastery ≈ 1.0` (100%).
- A wrong answer is `Rating.Again`
  ([`fsrs_scheduler.ts:185`](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts:185)),
  which correctly **collapses `stability`** (reproduced: 5 wrong reviews →
  0.212 → 0.083 → 0.035 → 0.015 → 0.007) — FSRS *does* track the wrongness — but
  `retrievability_at_review` stays pinned at `1.0` each time, masking it.
- The dashboard is passive and correct:
  [`bucket_card_vm.ts:42`](../../frontend/lib/translators/bucket_card_vm.ts:42)
  `masteryPct: Math.round(mastery * 100)` → rendered at
  [`components/dashboard/BucketCard.tsx:76`](../../frontend/components/dashboard/BucketCard.tsx:76).
  Given `1.0`, it shows `100%`.
- The reported "100%" is **not** the stale dev-seed (`s-style` seeds `0.82`,
  [`_dev_seed.ts:146`](../../frontend/lib/adapters/engine/_dev_seed.ts:146)) — it's what
  the 30 wrong grades **freshly overwrote**.

**Premise correction (important):** the working assumption that "the scheduler is
read-only during serving (FR-13), so mastery is frozen at seed during a session" is
**only true for `Scheduler.next()`** (question selection). `Scheduler.review()`
writes on every grade by design. So the bug is not "frozen seed"; it's "the per-grade
write uses the wrong quantity for a durable-progress display."

**Fix direction (for the spec, not decided here):** "mastery" as displayed should be a
**durable competence** signal, not instantaneous retrievability. Options to weigh:
(a) display a stability-derived measure (or accuracy over recent attempts) instead of
retrievability-at-review; (b) keep FSRS retrievability internally but compute the
dashboard "mastery" from `fsrs_stability` / a rolling correctness window; (c) evaluate
retrievability at *now* when the dashboard reads, not at review time (partial — still
re-pins to ~1 right after any grade). Whatever we pick, the acceptance test must assert
**direction**: N wrong answers must not *raise* displayed mastery.

**Test gap that let it ship:**
[`fsrs_scheduler.test.ts:151`](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.test.ts:151)
only asserts `mastery ∈ [0,1]` after a single review — never asserts *direction*
(wrong → down) and never runs the "many consecutive wrong answers in one session"
scenario. A red-first test for that scenario is the entry point for the fix.

**Scope note:** "review all the dashboard rules and identify the issues" — this trace
covered the mastery path end-to-end (display ← VM ← engine write). The `today-focus`
weakest-skill pick (`today_focus_vm.ts`, `focus_pick.ts`) reads the *same* `mastery`
field, so it inherits the same distortion (a skill you're failing can look mastered and
drop out of "today's focus"). Worth a full dashboard-rules audit as its own spec task.

---

## F2 (🟡 UX) — On the feedback screen, keep the question visible

> *"When answer is shown: we still want to show the question as well."*

**Confirmed.** On the `reviewing` phase the page builds `content` from `FeedbackView`
**only** ([`app/(coach)/learn/quiz/page.tsx:216–248`](../../frontend/app/(coach)/learn/quiz/page.tsx:216));
the `QuizView` that holds the stem (`data-testid='quiz-context'`) is unmounted. So the
learner reviews the answer with the **question gone** — they have to remember what was
asked. `FeedbackView`
([`components/feedback/FeedbackView.tsx`](../../frontend/components/feedback/FeedbackView.tsx))
renders the reviewed choices + rationale + rule, but never the stem.

**Fix direction:** render the stem (and ideally the choices in-context) above the
feedback in the `reviewing` branch. The stem is already on `state.item.question.stem`;
this is a presentational change in the page's reviewing branch + `FeedbackView`, no
engine work.

---

## F3 (🟡 content) — Show the rule *and* explain it with an example

> *"Lets show rule and explain it with an example."*

**Partially present — the rule shows, the example doesn't, and the example content
already exists in the data model but has no render path.**
- `FeedbackView` **already** renders a "The rule:" line from `question.rule_md`
  ([`FeedbackView.tsx:134–137`](../../frontend/components/feedback/FeedbackView.tsx:134),
  fed by [`feedback_vm.ts:77`](../../frontend/lib/translators/feedback_vm.ts:77)). So
  "show rule" is done.
- What's missing is a **worked example**. Good news: there's already a `SkillRule`
  schema with `rule` **+ `examples: z.array(z.string())`**
  ([`engine_entities.ts:268–274`](../../frontend/lib/wire/engine_entities.ts:268)), and
  it's read from the DB
  ([`drizzle_engine_db.ts:199`](../../frontend/lib/adapters/engine/db/drizzle_engine_db.ts:199))
  — but `examples[]` is **never surfaced in any UI** (grep confirms the only reference
  is the DB read). The content seam exists; the render path doesn't.

**Fix direction:** thread `SkillRule.examples` into the feedback VM and render one or
more examples under the rule line. Needs the bank to actually populate `examples` for
the served skills (a content check), plus the VM + component wiring. Likely its own
small spec since it crosses content + view.

---

## F4 (✅ SHIPPED — S5) — After the target, tell the learner the quiz is over

> *"After target of 30 questions, show an appropriate message: quiz is over.
> However you can continue if you like."*

**DONE 2026-07-09 as S5.** Shipped the milestone banner (`QuizDoneBanner`, "🎉 You've
completed your N-question session!") above the feedback at the target, plus target-gated
button relabels ("Keep practising" / "See summary" at/after the target; originals before).
Non-blocking, over-run continues, routes to Summary/retake. PR
[#138](https://github.com/rajnishkhatri/AgentsFramework/pull/138) (MERGED) + relabel revert PR
[#139](https://github.com/rajnishkhatri/AgentsFramework/pull/139) (MERGED) — both on `main`. Spec/plan/tasks:
`docs/plan/preact-quiz-done-state.*`. **No longer a backlog item.** (Original analysis kept below
for provenance.)

**This was exactly S5, the (then-)unbuilt half of the "infinite loop" gap** (S4 shipped the
progress bar; S5 is the done-state + retake). Today, past the target the session just
keeps serving: the progress bar goes into **over-run** — the counter shows the true
position and **drops the `of M` denominator**, bar clamped full
([`quiz_progress_vm.ts:57`](../../frontend/lib/translators/quiz_progress_vm.ts:57)) — but
there is **no "you've reached your goal" message and no retake prompt**. The learner
can't tell they finished.

**Fix direction (S5 spec):** when `position` reaches `target_count`, surface a
non-blocking done-state — "You've completed your 30-question session. Keep going?" —
with an explicit **continue** affordance (matches the user's "however you can continue
if you like") and a path to Summary/retake. The over-run rendering is already correct
and honest; S5 adds the *milestone message* on top of it. Clarify at spec time:
interstitial vs banner, and whether "continue" resets the counter or keeps counting up.

---

## F5 (🔒 infra/security) — Real per-learner identity: enable WorkOS auth for eng-coach + an agent registry

> User decision 2026-07-12: change the dev learner to **"Garvit"** now (done — the
> `maya → Garvit` rename commit), and **park** the real-identity wiring here.

**Today (dev posture).** Every coach surface hardcodes the dev learner instead of
deriving it from the authenticated session. One source of truth
([`DEV_LEARNER_ID`](../../frontend/lib/adapters/engine/_dev_seed.ts:43), now
`"Garvit"`) is re-hardcoded as a `const LEARNER_ID` at each of **7 read sites**:
[`learn/page.tsx:19`](../../frontend/app/(coach)/learn/page.tsx:19),
[`learn/skill/page.tsx:10`](../../frontend/app/(coach)/learn/skill/page.tsx:10),
[`learn/quiz/page.tsx:47`](../../frontend/app/(coach)/learn/quiz/page.tsx:47),
[`learn/coach/page.tsx:28`](../../frontend/app/(coach)/learn/coach/page.tsx:28),
[`learn/summary/page.tsx:23`](../../frontend/app/(coach)/learn/summary/page.tsx:23),
[`components/coach/use_coach.ts:53`](../../frontend/components/coach/use_coach.ts:53),
[`components/coach/CoachPanel.tsx:37`](../../frontend/components/coach/CoachPanel.tsx:37).
The auth stack itself exists and is wired for the **chat** surface (WorkOS AuthKit
behind the `AuthProvider` port; `Session.user_id`; see
`STYLE_GUIDE_FRONTEND.md` §16) — the coach `/learn/*` routes simply don't consume it
yet.

**Why it's parked, not a quick edit.** This is a cross-cutting integration, not a
value swap: (a) all 7 sites must change together or one surface reads a different
learner than the rest; (b) it's an ⚠️ Ask-first trigger (a new integration crossing
the auth boundary) → needs an SDD pass (brainstorm → spec) + an ADR; (c) the user
scoped a second deliverable — **create an agent registry for authentication** (the
eng-coach agent's identity/AgentFacts entry so the authenticated learner is bound to
a registered coach agent, mirroring the trust-kernel AgentFacts pattern). `DEV_LEARNER_ID`
stays as the unauthenticated dev/seed fallback.

**Two hidden couplings the rename exposed** (fix as part of this item so they don't
regress): tests that mix the auto-seeded dev corpus (`buildBrowserEngineAdapters` →
`seedDevCorpus`, keyed to `DEV_LEARNER_ID`) with a hand-seeded learner must bind to
`DEV_LEARNER_ID`, not a literal — done for
[`use_skill_detail.test.ts`](../../frontend/components/learn/use_skill_detail.test.ts)
and [`use_dashboard.test.ts`](../../frontend/components/dashboard/use_dashboard.test.ts);
any new such test inherits the same rule.

**Fix direction (spec):** derive the learner id from `AuthProvider`/`Session.user_id`
at each `/learn/*` entry (a single shared `useLearnerId()` seam so there's one read
path, not 7 constants), fall back to `DEV_LEARNER_ID` when unauthenticated; register
the eng-coach agent in the AgentFacts/agent registry so the session identity resolves
to a certified agent. Clarify at spec time: display-name source (WorkOS profile vs a
learner-profile store), and whether the dev-seed fallback ships to prod behind a flag
or is dev-only.

---

### Suggested sequencing (for whoever plans the sprint)
1. **F5 first if the coach ships beyond a single-user demo** — it's the
   infra/security gate (real identity + agent registry); everything else is
   single-learner UX polish that stays correct under the dev learner. If the
   near-term target is still the dev demo, F5 can wait behind F1.
2. **F1** — a correctness bug that actively misleads the learner about their
   progress; the remaining items are enhancements. Start with the red-first direction test.
3. **F4 / S5** — completes the originally-scoped loop-closure gap.
4. **F2 + F3** — both live in the feedback/reviewing render path; natural to do together.
