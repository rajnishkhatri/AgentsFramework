# Tasks — Exam module (official-rules durable test suite)

> **Status:** ✅ Approved 2026-09-02 (spec §10 + plan §6 + this tasks list signed off) — ready
> for **sdd-implement**, which creates `feat/exam-module` (off `main`) + the WT-1/WT-2
> worktrees per plan §6.4 and executes the lanes.
>
> SDD Stage 3 · derived from [spec](exam-module-official-rules.spec.md) (incl. §10 arch-sweep
> FRs) + [plan §6](exam-module-official-rules.plan.md) parallel-worktree strategy.
> **Base branch:** `feat/exam-module` off `main` (created at implement time).
> **Legend:** lane ∈ {BASE, WT-1, WT-2, SERIAL}; `∥` = runs concurrently with the sibling
> lane; **RED-FIRST** = author the failing test before impl (watch it fail). Every task's
> pass/fail is a named test mapped to an EARS FR. Paths verified by the 2026-09-02 evidence
> sweep unless marked *(new)*.

## Phase 0 · BASE — land FIRST on `feat/exam-module` (base stays releasable)

| ID | Task (files) | Deps | Pass/fail (test → FR) |
|---|---|---|---|
| **B0-1** | `lib/wire/exam_entities.ts` *(new)* — zod ExamForm/Section/Question, ExamRun, ExamSectionAttempt, ExamRunItem, ExamAnalytics | — | `exam_entities.test` zod round-trip + snapshot → **FR-9** |
| **B0-2** | `lib/adapters/engine/exam_forms/{index,test01_english}.ts` *(new)* — static registry wrapping `TEST01_SERVED_QUESTIONS`; load-time asserts | B0-1 | `exam_forms.test` empty form/section + unsupported `choice_count` throw at load → **FR-6** |
| **B0-3** | `components/exam/exam_dwell_merge.ts` *(new)* — **one** pure `monotonic-max` merge (dwell max, visits/changes max, first-answer keep-first) | B0-1 | `exam_dwell_merge.test` unit → **FR-39** (imported by both lanes) |
| **B0-4** | `frontend/tests/architecture/test_exam_isolation.test.ts` *(new)* — **RED-FIRST**; resolved module graph (type-only + dynamic imports); no `components/exam`/`exam_run_repo` ↔ quiz/scheduler/`skill_state` edges; no `skill_state` write; **+ a planted red fixture**. *(Frontend TS/ts-morph dir — root `tests/architecture/` is Python; corrects the spec/plan/ADR-0040 path.)* | — | guard green vacuously over empty tree **and** red fixture proves it fails on a forbidden edge → **FR-41/FR-26** |
| **B0-5** | `frontend/tests/architecture/test_exam_no_client_served_keys.test.ts` *(new)* + `components/exam/exam_key_posture.ts` *(new — frontend const code-switch, not env-overridable)* — **RED-FIRST**; no **DB-served** form serializes `answer_letter`/`per_choice_rationale`/`why_*` to client while posture=`"client"`. *(Frontend TS; conceptually mirrors ADR-0013's `coach_test_mode_posture.py` pattern — the exam module is frontend-only, so both flag and guard are TS.)* | B0-1 | guard green (client-bundled phase-1 exempt) + red fixture (DB-served form w/ keys fails) → **FR-35** |
| **B0-6** | injected `now()`/monotonic-clock seam contract *(new, tiny)* used by reducer + buffer | — | `tsc` green; deterministic in W2 tests → **§7** |
| **B0-7** | `EnginePortBag` exam **stub** — declare `examRunRepo?: ExamRunRepo` in server + browser composition roots (undefined stub) | B0-1 | `tsc` + `test_engine_port_conformance` green; lets **WT-2 compile against the port** |

*Freeze `exam_entities.ts` + `exam_dwell_merge.ts` after Phase 0* — lane changes to them route back to base.

## Phase 1 · WT-1 Persistence — `feat/exam-wt-persistence` (∥ WT-2) — owns `lib/adapters/engine/**` ONLY

| ID | Task (files) | Deps | Pass/fail (test → FR) |
|---|---|---|---|
| **W1-1** | `schema.{pg,sqlite}.ts` +3 tables + indexes; `drizzle/0005_exam_runs.sql` | B0-1 | `schema.parity.test` incl. **constraints/defaults/PK-FK** → **FR-40/§4.2** |
| **W1-2** | `EngineDb` +9 methods + `engine_db_disposition` (all "fine", learner-scoped); conformance count 32→**41** | W1-1, B0-7 | `http_engine_db.conformance.test` `toHaveLength(41)` |
| **W1-3** | **RED-FIRST** named-learner-arg convention + dispatcher `LEARNER_ARG` entries (arg0 named); completeness test (every exam method mapped; default **deny**) | W1-2 | `…dispatcher_learner_arg` completeness + arg0-name → **FR-38 (R4)** |
| **W1-4** | `in_memory_engine_db` +9 — upsert via `exam_dwell_merge`; **begin keep-first**; finish-once | W1-2, B0-3 | L2 idempotent-once + monotonic-max + finish-once + begin-keep-first → **FR-4/27/37** |
| **W1-5** | `drizzle_engine_db` +9 — upsert (pg/sqlite via shared merge contract); `.onConflict` | W1-4 | L2 sqlite **+ real-Postgres two-device concurrency** (RED-FIRST) → **FR-4/40 (R8)** |
| **W1-6** | `HttpEngineDb` +9 + BFF `/api/engine/db/[method]` wiring | W1-2 | conformance + **foreign-learner→403/404 on EACH method** → **FR-3 (R4/SEC-5)** |
| **W1-7** | `lib/ports/engine/exam_run_repo.ts` *(new)* + `repos/drizzle_exam_run_repo.ts` *(new)*; fill `EnginePortBag` exam entry | W1-6, B0-7 | port conformance + finished-cannot-reopen (FR-2) + begin-conflict (FR-12) |

## Phase 1 · WT-2 Domain — `feat/exam-wt-domain` (∥ WT-1) — owns `components/exam/**` ONLY (tests vs an in-memory `ExamRunRepo` fake)

| ID | Task (files) | Deps | Pass/fail (test → FR) |
|---|---|---|---|
| **W2-1** | `exam_section_reducer.ts` *(new)* — phases directions/in_section/finished; nav/answer/clear/flag; dwell (injected clock + `visibilitychange`); deadline→expired | B0-1/3/6 | `exam_section_reducer.test` → **FR-1,13–24** (deadline→expired+writes-refused; navigator states; dwell pause/sum/first-answer immutable) |
| **W2-2** | `exam_scoring.ts` *(new)* — raw over scored; scale|null; composite=round(mean),.5up | B0-1/2 | `exam_scoring.test` → **FR-7,8,27,28** |
| **W2-3** | `exam_analytics.ts` *(new)* — facets/pacing/recommendations; RULES-as-data; ≥5-item labels; median-dwell quadrants; **finalized-runs-only** | B0-1 | `exam_analytics.test` fire/don't-fire + `insufficient_data` + finalized filter → **FR-30–33** |
| **W2-4** | `exam_write_buffer.ts` *(new, C4 split)* — **R2 FULL LADDER**: buffer/debounce + `localStorage` mirror + `pagehide`/`sendBeacon` + backoff retry + block-finalize-while-unflushed; client side of `exam_dwell_merge` | B0-3/6, W1-7 (port type only) | `exam_write_buffer.test` offline-flush; failed-flush→not-saved; localStorage-restore; pagehide-beacon; **block scored finalize while unflushed** → **FR-5/36** |
| **W2-5** | `use_exam_section.ts` *(new)* — orchestration hook (begin/submit/wire buffer/offline state) vs in-memory port fake | W2-1, W2-4 | `use_exam_section.test` lifecycle + not-saved surfacing → **FR-5** |

## Phase 2 · SERIAL on base (after WT-1 + WT-2 merged)

| ID | Task (files) | Deps | Pass/fail (test → FR) |
|---|---|---|---|
| **S-D1** | 3 pages `app/(coach)/learn/exam/{page,[runId]/page,[runId]/[section]/page}.tsx` *(new)* — thin `'use client'` glue (B1) | WT-1✓, WT-2✓ | render + status per section → **FR-10–12** |
| **S-D2** | Views `ExamHome/Directions/Runner/Navigator/Review/Results/AnalyticsPanel` *(new)* | S-D1 | **FR-13–29** |
| **S-D3** | `/learn/progress` "Exam performance" panel via `use_progress_screen` → `listExamRunItemsByLearner` → `exam_analytics` | S-D2, W1-2 | panel sourced **only** from `ExamAnalytics` → **FR-34** |
| **S-D4** | nav entry (`nav_model` exam screen + `SCREEN_TITLES`) — **last commit** (reachability gate) | S-D3 | feature reachable; rollback = remove entry |
| **S-E1** | `e2e/learn/exam.spec.ts` *(new)* — walk; 5-min warning via `?dur=`; auto-submit; reload-resume; flag→review; **Test Mode e2e still green** | S-D4 | chromium smoke → **FR-13–16,23–25** |
| **S-F1** | ADR-0040 Proposed→Accepted (index/log) **[D1 human — still Proposed at implement start]**; `decisions.md` ✓; ADR-0041 ✓. D2 path: [approval-criteria.md](../adr/common/approval-criteria.md) (values UNSET) | — | OKF lint 0 failures; D1 remains human |
| **S-F2** | **R5 infra** — Cloud Run `min-instances ≥ 1` (exam route) + Cloud SQL pool cap | — | infra applied (Terraform/deploy) |
| **S-F3** | pre-traffic `migrate_engine.mjs` runs `0005`; second-device read-back smoke | S-F2 | prod smoke (plan §3) |

## Critical path & parallelism

- **Critical path:** `B0-* → (WT-1: W1-1→…→W1-7) → S-D* → S-E1 → S-F3`. WT-2 runs fully
  **inside** WT-1's window (it's pure-domain, no live adapter), so WT-2 is **off** the
  critical path — the wall-clock floor is BASE + WT-1 + SERIAL.
- **Parallel win:** WT-2's 5 tasks (reducer/scoring/analytics/buffer/hook — the bulk of the
  FR count, FR-1/5/8/13–33/36/39) execute concurrently with WT-1's 7, on disjoint files.
- **Merge points where the guards bite:** WT-1→base and WT-2→base each re-run
  `test_exam_isolation` + `test_exam_no_client_served_keys` + the `exam_dwell_merge` cross-side
  fixture → boundary + connascence verified at integration, not deferred to S-E1.

## Stage 4 · Analyze (cross-artifact check + baseline)

- **spec ↔ plan ↔ tasks:** every §3/§10 FR maps to ≥1 task above (FR-1..41 covered); every
  task cites a test. No task references a non-existent file/API (paths sweep-verified; new
  files marked *(new)*).
- **Constitution (AGENTS.md):** frontend-only; root invariants #1–#8 untouched; **no new
  `package.json`/`pyproject.toml` dep**; new abstractions (ExamRunRepo, ExamAnalytics,
  Write-Buffer) each carry an ADR/decisions entry (ADR-0040/0041 + 2026-09-02 lines).
- **ADR seam:** the ⚠️ Ask-first triggers (repo seam + analytics abstraction + answer-key
  posture) are covered by ADR-0040 + ADR-0041 → `test_adr_ratchet` satisfied.
- **Baseline before implement:** `make check` + `pytest tests/architecture/ -q` +
  `pnpm test` + `pnpm typecheck` green on `feat/exam-module` after Phase 0.

**Route → sdd-implement** (execute lanes; create the worktrees at that point per plan §6.4).
