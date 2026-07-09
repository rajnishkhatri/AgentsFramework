# Plan — S5: `/learn` quiz done-state + retake

**Status:** Plan (Stage 2) — **Gate 2 approved 2026-07-09** (OQ-1 = unconditional relabel) → Tasks next — 2026-07-09
**Spec:** [preact-quiz-done-state.spec.md](preact-quiz-done-state.spec.md) (Specified + Clarified, **Gate 1 approved 2026-07-09**)
**Owner:** Rajnish (PreAct English Coach)
**Constitution:** root `AGENTS.md` (8 invariants) + `frontend/AGENTS.md` Frontend Ring (F-R1…F-R9)

---

## 0. What this plan commits to

S5 is a **milestone message + two relabelled actions on the existing feedback screen**, driven
by one new boolean derived in the translator that already owns the progress-bar math. **No new
screen, no new reducer phase, no engine/scheduler call, no wire/schema change, no ADR.** Grounded
against the current tree (line numbers below are live as of 2026-07-09).

The decision the clarified spec deferred to plan time — *helper vs. VM flag* (spec §4) — is
resolved: **extend `quiz_progress_vm` with a `complete` flag**, not a standalone helper. Rationale
in §3.

---

## 1. Grounding — every touchpoint verified against the working tree

| # | Fact the plan relies on | File:line (current) | Verified |
|---|---|---|---|
| G1 | The reviewing branch builds `content`; the two action buttons live there as inline JSX | `app/(coach)/learn/quiz/page.tsx:225–247` | ✓ |
| G2 | "Next question →" button: `data-testid="quiz-next"`, `onClick={() => dispatch({ type: "next" })}` | `page.tsx:229–236` | ✓ |
| G3 | "Finish & see summary" button: `data-testid="quiz-finish"`, `onClick={onFinish}` | `page.tsx:237–244` | ✓ |
| G4 | `FeedbackView` is rendered as a sibling in `content`; it takes **only** `vm` — **no children/slot** | `page.tsx:227`; `components/feedback/FeedbackView.tsx:85` | ✓ |
| G5 | `toQuizProgressVM(state.score.total, state.phase, session?.target_count ?? null)` already called | `page.tsx:255–259` | ✓ |
| G6 | `<QuizProgress vm={progressVm} />` rendered in `framed` wrapper | `page.tsx:262` | ✓ |
| G7 | `session` state holds `target_count`; read as `session?.target_count ?? null` | `page.tsx:76, 258` | ✓ |
| G8 | `state.score.total` rides every non-early-return phase (incl. reviewing) | `quiz_screen_reducer.ts:53, 171–174` | ✓ |
| G9 | `onFinish` = `dispatch(finish)` → `closeSession(...)` → `router.push(summary?session=)` | `page.tsx:160–177` | ✓ |
| G10 | The loop never self-terminates at target; `next` = `reviewing → loading`; `done` only via `finish` | `quiz_screen_reducer.ts:177–185` | ✓ |
| G11 | Over-run VM already drops the denominator past target (S4) | `quiz_progress_vm.ts:57` | ✓ |
| G12 | Summary already IS the retake surface (link back to `/learn/quiz` + `?focus=` drill) | `components/summary/SummaryView.tsx:70, 78` | ✓ |
| G13 | VM test style = plain `describe`/`it`, **failure/edge-first**, not `describe.each` | `quiz_progress_vm.test.ts:15, 60` | ✓ |

**Consequence:** the milestone banner renders as a **sibling above `<FeedbackView>` inside the page's
`content` wrapper** (G4 — FeedbackView has no slot, and the clarified spec Q1 places the banner
"above the feedback"). FeedbackView is **not touched**. The "reached" signal is a pure function of
`(state.score.total, session.target_count)` — both already in hand at the `toQuizProgressVM` call
site (G5), so no new data threading.

---

## 2. Architecture placement (Frontend Ring)

```
 quiz_progress_vm.ts   (translator, PURE)   ← add `complete: boolean` to QuizProgressVM
        │  toQuizProgressVM(gradedTotal, phase, targetCount) → { …, complete }
        ▼
 page.tsx  (reviewing branch, presentational)
        ├─ if progressVm.complete  → render <QuizDoneBanner targetCount={…} />  (sibling ABOVE FeedbackView)
        ├─ relabel quiz-next  : "Next question →"        → "Keep practising"
        └─ relabel quiz-finish: "Finish & see summary"   → "See summary"
        ▼
 QuizDoneBanner.tsx  (NEW presentational component, no logic)  ← renders the milestone copy
```

- **F-R1 (no domain logic in components):** the "reached?" threshold + count math live in the
  translator; `page.tsx` and `QuizDoneBanner` only render the result. ✓
- **F-R9 / FR-13 (read-only serve path):** no scheduler/engine call; the banner reads the tally +
  target already in state. ✓
- **U-family (component conventions):** banner uses semantic tokens + `text-on-*` (dark/light AA,
  per [[preact-learn-a11y-phase4]]), real text (not colour/icon alone, WCAG 2.2 AA), all strings via
  `t()` (§13). No `useEffect`, no SDK import.

---

## 3. The deferred decision: **VM flag, not a standalone helper**

Spec §4 offered: (a) a standalone `isSessionComplete(gradedTotal, targetCount)` helper, OR (b) a
`complete` flag on `quiz_progress_vm`. **Choose (b).**

- **Zero new wiring.** The page already calls `toQuizProgressVM(state.score.total, state.phase,
  session?.target_count ?? null)` at `page.tsx:255–259`. A `complete` field on the returned VM is
  read as `progressVm.complete` — no new import, no second call, no extra state read. A standalone
  helper would need its own import + call site duplicating the same two inputs.
- **Single owner of the count math (F-R1 / DRY).** `quiz_progress_vm` already owns `bounded`,
  `position`, `total`, `fraction` from `(gradedTotal, targetCount)`. "reached" is the same family of
  derivation over the same inputs; splitting it into a second module fragments the spine S4 built.
- **`complete` is defined precisely and reuses existing internals:**
  `complete = bounded && position >= targetCount` where `position`/`bounded` are the values the VM
  already computes (`quiz_progress_vm.ts:48–54`). This satisfies FR-4 (`≥`, not `==`, so a resumed
  already-past-target session still surfaces it — spec §6) and FR-1 (endless ⇒ `bounded` false ⇒
  `complete` false).
  - **Numerator caveat (must-encode):** `position` is `gradedTotal` while `reviewing`/`loading`/`done`
    but `gradedTotal + 1` while `answering` (`quiz_progress_vm.ts:48–51`). The done-state is shown
    **only on the `reviewing` screen** (spec FR-4, clarify Q1), where `position === gradedTotal`, so
    `complete` is exact there. To keep the flag honest for any caller and avoid a false-positive one
    question early during `answering` (where `position = gradedTotal + 1`), compute `complete`
    against the **graded count**, not the display position:
    `complete = bounded && gradedTotal >= targetCount`. This is `≥` on the true graded tally (FR-4),
    independent of the answering/reviewing display offset. The page still only *acts* on it in the
    reviewing branch, but the flag itself is phase-robust.
- **G1-gate (new-abstraction):** a boolean field on an existing VM is not a load-bearing new
  abstraction — no ADR, no `docs/adr/decisions.md` entry required. The **new component**
  `QuizDoneBanner.tsx` is presentational only (renders copy from a prop); it introduces no seam,
  matching the existing `QuizProgress.tsx` presentational precedent. If a reviewer deems the new
  component worth a line, a 2-line note in `docs/adr/decisions.md` at implement time covers it — but
  no ADR trigger (`⚠️ Ask first`) fires (no new dep, no wire type, no reducer phase, no service).

---

## 4. File-level touchpoints

### 4.1 `frontend/lib/translators/quiz_progress_vm.ts` — EDIT (add `complete`)
- Add `readonly complete: boolean;` to `QuizProgressVM` (after `bounded`, `:37`).
- In `toQuizProgressVM`, compute `const complete = bounded && gradedTotal >= targetCount;` (uses the
  raw `gradedTotal` arg, not `position` — see §3 caveat) and include it in the returned object.
- JSDoc: one line documenting `complete` = "bounded session whose graded tally has reached the
  target (FR-4, `≥`); false when endless (FR-1)". Keeps the existing numerator/denominator docblock.
- **Imports unchanged** (still `wire/` only; no I/O, no React). Pure. ✓ Rule T1.

### 4.2 `frontend/lib/translators/quiz_progress_vm.test.ts` — EDIT (add cases, RED first)
- Mirror the existing plain `describe`/`it` **failure/edge-first** style (G13 — not `describe.each`).
- New `it` cases under the "failure/edge first" describe:
  - FR-1: endless (`targetCount` null) → `complete === false` (even at high gradedTotal).
  - FR-4 boundary: `gradedTotal === targetCount` → `complete === true`; `gradedTotal === targetCount - 1`
    → `complete === false`.
  - edge: `gradedTotal > targetCount` (over-run) → still `complete === true` (`≥`).
  - edge: `targetCount === 1`, `gradedTotal === 1` → `complete === true` (no off-by-one to "never").
  - FR-8 (purity): `complete` is a function of `(gradedTotal, targetCount)` only — assert it does not
    depend on `phase` (e.g. `answering` vs `reviewing` at the same `gradedTotal ≥ target` both `true`),
    proving the §3 caveat fix.

### 4.3 `frontend/components/quiz/QuizDoneBanner.tsx` — NEW (presentational)
- Props: `{ targetCount: number }`. No children, no logic, no `useEffect`, no SDK import.
- Renders the milestone copy (spec Q5): `🎉 You've completed your {targetCount}-question session!`
  as **real text** (WCAG 2.2 AA), with `{targetCount}` interpolated via a template literal (never
  hardcoded 30, FR-5).
- **String handling — INLINE literal, NOT `t()`.** *(Analyze correction, 2026-07-09.)* The repo has
  **no i18n helper**: `lib/i18n.ts` does not exist, and `QuizProgress.tsx:15` documents "this
  codebase has no i18n helper yet (QuizView/FeedbackView use inline literals); matching the
  surrounding code is correct here." The sibling presentational components (`QuizProgress`,
  `QuizView`, `FeedbackView`) all use inline literals. So `QuizDoneBanner` uses an inline template
  literal too (`` `🎉 You've completed your ${targetCount}-question session!` ``), matching the
  surrounding code. The style-guide §13 `t()` rule is aspirational and not yet wired; introducing a
  `t()` import would invent an API the repo doesn't have. (Carry the same one-line "no `t()` yet"
  JSDoc note QuizProgress uses, so the choice is self-documenting.)
- Styling: semantic tokens + `text-on-*` for AA in light AND dark (per [[preact-learn-a11y-phase4]]),
  `data-testid="quiz-done-banner"` for the E2E walk. shadcn/`cn()` if a card wrapper is used.
- Follows the `QuizProgress.tsx` presentational precedent (VM/prop in → JSX out).

### 4.4 `frontend/components/quiz/QuizDoneBanner.test.tsx` — NEW (component, RED first)
- FR-5: renders the milestone message as text; the **count is present and interpolated** (assert
  `targetCount=7` renders "7", never "30").
- FR-5: message is real text content (queryable by role/text), not colour/icon-only.

### 4.5 `frontend/app/(coach)/learn/quiz/page.tsx` — EDIT (reviewing branch only)
- In the reviewing branch `content` (`:225–247`), **above** `<FeedbackView .../>` (`:227`), inside
  the existing `<div className="mx-auto flex max-w-[760px] flex-col gap-6">` column (`:226` —
  confirmed; the banner inherits its `gap-6` spacing automatically, no extra wrapper):
  `{progressVm.complete ? <QuizDoneBanner targetCount={session?.target_count ?? 0} /> : null}`.
  (Guarded by `complete`, which is false unless bounded, so `target_count` is non-null there; the
  `?? 0` is a type-guard fallback that never renders because `complete` gates it.)
- **Relabel the two existing buttons (FR-5/FR-6/FR-7 — clarify Q1). Only the label text changes; the
  `data-testid`s, handlers, and structure stay identical** (keeps S4/S3 selectors + existing E2E
  green, FR-10):
  - `quiz-next` (`:235`): `Next question →` → **`Keep practising`** (`onClick` stays
    `dispatch({ type: "next" })` → same session, tally preserved, over-run per S4 — FR-7).
  - `quiz-finish` (`:243`): `Finish &amp; see summary` → **`See summary`** (`onClick` stays
    `onFinish` → same close+route, Summary never re-tallies — FR-6/G1).
  - *Note:* labels relabel **unconditionally** (both before and after target). The clarified decision
    (Q1) relabels the buttons on the last feedback; keeping them relabelled for every reviewing screen
    is simpler and non-regressive (the buttons do the same thing throughout). If the spec intends the
    OLD labels pre-target and NEW labels only at/after target, that is a conditional label — **flag for
    Gate 2** (see §7 open question OQ-1). Default assumed here: unconditional relabel.
- Import `QuizDoneBanner` at top of `page.tsx`. `useEffect`-free; no new state.
- **No change** to `onFinish`, `toQuizProgressVM` call, `<QuizProgress>`, the reducer, or FeedbackView.

### 4.6 `frontend/e2e/learn/quiz-done-state.spec.ts` — NEW (Playwright `learn-e2e`, on-demand)
- Walk a bounded session to the target (target=30 by seed floor, or seed a small `target_count` via
  the E2E seed hook to keep the walk short — confirm the hook supports `target_count` at implement;
  fallback = walk 30).
- Assert at boundary: `quiz-done-banner` visible on the reviewing screen; buttons read
  "Keep practising" / "See summary"; **NO auto-navigation** (still on `/learn/quiz`) — FR-3.
- "Keep practising" → same session continues, bar in over-run (S4: true position, denominator
  dropped) — FR-7.
- "See summary" → routes to Summary with the stored score — FR-6.

---

## 5. What is explicitly NOT touched (regression fence, FR-10)

- `quiz_screen_reducer.ts` — **no new phase, no new action.** `done` still reached only via `finish`.
- `use_quiz.ts`, scheduler, `SessionRepo`, S3 no-repeat seam, `target_count` field — untouched.
- `quiz_progress_vm.ts` over-run math (`total`, `fraction`, `bounded`, `position`) — unchanged; only
  an additive `complete` field.
- `FeedbackView.tsx` — untouched (banner is a sibling, not a child).
- `QuizProgress.tsx` — untouched (still `vm={progressVm}`; it ignores the new field).
- Backend / Python — zero change. No wire event, no `__python_schema_baseline__` (engine wire is
  frontend-only, [[preact-s3-bounded-session-spec]]).

---

## 6. Migration / sequencing

No data migration. Pure additive frontend change. Task order (red-first, failure-paths-first):
1. VM test (4.2, RED) → VM `complete` (4.1, GREEN).
2. Banner test (4.4, RED) → Banner component (4.3, GREEN).
3. Page wiring (4.5) — banner sibling + button relabels.
4. E2E walk (4.6).
5. Full gate (`tsc --noEmit`, `vitest run` new tests, layering arch test) + DoD evidence pasted.

Detailed atomic tasks with 1:1 EARS mapping → **Stage 3 (`docs/plan/preact-quiz-done-state.tasks.md`)**,
after Gate 2.

---

## 7. Constitution / ADR check + open question for Gate 2

- **ADR triggers (`⚠️ Ask first`):** none. No new dep, no trust-kernel type, no `react_loop.py` node,
  no new horizontal service, no new load-bearing abstraction. `QuizDoneBanner` is presentational
  (mirrors `QuizProgress`); `complete` is an additive VM field. → **No ADR.** (If a reviewer wants the
  new component recorded, a 2-line `docs/adr/decisions.md` entry at implement time suffices.)
- **Invariants:** F-R1 (logic in translator), F-R9/FR-13 (read-only), U-family (a11y/tokens/`t()`),
  Rule T1 (pure translator) — all preserved (§2).
- **`make check` / arch baseline:** `cd frontend && ./node_modules/.bin/tsc --noEmit -p tsconfig.json`
  + the frontend layering arch test must be green before implement (Stage 4).

**OQ-1 — RESOLVED at Gate 2 (2026-07-09): UNCONDITIONAL relabel.** The two buttons read
"Keep practising" / "See summary" on **every** reviewing screen (before and after target); the
milestone banner is the sole "you've arrived" signal. No `complete`-gated label branch — labels are
static text. This is the plan's §4.5 default; no change to the touchpoints. (Consequence for tests:
the E2E asserts the labels are present on a pre-target screen too, not only at the boundary.)

---

## 8. Gate 2

Approve this plan (and answer **OQ-1**) → I proceed to **Stage 3 (checklist + atomic tasks)**, then
Stage 4 (analyze + baseline), then implement is a **separate** go-ahead (Stage 6, sdd-implement).
Tell me to adjust the placement, the VM-flag decision, or OQ-1 and I revise before tasks.
