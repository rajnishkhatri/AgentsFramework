# Plan — Exam module: official-rules full-length test suite

**Status:** Draft for Stage-2 plan gate — 2026-09-01
**Spec:** [exam-module-official-rules.spec.md](exam-module-official-rules.spec.md) (approved 2026-09-01)
**ADR:** [ADR-0040](../adr/0040-exam-module-durable-runs-analytics.md) (proposed — covers the new repo seam + the analytics read model)
**Constitution check:** frontend-only; root invariants #1–#8 untouched (no Python, no `trust/`, no graph node, no new dependency). Frontend Ring rules F-R1…F-R9 / A2 / A3 / P1 / B1 apply and are named per track below.

---

## 0. Grounding corrections to the spec (found while planning)

- **Dispatcher, not a route family.** ADR-0038's fine-grained path is the *generic*
  `POST /api/engine/db/<method>` handler (`app/api/engine/db/[method]/route.ts`) whose
  `LEARNER_ARG` / `LEARNER_FIELD_ARG` maps override the learner argument from the server
  claim. Spec §4.3 said `/api/engine/exam/*`; the plan uses the dispatcher (ADR-0040
  option E) and the spec line is corrected to match.
- **`EngineDb` has 32 methods today** (not 31); the conformance test asserts the exact
  count, so +9 → 41 is an explicit edit.
- **sqlite has no migration runner** (`scripts/migrate_engine.mjs` is Postgres-only);
  sqlite parity is `schema.sqlite.ts` + `schema.parity.test.ts`, nothing more.
- **`useCountdown(durationMs)` anchors on `Date.now()` at mount** — deadline anchoring
  (FR-14) is `durationMs = deadline_at − now` at mount, so the hook is reused unchanged.

## 1. Architecture (least machinery)

```
app/(coach)/learn/exam/page.tsx                 home: forms × section status (FR-10–12)
app/(coach)/learn/exam/[runId]/page.tsx         run results + analytics (FR-28, FR-34)
app/(coach)/learn/exam/[runId]/[section]/page.tsx   directions → runner → review (FR-13–29)
components/exam/
  exam_section_reducer.ts      pure phase machine: directions|in_section|finished; nav, answer,
                               flag, dwell (injected monotonic clock + visibility events)
  exam_scoring.ts              raw over scored items, scale from table|null, composite|null
  exam_analytics.ts            ExamRunItem[] + ExamSection[] → ExamAnalytics; RULES table
  use_exam_section.ts          orchestration hook: begin, buffered/debounced flush, submit,
                               offline "not saved" state (FR-5, FR-21)
  ExamHomeView / ExamDirectionsView / ExamRunnerView / ExamNavigator /
  ExamReviewView / ExamResultsView / ExamAnalyticsPanel   presentational (F-R1)
lib/wire/exam_entities.ts      zod: ExamForm/Section/Question, ExamRun, ExamSectionAttempt,
                               ExamRunItem, ExamAnalytics (+ snapshot test)
lib/adapters/engine/exam_forms/index.ts + test01_english.ts   static form registry (FR-6/9)
lib/ports/engine/exam_run_repo.ts             ONE interface (P1), learnerId-first methods
lib/adapters/engine/repos/drizzle_exam_run_repo.ts   wraps EngineDb like drizzle_session_repo
lib/adapters/engine/db/{engine_db,engine_db_disposition,http_engine_db,drizzle_engine_db,
                        in_memory_engine_db}.ts        +9 methods each
lib/adapters/engine/db/schema.{pg,sqlite}.ts + drizzle/0005_exam_runs.sql
tests/architecture/test_exam_isolation.test.ts
e2e/learn/exam.spec.ts
```

Reused as-is (sibling imports, recorded in `decisions.md`): `components/test/format_clock.ts`,
`use_countdown.ts`, `CountdownTimer.tsx`; the engine `Grader` via `useEngine()`;
`TEST01_SERVED_QUESTIONS` as the phase-1 form's question source (do-not-edit respected —
the registry *wraps* it, never mutates it).

### `EngineDb` additions (all `"fine"` disposition, learner-scoped)

| Method | Args (learnerId first ⇒ dispatcher `LEARNER_ARG` = 0) | Semantics |
|---|---|---|
| `insertExamRun` | `(learnerId, run)` | new run row |
| `listExamRunsByLearner` | `(learnerId, formId?)` | runs + section attempts |
| `getExamRun` | `(learnerId, runId)` | run + attempts + items, `null` if not owned |
| `beginExamSection` | `(learnerId, runId, section, startedAt, deadlineAt)` | `not_started → in_progress`; **conflict** if another section of the run is in progress (FR-12) or attempt not `not_started` (FR-2) |
| `upsertExamRunItems` | `(learnerId, runId, section, items[])` | idempotent upsert; `dwell_ms = max(old,new)`, `visits`/`answer_changes` = max, first-answer fields keep-first; **rejected** if attempt not `in_progress` (FR-1/2) |
| `finishExamSection` | `(learnerId, runId, section, status, grades, remainingMs)` | at-most-once: if already finished return stored result (§7) |
| `setExamRunComposite` | `(learnerId, runId, composite\|null)` | written by the finish path when all composite sections done (FR-28) |
| `setExamBookmark` | `(learnerId, runId, section, questionId, bookmarked)` | allowed only on finished attempts (FR-25) |
| `listExamRunItemsByLearner` | `(learnerId)` | cross-run analytics input (FR-30) |

Ownership = every query joins `exam_run.learner_id = learnerId` (FR-3) — no new guard helper.

### Data (migration `0005_exam_runs.sql`, pg; mirrored in `schema.sqlite.ts`)

`exam_run(id pk, learner_id, form_id, created_at, composite null)` ·
`exam_section_attempt(pk(run_id, section_code), status, started_at, finished_at, deadline_at,
raw_correct, raw_scored_total, scale_score, time_remaining_ms_at_submit)` ·
`exam_run_item(pk(run_id, section_code, question_id), ordinal, chosen_letter, correct,
dwell_ms, visits, answer_changes, first_answered_at, dwell_at_first_answer_ms,
flagged_in_section, bookmarked, updated_at)` · indexes `exam_run(learner_id, form_id)`,
`exam_run_item(run_id, section_code)`. Timestamps follow `quiz_session`'s helpers.

### Analytics rules table (`exam_analytics.ts`)

`RULES: ReadonlyArray<{ id, applies(facets, pacing) → evidence | null, priority }>` — phase-1
rows: `pacing`, `careless`, `knowledge_gap`, `revise_flagged`. Thresholds as named constants
(`LABEL_MIN_ITEMS = 5`, `STRENGTH_ACC = 0.80`, `WEAKNESS_ACC = 0.60`) → `decisions.md`.

## 2. Tracks (dependency order; ∥ = parallelisable)

| Track | Scope | Depends on | FRs |
|---|---|---|---|
| **T-A Wire + forms** | `exam_entities.ts` (+ zod snapshot), `exam_forms/` registry with load-time assertions (`choice_count` ∈ renderer-supported set), Test-01 English form (`composite_sections=["english"]`, `scale_table` from `test_scoring.ts`'s band table ⇒ **band, not point** — expose as `scale_band` string and keep `scale_score: null`, honest FR-7) | — | 6, 7, 9 |
| **T-B Persistence** | schema pair + parity rows, `0005` SQL, `EngineDb` +9, disposition +9, in-memory impl, drizzle impl (upsert semantics), `HttpEngineDb` +9 + conformance rows (count 41), dispatcher `LEARNER_ARG` entries, port + repo, `EnginePortBag` (server + browser) | T-A | 1–4, 12, 27 (store) |
| **T-C Domain** ∥ T-B | `exam_section_reducer.ts` (nav/answer/clear/flag/dwell/visibility/deadline), `exam_scoring.ts`, `exam_analytics.ts`, `use_exam_section.ts` (buffer/flush/offline against the port interface — testable with an in-memory fake) | T-A | 1, 5, 8, 13–33 |
| **T-D UI** | three pages (B1 comments), views, navigator, nav_model `exam` screen (+`SCREEN_TITLES`), results + analytics panel; `/learn/progress` "Exam performance" panel via `use_progress_screen` (reads `listExamRunItemsByLearner` → `exam_analytics`) | T-B, T-C | 10–29, 34 |
| **T-E Guards + e2e** | `test_exam_isolation.test.ts` (ts-morph: no edges `components/exam|exam_run_repo ↔ components/quiz|scheduler|skill_state writers`), `e2e/learn/exam.spec.ts` (walk, 5-min warning via `?dur=`, auto-submit, reload-resume, flag→review), Test Mode e2e still green | T-D | 26, 13–16, 23–25 |
| **T-F Docs + deploy** | ADR-0040 accepted (index/log), `decisions.md` ×3 (thresholds, quadrant median, sibling timer imports), `docs/preact9secure/README.md` step-2 pointer → registry; pre-traffic `migrate_engine.mjs` (ADR-0038 Track F) | all | DoD |

## 3. Migration / rollout

1. Land T-A…T-E behind the new route only (no flag needed: unreachable unless navigated;
   nav entry is the last commit of T-D).
2. Deploy runs `scripts/migrate_engine.mjs` pre-traffic (existing step) — `0005` is
   additive; rollback = leave tables in place, remove the nav entry.
3. Smoke: one real section walk on prod (`gcp-live-smoke` style), then read the run back
   on a second device.

## 4. Risks & mitigations

- **Totality tests break on purpose** (method count, disposition keys, conformance
  table, parity pairs): each is a listed task, red before green.
- **Dwell accuracy** is client-side and advisory: monotonic-max upserts + server deadline
  keep the *section* honest even if dwell is lost (edge cases §6 of the spec).
- **Thin phase-1 corpus** (24 English items): the registry shape is the deliverable;
  follow-up specs load the Test-01 remaining sections and the private official forms.
- **Scope creep magnets**: Math rendering / 5-choice wire change / LLM narrative / Test
  Mode retirement — all named non-goals; route to sdd-replan if they surface.

## 5. Stage-4 analyze checklist (run before implementation)

- Every path above probed (glob/grep) — see tasks file "grounding" column.
- No `package.json` / `pyproject.toml` change.
- Baseline `make check` + `pytest tests/architecture/ -q` + `pnpm test` + `pnpm typecheck` green.

---

## 6. Parallel-worktree execution + merge strategy (2026-09-02 replan)

> Folds the ratified arch-sweep decisions into a build shaped for **maximum parallelism**.
> Tasks: [exam-module-official-rules.tasks.md](exam-module-official-rules.tasks.md).
> Clarify answers (2026-09-02): R2 **full** buffer ladder · guard = **no DB-served keys** ·
> **2 lanes on a guards-first base** · **continuous** integration to base.

### 6.1 Base branch
`feat/exam-module` off **`main`** (created at implement time — not now). The exam
spec/plan/ADR-0040/ADR-0041 + the `.arch/` sweep are migrated onto it, isolated from the
unrelated `feat/okf-curator-portability` work currently checked out.

### 6.2 Lane topology

```mermaid
flowchart TB
  subgraph P0["Phase 0 · BASE (feat/exam-module) — land FIRST, stays releasable"]
    A[T-A wire exam_entities + zod]:::b
    FR[Form registry + load asserts]:::b
    DM[R6 exam_dwell_merge.ts — ONE pure fn]:::b
    G1[R1 test_exam_isolation — resolved-graph + red fixture]:::b
    G3[R3 test_exam_no_client_served_keys — DB-served predicate]:::b
    CK[injected now/clock seam contract]:::b
  end
  subgraph P1["Phase 1 · TWO PARALLEL LANES (each its own worktree off base)"]
    W1["WT-1 Persistence · feat/exam-wt-persistence<br/>lib/adapters/engine/** ONLY"]:::w
    W2["WT-2 Domain · feat/exam-wt-domain<br/>components/exam/** ONLY"]:::w
  end
  subgraph P2["Phase 2 · SERIAL on base"]
    D[T-D UI]:::s --> E[T-E e2e]:::s --> F[T-F docs/deploy]:::s
  end
  P0 --> W1 & W2
  W1 -->|merge when green| P2
  W2 -->|merge when green| P2
  classDef b fill:#eef,stroke:#88a; classDef w fill:#efe,stroke:#8a8; classDef s fill:#ffe,stroke:#aa8;
```

**Phase 0 — BASE (the integration trunk).** The shared surfaces every lane depends on,
landed first so the lanes *inherit* them and can't diverge:
- `lib/wire/exam_entities.ts` (+ zod snapshot) [FR-9] · form registry [FR-6].
- **R6 `exam_dwell_merge.ts`** — the single `monotonic-max` fn both sides import [FR-39].
- **R1 `test_exam_isolation`** — authored red-fixture-first, then runs **green vacuously**
  over the empty tree (no exam code yet ⇒ no forbidden edge), so the boundary is enforced
  from commit 0 and the base stays releasable [FR-41/FR-26].
- **R3 `test_exam_no_client_served_keys`** — DB-served-form predicate (client-bundled
  phase-1 exempt) [FR-35].
- the injected `now()`/monotonic-clock seam contract [§7 determinism].

**Phase 1 — two parallel lanes (disjoint directories ⇒ clean merges):**

| Lane | Worktree / branch | Owns (only) | Folds in | FRs |
|---|---|---|---|---|
| **WT-1 Persistence** | `.worktrees/exam-persistence` · `feat/exam-wt-persistence` | `lib/adapters/engine/**` (EngineDb +9, disposition, conformance 32→41, HttpEngineDb, in-memory, drizzle, `schema.{pg,sqlite}`, `0005`, dispatcher `LEARNER_ARG`, `ExamRunRepo` port + adapter, `EnginePortBag`) | **R4** named-arg + completeness test · **R5** `begin` keep-first (FR-37) · **R8/R15** real-pg concurrency + deep parity (FR-40) | 1–4,12,27(store),37,38,40 |
| **WT-2 Domain** | `.worktrees/exam-domain` · `feat/exam-wt-domain` | `components/exam/**` (reducer, scoring, analytics, hook) + the **C4→Write-Buffer** unit `exam_write_buffer.ts` | **R2** full ladder — sendBeacon/pagehide + `localStorage` mirror + retry + block-finalize-while-unflushed (FR-36) · **R6** client side of the shared merge fn | 1,5,8,13–33,36,39 |

- **Conflict hotspot kept in ONE lane:** every `EngineDb` totality edit lives in **WT-1**;
  splitting them across lanes would collide on the same files. WT-2 is pure `components/exam/**`
  tested against an **in-memory fake of the `ExamRunRepo` port**, so it needs none of WT-1's
  live code to go green. The two lanes' file sets are **disjoint** ⇒ order-independent merges.

**Phase 2 — serial on base:** T-D UI (needs B+C) → T-E e2e (the isolation guard already
lives in base) → T-F docs/deploy (ADR-0040 acceptance, migrate pre-traffic, **R5 infra:
Cloud Run `min-instances ≥ 1` for the exam route + pool cap**).

### 6.3 Merge strategy — continuous to base
1. Land **Phase 0** on `feat/exam-module`; base is green (guards enforce vacuously + prove
   red via fixtures). **Freeze the wire + `exam_dwell_merge.ts` after Phase 0** — a lane
   needing a wire change routes it back to base (coordinated), never edits it in-lane.
2. WT-1 ∥ WT-2 branch off base; each **rebases on base** frequently (base rarely moves post-P0).
3. Merge **WT-1 → base** and **WT-2 → base** independently, each when green
   (`make check` + `pnpm vitest run` + `pytest tests/architecture/ -q`). Order between them
   is free (disjoint files). Their merge is where the R1/R3 guards + the R6 fixture bite —
   the boundary is verified *at integration*, not deferred to T-E.
4. Then T-D → T-E → T-F serially on base. Final: one PR `feat/exam-module → main` (or staged
   per-phase PRs).

**Conflict-avoidance invariants:** WT-1 owns all `lib/adapters/engine/**`; WT-2 owns all
`components/exam/**`; neither writes the other's tree. `EnginePortBag` (server + browser
composition roots) is a small shared-ish surface — land its exam stub in **Phase 0**, filled
by WT-1, so WT-2 compiles against the port without touching composition.

### 6.4 Worktree hygiene (this repo)
Fresh worktrees need `frontend/node_modules` symlinked to the main worktree and (for any
Python) the root `.venv` symlinked — see the repo's worktree notes; do this at `add` time.
