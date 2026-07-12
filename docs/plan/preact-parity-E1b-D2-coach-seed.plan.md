---
title: 'E1b-D2 — skill-only coach seed contract: implementation plan'
type: plan
sub_epic: E1b
direction: D2
status: Draft — 2026-07-12
derives_from: docs/plan/preact-parity-E1b-D2-coach-seed.spec.md
adr: docs/adr/0030-lesson-coach-seed-contract.md
---

# E1b-D2 — implementation plan

## Architecture

Widen the coach **pin** from an item-only shape to a **discriminated union** (`item | lesson`), add a
**lesson branch** to `assembleCoachContext` that emits a skill-only `coach_context` (honest-null
question), and replace the lesson's bare `<Link>` with a **store-write-then-navigate** so the coach
never cold-opens on a stale pin. Entirely frontend-ring: pure translators + the coach thread store +
the lesson view. The BFF sanitizer already fails closed to `pre_submit` on absent `question_id` — the
correct lesson default — so **no BFF/middleware change**.

## File-level touchpoints

| File | Change |
|------|--------|
| `frontend/lib/translators/coach_surface_vm.ts` | `CoachSurfacePin` (`:24-28`) → discriminated union: `{ kind:'item'; questionId; skillId; label } \| { kind:'lesson'; skillId; label }`. Every read of `pin.questionId` gains a `kind` guard. |
| `frontend/lib/wire/…coach context type` | `WireCoachContext`: add a lesson variant — `question_id`/`question` omitted when lesson; `skill_id` always present. Keep the item shape wire-compatible (discriminated on presence of `question_id`, or a `context_kind` tag — ADR-0030 picks). |
| `frontend/lib/translators/assemble_coach_context.ts` | Add the lesson branch (`:43-55`): for a `kind:'lesson'` pin return `{ mode:'pre_submit', skill_id, /* no question */ }`; **skip** the `question.id === pin.questionId` guard (`:48`) for lesson pins; keep the item branch unchanged. |
| `frontend/components/coach/coach_thread_store.ts` | `setCoachPin` (`:96`): accept the union; reset/fresh-thread logic keys on a **branch-aware identity** (skill for lesson, questionId for item) so a lesson pin doesn't mis-reset on a null questionId, and item↔lesson switch resets correctly. |
| `frontend/components/coach/use_coach.ts` | The `pin != null` block (`:107-134`): for a lesson pin **skip** `questionRepo.get(pin.questionId)` (`:110`) — pass `question: null`; still compute `missesOnSkill` + `skillStates` (both already skill-keyed). |
| `frontend/components/learn/SkillDetailView.tsx` | `CoachEntryBlock` (`:370-390`): replace the bare `<Link href={screen('coach').route}>` (`:381`) with `setCoachPin({ kind:'lesson', skillId: block.skillId, label: block.skillName }, 'pre_submit')` + navigate — mirror the quiz pin-write at `components/quiz/quiz_coach_pin.ts`. |
| `frontend/components/quiz/quiz_coach_pin.ts` | Update the item-pin construction to the `kind:'item'` tag (the other union writer) so both writers agree. |
| `docs/adr/0030-lesson-coach-seed-contract.md` | New ADR (the seed shape + honest-null question + rejected nullable-questionId). |
| `docs/adr/index.md`, `docs/adr/log.md` | OKF entries. |
| `frontend/e2e/learn/skill-coach-seed.spec.ts` (new) | L4: open coach from a `returning` lesson → skill-pinned, `pre_submit`, no item panel. |

**No change:** middleware, BFF coach route logic, `skill_state`/`attempt`/DB, the coach conversation UI.

## Migration
None — pins are ephemeral in-memory store state. No persisted shape changes. A revert restores the
bare link (and the cold-open bug).

## Invariants (constitution check)
- **Inv #3/#4 + F-R8:** all changes in `lib/translators` (pure) + `lib/wire` (Zod kernel) +
  `components/coach|learn|quiz`. No SDK type escapes; the wire type stays a pure kernel.
- **Security (fail-closed):** the lesson context carries **no `question_id`** → the sanitizer's
  existing default routes it to `pre_submit`; it cannot spoof `post_feedback` (no answer reveal). The
  union makes honest-null explicit rather than fabricating a question (which would risk answer-leakage).
- **Exhaustiveness:** the discriminated union forces every consumer to a `kind` switch — typecheck
  proves no consumer silently mishandles a lesson pin (FR-4).
- **⚠️ Ask-first → ADR-0030:** OQ-3/D4c is a named deferred *contract* decision. `test_adr_ratchet.py`
  satisfied by the new `docs/adr/0030-*.md`.

## Build order (red→green)
1. Write ADR-0030 (seed shape + honest-null + rejected nullable) — the *why* first.
2. **Red:** FR-1 (`coach_thread_store.test.ts`: lesson pin overwrites a stale item pin) + FR-2
   (`assemble_coach_context.test.ts`: lesson pin → valid context, not null) against current code.
3. Green: `CoachSurfacePin` union → let typecheck surface every consumer (FR-4); handle each `kind`.
4. Lesson branch in `assembleCoachContext` (FR-2/FR-5/FR-6); `use_coach` skip-`questionRepo.get`.
5. `setCoachPin` branch-aware reset (FR-1/FR-6b); `CoachEntryBlock` store-write-then-navigate (FR-3).
6. Grep-guard: no middleware/`question_id` change (FR-7); `check:*` scripts green.
7. `pnpm test` + `test:arch` + `typecheck` + `test:e2e:learn` (new skill-coach-seed spec, FR-8);
   paste FR-1/FR-2 red→green + the E2E run.

## Test → FR map
| FR | Test | Layer |
|----|------|-------|
| FR-1 | `coach_thread_store.test.ts::lesson pin overwrites stale item pin` | L1 |
| FR-2 | `assemble_coach_context.test.ts::lesson pin → valid context, not null` | L1 |
| FR-3 | `SkillDetailView.test.tsx::Open coach writes lesson pin + navigates` | L1 |
| FR-4 | `coach_surface_vm.test.ts::union both branches exhaustive` | L1 |
| FR-5 | `assemble_coach_context.test.ts::lesson pin → pre_submit` | L1 |
| FR-6 | `assemble_coach_context.test.ts::lesson pin skips questionId guard` | L1 |
| FR-6b | `coach_thread_store.test.ts::lesson→lesson same skill no spurious reset` | L1 |
| FR-7 | grep-guard + `check:*` scripts (no middleware diff) | L1 |
| FR-8 | `e2e/learn/skill-coach-seed.spec.ts::skill-pinned, no item panel` | L4 |
