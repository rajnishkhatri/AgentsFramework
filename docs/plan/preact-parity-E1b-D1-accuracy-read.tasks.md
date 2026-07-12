---
title: 'E1b-D1 — per-skill accuracy read + accuracyStat render: task checklist'
type: tasks
sub_epic: E1b
direction: D1
status: Ready — 2026-07-12
derives_from: docs/plan/preact-parity-E1b-D1-accuracy-read.plan.md
spec: docs/plan/preact-parity-E1b-D1-accuracy-read.spec.md
---

# E1b-D1 — task checklist

> **Read first (in order):** the [spec](preact-parity-E1b-D1-accuracy-read.spec.md) (the *what* +
> EARS FR-1..FR-8), then the [plan](preact-parity-E1b-D1-accuracy-read.plan.md) (the *how* +
> file-level touchpoints). This file is the atomic decomposition — one testable unit per task,
> dependency-ordered, red→green. Do NOT skip the red step: watch each failure-path test fail first.

## Checklist quality gate ("unit tests for English")

Every EARS criterion is measurable and has a mapped test — verified:

| FR | Measurable claim | Test that measures it |
|----|------------------|-----------------------|
| FR-1 | no attempts → no `accuracyStat` block | `skill_detail_vm.test.ts` self-omit |
| FR-2 | unavailable → omit, never mastery substitute | `skill_detail_vm.test.ts` no-substitute |
| FR-3 | value = correct/total over last 6 sessions; bars newest-first | `accuracy_vm.test.ts` |
| FR-4 | numeric % + distinct-from-mastery footnote rendered | `SkillDetailView.test.tsx` |
| FR-5 | derived from `attempt.correct`, never `SkillState.mastery` | `accuracy_vm.test.ts` |
| FR-6 | 3 sessions → exactly 3 bars, no padding | `accuracy_vm.test.ts` |
| FR-7 | reads `attempt` only, never `skill_state` | `drizzle_attempt_repo.test.ts` |
| FR-8 | hinted-but-correct counts as correct | `drizzle_attempt_repo.test.ts` |
| read | bank(test_item) attempts counted via COALESCE join | `engine_repos.test.ts` (L2) |

All criteria measurable → **no flags back to the spec.**

## Preconditions (do once, before Task 1)

- [ ] **P0.** Working from branch `feat/preact-parity-epic-E`. D0 (`fsrs_scheduler.ts` +
  `fsrs_scheduler.test.ts` + ADR-0029 + index/log) is **already implemented** on this tree
  (uncommitted, or committed as its own PR). D1 does **not** depend on D0 landing — the footnote
  reads `masteryPct` regardless — but if D0 is unmerged, the footnote number is the honest one.
- [ ] **P1.** `cd frontend && pnpm install` clean; baseline green: `pnpm test:arch` +
  `pnpm typecheck` before touching anything (per SDD Stage-4 baseline rule).

## Tasks (dependency-ordered, red→green)

### T1 — decisions.md line (the *why* before code)  ·  no dep
- [ ] **T1.** Append to `docs/adr/decisions.md` (2–4 lines): OQ-1 window = **last-6-sessions,
  1 bar/session** (bar count IS the window; rejected rolling-days — needs a 2nd constant, empty for
  inactive learners, misaligns with the session model) **and** the seam choice: `accuracyBySkill` is
  a **method on the existing `AttemptRepo`** (not a new port), ADR-0006 precedent. If a reviewer deems
  it port-level at review, escalate to a full ADR (next free number is **0031**) before merge.
- **Verify:** `.venv/bin/python scripts/okf_lint.py` → 0 new failures (the `:line`-anchored-link warning
  is pre-existing repo-wide, not introduced here).

### T2 — RED: author the render body + its failure-path tests  ·  dep: T1
> The self-omit path must be seen to fail against the **new render body**, not the old `return null`.
- [ ] **T2a.** In `frontend/lib/translators/skill_detail_vm.ts`: add the `accuracyStat` `BlockVM`
  variant to the union (`:95`) — fields `{ kind:'accuracyStat'; valuePct: number; bars: readonly
  number[]; masteryPct: number | null }`. Thread `masteryPct` from the skill's `SkillState` into
  `SkillDetailInputs` (for the FR-4 footnote).
- [ ] **T2b.** Replace the unconditional `return null` at `skill_detail_vm.ts:370` with the render VM,
  **keeping** the `inputs.accuracy == null → null` self-omit at `:368`.
- [ ] **T2c.** Add `skill_detail_vm.test.ts` cases: **FR-1** (`accuracy: null` because no attempts →
  block omitted) and **FR-2** (`accuracy: null` for any reason → omitted, and assert the VM never
  emits `mastery` under an accuracy label). **Run → RED** (these must fail meaningfully against the new
  body, i.e. prove the self-omit branch is exercised). Paste the failing output.

### T3 — GREEN read layer: EngineDb projection (InMemory first)  ·  dep: T2
- [ ] **T3a.** Add to the `EngineDb` interface (`frontend/lib/adapters/engine/db/engine_db.ts`):
  `accuracyRowsBySkill(subject, learnerId, skillId, sessions): Promise<SkillAccuracyRow[]>` where
  `SkillAccuracyRow = { sessionId: string; correct: number; total: number }` (newest-first). Mirror the
  signature style of `listSessionSkillIds` (`:271`). Declare `SkillAccuracyRow` in the wire/entities
  layer (`frontend/lib/wire/engine_entities.ts`) or a repo-local type per the plan.
- [ ] **T3b.** Implement in `frontend/lib/adapters/engine/db/in_memory_engine_db.ts`: filter `attempt`
  rows by `question.skill_id === skillId` (same join `listSessionSkillIds` uses at `:271`), group by
  `session_id`, newest-first, take `sessions` (default 6), each row `{correct: Σcorrect, total: Σ}`.
  **TDD the aggregation here** — it's the deterministic core.
- [ ] **T3c.** Implement in `frontend/lib/adapters/engine/db/drizzle_engine_db.ts` with the **broader
  COALESCE join** (`:500-534`, question + test_item) so ADR-0021 bank attempts count; `GROUP BY
  session_id`, `ORDER BY MAX(created_at) DESC`, `LIMIT sessions`.

### T4 — GREEN read layer: AttemptRepo method + passthrough  ·  dep: T3
- [ ] **T4a.** Add to `frontend/lib/ports/engine/attempt_repo.ts`:
  `accuracyBySkill(subject, learnerId, skillId, opts?: { sessions?: number }): Promise<AccuracyBySkill>`
  + doc contract (append-only source; `null` on no attempts). Type
  `AccuracyBySkill = { valuePct: number; bars: readonly number[] } | null`.
- [ ] **T4b.** Passthrough in `frontend/lib/adapters/engine/repos/drizzle_attempt_repo.ts`:
  `accuracyBySkill()` → `toAccuracyVM(await db.accuracyRowsBySkill(...))`, wrapped in
  `translate("accuracyBySkill", …)` (mirror `servedSkillIds` at `:69`).
- [ ] **T4c.** Tests **FR-7** (reads `attempt` only, never `skill_state`) + **FR-8** (hinted-correct
  counts as correct) in `drizzle_attempt_repo.test.ts`. GREEN.

### T5 — GREEN translator (pure L1)  ·  dep: T3 (needs SkillAccuracyRow)
- [ ] **T5a.** New `frontend/lib/translators/accuracy_vm.ts`:
  `toAccuracyVM(rows: SkillAccuracyRow[]): { valuePct; bars } | null` — `null` when `rows` empty;
  `valuePct = round(100 · Σcorrect / Σtotal)` over the ≤6 rows; `bars = rows.map(r =>
  round(100·r.correct/r.total))` newest-first, ≤6 entries, **no padding**. Pure. Mirror
  `newest_due_miss.ts`.
- [ ] **T5b.** `accuracy_vm.test.ts`: **FR-3** (value + bars over last 6 sessions), **FR-5** (from
  `attempt.correct`, not mastery — assert the function never touches a mastery field), **FR-6** (3
  sessions → 3 bars, no pad). GREEN.

### T6 — GREEN wiring + fixture  ·  dep: T4, T5
- [ ] **T6a.** `frontend/components/learn/use_skill_detail.ts`: in the `Promise.all` (`:51-55`) add
  `ports.attemptRepo.accuracyBySkill(subject, learnerId, skillId)`; replace `accuracy: null` (`:96`)
  with the read result. Loader stays thin (no aggregation in the loader).
- [ ] **T6b.** Author a **≥6-session, multi-skill learner fixture** in
  `frontend/lib/adapters/engine/_dev_seed.ts` (or a test fixture) — the missing E1a fixture. Keep the
  dev learner conventions (dev learner is **Garvit** — do not rename). This makes FR-3/FR-6 exercise the
  real-data render, not just the self-omit branch.
- [ ] **T6c.** L2 read test `engine_repos.test.ts::accuracyBySkill join counts bank(test_item)
  attempts` (COALESCE join over a fixture that includes a `test_item` attempt). GREEN.

### T7 — GREEN render: chart primitive + view  ·  dep: T2, T6
- [ ] **T7a.** New `frontend/components/learn/AccuracyBars.tsx`: the **6-bar chart primitive**,
  hand-built from the single-fill progressbar idiom (per FR-BLK-19). Inline-styled, ≤6 bars,
  a11y-labeled (each bar `role="img"` / `aria-label` with its %; the group labeled). No external chart lib.
- [ ] **T7b.** `frontend/components/learn/SkillDetailView.tsx`: add the `accuracyStat` renderer — the
  `%`, the caption, the `<AccuracyBars>` trend, and the **distinct-from-mastery footnote** ("Not your
  mastery estimate ({masteryPct}%) — accuracy is a different number"). If `masteryPct == null`, render
  the footnote without the parenthetical number (honest-absent).
- [ ] **T7c.** `SkillDetailView.test.tsx::FR-4` — renders `%` alongside bars + the distinct-from-mastery
  footnote. Flip T2's FR-1/FR-2 to GREEN (self-omit still holds; real data now renders). GREEN.

### T8 — full gate + evidence  ·  dep: all
- [ ] **T8.** From `frontend/`: `pnpm test` + `pnpm test:arch` + `pnpm typecheck` +
  `pnpm test:e2e:learn` (skill-lesson). **Paste the actual `vitest run` output** for the
  self-omit→render transition (the FR-1/FR-2 red→green) and the arch/typecheck exit-0. "Tests pass"
  without the output is not a result (AGENTS.md demand-evidence rule).

## Definition of Done (mirrors spec §9)
- [ ] FR-1..FR-8 implemented; FR-1/FR-2 seen RED on the new render body first.
- [ ] `accuracyBySkill` in InMemory + Drizzle; ≥6-session fixture authored + green.
- [ ] 6-bar primitive; `%` + distinct-from-mastery footnote (FR-BLK-19).
- [ ] `make check` / `pnpm test`+`test:arch`+`typecheck` green; AC-9/AC-10 satisfied.
- [ ] OQ-1 window ratified in `decisions.md`; read-seam decisions-line (or ADR-0031 if escalated) filed.
- [ ] Actual `vitest run` output pasted for the self-omit→render transition.

## Landmines (measured this session — do not re-discover)
- **`timeout` is not on macOS** — run `pnpm typecheck` directly, no `timeout` wrapper.
- **ts-morph arch flake:** the frontend arch suite can fail *under full-run CPU load* and pass in
  isolation ([[frontend-vitest-tsmorph-timeout-artifact]]). Trust an isolated re-run of
  `pnpm test:arch`; a lone arch failure amid a green full run is the flake, not a regression.
- **The ADR ratchet (`test_adr_ratchet.py`) triggers on Python paths only** — a pure-frontend change
  does not trip it mechanically. The decisions.md line here is by **convention** (ports/adapters change),
  not because the ratchet forces it. Do not wait for a red ratchet test that will never fire.
- **Bank attempts drop silently** if you use the narrow `question`-only join instead of the COALESCE
  (question + test_item) join at `drizzle_engine_db.ts:500-534`. Reuse the broad join (T3c).
- **The VM input type already exists** (`skill_detail_vm.ts:203` types `accuracy:{valuePct,bars}|null`)
  — you are filling a dormant slot, not inventing the shape.
