---
title: 'Epic E (re-scoped) — full learn → miss → revise skill loop: natural-integration Stage-1 brainstorm'
type: brainstorm
epic: E
stage: 1
scope: 'E1 re-scoped from "skill-detail screen" to the full learn→miss→revise loop for one skill, built on the design artifact''s block model, integrated naturally with the EXISTING quiz/miss/scheduler ports — NOT a parallel engine'
date: 2026-07-11
status: Open — awaiting human direction gate
supersedes_scope_of: docs/plan/preact-parity-sprint-board-E.md (E1 = "skill-detail screen")
depth_decision: 'I-3 — absorb the 9-block schema into a lesson wire type (per human gate 2026-07-11)'
artifact: eng-coach-ui-design/lesson-delivery/
parent: docs/plan/preact-parity-epic-E-lesson-delivery-integration.brainstorm.md
board: docs/plan/preact-parity-sprint-board-E.md
method: 'sdd-brainstorm — 2nd explore subagent mapped the 3 pillars (23 tool-uses, 3 findings tables); design specs read in full'
---

# Epic E (re-scoped) — the full **learn → miss → revise** skill loop

> **The re-scope.** Human gate 2026-07-11: *"replace E1 with full learn, miss, revise skill based on the
> design artifact; brainstorm how to naturally integrate with the existing system."* E1 is no longer the
> static "skill-detail screen." It is the **loop**: a learner opens a skill, **learns** it (lesson blocks),
> **practises** it (quiz), **misses** items (capture), and **revises** (FSRS re-schedule + a returning-state
> lesson that leads with the miss). Depth = **I-3** (absorb the 9-block schema). The design constraint is the
> word **"naturally"**: reuse the ports that already run this loop in the generic quiz — do not fork a parallel one.

## The key realisation: the loop already exists — it's just not *pinned to a skill or fronted by a lesson*

The existing quiz path **is** a learn→miss→revise loop; three verified ports already run it end-to-end:

| Loop phase | Existing port (already wired in `EnginePortBag`) | What it does | file:line |
|---|---|---|---|
| **LEARN / serve** | `Scheduler.next()` | picks (skill, question) from `skill_state`; **subject-agnostic** | `lib/ports/engine/scheduler.ts:9-70`; `fsrs_scheduler.ts:73-164` |
| **MISS / capture** | `AttemptRepo.record()` | append-only `Attempt` row | `lib/ports/engine/attempt_repo.ts:37-45` |
| **REVISE / reschedule** | `Scheduler.review(attempt)` | **sole** writer of `skill_state` (mastery/stability/`due_at`) | `scheduler.ts:37,68-69`; `fsrs_scheduler.ts:166-199` |
| revise / read | `LearnerReadRepo.listSkillState` | per-skill `due_at` + mastery, read-only | `lib/ports/engine/learner_read_repo.ts` |
| session tally | `SessionRepo.open/close` | `open(subject,learner,mode,focus?,targetCount?)` / `close(id,score)` | `lib/ports/engine/session_repo.ts:30-56` |

So the re-scoped E1 is **not** "build a loop." It is **"front the existing loop with a lesson, and pin it to
one skill."** That reframing is what makes the integration natural — and it shrinks the genuinely-new surface
to a short list (see §"What is actually new" below).

The design artifact even names this mapping: its **three context presets ARE the loop's three states.**

| Artifact context (`lesson-blocks-schema.json`) | Loop state | Block recipe | Driven by |
|---|---|---|---|
| `newSkill` | **LEARN** (first exposure) | rule → workedExample → completionTry → selfExplainPrompt → accuracyStat | `skill_state` absent / low mastery |
| `returning` | **MISS→REVISE** (has misses, due) | misconceptionCallout → annotatedExample → rule → dueChecklist → accuracyStat → coachEntry | recent misses + `due_at` past |
| `refresher` | quick **REVISE** (high mastery) | annotatedExample → rule → accuracyStat | mastery high, nothing due |

And the composer's own `selection` note: *"the context is not a preset name but a decision from learner state
(mastery, recent misconception tags, due schedule) — the same signals the v2 outer loop uses."* **That is the
integration seam, verbatim: the context selector consumes the same mastery/miss/due signals the scheduler
already computes.** No new signal source — a pure translator over existing reads.

---

## Premise audit (loop-integration premises; verified by the 2nd scout this session)

| # | Premise | Status | Evidence |
|---|---------|--------|----------|
| L-1 | The scheduler is **subject-/skill-agnostic** — `next()` reads `skill_state` only and takes **no focus param**; `?focus=` sets the *session mode*, never pins the pick | **verified** | `fsrs_scheduler.ts:73-78` (no focus arg); `resolve_focus_mode.ts:32-54`; matches [[preact-drill-focus-not-pinned]] |
| L-2 | `Attempt` carries `question_id` + `created_at` but **NO `misconception` and NO `skill_id`** | **verified (corrects prior brainstorm)** | `engine_entities.ts:224-235` |
| L-3 | Per-skill misses are a **UI-side 2-hop join** (`AttemptRepo.misses()` → per-id `QuestionRepo.get()` → filter `skill_id`), living in `use_coach_surface.ts:29-48` — **not** `use_coach.ts:111` (that's only the call site) | **verified (corrects prior file ref)** | `use_coach_surface.ts:29-48`; `use_coach.ts:110-115` |
| L-4 | `misconception` exists on `Question`/`TestItem` but **no UI reads it**, and it is **not** on the miss record → surfacing a misconception is a **3-hop** join (miss→question_id→`Question.misconception`) **and** requires bank rows to actually be tagged (content question, unverified) | **verified** | `engine_entities.ts:76-77,151-152`; no UI reader |
| L-5 | `Scheduler.review(attempt)` is the **sole** `skill_state` writer; no separate `SkillStateRepo` port exists (reads via `LearnerReadRepo`, writes via `Scheduler` only) | **verified** | `fsrs_scheduler.ts:166-199` (`upsertSkillState:194`); `SkillStateRepo` = test/comment refs only |
| L-6 | `getTutorial`/`listProgressPoints` are the **only** engine reads that are DB-only — no port, no repo class, **absent from `EnginePortBag`**; every other repo the loop needs is already wired | **verified** | `engine_db.ts:160-161`; `composition_engine.ts:64-87` (bag has questionRepo/attemptRepo/sessionRepo/scheduler/grader/contentRepo/learnerRead/hintRepo/testItemRepo/…, **no** tutorial/progress) |
| L-7 | `/learn/skill` route is absent; `BucketCard` "drill this skill" is an **interim `?focus=`** link explicitly commented as a stand-in "never the dead /learn/skill route" | **verified** | `find` (no `skill/` dir); `BucketCard.tsx:8-11,24-26` |
| L-8 | VM/translator precedent for a skill surface exists: `bucket_card_vm.ts` + `coach_surface_vm.ts` (pure T1 maps, **honest-null** for missing aggregates) — the pattern a `skill_detail_vm.ts` mirrors | **verified** | `coach_surface_vm.ts:94-104` |

**Correction folded in (from the prior integration brainstorm):** I previously called `misconceptionCallout`
"the one block with live data." L-2/L-4 sharpen that — the tag is *reachable* but 3 hops away and gated on
whether bank rows are tagged. It is still the **most-data-backed** block, but its integration cost is
"author the tag library + build a 3-hop join + verify bank coverage," not "read a column." That moves it from
"free block" to "the one block whose data path is worth a spec sub-section."

---

## Directions (how to integrate the loop naturally — each reuses the 3 ports, differs in *pinning* + *lesson wiring*)

### N-1 — **Pin the scheduler; lesson fronts the SAME session** *(high-prob; smallest honest change to the loop)*
Add an optional `skillId` filter to `Scheduler.next()` (close the D-4 gap [[preact-drill-focus-not-pinned]]).
The `/learn/skill` screen renders the lesson (blocks), and its "Practise" CTA opens a **normal quiz session**
with `focus=skillId` **that now actually pins**. Miss + revise are *unchanged* — the same `AttemptRepo.record`
+ `Scheduler.review` the generic quiz already calls. The lesson is a **new front door**; the loop's body is untouched.
- **Tradeoff:** minimal new engine surface — one scheduler param + a lesson read. But the lesson and the quiz
  are still **two screens** (lesson → practise navigates to `/learn/quiz?focus=`); the "learn→miss→revise on one
  surface" is achieved by *pinning + navigation*, not by co-locating quiz inside the skill screen.
- **What breaks:** the `skillId` filter is an ⚠️ engine-behaviour change → ADR (closes a known gap, low risk). If
  no question matches the skill, `next()` must define a fallback (empty-state, not a throw).
- **Invariant stressed:** scheduler contract change (ADR); otherwise pure reuse.

### N-2 — **Context-driven lesson: one screen, three states, driven by existing signals** *(high-prob; the artifact's own design)*
N-1's pinning **plus** the artifact's context selector: a **pure translator** `selectLessonContext({mastery,
misses, due})` → `newSkill | returning | refresher`, fed by `LearnerReadRepo.listSkillState` (mastery/due) + the
existing 2-hop miss join (L-3). The screen renders the block recipe for that context. This is I-3 (blocks) +
the *context* layer of the artifact **without** the full 6-mode SCQA engine (that's I-4, deferred).
- **Tradeoff:** delivers the artifact's real thesis (the lesson adapts to learn-vs-revise state) using **only
  signals that already exist** — no new engine concept, unlike the 6-mode `selectMode` which needs
  `feelsProblem`/`prefersWorked` we don't emit. 3 contexts fire from mastery/miss/due alone (all present).
- **What breaks:** `returning` leads with `misconceptionCallout` → forces the L-4 3-hop join + tag-library
  authoring onto the critical path. And `dueChecklist`/`accuracyStat` (rail blocks) need per-skill due items +
  the 6-session accuracy (SD-4, no primitive — build from progressbar).
- **Invariant stressed:** I-3 wire schema (blocks) + the context translator (T1 pure); leakage lint on callout text.

### N-3 — **Co-locate the quiz inside the skill screen (learn + practise on one surface)** *(exploratory; deepest "one loop" reading)*
Beyond N-2: embed the actual quiz *inside* `/learn/skill` — lesson blocks on top, an inline practise panel below,
so a learner never leaves the skill to miss/revise. The `completionTry` block (backward-faded practice) becomes a
**real graded item** via `AttemptRepo.record` + `Scheduler.review`, not a mock.
- **Tradeoff:** the most literal "learn→miss→revise on one screen." But it **duplicates quiz-session lifecycle**
  (open/close/tally, the session-close bug surface [[preact-quiz-session-close-bug]]) *inside* a screen that also
  hosts a lesson — two stateful concerns on one route. High G1/complexity risk; likely a program-rule-#4 split.
- **What breaks:** session ownership (does the skill screen own a `SessionRepo` session, or borrow the quiz's?),
  and the `completionTry`-as-real-item blurs "lesson content" vs "quiz item" — the provenance/verification cascade
  now spans both. Big.
- **Invariant stressed:** program-rule-#4 (releasable increment), session-lifecycle duplication, G1.

### N-4 — **Miss-first entry: the loop starts from a miss, not a lesson** *(exploratory; under-used-signal lens)*
Invert the entry: the primary way into `/learn/skill` is from a **miss** (Summary/Coach "you missed these on
Punctuation" → skill screen in `returning` context, leading with the misconception). The lesson is framed as
*remediation of a specific miss*, not generic teaching.
- **Tradeoff:** highest pedagogical focus — every visit is anchored to a real error (the SD-3 region as the hero,
  matching the sibling design D6). But it **subordinates the LEARN state** (first-exposure `newSkill`) to the
  revise state, and depends most heavily on the L-4 tag path being populated — if bank rows aren't tagged, the
  hero region is empty.
- **What breaks:** first-time learners (no misses) get a degraded entry; the 3-hop tag join is now load-bearing
  for the *primary* flow, not a secondary block.
- **Invariant stressed:** the leakage discipline (miss-evidence text) + content-coverage dependency (`needs-probe`
  on bank tag coverage).

### N-5 — **Two-loop split: ship LEARN now, MISS→REVISE behind the tag library** *(exploratory; dependency-honest sequencing)*
Recognise that LEARN (`newSkill` context) needs **no misconception data** — just the lesson blocks + pinned
practise. MISS→REVISE (`returning`) needs the tag library + 3-hop join + accuracy chart. So **split**: E1a ships
the pinned-lesson + LEARN context + practise (all reuse, one scheduler param, one new lesson wire type); E1b adds
the `returning`/`refresher` contexts once the misconception library is authored + cascaded.
- **Tradeoff:** each half is independently releasable (program-rule-#4 clean); E1a de-risks the schema+route+repo
  wiring without blocking on content authoring. But it defers the "miss→revise" half — the user asked for the
  *full* loop, so this is a sequencing proposal, not a scope cut.
- **What breaks:** nothing — it's the same work, ordered by data-readiness. The question is whether the user wants
  one drop or a de-risked two-step.
- **Invariant stressed:** none new; it's the releasability-honest packaging of N-2.

### N-6 — **Fork a parallel per-skill engine** *(exploratory; named to REJECT)*
Build a new per-skill scheduler/miss/session stack dedicated to `/learn/skill`, independent of the generic quiz ports.
- **Tradeoff:** total layout freedom. But it **violates the explicit "naturally integrate" instruction** — two
  schedulers, two miss paths, two `skill_state` writers (L-5 says there must be exactly one), guaranteed drift.
  This is the anti-direction the re-scope exists to avoid. **Reject.**
- **Invariant stressed:** L-5 (single `skill_state` writer), DRY across the loop. Anti-direction.

---

## What is actually NEW (vs. reuse) — the short list the re-scope produces

Because the loop already runs (LEARN/MISS/REVISE ports all wired, L-6), the genuinely-new surface is small and
**explicit**:

1. **Scheduler skill-pinning** — an optional `skillId` on `Scheduler.next()` (⚠️ engine ADR; closes D-4). *All directions except N-6 need this.*
2. **Lesson content wire type + write/read path** — the I-3 blocks schema as a new wire type, a `TutorialRepo`/`LessonRepo` port + composition wiring (the ONLY unwired reads, L-6), `insertTutorial` write seam (⚠️ ADR), and the B2 generator emitting **validated block JSON** through the provenance cascade (mirror hints [[coach-bank-hints-brainstorm]]).
3. **Context selector translator** — pure `selectLessonContext({mastery,misses,due})` (N-2+); no new signal, T1 pure.
4. **Misconception tag library + 3-hop join** — author the 16-tag taxonomy (pedagogy spec §3.3) → generate → leakage-lint → review; build the miss→question→tag join; **verify bank coverage** (`needs-probe`). *Load-bearing for `returning`/N-4; deferrable in N-5.*
5. **SD-4 accuracy chart** — 6-session per-skill accuracy from `SessionRepo.listClosedSessionsByLearner` (build from progressbar idiom; no chart primitive).
6. **Do-regardless:** route shell · `comingSoon:false` flip + 2 dormant entry points · `skill_detail_vm.ts` (mirror `coach_surface_vm.ts` honest-null) · token reconciliation (`--b-punct` → `--color-bucket-*`).

Everything else — serving questions, recording misses, FSRS rescheduling, session tally — is **reuse of wired ports**.

---

## Leading direction: **N-2 (context-driven single-surface lesson) + N-1's scheduler pin, packaged as N-5's two-step if releasability demands**

- N-2 is the artifact's own design realised with **only existing signals** (mastery/miss/due) — it delivers the
  full learn→miss→revise adaptivity the user asked for, without the I-4 6-mode engine that needs signals we don't emit.
- N-1's scheduler pin is a **prerequisite of N-2** (a per-skill loop that can't pin its practise isn't a skill loop) —
  and it closes a standing defect, so it earns its ADR independent of E.
- N-5 is the **fallback packaging**: if the misconception tag library (new-piece #4) can't be authored+cascaded in
  the E1 window, ship LEARN first (E1a) and MISS→REVISE second (E1b) — same work, data-readiness order. This keeps
  program-rule-#4 satisfiable without cutting scope.
- **Rejected:** N-3 (quiz-in-screen — session duplication, split anyway) as *too much for one increment*; N-6 (fork)
  as *against the integration instruction* (L-5 single-writer).

**Hypotheses:**
- *Works because* the loop's three ports are already wired + proven in the generic quiz (L-6), the context selector
  is a pure map over reads that already exist (L-3/L-5/L-8), and the lesson render reuses tokens + `react-markdown` +
  the block schema the artifact fully specified. New engine surface = one scheduler param + one wire type + one translator.
- *Safe because* MISS and REVISE are **literally the same calls** the quiz makes (no second `skill_state` writer, L-5),
  the context translator is T1-pure (no I/O), misconception text goes through the hint leakage lint, and every filled
  accent pairs with `on-*` (AA).
- *Forward-compatible because* the 3-context selector is the **lower half of the artifact's 6-mode engine** (`AL-23`:
  modes sit above contexts/blocks) — I-4 later adds modes *above* this without disturbing the block layer or the loop.

**needs-probe (measure before committing #4 to the critical path):** (a) how many bank rows actually carry a
`misconception` tag today (L-4 content coverage) — if near-zero, N-5's split is forced; (b) does
`listClosedSessionsByLearner` return enough per-skill history to fill the 6-bar accuracy, or is it sparse for new skills.

### PROBE RESULT (a) — misconception-tag coverage, measured 2026-07-11

`docs/plan/coach-item-bank-live.promoted.json`: **47 / 171 promoted items carry a `misconception` tag = 27%,
spread across all 6 skills.** Seed bank (`coach-item-bank-live.seed.json`): 0 / 192 (tags exist only on
*promoted*, cascade-verified items). Tags are **free-text, human-readable, per-item** — e.g. *"hearing 'could've'
as 'could of'"*, *"confusing weather/whether by sound"*, *"the sentence sounds fine aloud because the meaning is
guessable"* — **NOT a controlled 16-tag taxonomy.**

**What 27% means for the split (this is decisive, folds into tracks 2 & 4):**
- Enough to **demonstrate** `returning`/`misconceptionCallout`, **not** enough to **rely** on it: a learner's
  specific missed item has ~1-in-4 odds of being tagged → the callout block **MUST have a graceful fallback**
  (generic miss-*count* evidence — the existing `countMissesOnSkill`) when the missed item is untagged. It cannot
  assume a tag exists. (New-piece #4 gains a fallback requirement.)
- The tags are **free-text, not the pedagogy-spec §3.3 16-tag taxonomy** → "author the tag library" is really
  **normalize existing free-text tags into a taxonomy** (a mapping/clustering layer over 47 real strings), lighter
  than greenfield authoring but a distinct piece with its own leakage-lint pass.
- **Confirms N-5 is the right packaging, not forced-by-emptiness:** E1a (LEARN) needs **zero** tags → ships on
  solid ground; E1b (MISS→REVISE) rides the 27% *with the fallback*, and taxonomy-normalization is its own tracked
  sub-piece inside E1b. The split is data-readiness-honest, not a scope dodge.

Probe (b) — `listClosedSessionsByLearner` per-skill history depth — still open; run at spec time when seeding a
realistic multi-session learner.

---

## Human gate — pick the loop-integration shape (independent tracks)

1. **Integration shape** (pick one): **N-2 context-driven single surface** *(recommended)* · N-1 pin-only (lesson +
   navigate to quiz) · N-3 quiz-embedded-in-screen · N-4 miss-first entry.
2. **Packaging** (pick one): **single E1 drop** (all three contexts at once) · **N-5 two-step** (E1a LEARN now,
   E1b MISS→REVISE behind the tag library) *— recommended if the probe shows low tag coverage*.
3. **Scheduler pin** — confirm the `Scheduler.next(skillId?)` ADR is in-scope for E (it's a prerequisite for any
   per-skill loop and closes D-4). *(recommended yes)*
4. **Misconception path** — author the 16-tag library + 3-hop join **in E1** (needed for `returning`/N-4), or start
   `returning` with generic miss-*count* evidence and add tag-specific callouts in a follow-up? *(gate on the probe)*
5. **Do-regardless (confirm, no gate):** scheduler pin ADR · lesson wire type + `LessonRepo` port + composition ·
   route shell + `comingSoon:false` flip · `skill_detail_vm.ts` honest-null · token reconciliation · leakage-lint on callout text.

## Open integration questions (gate with the shape pick)

1. **Lesson wire type home (I-3):** blocks on `Tutorial` (cross-language wire kernel, W2) or a **new `LessonPlan`
   wire type** referencing a flat `Tutorial`? (New type isolates the churn — recommended.)
2. **Practise session ownership (N-2 vs N-3):** does the skill screen *navigate to* the existing quiz session
   (N-2, reuse) or *own* an embedded session (N-3, duplicate lifecycle)? The pick decides whether E1 touches
   `SessionRepo` lifecycle at all.
3. **`completionTry` semantics:** is the faded-practice block a *lesson illustration* (mock, no attempt row) or a
   *real graded item* (`AttemptRepo.record` + `Scheduler.review`)? Real → it enters the miss/revise loop and the
   provenance cascade; mock → it's lesson content only. (Recommend mock in E1, real in a later increment.)
4. **Tag-library coverage probe:** run the read-only count of tagged bank rows before committing the 3-hop
   misconception path to the critical flow (drives track 2 + 4 above).
5. **DC-vs-React:** confirm the `.dc.html` sources are **visual spec only** (non-portable DC runtime) — re-author
   the block components in React/Tailwind, mirroring `bucket_card_vm.ts` for the VM.
