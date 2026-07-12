---
title: 'E1b-D2 — skill-only coach seed contract: task checklist'
type: tasks
sub_epic: E1b
direction: D2
status: Ready — 2026-07-12
derives_from: docs/plan/preact-parity-E1b-D2-coach-seed.plan.md
spec: docs/plan/preact-parity-E1b-D2-coach-seed.spec.md
adr: docs/adr/0030-lesson-coach-seed-contract.md
---

# E1b-D2 — task checklist

> **Read first (in order):** the [spec](preact-parity-E1b-D2-coach-seed.spec.md) (EARS FR-1..FR-8),
> the [plan](preact-parity-E1b-D2-coach-seed.plan.md) (touchpoints), and [ADR-0030](../adr/0030-lesson-coach-seed-contract.md)
> (the *why* — discriminated union + honest-null + rejected alternatives). This file is the atomic
> decomposition, dependency-ordered, red→green. The core trick: **the discriminated union makes
> typecheck list every consumer for you** — let it.

## Checklist quality gate ("unit tests for English")

| FR | Measurable claim | Test |
|----|------------------|------|
| FR-1 | lesson pin overwrites a stale item pin | `coach_thread_store.test.ts` |
| FR-2 | lesson pin (no questionId) → valid context, not null | `assemble_coach_context.test.ts` |
| FR-3 | "Open coach" writes lesson pin + navigates | `SkillDetailView.test.tsx` |
| FR-4 | pin union — both branches exhaustive | `coach_surface_vm.test.ts` + typecheck |
| FR-5 | lesson pin derives `pre_submit` mode | `assemble_coach_context.test.ts` |
| FR-6 | lesson pin skips `question.id === pin.questionId` guard | `assemble_coach_context.test.ts` |
| FR-6b | lesson→lesson same skill → no spurious reset | `coach_thread_store.test.ts` |
| FR-7 | no middleware / `question_id` change | grep-guard + `check:*` |
| FR-8 | open coach from lesson → skill-pinned, no item panel | `e2e/learn/skill-coach-seed.spec.ts` (L4) |

All criteria measurable → **no flags back to the spec.**

## Preconditions

- [ ] **P0.** Branch `feat/preact-parity-epic-E`. **ADR-0030 already exists** on disk
  (`docs/adr/0030-lesson-coach-seed-contract.md`, status `proposed`) with index.md/log.md OKF entries
  already appended — do **not** re-author it; at the tasks→implement gate flip its status to
  `accepted` (per the ADR-0028 precedent). D2 is **independent of D1 and D0** (no shared files) — it
  can be done before, after, or in parallel via a separate worktree.
- [ ] **P1.** `cd frontend && pnpm install`; baseline `pnpm test:arch` + `pnpm typecheck` green first.

## Tasks (dependency-ordered, red→green)

### T1 — ratify ADR-0030 (the *why* is already written)  ·  no dep
- [ ] **T1.** Confirm `docs/adr/0030-lesson-coach-seed-contract.md` + its `index.md`/`log.md` entries
  are present and correct; flip `status: proposed → accepted` at the implement gate. `okf_lint.py` = 0
  new failures. (`test_adr_ratchet.py` is Python-path-only and won't fire on this frontend change —
  ADR-0030 satisfies the **convention**, not a mechanical gate.)

### T2 — RED: the two failure-path tests against current code  ·  no dep
> These must fail against the **current** bare-link / questionId-required code before any change.
- [ ] **T2a.** `coach_thread_store.test.ts::lesson pin overwrites a stale item pin` (**FR-1**) — seed an
  item pin, then `setCoachPin` a lesson pin, assert the store now holds the lesson pin (not the stale
  item). Against current code this won't even type (no lesson pin) — that *is* the red. Capture it.
- [ ] **T2b.** `assemble_coach_context.test.ts::lesson pin (no questionId) → valid skill-only context,
  not null` (**FR-2**) — assert a lesson pin yields a non-null `coach_context` with `skill_id` and no
  question. Against current code `assembleCoachContext` returns `null` (`:47-48`) → RED. Paste it.

### T3 — GREEN: widen the pin to a discriminated union  ·  dep: T2
- [ ] **T3a.** `frontend/lib/translators/coach_surface_vm.ts` (`:24-28`): `CoachSurfacePin` →
  `{ kind:'item'; questionId: string; skillId: string; label: string } | { kind:'lesson'; skillId:
  string; label: string }`. **Run `pnpm typecheck` → it now lists every consumer** that reads
  `pin.questionId` without narrowing. That list *is* your work-queue for T4/T5/T6 (FR-4 exhaustiveness).
- [ ] **T3b.** `frontend/components/quiz/quiz_coach_pin.ts` — tag the item-pin construction
  `kind:'item'` so both union writers agree.
- [ ] **T3c.** `coach_surface_vm.test.ts::pin union — both branches handled (exhaustive)` (**FR-4**) —
  a switch over `kind` with a `never`-exhaustiveness check; GREEN + typecheck proves no unhandled branch.

### T4 — GREEN: lesson branch in assembleCoachContext + wire variant  ·  dep: T3
- [ ] **T4a.** Wire type (`frontend/lib/wire/…coach context type`): add a **lesson variant** of
  `WireCoachContext` — `question_id`/`question` **omitted** when lesson; `skill_id` always present.
  ADR-0030 picks the discriminant (Zod discriminated union on a `context_kind` tag, or optional fields
  gated by `mode`); keep the **item shape wire-compatible**.
- [ ] **T4b.** `frontend/lib/translators/assemble_coach_context.ts` (`:43-55`): add the lesson branch —
  for a `kind:'lesson'` pin return `{ mode:'pre_submit', skill_id, /* no question */ }`; **skip** the
  `question.id === pin.questionId` guard (`:48`) for lesson pins; **item branch unchanged**.
- [ ] **T4c.** Tests **FR-5** (lesson pin → `pre_submit`) + **FR-6** (lesson pin skips the questionId
  guard) in `assemble_coach_context.test.ts`. Flip T2b's FR-2 to GREEN.

### T5 — GREEN: store reset + use_coach skip  ·  dep: T3
- [ ] **T5a.** `frontend/components/coach/coach_thread_store.ts` `setCoachPin` (`:96-130`): accept the
  union; make the fresh-thread/reset identity **branch-aware** — key on `skillId` for lesson pins,
  `questionId` for item pins — so a lesson pin doesn't mis-reset on a null questionId and an item↔lesson
  switch resets correctly. Flip T2a's FR-1 to GREEN.
- [ ] **T5b.** `coach_thread_store.test.ts::lesson→lesson (same skill) does not spuriously reset`
  (**FR-6b**) — two lesson pins for the same skill must not reset the thread. GREEN.
- [ ] **T5c.** `frontend/components/coach/use_coach.ts` `pin != null` block (`:107-134`): for a lesson
  pin **skip** `questionRepo.get(pin.questionId)` (`:110`) — pass `question: null`; still compute
  `missesOnSkill` + `skillStates` (both skill-keyed already).

### T6 — GREEN: entry write (store-write-then-navigate)  ·  dep: T3, T5
- [ ] **T6.** `frontend/components/learn/SkillDetailView.tsx` `CoachEntryBlock` (`:370-390`): replace
  the bare `<Link href={screen('coach').route}>` (`:381`) with
  `setCoachPin({ kind:'lesson', skillId: block.skillId, label: block.skillName }, 'pre_submit')` then
  navigate — mirror the quiz precedent (`quiz_coach_pin.ts` / the quiz page's pin-write). Test
  `SkillDetailView.test.tsx::Open coach writes a lesson pin + navigates` (**FR-3**). GREEN.

### T7 — GREEN: no-middleware grep-guard + E2E  ·  dep: T4, T5, T6
- [ ] **T7a.** Grep-guard **FR-7**: `git diff --stat middleware/` = empty; `grep -r question_id
  middleware/` unchanged vs base. The lesson `coach_context` flows opaquely; the `agent_id` branch is
  untouched. Confirm `check:*` scripts green.
- [ ] **T7b.** New `frontend/e2e/learn/skill-coach-seed.spec.ts` (**FR-8**, L4): open the coach from a
  `returning` lesson → assert skill-pinned, `pre_submit` mode, **no** current-item panel. Also add the
  edge-case assert from spec §6: a spoofed lesson-context carrying a `question_id` marker still fails
  closed to `pre_submit` (no answer reveal) — the sanitizer's existing rule.

### T8 — full gate + evidence  ·  dep: all
- [ ] **T8.** From `frontend/`: `pnpm test` + `pnpm test:arch` + `pnpm typecheck` +
  `pnpm test:e2e:learn` (new skill-coach-seed spec). **Paste** the FR-1/FR-2 red→green output and the
  E2E run. Confirm the FR-4 exhaustiveness held (typecheck exit-0 with the union in place).

## Definition of Done (mirrors spec §9)
- [ ] FR-1..FR-8 implemented; FR-1 (stale-pin overwrite) + FR-2 (null→valid lesson context) RED first.
- [ ] `CoachSurfacePin` discriminated union; every consumer exhaustive (typecheck proves it).
- [ ] E2E: coach from a `returning` lesson lands skill-pinned, `pre_submit`, no item panel.
- [ ] No middleware diff (grep-guard green); no `skill_state`/DB change.
- [ ] `make check` / `pnpm test`+`test:arch`+`typecheck` green + learn-e2e green.
- [ ] ADR-0030 flipped to `accepted`; ratchet convention satisfied.
- [ ] Actual output pasted for FR-1/FR-2 red→green + the E2E run.

## Landmines (measured this session — do not re-discover)
- **The union is the enforcement mechanism, not a nicety.** Do the pin-type change **first** (T3a) and
  let `pnpm typecheck` enumerate the consumers. Reset logic keys on `questionId` **equality**
  (`use_coach.ts:110`, `coach_thread_store.ts:104,116`) — a *nullable* field (the rejected alternative)
  would silently mis-reset. That is exactly why ADR-0030 chose the union.
- **NO middleware change — verify it, don't assume it.** `middleware/` branches on `agent_id`, carries
  `coach_context` opaquely; grep `question_id` in `middleware/` = 0. FR-7 is a *guard*, not a task to
  do work in middleware.
- **Sanitizer already fails closed** to `pre_submit` on absent `question_id`
  (`coach_context_sanitizer.ts:31,63`) — you are *reusing* the security property, not adding one. Do not
  add a new mode branch; a lesson context must simply carry no `question_id`.
- **Do not fabricate a placeholder Question** for the lesson pin (rejected in ADR-0030) — it risks the
  answer-leakage lint surface and violates honest-null (AP-6). Omit the question; don't fake it.
- **ts-morph arch flake** ([[frontend-vitest-tsmorph-timeout-artifact]]): a lone `test:arch` failure
  under full-run load is the flake — re-run isolated before treating it as a regression.
- **`timeout` is not on macOS** — run `pnpm typecheck` directly.
