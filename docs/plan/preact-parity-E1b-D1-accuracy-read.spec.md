---
title: 'E1b-D1 — Per-skill answer-accuracy read + accuracyStat render (/learn/skill)'
type: spec
sub_epic: E1b
direction: D1
status: Approved — 2026-07-12
owner: Rajnish Khatri
derives_from: docs/plan/preact-parity-epic-E1b.brainstorm.md
design_contract:
  - Eng-coach-ui-design/e1-learn-skill-delivery/specs/PreACT-English-Coach-v2-E1-LearnSkill-Implementation-Spec.md  # DATA-ACC-1/2, FR-CMP-10/11/12, FR-BLK-19, GUARD-ACC-1, AC-9/10, OQ-1
  - Eng-coach-ui-design/e1-learn-skill-delivery/specs/Adaptive-Lesson-Decisions.md  # D7-2
related:
  - docs/plan/preact-parity-epic-E1a.spec.md   # §1.1 carve-out this closes; FR-16 self-omit branch
  - docs/adr/0028-lesson-content-read-path.md  # the read-port pattern this mirrors
  - docs/plan/preact-parity-E1b-D0-mastery-write-path.spec.md  # sibling: mastery≠accuracy is the whole point
governs:
  - docs/plan/preact-parity-E1b-D1-accuracy-read.plan.md
  - docs/plan/preact-parity-E1b-D1-accuracy-read.tasks.md
adr_trigger: 'LIKELY — new read seam. If added as a METHOD on the existing AttemptRepo (no new port), downgrades to a decisions.md line (ADR-0006 precedent); if a new port, full ADR. Plan gate decides. Ratchet applies to the ports/adapters change.'
---

# E1b-D1 — Per-skill answer-accuracy read + `accuracyStat` render

> Closes E1a honest carve-out #1 (spec §1.1): *"`accuracyStat` self-omits. True per-skill
> answer-accuracy has no read today … a follow-up."* This IS the follow-up.

## 1. Goal

On `/learn/skill`, show a learner their **true answer-accuracy** for the skill — the share of
items they've answered **correctly** over a recent window — as the `accuracyStat` block (value +
6-bar trend), rendered **only when real data exists** and **never** conflated with the FSRS
mastery scalar. For every returning/learning learner with session history on that skill.

## 2. Context

**The design contract (verbatim anchors):**
- `DATA-ACC-1` ([design spec:141](../../Eng-coach-ui-design/e1-learn-skill-delivery/specs/PreACT-English-Coach-v2-E1-LearnSkill-Implementation-Spec.md)):
  `accuracyStat.value` is **true answer-accuracy over a real session window** — share correct —
  **not** the FSRS mastery/retrievability scalar (D7-2). *"Rendering mastery under an Accuracy
  label ships the known dashboard bug."* (That bug is E1b-D0.)
- `FR-BLK-19` (design spec:225): value + **6-bar trend** + caption; the numeric % **always
  rendered alongside** the bars; a footnote **distinct from mastery** ("Not your mastery estimate
  ({masteryPct}%) — accuracy is a different number").
- `FR-CMP-10/11/12` (design spec:191): gated on **data availability, not the context label**;
  **empty-state and forward-placeholder rejected** (a 6-bar trend on zero sessions is fabricated);
  when unavailable, **omit** rather than substitute the mastery scalar.
- `GUARD-ACC-1` (design spec:240): never render the mastery scalar under the "Accuracy" label.

**The implementation reality (audited):**
- The VM already types the input: [`skill_detail_vm.ts:203`](../../frontend/lib/translators/skill_detail_vm.ts:203)
  `accuracy: { valuePct: number; bars: readonly number[] } | null` — but the caller hard-codes
  `accuracy: null` ([`use_skill_detail.ts:96`](../../frontend/components/learn/use_skill_detail.ts:96)),
  and `resolveBlock`'s `accuracyStat` case returns `null` unconditionally
  ([`skill_detail_vm.ts:366-371`](../../frontend/lib/translators/skill_detail_vm.ts:366)) — an
  **authored-dormant** render path. `accuracyStat` is in all three `RAIL_RECIPES` (`:235-237`).
- **No accuracy read exists.** `AttemptRepo` exposes `misses`/`servedQuestionIds`/`servedSkillIds`
  ([`attempt_repo.ts:37-60`](../../frontend/lib/ports/engine/attempt_repo.ts:37)) — the last two
  already **join `attempt → question.skill_id`** and read the append-only `attempt` rows.
- **Raw data is present + joinable + proven in prod:** `attempt.correct` + the
  `attempt.question_id → skill_id` LEFT JOIN (COALESCE question + test_item) is live at
  [`drizzle_engine_db.ts:500-534`](../../frontend/lib/adapters/engine/db/drizzle_engine_db.ts:500)
  (`listSessionSkillIds`). Accuracy = `count(correct)/count(*)` grouped by skill needs **no new
  capture** — only a new read projection.
- **No 6-bar chart primitive exists** (E1a carve-out) — net-new render primitive.

## Clarify resolutions (2026-07-12, pre-plan)

- **OQ-1 RESOLVED — window = last-6-sessions, per bar = per-session accuracy.** The block shows a
  **6-bar trend**, so the natural, coupled window is the learner's **6 most recent closed sessions
  that included ≥1 attempt on this skill**, newest bar = newest session. `accuracyStat.value` = the
  aggregate accuracy across those 6 sessions' on-skill attempts (correct / total). Rationale: (i)
  the bar count IS the window — one bar per session avoids an arbitrary second parameter; (ii)
  "sessions" (not rolling days) matches the rest of the engine, which is session-structured
  (`listClosedSessionsByLearner`, S3 bounded sessions); (iii) fewer than 6 qualifying sessions →
  fewer bars (no fabricated/padded bars — FR-CMP-11). Rejected: rolling-days (needs a second
  constant; empty for inactive learners; misaligns with the session model). *Recorded here; a
  one-line ADR/decisions entry ratifies at the plan gate.*
- **Read placement = new METHOD on `AttemptRepo` (not a new port).** `accuracyBySkill(subject,
  learnerId, skillId, opts?)` sits beside `misses`/`servedSkillIds` (same append-only source, same
  join). Keeps the port count flat → likely a `decisions.md` line, not a new-port ADR (ADR-0006
  precedent). Plan gate confirms against ADR-0014/0015.
- **Aggregation lives in a T1 translator**, not the loader — `use_skill_detail` stays thin, passes
  the read result into `toSkillDetailVM({… accuracy})`; a pure `toAccuracyVM(perSessionRows)` maps to
  `{valuePct, bars[]}`. Mirrors `newest_due_miss.ts`.
- **`masteryPct` for the footnote** is already available in the VM inputs (the skill's `SkillState`)
  — the "distinct from mastery" footnote (FR-BLK-19) reads it; **post-D0** that number is itself
  honest, so D1 and D0 compose (D1 does not depend on D0 landing, but the footnote reads better after).

## 3. Functional requirements (EARS)

Failure paths first.

- **FR-1 (unwanted).** IF the learner has **no attempts** on the skill (true first exposure) THEN
  THE SYSTEM SHALL render **no `accuracyStat` block** (self-omit) — never a zero-bar or padded trend.
  ⟶ `DATA-ACC-2`, `FR-CMP-11`, `AC-9`.
- **FR-2 (unwanted).** IF real per-skill accuracy is unavailable for any reason THEN THE SYSTEM
  SHALL **omit** the block, and SHALL NOT substitute the FSRS `mastery`/retrievability scalar under
  the Accuracy label. ⟶ `GUARD-ACC-1`, `FR-CMP-12`.
- **FR-3 (event-driven).** WHEN the learner has ≥1 on-skill attempt THE SYSTEM SHALL compute
  `accuracyStat.value` as **correct ÷ total** over the last **6 qualifying sessions**' on-skill
  attempts, and `bars[]` as **per-session accuracy** newest-first, ≤6 bars. ⟶ `DATA-ACC-1`, OQ-1.
- **FR-4 (ubiquitous).** THE SYSTEM SHALL render the numeric accuracy **%** alongside the bars and
  a footnote asserting it is **distinct from mastery** ("Not your mastery estimate ({masteryPct}%)
  — accuracy is a different number"). ⟶ `FR-BLK-19`, `AC-10`.
- **FR-5 (ubiquitous).** THE SYSTEM SHALL derive accuracy **only** from `attempt.correct` over the
  `attempt → skill_id` join — **never** from `SkillState.mastery`/retrievability. ⟶ `D7-2`.
- **FR-6 (state-driven).** WHILE fewer than 6 qualifying sessions exist THE SYSTEM SHALL render
  exactly that many bars (e.g. 3 sessions → 3 bars), never pad to 6. ⟶ `FR-CMP-11`.
- **FR-7 (ubiquitous).** THE SYSTEM SHALL compute accuracy over the append-only `attempt` history
  and SHALL NOT read or write `skill_state` for it (serving-purity: the accuracy read is a report,
  not a scheduler signal). ⟶ FR-13 purity, ADR-0006.
- **FR-8 (event-driven).** WHEN a hinted-but-correct attempt is counted THE SYSTEM SHALL count it
  as **correct** (hints never change recorded correctness). ⟶ `attempt_repo.ts` FR-D5.

## 4. Data model / contracts

- **New read method (no schema change):** `AttemptRepo.accuracyBySkill(subject, learnerId, skillId,
  opts?: { sessions?: number }): Promise<AccuracyBySkill>` where
  `AccuracyBySkill = { valuePct: number; bars: readonly number[] } | null` (null when no attempts).
  Backed by a new `EngineDb` projection GROUP BY session over the existing `attempt → skill_id` join.
  Implement in **InMemory** + **Drizzle** engine DBs; passthrough in `DrizzleAttemptRepo`.
- **VM wiring:** flip [`use_skill_detail.ts:96`](../../frontend/components/learn/use_skill_detail.ts:96)
  from `accuracy: null` to the `toAccuracyVM(read)` result; the VM input type already matches
  ([`skill_detail_vm.ts:203`](../../frontend/lib/translators/skill_detail_vm.ts:203)).
- **New BlockVM variant + renderer:** add the `accuracyStat` `BlockVM` shape (value + bars + footnote
  fields), replace the `return null` at `skill_detail_vm.ts:370` with the render body (keeping the
  `inputs.accuracy == null → null` self-omit at `:368`), and add the `SkillDetailView` renderer + a
  **6-bar chart primitive** (hand-built from the single-fill progressbar idiom, per FR-BLK-19).
- **Composition:** the new method rides the existing `AttemptRepo` already wired in
  `composition_engine.ts`; no new composition field if it's a method (confirm at plan).

## 5. Invariants & security boundaries

- **Frontend Ring layering:** new read = port method (imports `wire/` only) → Drizzle adapter (SDK/DB
  isolation, F-R8, in `adapters/engine/repos|db/`) → T1 pure translator (`toAccuracyVM`) → view. No SDK
  type escapes the adapter. `use_skill_detail` composition unchanged except the one arg.
- **Determinism:** `toAccuracyVM` is pure (L1). The read is deterministic given fixed `attempt` rows.
- **Serving purity (FR-13):** accuracy is derived from `attempt` only, never `skill_state` — it is a
  read-report, does not feed `Scheduler.next()`. (FR-7.)
- **ADR trigger:** new read seam → ADR-or-`decisions.md` (plan gate). Ratchet enforced on ports/adapters.

## 6. Edge cases

- **Exactly 1 session, 1 attempt** → 1 bar, value = 0% or 100%; renders (not self-omit). Honest.
- **Sessions with 0 on-skill attempts** are **not** bars (only qualifying sessions count) — a learner
  who did other skills doesn't get empty bars.
- **All-wrong on the skill** → `value = 0%`, bars all 0 — renders a truthful 0% (the exact opposite
  of the D0 dashboard bug; this block must show it, not hide it).
- **Bank/test_item items** (ADR-0021) must be counted — the read MUST reuse the broader COALESCE
  join (`drizzle_engine_db.ts:500-534`), or bank attempts silently drop.
- **`>6` qualifying sessions** → take the newest 6 only; older sessions excluded from both value + bars
  (decision: value is windowed to the same 6 as the bars, for consistency — stated in FR-3).

## 7. Non-functional requirements

- **First paint / NFR-PERF-1:** the read is one indexed GROUP BY; the block is inline-styled, streams
  top-to-bottom. No blocking CSS.
- **L1/L2:** translator + read are deterministic; a **≥6-session multi-skill fixture** must be authored
  to test the real-data render (the E1a carve-out noted no such fixture exists).
- **No live LLM** — fully offline/deterministic (NFR-OFFLINE-1).

## 8. Test plan

Failure-path (FR-1/FR-2) first. All L1 in `make check` except where a fixture is L2.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `skill_detail_vm.test.ts::no attempts → accuracyStat self-omits` | L1 | yes |
| FR-2 | `skill_detail_vm.test.ts::accuracy unavailable → omit, never mastery substitute` | L1 | yes |
| FR-3 | `accuracy_vm.test.ts::value = correct/total over last 6 sessions; bars newest-first` | L1 | yes |
| FR-4 | `SkillDetailView.test.tsx::renders % alongside bars + distinct-from-mastery footnote` | L1 | yes |
| FR-5 | `accuracy_vm.test.ts::derived from attempt.correct, never SkillState.mastery` | L1 | yes |
| FR-6 | `accuracy_vm.test.ts::3 sessions → exactly 3 bars, no padding` | L1 | yes |
| FR-7 | `drizzle_attempt_repo.test.ts::accuracyBySkill reads attempt only, not skill_state` | L1 | yes |
| FR-8 | `drizzle_attempt_repo.test.ts::hinted-correct counts as correct` | L1 | yes |
| read | `engine_repos.test.ts::accuracyBySkill join counts bank(test_item) attempts` | L2 (fixture) | yes |

> **Fixture:** author a ≥6-session, multi-skill learner fixture (the missing E1a fixture) so FR-3/FR-6
> exercise the real-data render, not just the self-omit branch.

## 9. Definition of Done

- [ ] FR-1..FR-8 implemented; FR-1/FR-2 (self-omit / no-substitute) seen to fail first against the
      current `return null` stub only after the stub is replaced (i.e. red on the new render body).
- [ ] `accuracyBySkill` in InMemory + Drizzle; the ≥6-session fixture authored and green.
- [ ] 6-bar chart primitive added; `%` + distinct-from-mastery footnote render (FR-BLK-19).
- [ ] `make check` green (vitest + arch + typecheck); AC-9/AC-10 satisfied.
- [ ] OQ-1 window (last-6-sessions) ratified in `decisions.md`; read-seam ADR-or-`decisions.md` filed.
- [ ] Actual `vitest run` output pasted for the self-omit→render transition.
