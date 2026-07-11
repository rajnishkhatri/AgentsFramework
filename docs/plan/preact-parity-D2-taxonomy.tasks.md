---
title: 'D2 — Taxonomy + bucket dots · Tasks'
type: tasks
sprint: D2
epic: D
status: Ready — 2026-07-11 (post-plan sign-off)
owner: Rajnish Khatri
derives_from: docs/plan/preact-parity-D2-taxonomy.plan.md
related:
  - docs/plan/preact-parity-D2-taxonomy.spec.md
---

# D2 — Taxonomy + bucket dots · Tasks

Atomic tasks decomposed from the plan. Each task lists: **file**, **change**,
**FR mapping**, **verification**, **parallelisable?**. FR-N maps to the spec.

**Red bar rule (TAP-4):** every "add test" task ends with the test seen fail
first against the pre-D2 tree — paste the red output in the impl trace before
the corresponding "make green" task lands.

## Task list

### Setup

- **T-0. Read source-of-truth.**
  Read [`PreAct/UI-Design/design-spec.md:62-69`](../../PreAct/UI-Design/design-spec.md) once;
  confirm the 6 canonical labels are: `Rhetoric · Usage · Punctuation · Organization · Sentence Structure · Conciseness`.
  Verification: none — orientation only.

### Design (before code)

- **T-DES-D2. Dot-glyph design review** (blocks T-9).
  Read [`PreAct/UI-Design/design-spec.md`](../../PreAct/UI-Design/design-spec.md)
  for how the prototype renders the bucket dot (search "bucket dot", "•", size
  tokens near §2.3 Spacing). Confirm and record in `decisions.md` OR in the
  D2 impl trace:
  - **Size**: 8×8px (`h-2 w-2`, current plan §2) — matches the design-spec's
    "Spacing base 4px; common gaps 8/10/12/14/18/22px" ([§2.3](../../PreAct/UI-Design/design-spec.md:79-84)).
    If the prototype uses 10px, bump to `h-2.5 w-2.5`. Cite what the prototype
    actually shows.
  - **Placement**: leading (left of `<h3>`), inside a new flex-row wrapper —
    per plan §2. Confirm against `English Coach - Prototype.dc.html` bucket
    header. If prototype puts the dot after the label, swap the order (still
    inside the flex wrapper).
  - **Shape**: `rounded-full` (solid disc). If the prototype uses a hollow
    ring or diamond, change the class and note it.
  - **Colour opacity**: `bg-[var(--accent)]` (full-strength). If the prototype
    uses a muted tint, use the same `color-mix(in oklab, var(--accent) 60%, ...)`
    pattern already in play at [`BucketCard.tsx:36`](../../frontend/components/dashboard/BucketCard.tsx:36).
  **FR:** informs FR-5.
  **Verification:** a single `decisions.md` line (OR a note in the D2 impl
  trace) captures the four choices with source citation. NO screenshot
  required (that's the validation task); this is design intent locked before
  code.

### Red bar (failing tests first)

- **T-1 [parallel with T-2, T-3, T-4].** New arch test:
  `frontend/tests/architecture/test_bucket_labels_no_old_strings.ts`.
  ts-morph walk over `frontend/**/*.{ts,tsx}` excluding `PreAct/`, `.next/`,
  `node_modules/`. FAIL if any of `"Grammar & Usage"`, `"Rhetorical Skills"`, or
  a `name: "Style"` literal (in a Skill-map value context) is present.
  **FR:** FR-1.
  **Verification:** `pnpm exec vitest run frontend/tests/architecture/test_bucket_labels_no_old_strings.ts`
  → SEEN RED on pre-D2 tree (`_dev_seed.ts` still has all three).

- **T-2 [parallel with T-1, T-3, T-4].** New arch test:
  `frontend/tests/architecture/test_bucket_tokens_unchanged.ts`.
  Walk `_dev_seed.ts`, assert every row's `accent_var` matches `/^--color-bucket-/`.
  **FR:** FR-7.
  **Verification:** SEEN GREEN on pre-D2 tree AND after D2 (regression guard,
  not seen-red — an FR-7 test is a **NO-CHANGE** invariant, not a new-behavior
  gate). Justification recorded in G8 line.

- **T-3 [parallel with T-1, T-2, T-4].** New/extended L1:
  `frontend/lib/adapters/engine/_dev_seed.test.ts`.
  Two assertions: (a) `DEV_SKILLS.map(s => [s.id, s.name])` equals the exact
  6-tuple with new labels; (b) full-row snapshot per row (`key`, `accent_var`,
  `description`, `share_of_test_pct`, `order` — must equal today's values,
  guarding FR-6).
  **FR:** FR-3, FR-6.
  **Verification:** SEEN RED on pre-D2 tree (asserts new labels; code has old).

- **T-4 [parallel with T-1, T-2, T-3].** New L1:
  `frontend/e2e/fixtures/preact_learn_corpus.test.ts`.
  Assert the corpus fixture and `_dev_seed.ts` `DEV_SKILLS` agree row-by-row
  (id, name, key, accent_var, description, share_of_test_pct, order).
  **FR:** FR-4.
  **Verification:** SEEN RED on pre-D2 tree (both files have old labels but
  the test asserts new).

- **T-5 [parallel with T-1..T-4].** L1 tests in
  `frontend/components/dashboard/BucketCard.test.tsx` (extend or create):
  - `renders_no_dot_when_accent_var_missing` — VM with `accentVar: null`;
    assert `queryByTestId(/^bucket-dot-/) === null`. **FR:** FR-2.
  - `renders_dot_with_accent_variable` — VM with `accentVar: "--color-bucket-punctuation"`;
    assert `<span data-testid="bucket-dot-<id>">` exists inside the `<header>`,
    has `aria-hidden="true"`, className includes `bg-[var(--accent)]`. **FR:** FR-5.
  **Verification:** BOTH SEEN RED on pre-D2 tree (no dot rendered at all).

### Green bar (content + view)

- **T-6 [blocks T-9]. Content rename in seed.**
  Edit [`_dev_seed.ts:65,85,105`](../../frontend/lib/adapters/engine/_dev_seed.ts):
  `Grammar & Usage → Usage`, `Rhetorical Skills → Rhetoric`, `Style → Conciseness`.
  Touch nothing else on those rows.
  **FR:** FR-3, FR-6.
  **Verification:** `pnpm exec vitest run lib/adapters/engine/` — T-3 turns green.

- **T-7 [blocks T-9]. Content rename in corpus.**
  Edit [`e2e/fixtures/preact_learn_corpus.ts:47,49,51`](../../frontend/e2e/fixtures/preact_learn_corpus.ts):
  same three renames verbatim.
  **FR:** FR-4.
  **Verification:** T-4 turns green.

- **T-8 [blocks T-9]. Content rename in e2e maps + test fixtures.**
  Edit [`e2e/learn/quiz-no-repeat-60.spec.ts:35,37,39`](../../frontend/e2e/learn/quiz-no-repeat-60.spec.ts)
  (id→label map) and [`components/dashboard/use_dashboard.test.ts:87`](../../frontend/components/dashboard/use_dashboard.test.ts)
  (`name: "Style" → "Conciseness"`).
  **FR:** FR-1 (removes remaining old-label call sites).
  **Verification:** `pnpm exec vitest run components/dashboard/use_dashboard.test.ts` — green.

- **T-9. Insert dot glyph in `BucketCard.tsx`.**
  Wrap `<h3>` at [`BucketCard.tsx:41`](../../frontend/components/dashboard/BucketCard.tsx:41)
  and the leading dot `<span>` in a `<div className="flex items-center gap-2">`
  so they sit together on the left of the space-between header (the "Due" pill
  stays on the right). Gate the `<span>` on `vm.accentVar` per plan §2 fallback.
  ClassName: `"h-2 w-2 rounded-full bg-[var(--accent)]"`. Attributes:
  `data-testid="bucket-dot-<skillId>"`, `aria-hidden="true"`.
  **FR:** FR-2, FR-5.
  **Verification:** T-5 both cases turn green. Snapshot check that the `<dl>`
  at :72 is unchanged (a11y `definition-list` rule guard).

### Full-bundle gate

- **T-10 [blocks T-11, T-12]. Arch-test full run.**
  `pnpm exec vitest run frontend/tests/architecture/` — all green including
  T-1 (labels absent) + T-2 (tokens unchanged).
  **FR:** FR-1, FR-7.

- **T-11 [parallel with T-12]. New Playwright:**
  `frontend/e2e/learn/dashboard-bucket-taxonomy.spec.ts`.
  Walks `/learn` (dashboard route), asserts (a) exactly 6 bucket cards, (b)
  each header text equals one of the 6 new canonical labels, (c) each header
  contains a `[data-testid^="bucket-dot-"]`, (d) each dot's computed
  `background-color` is non-empty and non-transparent (evidence the `--accent`
  var resolved).
  **FR:** FR-5.
  **Verification:** `pnpm exec playwright test e2e/learn/dashboard-bucket-taxonomy.spec.ts --project chromium`
  → 1 test passes; SEEN RED on pre-D2 (no dot).

- **T-12 [parallel with T-11]. Continuity re-runs.**
  Re-run `validate_d0_baseline.spec.ts` + `quiz-no-repeat-60.spec.ts` +
  `use_dashboard.test.ts` — must still be green (label change did not
  regress prior sprints). Paste actual output.
  **FR:** FR-1 (regression guard).

### Validation (post-implementation UI walk)

Mirrors D1's paired `validate_d1_quiz_frame_ui.md` + `quiz-frame.spec.ts` pattern
([`frontend/scripts/validate_d1_quiz_frame_ui.md`](../../frontend/scripts/validate_d1_quiz_frame_ui.md), [`frontend/e2e/learn/quiz-frame.spec.ts`](../../frontend/e2e/learn/quiz-frame.spec.ts)).

- **T-VAL-D2a [blocks T-VAL-D2b, T-VAL-D2c].** Author manual runbook:
  `frontend/scripts/validate_d2_taxonomy_ui.md`.
  Mirror the shape of `validate_d1_quiz_frame_ui.md`:
  - **Header table**: Spec / Plan / Tasks / Playwright FRs / L4 suite / Board
    links (all D2 artefacts).
  - **What you should expect to SEE (acceptance bar)**: table of the 6 canonical
    labels + `bucket-dot` glyph expectations.
  - **Task → FR → manual step map**: mirror the D1 map.
  - **Part 0 — boot**: latest middleware + D2 branch + `pnpm dev`. Explicit
    branch checkout + hard-refresh warning (same "do not validate on stale
    UI" callout D1 has at line 19).
  - **Part 1 — Dashboard cold open**: 6 bucket cards visible; each header
    reads one of the 6 new canonical labels (Rhetoric · Usage · Punctuation
    · Organization · Sentence Structure · Conciseness); each has a
    `[data-testid^="bucket-dot-"]` glyph with a **resolved** `backgroundColor`
    (DevTools `getComputedStyle` snippet, same as D1's line 172-177). Includes
    the **fallback** check (fixture with null `accent_var` → no dot; done via
    a temporary DevTools eval OR the L1 test covers it — spec §7 accepts L1
    alone here).
  - **Part 2 — Regression walk**: navigate to `/learn/quiz` and confirm the
    Q-7 skill chip inside D1's frame chrome now shows the **new** canonical
    label when the current item's skill is `s-gram`/`s-rhet`/`s-style` (Usage
    /Rhetoric/Conciseness). If chip still says old label — D1's translator
    or seed didn't reload — hard refresh.
  - **Part 3 — Docs spot-check**: `decisions.md` newest line records the 6
    canonical labels; sprint-board D2 flipped to Implemented; parity report
    §D-3b marked Resolved and §X-4 marked Absorbed.
  - **Part 4 — Console hygiene**: no red errors during the walk.
  - **§A automated proof**: the exact `pnpm exec vitest run` +
    `pnpm exec playwright test` commands for D2's L1 + L4 (from T-3, T-4,
    T-5, T-11).
  - **Pass/fail summary table**: mirror D1's line 330-346.
  Every checkbox has a stable id (1.1, 1.2, …) so the impl trace can cite
  which ones passed.
  **FR:** covers FR-1, FR-3, FR-4, FR-5, FR-6 as a manual-eye sanity net on
  top of the automated tests.
  **Verification:** file exists; every FR maps to at least one manual step
  (mirror D1's task-to-manual matrix at line 71-80).

- **T-VAL-D2b [parallel with T-VAL-D2c]. Playwright validation suite.**
  Author `frontend/e2e/learn/validate_d2_taxonomy.spec.ts` (naming mirrors
  the D0 pattern `validate_d0_baseline.spec.ts`).
  - Two `test.describe` blocks: `D-3b: bucket labels` and `D-3b: bucket
    dots`.
  - Under `bucket labels`: navigate `/learn`, assert `page.getByRole('heading', { name: <label>, exact: true })`
    resolves for **all six** canonical labels; assert **none** of the three
    old strings render anywhere on the page.
  - Under `bucket dots`: for each of the 6 skill ids, assert
    `[data-testid="bucket-dot-<id>"]` exists inside the same card, has
    `aria-hidden="true"`, and its computed `background-color` is
    non-transparent (Playwright `evaluate` + `getComputedStyle`, same
    DevTools snippet from the runbook).
  - Uses `learn-e2e` project (mirror D1) + `E2E_BYPASS_AUTH=1` (same env as
    D1). Chromium only in `make check`; other browsers in nightly.
  **FR:** FR-1, FR-3, FR-5 — automated mirror of the manual walk.
  **Verification:** SEEN RED on pre-D2 tree; SEEN GREEN post-D2. Paste the
  actual output.

- **T-VAL-D2c [parallel with T-VAL-D2b]. Human runbook walk.**
  Run the T-VAL-D2a runbook in a browser end-to-end. Every checkbox ticked
  OR the failure is captured with step id + URL + screenshot (per D1
  convention line 348-350).
  **FR:** all D2 FRs as a final sanity net.
  **Verification:** all boxes ticked; a short summary line pasted into the
  D2 impl trace (`docs/plan/preact-parity-D2-taxonomy.impl.md`).

### Docs

- **T-13 [parallel with T-14, T-15]. `decisions.md` line.**
  Prepend newest-first to [`docs/adr/decisions.md`](../adr/decisions.md):
  > `- D2 taxonomy (2026-07-DD): 6 canonical bucket labels are Rhetoric · Usage · Punctuation · Organization · Sentence Structure · Conciseness. Source: PreAct/UI-Design/design-spec.md:62-69. Renamed Grammar & Usage → Usage, Rhetorical Skills → Rhetoric, Style → Conciseness in _dev_seed.ts + fixtures.`

- **T-14 [parallel with T-13, T-15]. Flip sprint-board status.**
  [`preact-parity-sprint-board-D.md`](preact-parity-sprint-board-D.md) — D2 status
  from Draft → Implemented; append an `## Implementation evidence (Stage 6 —
  YYYY-MM-DD)` section mirroring D1's format (shape call, L1, L4, PR log).

- **T-15 [parallel with T-13, T-14]. Update parity report.**
  [`preact-ui-prototype-parity-VISUAL-gap-report.md`](preact-ui-prototype-parity-VISUAL-gap-report.md) —
  §D-3b: mark Resolved with reference to D2 spec + `decisions.md` line. §X-4:
  mark **Absorbed into D2** with the same reference.

### Final gate

- **T-16 [blocks merge].** `make check` + `pytest tests/architecture/ -q` +
  `pnpm exec vitest run` + `pnpm exec playwright test e2e/learn/dashboard-bucket-taxonomy.spec.ts --project chromium`.
  Paste actual output (all four commands) into the impl trace. No summaries.

## Parallel groupings

```
T-0 → T-DES-D2                                              (design intent locked)
     → { T-1 ‖ T-2 ‖ T-3 ‖ T-4 ‖ T-5 }                      (red bar; parallel)
     → { T-6 ‖ T-7 ‖ T-8 } → T-9                            (green bar)
     → T-10 → { T-11 ‖ T-12 }                               (arch + e2e)
     → T-VAL-D2a → { T-VAL-D2b ‖ T-VAL-D2c }                (validation runbook + suite + walk)
     → { T-13 ‖ T-14 ‖ T-15 } → T-16                        (docs then final gate)
```

## FR-to-task coverage matrix

| FR | Task(s) | Layer |
|----|---------|-------|
| FR-1 | T-1, T-8, T-12, T-VAL-D2b | L1 arch + L1 fixture + L4 continuity + L4 validation |
| FR-2 | T-5 (no-dot case), T-9 (gate) | L1 |
| FR-3 | T-3, T-6, T-VAL-D2b | L1 seed snapshot + L4 validation |
| FR-4 | T-4, T-7 | L1 fixture parity |
| FR-5 | T-5 (dot case), T-9, T-11, T-VAL-D2b, T-VAL-D2c | L1 + L4 + manual |
| FR-6 | T-3 (full-row snapshot), T-6 | L1 |
| FR-7 | T-2, T-10 | L1 arch |
| design | T-DES-D2 | intent locked pre-code |
| runbook | T-VAL-D2a, T-VAL-D2c | manual walk |

Every FR maps to at least one seen-fail-first test (except FR-7 which is a
regression guard — justified in T-2's note and Plan §5 G8).
