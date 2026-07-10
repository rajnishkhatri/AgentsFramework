# Plan — PreAct Parity Sprint C2: Summary payoff

**Belongs to:** [preact-parity-C2-summary-payoff.spec.md](preact-parity-C2-summary-payoff.spec.md)
**Board:** [preact-parity-sprint-board-C.md](preact-parity-sprint-board-C.md) §Sprint C2
**ADR:** `docs/adr/00XX-question-misconception-field.md` — authored in Block 0 of tasks.
**Date:** 2026-07-10

---

## 1. Architecture map

```
                        ┌──────────────────────────────────────────────┐
                        │  Item-bank corpus (ADR-0021 cascade)           │
                        │  docs/plan/coach-item-bank-live.promoted.json  │
                        │        │                                       │
                        │        ▼  scripts/emit_test_item_bank.py       │
                        │  frontend/lib/adapters/engine/_test_item_bank.ts│
                        └───────────────────┬────────────────────────────┘
                                            │  seeded into
                                            ▼
     [Wire — W1/W3/W7]           [DB — Drizzle additive]
frontend/lib/wire/engine_entities.ts           schema.pg.ts
  ┌──────────────────────┐              ┌──────────────────────┐
  │ Question             │              │ testItem             │
  │  + misconception     │◄──map────────│  + misconception     │
  │    (string|null)     │              │    (TEXT NULL)       │
  │ TestItem             │              │                      │
  │  + misconception     │              │  migration: additive │
  │    (string|null)     │              │  nullable column     │
  └──────────┬───────────┘              └──────────────────────┘
             │
             │ read via
             ▼
    [Hook — F-R1]              [Ports (unchanged)]
  use_summary.ts               attemptRepo.misses               ← existing
  ┌──────────────────────┐     attemptRepo.servedQuestionIds    ← existing
  │ Promise.all 5-leg:   │◄─── sessionRepo.get                  ← existing
  │  session + skills    │     learnerRead.listSkillState       ← existing
  │  states + all-time   │     skillTaxonomy.list               ← existing
  │  misses + served ids │
  │                      │     Bounded loop after parallel legs:
  │ Derives:             │◄─── questionRepo.get(id)  ← ≤ session
  │  - session-scoped    │        length (S3 cap = 30); no getMany
  │    misses = misses   │        introduced (G1 abstraction rule)
  │    ∩ servedIds       │
  │  - misconception     │  (FR-12: last session-scoped miss on rec skill)
  │  - selfCorrected     │  (FR-14: attempt-index half-split, session-scoped)
  │  - scoreRatioMet     │  (FR-13: score_correct/score_total ≥ 0.6)
  └──────────┬───────────┘
             │ pushes derived scalars into
             ▼
    [Translator — T1 pure]
  session_summary_vm.ts
  ┌──────────────────────┐
  │ toSessionSummaryVM(  │
  │  session,            │
  │  recommended,        │
  │  nextSkill,          │
  │  masteryDeltaPct,    │
  │  misconception,      │  ← new
  │  selfCorrected,      │  ← new
  │  scoreRatioMet,      │  ← new
  │ ): SessionSummaryVM  │
  │                      │
  │ Emits VM fields:     │
  │  title / body        │  (branches based on scoreRatioMet + selfCorrected)
  │  misconception       │  (pass-through, "" normalized to null)
  │  recommended.drillTitle
  │  selfCorrected       │
  └──────────┬───────────┘
             │
             ▼
    [View — F-R1 presentational]
  SummaryView.tsx
  ┌──────────────────────────────────────────────────────┐
  │ <header>{vm.summary.title}<p>{vm.summary.body}</p></header>│
  │                                                        │
  │ {vm.summary.misconception && (                        │
  │   <section aria-label="The misconception I spotted"   │
  │            data-testid="summary-misconception">…      │
  │ )}                                                    │
  │                                                        │
  │ <dl> [existing 3 stat tiles]                          │
  │                                                        │
  │ <section aria-label="Recommended next"…               │
  │   <Link data-testid="summary-skill-link"…             │  ← preserved (S-5)
  │                                                        │
  │ <div role="group" aria-label="Session actions">       │
  │   <Link data-testid="summary-start-next"…             │  primary
  │   {screen("skill").comingSoon                         │
  │    ? <button disabled aria-disabled="true"…          │  secondary
  │    : <Link data-testid="summary-see-lesson"…}         │
  │   <Link data-testid="summary-done"…                   │  tertiary
  │ </div>                                                 │
  └────────────────────────────────────────────────────────┘

    [Coach onWrapUp — soft-gated seam]
  frontend/app/(coach)/learn/coach/page.tsx:101-104
  IFF continuity-fixes has landed readActiveQuiz():
    const id = readActiveQuiz()?.sessionId;
    router.push(id ? `${sumRoute}?session=${id}` : sumRoute);
  ELSE: no change; test.fail() stays put (FR-5, FR-18)
```

---

## 2. File-level touchpoints

Grouped by layer, in migration order. Every touch traces to one or more FRs
from `spec.md §3`.

### Group A — Wire kernel (Block 1)

- `frontend/lib/wire/engine_entities.ts`
  - **FR-9.** Add `misconception: z.string().nullable()` to `Question`.
  - **FR-10.** Add `misconception: z.string().nullable()` to `TestItem`.
  - No breaking rename. Field appears after existing rationale fields
    (grouped with author-supplied content).

- `frontend/lib/wire/engine_entities.test.ts` (may or may not exist; if
  absent, create per T4 table-driven pattern).
  - **FR-9.** New test — `Question` accepts `misconception: null` and
    `misconception: "some string"` and rejects `misconception: 42`.

### Group B — Drizzle schema + migration (Block 1)

- `frontend/lib/adapters/engine/db/schema.pg.ts`
  - **FR-10.** Add `misconception: text("misconception")` to `testItem`
    (no `.notNull()` → Postgres NULL-able).
- `frontend/drizzle/00NN_add_misconception_to_test_item.sql` — auto-generated
  by `pnpm drizzle-kit generate`. Verify additive nullable statement only.
- `frontend/lib/adapters/engine/db/in_memory_engine_db.ts`
  - No structural change (in-memory rows already carry any extra keys).
  - Verify `TestItemRepo.listReviewed` returns rows with `misconception`
    round-tripped (conformance test row).

### Group C — Item-bank emitter + regeneration (Block 6)

- `scripts/emit_test_item_bank.py`
  - Update the emitter to include the new `misconception` key on every
    emitted row (value: from `promoted.json` if present, else literal
    JSON `null`). **FR-6.**
- `docs/plan/coach-item-bank-live.promoted.json` — content-pass edits
  (only rows the probe surfaces; K rows).
- `frontend/lib/adapters/engine/_test_item_bank.ts` — **regenerated file**
  (not hand-edited); every row gains the `misconception` key.

### Group D — Translator (Block 2)

- `frontend/lib/translators/session_summary_vm.ts`
  - **FR-11 / FR-13 / FR-7 / FR-8 / FR-14.**
  - `SessionSummaryVM` grows: `title`, `body`, `misconception`,
    `selfCorrected`, `showFramedTitle`.
  - `RecommendedNextVM` grows: `drillTitle`.
  - `toSessionSummaryVM` gains three scalar params: `misconception: string
    | null`, `selfCorrected: boolean`, `scoreRatioMet: boolean`.
  - Internal helpers: `framedTitle()`, `framedBody()`, `drillTitleFrom()`.
    Pure — no `Date.now`, no React, no I/O.
  - Constant `SUMMARY_FRAMED_TITLE_RATIO = 0.6` exported for test reuse
    (§12 Q3 decision).

- `frontend/lib/translators/session_summary_vm.test.ts`
  - Table-driven cases per FR (T4). See test-plan crosswalk (`spec §8`).

### Group E — Hook (Block 3)

- `frontend/components/summary/use_summary.ts`
  - **FR-12 / FR-1 / FR-2.**
  - Adds two Promise.all legs (both existing port methods):
    `attemptRepo.misses(subject, learnerId)` (newest-first, all sessions)
    and `attemptRepo.servedQuestionIds(sessionId)` (session-scoped set).
  - Intersects: session-scoped-misses = `misses` filtered by `served`,
    newest-first order preserved.
  - Bounded sequential loop after `Promise.all`: walk session-scoped-misses,
    `await questionRepo.get(id)`, stop at first
    `question.skill_id === recommendedSkillId` — that miss's item's
    `misconception` is the derived value (or `null` if none found).
  - Similarly derives session-scoped correct attempts on the recommended
    skill as `served \ misses` filtered by skill for `selfCorrected`
    (FR-14 half-split).
  - Derives `scoreRatioMet` from the session tally directly.
  - Normalizes `misconception === ""` → `null`.
  - Passes derived scalars into `toSessionSummaryVM`.
  - No new port. No env read (C4 preserved). No SDK import (F-R2).

- `frontend/components/summary/use_summary.test.ts`
  - New table-driven cases: absent misconception, self-correction TRUE,
    self-correction FALSE, no misses on rec skill, `score_total==0`.
  - Test bag: `InMemoryEngineDb` seeded via the existing `_dev_seed`
    precedent + `attemptRepo.record` calls.

### Group F — View (Block 4)

- `frontend/components/summary/SummaryView.tsx`
  - **FR-15 / FR-16 / FR-3 / FR-17.**
  - Wraps the neutral copy with `vm.summary.title` / `vm.summary.body`.
  - Adds the `<section aria-label="The misconception I spotted"
    data-testid="summary-misconception">` conditional block.
  - Replaces the single CTA with the three-actions row.
  - Preserves `summary-skill-link` testId + href.
  - Uses `cn()` (U6); state-driven via `data-*` attributes (§13 style guide).

- `frontend/components/summary/SummaryView.test.tsx`
  - New cases (see spec §8 crosswalk).

### Group G — Coach seam (Block 7 — soft-gated)

- `frontend/app/(coach)/learn/coach/page.tsx:101-104` — **FR-18.**
  Only landed when `quiz_session_store` exports `readActiveQuiz`. At
  Block-7 time, check `grep -c "export.*readActiveQuiz"` on that file:
  - result > 0 → land FR-18 wire; unwrap `test.fail()` in
    `e2e/learn/validate_epic_ab.spec.ts`.
  - result == 0 → skip FR-18 entirely; add a `decisions.md` line noting
    the deferral; the FR-5 arch-test (below) blocks a phantom import.

### Group H — Arch test for the soft-gate (Block 8)

- `frontend/tests/architecture/test_c2_soft_gate.test.ts` (new, ts-morph).
  - **FR-5.** Walks the coach `page.tsx` AST. If `readActiveQuiz` symbol
    is NOT exported from `quiz_session_store`, then `page.tsx` MUST NOT
    import it. Prevents a red-import merge race.
  - Bidirectional: if `readActiveQuiz` IS exported and used in
    `page.tsx`, the test asserts the corresponding `test.fail()` in
    `validate_epic_ab.spec.ts` has been unwrapped (matches FR-18).

### Group I — Decisions ledger + PR (Block 8)

- `docs/adr/decisions.md` — append the five lines from `spec §13`.
- `docs/adr/00XX-question-misconception-field.md` — full ADR (authored in
  Block 0 alongside the spec, per §11 Gates).

---

## 3. Migration order (watched-red discipline)

Blocks fire in strict order — each ends with green tests. Every code change
lands its **red test first** (`AGENTS.md` — the ratchet rule).

```
Block 0  Baseline + ADR
         (a) make check + pnpm test + pnpm run test:arch — record baseline green
         (b) author docs/adr/00XX-question-misconception-field.md (Status: Accepted)
         (c) append docs/adr/log.md line + index.md entry

Block 1  Wire + Drizzle (red → green)
         (a) [red] add engine_entities.test.ts cases FR-9 → fail
         (b) [green] add misconception to Question + TestItem
         (c) [red] add testitem_misconception_roundtrip conformance row → fail
         (d) [green] add misconception column in schema.pg.ts + generate migration

Block 2  Translator (red → green)
         (a) [red] session_summary_vm.test.ts cases FR-11/13/14/7/8 → fail
         (b) [green] extend toSessionSummaryVM with three params + helpers
         (c) [green] export SUMMARY_FRAMED_TITLE_RATIO = 0.6

Block 3  Hook (red → green)
         (a) [red] use_summary.test.ts FR-12/1/2 → fail
         (b) [green] extend Promise.all to 5 legs + derive scalars
         (c) [green] normalize "" → null

Block 4  View (red → green)
         (a) [red] SummaryView.test.tsx FR-15/16/3/17 → fail
         (b) [green] misconception card + three-actions row + title/body swap
         (c) [green] disabled Lesson via data-* + aria-disabled

Block 5  e2e (red → green)
         (a) [red] e2e/learn/summary-payoff.spec.ts FR-17/framed-title
             branches + axe → fail
         (b) [green] via the code already landed in Blocks 1–4 (no new code)

Block 6  Content pass (probe → author K rows)
         (a) run needs-probe on _test_item_bank.ts against why_tempted_md
         (b) edit coach-item-bank-live.promoted.json to add misconception
             text on K rows (K may be 0 — FR-6 governs)
         (c) update emit_test_item_bank.py to emit the key
         (d) regenerate _test_item_bank.ts
         (e) verify _test_item_bank.test.ts::emits_misconception_key_even_when_null
             stays green

Block 7  FLAG-5 wire (soft-gated)
         if readActiveQuiz is exported by quiz_session_store on `main`:
           (a) [red] coach/page.test.tsx FR-4 → fail
           (b) [green] wire onWrapUp per FR-18
           (c) unwrap test.fail() in validate_epic_ab.spec.ts FLAG-5
         else:
           (a) add decisions.md line noting deferral
           (b) leave test.fail() intact
           (c) do NOT import readActiveQuiz

Block 8  Arch test + decisions ledger + PR
         (a) [red] add test_c2_soft_gate.test.ts (FR-5) → fail
             — asserts the correct import state given the Block-7 branch
         (b) [green] arch test passes given Block-7 outcome
         (c) append five decisions.md lines (spec §13)
         (d) make check + pnpm test + pnpm run test:arch + learn-e2e green
         (e) push branch; open PR
```

**Why Block 6 is not gated on 5:** the content pass changes JSON + a Python
emitter + a generated file. Neither blocks the code path (FR-6). The order
puts it after the code path lands so the probe operates on green code.

**Why Block 8 arch-test is LAST:** the arch test asserts an outcome from
Block 7. Landing it earlier would fail in the wrong direction.

---

## 4. Constitution touchpoints (crosswalk)

| Root `AGENTS.md` invariant | This sprint | Verdict |
|-----------------------------|-------------|---------|
| #1 (deps flow downward) | No layer inverted | ✅ |
| #2 (trust-kernel pure) | No trust type touched | ✅ untouched |
| #3 (components framework-agnostic) | No `langgraph`/`langchain` in `components/` | ✅ untouched |
| #4 (services framework-agnostic) | No backend service touched | ✅ untouched |
| #5 (no peer imports between components) | No new peer imports | ✅ upheld |
| #6 (orchestration nodes are thin) | No orch change | ✅ untouched |
| #7 (services do not import components) | No service change | ✅ untouched |
| #8 (meta does not import orchestration) | No meta change | ✅ untouched |

| Frontend F-R# | This sprint | Verdict |
|---------------|-------------|---------|
| F-R1 (no domain logic in components) | Logic in hook + translator | ✅ upheld |
| F-R2 (SDK imports in adapters only) | No SDK import | ✅ upheld |
| F-R3 (one interface per port module) | No port change | ✅ N/A |
| F-R4 (Route Handlers = composition adapters) | No Route Handler | ✅ N/A |
| F-R5 (prompts in `prompts/`) | No prompt string in TS | ✅ upheld |
| F-R6 (`trust-view/` read-only) | Not touched | ✅ upheld |
| F-R7 (`trace_id` propagation) | No new event | ✅ N/A |
| F-R8 (no SDK type escapes adapter) | No SDK type | ✅ upheld |
| F-R9 (BFF holds no cloud creds) | No env read added | ✅ upheld |

| Style guide (§12 W/P/A/T/X/C/B/U) | This sprint | Verdict |
|-----------------------------------|-------------|---------|
| W1 (pure shapes) | Additive nullable field | ✅ upheld |
| W3 (discriminated unions) | Not applicable — object extension | ✅ N/A |
| W7 (`Schema` const + `Type` co-export) | Preserved | ✅ upheld |
| T1 (translator pure) | New params scalar; no Date.now/React/I/O | ✅ upheld |
| T2 (`trace_id` forwarded) | N/A — no event | ✅ N/A |
| C1 / C4 (env reads composition-only) | No env added | ✅ upheld |
| B6 (Route Handler = composition adapter) | No route handler | ✅ N/A |
| U4 (`aria-live` for streaming) | Not applicable — no stream | ✅ N/A |
| U6 (`cn()` for class merging) | Enforced in the view | ✅ upheld |
| U8 (semantic Tailwind tokens) | Reuse existing accent tokens | ✅ upheld |

**Anti-patterns actively guarded:**
- **FE-AP-6** — no envelope mutation. N/A (no envelope).
- **AP-6 (honest absent)** — the whole misconception branch is a
  honest-absent design. FR-1 / FR-2 / FR-6 uphold.
- **FR-B5 (no dead controls)** — the disabled Lesson button (FR-3) is a
  live guard against becoming Epic A's dead `Reveal` button; asserted in
  the C2 arch/L1 tests.

---

## 5. Grounding pass (Stage 4)

Every file this plan references was probed on 2026-07-10. Grep summary:

| File | Confirmed | Note |
|------|-----------|------|
| `frontend/lib/wire/engine_entities.ts` | ✅ | `Question` at lines 61-79; no `misconception` key today (FR-9 precondition met) |
| `frontend/lib/adapters/engine/db/schema.pg.ts` | ✅ | `testItem` at line 137; no `misconception` column (FR-10 precondition met) |
| `frontend/lib/translators/session_summary_vm.ts` | ✅ | Pre-wired to accept misconception (comment says "passed by the hook") |
| `frontend/components/summary/use_summary.ts` | ✅ | Existing 3-leg `Promise.all` (FR-12 extends to 5) |
| `frontend/components/summary/SummaryView.tsx` | ✅ | `summary-skill-link` present at line 69-75 (FR-17 refuted-premise verified) |
| `frontend/lib/ports/engine/attempt_repo.ts` | ✅ | Only `misses(subject, learnerId)` + `servedQuestionIds(sessionId)` exist — session-scoped miss order derived by intersection (§spec FR-12); no new port method needed |
| `frontend/lib/ports/engine/question_repo.ts` | ✅ | Only `get(id)` exists — bounded sequential loop (≤ session length); no new port method needed (G1 abstraction gate not tripped) |
| `frontend/app/(coach)/learn/coach/page.tsx` | ✅ | `onWrapUp` at lines 101-104 with "B2 would append session id" comment (FR-18 precondition met) |
| `frontend/components/shell/nav_model.ts` | ✅ | `screen("skill").comingSoon === true` at line 75 (FR-3 precondition met) |
| `scripts/emit_test_item_bank.py` | ✅ | Emitter authoritative for `_test_item_bank.ts` (FR-6 dependency) |
| `docs/plan/coach-item-bank-live.promoted.json` | ✅ | Content-pass target (Block 6) |
| `epic-ab-continuity-fixes.spec.md` | ❌ **absent** | Board says "in flight" but no file on disk → FR-5/FR-18 soft-gate is load-bearing |
| `quiz_session_store` `readActiveQuiz` export | ❌ **absent** | Confirmed no export today → Block 7 defaults to the "skip" branch (see §3) |
| `frontend/e2e/learn/validate_epic_ab.spec.ts` | ❌ **absent** | The FLAG-5 e2e itself is authored by continuity-fixes — not by C2. FR-18 e2e-guard-flip becomes a no-op if this file is absent at merge time |

**Baseline required before Block 0:**
- `make check` — green
- `pnpm test` (frontend Vitest) — green
- `pnpm run test:arch` (frontend ts-morph) — green
- `.venv/bin/python -m pytest tests/architecture/ -q` — green
- `pnpm exec playwright test --project=learn-e2e` — green (or a matching
  known-flake baseline recorded)

If any is red, fix (or record as pre-existing) before landing FR tests.

---

## 6. No ADR beyond the one from Gates

- G1 fires — new derivation path + new corpus contract. **One ADR** per
  §11 Gates (`00XX-question-misconception-field.md`).
- G4 does NOT fire (no crypto/signing).
- G7 does NOT fire (no architecture invariant deviation).
- G8 does NOT fire (no mass-rewrite of existing tests — everything is
  additive; the T4 tables ADD cases and don't weaken).

No further ADR trigger.

---

## 7. Rollout / rollback

- **Rollout.** PR bundles everything except the Block 7 wire (if the
  substrate is absent). Ship as one commit series: `wire+schema`,
  `translator`, `hook`, `view`, `e2e`, `content probe`, `arch-test`,
  `decisions.md`. Each block's commit stands alone.
- **Rollback.** Revert-safe — all changes are additive. The Drizzle
  migration is an additive nullable column; a rollback simply stops
  writing new values; existing rows keep `null`. Wire additions are
  optional-nullable; downstream code that never read `misconception`
  before is unaffected.
- **Interaction with Epic E (skill route lands).** The moment
  `screen("skill").comingSoon` flips to `false`, the FR-3 disabled path
  becomes dead code (the ternary short-circuits to the Link branch). No
  code change needed on the C2 side.

---

## 8. Human gates from here

1. **Gate on this plan.** Advance to Stage 3 tasks (already authored) or
   revise.
2. **Gate on tasks.** Advance to Stage 6 (`sdd-implement`) or revise.
3. **Implement Block-by-Block.** Human gates each block's PR at review
   time via `code-review`.
4. **Merge.** After code-review green + `make check` green + `test:arch`
   green + `learn-e2e` green. Epic C completes on this merge (per the
   sprint board's Epic-C exit criteria).
