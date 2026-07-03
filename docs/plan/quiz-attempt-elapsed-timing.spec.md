# Spec — Quiz attempt real elapsed timing (D0)

> The spec captures the *what* (testable acceptance criteria). No `⚠️ Ask first`
> trigger fires for the D0 fix itself (no new dependency, no new graph node, no
> trust-kernel change, no new abstraction), so no ADR is required for it. The two
> consent-gated reversals in §2.1 are **non-goals** here — each is its own consent
> gate and, if pursued, its own spec.

**Status:** Draft — 2026-07-03
**Owner:** Rajnish Khatri
**Related:** [subject-coach-agent.plan.md](subject-coach-agent.plan.md) (Phase-1 `1B-8` marker write on submit); [FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md](../Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md); source seam [quiz/page.tsx:121](../../frontend/app/(coach)/learn/quiz/page.tsx#L121)

---

## 1. Goal

Every quiz attempt row records the learner's **real** answer latency instead of a
hardcoded `0`. Today `elapsedMs: 0` is pinned at the submit call site
([quiz/page.tsx:121](../../frontend/app/(coach)/learn/quiz/page.tsx#L121)), so
every `attempt.elapsed_ms` ever written is fabricated timing. This fix makes the
one already-declared behavioral field on the attempt honest, for whoever later
reads it (analytics, FSRS tuning, the coach's derived struggle signal).

## 2. Context

`elapsed_ms` is a fully plumbed field with a fabricated source:

- **Schema exists and is correct** — `elapsed_ms: integer(...).notNull().default(0)`
  in both dialects ([schema.pg.ts:168](../../frontend/lib/adapters/engine/db/schema.pg.ts#L168),
  [schema.sqlite.ts:121](../../frontend/lib/adapters/engine/db/schema.sqlite.ts#L121)),
  the wire entity (`elapsed_ms: z.number().int()`,
  [engine_entities.ts:144](../../frontend/lib/wire/engine_entities.ts#L144)), and
  the read-back (`Number(r.elapsed_ms ?? 0)`,
  [drizzle_engine_db.ts:128](../../frontend/lib/adapters/engine/db/drizzle_engine_db.ts#L128)).
- **The write path already carries the value** — `page.tsx onSubmit` → `submit({… elapsedMs …})`
  → `QuizSubmitArgs.elapsedMs` ([use_quiz.ts:113](../../frontend/components/quiz/use_quiz.ts#L113))
  → `attemptRepo.record({… elapsed_ms: args.elapsedMs …})`
  ([use_quiz.ts:146](../../frontend/components/quiz/use_quiz.ts#L146)). `use_quiz.test.ts`
  already asserts a non-zero `elapsedMs` (e.g. `1000`, `2000`, `3000`) survives to the
  recorded attempt — so the plumbing is proven; **only the value at the source is a stub.**
- **The clock is the missing piece.** The pure phase machine
  ([quiz_screen_reducer.ts](../../frontend/components/quiz/quiz_screen_reducer.ts))
  has no timing state today: the `answering` state carries no "presented at" timestamp,
  so the page has nothing real to subtract from at submit. The natural seam is the
  `item_loaded → answering` transition (clock start) and `onSubmit` (clock stop).
- **No downstream reader yet.** Nothing in Feedback or Summary reads `elapsed_ms`
  (grep-confirmed). This is therefore a **data-integrity fix ahead of need**, not a
  feature — which is exactly why it is safe to land small and why it must be honest
  now, before a reader trusts the fabricated column.

Wall-clock elapsed is the right primitive for "how long did the learner sit on
this item" and matches the field's intent; higher-fidelity active-focus timing
(pausing on tab-blur) is explicitly out of scope (§2.1, §6).

### 2.1 Non-goals (consent-gated — NOT in this spec)

These are **documented deliberate decisions**. Reversing either is a consent gate,
not a silent flip, and each would be its own spec. They are recorded here only so
the fix's scope is unambiguous:

- **Test mode persists nothing.** The timed `/learn/test` mode deliberately writes
  no durable attempt/session records. This spec does **not** make Test mode persist.
- **Coach threads evaporate on reload.** Coach threads are intentionally in-memory
  (`coach_thread_store`) and do not survive a reload. This spec does **not** add
  coach-thread durability.

If either reversal is later wanted, raise it explicitly with the user first; do not
fold it into the D0 fix.

## 3. Functional requirements (EARS)

Failure paths first.

- **FR-1.** IF no answer is selected at submit (the `letter == null` /
  no-selection path) THEN THE SYSTEM SHALL record no attempt and therefore write no
  `elapsed_ms` (unchanged FR-D2a behavior — the timing fix must not create a row
  where none existed).
- **FR-2.** IF a monotonic clock source is unavailable or a captured start timestamp
  is missing at submit THEN THE SYSTEM SHALL record a non-negative `elapsed_ms`
  (never a negative or `NaN` value; a `0` floor is acceptable in this degenerate case).
- **FR-3.** WHEN an item enters the `answering` phase (the `item_loaded` transition)
  THE SYSTEM SHALL capture a start timestamp for that item.
- **FR-4.** WHEN the learner submits a selected answer THE SYSTEM SHALL compute
  `elapsedMs` as the whole-millisecond difference between submit time and the item's
  captured start timestamp, and pass that value (not `0`) to `submit(...)`.
- **FR-5.** THE SYSTEM SHALL derive elapsed from a **monotonic** clock
  (`performance.now()`), so a wall-clock adjustment during answering cannot produce a
  negative or wildly skewed `elapsed_ms`.
- **FR-6.** WHERE an item is re-presented after a Next→loading→answering cycle THE
  SYSTEM SHALL reset the start timestamp for the new item (per-item timing, never
  cumulative across the walk).

## 4. Data model / contracts

**No wire, schema, or DB change.** `attempt.elapsed_ms` already exists as
`z.number().int()` on the wire and `integer notNull default 0` in both dialects.
`QuizSubmitArgs.elapsedMs: number` is unchanged. This spec changes only the *source*
of the value flowing into that existing contract.

The only new state is a transient, client-only start timestamp for the current item.
Preferred: hold it in the reducer's `answering` state (e.g. a `presentedAt: number`
from `performance.now()` set on `item_loaded`), keeping the page a thin glue and the
timing logic node-testable in the pure reducer (F-R1: no domain logic in the page).
A `useRef` in the page is the fallback if reducer state proves awkward, but the
reducer keeps it testable without React.

## 5. Invariants & security boundaries

- **F-R1 (no domain logic in React components).** The elapsed computation is trivial
  subtraction; keeping the timestamp in the pure reducer keeps `page.tsx` glue-only.
- **Frontend Ring layering.** No `wire/`, `ports/`, `adapters/`, or `translators/`
  change — the value originates in the page/reducer and rides the existing
  `use_quiz` orchestration. No SDK import, no new port.
- **No trust-kernel impact**, no re-signing, no new dependency, no new graph node,
  no new abstraction ⇒ no `⚠️ Ask first` trigger ⇒ no ADR required.
- **No PII / no new logging.** A latency integer is not PII; nothing new is logged.

## 6. Edge cases

- **No selection at submit** → no attempt row at all (FR-1); timing is irrelevant.
- **Missing/zeroed start timestamp** (defensive, e.g. a submit that somehow races
  ahead of `item_loaded`) → clamp to `>= 0` (FR-2), never negative/`NaN`.
- **Very fast submit** (sub-millisecond) → `Math.round` to whole ms, `0` is a valid
  honest value here and is distinguishable in intent from the old universal stub.
- **Tab backgrounded / learner walks away mid-item** → counted as elapsed wall time
  by design; active-focus (blur-pause) timing is explicitly **out of scope** (§2.1).
- **Hint used** → `used_hint` is orthogonal; timing still spans full answering phase.
- **Undecidable is not `0`-as-signal** — the `0` floor from FR-2 is a degenerate
  fallback, not a fabricated reading; the fix removes the *universal* fabrication.

## 7. Non-functional requirements

- **Determinism / testability.** Inject the clock (pass `performance.now()` or a
  `now()` seam) so tests feed fixed timestamps and assert an exact `elapsed_ms` —
  L1 deterministic, no flake.
- **Reversibility.** Pure additive value-source change; trivially revertible.
- **No live LLM calls**, no CI hot-path cost. Vitest only.
- **Latency:** negligible; two timestamp reads per item.

## 8. Test plan

Failure-path tests before happy-path. All L1 deterministic (Vitest), all in the
frontend unit gate.

| FR | Test | Layer | In gate? |
|----|------|-------|----------|
| FR-1 | `use_quiz.test.ts::…no selection records no attempt` (extend: asserts still no row) | L1 | yes |
| FR-2 | `quiz_screen_reducer.test.ts::…missing start ⇒ elapsed clamped ≥ 0` (new) | L1 | yes |
| FR-3 | `quiz_screen_reducer.test.ts::item_loaded sets presentedAt` (new) | L1 | yes |
| FR-4 | `quiz page / reducer test::submit computes elapsed = stop − start` with injected clock (new) | L1 | yes |
| FR-5 | reducer/page test uses monotonic `performance.now()` seam; wall-clock jump does not go negative (new) | L1 | yes |
| FR-6 | `quiz_screen_reducer.test.ts::next → item_loaded resets presentedAt` (new) | L1 | yes |
| regression | existing `use_quiz.test.ts` non-zero `elapsedMs` → recorded attempt stays green (unchanged) | L1 | yes |

Each new test must be **seen to fail first** (red) against the current `elapsedMs: 0`
source before the fix lands.

## 9. Definition of Done

- [ ] `page.tsx` no longer passes the literal `elapsedMs: 0`; the value is a real,
      per-item, monotonic elapsed reading.
- [ ] All FRs implemented; each has a passing test that was *seen to fail first*.
- [ ] `make check` green and frontend vitest green (paste actual counts, not a summary).
- [ ] Invariants in §5 unbroken (`tests/architecture/` + frontend layering green).
- [ ] No ADR needed (no ⚠️ Ask first trigger); a one-line `docs/adr/decisions.md`
      entry records the monotonic-clock + wall-clock-not-active-focus choice.
- [ ] §2.1 non-goals untouched: Test mode still persists nothing; coach threads still
      in-memory. No consent-gated reversal was folded in.
