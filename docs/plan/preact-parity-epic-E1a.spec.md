# Spec — Epic E1a: `/learn/skill` adaptive lesson surface (3-context)

**Status:** Draft — 2026-07-11
**Owner:** Rajnish Khatri
**Related:**
- Design contract (UI, authoritative): [`PreACT-English-Coach-v2-E1-LearnSkill-Implementation-Spec.md`](../../eng-coach-ui-design/e1-learn-skill-delivery/specs/PreACT-English-Coach-v2-E1-LearnSkill-Implementation-Spec.md) — the whole `/learn/skill` surface; its `FR-CTX-*`/`FR-CMP-*`/`FR-BLK-*`/`AC-*` are the UI behavior this spec ships. **Scope note:** the design spec §12.1 splits E1a (newSkill) from E1b (returning/refresher); a 2026-07-11 human gate re-scoped this spec to the **full 3-context surface** with two honest carve-outs (§1.1) — so the design spec's `returning`/`refresher` requirements are in scope here, its `E1b` accuracy-aggregation + tier-1 aggregate callout are not.
- Ratified decisions: [`Adaptive-Lesson-Decisions.md`](../../eng-coach-ui-design/e1-learn-skill-delivery/specs/Adaptive-Lesson-Decisions.md) (D1–D8 / I1 / A1–A3)
- SDD Stage-1: [`preact-parity-epic-E-learn-miss-revise.brainstorm.md`](preact-parity-epic-E-learn-miss-revise.brainstorm.md) (N-2 surface; **N-5 two-step gate superseded** by the full-surface re-scope) · [`preact-parity-epic-E-lesson-generation.brainstorm.md`](preact-parity-epic-E-lesson-generation.brainstorm.md) (A1 + B2 + file-research)
- Program: [`preact-parity-epics.md`](preact-parity-epics.md) (Epic E gate) · board [`preact-parity-sprint-board-E.md`](preact-parity-sprint-board-E.md)
- ADR (the *why*): [`0028-lesson-content-read-path.md`](../adr/0028-lesson-content-read-path.md) — one bundled ADR covering the teaching-field extension + read ports + authored-seed provenance (mirrors ADR-0014/0015/0021).
- Constitution: root `AGENTS.md` (8 invariants) · `docs/style-guides/STYLE_GUIDE_FRONTEND.md` (Frontend Ring W/P/A/T/C rules).

---

## 1. Goal

Ship the `/learn/skill` **adaptive lesson surface** — one English skill's content,
composed into a different ordered block sequence per learner **context**
(`newSkill` / `returning` / `refresher`), selected by `selectLessonContext` — as a core
screen in the coach shell. It fronts the existing learn→miss→revise loop with a lesson,
ends every context on its deepest available resolution, hands the learner into
skill-pinned practice, and writes **nothing** to mastery or the review schedule.

### 1.1 Scope — full 3-context surface, two honest carve-outs

A 2026-07-11 human gate re-scoped this from "newSkill only" to the **full 3-context
surface**. In scope: all three context render paths + the `selectLessonContext` selector
+ the misconception callout (verbatim, tier-2/3) + `annotatedExample` + the cross-skill
`dueChecklist` + the read-seam wiring + a hand-authored lesson seed.

**Two carve-outs, each because the honest data does not exist yet** (Stage-2 grounding,
not a preference):
- **`accuracyStat` self-omits.** True per-skill answer-accuracy has no read today
  (`Attempt` carries `question_id` but no `skill_id`; no aggregation exists; no bar-chart
  primitive; no ≥6-session fixture to test against). Per D7/`GUARD-ACC-1` the block
  renders **only when real accuracy data exists** and self-omits otherwise — it never
  fabricates a trend or substitutes the mastery scalar. The new AttemptRepo per-skill
  accuracy read + 6-bar chart primitive + multi-session fixtures are a **follow-up**.
- **Tier-1 aggregate callout deferred.** The "Your pattern · X" cross-miss aggregate
  needs a reviewed tag-clustering pipeline that does not exist; E1a ships **tier-2**
  (verbatim single newest-due miss) and **tier-3** (untagged → hide) only (`I1`).

## 2. Context

The loop already runs in the generic quiz through three wired ports (LEARN =
`Scheduler.next()`, MISS = `AttemptRepo.record()`, REVISE = `Scheduler.review()` —
the sole `skill_state` writer). E1a does **not** build a loop; it fronts the existing
loop with a lesson and a skill-pinned practice entry. The design agent delivered a
build-ready UI contract (a `.dc.html` reference prototype + numbered requirements);
this spec adds the **engine-side seams the design contract defers to us** and states
the whole as testable EARS criteria.

Stage-2 grounding (workflow `wf_659b0811-763`, 6 seams verified at HEAD) corrected the
scope in three ways, each folded in below:
- **No scheduler-pin work.** `?focus=<skillId>` already pins drill mode via a separate
  code path (`openQuizItem` → `openDrillQuizItem` → `questionRepo.nextReviewed`,
  `use_quiz.ts:177-225`), bypassing the subject-agnostic `Scheduler.next()`. The
  "Practice this skill →" CTA is just a link to `/learn/quiz?focus=<skillId>` — the
  `BucketCard.tsx:26` / `SummaryView.tsx:44` pattern, already e2e-covered. Zero engine
  change; the earlier D-4 scheduler-pin ADR is **dropped**.
- **D5 is a Drizzle-schema change, not a Rule-W2 cross-language change.** `Tutorial`
  (`engine_entities.ts:273-282`) is explicitly exempt from the Python↔TS wire mirror
  (ADR-0005 local-first; absent from `baseline_drift.test.ts`). Adding optional
  teaching fields follows the in-file `Verdict` optional-field precedent
  (`engine_entities.ts:303-309`).
- **Provenance is earned by a hand-authored + reviewed seed**, not a generator, for the
  first drop — mirroring the hint family's accepted `"authored"` stamp. The B2
  generator (`tutorial_generation.py` + `.j2` + a quality judge) is the E1b scale-up.

## 3. Functional requirements (EARS)

Failure paths first (TAP-4). Each FR maps to ≥1 test in §8. Requirements tagged
`⟶ <ref>` cite the design contract requirement they satisfy.

### Provenance & content integrity (failure paths)

- **FR-1.** IF a `tutorial` row has `reviewed = false` (or a `generated_from` that does
  not match the confinement format), THEN THE SYSTEM SHALL NOT serve it to `/learn/skill`
  — the reviewed gate is the same one the hint/test-item families enforce. *(Provenance
  is earned, never asserted at serve time.)*
- **FR-2.** IF a checked-in tutorial seed row carries `reviewed: true` with a
  `generated_from` that is neither `hand:<author>@<date>` nor `llm:<model>@<promptrev>`,
  THEN the architecture test SHALL fail the build (mirror
  `test_hint_provenance_confinement.py`). *(No forged stamp.)*
- **FR-3.** IF a skill has no reviewed tutorial content, THEN `/learn/skill` for that
  skill SHALL degrade honestly (render the header + a "lesson coming" empty state or a
  404-equivalent per the route contract), NEVER a fabricated lesson. *(Absence is the
  honest render; cf. AP-6.)*

### Context selection — `selectLessonContext` (D1)

- **FR-4.** WHEN `/learn/skill` is entered THE SYSTEM SHALL compute the context via
  `selectLessonContext({firstExposure, masteryPct, dueMisses, requested})`: `requested`
  wins; else `firstExposure || masteryPct == null → newSkill`; else
  `masteryPct >= 80 && dueMisses == 0 → refresher`; else `dueMisses > 0 → returning`;
  else `newSkill`. ⟶ `FR-CTX-1..5`, `AC-1`.
- **FR-5.** THE SYSTEM SHALL treat a misconception tag on a non-due miss as
  non-selecting — only `dueMisses > 0` routes to `returning`. ⟶ `FR-CTX-6`, `AC-3`.
- **FR-6.** THE SYSTEM SHALL render all three context paths: `newSkill` (§ FR-7..11),
  `returning` (§ FR-6a..6c), and `refresher` (§ FR-6d). The selector output drives the
  recipe; every context ends on its resolution (FR-10). *(Full-surface re-scope.)*

### The `returning` and `refresher` contexts (D2 / D6 / D8 / I1 / A3)

- **FR-6a.** WHILE the context is `returning` AND the newest due miss is **tagged** THE
  SYSTEM SHALL render the main zone `misconceptionCallout → annotatedExample → rule`,
  ending on `rule`; WHEN the newest due miss is **untagged** it SHALL drop the callout
  and render `annotatedExample → rule` (no gap). ⟶ `FR-CMP` returning row, `AC-4/5/7`.
- **FR-6b.** THE SYSTEM SHALL render the `misconceptionCallout` from the **newest due
  miss's verbatim** author-written tag with a single-item eyebrow ("On your last miss ·
  {skill}"), and SHALL NOT render a `fix` line, an aggregate "Your pattern" claim on a
  single miss, or any transformed/corrective text (leakage predicate). ⟶ `D6`, `I1`
  tier-2/3, `FR-BLK-16`, `GUARD-CALL-1`, `GUARD-LEAK-1`, `AC-7/8`.
- **FR-6c.** IF the newest due miss is untagged THEN the callout SHALL **hide** (tier-3)
  — the surface leads with `annotatedExample`; it SHALL NOT render a neutral miss-count
  line in its place. ⟶ `I1` tier-3, `DATA-CALL-1`, `AC-7`.
- **FR-6d.** WHILE the context is `refresher` THE SYSTEM SHALL render `rule →
  annotatedExample → pitfall(parting)`, ending on the parting `pitfall` (the AL-13
  exception, permitted because `rule` already led). ⟶ `FR-CMP-5`, `AC-5`.
- **FR-6e.** WHERE the context is `returning` THE SYSTEM SHALL render the rail
  `dueChecklist` (whole due skills from the scheduler, per-row skill-pinned "Drill →")
  and the skill-pinned `coachEntry` **seam** (button only; the lesson→coach seed contract
  is deferred — OQ-3). ⟶ `D8`, `D4c`, `FR-BLK-18/20`, `AC-11`. *(`dueChecklist` uses the
  existing whole-skill `due_at`; the intra-skill checklist is deferred.)*

### The block composer — `newSkill` inductive (D5 / A1 / A3)

- **FR-7.** WHILE the context is `newSkill` THE SYSTEM SHALL render the main zone in the
  order `ground → pitfall → question → selfExplainPrompt → rule → workedExample →
  completionTry`, each block in its resolved role tint, and no other blocks. ⟶ `FR-CMP-4`,
  `AC-4/5`.
- **FR-8.** THE SYSTEM SHALL compose block `order`/`zone`/`role`/tint at **render time**
  from raw authored content — it SHALL NOT read a persisted `blocks[]`/`zone`/`role`/
  `context`/`beats` array (order is not authored content). ⟶ `D5`, `FR-CMP-1/2`,
  `DATA-BLK-4/6`.
- **FR-9.** IF the composer encounters a recipe tag with no backing data, THEN it SHALL
  skip that block (no gap, no placeholder), never render an empty container. ⟶ `FR-CMP-6`.
- **FR-10.** THE SYSTEM SHALL end the `newSkill` main zone on the applied win
  (`completionTry`), and SHALL NOT end it on a tension block (`pitfall`) before `rule`
  has appeared. ⟶ `FR-CMP-7/8`, `GUARD-END-1`, `AC-5/6`.
- **FR-11.** THE SYSTEM SHALL render exactly one "▸ start here" opener marker (on the
  lead `ground` block) and SHALL NOT render a color-dot sequence. ⟶ `A2`,
  `FR-BLK-14/15`, `AC-14`.

### Interaction — inert to the scheduler (D3 / D4)

- **FR-12.** IF the learner interacts with `completionTry` (picks a choice) THEN THE
  SYSTEM SHALL grade locally (show ✓/✗, reveal the correct choice + one-line why on a
  miss, offer "↺ Try again", show "Practice this skill →" on success) and SHALL record
  no attempt, move no mastery, change no FSRS interval. `Scheduler.review()` /
  `AttemptRepo.record()` are NOT called. ⟶ `D3`, `FR-BLK-10/11/12`, `GUARD-NOWRITE-1`,
  `AC-12`.
- **FR-13.** THE SYSTEM SHALL NOT branch the lesson on a `completionTry` answer — a wrong
  pick reveals locally but does not change subsequent blocks. ⟶ `FR-BLK-13`.
- **FR-14.** WHEN the learner types into `selfExplainPrompt` THE SYSTEM SHALL echo the
  note back locally in the `rule` block ("You guessed: '{note}' …") and SHALL never
  store or score it. ⟶ `D4`, `FR-BLK-6/7/8`, `AC-13`.
- **FR-15.** WHEN the learner activates "Practice this skill →" THE SYSTEM SHALL navigate
  to `/learn/quiz?focus=<skillId>` (the existing skill-pinned drill entry), pinning
  practice to this skill. ⟶ §2 grounding; `use_quiz.ts:177-225`.

### Data gating — accuracy self-omit (D7)

- **FR-16.** THE SYSTEM SHALL render `accuracyStat` **only when real per-skill
  answer-accuracy data is available**, and SHALL self-omit otherwise — never a fabricated
  trend, never the mastery/retrievability scalar under an "Accuracy" label. Since no
  per-skill accuracy read exists yet (§4.4), the block **self-omits in every E1a context
  today** (no rail accuracy) until the accuracy aggregation ships as a follow-up. ⟶
  `FR-CMP-10/11/12`, `GUARD-ACC-1`, `AC-9`. *(Carve-out §1.1 — honest absence, not
  fabrication; the block's render path exists and activates when data arrives.)*

### Miss data — due-miss client-join (returning)

- **FR-16a.** THE SYSTEM SHALL identify "the newest due miss" for a skill via a **pure
  client-side join translator** over existing reads — `AttemptRepo.misses()`
  (newest-first) cross-referenced with `LearnerReadRepo.listSkillState()` `due_at` —
  mirroring the proven `use_summary.ts` `deriveMisconception` verbatim-tag binding. It
  SHALL add no new port or DB method. ⟶ Stage-2 grounding; `use_summary.ts:79-95`,
  `use_coach_surface.ts:26-48`.
- **FR-16b.** IF no due miss exists for the skill THEN the `returning` callout SHALL hide
  (same tier-3 render path as untagged), never fabricate a miss.

### Content read seam (engine wiring)

- **FR-17.** THE SYSTEM SHALL read lesson content through a read-only `TutorialRepo` port
  (`getTutorial(subject, skillId): Promise<Tutorial | null>`) and read progress through a
  read-only `ProgressRepo` port (`list(subject, learnerId): Promise<ProgressPoint[]>`),
  both wired into `EnginePortBag`, both mirroring the `HintRepo` read seam; serving code
  SHALL have no write surface on either port. ⟶ ADR-0014 template; `hint_repo.ts:26-29`.
- **FR-18.** IF `getTutorial` returns `null` THEN the surface SHALL take the FR-3 honest
  degrade path (no throw to the learner).

### Route shell & nav (do-regardless plumbing)

- **FR-19.** THE SYSTEM SHALL serve `/learn/skill` (a new `app/(coach)/learn/skill/`
  route, mirroring `learn/coach/page.tsx`), accepting the target `skillId` as a
  parameter — the surface SHALL NOT hardcode a skill. ⟶ `FR-DATA-BIND-2`.
- **FR-20.** THE SYSTEM SHALL flip the `skill` screen `comingSoon: true → false`
  (`nav_model.ts:75`) — activating the single dormant `summary-see-lesson` Link
  (`SummaryView.tsx:130-136`) — **and** add `"skill"` to `NAV_MEMBERSHIP`
  (`nav_model.ts:103-106`) so the Skill screen is a primary-nav destination (sidebar
  desktop/iPad, tab bar per the membership rules). *(Clarify Q3 → add to primary nav.)*

## 4. Data model / contracts

### 4.1 Lesson content — optional teaching fields on `Tutorial` (D5)

The durable authored content stays flat and close to today's shape. `Tutorial`
(`frontend/lib/wire/engine_entities.ts:273-282`) today:

```ts
Tutorial = { id, subject, skill_id, body_md, examples[], generated_from, reviewed }
```

E1a adds **optional** typed teaching fields (exact set finalized in the ADR; candidate
set below), following the `Verdict` optional-field precedent (`engine_entities.ts:303-309`
— fields added incrementally, absent for content that doesn't have them):

| candidate field | type | feeds block | note |
|---|---|---|---|
| `ground_md` | `string?` | `ground` | "what you already know" reminder |
| `pitfall_md` | `string?` | `pitfall` | generic structural trap (no miss data) |
| `question_md` | `string?` | `question` | the one framing question |
| `worked_example` | typed object? | `workedExample` | sentence + steps[] + answer |
| `completion_try` | typed object? | `completionTry` | sentence + choices[] (with `correct`) + why |
| `self_explain_prompt` | `string?` | `selfExplainPrompt` | the prompt text |
| `annotated_examples` | typed array? | `annotatedExample` | marked-up examples (pre/clause/post/essential/callouts) — `returning`+`refresher` |

- **NOT added to the persisted wire:** `blocks[]`, `zone`, `role`, `context`, `beats`,
  block `order`. Those are render-time composer outputs (FR-8; D5, `DATA-BLK-6`).
- The block VM (`BlockVM` — `tag/zone/role/border/background/ink/order` + resolved
  fields) is a **translator output**, not persisted (`DATA-BLK-4`).
- Cross-boundary: this is a **Drizzle-schema change** (`schema.pg.ts` + `schema.sqlite.ts`
  column adds + a migration), NOT a Rule-W2 change — verified: `Tutorial` is absent from
  `baseline_drift.test.ts` `schemaIndex` and `__python_schema_baseline__.json`.

### 4.2 `selectLessonContext` — pure T1 translator inputs (§3.1 of the design spec)

```ts
interface LearnerLessonState {
  firstExposure: boolean;        // no SkillState row for this skill
  masteryPct: number | null;     // SkillState.mastery (0..1 → pct); null on no row
  dueMisses: number;             // # due misses for this skill; derived by the §4.5 join
  requested?: LessonContext;     // explicit pick — overrides
}
type LessonContext = 'newSkill' | 'returning' | 'refresher';
```

`masteryPct` maps from `SkillState.mastery` (`engine_entities.ts:259`, the FSRS
retrievability scalar) — this is the **spec-correct** source for the selector; the
"mastery ≠ accuracy" dashboard bug is scoped to the `accuracyStat` VM (a different VM —
the accuracy carve-out §4.4), not to context selection (`DATA-CTX-2` / `DATA-ACC-1`).
`dueMisses` for the selector is a boolean-ish "any due miss" derived by the §4.5 join;
the precise integer count over sub-skill signals remains a follow-up (does not gate the
`returning` route, which fires on `dueMisses > 0`).

### 4.3 Read ports

- `TutorialRepo` (new, read-only): `getTutorial(subject, skillId): Promise<Tutorial|null>`.
- `ProgressRepo` (new, read-only): `list(subject, learnerId): Promise<ProgressPoint[]>`
  — wired now (clarify Q4 → both repos together).
- Both mirror `HintRepo` (`ports/engine/hint_repo.ts`) + `DrizzleHintRepo`
  (`adapters/engine/repos/drizzle_hint_repo.ts`), wired in `composition_engine.ts`
  (field at ~:75, `new Drizzle…Repo(db)` at ~:136). No `insertTutorial` — reads existing
  `EngineDb.getTutorial`/`listProgressPoints` (`engine_db.ts:160-161`).

### 4.4 What is NOT read (the accuracy carve-out)

True per-skill answer-accuracy has **no read** today: `Attempt` (`engine_entities.ts:224-239`)
carries `question_id` + `correct` but **no `skill_id`**; `listClosedSessionsByLearner`
(`engine_db.ts:107-111`) returns whole-session totals (`score_correct`/`score_total`),
not per-skill; no aggregation, chart primitive, or multi-session fixture exists. So
`accuracyStat`'s data source is a **follow-up** (a new per-skill accuracy read joining
`attempt.question_id → question.skill_id`, a hand-built 6-bar chart, seed fixtures);
E1a's block self-omits until then (FR-16).

### 4.5 Due-miss join (returning callout)

A **new pure translator** `newest_due_miss.ts` (or folded into `skill_detail_vm.ts`)
joins `AttemptRepo.misses()` (newest-first) × `LearnerReadRepo.listSkillState()` `due_at`
→ the newest miss whose skill is due, then `QuestionRepo.get(question_id).misconception`
→ verbatim tag (tier-2) or hide (tier-3). Mirrors `use_summary.ts:79-95`
`deriveMisconception` + `use_coach_surface.ts:26-48` `countMissesOnSkill`. No new port.

## 5. Invariants & security boundaries

Architecture invariants touched, and why each holds:

- **Frontend Ring — Rule T1 (pure translators).** `selectLessonContext`, the newest-
  due-miss join (§4.5), and `skill_detail_vm.ts` import only `wire/` (+ locally-defined
  E1a types); no I/O, no React, no SDK. Holds: the selector is a deterministic if/else
  over primitives (§4.2); the due-miss join takes already-fetched `misses`/`skillState`/
  `question` arrays as inputs (the caller/hook does the I/O), same as `deriveMisconception`.
- **Leakage predicate (`GUARD-LEAK-1`).** The misconception callout renders the tag
  **verbatim** — no transform into corrective text — the same predicate the Summary
  screen already ships; tags are author-written to not name the answer (FR-6b).
- **Frontend Ring — Rule P1/P6 (one interface per port, ports import only wire/).**
  `TutorialRepo`/`ProgressRepo` are single-method read interfaces mirroring `HintRepo`;
  no adapter import. Holds by construction.
- **Frontend Ring — Rule A4/A1 (SDK confined to adapters).** Drizzle stays in
  `adapters/engine/repos/`; the new repos wrap `EngineDb` exactly as `DrizzleHintRepo`
  does. Holds.
- **Frontend Ring — Rule C2 (compose at the root).** New repos wired only in
  `composition_engine.ts`. Holds.
- **Frontend Ring — Rule F5 / backend H1 (no prompts in TS).** E1a authors lesson
  content as **data** (seed rows), not prompts; the B2 generator prompt (`.j2`,
  deferred) would live in `prompts/`. Holds.
- **Downward-only deps (root invariant #1).** The read-only repos + translator sit in
  the Frontend Ring; nothing new reaches upward into the backend at module scope. Holds.
- **`Scheduler.review()` is the sole `skill_state` writer.** E1a's interactions
  (`completionTry`, `selfExplainPrompt`) are ephemeral/local and call no repo write
  (FR-12/14; `GUARD-NOWRITE-1`). Holds — verified the drill CTA only navigates.

**Security / boundary:** offline & deterministic (no LLM on this surface in E1 —
`NFR-OFFLINE-1`); the core screen is re-authored natively, **not** a sandboxed iframe
(strict CSP; the design contract's `.dc.html` is a visual reference only); no secrets.

**⚠️ Ask-first triggers → ADRs.** Per root `AGENTS.md` the following raise ADRs (Stage-3
plan decides 1-bundle-or-split):
1. **Lesson teaching fields on `Tutorial`** — G1 new-abstraction + a Drizzle migration
   (new persisted columns). File as G1/Drizzle, **not** Rule W2 (W2 mechanically does not
   fire — verified negative).
2. **`TutorialRepo`/`ProgressRepo` read ports** — the codebase ratchets "new read port"
   to an ADR (ADR-0014 and ADR-0015 each did, same read-seam shape).
3. **Authored-seed provenance-confinement** — a `test_tutorial_provenance_confinement.py`
   accepting `hand:<author>@<date>` | `llm:<model>@<promptrev>`; may be a
   `decisions.md` line rather than a full ADR (Stage-3 call).

**Dropped from the earlier scope** (grounding): scheduler-pin ADR (drill already pins);
`insertTutorial` write ADR (E1b — reads pre-seeded content); B2 generator + quality-judge
ADRs (E1b scale-up).

## 6. Edge cases

- **No reviewed content for the skill** → FR-3/FR-18 honest degrade (empty state), not a
  fabricated lesson.
- **`masteryPct == null` but `dueMisses > 0`** → selector returns `newSkill` (firstExposure
  branch wins before the due branch); confirm this is intended vs. `returning` — it is:
  no mastery yet means "keep teaching" (§4.1 of the design spec, `FR-CTX-2`).
- **`completionTry` has no `correct` flag in the seed** → the block must degrade to a
  read-only worked example (no gradable choices) rather than mis-grade.
- **`selfExplainPrompt` empty / whitespace note** → no echo chip renders (`hasNote`
  gate); the `rule` block renders plainly.
- **No due miss for a `returning`-routed skill** → the callout hides (tier-3 render path,
  FR-16b), never a fabricated miss.
- **Due miss whose skill has no `Question.misconception` tag** (~73%) → tier-3 hide;
  surface leads with `annotatedExample` (FR-6c). Not a miss-count line.
- **`dueMisses` count granularity** — the §4.5 join yields "any due miss" (boolean-ish),
  which is all the `returning` route needs (`dueMisses > 0`). The precise integer count /
  intra-skill breakdown remains a follow-up; E1a MUST NOT fabricate a count.
- **`accuracyStat` with no/partial per-skill accuracy read** → self-omit (FR-16); never
  substitute the mastery scalar. The block self-omits in every E1a context until the
  accuracy read ships (§4.4).
- **`refresher` for a skill with no `annotatedExample` content** → the composer skips
  that block (FR-9); `rule → pitfall(parting)` still ends on the parting caution.
- **Route entered with an unknown/absent `skillId`** → 404-equivalent, not a blank shell.

## 7. Non-functional requirements

- **Determinism / offline (`NFR-OFFLINE-1`).** No LLM, no network on this surface;
  fully deterministic render. Translator + selector are L1-pure.
- **Performance (`NFR-PERF-1`).** First paint < 100 ms; blocks paint top-to-bottom; only
  the try-grade and note-echo are late-bound.
- **Theme (`NFR-THEME-1`).** Light + dark via `data-theme`; `--accent` = the skill's
  `--color-bucket-*` token (via `Skill.accent_var`).
- **A11y (`NFR-A11Y-*`).** WCAG-AA both themes; role color always paired with a text
  label (`AL-25`/`AL-AC-8`); `role="status"` on try feedback; ≥44px targets; keyboard +
  visible focus.
- **State (`NFR-STATE-1`).** Read-mostly; only ephemeral local UI state (`note`,
  `tryPicked`); persists nothing.
- **No live LLM in CI.** Nothing on this path calls a model; all tests deterministic.

## 8. Test plan

Failure-path tests before happy-path. Layers: L1 deterministic / L2 reproducible /
L3 probabilistic / L4 behavioral (e2e).

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `TutorialRepo` conformance: unreviewed row not returned | L1 (vitest) | yes |
| FR-2 | `tests/architecture/test_tutorial_provenance_confinement.py` rejects bad `generated_from` | L1 (pytest arch) | yes |
| FR-3/18 | skill_detail render: no content → empty state, not fabricated | L1 (RTL) + L4 (e2e) | yes / e2e |
| FR-4 | `select_lesson_context.test.ts` — `describe.each` over design §9.2 5 rows | L1 (vitest) | yes |
| FR-5 | selector: tag on non-due miss does not flip to `returning` | L1 | yes |
| FR-6 | all three context render paths reachable from selector output | L1 (RTL) | yes |
| FR-6a | `returning` tagged → `misc→annotated→rule`; untagged → `annotated→rule` | L1 (RTL) | yes |
| FR-6b | callout: verbatim tag, single-item eyebrow, no `fix`, no "Your pattern" on n=1 | L1 (RTL) | yes |
| FR-6c | untagged due miss → callout hides; leads with `annotatedExample`; no miss-count line | L1 (RTL) | yes |
| FR-6d | `refresher` → `rule→annotated→pitfall(parting)`, ends on parting `pitfall` | L1 (RTL) | yes |
| FR-6e | `returning` rail: `dueChecklist` whole-skill rows + `coachEntry` seam button | L1 (RTL) | yes |
| FR-7 | composer renders newSkill recipe in order, no other blocks | L1 (RTL) | yes |
| FR-8 | composer reads raw fields, no `blocks[]` in persisted read (type-level + row assert) | L1 | yes |
| FR-9 | composer skips a tag with no backing data (no empty container) | L1 (RTL) | yes |
| FR-10 | main zone ends on `completionTry`; never ends on `pitfall` pre-`rule` | L1 (RTL) | yes |
| FR-11 | exactly one "▸ start here"; no color-dot sequence | L1 (RTL) | yes |
| FR-12 | `completionTry` click grades locally; asserts no `attemptRepo.record`/`scheduler.review` call (spy) | L1 (RTL) | yes |
| FR-13 | wrong pick does not change subsequent blocks | L1 (RTL) | yes |
| FR-14 | self-explain note echoed in `rule`; never persisted (spy) | L1 (RTL) | yes |
| FR-15 | "Practice this skill →" navigates to `/learn/quiz?focus=<skillId>` | L4 (e2e) | e2e |
| FR-16 | `accuracyStat` self-omits with no aggregation; no fabricated trend | L1 (RTL) | yes |
| FR-16a | newest-due-miss join: table-driven over (misses × skillState × question) fixtures | L1 (vitest) | yes |
| FR-16b | no due miss → callout hides | L1 | yes |
| FR-17 | `TutorialRepo`+`ProgressRepo` wired in `EnginePortBag`; read-only (no write method) | L1 (arch/type) | yes |
| FR-19 | `/learn/skill?skill=<id>` renders; unknown id → 404-equiv | L4 (e2e) | e2e |
| FR-20 | `comingSoon` flip activates `summary-see-lesson` Link; `summary-payoff.spec.ts` updated | L4 (e2e) | e2e |

**Watched-red first:** each FR test is written and seen to fail before the
implementation (root `AGENTS.md` red/green rule). The `summary-payoff.spec.ts:130-143`
disabled-button assertion is **rewritten** (not left passing) under G8 — the rewrite is
justified because the `comingSoon` branch it asserted no longer exists once flipped.

## 9. Definition of Done

- [ ] All FRs implemented; each has a passing test seen to fail first.
- [ ] `make check` green (lint + format-check + pyright + cite-lint + hygiene + test).
- [ ] `pytest tests/architecture/ -q` green (incl. the new provenance-confinement test).
- [ ] Frontend arch/layering + a11y (axe) green; e2e for FR-15/19/20 green.
- [ ] Invariants in §5 unbroken; ADR(s) appended for the §5 triggers with `index.md` +
      `log.md` entries; `decisions.md` line for any sub-ADR choice.
- [ ] Lesson seed for ≥1 skill authored, human-leak-checked, stamped
      `reviewed:true` + `generated_from="hand:<author>@<date>"` — never a forged stamp.
- [ ] Actual command output pasted (not summarized) for the verification claims.
- [ ] Design contract `AC-1..AC-17` demonstrably satisfied for **all three contexts**,
      except the two carve-outs (§1.1): `accuracyStat` (`AC-9/10` — self-omit path
      verified; real-data render is a follow-up) and the tier-1 aggregate callout.

## 10. Clarify pass — resolved (2026-07-11)

The Stage-2 ambiguity pass ran two rounds of targeted questions; all resolved:

- **Scope (round 1).** → **Full 3-context surface** (not newSkill-only). Supersedes the
  N-5 two-step gate. Consequences absorbed above (FR-6a..6e, §1.1).
- **ADR bundling (round 1).** → **One bundled ADR** — "lesson content read path"
  (teaching fields + Drizzle migration + `TutorialRepo`/`ProgressRepo` read ports +
  authored-seed provenance test). §5.
- **Nav membership (round 1).** → **Add `"skill"` to `NAV_MEMBERSHIP`** (primary-nav
  destination). FR-20.
- **ProgressRepo (round 1).** → **Wire both repos now**. FR-17, §4.3.
- **accuracyStat gap (round 2).** Grounding found no honest data (no per-skill accuracy
  read, no chart primitive, no ≥6-session fixture). → **Self-omit; build the rest.** The
  accuracy read + chart + fixtures are a follow-up. §1.1, §4.4, FR-16.
- **Due-miss read (round 2).** Grounding found "newest due miss" has no existing read. →
  **Client-side join in a new pure translator** (no new port/DB method), mirroring
  `use_summary.ts` `deriveMisconception`. §4.5, FR-16a.

### Remaining open (do not block the spec; resolve at plan/impl time)

- **OQ-3 (design spec).** The lesson→coach seed contract when no active `question_id`
  — the `coachEntry` ships as a **seam** (button only) in E1a; the seed contract is
  deferred. FR-6e.
- **Teaching-field granularity** — `workedExample`/`completionTry`/`annotatedExample`
  as typed sub-objects vs. flat markdown: finalized in the ADR's data-model section
  (lean: typed sub-objects for the interactive/marked-up blocks, flat markdown for
  `ground`/`pitfall`/`question`/`selfExplainPrompt`). §4.1.
```
