---
title: 'D3 — Session-length decision (Q-1b) (PreAct parity Epic D)'
type: spec
sprint: D3
epic: D
status: Implemented — 2026-07-11 (Phase 1 docs-only; keep 30; Phase 2 did not fire)
owner: Rajnish Khatri
derives_from: docs/plan/preact-parity-sprint-board-D.md
governs:
  - docs/plan/preact-parity-D3-session-length.plan.md  # written only if outcome = code change
  - docs/plan/preact-parity-D3-session-length.tasks.md # written only if outcome = code change
related:
  - docs/plan/preact-parity-sprint-board-D.md
  - docs/adr/0023-quiz-bounded-session-target-count.md  # to be amended iff outcome flips
  - docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md  # §Q-1b
---

# D3 — Session-length decision (Q-1b)

**Report finding:** `Q-1b` — app default `target_count = 30` (source-of-truth at
[`drizzle_session_repo.ts:26`](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:26));
prototype's session-supplement line at [`PreAct/UI-Design/design-spec.md:143`](../../PreAct/UI-Design/design-spec.md:143) reads
**"Session = 10 items, Punctuation drill"**. Parity report leaves the question
**explicitly open** ("is 30 intended for adaptive?").

## 1. Goal

**Resolve the question**, not "fix a bug." Record the product answer with
rationale in [`docs/adr/decisions.md`](../adr/decisions.md). If the answer keeps
the current 30, the sprint closes docs-only. If the answer changes it, D3
upgrades: a one-const change, ADR-0023 amended, tests seen fail first, TDD green.

## 2. Context

Stage-1 P10 refuted the epics-doc premise that Q-1b is a code sprint. The
prototype's `10` appears in a **session-supplement narrative** (a demo
walkthrough), not a product spec. ADR-0023 (accepted 2026-07-08) locked
`DEFAULT_TARGET_COUNT = 30` as the adaptive-loop mastery signal. Either the
prototype's 10 was a demo-length choice AND the 30 is right, OR the design
intent is 10 and the ratchet needs an amendment. Only a human product answer
resolves this.

**Recommended answer (spec author's read): keep 30.** Rationale — S3 shipped 30
as the adaptive mastery signal (ADR-0023 §Rationale); the 10 in the design-spec
appears only in a narrative "sample session" (line 143), not the acceptance
criteria; and 30 is what the coverage-ratchet and no-repeat validator were
designed against (60-Q audit passes at 30 × 2). The human overrides at §5.

## Clarify resolutions (2026-07-11, pre-plan)

- **Fresh S3 signal considered.** S3-pre bank growth is deferred (memory:
  [[preact-s3-bounded-session-spec]]); thin skills (e.g. `s-sent = 23`
  reviewed items) currently CANNOT fill a 30-unique drill anyway — FR-11
  (end-early-on-exhaustion) is what keeps runtime correct. Moving to 10 would
  make 30-item drills achievable across the current bank without the S3-pre
  wait — a real product benefit if the answer is "10".
- **Scope of "session length"**: only `DEFAULT_TARGET_COUNT` (the seed-floor
  default when no policy row is set). Per-mode policy overrides
  (`session.target_count.drill = 30` at [`engine_repos.test.ts:544`](../../frontend/lib/adapters/engine/repos/engine_repos.test.ts:544))
  are **out of scope** — those are content-team levers, not the parity delta.
- **If "keep 30" wins**: no code, no test, one `decisions.md` line, sprint
  closes docs-only.
- **If "change to N" wins**: one-const change + ADR-0023 amend + ~17 test
  literals updated (grep at [decision time](#3-functional-requirements-ears)).

## 3. Functional requirements (EARS)

**Phase 1 — decision (Ubiquitous).**

- **FR-1.** THE SYSTEM (this spec) SHALL record the human product answer to
  Q-1b as an entry in [`docs/adr/decisions.md`](../adr/decisions.md), in the
  form:
  > `- Q-1b (2026-07-DD): DEFAULT_TARGET_COUNT stays at 30 [OR moves to N]. Rationale: …. Rejected alternative: …. Cites PreAct/UI-Design/design-spec.md:143 as the origin of the 10-item narrative.`

  A single line, newest-first, with a date, the outcome, the rejected
  alternative, and a source citation.

**Phase 2 — code (Conditional; only fires if Phase 1 flips 30 → N).**

- **FR-2 (unwanted; only if flip).** IF the outcome flips to N, THEN
  [`drizzle_session_repo.ts:26`](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:26)'s `const DEFAULT_TARGET_COUNT = 30`
  MUST change to `= N`, and every test whose asserted default is the OLD 30
  (see grep audit at §8) MUST be updated to N in the same PR.
- **FR-3 (only if flip).** WHEN a new session opens with no per-mode policy
  override, THE SYSTEM SHALL resolve `target_count = N` (verified at
  [`use_quiz.test.ts:563`](../../frontend/components/quiz/use_quiz.test.ts:563)
  and [`engine_repos.test.ts`](../../frontend/lib/adapters/engine/repos/engine_repos.test.ts) session-open paths).
- **FR-4 (only if flip).** THE SYSTEM SHALL amend
  [ADR-0023](../adr/0023-quiz-bounded-session-target-count.md) with a new
  section `## Amendment — 2026-07-DD (Q-1b resolved)` recording the new
  default, the rejected alternative (keeping 30), and the source-of-truth
  citation. This is an **ADR amendment**, not a new ADR (structural change to
  a shipped decision — that's the ADR ratchet discipline).
- **FR-5 (only if flip).** THE SYSTEM SHALL NOT change the
  per-mode-policy-override seam (the `session.target_count.<mode>` policy row
  read at [`drizzle_session_repo.ts:94-110`](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:94)) — only the
  seed-floor default moves.

## 4. Data model / contracts

- Phase 1: none (docs).
- Phase 2 (iff flip): no wire change. `QuizSession.target_count` remains
  nullable-int-positive ([`engine_entities.ts:213`](../../frontend/lib/wire/engine_entities.ts:213)); only the
  seed-floor **default** value moves.

## 5. Invariants & security boundaries

- **AGENTS.md invariant #7 (services framework-agnostic)** — untouched.
- **F-R7 (trace propagation)** — untouched.
- **ADR ratchet (ADR.1)** — Phase 2 explicitly **amends** ADR-0023 rather than
  authoring ADR-0028. Amending a shipped decision is the ratchet discipline
  when the *what* changes but the *why* is a refinement of the same context.
  (Route through the same file — no new ADR filename.)
- **Human gate**: this spec cannot leave Draft until the human answers §3
  FR-1. The plan file is only authored if the answer flips.

## 6. Edge cases

- **Existing sessions in flight** at deploy time — no migration issue: only
  the **seed-floor default** moves, and existing `quiz_sessions.target_count`
  rows already store their own snapshot (per S3's field-persistence design).
- **Per-mode policy override present** — override wins (unchanged; FR-5).
- **`target_count = null` on legacy rows** — unchanged path via
  [`drizzle_session_repo.ts:110`](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:110); still falls back to the
  (new) default.
- **Coverage-ratchet + no-repeat validator** — need re-audit iff flip to a
  count that (a) exceeds a skill's reviewed-item pool, or (b) is much smaller
  than 30. The audit at [[preact-no-repeat-60-audit-passage-sharing]] runs
  60 questions across 2 sessions of 30; moving to 10 makes it 6 sessions of
  10 — validator must pass.

## 7. Non-functional requirements

- **Phase 1:** zero cost, zero latency, zero determinism impact.
- **Phase 2 (iff flip):** L1 deterministic; no live-LLM calls.
- **Reversibility:** trivial in both phases (revert one line + one ADR
  amendment; `decisions.md` line stays as a historical marker either way).

## 8. Test plan

**Phase 1** — no tests; `make check` green trivially.

**Phase 2 (iff flip)** — failure paths first:

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-2 | `drizzle_session_repo.test.ts::opens_default_to_N` — asserts `DEFAULT_TARGET_COUNT === N`. Seen red first (test asserts `N`, code says `30`). | L1 | yes |
| FR-2 | Grep audit `frontend/**/*.{ts,tsx}` for the literal `30` as a `target_count` assertion — updated in the same PR (17 known sites; see grep results below). | L1 (arch) | yes |
| FR-3 | `use_quiz.test.ts::opens_session_with_default_target_count` — asserts `session.target_count === N` (currently asserts `30` at line 563). | L1 | yes |
| FR-3 | `engine_repos.test.ts` session-open paths (drill/adaptive without policy row) — assert `N`. | L1 | yes |
| FR-3 | `weekly_sessions_vm.test.ts:20` + `streak_vm.test.ts:20` fixtures — update fixture `target_count: N`. | L1 | yes |
| FR-4 | `docs/adr/0023-*.md` has a new `## Amendment` section with a dated line, new value, and rejected alternative. Verified by hand at review; no test. | docs | n/a |

**Known grep footprint (seen 2026-07-11):**
- `lib/adapters/engine/repos/drizzle_session_repo.ts:26,101,107,110`
- `lib/adapters/engine/repos/engine_repos.test.ts:544,547,555,560,568,576,580,601`
- `components/quiz/use_quiz.test.ts:563`
- `lib/wire/engine_entities.test.ts:31,108,109`
- `lib/translators/weekly_sessions_vm.test.ts:20`
- `lib/translators/streak_vm.test.ts:20`
- `scripts/validate_s3_bounded_session.ts:142,150,152,207,208,465`
- `e2e/learn/validate_s5_done_state.spec.ts:32`, `quiz-progress.spec.ts:6,7,30`

## 9. Definition of Done

**Phase 1 (always):**
- [ ] `docs/adr/decisions.md` has a newest-first line recording the outcome,
      rationale, rejected alternative, and source citation.
- [ ] Parity report §Q-1b marked resolved (with cite to the `decisions.md`
      line).
- [ ] Sprint-board D3 header status flips to Implemented.

**Phase 2 (iff outcome flips 30 → N):**
- [ ] `DEFAULT_TARGET_COUNT` = N in [`drizzle_session_repo.ts:26`](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:26).
- [ ] Every literal-30 test in the grep footprint above updated in the same
      PR — each new assertion seen fail first against the old code.
- [ ] ADR-0023 amended (not replaced) with a dated `## Amendment` section
      recording new default + rejected alternative.
- [ ] `make check` green; `pytest tests/architecture/ -q` green.
- [ ] No-repeat 60-Q validator re-run and green at the new count (2 sessions
      of 30 → K sessions of N; math still lands).

## 10. Gates

- **⚠️ Ask first (Phase 1)** — human product decision is the whole point.
  This is the only ADR trigger this sprint fires unless the code path runs.
- **⚠️ Ask first (Phase 2, iff flip)** — a structural change to a shipped
  decision (ADR-0023) is an amendment, not a new ADR (per ratchet). No new
  `docs/adr/0028-*.md` file created.
- **G8 (test-mass-rewrite gate)** — Phase 2 rewrites ~17 test literals.
  Justification: each old assertion pinned the **old** default; the new
  assertion pins the **new** default. Same claim, updated value — not a
  weakening (each test still asserts an exact number; the code change forces
  the update; test rewrites are seen fail first, not blind-approve).
