# Spec — PreACT English Coach · Engine Requirements

> **Scope discipline.** This is the **engine** spec — the sibling the
> [UI spec](preact-english-coach-ui.spec.md) names three times as the owner of
> "the quiz engine, FSRS scheduler, data persistence, content-generation pipeline,
> or backend." It is the testable *what* of everything **behind** the view-models:
> the adaptivity loop, the `reviewed` gate, grading, sessions/attempts, the offline
> generation pipeline, and content delivery. Where the engine *produces* what the UI
> consumes (questions, mastery numbers, the coach context), this spec owns the
> contract and the UI spec owns the rendering. It does **not** re-spec any screen.
>
> This spec *implements* decisions already ratified — it does **not** re-decide them:
> - [ADR-0005](../adr/0005-subject-coach-engine-home-and-substrate.md) — engine home (Frontend-Ring local-first) + substrate (Drizzle, Postgres↔SQLite, no sync yet). **Accepted.**
> - [ADR-0006](../adr/0006-subject-coach-component-protocols.md) — the seven component protocols (ports) + the `Verdict` shape + the renderer registry. **Accepted.**
> - [Data & protocols design doc](../Architectures/SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md) — the entity model (§2) this spec's data section references rather than restates.
>
> No `⚠️ Ask first` trigger fires here: the abstractions, the substrate, and the
> protocols are all pre-decided in the two Accepted ADRs above. The one item still
> flagged-not-decided is the **coach-agent fork from `reactLoop`** (a separate
> new-graph-node ADR); this spec consumes the coach only as an existing SSE stream.
>
> Acceptance criteria use **EARS** so each one is directly testable:
> - **Ubiquitous:** `THE SYSTEM SHALL <behavior>.`
> - **Event-driven:** `WHEN <trigger> THE SYSTEM SHALL <behavior>.`
> - **State-driven:** `WHILE <state> THE SYSTEM SHALL <behavior>.`
> - **Unwanted:** `IF <condition> THEN THE SYSTEM SHALL <behavior>.`
> - **Optional:** `WHERE <feature is present> THE SYSTEM SHALL <behavior>.`

**Status:** Draft — 2026-06-30
**Owner:** Rajnish Khatri
**Related:**
- UI sibling: [`preact-english-coach-ui.spec.md`](preact-english-coach-ui.spec.md) (the *what* of the surface; this is the *what* behind it)
- Design doc (the entity model + port table): [`SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md`](../Architectures/SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md)
- ADRs (the *why*): [ADR-0005](../adr/0005-subject-coach-engine-home-and-substrate.md), [ADR-0006](../adr/0006-subject-coach-component-protocols.md)
- Engine direction (seed schema + research): [`QUIZ-APP-RESEARCH.md`](../../PreAct/QUIZ-APP-RESEARCH.md)
- Genericity stance: [`subject-coach-engine.brainstorm.md`](subject-coach-engine.brainstorm.md) — **English-concrete, seams only**
- Frontend law: [`STYLE_GUIDE_FRONTEND.md`](../style-guides/STYLE_GUIDE_FRONTEND.md), [`FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md`](../Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md) (F-R3, SDK confinement)
- Template: [`_spec_template.md`](_spec_template.md)

---

## 1. Goal

Deliver the **on-device adaptive learning engine** that drives the PreACT English
Coach: it selects the next item for the learner (weakest + most-due skill), grades
the answer deterministically, records the attempt, updates mastery via FSRS, and
serves only **reviewed** content — all working **offline** for the quiz/drill/
feedback/progress loop. The engine is built **English-concrete** but every
subject-variant decision (taxonomy, item shape, grading) sits behind a port so a
future Math/Science coach is a new adapter + content rows, **not** an engine rewrite.
A separate **backend generation pipeline** authors questions/tutorials offline and
gates them; the live coach is consumed as an existing SSE stream, not built here.

## 2. Context

The [UI spec](preact-english-coach-ui.spec.md) (SDD Stage 2, UI half) is settled and
explicitly defers all of this. ADR-0005 and ADR-0006 (both **Accepted**) decided
*where* the engine runs and *what its ports are*. This spec is the remaining Stage-2
artifact: the **engine requirements**, written so the schema in the design doc §2 can
be proven complete before it is frozen into concrete DDL.

Forces / decisions already pinned (do not re-litigate):
- **Engine home = the SPLIT** (ADR-0005). Learner-facing schema + FSRS + adaptivity +
  grading run **on-device in the Frontend-Ring** (local-first, §7 of the UI spec is an
  acceptance criterion). LLM question/tutorial **generation** + the live coach run
  **backend**.
- **Substrate = one Drizzle schema, Postgres-first, SQLite-compatible, no sync engine
  yet** (ADR-0005). The on-device store is the working store for the single learner.
- **Seven ports + a renderer registry** (ADR-0006). `Grader` is pure/deterministic/
  verifier-first; the `Grader`+registry pair is the OCP seam for new subjects.
- **English-concrete, seams only** (brainstorm). No generic `ItemType` table, no
  plugin loader, no external CMS, no CRDT — all documented-open, none built (design
  doc §4).
- **Single learner; auth deferred** (UI spec §1). The engine carries a `learner_id`
  column so auth can be added later without a schema change, but assumes one learner.

> **Constitution note.** This is **Frontend Ring** work (`frontend/lib/`), governed by
> [`STYLE_GUIDE_FRONTEND.md`](../style-guides/STYLE_GUIDE_FRONTEND.md). SDKs (Drizzle,
> ts-fsrs) are confined to `frontend/lib/adapters/`; the engine core (flow, scheduler
> policy, translators, registry) depends only on the ADR-0006 port interfaces. The
> generation pipeline and coach are reached over the BFF, never by the client calling
> an LLM directly (no secrets in the client bundle; no live LLM on the CI hot path).

---

## 3. Functional requirements (EARS)

Grouped: **A** adaptivity loop, **B** the `reviewed` content gate, **C** grading,
**D** sessions & attempts, **E** generation pipeline (backend, offline), **F** content
delivery, **G** offline / local-first posture, **H** the subject seam (OCP).
Failure-path (`IF…THEN`) requirements are written alongside their happy path. Each FR
maps to ≥1 test in §8.

### A. Adaptivity loop (Scheduler / FSRS)

- **FR-A1.** WHEN the learner starts an **adaptive** session THE SYSTEM SHALL select
  the next item from the highest-priority skill, where priority is the weakest +
  most-due skill determined from `skill_state` (lowest mastery among `due_at ≤ now`,
  ties broken by oldest `due_at`).
- **FR-A2.** THE SYSTEM SHALL treat `skill_state` as the **single source of truth** for
  adaptivity; the `Scheduler` (FSRS) port SHALL be the **only writer** of `skill_state`.
  No other component writes mastery, stability, difficulty, or `due_at`.
- **FR-A3.** WHEN an attempt is recorded THE SYSTEM SHALL call `Scheduler.review(attempt)`
  to update that skill's FSRS state (stability, difficulty, `due_at`, mastery) using the
  FSRS algorithm against a caller-supplied clock.
- **FR-A4.** IF no skill is currently due (`due_at > now` for all skills) THEN THE
  SYSTEM SHALL fall back to the lowest-mastery skill rather than returning no item, so
  an adaptive session is never empty when reviewed content exists.
- **FR-A5.** WHEN the learner starts a **drill** session scoped to one skill THE SYSTEM
  SHALL draw items from that skill only and SHALL NOT consult cross-skill priority.
- **FR-A6.** WHEN the learner starts a **review** session THE SYSTEM SHALL draw from the
  learner's prior **missed** attempts (`AttemptRepo.misses`), newest-incorrect first.
- **FR-A7.** IF a brand-new learner has no `skill_state` rows THEN THE SYSTEM SHALL seed
  a default state per skill (mastery 0, `due_at = now`) so the first adaptive session is
  well-defined, not a crash or an empty set.

### B. The `reviewed` content gate (the engine's hard invariant)

- **FR-B1.** THE SYSTEM SHALL serve to the learner only `question` and `tutorial` rows
  with `reviewed = true`. `QuestionRepo.nextReviewed` SHALL return reviewed items only.
- **FR-B2.** IF a `question` or `tutorial` row has `reviewed = false` THEN THE SYSTEM
  SHALL NOT surface it through any learner-facing read path (next item, drill pool,
  review pool, tutorial lookup), regardless of which port is called.
- **FR-B3.** IF the reviewed pool for a requested skill is empty THEN THE SYSTEM SHALL
  return an explicit empty result (a defined "no items yet" state), never a fabricated
  or `reviewed = false` item.
- **FR-B4.** THE SYSTEM SHALL record provenance (`generated_by`) on every generated
  `question`/`tutorial` row so a served item is auditable back to its source.

### C. Grading (Grader — pure, deterministic, verifier-first)

- **FR-C1.** THE SYSTEM SHALL grade an answer via the `Grader.grade(question, answer)`
  port, returning a `Verdict` (`{ correct, correctLetter?, canonicalAnswer?,
  rationaleKey? }`); the English grader SHALL decide correctness by exact match of the
  chosen letter against `question.answer_letter`.
- **FR-C2.** THE SYSTEM SHALL keep `Grader` **pure** — deterministic, no I/O, no
  network, no clock — so the same `(question, answer)` always yields the same `Verdict`
  and the grader is reusable on the generation side as the gate that sets `reviewed`.
- **FR-C3.** WHEN a `Verdict` is produced for an **incorrect** pick THE SYSTEM SHALL
  surface **two** rationales — the chosen distractor's specific rationale (`rationaleKey`
  selecting that letter) **and** the correct answer's rationale — so the UI's `FeedbackVM`
  renders both "Why [pick] tempted you" and "Why A is correct" (UI spec FR-E3) without
  engine-side branching in the component.
  *(Evidenced by prototype test `wrong pick (B) gives gentle, distractor-specific
  feedback`, which asserts both "Why B tempted you" and "Why A is correct" are shown.)*
- **FR-C3a.** WHEN a `Verdict` is produced for a **correct** pick THE SYSTEM SHALL set
  `correct = true` and `correctLetter` so the UI shows the celebrate state ("Exactly
  right." + "Why A is correct"), distinct from the soft incorrect state.
  *(Evidenced by prototype test `correct pick (A — NO CHANGE) celebrates`.)*
- **FR-C4.** IF a free-response or non-MC grading strategy is ever introduced THEN THE
  SYSTEM SHALL place any LLM judge **behind** a deterministic verifier (the repo's
  GoalJudge correctness-cascade discipline), never in front of the learner-facing
  verdict. (Documented-open per design doc §4; not built for English.)

### D. Sessions & attempts

- **FR-D1.** WHEN a session is opened THE SYSTEM SHALL create a `quiz_session` row via
  `SessionRepo.open(subject, learner, mode, focus?)` capturing mode
  (`adaptive`|`drill`|`review`), optional skill focus, and `started_at`.
- **FR-D2.** WHEN the learner submits an answer THE SYSTEM SHALL record an `attempt` row
  (chosen letter, correctness from the `Verdict`, `elapsed_ms`, `used_hint`) via
  `AttemptRepo.record`, linked to its session and question.
- **FR-D2a.** IF no choice has been selected THEN THE SYSTEM SHALL NOT produce a `Verdict`
  or record an attempt — a selected letter is a precondition of grading. *(Evidenced by
  prototype test `submit is gated until a choice is selected`; the UI disables Submit, but
  the engine SHALL also reject an empty pick so the gate is not UI-only.)*
- **FR-D3.** WHEN a session is closed THE SYSTEM SHALL set `ended_at` and the
  score tally (`score_correct`/`score_total`) via `SessionRepo.close(id, score)` so the
  UI's Summary stats (UI spec FR-G1) derive from stored values, not re-computation.
- **FR-D4.** THE SYSTEM SHALL expose the learner's missed attempts via
  `AttemptRepo.misses(subject, learner)` to back the "Review my misses (N)" surface
  (UI spec FR-C5) and the review-session pool (FR-A6).
- **FR-D5.** IF a hint was used on an attempt THEN THE SYSTEM SHALL persist `used_hint =
  true` on that attempt (hint use is auditable and may inform future scheduling), while
  the hint itself never changes the recorded correctness.
- **FR-D5a.** THE SYSTEM SHALL expose a hint that is **Socratic — not the answer**: the
  hint text SHALL NOT reveal `answer_letter` or the correct choice's label. The hint is a
  guiding question sourced from the question's rule/`why_*` fields, never from the answer.
  *(Evidenced by prototype test `hint toggles open and closed (and is not the answer)`,
  which labels the affordance "Coach hint — not the answer".)*
- **FR-D6.** WHEN a session is closed THE SYSTEM SHALL compute a **recommended next**
  (skill + mode) from the just-finished session's `skill_state` deltas, so the UI's
  "Start recommended drill" re-opens a session on that skill (UI spec FR-G2). The
  recommendation is derived from stored mastery/due state (FR-A1 priority), not a hardcoded
  skill. *(Evidenced by prototype tests `walks the full loop end to end` and
  `Drill this skill launches the Quiz`, where "recommended drill"/"Drill this skill" loop
  back into the Quiz.)*

### E. Generation pipeline (backend, offline)

- **FR-E1.** THE SYSTEM SHALL generate `question` and `tutorial` bodies **offline on the
  backend** (LLM + secrets server-side), never in the client and never on the CI hot
  path.
- **FR-E2.** WHEN a question is generated THE SYSTEM SHALL run the deterministic `Grader`
  (FR-C2) against its declared answer as a self-consistency gate **before** `reviewed`
  may be set to `true` — a generated item whose stated answer the grader cannot confirm
  SHALL remain `reviewed = false`.
- **FR-E3.** THE SYSTEM SHALL stamp every generated row with `generated_by` provenance
  (FR-B4) and default `reviewed = false`; promotion to `reviewed = true` is a separate,
  explicit step (human or gated-automatic), never the generator's default.
- **FR-E4.** IF generation produces a malformed item (missing choices, no answer letter,
  empty stem) THEN THE SYSTEM SHALL reject it (not persisted, or persisted `reviewed =
  false` with a defect marker) rather than emit a half-formed row.

### F. Content delivery (to the device)

- **FR-F1.** THE SYSTEM SHALL make `reviewed`-gated content reach the on-device store via
  a **seed bundle** for the initial English ship (the device works from local rows).
- **FR-F2.** WHERE a pull/sync path is later added THE SYSTEM SHALL deliver only
  `reviewed = true` rows to the device and SHALL route delivery through the same
  `ContentRepo`/`QuestionRepo` ports (no new bypass path). (Sync engine itself is
  deferred per ADR-0005; this FR constrains the seam, it does not require building sync.)
- **FR-F3.** THE SYSTEM SHALL serve all objective-plane UI strings via
  `ContentRepo.text(subject, key, locale)` so screen copy is data, not hardcoded — an
  in-repo typed bundle satisfies the port now; a CMS is a later adapter swap.

### G. Offline / local-first posture

- **FR-G1.** WHILE the device is offline THE SYSTEM SHALL fully serve the
  quiz/drill/feedback/progress loop (item selection, grading, attempt recording,
  mastery update, progress reads) from the local store — honoring UI spec §7.
- **FR-G2.** IF the live coach is unavailable (offline or stream failure) THEN THE
  SYSTEM SHALL surface a defined unavailable state to the UI (UI spec FR-F4) WITHOUT
  blocking or degrading the offline learning loop in G1.
- **FR-G3.** THE SYSTEM SHALL author the schema once in Drizzle with a
  **dialect-portable** shape (no Postgres-only column types on shared tables) so the same
  tables resolve to Postgres/Neon (canonical) and SQLite (on-device) — ADR-0005 substrate.

### H. The subject seam (OCP — closed for English, open for future)

- **FR-H1.** THE SYSTEM SHALL carry a `subject` discriminator (default `'act-english'`)
  on every engine table; a new subject SHALL be addable as new rows + a new `Grader`
  adapter + a new renderer-registry entry, with **zero edits** to the engine core
  (flow, scheduler policy, session/attempt logic).
- **FR-H2.** THE SYSTEM SHALL render each item via `registry[question.item_type]` (the
  client-side renderer registry), never via `switch(subject)`; English registers
  `underlined-span-mc`.
- **FR-H3.** IF any read path or renderer branches on `subject` directly (a
  `switch(subject)` bypassing the registry/port seam) THEN review SHALL reject it (the
  repo's "template-as-enforcement" check) — `subject` is a row discriminator + adapter
  set, not a control-flow fork.

---

## 4. Data model / contracts

This spec does **not** restate the entity model — it is owned by the design doc
[§2](../Architectures/SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md#2-entity-model-english-concrete-subject-column--the-only-seam-in-the-rows):
the eight tables (`skill`, `question`, `quiz_session`, `attempt`, `skill_state`,
`tutorial`, `content_string`, `progress_point`), each with the `subject` discriminator,
the `reviewed` gate, and `skill_state` as the adaptivity source of truth. The concrete
dual-dialect Drizzle DDL that resolves the design doc's abstract §2.1 types lands under
`frontend/lib/adapters/engine/db/` (Item 1 of this work).

The engine's **contract surface** is the seven ports from
[ADR-0006](../adr/0006-subject-coach-component-protocols.md) plus the `CoachAgentClient`
and the renderer registry. The one contract this spec pins is the grading return shape:

- **`Verdict`** `{ correct: boolean, correctLetter?: string, canonicalAnswer?: string,
  rationaleKey?: string }` — generic enough for a future symbolic/numeric grader
  (`canonicalAnswer`) without being abstract now (English uses `correctLetter` +
  `rationaleKey`).

The engine never hands raw rows to the UI; **translators** (Frontend-Ring convention)
map rows → the UI spec's view-models (`BucketCardVM`, `QuizItemVM`, `FeedbackVM`,
`ProgressVM`) per design doc §2.2. `CoachMessage` is **not** an engine row — it rides
the existing coach SSE stream.

No trust-kernel types are touched.

## 5. Invariants & security boundaries

- **Frontend-Ring boundary (F-R*).** Engine logic lives in `frontend/lib/` behind the
  ADR-0006 ports; SDKs (Drizzle, ts-fsrs) are confined to `frontend/lib/adapters/`
  (F-R2 / SDK confinement). One interface per `ports/` module (F-R3). The UI never
  imports a port's row types — only the translated view-models.
- **The three carried engine invariants:**
  1. **`reviewed` gate** (§3.B) — no `reviewed = false` content ever reaches a learner.
  2. **`skill_state` = adaptivity source of truth; FSRS is its only writer** (FR-A2).
  3. **IR-NEON-5 analogue** — engine tables live behind the same Drizzle `tablesFilter`
     whitelist that already excludes LangGraph checkpoint tables; the engine never
     manages `checkpoints*`.
- **Security.** No secrets in the client bundle. Generation runs server-side; the live
  coach is consumed over the BFF, never by the client calling an LLM. No live LLM on the
  CI hot path (generation + any future LLM grading are off the deterministic gate).
- **Dual-dialect constraint** (ADR-0005) — shared tables avoid Postgres-only column
  types so the schema resolves to both Postgres and SQLite.
- **Python four-layer invariants (#1–#8)** are **not** touched — this is Frontend-Ring
  + a backend generation job, not a change to `trust/`/`services/`/`components/`/
  `orchestration/`. The architecture tests in `tests/architecture/` do not gate this
  spec; the constitution here is `STYLE_GUIDE_FRONTEND.md` + the port conformance suite.
- **ADR triggers.** None new — this implements Accepted ADR-0005/0006. The
  **coach-agent fork from `reactLoop`** remains a separate `⚠️ Ask first` / new-graph-node
  ADR (flagged, not decided here); this spec only consumes the coach as an SSE stream.

## 6. Edge cases

- **Brand-new learner, no `skill_state`** — seed default state per skill (FR-A7); first
  adaptive session is well-defined, not empty/crash.
- **All skills not-yet-due** — fall back to lowest mastery (FR-A4); never an empty
  adaptive session when reviewed content exists.
- **Empty reviewed pool for a skill** — explicit "no items yet" state (FR-B3), not a
  fabricated or unreviewed item.
- **Generated item the grader can't confirm** — stays `reviewed = false` (FR-E2);
  never auto-promoted.
- **Hint used then correct/incorrect** — `used_hint = true` persisted; correctness
  unaffected by the hint (FR-D5).
- **Coach offline mid-loop** — learning loop continues; coach shows defined unavailable
  state (FR-G2); no infinite spinner (UI spec FR-F4).
- **Undecidable mastery (no attempts yet)** — read paths return `None`/empty, not a
  fabricated `0.0` that reads as "mastered the wrong way" (AP-6 discipline).
- **Same skill due across `adaptive` and `drill`** — drill ignores cross-skill priority
  (FR-A5); the two modes don't contend for "next item" logic.
- **Subject discriminator on a query that forgot it** — every read is keyed by
  `subject`; a query without it is a bug the conformance test for repos must catch.

## 7. Non-functional requirements

- **Determinism for tests:** the engine loop is **L1 deterministic** — FSRS runs against
  a fixed/injected clock, the grader is pure exact-match, the `reviewed` gate is a
  predicate. All of §3.A–D and §3.G are reproducible without sampling.
- **Generation is off the hot path:** §3.E runs **on-demand / cadence**, server-side,
  never in `make check` and never live-LLM in CI (L2/L4 at most, behind a `live` tag).
- **Offline latency:** local item selection + grading + attempt write complete with no
  network round-trip (the loop is on-device, FR-G1).
- **Reversibility:** attempts and sessions are append-only history; no destructive
  learner action. Soft-delete/archival follows the existing `thread_store` pattern.
- **Cost:** the only paid path is backend generation (batched, offline) + the live coach
  stream (already-budgeted SSE); the learning loop itself has zero per-use LLM cost.

## 8. Test plan

Engine logic is deterministic and tested at **L1** (Vitest, pure functions + a fake
clock + an in-memory/SQLite repo). Generation is **L2/L4 on-demand** (no live LLM in
`make check`). Failure-path tests precede happy-path. Port conformance (mock + real per
ADR-0006) is its own bundle.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-A1/A2 | `scheduler.spec::adaptive_picks_weakest_due_and_only_fsrs_writes_skill_state` | L1 | yes |
| FR-A4/A7 | `scheduler.spec::no_due_falls_back_to_lowest_mastery_and_new_learner_is_seeded` | L1 | yes |
| FR-A3 | `scheduler.spec::review_updates_fsrs_state_against_fixed_clock` | L1 | yes |
| FR-A5/A6 | `scheduler.spec::drill_scopes_one_skill_review_draws_misses` | L1 | yes |
| FR-B1/B2 | `reviewed_gate.spec::unreviewed_never_served_on_any_read_path` (failure-first) | L1 | yes |
| FR-B3 | `reviewed_gate.spec::empty_reviewed_pool_returns_explicit_empty_not_fabricated` | L1 | yes |
| FR-C1/C2 | `grader.spec::exact_letter_match_is_pure_and_deterministic` | L1 | yes |
| FR-C3/C3a | `grader.spec::wrong_pick_yields_both_distractor_and_correct_rationale; correct_pick_sets_celebrate` | L1 | yes |
| FR-D1/D2/D3 | `session.spec::open_record_close_persists_score_tally` | L1 | yes |
| FR-D2a | `grader.spec::no_selected_letter_produces_no_verdict_and_no_attempt` (failure-first) | L1 | yes |
| FR-D4/D5 | `attempt.spec::misses_query_and_used_hint_persisted_without_changing_correctness` | L1 | yes |
| FR-D5a | `hint.spec::hint_is_socratic_and_never_reveals_answer_letter` | L1 | yes |
| FR-D6 | `session.spec::close_computes_recommended_next_from_skill_state_not_hardcoded` | L1 | yes |
| FR-E2 | `generation.spec::grader_self_consistency_gates_reviewed` (mock generator) | L2 | yes (gate logic; generator mocked) |
| FR-E1/E3/E4 | `generation.spec::offline_provenance_and_malformed_rejected` | L2/L4 | on-demand (live-tag) |
| FR-F2/F3 | `content_delivery.spec::only_reviewed_delivered_strings_via_contentrepo` | L1 | yes |
| FR-G1/G2 | `offline.spec::loop_runs_without_network_coach_unavailable_does_not_block` | L1 | yes |
| FR-G3 | `schema.spec::same_drizzle_schema_compiles_pg_and_sqlite` (tsc + dialect parse) | L1 | yes |
| FR-H1/H2/H3 | `oue_seam.spec::new_subject_is_rows_plus_adapter_no_engine_edit_no_switch_subject` | L1 | yes |
| (ports) | `test_port_conformance.ts::{Scheduler,Grader,QuestionRepo,…}` (mock + real) | L1 | yes |

> The Python `tests/architecture/` suite does not gate this Frontend-Ring spec; the
> equivalent constitution is `STYLE_GUIDE_FRONTEND.md` + the port conformance bundle +
> the `tsc --noEmit` dialect compile check.

### 8.1 Traceability to the existing prototype tests

The design agent's Playwright suite at [`preact/ui-design/tests/e2e/`](../../preact/ui-design/tests/e2e/)
already pins the **UI contract** of several engine behaviors — the prototype faked them
in scripted JS, but the real engine must satisfy the same observable contract. The table
below maps each engine FR to the existing prototype test that exercises its UI side, so
the engine unit tests in §8 inherit a known-good behavioral oracle rather than starting
from a blank assertion. (These are **UI** tests and stay owned by the
[UI spec](preact-english-coach-ui.spec.md); this mapping makes the engine ⇄ surface
contract explicit and prevents the two layers from drifting.)

| Engine FR | Prototype test (`english-coach.spec.js`) | What the test proves the engine must produce |
|---|---|---|
| FR-D2a (submit precondition) | `submit is gated until a choice is selected` | No verdict/attempt without a selected letter |
| FR-D5a (Socratic hint) | `hint toggles open and closed (and is not the answer)` | Hint copy is "not the answer"; never leaks `answer_letter` |
| FR-C3a (celebrate) | `correct pick (A — NO CHANGE) celebrates` | `correct=true` + `correctLetter` → "Exactly right." + "Why A is correct" |
| FR-C3 (two rationales) | `wrong pick (B) gives gentle, distractor-specific feedback` | Both the distractor rationale ("Why B tempted you") **and** "Why A is correct" |
| FR-D1/D2/D3 + FR-D6 (loop + recommended next) | `walks the full loop end to end` | Open→grade→record→close→**recommended drill re-opens Quiz** |
| FR-D3 (close → Summary) | `Feedback -> Next question goes to Summary` | Closing a session yields the scored Summary, not a recompute |
| FR-A5 + FR-D6 (drill scope) | `Drill this skill launches the Quiz` | "Drill this skill" opens a skill-scoped session |

> **Not mapped (deliberately UI-only):** theme toggle, sidebar/flow-pill navigation,
> banner styling, timer dismiss, range-tab switching — these assert rendering, not an
> engine contract, and remain in the [UI spec](preact-english-coach-ui.spec.md) §8.
>
> **Coverage gap the prototype tests do NOT reach** (engine-only, no UI oracle — write
> these from the FR alone): the `reviewed` gate (§3.B), FSRS-only `skill_state` writes
> (FR-A2), new-learner seeding (FR-A7), generation self-consistency (FR-E2), and
> dual-dialect schema parity (FR-G3). The prototype had no persistence, so these have no
> existing test to inherit from — they are pure red/green TDD targets.

### 8.2 Deferred / on-demand test follow-ups (tracked, not yet in `make check`)

These are named tests the design references but that are **not implemented yet**. They are
tracked here as the canonical follow-up list so citations point at a real item rather than a
gap. Both gate the **next** increment (the on-device SQLite adapter), not the shipped
Postgres + `InMemoryEngineDb` code — this is the substance of
[ADR-0010](../adr/0010-subject-coach-engine-ports-realization-and-ts-fsrs.md)'s two pending
acceptance conditions.

| # | Test | Purpose | Gate |
|---|------|---------|------|
| 8.2-a | `schema.spec::same_drizzle_schema_compiles_pg_and_sqlite` (FR-G3) | `tsc --noEmit` + column-for-column parity over `schema.pg.ts` / `schema.sqlite.ts` so the dual-dialect substrate is *verified*, not asserted. | add to `make check` **before** writing SQLite-dialect code against these schemas (ADR-0010 condition #1) |
| 8.2-b | `pg_engine_db.integration.spec` (`DATABASE_URL`-gated) | exercise the live `pgEngineDb` seam against a real Postgres (the one path `make check` cannot cover — no DB on the deterministic gate); asserts it reproduces `InMemoryEngineDb` behavior. | on-demand (`live`-tagged), never on the CI hot path (ADR-0010 condition #2 — this item replaces the ADR's dangling "§8.2" citation) |

## 9. Definition of Done

- [ ] All FRs implemented; each has a passing test that was *seen to fail first*
      (red/green TDD — the `reviewed`-gate and seam tests especially).
- [ ] Engine loop (§3.A–D, §3.G) is L1-deterministic and green in `make check`
      (Frontend lint/typecheck + Vitest); generation tests run on-demand, not in CI.
- [ ] Port conformance bundle (mock + real per port) green; `tsc --noEmit` passes on
      both the Postgres and SQLite schema (FR-G3).
- [ ] Frontend-Ring boundary held: SDKs only in `adapters/`, one interface per `ports/`
      module, UI consumes view-models not rows, no `switch(subject)` (FR-H3).
- [ ] The three engine invariants verified, not asserted: `reviewed` gate, FSRS-only
      `skill_state` writes, IR-NEON-5 `tablesFilter` excludes checkpoints.
- [ ] No new ADR needed (implements Accepted ADR-0005/0006); a `decisions.md` entry
      filed for any small non-obvious choice made during build.
- [ ] The coach-agent-fork ADR is filed **before** any `reactLoop` change (out of scope
      here; flagged so the implementing PR raises it).
- [ ] Actual command/test output pasted (not summarized) for the verification claims.
