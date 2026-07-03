# Plan + Tasks — Quiz attempt real elapsed timing (D0)

**Spec:** [quiz-attempt-elapsed-timing.spec.md](quiz-attempt-elapsed-timing.spec.md)
**Clarified decisions (2026-07-03):** start timestamp lives in **reducer state**;
elapsed is **wall-clock via monotonic `performance.now()`** (active-focus timing is
out of scope). Both match the spec's recommended path.

---

## Plan (Stage 2 — architecture + touchpoints)

The clock starts at the `item_loaded → answering` transition and stops at submit.
The start timestamp lives in the reducer's `answering` state so `page.tsx` stays
glue-only (F-R1) and timing is node-testable without React.

**Data flow (unchanged plumbing, honest source):**

```
item_loaded(item, presentedAt)         ← NEW: clock start (performance.now())
   → answering{ …, presentedAt }       ← NEW reducer field
onSubmit: elapsedMs = round(now() − presentedAt)   ← replaces literal 0
   → submit({ …, elapsedMs })          ← existing arg (use_quiz.ts:113)
   → attemptRepo.record({ elapsed_ms }) ← existing write (use_quiz.ts:146)
   → schema/wire (unchanged)
```

**File-level touchpoints (all under `frontend/`, all verified to exist):**

| File | Change | Kind |
|------|--------|------|
| `components/quiz/quiz_screen_reducer.ts` | Add `presentedAt: number` to `AnsweringPhase`; `item_loaded` action carries `presentedAt`; set it on the transition | source |
| `app/(coach)/learn/quiz/page.tsx` | Pass `performance.now()` into the `item_loaded` dispatch (effect 2); in `onSubmit` compute `elapsedMs = Math.max(0, Math.round(performance.now() − state.presentedAt))` instead of `0` (line 121) | source |
| `components/quiz/quiz_screen_reducer.test.ts` | New L1 cases: FR-2/3/5/6 | test |
| `components/quiz/use_quiz.test.ts` | Keep non-zero-`elapsedMs` regression green; extend FR-1 no-row assertion | test |
| `docs/adr/decisions.md` | 2–4 line entry: monotonic clock + wall-clock (not active-focus) | doc |

**No** change to `wire/`, `ports/`, `adapters/`, `translators/`, DB schema, or
`pyproject.toml`. No ADR (no ⚠️ Ask first trigger). No new dependency.

**Clock injection for tests.** `performance.now()` is called at the page (dispatch
site + submit site). To keep reducer tests deterministic, the reducer receives
`presentedAt` as *data* on `item_loaded` (it never calls the clock itself) — tests
feed fixed numbers. The page's two `performance.now()` reads are exercised by the
existing page/integration test with a stubbed `performance.now` (or the elapsed math
is factored into a tiny pure `elapsedMsFrom(presentedAt, now)` helper the tests call
directly).

---

## Tasks (Stage 3 — atomic, red-first, 1:1 to EARS)

Order: failure paths first. Each task: write test → **see it fail** → implement →
green. `[P]` = parallelizable with siblings once T1 lands.

### T1 — Reducer carries the start timestamp  (FR-3, FR-6)
- **Depends on:** none (foundation).
- **Change:** `AnsweringPhase` gains `readonly presentedAt: number`. The
  `item_loaded` action gains `presentedAt: number`; the reducer stores it on the
  `answering` slate. `next → loading → item_loaded` naturally supplies a fresh
  `presentedAt` (per-item reset, FR-6).
- **Tests (red first):**
  - `item_loaded sets presentedAt on the answering state` (FR-3).
  - `a second item_loaded after next resets presentedAt` (FR-6).
- **Pass/fail:** reducer state exposes the per-item `presentedAt`; no cumulative carry.

### T2 [P] — Elapsed computation is monotonic and clamped  (FR-2, FR-5)
- **Depends on:** T1.
- **Change:** introduce `elapsedMsFrom(presentedAt: number, now: number): number`
  returning `Math.max(0, Math.round(now − presentedAt))` (co-located pure helper, or
  inline with a direct unit test). Guarantees non-negative, whole-ms, `NaN`-safe.
- **Tests (red first):**
  - `elapsed clamps to 0 when now < presentedAt` (monotonic-safety / FR-5).
  - `missing/undefined start ⇒ 0, never NaN/negative` (FR-2).
  - `sub-ms delta rounds to 0` (honest 0, not stub — edge case §6).
- **Pass/fail:** helper is pure, deterministic, and never emits a negative/`NaN`.

### T3 — Page computes and passes real elapsed  (FR-4)
- **Depends on:** T1, T2.
- **Change:** in [page.tsx](../../frontend/app/(coach)/learn/quiz/page.tsx):
  (a) effect 2's `item_loaded` dispatch carries `performance.now()`;
  (b) `onSubmit` replaces `elapsedMs: 0` (line 121) with
  `elapsedMs: elapsedMsFrom(state.presentedAt, performance.now())`.
- **Tests (red first, against current stub):**
  - page/integration test with stubbed `performance.now`: submit records
    `elapsed_ms = stop − start` (e.g. start 1000, stop 3500 ⇒ `2500`) (FR-4).
- **Pass/fail:** no literal `0` remains at the submit site; recorded attempt carries
  the computed value.

### T4 [P] — No-selection path still writes no row  (FR-1, regression)
- **Depends on:** T1.
- **Change:** none to production code (behavior must be preserved).
- **Tests:**
  - Extend `use_quiz.test.ts` no-selection case to assert **no attempt recorded**
    (and thus no `elapsed_ms`) after the timing change (FR-1).
  - Confirm existing non-zero-`elapsedMs`→recorded-attempt cases stay green.
- **Pass/fail:** timing change creates zero new rows on the no-selection path.

### T5 — Decision record + gate
- **Depends on:** T1–T4.
- **Change:** append a 2–4 line entry to `docs/adr/decisions.md` (monotonic
  `performance.now()`; wall-clock, not active-focus; reducer-held start).
- **Verify:** run `make check` and frontend vitest; paste **actual** output
  (counts, not a summary). Confirm `tests/architecture/` + frontend layering green.

---

## Stage 4 — Analyze (pre-implementation cross-check)

- **Spec ↔ tasks coverage:** FR-1→T4, FR-2→T2, FR-3→T1, FR-4→T3, FR-5→T2,
  FR-6→T1. Every FR has ≥1 red-first test. ✅ no zero-coverage requirement.
- **Grounding (all confirmed):** `page.tsx:121` literal `0` present;
  `use_quiz.ts:113/146` args carry `elapsedMs`→`elapsed_ms`; wire
  `engine_entities.ts:144` + both schema dialects define the column; reducer
  `AnsweringPhase`/`item_loaded` are the correct seam and have no timing today.
- **Invariants:** F-R1 held (logic in reducer/helper, page is glue); no SDK import;
  no layering crossing; no trust/kernel/dependency/graph-node/abstraction trigger ⇒
  **no ADR** (decisions.md entry only). ✅
- **Non-goals fenced:** Test-mode persistence and coach-thread durability are
  consent-gated (spec §2.1); no task touches them. ✅
- **Baseline before coding:** `make check` + `pytest tests/architecture/ -q` green.

**Advance →** `sdd-implement` (execute T1→T5, red/green per task).

---

## Stage 5 — Replan / sprint board (2026-07-03)

**Trigger:** (c) a review finding (D0 code review, design/style pass). The FD2
warning it raised is **already fixed**; this replan routes the residual "not
checked" gaps + the outstanding gate. No scope change ⇒ no backward spec edit
(spec §2.1 non-goals untouched; the fix stays inside the existing FR-2/FR-5 contract).

### Done since the original board (do NOT re-do)

- **T1, T2, T4** — landed red/green. Reducer `presentedAt`, `elapsedMsFrom`,
  no-selection-no-row regression + the `elapsed_ms`-reaches-attempt plumbing test.
- **FD2 fix (review finding, resolved).** The reducer default was `?? 0`, which
  laundered a missing clock into a **finite** `0`; `elapsedMsFrom(0, now)` then
  returns `now` — a fabricated multi-million-ms elapsed (the exact D0 bug class).
  Fixed with `?? Number.NaN` so the helper's `!Number.isFinite` guard is the single
  authority on "no start captured." Rejected the reviewer's two alternatives:
  `=== 0` in the guard (overloads a legitimate 0-ms reading as "missing") and
  required-field (churns ~10 test call sites, spreads the magic value). Locked by a
  **red-first contract-guard test** (proven to fail on the old `?? 0`:
  `expected true to be false`). `decisions.md` updated. Quiz suite 50/50, touched
  files typecheck clean.

### Remaining tasks

#### T3-b — Page-wiring behavioral assertion (the review's open "not checked" gap)
- **Origin:** T3's original board text called for a "page/integration test with
  stubbed `performance.now`" asserting `submit` receives `elapsed_ms = stop − start`.
  During implementation T3 was landed as **typecheck-clean-only**; the runtime
  assertion was deferred. The reviewer named this honestly as a gap.
- **Grounding (checked, not assumed):** an RTL test on `QuizPage` must mock
  `useRouter` (next/navigation), `useEngine` (via `useQuiz`), `useSurface`, and
  `buildBrowserRuntimeClient`, then drive the async effect chain
  (openSession → openItem → answering → select → submit) with a stubbed
  `performance.now`, to assert the injected `submit` spy is called with a non-zero
  `elapsedMs`. No page-level RTL test exists under `app/(coach)/` today (no precedent
  harness to extend).
- **Fix-vs-justify — RECOMMEND JUSTIFY (with a thin belt-and-suspenders option):**
  the timing *logic* is already covered deterministically at two layers
  (`elapsedMsFrom` unit tests FR-2/4/5 + the reducer contract-guard). The page is
  F-R1 glue: its only new behavior is `elapsedMsFrom(state.presentedAt, performance.now())`
  forwarded to `submit`, which is typechecked. A full RTL mock-fest asserts *wiring*,
  not logic, at high mock cost and low marginal coverage — the classic low-ROI
  glue test §20 warns against.
  - **Justify path (default):** one PR/`decisions.md` line — "page is F-R1 glue;
    the elapsed contract is locked by unit + reducer tests; page wiring is
    typechecked, not RTL-asserted (low-ROI mock-fest deliberately skipped)."
  - **Belt option (only if belt-and-suspenders wanted):** extract the two-line
    submit-time computation is NOT worth it; instead add ONE focused RTL test that
    stubs the four hooks + `performance.now` and asserts `submit` got a non-zero
    `elapsedMs`. Ship only if the reviewer/human wants gate-grade wiring proof.
- **Pass/fail:** either a landed RTL assertion OR a recorded justify line. Not both.
- **RESOLVED 2026-07-03 (human-approved JUSTIFY):** justify line recorded in
  `docs/adr/decisions.md`. No RTL test written — the elapsed contract is locked at
  the unit + reducer layers; page wiring is glue (F-R1), typechecked, low-ROI to
  RTL-mock. Gap closed by conscious decision, not by test.

#### T5 — Decision record + FULL gate (re-run after the FD2 fix)
- **Status:** `decisions.md` entry done (incl. the FD2 NaN-sentinel rationale).
  The gate was green *before* the FD2 fix; it must be **re-run after** it.
- **Verify:** `make check` (D1/D4 authoritative gate) + frontend vitest; paste
  **actual** counts. The fix is TS-only (reducer default + one test + JSDoc + a doc
  line) ⇒ no expected Python impact, but the gate confirms rather than assumes.
- **Pass/fail:** `make check` EXIT 0; frontend vitest green; counts pasted.

### Routing (per the skill)

Only priorities/decomposition changed — **no spec/scope change**. Route → back to
**sdd-implement** with this order: **T3-b decision first** (fix or justify), then
**T5 gate re-run**. Human gate: approve the T3-b fix-vs-justify recommendation
(justify is recommended) before executing.
