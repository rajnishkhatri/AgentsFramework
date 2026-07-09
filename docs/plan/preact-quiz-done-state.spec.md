# Spec — S5: `/learn` quiz done-state + retake ("you've completed your N-question session")

**Status:** **IMPLEMENTED 2026-07-09** (Stage 6, sdd-implement) — all FRs green, full gate + S5 E2E
passing (§9). Gates 1+2 approved; ready for Stage 7 review (code-review) + commit.
**Owner:** Rajnish (PreAct English Coach)
**Related:** [[preact-quiz-progress-surface.spec.md]] (S4 progress bar — the other half of
this gap) · backlog item **F4** in [preact-learn-followups.notes.md](preact-learn-followups.notes.md) ·
[[preact-ui-gap-brainstorm]] (Stage-1 brainstorm: infinite loop by design) · ADR-0011
(Summary handoff) · S3 `target_count` ([[preact-s3-bounded-session-spec]]).

---

## 1. Goal

When a learner reaches their session target (the `target_count`, 30 by the seed
floor), tell them they've **finished the session** and offer a clear choice —
**see the summary** or **keep practising** — instead of silently serving question
31 as if nothing happened. This closes the *done-state* half of the reported
"`/learn` is an infinite loop" gap; S4 shipped the *progress* half (the bar).

For: a learner on the `/learn` quiz who set out to do a bounded session and needs a
sense of completion + a natural exit, without being trapped or force-ejected.

## 2. Context

**Premise audit (verified against the working tree 2026-07-09 — all confirmed):**

| Premise | Status | Evidence |
|---|---|---|
| The quiz loop never self-terminates at the target | **verified** | `quiz_screen_reducer.ts:177` — `next` always goes `reviewing → loading`; the page then fetches another item. No `target_count` check anywhere in the loop. |
| The only path to Summary today is the manual "Finish & see summary" button | **verified** | `app/(coach)/learn/quiz/page.tsx:237` (`quiz-finish`) → `onFinish` → `closeSession` → `router.push(summary)`. The `done` phase is reached ONLY via `finish` (`reducer.ts:182`). |
| Past the target the bar goes into over-run (true position, denominator dropped, bar clamped full) | **verified** | `quiz_progress_vm.ts:57` — `total = bounded && position <= targetCount ? targetCount : null`. Correct + honest today; but there is NO milestone message. |
| "Reached the target" is derivable from signals already on the reducer | **verified** | `SessionTally.total` (`reducer.ts:53`) rides every phase; `session.target_count` is read at `page.tsx:255`. `reached = total >= target_count`. No new engine signal needed. |
| The Summary screen already IS the retake surface | **verified** | `SummaryView.tsx:78` — a CTA linking back to `/learn/quiz` (fresh session); `:70` a `?focus=` drill deep-link. So "path to retake" already exists downstream — S5 routes to it, it does not build it. |
| The `done` phase renders nothing meaningful (transient "closing" state) | **verified** | `page.tsx:187` — `loading || done` early-returns the "Loading your next question…" status line, then navigates. |

**Consequence for scope:** S5 is a **milestone + navigation prompt at the target**,
NOT a new retake screen and NOT an engine change. The retake affordance (Summary)
already exists; the over-run bar rendering is already correct. S5 adds the *signal*
that the goal was reached and a *non-trapping* choice at that moment.

**What S5 is NOT:** it does not change `target_count`, the scheduler, the no-repeat
seam (S3), or the over-run VM math (S4). It does not auto-close or force-navigate in a
way that strands the learner (see FR failure paths). It is a Frontend-Ring-only change
(page phase + presentational surface + a pure "reached?" derivation).

## 3. Functional requirements (EARS)

*Failure paths first (TAP-4).* The numerator/denominator convention is inherited
from S4: `position` is 1-based; `reached` means `graded total ≥ target_count`.

- **FR-1 (endless never blocks).** IF the session is endless (`target_count` is null)
  THEN THE SYSTEM SHALL NOT show any done-state — the loop continues exactly as
  today (no milestone, no prompt). *(Failure path: a null target must not be treated
  as "reached at 0".)*
- **FR-2 (no dead-end / not trapped).** WHILE the done-state is shown THE SYSTEM SHALL
  keep a working **"keep practising"** affordance that returns the learner to a live
  answering phase — the learner is never stuck on a terminal screen with no forward
  path. *(Failure path: the done-state must not be a trap.)*
- **FR-3 (no force-eject).** WHEN the learner reaches the target THE SYSTEM SHALL NOT
  auto-navigate away from the quiz or auto-close the session — the exit to Summary is
  learner-initiated. *(Failure path: reaching 30 must not yank the learner out
  mid-thought.)*
- **FR-4 (fires at/after the boundary, once).** WHILE the graded total is ≥
  `target_count` (bounded session) AND the phase is `reviewing` THE SYSTEM SHALL show
  the done-state milestone. The milestone thus first appears on the feedback for the
  item that hits the target (not at N−1); by Q4 it is not separately "re-armed" — it
  is simply present whenever a reviewing screen is at/over the target. *(Edge: `≥`,
  not `==`, so a resumed already-past-target session still shows it — see §6.)*
- **FR-5 (the milestone message, inline above feedback).** WHILE the done-state is
  shown THE SYSTEM SHALL display, **above the item's feedback** (which remains
  visible, Q1), a completion message naming the count reached — "🎉 You've completed
  your {target_count}-question session!" — as real text (WCAG 2.2 AA; not colour/icon
  alone), with `{target_count}` interpolated from the session, never hardcoded.
- **FR-6 (see-summary path).** WHILE the done-state is shown THE SYSTEM SHALL offer a
  **"see summary"** action that closes the session with the running tally and routes
  to the Summary (the same close+route as today's Finish button — Summary never
  re-tallies, ADR-0011/G1).
- **FR-7 (continue keeps the tally).** WHEN the learner chooses "keep practising" from
  the done-state THE SYSTEM SHALL continue the SAME session (tally preserved, no
  re-open) — subsequent items are over-run and the bar renders per S4 (true position,
  denominator dropped). *(Confirmed clarify Q2 decision — see §2.2.)*
- **FR-8 (pure "reached" derivation, F-R1).** THE SYSTEM SHALL compute "reached the
  target" as a pure function of `(gradedTotal, targetCount)` in a translator/helper —
  the page component holds no threshold logic (mirrors S4's `quiz_progress_vm`).
- **FR-9 (read-only, no engine call).** THE SYSTEM SHALL derive and render the
  done-state without any scheduler/engine write — it reads the tally + target already
  in hand (FR-9/FR-13 preserved; the done-state is a view concern).
- **FR-10 (no regression to the loop/bar).** THE SYSTEM SHALL leave S3 (no-repeat), S4
  (progress bar over-run rendering), and the existing Next/Finish reviewing actions
  behaving exactly as before for every pre-target item.

## 2.2 Clarify decisions (from the clarify pass, 2026-07-09)

- **Q1 — surface shape → INLINE on the last feedback.** After grading the item that
  hits the target, the normal `reviewing` feedback screen (which still shows the
  answer to that item) gains a **milestone banner above it**, and the existing two
  actions relabel: `Next question →` → **"Keep practising"**, `Finish & see summary`
  → **"See summary"**. Reuses the `reviewing` phase — **no new reducer phase**. Pins
  FR-2 (learner still sees #30's answer) and FR-5 placement.
- **Q2 — "Keep practising" → CONTINUE THE SAME SESSION (over-run).** Same session,
  tally preserved, no re-open. Subsequent items are over-run and the bar renders per
  S4 (true position e.g. "Question 31", denominator dropped, bar full). Matches the
  original "you can continue if you like." Pins FR-7.
- **Q3 — auto-navigate → NEVER (offer only).** Reaching the target only SHOWS the
  done-state + choices; leaving to Summary is always an explicit click. No timed
  redirect, no force-eject. Pins FR-3.
- **Q4 — over-run cap → FIRE ONCE, at the exact boundary (default, no re-arm).** The
  milestone appears exactly when `gradedTotal` first equals `target_count` (FR-4).
  After "Keep practising" the session is uncapped over-run and the milestone does
  **not** re-arm at every +N (that would nag a learner who already chose to continue).
  The see-summary action remains available on every subsequent feedback screen (it's
  the same relabelled/kept Finish control). *Small default, not a user question —
  recorded in `docs/adr/decisions.md` at plan time.*
- **Q5 — copy → dynamic count.** Banner: **"🎉 You've completed your {target_count}-question
  session!"**; actions **"Keep practising"** / **"See summary"**. Count is read from
  `target_count`, never hardcoded 30.

## 4. Data model / contracts

No wire/schema change. `target_count` (S3, `engine_entities.ts:213`) and
`SessionTally` (`reducer.ts:53`) already exist. S5 adds at most:
- a pure helper (e.g. `isSessionComplete(gradedTotal, targetCount): boolean`, or an
  extension of the existing `quiz_progress_vm` VM with a `complete` flag), and
- possibly one new reducer phase or a derived flag on the page (decided at plan time,
  post-clarify).

No trust-kernel type, no `pyproject.toml` dep, no new wire event.

## 5. Invariants & security boundaries

Frontend Ring only. Touches:
- **F-R1 (no domain logic in components):** the "reached?" threshold + any count math
  lives in a pure translator/helper; the component renders the result (as S4 did).
- **F-R9 / FR-13 (read-only serve path):** the done-state is a view over existing
  signals — no engine write, no scheduler call.
- No SDK import, no `trace_id` concern, no CSP/sandbox surface. Backend Architecture
  Invariants #1–#8 untouched (no Python change).

Security: none — no secrets, no live LLM, no new network path.

## 6. Edge cases

- **Endless session** (`target_count` null): no done-state ever (FR-1).
- **Target already exceeded on load** (e.g. a resumed session where `total` >
  `target_count`): the done-state logic must be `≥`, not `==`, so a session that is
  already past the target still surfaces the choice rather than silently looping
  (pin in a test).
- **`target_count` of 1:** the done-state fires after the first graded item — must not
  off-by-one to "never" or "immediately at 0".
- **Double-tap "see summary":** close is idempotent (`sessionRepo.close`,
  `use_quiz.ts` close path) — a duplicate must not double-tally.
- **"Keep practising" then reaching a second milestone:** decided by Q4 (over-run cap)
  — if uncapped, no second milestone; if re-armed, define when.

## 7. Non-functional requirements

Deterministic, synchronous, client-only. No latency/cost surface (no new I/O). Fully
reversible (a presentational + phase change). No live-LLM path. L1/L4 testable exactly
like S4 (pure helper unit test + a Playwright walk).

## 8. Test plan

*Failure-path tests first. Filenames provisional — settled at plan/tasks time.*

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | helper: endless (`targetCount` null) → not complete | L1 (vitest) | yes |
| FR-4 | helper: `total == target` → complete; `total == target-1` → not | L1 | yes |
| FR-8 | helper is pure `(gradedTotal, targetCount)` — no imports | L1 | yes |
| edge | helper: `total > target` → still complete (≥) ; `target==1` boundary | L1 | yes |
| FR-2 | component/page: done-state renders a working "keep practising" control | L1 (vitest SSR/RTL) | yes |
| FR-5 | component: milestone message present as text, names the count | L1 | yes |
| FR-6 | component: "see summary" control present + wired to close+route | L1 | yes |
| FR-3/FR-7/FR-10 | Playwright `learn-e2e`: reach target → done-state shows, NO auto-nav; "keep practising" continues same session (bar over-run); "see summary" → Summary with stored score | L4 | on-demand |

## 9. Definition of Done — MET (implemented 2026-07-09, Stage 6)

- [x] All FRs implemented; each has a passing test *seen to fail first* (red→green).
      RED evidence: VM `complete` → `expected undefined to be true` (7 failed); banner →
      `Failed to resolve import "./QuizDoneBanner"`. Both then GREEN (below).
- [x] Clarify §2.2 decisions filled and reflected in the FRs before plan. Gate-2 OQ-1
      first resolved = unconditional relabel, then **REVERTED 2026-07-09 (user)** to
      **target-gated relabel**: buttons keep the ORIGINAL labels ("Next question →" /
      "Finish & see summary") pre-target and flip to "Keep practising" / "See summary"
      only at/after the target (gated on `progressVm.complete`, in lock-step with the
      banner). See `docs/adr/decisions.md` (2026-07-09 revert entry).
- [x] Frontend gate green (actual output pasted):
- [x] Playwright `e2e/learn/quiz-done-state.spec.ts` passes against the bypass-auth dev server.
- [x] Invariants in §5 unbroken (F-R1: threshold in translator; F-R9/FR-13: read-only, no
      engine call; U-family: `text-on-accent` AA + real text; Rule T1: translator `wire/`-only —
      layering arch test 5/5).
- [x] No ADR trigger fired (additive VM `complete` field + presentational `QuizDoneBanner`
      mirroring `QuizProgress`; no dep, wire type, reducer phase, or service). Recorded in
      `docs/adr/decisions.md`.
- [x] Actual command output pasted (not summarized) — below.

### Implementation evidence (Stage 6, 2026-07-09)

**Files:** `lib/translators/quiz_progress_vm.ts` (+`complete`), `.test.ts` (+7 cases),
`components/quiz/QuizDoneBanner.tsx` (new), `.test.tsx` (new), `app/(coach)/learn/quiz/page.tsx`
(banner sibling + target-gated relabel — original labels pre-target, S5 labels at/after target,
gated on `progressVm.complete`; `progressVm` hoisted above the phase branch so the banner
shares it), `components/quiz/QuizProgress.test.tsx` (7 VM literals + `complete`),
`e2e/learn/quiz-done-state.spec.ts` (new, 4 tests).

**Full gate (all four green):**
```
1/4  tsc --noEmit -p tsconfig.json                          → exit 0
2/4  vitest quiz_progress_vm.test.ts + QuizDoneBanner.test.tsx + QuizProgress.test.tsx
     → Test Files 3 passed (3) · Tests 20 passed (20)
3/4  vitest tests/architecture/test_frontend_layering.test.ts
     → Test Files 1 passed (1) · Tests 5 passed (5)
4/4  playwright --project=learn-e2e quiz-progress.spec.ts + quiz-no-repeat-60.spec.ts (regression)
     → 5 passed (15.7s)  [walked=60 duplicates=0 perSkill=punc:10 gram:10 sent:10 rhet:10 org:10 style:10]
```

**S5 E2E (`quiz-done-state.spec.ts`, bypass-auth dev server, port 3000):**
```
Running 4 tests using 1 worker
  ✓ 1 pre-target screens keep the ORIGINAL labels (relabel gated on the target) (2.1s)
  ✓ 2 reaching the target shows the milestone and does NOT auto-navigate (FR-3/FR-4/FR-5) (5.4s)
  ✓ 3 'Keep practising' continues the same session into over-run (FR-2/FR-7) (3.8s)
  ✓ 4 'See summary' closes the session and routes to the Summary (FR-6) (7.3s)
  4 passed (19.7s)
```

**EARS coverage:** FR-1/FR-4/FR-8 + edges → VM unit tests (12 pass) · FR-5 → banner unit (2) +
E2E #2 (placement) · FR-2/FR-3/FR-6/FR-7 → E2E #2–#4 · FR-10 → S3/S4 regression (5 pass, selectors
intact). No orphan criteria.
