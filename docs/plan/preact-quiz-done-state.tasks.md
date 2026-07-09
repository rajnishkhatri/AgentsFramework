# Tasks — S5: `/learn` quiz done-state + retake

**Status:** **ALL TASKS DONE — IMPLEMENTED 2026-07-09** (Stage 6). T-s0…T-sg green; evidence in spec §9.
**Spec:** [preact-quiz-done-state.spec.md](preact-quiz-done-state.spec.md) (Gate 1 ✓)
**Plan:** [preact-quiz-done-state.plan.md](preact-quiz-done-state.plan.md) (Gate 2 ✓, OQ-1 = unconditional relabel)

---

## A. Checklist — "unit tests for English" (is every criterion measurable?)

Each spec criterion, judged for **measurability** (can a red-first test decide pass/fail?). Anything
unmeasurable goes back to the spec. Result: **all measurable** — no spec bounce.

| Criterion | Measurable? | How it becomes a test | Layer |
|---|---|---|---|
| **FR-1** endless never blocks | ✅ | VM: `targetCount=null` ⇒ `complete===false` at any `gradedTotal` | L1 unit |
| **FR-2** no dead-end (keep-practising works) | ✅ | E2E: after boundary, "Keep practising" returns to a live answering phase | L4 |
| **FR-3** no force-eject (no auto-nav) | ✅ | E2E: at boundary, URL still `/learn/quiz`; no redirect | L4 |
| **FR-4** fires at/after boundary, once, `≥` not `==` | ✅ | VM: `gradedTotal==target`→true, `==target-1`→false, `>target`→true | L1 unit |
| **FR-5** milestone message inline above feedback, names count, real text | ✅ | Component: renders text; count interpolated (7≠30); banner is text not colour-only. E2E: banner is a sibling ABOVE feedback | L1 + L4 |
| **FR-6** see-summary closes + routes | ✅ | E2E: "See summary" → Summary URL with stored score | L4 |
| **FR-7** continue keeps tally (over-run) | ✅ | E2E: "Keep practising" → same session, bar over-run (true position, no `of M`) | L4 |
| **FR-8** pure "reached" derivation (F-R1) | ✅ | VM test: `complete` depends only on `(gradedTotal, targetCount)`, not `phase`; translator imports `wire/` only (arch test) | L1 + arch |
| **FR-9** read-only (no engine write) | ✅ | Covered structurally: no scheduler/`use_quiz` call added (code review + arch); no new engine seam in the diff | review/arch |
| **FR-10** no regression to loop/bar/actions | ✅ | Existing `quiz-progress.spec.ts` (S4) + `quiz-no-repeat-60.spec.ts` (S3) stay green; `data-testid`s unchanged | L4 regression |
| **Edge** target already exceeded on load (`≥`) | ✅ | VM: `gradedTotal>target` ⇒ true (same as FR-4 `>` case) | L1 unit |
| **Edge** `target_count===1` | ✅ | VM: `gradedTotal=1, target=1` ⇒ true (no off-by-one) | L1 unit |
| **Edge** double-tap "see summary" idempotent | ✅ | Inherited: `onFinish`/`closeSession` already idempotent (`page.tsx:169` comment, S3) — assert once in E2E, no new code | L4 |
| **Edge** keep-practising then 2nd milestone (Q4 no re-arm) | ✅ | By construction: unconditional over-run past target keeps `complete` true, but the banner + relabelled buttons are already shown; no separate "2nd fire" logic. Assert the see-summary control remains available on a subsequent over-run screen | L4 |

**Numerator caveat (plan §3) is itself a test** — FR-8 case proves `complete` uses raw `gradedTotal`,
not the answering-offset `position`, so it never false-positives one question early.

---

## B. Atomic tasks (red-first, failure-paths-first; 1:1 EARS mapping)

Dependency + parallel markers: `[seq:N]` must follow N; `[par]` = independent of same-letter peers.
Every implementation task pastes **failing output first, then passing** (root `AGENTS.md` ✅ Always).

### T-s0 — VM `complete` test (RED) · `quiz_progress_vm.test.ts` · [par]
- **Covers:** FR-1, FR-4, FR-8, edge(≥), edge(target=1).
- Add `it` cases in the existing **"failure/edge first"** `describe` (plain `describe`/`it`, NOT
  `describe.each` — mirror G13):
  1. FR-1 — `toQuizProgressVM(99, "reviewing", null).complete === false`.
  2. FR-4 boundary — `(30,"reviewing",30).complete === true`; `(29,"reviewing",30).complete === false`.
  3. edge over-run — `(31,"reviewing",30).complete === true`.
  4. edge target=1 — `(1,"reviewing",1).complete === true`; `(0,"reviewing",1).complete === false`.
  5. FR-8 purity/offset — `(30,"answering",30).complete === true` **and** `(30,"reviewing",30).complete === true`
     (same `gradedTotal`, different phase ⇒ same `complete`; proves raw-gradedTotal, not `position`).
- **Pass/fail:** `./node_modules/.bin/vitest run lib/translators/quiz_progress_vm.test.ts` — MUST FAIL
  (no `complete` field yet). Paste the failure.

### T-s1 — VM `complete` impl (GREEN) · `quiz_progress_vm.ts` · [seq:T-s0]
- Add `readonly complete: boolean;` to `QuizProgressVM` (after `bounded`).
- Compute `const complete = bounded && gradedTotal >= targetCount;` (raw `gradedTotal`, per plan §3).
- Return it; add the one-line JSDoc (plan §4.1).
- **Pass/fail:** the T-s0 file now PASSES; `tsc --noEmit` clean. Paste both. Imports unchanged (Rule T1).

### T-s2 — Banner test (RED) · `QuizDoneBanner.test.tsx` (new) · [par]
- **Covers:** FR-5.
- Cases: (a) renders the milestone text; (b) `targetCount={7}` ⇒ output contains "7" and NOT "30"
  (count interpolated, FR-5); (c) message is queryable as text content (role/text), not colour/icon-only.
- **Pass/fail:** vitest on the new file — MUST FAIL (component absent). Paste it.

### T-s3 — Banner component (GREEN) · `QuizDoneBanner.tsx` (new) · [seq:T-s2]
- Props `{ targetCount: number }`; presentational; `data-testid="quiz-done-banner"`.
- Copy: **inline template literal** `` `🎉 You've completed your ${targetCount}-question session!` ``
  — **NOT `t()`** (repo has no i18n helper; match `QuizProgress`/`FeedbackView` inline-literal
  precedent — analyze correction). Carry the one-line "no `t()` yet" JSDoc note.
- Semantic tokens + `text-on-*` (AA light+dark). No `useEffect`, no SDK import, no logic (F-R1, U-family).
- **Pass/fail:** T-s2 PASSES; `tsc --noEmit` clean; a11y — `eslint-plugin-jsx-a11y` clean on the file.

### T-s4 — Page wiring · `app/(coach)/learn/quiz/page.tsx` · [seq:T-s1, T-s3]
- **Covers:** FR-5 (placement), FR-6, FR-7 (via relabel), FR-10 (selectors unchanged).
- Import `QuizDoneBanner`.
- In the reviewing `content` (`:225–247`), **above** `<FeedbackView>` (`:227`):
  `{progressVm.complete ? <QuizDoneBanner targetCount={session?.target_count ?? 0} /> : null}`.
- Relabel **label text only** (unconditional, Gate-2 OQ-1): `quiz-next` `Next question →` →
  `Keep practising`; `quiz-finish` `Finish &amp; see summary` → `See summary`. **`data-testid`s +
  `onClick` handlers + structure unchanged.**
- **Pass/fail:** `tsc --noEmit` clean; existing S4 spec `quiz-progress.spec.ts` still green
  (selectors intact); manual/preview smoke shows banner at target.

### T-s5 — E2E done-state walk (RED→GREEN) · `e2e/learn/quiz-done-state.spec.ts` (new) · [seq:T-s4]
- **Covers:** FR-2, FR-3, FR-6, FR-7, FR-5(sibling placement), edge(double-tap), edge(no re-arm).
- **Walk to the target of 30** (analyze: the E2E seed hook `__PREACT_E2E_SEED__` carries the corpus,
  NOT session `target_count` — no short-target shortcut exists; the S4 `quiz-progress.spec.ts` already
  walks the real bank at the 30 floor, reuse that pattern). Set a generous `test.setTimeout`.
  Assertions:
  1. Pre-target reviewing screen: buttons already read "Keep practising"/"See summary" (unconditional).
  2. At boundary: `quiz-done-banner` visible AND positioned **above** the feedback banner (DOM order);
     URL still `/learn/quiz` (**no auto-nav**, FR-3).
  3. "Keep practising" → still answering, same session; progress bar in over-run (true position, no
     `of M` — reuses S4 assertion) (FR-2, FR-7).
  4. On a subsequent over-run reviewing screen, "See summary" still present (edge: no re-arm needed;
     control persists).
  5. "See summary" → Summary route with the stored score (FR-6).
- **Pass/fail:** `CI=1 BASE_URL=… ./node_modules/.bin/playwright test --project=learn-e2e
  e2e/learn/quiz-done-state.spec.ts --reporter=list` PASSES against a running bypass-auth dev server.

### T-sg — Full gate + DoD evidence · [seq:T-s5]
- `cd frontend && ./node_modules/.bin/tsc --noEmit -p tsconfig.json` → exit 0.
- `./node_modules/.bin/vitest run lib/translators/quiz_progress_vm.test.ts components/quiz/QuizDoneBanner.test.tsx`
  → all pass.
- Layering arch test green (translator still `wire/`-only; new component has no SDK import).
- Regression: `quiz-progress.spec.ts` (S4) + `quiz-no-repeat-60.spec.ts` (S3) green (FR-10).
- **Paste actual command output** (not summaries) into the spec §9 DoD. Tick the DoD boxes.

---

## C. EARS ↔ task coverage matrix (no orphan criteria)

| EARS | Task(s) |
|---|---|
| FR-1 | T-s0/T-s1 |
| FR-2 | T-s5 |
| FR-3 | T-s5 |
| FR-4 | T-s0/T-s1 |
| FR-5 | T-s2/T-s3 (message) + T-s4 (placement) + T-s5 (sibling order) |
| FR-6 | T-s4 (relabel/handler) + T-s5 |
| FR-7 | T-s4 + T-s5 |
| FR-8 | T-s0/T-s1 (+ arch test in T-sg) |
| FR-9 | structural — no engine seam in diff (T-sg arch + code review) |
| FR-10 | T-s4 (selectors intact) + T-sg (S3/S4 regression) |
| edge ≥ / target=1 / double-tap / no-rearm | T-s0/T-s1 (unit edges) + T-s5 (runtime edges) |

**Every FR maps to at least one task; every task maps to at least one FR.** No orphans.

---

## D. Stage 4 — Analyze (DONE 2026-07-09)

Cross-artifact read-only check (spec ↔ plan ↔ tasks ↔ constitution) + grounding probe of every
referenced path/symbol + baseline. Outcome:

- **Grounding:** all §1 plan touchpoints re-verified by direct read (page reviewing branch
  `:225–247`, FeedbackView props `:85`, `toQuizProgressVM` call `:255–259`, reducer `score`). ✓
- **2 CRITICAL corrections caught (fixed in plan+tasks before implement):**
  1. **No `t()` helper exists** — `lib/i18n.ts` absent; sibling components use inline literals
     (`QuizProgress.tsx:15` documents this). Banner copy → inline template literal, not `t()`. Using
     `t()` would reference a non-existent API (context-blindness). *(plan §4.3, T-s3)*
  2. **E2E seed hook carries corpus, not `target_count`** — no short-target shortcut; T-s5 walks to
     the 30 floor (reuse S4 `quiz-progress.spec.ts` pattern). *(T-s5)*
- **No CRITICAL invariant violations, no zero-coverage FR, no non-existent-file reference remaining.**
- **Baseline green:** `./node_modules/.bin/tsc --noEmit -p tsconfig.json` → exit 0 ✓ ;
  `CI=1 ./node_modules/.bin/vitest run tests/architecture/test_frontend_layering.test.ts` → **5/5
  passed** ✓ (scoped to the layering gate to avoid the port-conformance ts-morph-under-load flake,
  [[frontend-vitest-tsmorph-timeout-artifact]]; S5 stresses layering, not port conformance).
- **ADR:** none triggered (re-confirmed — additive VM field + presentational component; no dep, wire
  type, reducer phase, or service).

**Ready for implement.** Stage 6 (sdd-implement) is a **separate** go-ahead — red-first per task, gate
after.
