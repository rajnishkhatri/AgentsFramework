# Tasks — Epic E1a: `/learn/skill` adaptive lesson surface (3-context)

**Status:** Draft — 2026-07-11 · **Spec:** [`preact-parity-epic-E1a.spec.md`](preact-parity-epic-E1a.spec.md) · **ADR:** [`0028-lesson-content-read-path.md`](../adr/0028-lesson-content-read-path.md)

SDD Stage 3. Atomic, file-level tasks with dependency (`⇦ Tn`) and parallelization
(`∥ group`) markers. Each task states its **verify** (the seen-to-fail-first test) mapped
1:1 from the spec's EARS FRs. Red/green: write the test, watch it fail, implement, watch
it pass — paste the actual output.

**Legend:** `⇦` depends on · `∥A` may run in parallel with others in group A · `[ADR]`
this task realizes an ADR-0028 clause · layers L1 (vitest/RTL/pytest-arch, deterministic) /
L4 (Playwright e2e).

**Measurability notes (Stage-3 checklist).** Three FRs get a tightened test predicate so
they stay objectively decidable — carried into the task's *verify* below:
- **FR-8** — assert (a) the persisted `Tutorial` read type has **no** `blocks[]/zone/role/
  context/beats` field (compile/type assertion) + (b) the composer derives order from a
  fixed recipe map, not from data. ("Render-time" is not directly observable; these two
  proxies are.)
- **FR-6b** — assert the callout body is **byte-for-byte equal** to `question.misconception`
  (verbatim), plus no `fix`/aggregate DOM node. ("No transformed text" → concrete equality.)
- **FR-16** — assert the **self-omit** branch only (no rail accuracy node). The
  "renders-when-data-arrives" branch has no data source in E1a and is a follow-up.

---

## Phase 0 — Engine content read path (the ADR-0028 seam) · group A

> The durable content + read ports. Everything renderable depends on T3/T4.

### T1 — `[ADR]` Extend `Tutorial` with optional teaching fields (wire)
- **File:** `frontend/lib/wire/engine_entities.ts` (Tutorial `z.object`, currently :273-282).
- **Do:** add the optional fields per spec §4.1 — `ground_md`/`pitfall_md`/`question_md`/
  `self_explain_prompt` as `z.string().optional()`; `worked_example`/`completion_try`/
  `annotated_examples` as optional typed sub-objects (`completion_try.choices[]` carries a
  `correct` flag). Follow the `Verdict` optional-field precedent (:303-309). Do **NOT** add
  `blocks[]/zone/role/context/beats`.
- **Verify (FR-8a):** a vitest type/parse test — `Tutorial.parse()` accepts a row with the
  new fields and a row without them (all optional); a `@ts-expect-error` asserts no
  `blocks`/`zone`/`role` key exists on the inferred type. **Watch fail** (fields absent) → add → pass.
- **Deps:** none. **∥A** with T2.

### T2 — `[ADR]` Drizzle columns + migration for the teaching fields
- **Files:** `frontend/lib/adapters/engine/db/schema.pg.ts` (`tutorial` pgTable :265) +
  `schema.sqlite.ts` (sqlite mirror) + a new migration under `frontend/drizzle/`; update
  `toTutorial` mapper (`drizzle_engine_db.ts:195`) to read the new columns.
- **Do:** add nullable columns matching T1's fields (both dialects, parity-guarded); the
  migration adds columns only (no drop). `tablesFilter` still excludes LangGraph checkpoint
  tables.
- **Verify (FR-8b):** the existing dialect-parity architecture test passes (pg ≡ sqlite
  columns); a round-trip test seeds a row with teaching fields and reads it back equal via
  `toTutorial`. **Watch fail** → add columns → pass.
- **Deps:** ⇦ T1 (field names). **∥A** with T1 authoring but land T1 first.

### T3 — `[ADR]` `TutorialRepo` port + `DrizzleTutorialRepo` adapter
- **Files:** new `frontend/lib/ports/engine/tutorial_repo.ts` (single method
  `getTutorial(subject, skillId): Promise<Tutorial | null>`, JSDoc behavioral contract +
  `@throws EngineRepoError`, read-only — mirror `hint_repo.ts:26-29`); new
  `frontend/lib/adapters/engine/repos/drizzle_tutorial_repo.ts` (mirror
  `drizzle_hint_repo.ts` — constructor `(db: EngineDb)`, delegate to `db.getTutorial`,
  reviewed-gate defense-in-depth filter, `translate()` → `EngineRepoError`).
- **Verify (FR-1, FR-17):** conformance test — an **unreviewed** tutorial row is NOT returned
  (reviewed gate); the port has no write method (type assertion). **Watch fail** → implement → pass.
- **Deps:** ⇦ T1. **∥B** with T4.

### T4 — `[ADR]` `ProgressRepo` port + `DrizzleProgressRepo` adapter
- **Files:** new `frontend/lib/ports/engine/progress_repo.ts` (`list(subject, learnerId):
  Promise<ProgressPoint[]>`, read-only) + new `frontend/lib/adapters/engine/repos/drizzle_progress_repo.ts`
  (delegate to `db.listProgressPoints`).
- **Verify (FR-17):** conformance test — returns `[]` (not throw) on no data; no write method.
  **Watch fail** → implement → pass.
- **Deps:** ⇦ (uses existing `ProgressPoint` type). **∥B** with T3.

### T5 — `[ADR]` Wire both repos into `EnginePortBag`
- **File:** `frontend/lib/composition_engine.ts` — add `tutorialRepo`/`progressRepo` fields to
  `EnginePortBag` (near :75) + `new DrizzleTutorialRepo(db)`/`new DrizzleProgressRepo(db)` in
  `buildEngineAdapters` (near :136), following the `hintRepo` pattern.
- **Verify (FR-17):** a wiring test asserts the bag exposes both repos and they read through
  the live seam. **Watch fail** → wire → pass.
- **Deps:** ⇦ T3, T4.

### T6 — `[ADR]` Authored lesson seed + provenance-confinement test (one skill)
- **Files:** a seed file under `frontend/lib/adapters/engine/` (the `_*_seed.ts` pattern) with
  ONE skill's full lesson content (all block copy), stamped `reviewed:true` +
  `generated_from="hand:<author>@<date>"`, human-leak-checked; new
  `tests/architecture/test_tutorial_provenance_confinement.py` mirroring
  `test_hint_provenance_confinement.py` (accepts `hand:<author>@<date>` |
  `llm:<model>@<promptrev>`, rejects a bare unstamped `reviewed:true`).
- **Verify (FR-2):** the confinement test **fails** on a deliberately-bad `generated_from`,
  passes on the real seed. **Watch fail** (write a bad-stamp fixture) → author test → pass.
- **Deps:** ⇦ T1 (fields to author into). **∥C** with T7 (independent file).

---

## Phase 1 — Pure translators (no I/O; table-driven) · group C

### T7 — `selectLessonContext` T1 translator
- **File:** new `frontend/lib/translators/select_lesson_context.ts` — pure function per spec
  §4.1/§4.2, imports only `wire/` + a local `LearnerLessonState`/`LessonContext`; mirror
  `bucket_card_vm.ts` shape (JSDoc T1 purity contract). Co-locate `select_lesson_context.test.ts`.
- **Verify (FR-4, FR-5):** `describe.each` seeded from the design spec §9.2 5-row table +
  the AC-2 `requested`-override case + the AC-3 "tag on non-due miss does not flip" case.
  **Watch fail** → implement the if/else ladder → pass.
- **Deps:** none. **∥C** with T6, T8.

### T8 — newest-due-miss join translator
- **File:** new `frontend/lib/translators/newest_due_miss.ts` — pure function taking already-
  fetched `misses` (newest-first) × `skillStates` (`due_at`) × `questions` (for
  `misconception`); returns the newest miss whose skill is due + its verbatim tag, or `null`.
  Mirror `use_summary.ts:79-95` `deriveMisconception`. Co-locate the test.
- **Verify (FR-16a, FR-16b):** table-driven — (a) tagged newest-due → verbatim tag; (b) no
  due miss → `null`; (c) untagged due miss → `null` (tier-3). **Watch fail** → implement → pass.
- **Deps:** none. **∥C** with T6, T7.

### T9 — `skill_detail_vm.ts` (honest-null composer VM)
- **File:** new `frontend/lib/translators/skill_detail_vm.ts` — composes selector output +
  recipe map → ordered `BlockVM[]` (main/rail zones, resolved role tint, `order`); honest-null
  (mirror `coach_surface_vm.ts:94-104`). Holds the recipe map per context (§5.1 of the design
  spec) and the role→token resolution (§2.4). Co-locate the test.
- **Verify (FR-7, FR-8b, FR-9, FR-10):** (7) newSkill recipe order, no other blocks; (8b)
  order comes from the recipe map given raw fields, not a persisted array; (9) a tag with no
  backing field is skipped (no empty VM); (10) main zone ends on `completionTry`, never on
  `pitfall` pre-`rule`. **Watch fail** → implement → pass.
- **Deps:** ⇦ T7 (selector output shape). **∥D** with T10.

### T10 — returning/refresher recipes in the VM
- **File:** `frontend/lib/translators/skill_detail_vm.ts` (extend T9).
- **Verify (FR-6a, FR-6c, FR-6d):** (6a) returning tagged → `misc→annotated→rule`; untagged →
  `annotated→rule`; (6c) untagged hides callout, no miss-count line; (6d) refresher →
  `rule→annotated→pitfall(parting)`, ends on parting `pitfall`. **Watch fail** → extend → pass.
- **Deps:** ⇦ T9, ⇦ T8 (due-miss for the callout tier). **∥D** with T9 authoring but land T9 first.

---

## Phase 2 — The surface (route + blocks + interaction) · group E

### T11 — `/learn/skill` route shell
- **Files:** new `frontend/app/(coach)/learn/skill/page.tsx` (mirror `learn/coach/page.tsx`
  RSC/client-leaf split), accepts `skillId` (await `searchParams`, Next 15); a host hook does
  the I/O (`TutorialRepo.getTutorial` + `LearnerReadRepo.listSkillState` + `AttemptRepo.misses`)
  and passes fetched arrays to the pure VM (T9/T10).
- **Verify (FR-19, FR-3, FR-18):** e2e — valid skill renders; unknown/absent `skillId` →
  404-equiv; no reviewed content → honest empty state (not fabricated). **Watch fail** (route
  404s) → build → pass.
- **Deps:** ⇦ T5 (repos wired), ⇦ T9/T10 (VM), ⇦ T6 (seed to render).

### T12 — Block renderers (presentational, role-tinted, a11y)
- **Files:** block components under `frontend/components/learn/` (or the skill surface dir) —
  `ground`/`pitfall`/`question`/`rule`/`workedExample`/`annotatedExample`/`misconceptionCallout`/
  `dueChecklist`/`accuracyStat`/`coachEntry`, each rendering a `BlockVM` in its role tint with
  a **text label** (never color alone, AL-25/AL-AC-8). `cn()` for classes; `data-*` for state.
- **Verify (FR-6b, FR-6e, FR-11, FR-16):** (6b) callout body byte-equal to
  `question.misconception`, no `fix`/aggregate node; (6e) returning rail = `dueChecklist`
  whole-skill rows + `coachEntry` seam button; (11) exactly one "▸ start here", no color-dot
  sequence; (16) `accuracyStat` self-omits (no rail accuracy node). Plus axe on the route.
  **Watch fail** → build → pass.
- **Deps:** ⇦ T9/T10 (VM feeds them), ⇦ T11 (mounted in the route).

### T13 — `completionTry` interactive (inert to scheduler)
- **File:** the `completionTry` block component (T12) + its local state.
- **Verify (FR-12, FR-13):** (12) click grades locally (✓/✗, reveal on miss, ↺, success CTA)
  AND a spy asserts **no** `attemptRepo.record` / `scheduler.review` call; (13) a wrong pick
  does not change subsequent blocks. **Watch fail** → implement → pass.
- **Deps:** ⇦ T12. **∥E** with T14.

### T14 — `selfExplainPrompt` local echo (never stored)
- **File:** the `selfExplainPrompt` + `rule` block components (T12).
- **Verify (FR-14):** typing a note echoes it in the `rule` block ("You guessed: …"); a spy
  asserts nothing is persisted/scored; empty/whitespace note → no echo chip. **Watch fail** →
  implement → pass.
- **Deps:** ⇦ T12. **∥E** with T13.

### T15 — "Practice this skill →" CTA (skill-pinned drill)
- **File:** the `completionTry` success CTA (T13) — a link to `/learn/quiz?focus=<skillId>`
  (the `BucketCard.tsx:26`/`SummaryView.tsx:44` pattern; drill already pins, `use_quiz.ts:177-225`).
- **Verify (FR-15):** e2e — activating the CTA navigates to `/learn/quiz?focus=<skillId>` and
  the drill serves only that skill. **Watch fail** → wire href → pass.
- **Deps:** ⇦ T13.

---

## Phase 3 — Nav activation (do-regardless plumbing) · group F

### T16 — Flip `comingSoon` + add `skill` to `NAV_MEMBERSHIP`
- **File:** `frontend/components/shell/nav_model.ts` — `skill` `comingSoon: true → false` (:75);
  add `"skill"` to `NAV_MEMBERSHIP` desktop/ipad (and iphone per the membership rules) (:104-106).
- **Verify (FR-20 part 1):** nav unit test — `skill` screen resolves to a live `href`
  (not disabled) and appears in the membership list(s). **Watch fail** → flip → pass.
- **Deps:** ⇦ T11 (route must exist before nav points at it). **∥F** with T17.

### T17 — Rewrite the `summary-see-lesson` e2e assertion (G8)
- **File:** `frontend/e2e/learn/summary-payoff.spec.ts:130-143` — the test currently asserts
  the lesson button `toBeDisabled()` / `aria-disabled` while `comingSoon`; rewrite to assert
  the now-live `<Link href={skillScreen.route}>` (href present, not disabled). The
  `summary-skill-link` tests (:91-103) and `summary-cta.spec.ts:103` are **unaffected** (they
  target the always-live focus-drill link).
- **Verify (FR-20 part 2):** the rewritten test passes with `comingSoon:false`; **G8
  justification** in the test/commit: the disabled-button branch it asserted no longer exists
  once flipped, so the assertion is replaced (not weakened) — the live-Link path is a stronger
  claim. **Watch fail** (old assertion breaks post-flip) → rewrite → pass.
- **Deps:** ⇦ T16. **∥F** with T16 authoring but land T16 first.

---

## Verification matrix (FR → task → layer)

| FR | Task(s) | Layer |
|----|---------|-------|
| FR-1 | T3 | L1 |
| FR-2 | T6 | L1 (pytest arch) |
| FR-3 / FR-18 | T11 | L1 + L4 |
| FR-4 | T7 | L1 |
| FR-5 | T7 | L1 |
| FR-6 | T9,T10 (paths reachable) | L1 |
| FR-6a | T10 | L1 |
| FR-6b | T12 | L1 |
| FR-6c | T10 | L1 |
| FR-6d | T10 | L1 |
| FR-6e | T12 | L1 |
| FR-7 | T9 | L1 |
| FR-8 | T1 (type-absence) + T9 (recipe-map) | L1 |
| FR-9 | T9 | L1 |
| FR-10 | T9 | L1 |
| FR-11 | T12 | L1 |
| FR-12 | T13 | L1 |
| FR-13 | T13 | L1 |
| FR-14 | T14 | L1 |
| FR-15 | T15 | L4 |
| FR-16 | T12 (self-omit branch) | L1 |
| FR-16a | T8 | L1 |
| FR-16b | T8 | L1 |
| FR-17 | T3,T4,T5 | L1 |
| FR-19 | T11 | L4 |
| FR-20 | T16 (nav) + T17 (e2e rewrite) | L1 + L4 |

Every FR has ≥1 task with a seen-to-fail-first test. No FR is unmapped.

## Dependency graph (topological)

```
T1 ─┬─ T2                          (wire → drizzle)
    ├─ T3 ─┐
    ├─ T4 ─┤
    └─ T6  │
           └─ T5 ──┐               (repos → bag)
T7 ────────────────┤
T8 ────────────────┤
           T9 ⇦ T7  │
           T10 ⇦ T9,T8
                    └─ T11 ⇦ T5,T9,T10,T6
                          ├─ T12 ─┬─ T13 ─ T15
                          │       └─ T14
                          └─ T16 ─ T17
```

**Parallelizable groups:** {T1,T6} · {T3,T4} · {T7,T8} · {T9,T10 author} · {T13,T14} ·
{T16,T17 author}. Critical path: T1 → T5 → T11 → T12 → T13 → T15.

## Definition of Done (rolls up spec §9)

- [ ] All 17 tasks complete; each FR test seen to fail first, output pasted.
- [ ] `make check` green · `pytest tests/architecture/ -q` green (incl. T6's confinement test).
- [ ] Frontend arch/layering + axe green; e2e T11/T15/T17 green.
- [ ] ADR-0028 ratified (Proposed → Accepted) at this tasks→implement gate; `decisions.md`
      line if any sub-choice (e.g. teaching-field granularity) lands outside the ADR.
- [ ] One skill's lesson seed authored + leak-checked + honestly stamped.
- [ ] Design contract AC-1..AC-17 satisfied for all three contexts except the §1.1 carve-outs
      (accuracyStat real-data render + tier-1 aggregate callout).
```
