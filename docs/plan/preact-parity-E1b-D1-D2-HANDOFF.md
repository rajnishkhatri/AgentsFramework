---
title: 'E1b-D1 + D2 — implementation handoff manifest (for a fresh coding-agent session)'
type: handoff
sub_epic: E1b
covers: [D1, D2]
status: Ready to implement — 2026-07-12
branch: feat/preact-parity-epic-E
---

# E1b D1 + D2 — coding-agent handoff

**You are picking up two independent, ready-to-implement deliverables of Epic E1b (`/learn/skill`).**
All design/spec/plan/ADR/tasks artifacts are already written and on disk. Your job is to **implement
them red→green** following the tasks files. Do **not** re-run brainstorm or re-derive the specs.

## TL;DR — what to build

| Dir | One-line goal | Independence | ADR / decision |
|-----|---------------|--------------|----------------|
| **D1** | Per-skill **answer-accuracy** read + render the dormant `accuracyStat` block (value + 6-bar trend), never conflated with FSRS mastery. | Independent of D0/D2. | `decisions.md` line (method-on-existing-port); ADR-**0031** only if a reviewer deems it port-level. |
| **D2** | **Skill-only coach seed**: "Open coach" on a lesson opens **pinned to that skill**, `pre_submit`, no `question_id`; fix the cold-open-against-stale-pin bug. | Independent of D0/D1. | **ADR-0030** (already written, `status: proposed` → flip to `accepted`). |

D1 and D2 **share no files** — do them in any order, or in parallel via separate worktrees.

## The single source of truth (read in this order)

**D1:**
1. `docs/plan/preact-parity-E1b-D1-accuracy-read.spec.md` — the *what* (EARS FR-1..FR-8, OQ-1 resolved).
2. `docs/plan/preact-parity-E1b-D1-accuracy-read.plan.md` — the *how* (file-level touchpoints).
3. `docs/plan/preact-parity-E1b-D1-accuracy-read.tasks.md` — **the atomic checklist you execute** (T1..T8).

**D2:**
1. `docs/plan/preact-parity-E1b-D2-coach-seed.spec.md` — the *what* (EARS FR-1..FR-8).
2. `docs/plan/preact-parity-E1b-D2-coach-seed.plan.md` — the *how*.
3. `docs/adr/0030-lesson-coach-seed-contract.md` — the *why* (union + honest-null + rejected options).
4. `docs/plan/preact-parity-E1b-D2-coach-seed.tasks.md` — **the atomic checklist you execute** (T1..T8).

**Shared context (optional but useful):**
- `docs/plan/preact-parity-epic-E1b.brainstorm.md` — Stage-1 origin (why tier-1 was deferred, the 3-way split).
- `docs/adr/0028-lesson-content-read-path.md` — the read-seam pattern D1 mirrors; E1a shipped coachEntry inert.
- `docs/adr/0029-mastery-from-stability.md` — D0 (already implemented); explains why mastery ≠ accuracy.

## Full artifact inventory (everything that exists for D1 + D2)

### Already on disk — DO NOT recreate
| Path | Kind | Status |
|------|------|--------|
| `docs/plan/preact-parity-epic-E1b.brainstorm.md` | Stage-1 brainstorm | Accepted |
| `docs/plan/preact-parity-E1b-D1-accuracy-read.spec.md` | D1 spec | Approved |
| `docs/plan/preact-parity-E1b-D1-accuracy-read.plan.md` | D1 plan | Draft (approved verbally) |
| `docs/plan/preact-parity-E1b-D1-accuracy-read.tasks.md` | **D1 tasks** | Ready |
| `docs/plan/preact-parity-E1b-D2-coach-seed.spec.md` | D2 spec | Approved |
| `docs/plan/preact-parity-E1b-D2-coach-seed.plan.md` | D2 plan | Draft (approved verbally) |
| `docs/plan/preact-parity-E1b-D2-coach-seed.tasks.md` | **D2 tasks** | Ready |
| `docs/adr/0030-lesson-coach-seed-contract.md` | ADR (D2) | proposed → flip to accepted |
| `docs/adr/index.md`, `docs/adr/log.md` | OKF entries for 0029+0030 | already appended |
| `docs/adr/decisions.md` | exists (75 KB) | append the D1 OQ-1 line here |

### You will CREATE (net-new source files)
**D1:**
- `frontend/lib/translators/accuracy_vm.ts` — pure `toAccuracyVM(rows)→{valuePct,bars}|null`.
- `frontend/lib/translators/accuracy_vm.test.ts` — FR-3/FR-5/FR-6.
- `frontend/components/learn/AccuracyBars.tsx` — 6-bar chart primitive (hand-built progressbar idiom).
- (fixture) a ≥6-session multi-skill learner in `frontend/lib/adapters/engine/_dev_seed.ts` or a test fixture.
- 1 line in `docs/adr/decisions.md` (OQ-1 window + seam choice). ADR-**0031** only if escalated.

**D2:**
- `frontend/e2e/learn/skill-coach-seed.spec.ts` — L4 open-coach-from-lesson E2E.
- (ADR-0030 already exists — just flip status.)

### You will EDIT (existing seams — all path-verified 2026-07-12)
**D1 read layer:**
- `frontend/lib/ports/engine/attempt_repo.ts` — add `accuracyBySkill(...)` method.
- `frontend/lib/adapters/engine/db/engine_db.ts` — add `accuracyRowsBySkill(...)` to the interface.
- `frontend/lib/adapters/engine/db/in_memory_engine_db.ts` — implement (mirror `listSessionSkillIds` at `:271`).
- `frontend/lib/adapters/engine/db/drizzle_engine_db.ts` — implement w/ COALESCE join (`:500-534`).
- `frontend/lib/adapters/engine/repos/drizzle_attempt_repo.ts` — passthrough (mirror `servedSkillIds` at `:69`).
- `frontend/lib/wire/engine_entities.ts` — declare `SkillAccuracyRow` (+ `AccuracyBySkill` type).

**D1 render layer:**
- `frontend/components/learn/use_skill_detail.ts` — wire the read (`:51-55` Promise.all; replace `accuracy: null` at `:96`).
- `frontend/lib/translators/skill_detail_vm.ts` — add `accuracyStat` BlockVM variant (`:95`); replace `return null` at `:370`; thread `masteryPct`.
- `frontend/components/learn/SkillDetailView.tsx` — add the `accuracyStat` renderer (`CoachEntryBlock` neighbor; `resolveBlock` switch near `:434`).

**D2:**
- `frontend/lib/translators/coach_surface_vm.ts` — `CoachSurfacePin` → discriminated union (`:24-28`).
- `frontend/lib/wire/<coach context type>` — add the lesson variant of `WireCoachContext`.
- `frontend/lib/translators/assemble_coach_context.ts` — lesson branch, skip questionId guard (`:43-55`, guard at `:48`).
- `frontend/components/coach/coach_thread_store.ts` — branch-aware `setCoachPin`/reset (`:96-130`). **← NOTE: the D2 spec §4 mis-cites this at `lib/adapters/engine/`; the real path is `components/coach/`. The plan is correct.**
- `frontend/components/coach/use_coach.ts` — skip `questionRepo.get` for lesson pins (`:107-134`, `:110`).
- `frontend/components/learn/SkillDetailView.tsx` — `CoachEntryBlock` bare `<Link href={screen("coach").route}>` at **`:382`** → store-write-then-navigate.
- `frontend/components/quiz/quiz_coach_pin.ts` — tag the item pin `kind:'item'`.

## Ground-truth anchors (verified this session — trust these over your first grep)
- **Dormant D1 render slot:** `skill_detail_vm.ts:366-371` `accuracyStat` case = self-omit guard (`:368`) + unconditional `return null` (`:370`). VM input type already exists: `skill_detail_vm.ts:203` types `accuracy:{valuePct,bars}|null`. You fill a dormant slot; you don't invent the shape.
- **D1 read precedent:** `drizzle_engine_db.ts:500-534` `listSessionSkillIds` is the live COALESCE (question + test_item) join — **reuse the broad join** or ADR-0021 bank attempts drop silently.
- **D2 bare-link bug:** `SkillDetailView.tsx:382` `href={screen("coach").route}` inside `CoachEntryBlock` (`:370`) — no pin write → cold-opens on a stale/null store pin.
- **D2 store-write-then-navigate precedent:** `app/(coach)/learn/quiz/page.tsx` (uses `setCoachPin`) — mirror it.
- **D2 fail-closed security:** `coach_context_sanitizer.ts:31,63` already defaults absent `question_id` → `pre_submit`. Reuse it; do not add a mode branch.

## Non-negotiable working rules (from AGENTS.md — the reviewer enforces these)
1. **Red/green TDD, watch it fail first.** Every FR has a mapped test; the failure-path tests (FR-1/FR-2 in both) must be seen RED before the implementation. A test that never failed proves nothing.
2. **Demand evidence — paste actual output.** `pnpm test`/`test:arch`/`typecheck`/`test:e2e:learn` — paste the real `vitest run` / Playwright output, not "tests pass".
3. **Frontend Ring layering (Inv #3/#4, F-R8):** SDK/Drizzle only in `lib/adapters/**`; ports import `wire/` only; translators are pure L1; no SDK type escapes the adapter. `SkillAccuracyRow` is a plain wire shape.
4. **Serving purity (D1 FR-7):** accuracy is derived from the append-only `attempt` history **only** — never read/write `skill_state`. It's a report, not a scheduler signal.
5. **Honest-null (D2):** omit `question_id`/`question` for a lesson pin — never fabricate a placeholder Question (rejected in ADR-0030; answer-leakage risk).
6. **Do not rename the dev learner** (`Garvit`) or any item-bank content author (`Maya`) — corrupts provenance stamps.
7. **ADR ratchet is Python-path-only** — a pure-frontend change won't trip `test_adr_ratchet.py`. D1's decisions.md line and D2's ADR-0030 are **convention**, not a mechanical gate. Don't wait for a red ratchet test.
8. **`make check` / `pnpm test` green before done.** Commit only when the user asks; branch first if on `main`. End commit messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## Landmines (measured this session — don't re-discover)
- **`timeout` is not on macOS** — run `pnpm typecheck` directly, no `timeout` wrapper.
- **ts-morph arch flake** (`frontend-vitest-tsmorph-timeout-artifact`): a lone `test:arch` failure under full-run CPU load is the flake — re-run isolated before treating it as a regression.
- **`.venv/bin/python` is the only working interpreter** for any Python tooling (e.g. `scripts/okf_lint.py`).
- **Bank attempts drop** if you use the narrow `question`-only join instead of the COALESCE join (D1 T3c).
- **D2 pin-type change first (T3a), then let `pnpm typecheck` enumerate consumers** — that list IS the work-queue. A *nullable* questionId (rejected) would silently mis-reset the thread; the union forces exhaustive handling.

## Current state / where to start
- Branch: `feat/preact-parity-epic-E`.
- **D0 is already implemented** on this tree (uncommitted): `fsrs_scheduler.ts` + `.test.ts` + ADR-0029 + index/log. It ships as its **own PR** (per the D0 spec). D1/D2 do not depend on it landing.
- **Start D1 at task T1**, D2 at task T2 (both tasks files begin with preconditions P0/P1: baseline `pnpm test:arch` + `pnpm typecheck` green first).
- Run each deliverable's `## Definition of Done` before declaring complete.
