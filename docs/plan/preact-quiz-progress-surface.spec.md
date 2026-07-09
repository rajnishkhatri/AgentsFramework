# Spec — S4 · Visible session-progress surface for the PreAct `/learn` quiz

**Status:** Implemented (Stage 6, red/green per task) — 2026-07-08 · §10 evidence
**Owner:** Rajnish Khatri
**Related:** [S3 target_count spec](preact-quiz-target-count.spec.md) (the data spine this reads) · [ADR-0023](../adr/0023-quiz-bounded-session-target-count.md) · builds the "Question N / M top bar + progress bar" S3's **FR-14** explicitly deferred to S4 · sibling [S3.1 rotation spec](preact-quiz-skill-rotation.spec.md)

---

## 1. Goal

Show the learner **how far through the quiz session they are** — a "Question N of M"
counter plus a progress bar — so a bounded 30-question session stops feeling like the
infinite loop it currently looks like. For the PreAct `/learn` learner ("Maya").

The number already exists (`QuizSession.target_count`, shipped in S3) and is **stored
but never rendered**. S4 renders it. No engine, schema, or scheduler change.

## 2. Context

S3 shipped `target_count` (a nullable per-session length; per-mode default **30**) and
the within-session served-ids spine, then **explicitly reserved the visible bar for S4**
([target-count spec FR-14](preact-quiz-target-count.spec.md): *"THE SYSTEM SHALL NOT add
the 'Question N / M' bar (S4) …"*). The brainstorm that started this line
([[preact-ui-gap-brainstorm]]) named the root gap: the quiz is an **infinite loop by
design** with **no progress / count / done-prompt**, so the learner has no sense of
session length or position.

S4 closes the *progress* half of that gap (S5 closes the *done-state + retake* half).
The two data signals S4 reads both already exist in the running page:

- `session.target_count` — the denominator **M** (nullable; `null` = endless).
- `quiz_screen_reducer`'s `SessionTally.total` — graded-so-far, incremented once per
  submit ([quiz_screen_reducer.ts:172-173](../../frontend/components/quiz/quiz_screen_reducer.ts)),
  carried across `next`/`finish`. This is the basis for the current-position **N**.

**Frontend Ring shape (F-R1):** progress is a **pure view-model** computed by a
translator from `(total, phase, target_count)`, rendered by a new **presentational**
component. No domain logic in the component; the page passes props.

## 3. Functional requirements (EARS)

Failure / edge paths first (TAP-4).

- **FR-1 (endless session — no denominator).** IF `target_count` is `null` THEN THE
  SYSTEM SHALL render the position **without** a total and **without** a bounded bar
  (e.g. "Question 3" and an indeterminate/hidden bar) — never "3 of null", "3 of 0", or
  a divide-by-zero.
- **FR-2 (over-run past the target).** IF the served count exceeds `target_count`
  (a session continues past its nominal length — allowed today) THEN THE SYSTEM SHALL
  clamp the **bar** at 100% and show the **true position with the denominator dropped**
  (e.g. "Question 32", not "32 of 30" and not a frozen "30 of 30") — the fixed target
  has stopped being a meaningful denominator past the target. Never a bar wider than
  full, never a negative remainder. _(§2.2 Q4.)_
- **FR-3 (first item, nothing graded yet).** WHEN the first item is presented and no
  answer has been graded THE SYSTEM SHALL show position **1** of M (1-based), not 0 —
  the learner is *on* question 1.
- **FR-4 (position advances on grade, not on select).** WHEN an answer is graded
  (`submitted` with a verdict) THE SYSTEM SHALL advance the displayed position to the
  next question's index; selecting or opening a hint SHALL NOT change it.
- **FR-5 (bar reflects position/target).** WHILE a bounded session is in progress THE
  SYSTEM SHALL render a progress bar whose fill = `clamp(position / target_count, 0, 1)`.
- **FR-6 (loading has no flicker to a wrong number).** WHILE the phase is `loading`
  (between `next` and the next `item_loaded`) THE SYSTEM SHALL keep the last shown
  position stable (no reset to 1, no jump to 0).
- **FR-7 (accessible progress semantics).** THE SYSTEM SHALL expose the progress with an
  ARIA progressbar role carrying `aria-valuenow` / `aria-valuemin` / `aria-valuemax`
  (or an equivalent labelled text alternative) so a screen reader announces position;
  the counter text SHALL be readable, not conveyed by color alone (WCAG 2.2 AA, §13).
- **FR-8 (pure translator owns the math — F-R1).** THE SYSTEM SHALL compute the
  displayed `{ position, total, fraction, bounded }` in a **pure, React-free translator**
  from `(gradedTotal, phase, targetCount)`; the component SHALL render that VM and hold
  no counting logic.
- **FR-9 (read-only — no engine write).** THE SYSTEM SHALL derive progress purely from
  the in-page reducer tally and the already-open session; it SHALL NOT call the engine,
  the scheduler, or any repo, and SHALL NOT write `skill_state` or mutate the session.
- **FR-10 (backward-compatible; no behavior regressions).** THE SYSTEM SHALL leave the
  serving/no-repeat/rotation behavior (S3 FR-9/10/11, S3.1) and the score tally
  unchanged — S4 is additive UI over existing signals.

## 4. Data model / contracts

**No wire / schema / DB change.** `target_count` already exists on `QuizSession`
([engine_entities.ts:213](../../frontend/lib/wire/engine_entities.ts),
`z.number().int().positive().nullable()`).

**New (frontend-only) view-model** — the translator output shape (name TBD in plan,
e.g. `QuizProgressVM`):

```ts
interface QuizProgressVM {
  readonly position: number;      // 1-based index of the question the learner is on/just did
  readonly total: number | null;  // denominator to DISPLAY: target_count while position<=target;
                                  //   null when endless (target_count null) OR over-run (position>target)
  readonly fraction: number;      // clamp(position / target_count, 0, 1); 0 when target_count is null
  readonly bounded: boolean;      // target_count != null — determinate vs indeterminate bar
}
```

Inputs: `gradedTotal` (`SessionTally.total`), `phase` (`answering → gradedTotal + 1`;
`reviewing → gradedTotal`; `loading`/`done` carry the last), `targetCount`
(`session.target_count`). Note `total` (display denominator) and `bounded`/`fraction`
(bar geometry) diverge on over-run: past the target the **bar stays full** (`bounded`
true, `fraction` clamped to 1) but the **counter drops "/ M"** (`total` → null) — §2.2 Q4.

## 5. Invariants & security boundaries

This is a Frontend-Ring change; the relevant invariants are the **F-R** rules
(STYLE_GUIDE_FRONTEND / frontend `AGENTS.md`), not the Python layer invariants.

- **F-R1 (no domain logic in components).** The counting/clamp math lives in a pure
  translator (FR-8); the component is presentational — **this is the load-bearing
  invariant** and the reason for the translator split.
- **F-R2 (SDK imports only in adapters).** N/A — no SDK touched.
- **Backend Architecture Invariant #2/#3 (trust purity / framework-agnostic):** untouched
  — no Python change.
- **W2 / schema-baseline:** N/A — no `wire/` shape crosses the Python boundary (the
  engine is frontend-only; `target_count` already shipped).
- **Read-only serve-path (S3 FR-13 / S3.1 FR-7):** preserved by FR-9 — progress is a
  *read* of existing state, zero writes.

**No security boundary touched** — no secrets, no auth, no sandbox, no live LLM, no CI
hot-path change.

## 6. Edge cases

- **`target_count = null` (endless).** No denominator, no bounded bar (FR-1). The dev
  seed's default is 30, but an explicit `null` session must not crash.
- **Served count > target_count.** Bank exhaustion or a short target lets the walk pass
  M; bar clamps at 100%, counter may read "32 of 30" (FR-2). Never a >100% bar.
- **`loading` phase between items.** The reducer has no item in `loading`; the progress
  must read from the carried `score` + session, not from the (absent) item, and not
  flicker (FR-6).
- **First render before the session resolves.** `session` is `null` until Effect 1
  completes; progress must render nothing (or a stable placeholder), not "1 of
  undefined".
- **`done` phase (manual Finish).** Position at Finish = graded total; the bar reflects
  final position. (The *visible done-screen* itself is S5 — S4 only ensures the number
  is sane if shown.)
- **No graded answers yet but not the first item?** Not reachable — `total` only grows;
  the only `total = 0` state is question 1 (FR-3).

## 7. Non-functional requirements

- **Determinism:** the translator is a pure function → L1 exact table tests.
- **No latency / cost:** no network, no engine call (FR-9); render-time arithmetic only.
- **No live LLM anywhere** — stays off the CI hot path by construction.
- **Reversibility:** additive UI; removing the component + translator restores today's
  behavior exactly (FR-10).
- **Bundle:** one small presentational component + one pure translator; no new dep.

## 8. Test plan

Failure-path tests first. All L1 (pure translator) + L1 component SSR (repo's
`renderToStaticMarkup` + JSDOM convention, per `QuizView.test.tsx`); optionally one L4
Playwright read of the rendered counter/bar on the live `/learn/quiz`.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `quiz_progress_vm.test.ts::null target → total null, bounded false, fraction 0` | L1 | yes (frontend vitest) |
| FR-2 | `quiz_progress_vm.test.ts::position > target → fraction clamps to 1` | L1 | yes |
| FR-3 | `quiz_progress_vm.test.ts::gradedTotal 0 while answering → position 1` | L1 | yes |
| FR-4 | `quiz_progress_vm.test.ts::position = gradedTotal+1 answering, = index reviewing` | L1 | yes |
| FR-5 | `QuizProgress.test.tsx::bar fill width matches fraction` | L1 (SSR) | yes |
| FR-6 | `quiz_progress_vm.test.ts::loading carries last position (no reset)` | L1 | yes |
| FR-7 | `QuizProgress.test.tsx::progressbar role + aria-valuenow/min/max present` | L1 (SSR) | yes |
| FR-8 | (structural) translator is pure — no React/adapter import; asserted by frontend layering test + the fact tests need no mocks | L1 / arch | yes |
| FR-9 | (structural) component/translator import graph: no engine/repo/scheduler import | arch | yes |
| FR-10 | existing S3/S3.1 suites stay green (no edit to serving/reducer tally) | L1 | yes |
| FR-1/3/5 (live) | `e2e/learn/quiz-progress.spec.ts::counter reads "1 of 30" then advances` | L4 | on-demand |

## 9. Definition of Done

- [ ] All FRs implemented; each has a passing test that was **seen to fail first**
      (red/green — paste the failing output, not a summary).
- [ ] `frontend` `tsc --noEmit` → 0 errors; touched vitest suites green.
- [ ] Frontend layering / port-conformance arch tests green (F-R1 holds: no domain
      logic in the component; translator pure).
- [ ] `pytest tests/architecture/ -q` green (no Python touched, but the constitution
      gate must stay green).
- [ ] ADR appended **iff** an ⚠️ Ask-first trigger fired (expected: **none** — no new
      dep, no trust type, no new graph node/service, no new abstraction beyond a routine
      component+translator). If the plan surfaces one (e.g. a new port), raise ADR-0025.
- [ ] Live `/learn/quiz` shows "Question 1 of 30" on open and advances on Next
      (screenshot / Playwright evidence pasted).

---

## Premise audit (Stage 1 discipline — verified against the working tree)

| Premise | Status | Evidence |
|---|---|---|
| `target_count` exists on `QuizSession`, nullable | **verified** | [engine_entities.ts:213](../../frontend/lib/wire/engine_entities.ts) `target_count: z.number().int().positive().nullable()` |
| S3 deferred the "Question N / M" bar to S4 (no conflict) | **verified** | [target-count spec FR-14](preact-quiz-target-count.spec.md): *"THE SYSTEM SHALL NOT add the 'Question N / M' bar (S4) …"* |
| A served-so-far count already exists in the running page | **verified** | `SessionTally.total`, incremented once per graded submit ([quiz_screen_reducer.ts:172-173](../../frontend/components/quiz/quiz_screen_reducer.ts)), carried across `next`/`finish` |
| The session object (with `target_count`) is live at render time | **verified** | `const [session, setSession] = useState<QuizSession|null>` in [quiz page](../../frontend/app/(coach)/learn/quiz/page.tsx) (set by Effect 1) |
| No existing progress/counter component to extend | **verified** | grep of `components/` for progress/counter/aria-valuenow found only unrelated `TaskList`/`BucketCard` — S4 adds a new component |
| No engine/schema/scheduler change needed | **verified** | both signals (`target_count`, `total`) already exist; S4 is pure read + render |
| The `null` (endless) and over-run (>M) cases are reachable | **verified** | `target_count` is nullable by schema; the bank is 171 items and sessions can walk past 30 → over-run is real, not hypothetical (drives FR-1/FR-2) |

**No refuted premises.** The one nuance the clarify pass must pin down (below) is the
exact **numerator semantics** (the +1 while answering vs. reviewing) and how `null`/
over-run render — these are §2.2 clarify items, not refutations.

## §2.2 Clarify — decisions (resolved 2026-07-08, before planning)

Four questions posed, one screen; all answered. Resolutions now bind the FRs above.

1. **Numerator convention → "on the question you're working (1-based)".** N =
   `gradedTotal + 1` while answering; after grading, the reducer increments `total`, so
   the next item's "answering" render is already `gradedTotal + 1` again → the counter
   advances exactly once per graded item. First item = **"Question 1 of 30"**. (FR-3/FR-4.)
   - *Implication for `reviewing`:* the graded item's position is `gradedTotal` (the item
     you just answered, now counted). The bar and counter during the Feedback screen
     reflect **that** position (the question you just finished), then the next
     "answering" render shows the next position. The translator keys off `phase`:
     `answering → gradedTotal + 1`, `reviewing → gradedTotal`.
2. **Endless (`null`) → position only, no bar.** Show "Question 7", no "/ M", no filled
   (bounded) bar; `bounded=false` may drive a subtle indeterminate stripe or nothing.
   No fabricated denominator. (FR-1.)
3. **Placement → new top bar above the item.** A standalone `<QuizProgress>` rendered
   **above** the phase content on the quiz page — visible in **both** `answering` and
   `reviewing` (Feedback) phases. Its own file → isolated tests, no coupling to
   `QuizView`. (Touchpoints in the plan.)
4. **Over-run → true position, denominator dropped.** Past the target the counter shows
   "Question 32" (no "of 30", not a frozen "30 of 30"); the bar stays clamped at 100%.
   The fixed target is no longer a meaningful denominator once exceeded. (FR-2.)

**Refined VM contract** (supersedes §4's first sketch): `total` is shown **only while
`position ≤ target_count`**; past that (or when `target_count` is `null`) the VM carries
`total: null` so the component renders position-only. So `total: number | null` means
"the denominator to display, or none," folding FR-1 and FR-2 into one rule the component
renders blindly.

---

## 10. Implementation evidence (Stage 6 — red/green per task, 2026-07-08)

All frontend commands from `frontend/` with the local binary. Commit: on branch
`feat/preact-s3-bounded-session` (S1→S3.1 already landed; S4 additive).

**Files added:** `lib/translators/quiz_progress_vm.ts` (+ `.test.ts`),
`components/quiz/QuizProgress.tsx` (+ `.test.tsx`). **Edited:**
`app/(coach)/learn/quiz/page.tsx` (2 imports + ~14 lines glue). **No engine/schema
/scheduler/wire change. No ADR** (plan §6).

### Red-first, per task

- **T-s2 → T-s1 (translator).** T-s2 authored first, run RED:
  `Error: Cannot find module './quiz_progress_vm'` — 1 failed, no tests. After T-s1:
  `Test Files 1 passed · Tests 7 passed`; `tsc --noEmit` exit 0.
- **T-s4 → T-s3 (component).** T-s4 authored first, run RED: 1 failed (import of
  `./QuizProgress` unresolvable). After T-s3: `Test Files 1 passed · Tests 5 passed`;
  `tsc --noEmit` exit 0.

### Full gate (T-sg) — pasted, not summarized

- **S4 suites + reducer regression + layering:** `Test Files 4 passed · Tests 37
  passed` (`quiz_progress_vm` 7 + `QuizProgress` 5 + `quiz_screen_reducer` unchanged +
  `test_frontend_layering` 5 — F-R1/F-R8/F-R9 hold: translator pure, component imports
  no adapter).
- **Broader regression:** `vitest run components/quiz/ lib/translators/` → `Test Files
  24 passed · Tests 253 passed` (no regressions).
- **Type gate:** `tsc --noEmit -p tsconfig.json` → exit 0.
- **Constitution:** `.venv/bin/python -m pytest tests/architecture/ -q` → `181 passed,
  3 skipped` (no Python touched; gate stays green).

### Live verification (real browser, dev preview `/learn/quiz`)

Driven via the preview server; a11y snapshot + scripted walk + screenshot:

- On load: `region "Session progress"` → **"Question 1 of 30"**, `progressbar
  (aria-valuenow=1, aria-valuemax=30)`, fill width **3%** (=1/30) — **FR-3** (position
  1, not 0), **FR-7** (progressbar semantics), placement above the item.
- Scripted 3-item walk (answer A → Submit → Next), progress read at each step:
  | step | counter | fill | aria-valuenow |
  |---|---|---|---|
  | answering #1 | Question 1 of 30 | 3% | 1 |
  | reviewing #1 (feedback) | Question 1 of 30 | 3% | 1 |
  | answering #2 | Question 2 of 30 | 7% | 2 |
  | answering #3 | Question 3 of 30 | 10% | 3 |
  → **FR-4** (advances once per graded item; reviewing shows the item just done, §0),
  **FR-5** (bar grows monotonically), **FR-6** (no reset/flicker across `loading`).
- **Zero console errors** across the walk.

### DoD

- [x] All FRs implemented; T-s2/T-s4 seen RED before their impl.
- [x] `tsc --noEmit` 0; touched vitest green; `test_frontend_layering.test.ts` green.
- [x] `pytest tests/architecture/ -q` green.
- [x] No ADR needed (plan §6 is the record); no `decisions.md` line required.
- [x] Live `/learn/quiz` shows "Question 1 of 30" → advances on Next (snapshot +
      screenshot evidence above).
- [ ] T-s6 live Playwright spec — **deferred** (the preview-driven walk above already
      proves the same behavior end-to-end in a real browser; the `.spec.ts` can be added
      in review if a CI-runnable artifact is wanted).
