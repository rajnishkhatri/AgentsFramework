---
title: 'E1b-D1 — per-skill accuracy read + accuracyStat render: implementation plan'
type: plan
sub_epic: E1b
direction: D1
status: Draft — 2026-07-12
derives_from: docs/plan/preact-parity-E1b-D1-accuracy-read.spec.md
decision: docs/adr/decisions.md   # read-seam is a METHOD on an existing port → decisions.md line, not a new ADR (confirm at build)
---

# E1b-D1 — implementation plan

## Architecture

A read-only vertical slice following the ratified E1a read-seam shape (ADR-0028): **EngineDb
projection → AttemptRepo method → thin loader wiring → pure T1 translator → BlockVM + view + chart
primitive**. Accuracy is computed from the append-only `attempt` history (never `skill_state`), so it
is a report, not a scheduler signal (FR-13 purity). The window (last-6-sessions, one bar per session)
is resolved (OQ-1) — the read returns per-session rows; the translator squashes to `{valuePct, bars}`.

**Seam placement decision:** `accuracyBySkill` is a **method on the existing `AttemptRepo`**, not a new
port (it shares the append-only source + the `attempt → skill_id` join that `servedSkillIds`/`misses`
already use). New port would be over-abstraction. Per ADR-0006 precedent this is a `decisions.md` line,
not a new-port ADR — confirmed at build; if review disagrees, escalate to a full ADR before merge
(ratchet: the ports/adapters change needs the decisions entry or an ADR).

## File-level touchpoints

**Read layer (the honest data):**
| File | Change |
|------|--------|
| `frontend/lib/ports/engine/attempt_repo.ts` | Add `accuracyBySkill(subject, learnerId, skillId, opts?: { sessions?: number }): Promise<AccuracyBySkill>` to the `AttemptRepo` interface + its doc contract (append-only source, `null` on no attempts). |
| `frontend/lib/wire/engine_entities.ts` (or a repo-local type) | `AccuracyBySkill = { valuePct: number; bars: readonly number[] } \| null` — the read result (per-session bars already reduced, or raw per-session rows if the translator does the reduce; plan choice: **read returns per-session `{sessionId, correct, total}[]` newest-first; translator reduces** — keeps SQL simple + the window/reduce testable in the pure layer). Rename result type accordingly (`SkillAccuracyRow[]`). |
| `frontend/lib/adapters/engine/db/engine_db.ts` | Add `accuracyRowsBySkill(subject, learnerId, skillId, sessions): Promise<SkillAccuracyRow[]>` to the `EngineDb` interface (mirrors `listSessionSkillIds` at `:271`). |
| `frontend/lib/adapters/engine/db/in_memory_engine_db.ts` | Implement it: filter `attempt` rows by `question.skill_id === skillId` (via the same join `listSessionSkillIds` uses at `:271`), group by `session_id`, newest-first, take `sessions` (default 6), per row `{correct: Σcorrect, total: Σ}`. |
| `frontend/lib/adapters/engine/db/drizzle_engine_db.ts` | Implement it with the **broader COALESCE join** (`:500-534`, question + test_item) so ADR-0021 bank attempts are counted; `GROUP BY session_id`, `ORDER BY MAX(created_at) DESC`, `LIMIT sessions`. |
| `frontend/lib/adapters/engine/repos/drizzle_attempt_repo.ts` | Passthrough `accuracyBySkill()` → `db.accuracyRowsBySkill(...)`, wrapped in `translate("accuracyBySkill", …)` (mirror `servedSkillIds` at `:69`). |

**Translate + render layer:**
| File | Change |
|------|--------|
| `frontend/lib/translators/accuracy_vm.ts` (new) | Pure `toAccuracyVM(rows: SkillAccuracyRow[]): { valuePct; bars } \| null` — `null` when `rows` empty; `valuePct = round(100 · Σcorrect / Σtotal)` over the ≤6 rows; `bars = rows.map(r => round(100·r.correct/r.total))` newest-first, ≤6 entries (no padding). Mirrors `newest_due_miss.ts`. |
| `frontend/components/learn/use_skill_detail.ts` | In the `Promise.all` (`:51-55`) add `ports.attemptRepo.accuracyBySkill(subject, learnerId, skillId)`; replace `accuracy: null` (`:96`) with `toAccuracyVM(rows)`. Loader stays thin. |
| `frontend/lib/translators/skill_detail_vm.ts` | Add the `accuracyStat` `BlockVM` variant (value, bars, `masteryPct` for the footnote) to the `BlockVM` union (`:95`); replace the unconditional `return null` (`:370`) with the render VM, keeping the `inputs.accuracy == null → null` self-omit (`:368`). Thread `masteryPct` from the skill's `SkillState` into `SkillDetailInputs`. |
| `frontend/components/learn/SkillDetailView.tsx` | Add the `accuracyStat` renderer: the `%`, the caption, the **6-bar trend** (new primitive), and the distinct-from-mastery footnote (FR-BLK-19). |
| `frontend/components/learn/AccuracyBars.tsx` (new) | The 6-bar chart primitive, hand-built from the single-fill progressbar idiom (per FR-BLK-19 / memo §4). Inline-styled, ≤6 bars, a11y-labeled. |

**Fixtures + decisions:**
| File | Change |
|------|--------|
| `frontend/lib/adapters/engine/_dev_seed.ts` (or a test fixture) | A ≥6-session, multi-skill learner so the real-data render is exercisable (the missing E1a fixture). Keep the dev learner (`Garvit`) conventions. |
| `docs/adr/decisions.md` | Line: OQ-1 window = last-6-sessions/1-bar-per-session + the `accuracyBySkill`-as-method seam choice + rejected rolling-days. |

## Migration
None — read-only add over existing `attempt` rows. No schema change.

## Invariants (constitution check)
- **Inv #3/#4:** SQL/Drizzle stays in `adapters/engine/db|repos`; the port imports `wire/` only; the
  translator is pure. No SDK type escapes. `SkillAccuracyRow` is a plain wire shape.
- **FR-13 purity:** derived from `attempt` only; never reads/writes `skill_state`. The FR-7 test guards it.
- **Determinism:** `toAccuracyVM` is pure (L1); the DB read is deterministic given fixed rows.
- **⚠️ Ask-first:** new read seam — **method-on-existing-port → `decisions.md`** (not a new port/ADR).
  If a reviewer deems it port-level, escalate to ADR-0030 before merge. Ratchet: the decisions entry
  (or ADR) covers the ports/adapters change.

## Build order (red→green)
1. `decisions.md` line (window + seam choice) — the *why* before code.
2. **Red (self-omit):** keep `accuracy: null` wiring; add the `accuracyStat` render body; test FR-1/FR-2
   (no data → omit; unavailable → omit, never mastery) — watch fail against the new body first.
3. Green: implement the read (InMemory first — TDD the aggregation), then Drizzle (COALESCE join).
4. `toAccuracyVM` + tests FR-3/FR-5/FR-6 (value/bars/window/no-pad/derived-from-attempt).
5. Wire `use_skill_detail`; author the ≥6-session fixture; test the real-data render.
6. `AccuracyBars` primitive + `SkillDetailView` renderer + FR-4 (% + footnote).
7. `pnpm test` + `test:arch` + `typecheck` + `test:e2e:learn` (skill-lesson); paste self-omit→render output.

## Test → FR map
| FR | Test | Layer |
|----|------|-------|
| FR-1 | `skill_detail_vm.test.ts::no attempts → self-omit` | L1 |
| FR-2 | `skill_detail_vm.test.ts::unavailable → omit, no mastery substitute` | L1 |
| FR-3 | `accuracy_vm.test.ts::value + bars over last 6 sessions` | L1 |
| FR-4 | `SkillDetailView.test.tsx::% + distinct-from-mastery footnote` | L1 |
| FR-5 | `accuracy_vm.test.ts::from attempt.correct, not mastery` | L1 |
| FR-6 | `accuracy_vm.test.ts::3 sessions → 3 bars, no pad` | L1 |
| FR-7 | `drizzle_attempt_repo.test.ts::reads attempt only` | L1 |
| FR-8 | `drizzle_attempt_repo.test.ts::hinted-correct = correct` | L1 |
| read | `engine_repos.test.ts::counts bank(test_item) attempts via COALESCE join` | L2 |
