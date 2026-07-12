---
title: 'E1b-D2 — Skill-only coach seed contract (lesson→coach, no question_id) (/learn/skill)'
type: spec
sub_epic: E1b
direction: D2
status: Approved — 2026-07-12
owner: Rajnish Khatri
derives_from: docs/plan/preact-parity-epic-E1b.brainstorm.md
design_contract:
  - Eng-coach-ui-design/e1-learn-skill-delivery/specs/PreACT-English-Coach-v2-E1-LearnSkill-Implementation-Spec.md  # FR-BLK-20, OQ-3
  - Eng-coach-ui-design/e1-learn-skill-delivery/specs/Adaptive-Lesson-Decisions.md  # D4c
related:
  - docs/plan/preact-parity-epic-E1a.spec.md   # FR-6e coachEntry seam (button-only)
  - docs/adr/0028-lesson-content-read-path.md  # E1a shipped coachEntry inert (:170-171)
governs:
  - docs/plan/preact-parity-E1b-D2-coach-seed.plan.md
  - docs/plan/preact-parity-E1b-D2-coach-seed.tasks.md
adr_trigger: 'YES — OQ-3/D4c is an explicit deferred contract decision (a new coach seed shape). Its own decision record (ADR or decisions.md). Frontend-ring only; NO middleware change.'
---

# E1b-D2 — Skill-only coach seed contract

> Closes OQ-3/D4c: *"the lesson→coach seed contract — how a skill-pinned, lesson-context coach
> entry is expressed when there is no active `question_id`."* E1a shipped the `coachEntry` block
> as a button-only **seam** (FR-BLK-20; ADR-0028:170-171 inert).

## 1. Goal

When a learner clicks **"Open coach"** from a `/learn/skill` lesson, the coach must open
**pinned to that skill** in a lesson context — Socratic, hint-first — **without** an active
`question_id`. Today the button is a bare link that cold-opens the coach against whatever stale
pin sits in the store; this authors the honest skill-only seed. For every `returning`-context
lesson learner.

## 2. Context

**The design contract:**
- `FR-BLK-20` ([design spec:226](../../Eng-coach-ui-design/e1-learn-skill-delivery/specs/PreACT-English-Coach-v2-E1-LearnSkill-Implementation-Spec.md)):
  `coachEntry` is a **skill-pinned entry point** ("pinned to {skill}"); E1: button is the seam,
  the **seed contract is authored in E1b** (D4c). `returning` only.
- `OQ-3` (design spec:331): express a skill-pinned, lesson-context coach entry **when there is no
  active `question_id`**.

**The refuted framing (brainstorm clarify):** it is NOT that "the coach has no skill-only path."
The `/learn/skill` `CoachEntryBlock` is **already a skill-scoped ENTRY** — but it carries **no
seed**: a bare `<Link href={screen("coach").route}>` ([`SkillDetailView.tsx:381`](../../frontend/components/learn/SkillDetailView.tsx:381))
with no pin write, landing the learner on whatever **stale/null pin** sits in the
`coach_thread_store` singleton. What's absent is a skill-only **SEED** that yields a valid
`coach_context`. **This cold-open-against-stale-pin is the real latent bug D2 closes.**

**The two hard blockers (audited):**
1. `CoachSurfacePin.questionId: string` is **required** ([`coach_surface_vm.ts:25`](../../frontend/lib/translators/coach_surface_vm.ts:25)).
2. `assembleCoachContext` returns **null** unless `question != null && question.id === pin.questionId`
   ([`assemble_coach_context.ts:47-48`](../../frontend/lib/translators/assemble_coach_context.ts:47))
   — and `WireCoachContext` requires `question_id` + `question`.

**What's already ready (so this is a narrow widening, not a rebuild):**
- The coach display chrome already runs on **`skillId` alone** (coach page + `coach_surface_vm`
  render `missesOnSkill`/`skillLabel` without a question).
- The BFF sanitizer **already fails closed to `pre_submit`** on absent `question_id`
  ([`coach_context_sanitizer.ts:31,63`](../../frontend/lib/translators/coach_context_sanitizer.ts:31))
  — the **correct default** for a lesson entry (no submitted item).
- The `coachEntry` `BlockVM` already carries `skillId` + `skillName`
  ([`skill_detail_vm.ts:372-382`](../../frontend/lib/translators/skill_detail_vm.ts:372)).
- **No middleware change:** middleware carries `coach_context` opaquely and branches only on
  `agent_id` (orthogonal); grep `question_id` in `middleware/` = 0.

## Clarify resolutions (2026-07-12, pre-plan)

- **Pin shape = discriminated union (human gate HG-5), NOT nullable questionId.** `CoachSurfacePin`
  becomes `{ kind: 'item'; questionId; skillId; label } | { kind: 'lesson'; skillId; label }`.
  Rationale: fresh-thread/transcript-reset logic keys on `questionId` **equality** (`use_coach.ts:110`,
  `coach_thread_store.ts:104,116`); a nullable field would silently mis-reset. The union forces every
  consumer to handle the lesson branch explicitly (exhaustive `switch`).
- **Lesson coach_context = honest-null question.** `assembleCoachContext` gets a **lesson branch**
  that returns a `WireCoachContext` with `skill_id` set and `question_id`/`question` **omitted**
  (a lesson variant of the wire type), NOT a fabricated question. Mode = `pre_submit` (sanitizer default).
- **Entry write = store-write-then-navigate**, mirroring the quiz. Replace the bare `<Link>` in
  `CoachEntryBlock` with `setCoachPin({kind:'lesson', skillId, label}, 'pre_submit')` + navigate,
  mirroring the quiz page's `page.tsx:411-418` precedent. So the coach never cold-opens on a stale pin.
- **Scope = the seed, not the conversation.** The live Socratic conversation already exists; D2 only
  makes the **entry carry a valid skill-only seed**. No new coach UI.

## 3. Functional requirements (EARS)

Failure paths first.

- **FR-1 (unwanted).** IF a learner opens the coach from `/learn/skill` while a **stale item pin**
  from a prior quiz sits in the store THEN THE SYSTEM SHALL **overwrite** it with the current skill's
  lesson pin — the coach SHALL NOT open against the stale question. *(The latent bug.)*
- **FR-2 (unwanted).** IF a lesson pin has **no `questionId`** THEN `assembleCoachContext` SHALL
  return a valid **lesson** `coach_context` (skill_id, no question) — NOT `null`, and NOT a
  fabricated question. ⟶ blocker (2).
- **FR-3 (event-driven).** WHEN the learner clicks "Open coach" in a `returning` lesson THE SYSTEM
  SHALL write a **lesson pin** `{kind:'lesson', skillId, label}` and navigate to the coach, opening it
  **pinned to that skill** in `pre_submit` mode. ⟶ `FR-BLK-20`, D4c.
- **FR-4 (ubiquitous).** THE SYSTEM SHALL represent the coach pin as a **discriminated union**
  (`item` | `lesson`); every consumer SHALL handle both branches (exhaustive). ⟶ HG-5.
- **FR-5 (ubiquitous).** THE SYSTEM SHALL derive coach **mode = `pre_submit`** for a lesson pin (no
  submitted item), via the existing sanitizer's fail-closed default. ⟶ `coach_context_sanitizer.ts:31`.
- **FR-6 (state-driven).** WHILE the pin is a **lesson** pin THE SYSTEM SHALL NOT run the
  `question.id === pin.questionId` guard (there is no question) and SHALL NOT reset the thread on a
  questionId mismatch. ⟶ `assemble_coach_context.ts:48`, `coach_thread_store.ts:104`.
- **FR-7 (ubiquitous).** THE SYSTEM SHALL require **NO middleware change** — the lesson `coach_context`
  flows through the BFF and middleware unchanged (opaque payload; `agent_id` branch untouched).
- **FR-8 (event-driven).** WHEN the coach opens from a lesson pin THE SYSTEM SHALL show the
  skill-scoped chrome (skill label, `missesOnSkill` if available) with **no** current-item panel.

## 4. Data model / contracts

- **`CoachSurfacePin`** ([`coach_surface_vm.ts:24-28`](../../frontend/lib/translators/coach_surface_vm.ts:24)):
  from `{ questionId; skillId; label }` → `{ kind:'item'; questionId; skillId; label } | { kind:'lesson'; skillId; label }`.
- **`WireCoachContext`:** add a lesson variant — `question_id`/`question` **optional/omitted** when a
  lesson context; `skill_id` always present. (Zod discriminated union or optional fields with a `mode`
  guard — plan decides; must keep the existing item shape wire-compatible.)
- **`assembleCoachContext`** ([`assemble_coach_context.ts:43-55`](../../frontend/lib/translators/assemble_coach_context.ts:43)):
  add the lesson branch (skill-only, no question guard).
- **`coach_thread_store`** ([`coach_thread_store.ts:96-130`](../../frontend/lib/adapters/engine/coach_thread_store.ts:96)):
  `setCoachPin` + reset keyed on a skill-branch for lesson pins.
- **`CoachEntryBlock`** ([`SkillDetailView.tsx:370-390`](../../frontend/components/learn/SkillDetailView.tsx:370)):
  bare `<Link>` → store-write-then-navigate.
- **No `skill_state`/`attempt`/DB change; no middleware change.**

## 5. Invariants & security boundaries

- **Frontend Ring layering:** all changes in `lib/translators` (pure) + `lib/adapters/engine`
  (store singleton) + `components/learn` (view). Wire type stays a pure Zod kernel. No SDK escape.
- **Security — fail-closed preserved:** the lesson pin routes to `pre_submit` via the **existing**
  sanitizer default; a lesson context carries **no `question_id`**, so it cannot spoof a
  `post_feedback` answer-reveal. The union makes the honest-null explicit rather than a fabricated
  question (which would risk the answer-leakage surface). ⟶ `coach_context_sanitizer.ts` fail-closed.
- **ADR trigger:** OQ-3/D4c is a named deferred contract → **its own ADR/decisions record** for the
  seed shape (discriminated union + lesson coach_context). Frontend-ring; ratchet applies to the
  translator/wire change.

## 6. Edge cases

- **No prior pin at all** (fresh session) → lesson pin writes cleanly; no reset needed.
- **Item pin then lesson pin** (quiz → lesson → coach) → lesson pin overwrites; thread resets on the
  branch change, not a questionId mismatch (FR-6).
- **Lesson pin then back to quiz** (coach → quiz item) → item pin overwrites; existing item path intact.
- **`missesOnSkill` unavailable** for the lesson pin → chrome renders skill label only (existing
  `missesOnSkill: null` honest-absent path, `coach_surface_vm.ts:37`).
- **Spoofed client sends a lesson context with a `question_id`** → sanitizer still keys mode on the
  marker; a lesson context asserting a submitted marker without a real question fails closed to
  `pre_submit` (no reveal). Assert this.

## 7. Non-functional requirements

- **L1 deterministic** — translators + store are pure/local; no live LLM in the seed path (the
  conversation itself streams live, unchanged, outside this spec's scope).
- **Reversibility:** revert restores the bare link (and the cold-open bug); no persisted state.
- **No new network calls** from the seed; the coach run stream is the pre-existing path.

## 8. Test plan

Failure-path (FR-1/FR-2) first. L1 unit; one L4 behavioral for the end-to-end open.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `coach_thread_store.test.ts::lesson pin overwrites a stale item pin` | L1 | yes |
| FR-2 | `assemble_coach_context.test.ts::lesson pin (no questionId) → valid skill-only context, not null` | L1 | yes |
| FR-3 | `SkillDetailView.test.tsx::Open coach writes a lesson pin + navigates` | L1 | yes |
| FR-4 | `coach_surface_vm.test.ts::pin union — both branches handled (exhaustive)` | L1 | yes |
| FR-5 | `assemble_coach_context.test.ts::lesson pin derives pre_submit mode` | L1 | yes |
| FR-6 | `assemble_coach_context.test.ts::lesson pin skips question.id === pin.questionId guard` | L1 | yes |
| FR-6b | `coach_thread_store.test.ts::lesson→lesson (same skill) does not spuriously reset` | L1 | yes |
| FR-7 | `(grep-guard) e2e/…::no middleware/question_id change` + `check:*` scripts | L1 | yes |
| FR-8 | `e2e/learn/skill-coach-seed.spec.ts::open coach from lesson → skill-pinned, no item panel` | L4 | learn-e2e |

## 9. Definition of Done

- [ ] FR-1..FR-8 implemented; FR-1 (stale-pin overwrite) + FR-2 (null→valid lesson context) seen to
      fail first against the current bare-link / questionId-required code.
- [ ] `CoachSurfacePin` discriminated union; every consumer updated to exhaustive handling (typecheck proves it).
- [ ] E2E: opening the coach from a `returning` lesson lands skill-pinned, `pre_submit`, no item panel.
- [ ] No middleware diff (grep-guard green); no `skill_state`/DB change.
- [ ] `make check` green (vitest + arch + typecheck) + learn-e2e green.
- [ ] OQ-3/D4c ADR-or-`decisions.md` filed for the seed shape; ratchet satisfied.
- [ ] Actual output pasted for the FR-1/FR-2 red→green + the E2E run.
