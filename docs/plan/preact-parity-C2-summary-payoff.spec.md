# Spec — PreAct Parity Sprint C2: Summary payoff (misconception + framed title + three actions + FLAG-5)

**Status:** Draft — 2026-07-10
**Owner:** Rajnish Khatri
**Related:**
- Epic board: [preact-parity-sprint-board-C.md](preact-parity-sprint-board-C.md) — §"Sprint C2"
- Epic decomposition: [preact-parity-epics.md](preact-parity-epics.md) — §"Epic C"
- Stage-1 brainstorm: [preact-parity-epic-C.brainstorm.md](preact-parity-epic-C.brainstorm.md) — CLOSED, direction **D4** (Question-authored misconception)
- Parity report findings: `S-3`, `S-1`, `S-4b`, `S-6` (+ `S-5` refuted-premise regression guard)
- Manual-validation-report **FLAG-5** (Wrap-up `?session=` wire) — soft-gated on continuity-fixes
- Preceding sprint: [preact-parity-C1-dashboard-rail.spec.md](preact-parity-C1-dashboard-rail.spec.md) (Implemented) + [preact-parity-C1-review-fixes.spec.md](preact-parity-C1-review-fixes.spec.md) (Draft, in flight)
- Style guides: [STYLE_GUIDE_FRONTEND.md](../style-guides/STYLE_GUIDE_FRONTEND.md) — rules W1/W3/W7, T1/T2, P1, F-R1..F-R9, U6, B6, C4, FE-AP-6, AP-6 (honest-absent)
- Item-bank precedent: [coach-item-bank-live.spec.md](coach-item-bank-live.spec.md) (ADR-0021) — misconception rides the same cascade

---

## 1. Goal

Close the Summary "misconception payoff" gap. Turn `/learn/summary` from three
neutral stat tiles + one CTA into the prototype's **coaching payoff surface**:
a title framed by outcome, a misconception accent card when the item author
captured one, a specific *drill* recommendation (not a bare skill), and the
three-actions row (drill / see full lesson (disabled while `comingSoon`) / done
for today). Ship the manual-report **FLAG-5** wire (Wrap-up `?session=`) when
the continuity-fixes substrate is available, else defer the wire without
blocking the payoff surface.

Audience: the single Phase-1 learner ("Maya"), on the shipped `/learn/summary`
surface. Every value is a real read from the engine OR honestly absent (C-4
honesty rule from Epic B) — never a placeholder.

## 2. Context

Stage-1 audit (2026-07-10, brainstorm CLOSED) refuted the naïve premise that
misconception "comes from the coach" — no engine seam produces it today and D5
(coach-runtime marker) has an adoption gap (only fires when the learner used
the coach, a proper subset of "everyone"). Direction **D4** landed: carry
misconception as a new **nullable `Question.misconception` field** filled by
content authoring on the item-bank cascade (ADR-0021 precedent). Absent → no
card (honest-absent, AP-6). This turns "what misconception did the coach
spot?" into a deterministic derivation from author-captured metadata on the
misses the learner just posted — the same discipline the Coach chrome (Epic
B) uses for the trust rail.

The four cheap `S-1` (title) + `S-4b` (drill title) + `S-6` (three actions)
items fold in because C2 already reworks the Summary landing surface (the
Stage-1 audit dropped the standalone D1 "pure wire-up" sprint). FLAG-5 folds
in for the same reason — Wrap-up is a one-line change once
`readActiveQuiz()?.sessionId` is available.

Grounded on the current state of these seams:
- `frontend/lib/wire/engine_entities.ts:61-79` — `Question` has no
  `misconception` field.
- `frontend/lib/adapters/engine/db/schema.pg.ts:130-160` — `testItem`
  (ADR-0021 bank storage) has no `misconception` column.
- `frontend/lib/adapters/engine/_test_item_bank.ts` — the generated 60-row
  corpus is authored without a misconception field today.
- `frontend/lib/translators/session_summary_vm.ts:12-18` — the pure T1 note
  itself says "misconception passed by the hook, not synthesized here" — the
  seam is pre-wired to accept it.
- `frontend/components/summary/use_summary.ts:64-118` — `loadSummary` already
  reads three ports concurrently; adding an `attemptRepo.misses(session)` fetch
  is a fourth `Promise.all` leg — no new port.
- `frontend/components/summary/SummaryView.tsx:44-89` — the header/stats grid +
  recommended-next card is the surface being extended; **`summary-skill-link`
  is already tappable** (Stage-1 refuted-premise `S-5`) — C2 e2e verifies
  in-passing.
- `frontend/lib/ports/engine/attempt_repo.ts` — `misses(subject, learnerId)`
  and `servedQuestionIds(sessionId)` both exist. Session-scoped miss
  ordering is derivable by intersecting the two (`misses` filtered to
  ids that appear in `servedQuestionIds`, preserving `misses`' newest-first
  order). No new port method needed (G1 abstraction-introduction principle).
- `frontend/app/(coach)/learn/coach/page.tsx:101-104` — `onWrapUp` already
  has the "session query appended in B2" comment; ships the wire the moment
  `readActiveQuiz()` is on `main`.
- `frontend/components/shell/nav_model.ts:75` — `screen("skill")` is
  `comingSoon: true`; the three-actions row must render Lesson **disabled**
  (FR-B5), else it's a dead nav item.

Not yet on disk: `epic-ab-continuity-fixes.spec.md` (referenced by the board
as "in flight, Approved") — no file exists. The FLAG-5 wire is therefore
**soft-gated** at merge time (see §12 Q1).

## 3. Functional requirements (EARS)

Failure/robustness paths first (TAP-4 gap-blindness).

### Failure paths (write first)

- **FR-1 (honest-absent misconception).** IF the recommended-next skill's
  most-recent miss for the session names an item whose `Question.misconception`
  is `null`, THEN THE SYSTEM SHALL render the Summary WITHOUT the misconception
  accent card and WITHOUT the misconception-referring title body copy — the
  "Session summary / Here's how this session went." neutral state is preserved
  (no placeholder card, no fabricated coach voice; AP-6, C-4 honesty rule).

- **FR-2 (honest-absent misses).** IF the session has zero attempts on the
  recommended-next skill (drill immediately abandoned, or the skill was never
  practised in this session), THEN THE SYSTEM SHALL render Summary WITHOUT the
  misconception card AND WITHOUT the framed title body copy — the neutral title
  is preserved. No exception is thrown; `loadSummary` resolves cleanly.

- **FR-3 (dead-control block for "See full lesson").** IF the "See full lesson"
  action would route to a screen whose `nav_model.ts` entry has
  `comingSoon: true`, THEN THE SYSTEM SHALL render that action **disabled**
  (visually + `aria-disabled="true"` + no `href`), never as an active link.
  (FR-B5 upheld; mirrors the `S-5` interim treatment.)

- **FR-4 (FLAG-5 honest recovery).** IF the Coach's `onWrapUp` cannot resolve
  a live quiz session id (continuity-fixes `readActiveQuiz()` returns null,
  or the substrate is not yet on `main`), THEN THE SYSTEM SHALL fall back to
  today's behavior (`router.push(screen("summary").route)`) with no
  `?session=` appended — the Summary page falls through to its existing
  session-lookup path. No error thrown, no dead landing.

- **FR-5 (soft-gate: no wire without substrate).** IF the continuity-fixes
  `readActiveQuiz` substrate is not present at C2 merge time, THEN THE
  SYSTEM SHALL ship C2 WITHOUT the FLAG-5 wire, WITHOUT importing a
  `readActiveQuiz` stub, and the FLAG-5 e2e regression guard SHALL remain
  wrapped in `test.fail()`. A follow-up commit lands the wire once
  continuity-fixes merges. (Prevents a phantom import; see §12 Q1.)

- **FR-6 (item-bank content pass gated on data).** IF the seed content pass
  authors N=0 misconception rows (the reviewer probe returns nothing
  eligible), THEN THE SYSTEM SHALL ship the code path anyway — every session
  renders the honest-absent branch (FR-1) until content lands as its own
  follow-up commit. No code path is gated on N > 0.

- **FR-7 (framed title threshold — floor).** IF the session's stored
  `score_correct / score_total` ratio is **below** the threshold (0.6, ratified
  §12 Q3), THEN THE SYSTEM SHALL keep the neutral title ("Session summary")
  and neutral body ("Here's how this session went.") — no "Nice work"
  framing when performance does not warrant it (C-4 honesty).

- **FR-8 (`score_total = 0` guard).** IF the session closed with
  `score_total == 0` (edge case: closed immediately with no attempts), THEN
  THE SYSTEM SHALL treat the score ratio as **below** the threshold and
  render the neutral title/body (no divide-by-zero, no fabricated framing).

### Happy paths

- **FR-9 (misconception field on wire).** THE SYSTEM SHALL extend the
  `Question` Zod schema in `wire/engine_entities.ts` with a new
  `misconception: z.string().nullable()` field (additive, nullable — no
  back-compat break for existing bank rows; W1/W3 preserved).

- **FR-10 (misconception on the item-bank row).** THE SYSTEM SHALL add a
  nullable `misconception TEXT NULL` column to the `test_item` Drizzle table
  in `schema.pg.ts` (additive migration) and mirror it in the `TestItem` Zod
  schema, so a bank row can carry it through the `TestItemQuestionRepo`
  mapper into `Question` unchanged.

- **FR-11 (Summary VM carries misconception + drill-title).** THE SYSTEM
  SHALL add two fields to the translator output shapes in
  `session_summary_vm.ts`:
  - `SessionSummaryVM.misconception: string | null`
  - `RecommendedNextVM.drillTitle: string`
  Both are pure (T1) — `misconception` is passed in from the hook (translator
  never fabricates); `drillTitle` is a deterministic string derived from
  `session.target_count` + `nextSkill.name` ("N-item drill: {skillName}") —
  target_count-null → "Drill: {skillName}".

- **FR-12 (hook derives misconception from the session's misses on the
  recommended skill).** WHEN `loadSummary` runs, THE SYSTEM SHALL:
  (a) call `attemptRepo.misses(subject, learnerId)` (newest-first, all
  sessions);
  (b) call `attemptRepo.servedQuestionIds(sessionId)` (session-scoped
  set);
  (c) filter (a) to attempts whose `question_id` is in the (b) set —
  yielding this session's misses in newest-first order;
  (d) fetch each miss's `Question` via `questionRepo.get(id)` (small N —
  ≤ session length, ≤ 30 items S3 cap) until one whose
  `skill_id === recommendedSkillId` is found;
  (e) return that question's `misconception` (or `null`).
  No new port method. `misses` provenance (session join) is deferred to
  a follow-up if a second consumer needs a session-scoped miss API.

- **FR-13 (framed title flips at threshold).** WHEN `score_correct /
  score_total >= 0.6` AND `score_total > 0`, THE SYSTEM SHALL render the
  Summary header title as "Nice work — you found the pattern." The body copy
  additionally references the misconception ("The pattern: {misconception}.")
  **only when** a self-correction signal (FR-14) fires; otherwise the body
  is a neutral outcome sentence ("You cleared the {skillName} bar.").

- **FR-14 (self-correction signal — deterministic).** WHEN the session's
  attempts on the recommended-next skill contain **at least one incorrect
  attempt in the first half** AND **at least one correct attempt in the
  second half AND no incorrect attempt in the second half**, THE SYSTEM
  SHALL set `selfCorrected = true` in the VM (drives the FR-13 body copy).
  The "half" split is by attempt index in that skill's session-scoped
  order (not time): first half = indices `[0 .. floor(n/2))`, second half
  = indices `[floor(n/2) .. n)`. Session-scoped attempts on the skill are
  derived the same way as FR-12: intersect `misses ∪ non-misses` with
  `servedQuestionIds(sessionId)`, filter by `question.skill_id ==
  recommendedSkillId`. Pure derivation; no clock, no new port. Note:
  `AttemptRepo` today only exposes `misses` (incorrect) and
  `servedQuestionIds` (all) — the "correct in second half" leg is
  derived as `served \ misses`.

- **FR-15 (misconception accent card renders when present).** WHILE the VM's
  `misconception != null`, THE SYSTEM SHALL render a `<section aria-label="The
  misconception I spotted">` accent card in the Summary immediately after the
  header and before the stat tiles, with the misconception text as its body
  and a testId `summary-misconception`. Uses the same accent tokens (U8) as
  the recommended-next card, styled distinctly (accent-tinted border, no
  bucket-color rebind — U6 `cn()`).

- **FR-16 (three actions row).** THE SYSTEM SHALL replace today's single
  "Practice this next" CTA with a three-actions row containing, in order:
  1. **Primary** — `Start recommended drill` (testId
     `summary-start-next`, `href = /learn/quiz?focus=<skillId>`; keeps the
     brand-accent fill from S1 — WCAG-AA, no bucket rebind).
  2. **Secondary** — `See full lesson` (testId
     `summary-see-lesson`; when `screen("skill").comingSoon === true`,
     rendered as a `<button disabled aria-disabled="true">` with `title`
     "Coming soon"; otherwise a `<Link href={screen("skill").route}>`).
  3. **Tertiary** — `Done for today` (testId `summary-done`,
     `<Link href={screen("dashboard").route}>`).

- **FR-17 (S-5 refuted-premise regression guard).** THE SYSTEM SHALL preserve
  the `summary-skill-link` testId on the recommended-skill name (already
  shipped at `SummaryView.tsx:69-75`). A C2 e2e SHALL assert the link
  renders + points to `/learn/quiz?focus=<skillId>` — refuted-premise stays
  refuted (Stage-1 audit).

- **FR-18 (FLAG-5 wire — soft-gated).** WHERE the continuity-fixes
  `readActiveQuiz()` API is present in `quiz_session_store` at C2 merge
  time, THE SYSTEM SHALL replace `coach/page.tsx:101-104` `onWrapUp` with:
  ```ts
  const id = readActiveQuiz()?.sessionId;
  const url = id
    ? `${screen("summary").route}?session=${id}`
    : screen("summary").route;
  router.push(url);
  ```
  and — if `frontend/e2e/learn/validate_epic_ab.spec.ts` also exists at
  merge time — flip its FLAG-5 `test.fail()` to `test()`. If the e2e file
  itself has not been authored yet (continuity-fixes not merged), the wire
  still ships; the guard-flip is a no-op deferred to a follow-up commit
  when the e2e is authored. If the `readActiveQuiz` API is absent, FR-5
  governs (no wire, no phantom import, no e2e edit).

## 4. Data model / contracts

**Wire changes (additive, W1 / W3 / W7 preserved):**

- `frontend/lib/wire/engine_entities.ts`:
  - `Question` — add `misconception: z.string().nullable()` (default omitted;
    Zod parse of a legacy row without the key sets it to `null` implicitly
    via `.nullable()` treatment of `undefined` — verify at test time).
  - `TestItem` — add `misconception: z.string().nullable()`. The
    `TestItemQuestionRepo` mapper copies it 1:1 into the `Question` shape.

**DB / schema (additive):**

- `frontend/lib/adapters/engine/db/schema.pg.ts`:
  - `testItem` — add `misconception: text("misconception")` (nullable —
    Postgres NULL by default without `.notNull()`; matches Zod
    `.nullable()`).
  - Migration file: `drizzle/00NN_add_misconception_to_test_item.sql` (auto-
    generated by `drizzle-kit push`). Nullable column; zero back-compat risk;
    no data migration.
  - `_test_item_bank.ts` (generated corpus): no manual edit; the regeneration
    script (`scripts/emit_test_item_bank.py`) MUST emit the new key. Initial
    rows carry `misconception: null` until the content pass authors values.

**Translator (T1 pure):**

- `frontend/lib/translators/session_summary_vm.ts`:
  - `SessionSummaryVM` — add `misconception: string | null`, `title: string`,
    `body: string`, `selfCorrected: boolean`, `showFramedTitle: boolean`.
    (title/body derived here so the view renders whatever string is passed;
    keeps F-R1 — no logic in the view.)
  - `RecommendedNextVM` — add `drillTitle: string`.
  - `toSessionSummaryVM(session, recommended, nextSkill, masteryDeltaPct,
    misconception, selfCorrected, framedTitleThresholdMet)` — three new
    scalar params; still pure.

**Hook (F-R1 preserved):**

- `frontend/components/summary/use_summary.ts`:
  - `Promise.all([sessionRepo.get, learnerRead.listSkillState,
    skillTaxonomy.list, attemptRepo.misses(subject, learnerId),
    attemptRepo.servedQuestionIds(sessionId)])` — extends to a five-leg
    concurrent read (all existing port methods).
  - After the join: build session-scoped-misses = `misses` filtered by
    `served`; walk newest-first, `await questionRepo.get(id)` for each
    (bounded by ≤ session length, ≤ 30 items S3 cap), stop at first
    `question.skill_id === recommendedSkillId` — that is the "last
    incorrect attempt on the recommended skill this session" (FR-12).
  - Similarly derives `selfCorrected` (FR-14) by intersecting `served` \
    `misses` to get session correct attempts on the recommended skill,
    then applying the half-split.
  - Derives `scoreRatioMet` (FR-13, FR-7, FR-8) directly from
    `session.score_correct` / `session.score_total`.
  - Passes derived scalars into `toSessionSummaryVM`.
  - No new port. No new adapter family. No env read (C4).

  Note: sequential `questionRepo.get` calls after the parallel legs are
  the honest option — adding `getMany` would be a G1 abstraction
  introduction without a second consumer (root `AGENTS.md`). If the
  bounded loop measurably regresses Summary latency, `getMany` becomes
  its own ADR follow-up.

**View (F-R1, U4, U6, F-R5-free):**

- `frontend/components/summary/SummaryView.tsx`:
  - Renders `<section aria-label="The misconception I spotted"
    data-testid="summary-misconception">` conditionally on
    `vm.summary.misconception != null` (FR-15).
  - Header title/body render `vm.summary.title` / `vm.summary.body` (the
    branching happens in the translator; view is presentational).
  - Three-actions row replaces the single CTA (FR-16). Uses `cn()` (U6);
    disabled state via `data-disabled` + `aria-disabled` (§13
    style-guide).

**Coach seam (soft-gated):**

- `frontend/app/(coach)/learn/coach/page.tsx:101-104` — see FR-18. Only
  landed when `readActiveQuiz` exports exist in `quiz_session_store`.

**No trust-kernel change** (F-R6/W4 — misconception is not signed). No new
ADR-triggering abstraction beyond the D4 wire+corpus decision.

## 5. Invariants & security boundaries

### Backend architecture invariants (root `AGENTS.md` #1–#8)

- **#2 (trust kernel purity):** untouched. Misconception is a domain-content
  field, not a trust type. No re-signing.
- **#4 (services framework-agnostic):** N/A — this is a frontend-ring sprint.
  No backend service touched.
- **All others:** untouched (no orchestration change, no new node, no service
  boundary).

### Frontend ring invariants (`frontend/AGENTS.md`, style guide §11)

- **F-R1 (no domain logic in components):** the misconception+self-correction
  decision lives in `use_summary` (the hook) + translator; the view renders
  strings passed in (title/body).
- **F-R2 (SDK imports only in adapters):** none touched.
- **F-R3 (one interface per port module):** N/A — no port change.
- **F-R4 (BFF Route Handlers are composition adapters):** N/A — no route
  handler change.
- **F-R5 (system prompts in `prompts/`):** no prompt string in TS.
- **F-R6 / W4 (trust-view read-only, sealed envelopes):** untouched.
- **F-R7 (`trace_id` propagation):** N/A — no new event on the wire.
- **F-R8 (no SDK type escapes adapter):** untouched.
- **F-R9 (BFF holds no cloud credentials):** untouched.
- **W1 / W3 (wire kernel purity, discriminated unions):** additive nullable
  field; Zod `.nullable()` preserves union soundness.
- **T1 (pure translator):** upheld — new params are scalar values passed in
  from the hook; no `Date.now`, no React, no I/O in the translator.
- **T2 (`trace_id` forwarding):** N/A.
- **U6 (`cn()` for class merging):** upheld in the three-actions row and
  misconception card.
- **U8 (semantic tokens):** the misconception card uses `--accent` /
  `--color-border` / `--color-fg-muted` — no raw hues.
- **FR-B5 upheld (see FR-3):** disabled-Lesson render when `comingSoon`.
- **C1 / C4 (composition-root-only env reads):** no env read added.
- **B6 (Route Handlers = composition adapters):** untouched.
- **FE-AP-6 (mutating sealed envelope):** N/A.
- **AP-6 (honest absent):** FR-1 / FR-2 / FR-6 uphold this — the card and
  framed-title body render only when a real source produced them.

### Security / trust boundaries

- No secret read, no `.env` change, no new dependency (see §12 Q1 — the
  D4 decision means the misconception is authored content, not runtime
  synthesis; no LLM call in the summary hot path).
- Item-bank cascade (ADR-0021) governs how misconception values earn
  `reviewed = true` — same discipline as `why_correct_md`, `rule_md` today.
  A row's `misconception` is either author-provided + review-earned, or
  `null`.
- No live LLM in CI (root `AGENTS.md`) — misconception is a static column,
  never generated at Summary-render time.

## 6. Edge cases

- **`ended_at == null`** (session not yet closed): today's `use_summary`
  reads it via `sessionRepo.get` and the translator already renders "—" for
  the time tile. FR-1 / FR-2 apply — the misconception path is a no-op in
  this case (no closed session should reach Summary, but the code path
  survives).
- **`ended_at` present but `score_total == 0`** (immediate close): FR-8
  governs — neutral title/body, no framed copy, no misconception (no misses
  to derive from).
- **Recommended-next skill differs from the session's own `skill_focus`**:
  the derivation reads misses **on the recommended-next skill within THIS
  session's attempts** (FR-12). If there are no such misses (rare — the
  scheduler picked a skill the learner never touched this session), FR-2
  applies (no misconception).
- **Attempted questions whose `Question` row has been deleted / not yet
  loaded**: `questionRepo.getMany` returns a subset map. FR-12 falls
  through to `null` for any missing id — never throws.
- **Two misses on the same skill with different `misconception` texts**:
  FR-12 says "most-recent" — the last incorrect attempt's item wins.
  Deterministic (attempt order is timestamp+id from schema).
- **`Question.misconception` is present but empty string (`""`)**: Zod
  `.nullable()` allows `""`, which is truthy-null-like. The hook MUST
  normalize `misconception === ""` to `null` before passing to the
  translator (FR-1 branch treats it as absent).
- **`target_count == null`** (endless session): FR-11 falls back to
  "Drill: {skillName}" (no number prefix). Never fabricates "0-item drill".
- **`screen("skill").comingSoon` flips to `false` mid-release** (Epic E
  ships): FR-3 automatically stops disabling the Lesson button — no code
  change needed on the C2 side. Verified by the nav-model precedent.
- **Dark theme:** the misconception card + three-actions row hold WCAG-AA in
  both themes (S1 fix precedent — brand accent, not bucket).
- **Cold Summary render** (`baseVm == null` or read throws): today's page
  renders "Loading your session…" / error state — unchanged. The five-leg
  `Promise.all` cascades error identically (as one rejection).

## 7. Non-functional requirements

- **Determinism.** Full — no LLM at render, no clock inside the translator
  (`nowISO` is injected). All tests deterministic (L1).
- **Latency.** The fourth+fifth `Promise.all` legs add one indexed read
  (`attemptRepo.sessionAttemptsInOrder(sessionId)`) and a small `getMany`
  batch. Net: ~1–2 ms Node p50 vs today; negligible browser paint impact.
- **Reversibility.** Fully reversible — additive nullable wire+schema
  fields; corpus rows keep `misconception: null` if the sprint is reverted.
- **No live LLM.** Misconception is authored, not synthesized. Content pass
  is a separate track (calendar-load-bearing), not on the CI hot path.
- **Bundle.** No new dep; no new adapter family; no new SDK import.

## 8. Test plan

Failure-path tests first (§3 order preserved). L1 unless noted.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `use_summary.test.ts::renders_no_misconception_card_when_question_misconception_null` | L1 | yes |
| FR-2 | `use_summary.test.ts::renders_no_misconception_when_no_misses_on_recommended_skill` | L1 | yes |
| FR-3 | `SummaryView.test.tsx::see_lesson_renders_disabled_when_screen_comingSoon` | L1 | yes |
| FR-4 | `coach/page.test.tsx::onWrapUp_falls_back_to_summary_route_when_readActiveQuiz_returns_null` (only landed with FR-18) | L1 | yes |
| FR-5 | `frontend/tests/architecture/test_c2_soft_gate.test.ts::coach_page_does_not_import_readActiveQuiz_when_export_absent` (ts-morph) — also asserts `page.tsx` does not import a non-existent `readActiveQuiz` symbol from `quiz_session_store` | L1 | yes |
| FR-6 | `_test_item_bank.test.ts::emits_misconception_key_even_when_null` | L1 | yes |
| FR-7 | `session_summary_vm.test.ts::keeps_neutral_title_when_score_ratio_below_threshold` | L1 | yes |
| FR-8 | `session_summary_vm.test.ts::treats_score_total_zero_as_below_threshold` | L1 | yes |
| FR-9 | `engine_entities.test.ts::question_schema_accepts_misconception_null_and_string` | L1 | yes |
| FR-10 | `engine_repos.test.ts` (existing conformance) `+ testitem_misconception_roundtrip` | L1 | yes |
| FR-11 | `session_summary_vm.test.ts::drill_title_uses_target_count_when_present_and_skill_name_when_null` | L1 | yes |
| FR-12 | `use_summary.test.ts::derives_misconception_from_last_incorrect_attempt_on_recommended_skill` | L1 | yes |
| FR-13 | `session_summary_vm.test.ts::flips_framed_title_at_ratio_gte_0_6` (+ self-correction body variant) | L1 | yes |
| FR-14 | `session_summary_vm.test.ts::self_correction_signal_detects_first_half_miss_second_half_clean` | L1 | yes |
| FR-15 | `SummaryView.test.tsx::renders_summary_misconception_section_when_vm_misconception_present` | L1 | yes |
| FR-16 | `SummaryView.test.tsx::renders_three_actions_in_order_with_correct_hrefs` | L1 | yes |
| FR-17 | `e2e/learn/summary-payoff.spec.ts::skill_link_still_navigates_to_focused_quiz` | e2e | yes (learn-e2e) |
| FR-18 | `coach/page.test.tsx::onWrapUp_appends_session_query_when_readActiveQuiz_present` (L1); AND when `e2e/learn/validate_epic_ab.spec.ts` exists on `main` at merge time, unwrap its FLAG-5 `test.fail()` (e2e) | L1 (+ e2e if avail.) | yes |

Additional e2e (learn-e2e project):

- `e2e/learn/summary-payoff.spec.ts` — one item flow (authored misconception):
  finish session → Summary renders framed title + misconception card + three
  actions + disabled Lesson.
- Same spec, second variant — session on an item whose `misconception == null`:
  neutral title, no misconception card, three actions still render.
- Framed-title body branches — self-correction TRUE and FALSE cases.
- Axe sweep (`summary-payoff.spec.ts::axe_clean_light_and_dark`) — reuses
  the S1 pattern.

## 9. Definition of Done

- [ ] All FRs implemented; each has a passing test *seen to fail first*
      (watched-red, root `AGENTS.md`).
- [ ] `Question.misconception` on the wire + `TestItem.misconception` +
      Drizzle migration file committed + `_test_item_bank.ts` regenerated
      with the new key (all rows `null` initially).
- [ ] `SessionSummaryVM` + `RecommendedNextVM` grow the fields in §4;
      translator remains pure (T1).
- [ ] `use_summary` derives misconception + self-correction with no new port.
- [ ] Misconception accent card renders when present; absent otherwise
      (FR-1 / FR-15).
- [ ] Framed title (title + body) branches on ratio + self-correction
      (FR-7 / FR-13 / FR-14).
- [ ] Three actions row with disabled Lesson while `comingSoon` (FR-3 /
      FR-16); `summary-skill-link` still present (FR-17).
- [ ] **FLAG-5 wire** in place iff continuity-fixes is on `main`; otherwise
      ship without it and the `test.fail()` guard stays put with an entry in
      `decisions.md` explaining the deferral (FR-5 / FR-18).
- [ ] Seed content pass — target N = probe-based (see §12 Q2); if probe
      returns 0, spec allows zero-content merge (FR-6).
- [ ] `make check` + `pnpm test` + frontend `test:arch` + `learn-e2e`
      Playwright green.
- [ ] Backend `tests/architecture/` green (arch-tests unchanged — no
      backend seam moved).
- [ ] **ADR** written and Accepted (see §11 Gates).
- [ ] `docs/adr/decisions.md` entries for: framed-title threshold value
      (§12 Q3), self-correction algorithm (§12 Q4), FLAG-5 soft-gate
      posture (§12 Q1), item-bank `misconception` seed-count probe result
      (§12 Q2).

## 10. Implementation evidence

*Populated at Stage 6 (sdd-implement). Watched-red trail + evidence for
every FR + `make check` output + screenshots for FR-15/FR-16.*

### T0.1 Baseline (2026-07-10, pre-Block-1)

| Gate | Result | Notes |
|------|--------|-------|
| `make check` | **GREEN** — 5277 passed, 51 skipped, 72 deselected | ~216s |
| `pnpm test` (frontend Vitest) | **3 RED (pre-existing)** — 1595 passed / 3 failed | See below |
| `pnpm run test:arch` | **5 RED (pre-existing timeouts)** — 166 passed / 5 failed | ts-morph 10s timeouts under load |
| `.venv/bin/python -m pytest tests/architecture/ -q` | **GREEN** — 181 passed, 3 skipped | ~69s |
| `pnpm exec playwright test --project=learn-e2e` | *(recording)* | |

**Pre-existing reds (not caused by C2 — documented before Block 1):**

1. `components/quiz/QuizView.test.tsx` — Reveal `disabled` attr expected `false`, got `undefined`.
2. Arch ts-morph suites timing out at 10s under parallel load (`test_frontend_layering`, `test_engine_port_conformance`, `test_adapter_conformance`, `test_port_conformance`).

C2 does not touch quiz Reveal or those scanners. Re-check at T8.4.

### T0.2–T0.3 ADR

- Authored `docs/adr/0027-question-misconception-field.md` (Accepted 2026-07-10).
- `docs/adr/index.md` + `docs/adr/log.md` updated.
- `pytest tests/architecture/test_adr_ratchet.py -q` → **1 passed**.

### Stage-6 evidence trail (Blocks 1–8)

| Block | Evidence |
|-------|----------|
| 1 Wire+Drizzle | T1.1/T1.2 watched red (`misconception: 42` stripped); green after Zod+column+mappers. Migration hand-authored `frontend/drizzle/0001_add_misconception_to_test_item.sql` (engine has no drizzle-kit pipeline — S3 T-a3 N/A posture). |
| 2 Translator | T2.1 7 red → T2.2 14 green. `SUMMARY_FRAMED_TITLE_RATIO = 0.6`. |
| 3 Hook | T3.1 6 red → 13 green. No `getMany` / `sessionAttemptsInOrder` (T3.5). |
| 4 View | T4.1 5 red → 15 green. Misconception card + three-actions + framed title. |
| 5 e2e | `frontend/e2e/learn/summary-payoff.spec.ts` authored. |
| 6 Content | Probe **K=47**; authored 47 misconceptions in `promoted.json`; emit regenerates bank (171 keys, 124 null). |
| 7 FLAG-5 | Substrate count **0** → deferred (T7.1c). `coach/page.tsx` untouched. |
| 8 Soft-gate | `test_c2_soft_gate.test.ts` + five `decisions.md` lines appended. |

### Phase-1 converge classify (2026-07-10, post-merge #145)

- Merged: `95d9dc6` on `main`. C2 unit slice **56/56** green.
- CI deterministic reviewer / architecture / pytest: **SUCCESS**.
- CI `TS <-> Python wire schema parity` job: **FAILURE** on `tsc --noEmit`
  (not wire-schema drift — typecheck). Errors are **pre-C2**
  (`learnerReadRepo` vs `learnerRead`, `onAskCoach` exactOptional,
  `EngineProvider` children) — see tasks **Phase 1 — Convergence** T9.1–T9.5.
- FLAG-5: deferred by design (not a gap).
- Manual UI walk: human gate open (T9.6).

### Phase-1 implement (T9.1–T9.5) — 2026-07-10

- Branch: `fix/c2-phase1-typecheck-hygiene`
- Watched red: 6 `tsc` errors (learnerReadRepo / onAskCoach / EngineProvider children)
- Green: `pnpm --dir frontend exec tsc --noEmit` → exit 0
- Vitest: 68 passed (C2 slice + coach files touched)

## 11. Gates

- **G1 (new-abstraction gate) fires.** New wire field + new corpus contract
  = new derivation path. **ADR required** — `docs/adr/00XX-question-
  misconception-field.md`. Rejected alternatives:
  (a) LLM-synthesize misconception at Summary render time — rejected: C-4
      honesty (Summary would claim "I spotted a misconception" after 5
      items with no author signal); also puts an LLM call on the render
      hot path.
  (b) Attach to `Skill` — rejected: skill-level blurs it back to the skill
      name; prototype's "conciseness overrode punctuation" is item-specific.
  (c) Attach to `Attempt` at grade time — rejected: post-hoc; no author
      signal.
  (d) D5 Coach-runtime marker — rejected in Stage 1: only fires when the
      learner used the coach (adoption gap); keep as future variant if D4
      falters.
  (e) `Question.misconception_id` FK to a separate `misconception` table —
      rejected: over-abstracted; a nullable TEXT column suffices for the
      one-line copy the prototype shows.

- **Architecture invariants stressed:** #2 (untouched); F-R1 (upheld); T1
  (upheld); W1 / W3 (upheld — additive nullable); C4 (no new env read);
  U6 / U8 (upheld); FR-B5 (actively upheld via disabled Lesson).

- **⚠️ Ask-first triggers:**
  - **New corpus contract** (misconception field earns `reviewed=true` via
    the ADR-0021 cascade) — ADR.
  - **NOT a new port** (extends translator + hook only).
  - **NOT a new dep** (§12 Q1 — no new package).
  - **NOT a new node/service** (view-only).

## 12. Clarify pass

Auto-Mode recommendations (per the SDD skill's Stage-2 clarify contract). One
question at a time, each with a recommended answer + rationale. All four are
**ratified as recommended** unless the user redirects.

- **Q1 (FLAG-5 soft-gate).** Continuity-fixes spec is referenced by the
  board as "in flight, Approved 2026-07-10" but no `epic-ab-continuity-
  fixes.spec.md` exists on disk. Do we ship C2 with **any** interim FLAG-5
  wire, or defer the wire entirely?

  **Recommendation: defer entirely (FR-5).** Ship C2 chrome + all
  §3 items *except* FR-18. Leave the FLAG-5 `test.fail()` guard alone. A
  follow-up commit lands the wire the day continuity-fixes merges. Adds
  a `decisions.md` line noting the deferral. Rationale: any interim
  substrate (a `window.__PREACT_ACTIVE_QUIZ__` shim, an ad-hoc
  `sessionStorage` read, etc.) violates §12 store discipline and would be
  removed the moment the real API lands — net negative. **Ratified.**

- **Q2 (misconception seed-count).** How many bank items get authored
  misconception in the C2 sprint to make the card meaningful?

  **Recommendation: probe first, then N ≥ probe-return.** Run a
  `needs-probe` scan of the 60-row `_test_item_bank.ts` corpus at
  implementation time (looking for items where the `why_tempted_md`
  already hints at a one-line misconception — e.g. "The simple past 'rose'
  is the form we say most often" ⇒ misconception: "confusing simple past
  with past participle after 'had'"). If the probe returns K ≥ 5, the
  content pass authors K rows in this sprint. If K == 0, C2 ships
  code-only (FR-6 governs); the content pass becomes its own follow-up
  track. Records the probe result in `decisions.md`. **Ratified.**

- **Q3 (framed-title threshold).** What score ratio flips the title from
  neutral to "Nice work — you found the pattern."?

  **Recommendation: `correct/total >= 0.6`.** Prototype §5.5 example is
  7/10 (0.7); 0.6 gives room for 3/5, 4/6, 6/10, 9/15 — deliberately
  below the prototype's stated bar so we do not over-praise. Records in
  `decisions.md`. Hardcoded const in the translator; if it ever needs to
  be per-learner, an ADR moves it. **Ratified.**

- **Q4 (self-correction signal).** What deterministic pattern counts as
  "self-corrected the misconception" for the framed-title body?

  **Recommendation: attempt-index half-split** (FR-14). At least one
  incorrect attempt on the recommended-next skill in the first half of the
  session's attempts on that skill, AND at least one correct in the
  second half, AND no incorrect in the second half. Purely from
  `AttemptRepo.sessionAttemptsInOrder`; no new port; no clock; no timing
  heuristic. Records algorithm in `decisions.md`. **Ratified.**

## 13. Decisions ledger (to append at T-tail via `docs/adr/decisions.md`)

Five lines authored here; appended in the final task block, not inline:

1. **C2 framed-title threshold = 0.6.** Score ratio at which the neutral
   title flips to "Nice work — you found the pattern." Hardcoded const in
   `session_summary_vm.ts`. Rationale: prototype §5.5 uses 7/10 (0.7); 0.6
   is a deliberate 10-point undercut to avoid over-praise.
2. **C2 self-correction signal = attempt-index half-split.** First-half
   incorrect + second-half correct + no second-half incorrect on the
   recommended skill. Pure derivation from
   `AttemptRepo.sessionAttemptsInOrder`. No clock, no new port.
3. **C2 FLAG-5 wire deferred until continuity-fixes lands `readActiveQuiz`.**
   No interim substrate ships; `test.fail()` guard stays; follow-up commit
   flips it green when the real API is on `main`.
4. **C2 misconception seed-count = probe-based (K, records at impl time).**
   Content pass authors K rows where the existing `why_tempted_md` already
   implies a one-line misconception. K == 0 → code ships without any
   authored row; content is a separate follow-up track.
5. **C2 misconception field lives on the `Question` wire (D4 direction).**
   Not on `Skill`, not on `Attempt`, not derived at render. Rejects D5
   (Coach-runtime marker) and any Summary-time LLM synthesis. Authored on
   the `test_item` bank row; mapped through `TestItemQuestionRepo`.

---

## Handoff — next stages

**Stage 3 (Plan / Tasks / Analyze):** authored alongside this spec:
- Plan: [preact-parity-C2-summary-payoff.plan.md](preact-parity-C2-summary-payoff.plan.md)
- Tasks: [preact-parity-C2-summary-payoff.tasks.md](preact-parity-C2-summary-payoff.tasks.md)

**Stage 4 grounding pass:** confirmed all touched files exist and the
pre-fix state matches this spec's premise (see the plan §"Grounding pass").

**Stage 5 human gate:** advance to `sdd-implement` (Stage 6).

**Stage 6 (implement):** ADR authored first (Gates §11); Block 0 baseline
`make check` + `pnpm test` + `test:arch`; Block 1 wire + schema (FR-9 /
FR-10); Block 2 translator (FR-11 / FR-13 / FR-14 / FR-7 / FR-8); Block 3
hook (FR-12 / FR-1 / FR-2); Block 4 view (FR-15 / FR-16 / FR-3 / FR-17);
Block 5 e2e; Block 6 content-pass probe + N rows; Block 7 FLAG-5 wire (only
if substrate present, FR-18); Block 8 arch-test (FR-5) + decisions ledger +
PR.
