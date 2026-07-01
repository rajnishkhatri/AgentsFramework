---
type: architecture
title: 'Subject-Coach — Detailed Component & Per-Screen Design'
description: 'The HOW: the low-level component design behind the accepted PreACT English Coach specs — every component, a per-screen design for all seven screens, the end-to-end coach (client stream + backend persona + the three judges), and the adjudication of the open ADRs. Sibling to SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md (the WHAT).'
tags: [architecture, frontend-ring, components, coach, judges]
---

# Subject-Coach — Detailed Component & Per-Screen Design

**Status:** Draft — 2026-07-01 · **Owner:** Rajnish Khatri
**Audience:** anyone building a PreACT English Coach screen, the live coach, the offline
generator, or the three judges — and anyone reconsidering an open ADR (§7).

**Companion records (the WHY — read to reconsider a decision):**
- [ADR-0005](../adr/0005-subject-coach-engine-home-and-substrate.md) — engine home + substrate. **Accepted.**
- [ADR-0006](../adr/0006-subject-coach-component-protocols.md) — the seven engine ports + `Verdict` + renderer registry. **Accepted.**
- [ADR-0007](../adr/0007-subject-coach-agent-tool-capability-gating.md) — capability-gated tools + English-only guardrail. **Accepted** (gate mechanism landed).
- [ADR-0008](../adr/0008-subject-coach-judges-grader-and-pedagogy.md) — the three-judge split. **Accepted with conditions** (adjudicated in §7).
- [ADR-0009](../adr/0009-subject-coach-reflexion-not-on-live-path.md) — Reflexion OFF for the coach. **Accepted** (adjudicated in §7).
- [ADR-0010](../adr/0010-subject-coach-engine-ports-realization-and-ts-fsrs.md) — ports realization + ts-fsrs + `EngineDb`. **Accepted with conditions.**
- [ADR-0011](../adr/0011-subject-coach-engine-learner-read-port.md) — the `LearnerReadRepo` read port. **Accepted** (adjudicated in §7; amended 2026-07-01).

**The WHAT this refines (does not restate):**
- [SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md](SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md) — the entity model + the port table. This doc is the HOW-each-is-realized.
- Specs: [UI](../plan/preact-english-coach-ui.spec.md), [engine](../plan/preact-english-coach-engine.spec.md), [agent](../plan/subject-coach-agent.spec.md) (the *what* of each plane).
- [subject-coach-agent.brainstorm.md](../plan/subject-coach-agent.brainstorm.md) — the pedagogy + reuse-inventory grounding for §5 (Feynman/Oakley/Holt; the live-code reuse map).

**Builds on (does not restate):**
- [STYLE_GUIDE_FRONTEND.md](../style-guides/STYLE_GUIDE_FRONTEND.md) — the F/W/P/A/T/X/C/B/U rule families this design obeys.
- [FRONTEND_ARCHITECTURE.md](FRONTEND_ARCHITECTURE.md) — the F-R1..F-R9 invariants + the chat data-flow this replicates.

---

## 1. Governing thought — the four-layer replication law

The chat slice already proves the shape every English-Coach screen copies: a **composition
root** injects ports → a **hook** holds all the logic → a **pure translator** produces a
view-model → a **presentational component** renders props. This doc's job is to pin, per
screen, which files fill each slot and which ports they touch. The one rule:

```
composition_engine_browser.ts → useEngine()          [C2/C3: only the root names adapters]
        │  injects EnginePortBag (ports only; no SDK, no EngineDb)
        ▼
use_<screen>.ts     (orchestration hook)              [F-R1: ALL domain logic lives here]
        │  calls ports, folds state; the core is React-free async fns
        │  (openQuizItem/runQuizSubmit) so node tests exercise it with no React, no mocks
        ▼
lib/translators/<vm>.ts   (pure view-model)           [T1: wire → VM; no I/O, React, or SDK]
        │  imports wire/ (+ trust-view/) only — the layering test enforces it
        ▼
components/<screen>/<Screen>View.tsx  (leaf)           [F-R1 leaf: renders props; data-* styling]
        ▼
DOM
```

**In-repo exemplars (the template to mirror exactly):**
- Engine: [`use_quiz.ts`](../../frontend/components/quiz/use_quiz.ts) (React-free `openQuizItem`/`runQuizSubmit`) → [`quiz_item_vm.ts`](../../frontend/lib/translators/quiz_item_vm.ts) → [`QuizView.tsx`](../../frontend/components/quiz/QuizView.tsx).
- Chat twin: [`use_agent_run.ts`](../../frontend/components/chat/use_agent_run.ts) → [`run_view_reducer.ts`](../../frontend/lib/translators/run_view_reducer.ts) → [`chat-shell.tsx`](../../frontend/app/chat-shell.tsx).

Everything below is that shape, filled in per screen.

---

## 2. Component catalog

Every component in the coach, one row. Status: **BUILT** (green + tested), **TO-BUILD**,
**DEFERRED** (gated on a later ADR amendment). Layer letters are the STYLE_GUIDE_FRONTEND
families (P=port, A=adapter, C=composition, T=translator, U=UI/hook, B=route).

### 2.1 Engine — objective plane (frontend/)

| Component | Layer | File | Status | Ports/Consumes |
|---|---|---|---|---|
| `SkillTaxonomy` | P | `lib/ports/engine/skill_taxonomy.ts` | BUILT | — |
| `QuestionRepo` | P | `lib/ports/engine/question_repo.ts` | BUILT | reviewed gate |
| `AttemptRepo` | P | `lib/ports/engine/attempt_repo.ts` | BUILT | — |
| `SessionRepo` | P | `lib/ports/engine/session_repo.ts` | BUILT | — |
| `Scheduler` (FSRS) | P | `lib/ports/engine/scheduler.ts` | BUILT | **sole `skill_state` writer** |
| `Grader` | P | `lib/ports/engine/grader.ts` | BUILT | pure, sync (P5 exception) |
| `ContentRepo` | P | `lib/ports/engine/content_repo.ts` | BUILT | objective-plane strings |
| **`LearnerReadRepo`** | P | `lib/ports/engine/learner_read_repo.ts` | **TO-BUILD** (ADR-0011) | read-only skill_state |
| Drizzle repos ×5 | A | `lib/adapters/engine/repos/drizzle_*.ts` | BUILT | depend on `EngineDb` |
| `DrizzleLearnerReadRepo` | A | `lib/adapters/engine/repos/drizzle_learner_read_repo.ts` | **TO-BUILD** | depends on **`ReadableEngineDb`** |
| `FsrsScheduler` | A | `lib/adapters/engine/scheduler/fsrs_scheduler.ts` | BUILT | ts-fsrs; round-trips opaque `fsrs_card` |
| `ExactLetterGrader` | A | `lib/adapters/engine/grader/exact_letter_grader.ts` | BUILT | **= ADR-0008 frontend MC-Grader stage** |
| `EngineDb` / `ReadableEngineDb` | A(seam) | `lib/adapters/engine/db/engine_db.ts` | BUILT / **`ReadableEngineDb` TO-BUILD** | narrow row seam |
| `InMemoryEngineDb` | A | `lib/adapters/engine/db/in_memory_engine_db.ts` | BUILT | L1/dev/browser fake |
| `pgEngineDb` | A | `lib/adapters/engine/db/drizzle_engine_db.ts` | BUILT | the one live drizzle+pg seam |
| dual-dialect schema | A | `lib/adapters/engine/db/schema.{pg,sqlite}.ts` | BUILT (parity test **missing** — ADR-0010) | 8 tables each |
| composition (server) | C | `lib/composition_engine.ts` | BUILT | `DATABASE_URL` selector |
| composition (browser) | C | `lib/composition_engine_browser.ts` | BUILT | InMemory only (keeps `pg` out of client) |
| engine provider | C/U | `app/engine-provider.tsx` | BUILT | `EngineProvider` / `useEngine()` |
| wire kernel | W | `lib/wire/engine_entities.ts` | BUILT | pure Zod entities + `Verdict` |

### 2.2 View-model translators (all BUILT)

`bucket_card_vm`, `quiz_item_vm`, `feedback_vm`, `today_focus_vm`, `session_summary_vm`,
`coach_message_vm`, `todo_list_projection` — all under `lib/translators/`, all with
co-located `.test.ts` (T4 table-driven). New VMs for the deferred plane: `skill_detail_vm`,
`progress_vm` (TO-BUILD with Screens 6/7).

### 2.3 Screens — hooks + components

| Screen | Hook | Component | Status |
|---|---|---|---|
| Dashboard | `use_dashboard` | `DashboardView` (+ `BucketCard`, `TodayFocusBanner`) | TO-BUILD |
| Quiz | `use_quiz` (BUILT) | `QuizView` (BUILT) | BUILT |
| Feedback | `use_feedback` (BUILT) | `FeedbackView` (BUILT) | BUILT |
| Coach | `use_coach` | `CoachView` (+ `CoachPanel`, `coach_thread_store`) | TO-BUILD |
| Summary | `use_summary` | `SummaryView` | TO-BUILD |
| Skill-detail | `use_skill_detail` | `SkillDetailView` | DEFERRED (D1) |
| Progress | `use_progress` | `ProgressView` | DEFERRED (D1) |
| shell/nav | `use_surface` | `AppNav`, `FocusModeChrome` | TO-BUILD |
| routes | — | `app/(coach)/{layout,page,quiz,summary,coach}` | TO-BUILD |
| coach BFF | — | `app/api/coach/stream/route.ts` | TO-BUILD |

### 2.4 Backend coach — subjective plane

| Component | File | Status |
|---|---|---|
| capability-gating filter | `components/capability_gating.py` (`derive_bound_tools`/`filter_registry_schemas`) | **BUILT** (wired in `react_loop.py::build_graph`, flags OFF) |
| declared=bound arch test | `tests/architecture/test_capability_gating.py` | **BUILT** |
| `subject-coach-english` AgentFacts instance | `services/governance/agent_facts_registry.py` (new instance) | TO-BUILD |
| coach persona prompt | `prompts/subject_coach_system_prompt.j2` | TO-BUILD |
| Grader Judge prompt | `prompts/subject_coach_grader_judge.j2` | TO-BUILD |
| Pedagogy judge prompt | `prompts/subject_coach_pedagogy_judge.j2` | TO-BUILD |
| `GraderVerdict` / `PedagogyVerdict` | `components/` (new types) | TO-BUILD |
| Grader Judge + Pedagogy GoalJudge | `components/` | TO-BUILD |
| general GoalJudge | `components/goal_judge.py` | **reused unchanged** |

**Reuse inventory (verified live code, agent brainstorm §2):** `build_graph`
(`orchestration/react_loop.py`), `agent_facts_registry.py` (HMAC-signed), `guardrails.py::InputGuardrail`
(3-stage cascade), `guardrail_validator.py` (the judge-input **redactor**),
`registry.py::ToolRegistry` (the gating surface), `llm_config.py` (tiers), `prompt_service.py`,
`goal_judge.py` (the H1/H2 injectable shape + the ADR-0003 cascade the new judges fork).

---

## 3. Engine substrate (brief — the sibling doc owns the schema)

- **`EngineDb`** is the narrow row-level seam — the `thread_store`/`DrizzleLike` analogue.
  All six DB-backed repos depend only on it; two impls satisfy it (`InMemoryEngineDb` for
  L1/dev/browser, `pgEngineDb` for the one live drizzle+pg seam). `composition_engine.ts`
  selects by `DATABASE_URL`.
- **FSRS card round-trip:** the scheduler persists the *full* FSRS card via an opaque
  `skill_state.fsrs_card` JSON column typed `unknown` on the wire, so no FSRS type leaks the
  adapter (F-R8). The named `mastery`/`fsrs_stability`/`fsrs_difficulty`/`due_at`/`last_seen`
  columns stay the vendor-neutral projection. Guarded by a multi-review progression test.
- **Dual-dialect** `schema.pg.ts` + `schema.sqlite.ts` (8 tables each).

**Known-unverified edges (cite, don't assume — ADR-0010 pending conditions):**
1. The **FR-G3 dual-dialect parity test** (`schema.spec::same_drizzle_schema_compiles_pg_and_sqlite`)
   is referenced in README/schema comments and the engine spec §8 test plan but **does not
   exist**. Until it lands, treat dialect parity as *unverified*, not merely "not yet exercised."
2. The **`pgEngineDb` integration test** (`DATABASE_URL`-gated) is an unimplemented follow-up.
3. The **on-device SQLite `EngineDb`** impl is not wired (the seam admits it; the driver
   lands under Capacitor). These three gate the *next* increment, not the shipped code.

---

## 4. Per-screen design

Each screen: **(a)** regions/states, **(b)** hook contract, **(c)** VM consumed, **(d)** ports
touched, **(e)** tests, **(f)** status/gaps.

### 4.1 Dashboard (Screen 1) — TO-BUILD

- **(a) Regions/states (FR-C1..C5).** Greeting + day-part + score-goal line ("26 → 28");
  Today's-focus banner (weakest+due skill, canonical = Punctuation; CTA "Start adaptive
  session" → Quiz); 6-card skill-mastery grid (name, mastery %, share-of-test %,
  bucket-colored bar, "Due" badge); secondary actions ("Drill a skill", "Review my misses
  (N)"); right-rail (desktop) / row (iPad) — score-goal progress, streak, 7-dot week strip,
  Coach note. **Empty states:** "Review my misses (0)"; cold-start no-due → banner falls back
  to lowest-mastery (engine FR-A4).
- **(b) Hook `use_dashboard`.** React-free `buildDashboard(ports, {subject, learnerId, nowISO})`:
  `skillTaxonomy.list(subject)` → 6 skills; **`learnerReadRepo.listSkillState(subject, learner)`**
  → mastery per skill (⚠️ ADR-0011); `scheduler.next(subject, learner)` → `NextItem` for the
  banner. Folds `{ focus, cards, missesCount }`. `due` computed off the injected `nowISO`
  (deterministic).
- **(c) VMs.** `TodayFocusVM` (`today_focus_vm.ts`, null-safe cold-start) + `BucketCardVM[]`
  (`bucket_card_vm.ts`, maps `SkillState | null → 0%`).
- **(d) Ports.** `SkillTaxonomy`, `Scheduler` (read of `next`), **`LearnerReadRepo`** (ADR-0011).
- **(e) Tests.** `dashboard.spec::mastery_grid_six_buckets_with_share_and_due`;
  `::today_focus_is_weakest_due_skill`; `::review_misses_zero_empty_state`.
  `bucket_card_vm.test.ts` + `today_focus_vm.test.ts` BUILT. **Placeholder-path test:** with
  `LearnerReadRepo` absent, the grid renders 0%/"—" (no boundary crossing).
- **(f) Gap.** Blocked on ADR-0011 for real mastery; ships the 0%/"—" placeholder until the
  port lands.

### 4.2 Quiz (Screen 2) — BUILT (the reference implementation)

- **(a) Regions/states (FR-D1..D8).** Slim top bar (End-session, "Q N/M" + progress bar,
  bucket badge, dismissible timer ⊘↔⏱); item column ≤760px (context sentence with the
  **underlined span** FR-A6, stem, 4 choice rows, A = "NO CHANGE"); selection (accent border +
  filled letter-tile, clears prior); Submit gated (FR-D4, 0.6 opacity); Socratic hint toggle
  (dashed accent, **never reveals the answer** FR-D5); ghost "Reveal answer" (FR-D6).
- **(b) Hook `use_quiz` (BUILT — canonical contract).** `openQuizItem(ports, {subject, learnerId})`
  = `scheduler.next` → `questionRepo.get` (**throws on an unresolved id — a seam defect
  surfaced, never a blank item**). `runQuizSubmit(ports, args)` grading order: **grade (pure
  Grader) → if (verdict && letter) record attempt → scheduler.review** (the sole `skill_state`
  writer). No selection ⇒ all-null result, zero side effects (FR-D2a). The whole sequence is
  React-free async fns, node-tested against a seeded `InMemoryEngineDb`.
- **(b′) ADR-0011 §4 addition.** The session lifecycle owner (`use_quiz`/`use_session`)
  captures **`skillStateAtStart: ReadonlyMap<skillId, SkillState>`** via
  `learnerReadRepo.listSkillState` **once at session open** (after `sessionRepo.open`
  resolves, before the first `review()` mutates state) — the "before" half of the FR-G1 delta.
- **(c) VM.** `QuizItemVM` (`quiz_item_vm.ts` — omits the answer letter so pre-answer DOM
  cannot leak it; `canSubmit` helper drives the disabled state).
- **(d) Ports.** `Scheduler`, `QuestionRepo`, `Grader`, `AttemptRepo` (+ `LearnerReadRepo` for
  the start snapshot).
- **(e) Tests (BUILT).** `use_quiz.test.ts`, `QuizView.test.tsx`; UI-spec
  `quiz.spec::submit_disabled_until_choice`, `::hint_toggles_socratic_and_never_reveals_answer`,
  `::underlined_span_accent_then_success_in_recap`.

### 4.3 Feedback (Screen 3) — BUILT

- **(a) Regions/states (FR-E1..E5).** Result banner (success "Exactly right." FR-E2 / soft
  "Not quite — and that's useful." FR-E3); sentence recap with the correct span in **success
  color** (FR-A7); reviewed-choices list styled per state (correct / chosen-wrong / other,
  FR-E4) — **color + icon + label, never color alone** (FR-A8); "Why A is correct"; "Why
  [pick] tempted you"; rule-under-test; action row "Ask the coach" → Coach + "Next question →"
  → Summary.
- **(b) Hook `use_feedback` (BUILT).** Feedback is a **Quiz sub-state, not a route**.
  `buildFeedback(question, verdict, answer)` → `{ present, vm, askCoachContext: {questionId,
  skillId} }`; `verdict == null` ⇒ `{ present: false }`. `askCoachContext` is the seam that
  carries the item into Coach (FR-E5).
- **(c) VM.** `FeedbackVM` (`feedback_vm.ts` — per-choice states + why_correct / why_tempted /
  rule).
- **(d) Ports.** None at feedback time — the verdict was computed by `Grader` at submit; this
  is a pure projection.
- **(e) Tests (BUILT).** `use_feedback.test.ts`, `FeedbackView.test.tsx`;
  `feedback.spec::correct_pick_A_celebrates`, `::wrong_pick_B_gives_distractor_specific_soft_feedback`.

### 4.4 Coach (Screen 4) — TO-BUILD (full detail in §5)

- **(a) Regions/states (FR-F1..F6).** Coach header (avatar + "Your Coach" + Wrap-up); context
  rail (current item + history-awareness line "3 of last 5 comma items missed" + 3 coach
  modes); conversation (coach bubbles surface/left ~74–80% max-width, learner bubbles
  accent/right, rounded tail FR-F5); composer (quick-reply chips + input + send). **Streaming:**
  typing indicator on send (FR-F2), progressive token render (FR-F3), recoverable error + retry
  (FR-F4, **never an infinite spinner**).
- **(b) Hook `use_coach`.** **Wraps `use_agent_run`** (reuses the chat lifecycle F-R1 hook)
  bound to the chat `AgentRuntimeClient` over `app/api/coach/stream/route.ts`; folds each
  `AssistantRunView` through **`coach_message_vm.toCoachMessage`** → `{ markdown, pending,
  error, canRetry, traceId }`. Shared thread id = the iPad-split↔Coach-screen thread (FR-J3).
  Seeds the rail from `askCoachContext` (FR-E5) + recent `attempt` history (FR-F6).
- **(c) VM.** `CoachMessage` (`coach_message_vm.ts`, BUILT — flattens text segments, drops tool
  segments; "error" terminal → recoverable with retry, FR-F4).
- **(d) Ports.** `AgentRuntimeClient` (**the chat port, not an engine port** — see the
  divergence note, §7); `AttemptRepo` (read recent misses for the rail).
- **(e) Tests.** `coach.spec::send_streams_tokens_with_typing_then_bubble` (mocked SSE, L2),
  `::stream_failure_shows_retry_not_infinite_spinner` (L1); `coach_message_vm.test.ts` (BUILT).

### 4.5 Summary (Screen 5) — TO-BUILD

- **(a) Regions/states (FR-G1..G3).** Misconception-framed title; 3 stat tiles — score "7/10"
  from **stored** `score_correct/score_total` (no re-tally), mastery delta "+8%", time "12 min";
  coach misconception write-up (accent card, generated content passed through); recommended-next
  card (skill + mode; CTA re-opens Quiz FR-G2); action row ("Start recommended drill" → Quiz,
  "See full explanation" → Skill detail, "Done for today" → Dashboard). Frames around the
  *misconception found*, not the raw score (FR-G3).
- **(b) Hook `use_summary`.** `sessionRepo.close` → scored `QuizSession`; compute
  `RecommendedNext` from `skill_state` (engine FR-D6, not hardcoded); **delta** =
  `currentMasteryPct − startMasteryPct` from the **`skillStateAtStart` snapshot** (ADR-0011 §4)
  + a fresh `learnerReadRepo.listSkillState`; resolve `nextSkill` via `skillTaxonomy`. The
  delta is passed *in* so the VM stays pure; absent-start (brand-new learner seeded mid-session
  by FR-A7) → "—".
- **(c) VM.** `SessionSummaryVM` (`session_summary_vm.ts`, BUILT — never re-tallies; `signedPct`
  handles the -0% edge; time derived from ISO stamps).
- **(d) Ports.** `SessionRepo`, `SkillTaxonomy`, **`LearnerReadRepo`** (ADR-0011).
- **(e) Tests.** `summary.spec::score_tile_reads_stored_not_retallied`, `::mastery_delta_signed`,
  `::recommended_drill_reopens_quiz`; `session_summary_vm.test.ts` (BUILT).
- **(f) Gap.** Delta tile shows "—" until ADR-0011 lands. **Session-resume limitation:** on a
  page reload / cold-start the in-memory `skillStateAtStart` is lost → the delta renders "—"
  for that session (acceptable for Phase-1 single-learner short sessions; ADR-0011 §4 decision
  trigger = real session-resume UX).

### 4.6 Skill-detail (Screen 6) — DEFERRED (UI-spec D1)

- **(a) Regions/states (FR-H1/H2).** Bucket-tinted header (dot + name + share + "Drill this
  skill"); two-column body — left "The rule, in one line" + ✓ examples + auto-built "Why you
  missed these"; right accuracy bar chart (last 6 sessions) + "Due for review" list. "Drill
  this skill" → Quiz scoped to that skill.
- **(b) Hook `use_skill_detail`.** Needs the **tutorial read** (`getTutorial`) — **NOT** on
  `LearnerReadRepo` per amended ADR-0011; it waits for a **second ADR-0006 amendment** gated on
  Screens 6/7 — plus `attemptRepo` misses aggregation.
- **(c/d) VM/ports.** New `skill_detail_vm` (TO-BUILD); the second-amendment tutorial read +
  `AttemptRepo` + `SkillTaxonomy`.
- **(e/f) Tests/status.** `skill.spec::rule_and_examples`, `::why_you_missed_empty_state`.
  Deferred; Dashboard/Summary "See full explanation" links ship **disabled "coming soon"**
  (FR-B5 — never dead controls).

### 4.7 Progress (Screen 7) — DEFERRED (UI-spec D1)

- **(a) Regions/states (FR-I1/I2).** Header ("Your progress", items-reviewed + streak); range
  tabs (30 days / All time); projected-score trend line + goal guide line; mastery-by-bucket
  bars (% + Due flag). Range tab switches active tab + caption + trend data ("Goal 28 · on
  track" ↔ "Goal 28 · since September").
- **(b) Hook `use_progress`.** Needs `listProgressPoints` (second amendment) + `listSkillState`.
- **(c/d) VM/ports.** New `progress_vm` (TO-BUILD); second-amendment progress read +
  `LearnerReadRepo`.
- **(e/f) Tests/status.** `progress.spec::range_tab_switches_caption_and_trend`. Deferred with
  Screen 6. Also gated by FR-G3 parity (ADR-0010) since trend reads span both dialects.

### 4.8 Cross-screen navigation (FR-B1..B5)

| Surface | Primary nav | Focus-mode behavior |
|---|---|---|
| Desktop | persistent sidebar + numbered flow-step pills (1 Dashboard · 2 Quiz · 3 Feedback · 4 Coach · 5 Summary), pills jump-nav | one screen at a time |
| iPad (landscape) | persistent sidebar (Home / Practice / Coach / Progress) | Quiz = split with the live coach panel always visible (FR-J3) |
| iPhone (≤393pt) | **3-tab bottom bar: Home / Practice / Progress** (Coach is **contextual** — reached Feedback→Coach) | tabs hidden in Quiz/Feedback/Coach/Summary; **"✕" close** returns to the prior screen (FR-B2) |

> **FR-B1 reconciliation.** UI-spec FR-B1 lists iPhone tabs "Home / Practice / Coach /
> Progress"; **§8.1 refines this to 3 tabs (Coach contextual on iPhone)** and the design
> encodes the refined model — FR-B1's 4-tab text is **superseded by §8.1**.

Route group: `app/(coach)/` with an **RSC layout** wrapping `<EngineProvider>` (B1/B2); each
screen is a **leaf `'use client'` island** with a justifying comment (B1). No control ships
without a destination (FR-B5).

---

## 5. Coach end-to-end (client stream ↔ BFF ↔ backend persona ↔ judges)

The showcase. One data flow spanning both rings, then the judge composition.

```
[Frontend Ring — browser]                         [Frontend Ring — BFF]         [Backend]
CoachView                                          app/api/coach/stream/route.ts  agent_ui_adapter
   │  send / chip / Enter (FR-F2)                       │  (F-R4/B6: adapter only)   → middleware
   ▼                                                    │  AuthProvider.getAccessToken → build_graph
use_coach  (wraps use_agent_run — F-R1)                 │  edge_proxy.forwardSSEStream   (subject-coach-
   │  holds threadId + lifecycle                        │  agent_id=subject-coach-english english persona,
   ▼                                                    │  strip Accept-Encoding (X6)    think+file_io only,
run_view_reducer  (reused pure fold)  ◄─── SSE tokens ──┤  no trace_id minting (F-R7)     reflexion OFF)
   │  AssistantRunView                                  │                                   │
   ▼                                                    │                              evaluate:
coach_message_vm.toCoachMessage  (T1, BUILT)            │                              Pedagogy + general
   │  { markdown, pending, error, canRetry }            │                              GoalJudge
   ▼                                                    │                                   │
coach bubble  (FR-F3 tokens; FR-F4 retry, no spinner)   │                              Grader Judge
                                                                                        (generated content)
```

### 5.1 Client stream — reuse, zero new client ports

The coach adds **no new client-side port**. `use_coach` wraps
[`use_agent_run`](../../frontend/components/chat/use_agent_run.ts) (the existing chat lifecycle
hook over `AgentRuntimeClient`), reusing the whole `transport/sse_client.ts` +
`translators/ag_ui_to_ui_runtime.ts` chain. It inherits the chat pipeline's terminal-state
safety (`run_error` synthesized on stream failure) which satisfies **FR-F4** (retry, never an
infinite spinner) for free. The only new client files are `use_coach` + `CoachView` +
`CoachPanel` — the VM (`coach_message_vm.ts`) is already built.

### 5.2 The shared thread (FR-J3 / FR-J3a / FR-J4)

The iPad split-coach panel and the full Coach screen are **one thread**: both bind the same
`threadId` in a single `use_coach` instance lifted to the `(coach)` layout (via a
`coach_thread_store` singleton / context), so `use_agent_run`'s send/resume continue the same
LangGraph checkpoint. This intra-surface sharing must **not** be conflated with **FR-J4**
cross-surface isolation (an iPhone and an iPad shown together keep independent state). The
two-tier hint **"One more nudge"** (FR-J3a) is a panel-local affordance that posts a "deeper
hint" quick-reply into the *same* thread; neither tier reveals the answer (FR-D5).

### 5.3 The thin BFF SSE route

`app/api/coach/stream/route.ts` is a **composition adapter only** (F-R4 / B6 / anti-pattern
FE-AP-3): read `AuthProvider.getAccessToken()`, call `transport/edge_proxy.forwardSSEStream`
**byte-for-byte** to `${MIDDLEWARE_URL}/agent/runs/stream` with the `subject-coach-english`
`agent_id`, strip `Accept-Encoding` (X6). No business logic, no `trace_id` generation (F-R7 —
the Python runtime mints it), no secrets in the bundle (F-R9). **Node runtime** (not edge —
downstream adapters are server-only). A clone of the existing `run/stream` route.

### 5.4 Backend coach persona

The coach is a **configured instance of the existing `build_graph`**, not a new graph node
(prompt-param fork, agent-spec invariant #6).

- **AgentFacts instance `subject-coach-english`:** `capabilities = [think, file_io]`,
  `policies = [domain=english-teaching, no-code-execution, answer-leakage-prohibited,
  rate-limit]`, HMAC-signed at registration. **Reuses the existing `AgentFacts` type — no
  `trust/models.py` change → no kernel re-sign** (agent-spec §5).
- **Capability gating — already landed** (ADR-0007): `components/capability_gating.py`
  (`derive_bound_tools`/`filter_registry_schemas`) is wired in `react_loop.py::build_graph`
  behind `bound_capabilities`; `test_capability_gating.py` asserts *declared = bound*
  (`shell`/`web_search`/`python` unbindable). Flags default OFF → coach shadow-first.
- **Persona prompt `prompts/subject_coach_system_prompt.j2`** (TO-BUILD), injected via
  `AgentConfig.additional_instructions`. **Acceptance criteria (agent brainstorm §3.1/§3.5):**
  scaffolding-first + Socratic; **teach-back** (Feynman — ask the student to explain their
  reasoning); **analogy-first** over re-explanation; **name-the-why** of revisiting a skill
  (Oakley / FSRS); **preserve productive struggle** — don't rescue too early (Holt). The
  persona *encodes* the anti-leakage stance the Pedagogy judge *measures*.
- **English-only input guardrail:** the injectable `InputGuardrail.accept_condition` (landed)
  set to a broad English-learning condition (grammar / usage / mechanics / rhetoric / reading /
  vocabulary / test strategy — not narrow "ACT English"); off-topic refused at `guard_input`
  before any coach LLM call. An FP-rate acceptance criterion guards over-refusal (agent-spec §7).
- **Reflexion OFF** (`reflexion_enabled = False`, ADR-0009): the coach must not rescue the
  answer; reflection is the offline Pedagogy judge, not an inline retry.

### 5.5 The three judges + `Verdict` composition (ADR-0008)

| Judge | Verdict shape | Home | Realized by | CI/cadence |
|---|---|---|---|---|
| **MC Grader** | `{correct}` (+ `correct_letter`, `rationale_key`) | **Frontend, offline** | `ExactLetterGrader` (**BUILT**, pure, sync) — the deterministic stage of the `Grader` port | client-only; no network |
| **Grader Judge** | `{faithfulness, correctness, justification, actionability}` | **Backend** | new `.j2` + `GraderVerdict` in `components/`; grades the coach's *generated content* every turn | L2 sampled + L3 nightly |
| **Pedagogy GoalJudge** | `{mistake_identification, mistake_location, actionability, coherence, productive_struggle, illusion_of_competence}` + **`answer_leakage` flag** | **Backend** | new `.j2` + `PedagogyVerdict` in `components/` | L2/L3, κ-calibrated |
| **general GoalJudge** | `{goal_met, criteria_met, unmet_conditions}` | Backend | **reused unchanged** | session-goal only |

**Composition statement.** ADR-0006's single `Grader` port `Verdict` is composed of **two
homes**: the frontend `ExactLetterGrader` owns the deterministic `correct` / `correct_letter` /
`rationale_key` — the **learner-facing** verdict, instant and offline; the backend Grader Judge
is the LLM-rubric stage that sits **behind** the deterministic verdict (verifier-first, per the
`Grader` port contract — the LLM never grades MC correctness in front of the learner). The
Pedagogy judge is the **offline turn-reflection** (ADR-0009) — it scores the coach's *own* turn,
not the learner's answer.

**The one non-negotiable constraint:** `answer_leakage` is recorded **distinctly, never
averaged** into a single quality score — a high-clarity hint that leaks the answer must still be
flagged (ADR-0008 rationale; the #1 measured tutoring failure mode, brainstorm §3.1). The Holt
(productive-struggle) and Oakley (illusion-of-competence) axes pull the same direction.

**Safety wiring:** all three LLM judges are flag-gated + mockable (reusing
`GoalJudgeRuntimeConfigReader`) so the CI path stays the deterministic grader + keyword fallback
— **no live LLM in CI**. Every evidence/content line passes the `GuardRailValidator` redactor
before it reaches a judge prompt (PII/secret hygiene, FR-18). The judges are injected into
`build_graph` (a small recorded API change, **paired** with ADR-0007's `build_graph` changes —
see ADR-0008 condition #2, §7). The new verdict types live in `components/`, importing only
`services/` + `trust/` (no langgraph — invariant #3/#4).

---

## 6. Cross-cutting invariants applied

| Rule | Statement | Satisfied by |
|---|---|---|
| **F-R1** | No domain logic in components | logic in `use_quiz`/`use_feedback`/`use_coach`; `QuizView`/`CoachView` are leaves |
| **F-R2 / A1** | SDK imports only in adapters | ts-fsrs/drizzle/pg in `adapters/engine/`; CopilotKit/AG-UI in chat adapters; `SDK_PACKAGES` list |
| **F-R4 / B6** | BFF routes are thin adapters | `app/api/coach/stream/route.ts` = auth + forward only |
| **F-R5** | Prompts in `.j2`, none in `.ts` | `subject_coach_*.j2`; no persona string in a `.ts`/`.tsx` |
| **F-R7** | `trace_id` from Python, browser never mints | coach reuses the chat SSE chain; route forwards, never generates |
| **T1** | VMs pure, import `wire/` (+`trust-view/`) only | all 7 VM translators; layering test enforces |
| **C2 / C3** | adapters only in composition roots; ports via context | `composition_engine*.ts`; ports via `useEngine()` |
| **B4** | Server Actions for UI mutations; Route Handlers for SSE | `record`/`close` via Server Actions; coach SSE via Route Handler |
| **P (ADR-0011)** | read-only compiler-enforced | `DrizzleLearnerReadRepo` depends on `ReadableEngineDb` (no write methods reachable) |

---

## 7. ADR adjudication (2026-07-01)

Ratifying = **flip the status header + a newest-first `log.md` line + update the `index.md`
entry** (the OKF triple).

### ADR-0011 `LearnerReadRepo` — **ACCEPTED** (the amended 2026-07-01 shape)

- **Context.** Dashboard mastery (FR-C3) + Summary delta (FR-G1) must *read* `skill_state`, but
  no accepted ADR-0006 port exposes it; the reads live on the `EngineDb` adapter seam, which UI
  code may not touch (C2/F-R1). The record was **materially amended 2026-07-01** (still
  Proposed at amend time).
- **Trade-off.** +1 read-only port and an ADR-0006 amendment (7→8 engine ports) *vs.* leaving
  the core loop's mastery permanently placeholdered or crossing a boundary. The amended shape
  fixes the earlier draft's two weaknesses: (i) it **narrows to Phase-1 `skill_state` reads
  only** (deferring `getTutorial`/`listProgressPoints` to a second amendment — the four-layer
  "build on the second consumer" rule + ADR-0010's deferral precedent, avoiding a frozen port
  shape for the still-Proposed subjective plane); (ii) it makes read-only **compiler-enforced**
  via a `ReadableEngineDb` projection (a deliberate rejection of the assert-in-prose hedge that
  forced ADR-0010's re-ratification); (iii) it specifies the FR-G1 before/after via a
  UI-captured session-start snapshot.
- **Decision.** **Accept.** Smallest correct unblock of the core loop; read-only by
  construction (Scheduler stays sole writer, FR-A2); delegates to reads that already exist on
  `EngineDb` + the in-memory fake.
- **Follow-through.** Flip proposed→accepted; `log.md` + `index.md`. Then build
  `learner_read_repo.ts` + `drizzle_learner_read_repo.ts` + `ReadableEngineDb` in `engine_db.ts`
  + two composition-bag lines + a conformance row + the no-write arch assertion + a
  `bucket_card_vm` `null→0%` lock test. Record ADR-0006 "amended by ADR-0011 (7→8 ports)".

### ADR-0009 Reflexion OFF for the coach — **ACCEPTED (clean)**

- **Context.** Whether to enable the pipeline's T2 Reflexion loop (a per-task retry) for the
  multi-turn coach.
- **Trade-off.** Essentially none — four independent grounds disqualify T2: wrong trigger (a
  coaching turn has no task-failure verdict; the student's reply *is* the loop);
  counter-pedagogical (Reflexion converges toward *the answer* = the answer-leakage the design
  forbids; Holt: don't rescue early); cost (2–3× LLM calls/turn on a latency-sensitive UX, no
  measured gain); and a latent `reflections` cross-turn leak. **The one hard prerequisite — the
  `reflections` leak — is already fixed** (`efc1715`/`27f1490`: per-entry `task_id` guard +
  `reflections_for_task`), so the blocker that would have forced "with conditions" is closed.
- **Decision.** **Accept (clean).** Codifies the shipped default (`reflexion_enabled = False`).
- **Follow-through.** Flip proposed→accepted; `log.md` (note "prerequisite satisfied by
  `efc1715`"); `index.md`. Update the ADR body's prerequisite section to MET and fix the
  past-tense reversal-trigger nit. No code change.

### ADR-0008 Three-judge split — **ACCEPTED WITH CONDITIONS**

- **Context.** The general `GoalJudge` cannot be retargeted (no correctness / answer-leakage /
  per-criterion axis). Ship three judges (MC Grader / Grader Judge / Pedagogy GoalJudge),
  maximal reuse; MC Grader is already built (`ExactLetterGrader`).
- **Trade-off.** Right, research-grounded design *vs.* two mitigations that are prose, not
  mechanical. The brainstorm §3.3 itself warns "a bad judge propagates errors unless
  rubric-anchored, criterion-separated, **and calibrated**" — so trusting the answer-leakage
  flag before a calibration floor exists is unearned.
- **Decision.** **Accept with conditions:** (1) a **stated, tracked κ TPR/TNR floor** for the
  answer-leakage detector before its flag is trusted in any gate (the ADR-0003 discipline); (2)
  the **`GoalJudge` `build_graph`-injection API change lands paired** with the judge build, not
  drifted.
- **Follow-through.** Flip proposed→accepted (with conditions); `log.md` + `index.md`. Then
  `GraderVerdict`/`PedagogyVerdict` in `components/`; the two `.j2` rubrics; the two judges;
  judge injection into `build_graph`; a calibration-cert row reusing the GoalJudge harness.
  Pedagogy axes include Holt (productive-struggle) + Oakley (illusion-of-competence).

### ADR-0010 ports realization / ts-fsrs / `EngineDb` — **KEEP Accepted-with-conditions; execute the two conditions**

- **Context.** Already Accepted (shipped, 129/129 arch tests green), re-ratified to
  Accepted-with-conditions after a review found two mitigations asserted-but-not-backed.
- **Trade-off.** Nothing warrants re-adjudicating the decision itself; re-opening is churn. The
  two conditions gate only the *next* increment (on-device SQLite), not merged code.
- **Decision.** **Keep as-is; drive the two conditions to closure.**
- **Follow-through.** (1) Write `schema.spec::same_drizzle_schema_compiles_pg_and_sqlite`
  (`tsc --noEmit` + column-for-column parity over `schema.{pg,sqlite}.ts`); add to `make check`.
  (2) Add a real numbered follow-up to `preact-english-coach-engine.spec.md` §8 for the
  `DATABASE_URL`-gated `pgEngineDb` integration test, replacing the dangling "§8.2" citation.
  When both land: a `log.md` "conditions MET" line + drop the ⏳ PENDING banner (mirrors the
  ADR-0007-condition-MET precedent).

| ADR | Prior | Ruling | Key reason |
|---|---|---|---|
| 0011 | Proposed (amended) | **Accept** | Amended shape fixes the bundling + assert-in-prose weaknesses; smallest correct core-loop unblock |
| 0009 | Proposed | **Accept (clean)** | Airtight; the one prerequisite (reflections leak) already fixed in `efc1715` |
| 0008 | Proposed | **Accept w/ conditions** | Right design; the κ-floor + `build_graph` injection must be mechanical, not prose |
| 0010 | Accepted-w/-cond. | **Keep; execute conditions** | Decision sound; conditions gate the next increment only |

### Spec-vs-code divergences (documented; follow-ups filed)

1. **`CoachAgentClient` is not an engine port.** The sibling design doc §3 and the agent
   brainstorm §4 list `CoachAgentClient` as an 8th "engine port." The built code has **no** such
   port — the coach rides the **chat `AgentRuntimeClient`** (`use_coach` wraps `use_agent_run`,
   per `coach_message_vm.ts`'s own header). **Reconciliation:** the coach is a *consumer of the
   chat runtime port*, not an engine port; the engine bounded context is 7 ports (→ 8 with
   `LearnerReadRepo`, still not the coach). Filed to `docs/adr/decisions.md`.
2. **FR-G3 parity test missing** (ADR-0010 condition #1) — flagged in §3; tracked.
3. **iPhone 3-tab model** — FR-B1's 4-tab text is superseded by UI-spec §8.1; §4.8 encodes the
   3-tab (Coach-contextual) model.

---

## 8. Build sequencing

1. **Ratify ADR-0011** → build `LearnerReadRepo` + `ReadableEngineDb` + adapter + conformance
   row + two composition-bag lines → **unblocks Dashboard (4.1) + Summary delta (4.5)**.
2. **Execute ADR-0010's two conditions** (FR-G3 parity test; real §8 tracked item) → unblocks
   the on-device SQLite increment + Progress (4.7).
3. Build **Dashboard, Summary, coach client** (`use_coach` + `CoachView` + iPad split panel +
   shared-thread singleton), the `app/(coach)/` route group, and `app/api/coach/stream/route.ts`.
4. **Ratify ADR-0008 (with conditions) + ADR-0009** → build the persona `.j2`, the
   `subject-coach-english` AgentFacts instance, the two backend judges + verdict types, and the
   judge injection into `build_graph`; **flip the coach flags on shadow-first**.
5. Resume **Screens 6/7** (deferred) via a **second ADR-0006 amendment** that lands the
   `getTutorial` / `listProgressPoints` reads.

Every build step carries its own red-first tests per the specs' §8 test plans (each screen's
test list is in §4; the engine's in `preact-english-coach-engine.spec.md` §8; the agent's in
`subject-coach-agent.spec.md` §8).
