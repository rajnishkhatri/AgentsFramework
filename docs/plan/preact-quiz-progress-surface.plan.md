# Plan — S4 · Visible session-progress surface (`/learn` quiz)

**Derived from:** [`preact-quiz-progress-surface.spec.md`](preact-quiz-progress-surface.spec.md) (Status Draft, clarify resolved 2026-07-08) · **Constitution:** frontend `AGENTS.md` (F-R1..F-R9) + root `AGENTS.md` 8 invariants.

This is the *what-goes-where*; the spec is the *what*. No ADR is expected (see §ADR check) — if planning surfaced an ⚠️ trigger it would be raised here first.

---

## 0. Resolved open item (reviewing-phase numerator)

The one choice left open at the spec gate — what the counter shows on the **Feedback
(reviewing)** screen — is resolved to the **honest default**: reviewing shows the
position of the **item you just answered** (`gradedTotal`), and the counter advances to
`gradedTotal + 1` only when the next item loads (`answering`). This is decision #1's
natural consequence; no re-open needed. Encoded in the translator's `phase` branch.

## 1. Architecture (F-R1 split)

Three pieces, mirroring the existing `quiz_item_vm` (translator) + `QuizView`
(component) split already used one file over:

```
 state.score.total ─┐
 state.phase        ├─► [translator]  toQuizProgressVM(gradedTotal, phase, targetCount)
 session.target_count┘        │  PURE, wire-only, no React            (FR-8, F-R1)
                              ▼
                       QuizProgressVM { position, total, fraction, bounded }
                              │
                              ▼
                       [component]  <QuizProgress vm={…} />           (presentational)
                              │  renders counter text + ARIA progressbar (FR-7)
                              ▼
                       page frame: rendered ABOVE `content` in BOTH return paths
```

- **No engine call, no repo, no scheduler, no write** (FR-9). The page already holds
  `session` (Effect 1) and `state.score` (reducer) — the translator is fed from those.
- **F-R1 holds:** all counting/clamp math is in the pure translator; `<QuizProgress>` is
  presentational and holds no logic (mirrors `QuizView` ← `quiz_item_vm`).

## 2. File-level touchpoints

| # | File | Change | Rule |
|---|------|--------|------|
| **T1** | `frontend/lib/translators/quiz_progress_vm.ts` **(new)** | Pure `toQuizProgressVM(gradedTotal: number, phase: QuizScreenPhase, targetCount: number \| null): QuizProgressVM`. Exports the `QuizProgressVM` interface. Header comment in house style ("Imports `wire/` only. No I/O, no React, no SDK."). | T1/FR-8, F-R1 |
| **T2** | `frontend/lib/translators/quiz_progress_vm.test.ts` **(new)** | Table-driven L1 tests, **failure paths first** (null target, over-run, first-item, loading-carry) then happy path. No mocks. | §20 TAP-4 |
| **T3** | `frontend/components/quiz/QuizProgress.tsx` **(new)** | Presentational component: `{ vm: QuizProgressVM }`. Renders counter text (inline literal `"Question {position} of {total}"` or `"Question {position}"` when `total==null` — **no `t()`; this codebase has none**, see §Analyze) + a progressbar (`role="progressbar"`, `aria-valuenow/min/max`, `aria-valuetext`) with inline fill width from `vm.fraction`. `data-testid="quiz-progress"`; `cn()` for static classes (§13). | U-family, FR-5/FR-7 |
| **T4** | `frontend/components/quiz/QuizProgress.test.tsx` **(new)** | SSR structural tests (repo's `renderToStaticMarkup` + JSDOM convention, twin of `QuizView.test.tsx`): progressbar role + aria attrs present (FR-7); bar fill width matches fraction (FR-5); counter drops "/ M" when `total` null (FR-1/FR-2). | §20, FR-5/7 |
| **T5** | `frontend/app/(coach)/learn/quiz/page.tsx` | Compute `const progressVm = toQuizProgressVM(state.score.total, state.phase, session?.target_count ?? null)` in the `answering`/`reviewing` branch; render `<QuizProgress vm={progressVm} />` **above** `content` in a small frame that wraps **both** return paths (plain + iPad-split). ~6–10 lines, thin glue only (F-R1: no logic here). | B/F-R1 |
| **T6** | `frontend/e2e/learn/quiz-progress.spec.ts` **(new, on-demand)** | L4 `learn-e2e`: open `/learn/quiz`, assert `[data-testid="quiz-progress"]` reads "Question 1 of 30"; answer+Next; assert it reads "Question 2 of 30". Mirrors `quiz-rotation.spec.ts` conventions. | FR-1/3/5 live |

**Export note (T1):** `QuizScreenState`'s phase is a union of the `phase` string
literals; the translator needs just the tag. Export a `QuizScreenPhase =
QuizScreenState["phase"]` (or accept the four string literals) from
`quiz_screen_reducer.ts` **or** define the narrow input type in the translator — decide
in impl; do **not** import the reducer into the translator if it drags React-adjacent
types (keep the translator `wire/`-only per T1). Simplest: translator takes
`phase: "loading" | "answering" | "reviewing" | "done"` as a plain string-union param.

## 3. The translator logic (the load-bearing 8 lines)

Pin the exact math so impl + tests agree (this is the whole feature):

```
position =
  phase === "answering" ? gradedTotal + 1     // FR-3/FR-4: you're ON the next one
  : phase === "reviewing" ? gradedTotal        // §0: the one you just graded
  : gradedTotal                                // loading/done: carry (FR-6)
                                              //   (clamped >= 1 so first render is 1, not 0)

bounded  = targetCount != null                                 // FR-1
fraction = bounded ? clamp(position / targetCount, 0, 1) : 0   // FR-5 (clamp handles over-run FR-2)
total    = (bounded && position <= targetCount) ? targetCount  // show "/ M"…
         : null                                                // …dropped when endless OR over-run (FR-1/FR-2, §2.2 Q4)
```

`position` floored at `1` handles the `gradedTotal === 0` first-item case for the
`answering` branch it already is (`0+1`); the `reviewing`/`loading` branches guard the
`Math.max(1, …)`. Confirm in T2 that `reviewing` at `gradedTotal===0` can't happen
(the reducer only reaches `reviewing` via a graded `submitted`, so `total>=1` there) —
but clamp defensively anyway.

## 4. Test / verification strategy (red first)

Per-task red→green (sdd-implement): write T2/T4 rows, **watch them fail**, then T1/T3.

- **T1/T2 (translator, L1):** the failure rows (null target, over-run past M, first-item,
  loading-carry) are authored and seen red before the translator body exists. All in
  `make check` (frontend vitest).
- **T3/T4 (component, L1 SSR):** aria + fill-width + counter-text-drop assertions.
- **Arch (FR-8/FR-9 structural):** the frontend layering test already forbids a
  component importing adapters and a translator importing React/SDK — no new arch test
  needed; the split *is* the enforcement. Confirm `test_frontend_layering.test.ts` stays green.
- **Regression (FR-10):** run the touched S3/S3.1 suites + `quiz_screen_reducer.test.ts`
  unchanged-green (we edit neither the reducer nor the serving path).
- **Gate:** `frontend` `tsc --noEmit` = 0; `pytest tests/architecture/ -q` green
  (constitution, though no Python changes).
- **Live (T6, on-demand):** Playwright read of the counter advancing.

## 5. Migration steps

None. No schema, no DB, no wire-baseline (`target_count` already shipped in S3;
`QuizProgressVM` is frontend-only with no Python mirror → no `__python_schema_baseline__`
entry, same as `wire/ui_runtime_events.ts` precedent). Additive UI; reversible by
deleting T1/T3 and the T5 glue.

## 6. ADR check (⚠️ Ask-first triggers) — **none fire**

Walked the root `AGENTS.md` ⚠️ list against this plan:

| Trigger | Fires? | Why not |
|---|---|---|
| New `pyproject.toml` dependency | ❌ | No dep; frontend-only, no package added |
| Trust-kernel type change (`trust/models.py`) | ❌ | No Python touched |
| New graph node (`orchestration/react_loop.py`) | ❌ | No orchestration touched |
| New horizontal service | ❌ | No service |
| **New abstraction / deviation from an invariant (G1)** | ❌ | A component + a pure VM translator is the **established** Frontend-Ring pattern (`QuizView`←`quiz_item_vm`, `FeedbackView`←`feedback_vm`, `SessionSummary`←`session_summary_vm`) — S4 adds one more instance of a shipped pattern, not a new abstraction. No new port, no new sub-package (Rule F2). |
| Persisted wire-type change | ❌ | `target_count` already exists; `QuizProgressVM` never crosses the wire |

**Conclusion: no ADR.** This is a routine, in-pattern Frontend-Ring UI addition. The
`stop_adr_reminder.py` hook should stay quiet (no ADR seam path touched); if it fires
spuriously, the waiver rationale is "in-pattern VM+component, G1 not triggered — no new
abstraction." Recorded here rather than a stray `docs/adr/decisions.md` line since the
spec+plan already carry it. *(If impl deviates — e.g. we find we need a new port to
reach `target_count` — stop and raise ADR-0025.)*

## 7. Definition of Done (inherits spec §9)

- [ ] T1–T5 landed; T2/T4 seen-red-first; T6 optional.
- [ ] `frontend` `tsc --noEmit` 0; touched vitest green; `test_frontend_layering.test.ts` green.
- [ ] `pytest tests/architecture/ -q` green.
- [ ] Live `/learn/quiz` shows "Question 1 of 30" → advances on Next (evidence pasted).
- [ ] No ADR needed (this plan §6 is the record); no `decisions.md` line required.
