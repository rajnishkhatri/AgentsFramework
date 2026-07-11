# Tasks — PreAct Parity Sprint C2: Summary payoff

**Belongs to:** [preact-parity-C2-summary-payoff.spec.md](preact-parity-C2-summary-payoff.spec.md) · [plan](preact-parity-C2-summary-payoff.plan.md)
**Date:** 2026-07-10

Task markers:
- `[red]` — write a failing test *and see it fail* before touching prod code.
- `[green]` — make the failing test pass (and no other test fail).
- `[P]` — can run in parallel with siblings inside the same block.

---

## Block 0 — Baseline + ADR

- **T0.1** Baseline. Run `make check`, `pnpm test` (frontend Vitest),
  `pnpm run test:arch`, `.venv/bin/python -m pytest tests/architecture/ -q`,
  `pnpm exec playwright test --project=learn-e2e`. Record the raw stdout of
  each as a "baseline" note in `spec §10`. Any red baseline that this sprint
  did not cause must be documented as pre-existing before Block 1 fires.
- **T0.2** Author `docs/adr/00XX-question-misconception-field.md` (Status:
  Accepted 2026-07-10). Copy the template. Rejected alternatives = the five
  from `spec §11 Gates`. **G1 gate satisfied.**
- **T0.3** Append `docs/adr/log.md` newest-first line and
  `docs/adr/index.md` entry for the new ADR (OKF discipline). Verify
  `pytest tests/architecture/test_adr_ratchet.py -q` green (must be green
  before the trigger paths in Block 1 land).

## Block 1 — Wire + Drizzle (FR-9, FR-10)

- **T1.1 [red] [P]** Add a `Question` schema case in
  `frontend/lib/wire/engine_entities.test.ts` (create the file if it
  doesn't exist — table-driven per T4). Assert
  `Question.safeParse({...validQuestion, misconception: null}).success ===
  true`, and same with `misconception: "some string"`, and
  `misconception: 42` fails. Watched red (`FR-9` — no field yet).
- **T1.2 [red] [P]** Add a `TestItem` schema case in the same test file.
  Same three assertions. Watched red (`FR-10` — no field yet).
- **T1.3 [green]** Add `misconception: z.string().nullable()` to
  `Question` in `frontend/lib/wire/engine_entities.ts`. T1.1 turns green.
- **T1.4 [green]** Add `misconception: z.string().nullable()` to
  `TestItem` in the same file. T1.2 turns green.
- **T1.5 [red]** Add a conformance-row case in the existing engine repos
  test (or `engine_repos.test.ts` — grounded existence in spec §2) that
  asserts a TestItem row round-trips `misconception` (both null and
  string) through `TestItemRepo.listReviewed`. Watched red (no column
  yet).
- **T1.6 [green]** Add `misconception: text("misconception")` to
  `testItem` in `frontend/lib/adapters/engine/db/schema.pg.ts`. Generate
  the Drizzle migration:
  ```bash
  pnpm --dir frontend drizzle-kit generate
  ```
  Verify the generated `drizzle/00NN_add_misconception_to_test_item.sql`
  is `ALTER TABLE ... ADD COLUMN misconception text` (nullable).
- **T1.7 [green]** `in_memory_engine_db.ts` — verify `listClosedSessionsByLearner`-style
  pass-through; no change expected but confirm the field survives
  round-trip. T1.5 turns green.

## Block 2 — Translator (FR-11, FR-13, FR-14, FR-7, FR-8)

- **T2.1 [red] [P]** Add table-driven cases to
  `frontend/lib/translators/session_summary_vm.test.ts`:
  - `drill_title_uses_target_count_when_present` (`FR-11`).
  - `drill_title_falls_back_to_skill_name_when_target_count_null` (`FR-11`).
  - `keeps_neutral_title_when_score_ratio_below_threshold` (`FR-7`).
  - `flips_framed_title_at_ratio_gte_0_6` (`FR-13`).
  - `treats_score_total_zero_as_below_threshold` (`FR-8`).
  - `framed_title_body_uses_neutral_copy_when_selfCorrected_false` (`FR-13`).
  - `framed_title_body_references_misconception_when_selfCorrected_true`
    (`FR-13`).
  - Watched red for each.
- **T2.2 [green]** Extend `toSessionSummaryVM` signature with three new
  scalar params: `misconception: string | null`, `selfCorrected: boolean`,
  `scoreRatioMet: boolean`. Add `title`, `body`, `misconception`,
  `selfCorrected`, `showFramedTitle` to `SessionSummaryVM`; add
  `drillTitle` to `RecommendedNextVM`. Export
  `SUMMARY_FRAMED_TITLE_RATIO = 0.6` (§13 decisions §1 references it).
  All T2.1 cases turn green.
- **T2.3 [green]** Verify that `use_summary` still typechecks against the
  new signature (compile fails until Block 3 supplies the new args — that
  is fine and expected; do NOT ship the translator alone).

## Block 3 — Hook (FR-12, FR-1, FR-2, FR-14 wiring)

- **T3.1 [red]** Add cases to
  `frontend/components/summary/use_summary.test.ts`:
  - `renders_no_misconception_card_when_question_misconception_null` (FR-1).
  - `renders_no_misconception_when_no_misses_on_recommended_skill` (FR-2).
  - `derives_misconception_from_last_incorrect_attempt_on_recommended_skill`
    (FR-12).
  - `self_correction_signal_true_when_first_half_miss_second_half_clean`
    (FR-14 through the hook).
  - `self_correction_signal_false_when_second_half_still_missing`
    (FR-14 through the hook).
  - `normalizes_empty_string_misconception_to_null` (edge case in `spec §6`).
  - Watched red for each.
- **T3.2 [green]** Extend `Promise.all` in `loadSummary` to 5 legs (all
  existing port methods):
  add `attemptRepo.misses(subject, learnerId)` and
  `attemptRepo.servedQuestionIds(sessionId)`.
- **T3.3 [green]** After the parallel legs resolve, derive
  session-scoped-misses (`misses` filtered by `served`, newest-first
  preserved). Then a bounded sequential loop:
  - `for miss of sessionScopedMisses: await questionRepo.get(miss.question_id)`,
    stop at first `question.skill_id === recommendedSkillId` → its
    `misconception` is the derived value.
  - Normalize `misconception === ""` → `null`.
  - `deriveSelfCorrection`: filter (`served \ missIds`) to session
    correct attempts; combine with session-scoped-misses on the
    recommended skill; apply attempt-index half-split (FR-14).
  - `deriveScoreRatioMet(session)` — `score_total > 0 && score_correct /
    score_total >= SUMMARY_FRAMED_TITLE_RATIO`.
- **T3.4 [green]** Thread scalars into `toSessionSummaryVM`. All T3.1
  cases turn green.
- **T3.5 [P]** In the test bag, verify no `AttemptRepo.getMany` or
  `AttemptRepo.sessionAttemptsInOrder` is referenced anywhere in the
  patch — the sprint MUST land without adding a port method (G1
  abstraction-introduction gate).

## Block 4 — View (FR-15, FR-16, FR-3, FR-17)

- **T4.1 [red] [P]** Add cases to
  `frontend/components/summary/SummaryView.test.tsx`:
  - `renders_summary_misconception_section_when_vm_misconception_present`
    (FR-15).
  - `omits_summary_misconception_section_when_vm_misconception_null`
    (FR-15/FR-1 through the view).
  - `renders_three_actions_in_order_with_correct_hrefs` (FR-16).
  - `see_lesson_renders_disabled_when_screen_comingSoon` (FR-3).
  - `summary_skill_link_stays_present_and_focused` (FR-17).
  - `renders_framed_title_when_vm_showFramedTitle_true` (FR-13 through the
    view).
  - `renders_neutral_title_when_vm_showFramedTitle_false` (FR-7/FR-8
    through the view).
  - Watched red for each.
- **T4.2 [green]** Add the `<section aria-label="The misconception I
  spotted" data-testid="summary-misconception">` block. Insert between the
  header and the stat-tile grid. Style via existing accent tokens (U8).
  T4.1 misconception cases turn green.
- **T4.3 [green]** Replace the single "Practice this next" CTA with the
  three-actions row (§spec §3 FR-16 markup). Use `cn()` (U6);
  `data-disabled` / `aria-disabled` for the Lesson state (§13 style
  guide). T4.1 three-actions + disabled cases turn green.
- **T4.4 [green]** Swap the header to render `vm.summary.title` +
  `vm.summary.body`. T4.1 title cases turn green.
- **T4.5 [green]** Confirm `summary-skill-link` still resolves + points to
  `/learn/quiz?focus=<skillId>`. T4.1 FR-17 case turns green.

## Block 5 — e2e (FR-17 + framed-title branches + axe)

- **T5.1 [red]** Author `frontend/e2e/learn/summary-payoff.spec.ts`:
  - `skill_link_still_navigates_to_focused_quiz` (FR-17 e2e).
  - `renders_misconception_card_when_authored` (uses a bank item seeded
    with `misconception: string` — coord with Block 6 K==0 fallback: this
    test dev-seeds one row inline).
  - `omits_misconception_card_when_not_authored` (baseline item, no
    misconception).
  - `renders_three_actions_and_disables_lesson_while_comingSoon` (FR-3).
  - `renders_framed_title_when_score_ratio_met` (FR-13 e2e; drives a
    high-ratio session).
  - `renders_neutral_title_when_score_ratio_below_threshold` (FR-7 e2e).
  - `axe_clean_light_and_dark` (WCAG-AA, S1 pattern).
  - Watched red for each.
- **T5.2 [green]** Verify all T5.1 cases pass on the code from Blocks
  1-4 (no new prod code should be needed here). If a case fails, the
  root cause is a gap in Blocks 1-4 — patch there, not in the e2e.

## Block 6 — Content pass (FR-6)

- **T6.1** Run the misconception probe: grep `_test_item_bank.ts` for
  items where `why_tempted_md` already implies a one-line misconception.
  Record K (the probe return count) in `spec §10`. If K == 0, skip to
  T6.4 with a `decisions.md` line stating "K=0; content-pass follow-up
  track opens as its own sprint".
- **T6.2** If K > 0: for K rows, edit
  `docs/plan/coach-item-bank-live.promoted.json` to add
  `"misconception": "one-line copy"` to each row. Match the diction of
  existing `why_correct_md` / `rule_md` fields.
- **T6.3** Update `scripts/emit_test_item_bank.py` to emit the
  `"misconception"` key on every row (value taken from `promoted.json`,
  else literal `null`).
- **T6.4** Regenerate `_test_item_bank.ts`:
  ```bash
  .venv/bin/python scripts/emit_test_item_bank.py
  ```
- **T6.5 [red] [P]** Add to `_test_item_bank.test.ts`:
  `emits_misconception_key_even_when_null` — asserts every row in
  `TEST_ITEM_BANK` has the `misconception` key present (null or string).
  Watched red before T6.4 fires.
- **T6.6 [green]** T6.5 turns green after T6.4.

## Block 7 — FLAG-5 wire (soft-gated, FR-4, FR-18)

Precondition check:
```bash
grep -c "^export.*readActiveQuiz\|^export {.*readActiveQuiz" \
  frontend/components/quiz/quiz_session_store.ts
```

- If **count > 0** (substrate present):
  - **T7.1a [red]** Add `frontend/app/(coach)/learn/coach/page.test.tsx`
    case `onWrapUp_appends_session_query_when_readActiveQuiz_present`
    (FR-18) — watched red.
  - **T7.1b [red]** Add
    `onWrapUp_falls_back_to_summary_route_when_readActiveQuiz_returns_null`
    (FR-4) — watched red.
  - **T7.2 [green]** Replace `onWrapUp` in
    `frontend/app/(coach)/learn/coach/page.tsx:101-104` with the FR-18
    body. T7.1a + T7.1b turn green.
  - **T7.3 [green]** Check whether
    `frontend/e2e/learn/validate_epic_ab.spec.ts` exists:
    - if yes → unwrap the FLAG-5 `test.fail()` and re-run
      `learn-e2e` to confirm green.
    - if no → the e2e file itself is authored by continuity-fixes; no
      C2 edit needed. Follow-up commit flips it green when that spec is
      merged. Add a `decisions.md` note recording this branch.

- If **count == 0** (substrate absent):
  - **T7.1c** Add a `decisions.md` line: "C2 FLAG-5 wire deferred pending
    continuity-fixes `readActiveQuiz` export. Follow-up commit lands the
    wire the day the substrate merges." (Spec §13 line 3 already covers
    this.)
  - Do NOT edit `coach/page.tsx`. Do NOT create `validate_epic_ab.spec.ts`.

## Block 8 — Soft-gate arch-test + decisions ledger + PR

- **T8.1 [red]** Author
  `frontend/tests/architecture/test_c2_soft_gate.test.ts` (ts-morph):
  - Reads whether `readActiveQuiz` is exported by `quiz_session_store`.
  - Asserts the correct import state on `coach/page.tsx` given that read:
    - substrate absent → `readActiveQuiz` MUST NOT be imported (no
      phantom import).
    - substrate present → `readActiveQuiz` MUST be imported.
    - substrate present AND `e2e/learn/validate_epic_ab.spec.ts` exists →
      that file's FLAG-5 `test.fail()` MUST be unwrapped (matches T7.3
      branch A). If the e2e file is absent, no e2e assertion made.
  - Watched red (fails because the test file doesn't exist yet).
- **T8.2 [green]** The arch test passes given Block-7 outcome.
- **T8.3** Append the five decisions to `docs/adr/decisions.md`:
  1. C2 framed-title threshold = 0.6 (spec §13 #1).
  2. C2 self-correction signal = attempt-index half-split (spec §13 #2).
  3. C2 FLAG-5 wire deferred until continuity-fixes lands
     `readActiveQuiz` (spec §13 #3). *If* Block 7 wired the FLAG-5 fix,
     re-word this to record "landed inline with continuity-fixes on
     `main`".
  4. C2 misconception seed-count = probe-based (K = <value from T6.1>)
     (spec §13 #4).
  5. C2 misconception field lives on `Question` wire (D4 direction)
     (spec §13 #5).
- **T8.4** Verify green — `make check`, `pnpm test`,
  `pnpm run test:arch`,
  `.venv/bin/python -m pytest tests/architecture/ -q`,
  `pnpm exec playwright test --project=learn-e2e`. Paste stdout into
  `spec §10`.
- **T8.5** Push branch `feat/preact-parity-c2-summary-payoff` from the
  current `main` tip. Open PR titled
  `feat(summary): C2 misconception payoff + framed title + three actions
  + FLAG-5 (soft-gated)`. Body: link the spec, plan, tasks, and ADR.
  Note the Block-7 branch taken.

---

## FR → task crosswalk

Every FR from `spec §3` maps to at least one task with a `[red]` marker.

| FR | Red task | Green task |
|----|----------|------------|
| FR-1 (honest-absent misconception) | T3.1, T4.1 | T3.4, T4.2 |
| FR-2 (honest-absent misses) | T3.1 | T3.4 |
| FR-3 (dead-control block for See full lesson) | T4.1 | T4.3 |
| FR-4 (FLAG-5 honest recovery) | T7.1b (if substrate present) | T7.2 |
| FR-5 (soft-gate: no wire without substrate) | T8.1 | T8.2 |
| FR-6 (item-bank content pass gated on data) | T6.5 | T6.4 (or T6.1 short-circuit if K=0) |
| FR-7 (framed title threshold — floor) | T2.1 | T2.2 |
| FR-8 (`score_total = 0` guard) | T2.1 | T2.2 |
| FR-9 (misconception on `Question`) | T1.1 | T1.3 |
| FR-10 (misconception on `TestItem` + column) | T1.2, T1.5 | T1.4, T1.6 |
| FR-11 (VM misconception + drillTitle) | T2.1 | T2.2 |
| FR-12 (hook derives from last incorrect) | T3.1 | T3.3, T3.4 |
| FR-13 (framed title flips at threshold) | T2.1, T4.1 | T2.2, T4.4 |
| FR-14 (self-correction signal) | T2.1, T3.1 | T2.2, T3.3 |
| FR-15 (misconception accent card) | T4.1 | T4.2 |
| FR-16 (three-actions row) | T4.1 | T4.3 |
| FR-17 (S-5 refuted-premise regression guard) | T4.1, T5.1 | T4.5 (already shipped in prod code) |
| FR-18 (FLAG-5 wire, soft-gated) | T7.1a (if substrate present) | T7.2 |

Every FR has a red step. Every red step has a matching green. No FR is
"tested by inspection".

---

## Parallelization envelope (for `[P]` markers)

Blocks fire sequentially (each has an artifact the next reads). Inside a
block:

- **Block 1:** T1.1 || T1.2 (independent test additions).
- **Block 4:** T4.1's cases can be authored in one commit but reviewed as
  parallel additions. T4.2 || T4.3 || T4.4 || T4.5 all touch the same
  file — sequential edits, one commit each.
- **Block 6:** T6.5 (test) can be authored in parallel with T6.2 (json
  edit). T6.3 → T6.4 must be sequential.
- **Block 7:** no `[P]` — one branch at a time.

No `[P]` marker exists across blocks — each block's evidence gates the
next.

---

## Phase 1 — Convergence (2026-07-10, post-merge PR #145)

PR [#145](https://github.com/rajnishkhatri/AgentsFramework/pull/145) merged
to `main` at `95d9dc6`. Deterministic reviewer + architecture + pytest CI
green. Stage 9 classification of remaining reds / DoD gaps:

| ID | Finding | gap-type | source-ref | Route |
|----|---------|----------|------------|-------|
| G1 | CI `frontend-wire-baseline` / `tsc --noEmit` RED on `main` | `partial` (DoD T8.4 / spec §9 “make check + pnpm test… green”) | CI run `29130232617`; local repro identical | → sdd-implement |
| G2 | `use_coach.ts` still keys `learnerReadRepo`; bag is `learnerRead` | `unrequested` vs C2 FRs (Epic B rename drift; predated C2 — present at `7c2ad26`) | `frontend/components/coach/use_coach.ts:67,117,120,193` + tests | → sdd-implement (same PR as G1; not a C2 FR miss) |
| G3 | `quiz/page.tsx` `onAskCoach` exactOptionalPropertyTypes | `unrequested` (Epic B Feedback bridge; blame `8240052`) | `frontend/app/(coach)/learn/quiz/page.tsx:265` | → sdd-implement w/ G1 |
| G4 | `coach_agent_id_flow.test.tsx` missing `children` on `EngineProvider` | `unrequested` (Epic B; blame `8240052`) | `frontend/components/coach/coach_agent_id_flow.test.tsx:124` | → sdd-implement w/ G1 |
| G5 | Human manual UI validation of Summary payoff | `partial` (Stage-6 local stack ready; human walk not signed) | walkthrough 2026-07-10 | human gate — no code task |
| G6 | FLAG-5 wire absent | **not a gap** — FR-5 / T7.1c deferral; substrate count 0 | ADR decisions.md + soft_c2_soft_gate | none |
| G7 | Pre-existing QuizView Reveal + ts-morph arch timeouts | **not a gap** — documented T0.1 baseline; C2 untouched | spec §10 T0.1 | none / separate track |

### Phase-1 fix tasks (append-only; do not rewrite Blocks 0–8)

- **T9.1 [red]** `pnpm --dir frontend exec tsc --noEmit` fails on `main`
  with the four errors in G1–G4. Watched red: paste the four TS error
  lines. `source-ref:` G1–G4. `gap-type:` partial + unrequested (main
  hygiene blocking C2 DoD paste).
- **T9.2 [green]** Rename `learnerReadRepo` → `learnerRead` in
  `use_coach.ts` + `use_coach.test.ts` (and any coach test doubles).
  Typecheck errors on those lines gone.
- **T9.3 [green]** Fix `onAskCoach` prop pass under
  `exactOptionalPropertyTypes` in `quiz/page.tsx` (omit prop when
  undefined, or widen FeedbackView prop to `| undefined`).
- **T9.4 [green]** Pass `children` (or `null`) into `EngineProvider` in
  `coach_agent_id_flow.test.tsx`.
- **T9.5 [green]** `pnpm --dir frontend exec tsc --noEmit` exits 0; paste
  into spec §10 Phase-1 evidence. Re-run C2 unit slice
  (`components/summary`, `session_summary_vm`, `engine_entities`
  misconception, `test_c2_soft_gate`) — expect still green (56/56 at
  converge classify).
- **T9.6 [P]** Human: complete Walk A/B/C from the C2 manual-validation
  guide; check DoD boxes in spec §9 that are UI-visible (FR-15/16/13/1).
  `source-ref:` G5.

**Out of Phase-1 scope:** FLAG-5 wire (awaits continuity-fixes
`readActiveQuiz`), QuizView Reveal flake, ts-morph arch timeouts.

**Max iterations:** 1 more implement pass for T9.1–T9.5, then Stage-10
sign-off. If typecheck still red after that pass → stop for human review.

### Phase-1 implement evidence (2026-07-10, branch `fix/c2-phase1-typecheck-hygiene`)

**T9.1 watched red** (`pnpm --dir frontend exec tsc --noEmit`):

```
app/(coach)/learn/quiz/page.tsx(265,12): error TS2375: … onAskCoach …
components/coach/coach_agent_id_flow.test.tsx(124,9): error TS2769: … children …
components/coach/use_coach.ts(67,5): error TS2344: … "learnerReadRepo" …
components/coach/use_coach.ts(117,34): error TS2339: … learnerReadRepo …
components/coach/use_coach.ts(120,29): error TS18046: …
components/coach/use_coach.ts(193,32): error TS2551: … Did you mean 'learnerRead'?
```

**T9.2–T9.4 green:**
- `learnerReadRepo` → `learnerRead` in `use_coach.ts` + `use_coach.test.ts`
- `FeedbackView` gets conditional `onAskCoach` spread (exactOptionalPropertyTypes)
- `EngineProvider` props include `children` (matches `engine-provider.test.tsx`)

**T9.5:** `tsc --noEmit` exit 0; vitest slice 7 files / **68 passed**
(`summary` + `session_summary_vm` + `engine_entities` + `test_c2_soft_gate`
+ `use_coach` + `coach_agent_id_flow`).
