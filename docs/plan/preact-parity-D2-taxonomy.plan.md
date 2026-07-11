---
title: 'D2 — Taxonomy + bucket dots · Plan'
type: plan
sprint: D2
epic: D
status: Draft — 2026-07-11
owner: Rajnish Khatri
derives_from: docs/plan/preact-parity-D2-taxonomy.spec.md
governs:
  - docs/plan/preact-parity-D2-taxonomy.tasks.md
related:
  - docs/plan/preact-parity-sprint-board-D.md
  - PreAct/UI-Design/design-spec.md
---

# D2 — Taxonomy + bucket dots · Plan

Derives from `preact-parity-D2-taxonomy.spec.md` (7 FRs). This plan translates the
spec into concrete file-level touchpoints, execution order, and gates. It does not
introduce anything the spec did not authorise.

## 1. Architecture posture

- **Layer:** Content (seed row `name` values) + presentation (one `<span>` inside
  `BucketCard.tsx`'s existing `<header>`).
- **Frontend Ring patterns touched:**
  - **U6** (`cn()` merging) — no change; new `<span>` uses `cn()` for its
    className.
  - **U8** (semantic tokens via `@theme`) — no change; reuses the existing
    card-scoped `--accent` CSS variable set at
    [`BucketCard.tsx:33`](../../frontend/components/dashboard/BucketCard.tsx:33).
  - **F-R1** (no domain logic in components) — untouched; the dot is style-only.
- **What is NOT introduced:** no new VM, no new translator, no new CSS token, no
  new wire schema, no new abstraction (G1 does not fire), no new `.tsx` file.

## 2. Shape call

- **Where the dot renders:** as a sibling of `<h3>` inside the existing
  `<header className="flex items-center justify-between gap-2">` at
  [`BucketCard.tsx:40`](../../frontend/components/dashboard/BucketCard.tsx:40) —
  wrapped with the `<h3>` inside a leading `<div className="flex items-center gap-2">`
  so the dot sits **before** the label without disturbing the existing
  space-between `<header>` (which keeps the "Due" pill on the right). Layout diff
  is one extra flex container.
- **Colour source:** `background: var(--accent)` (the same variable the mastery
  bar reads at [`BucketCard.tsx:61`](../../frontend/components/dashboard/BucketCard.tsx:61)) —
  no direct `vm.accentVar` read in the view (all `accent_var` propagation stays
  centralised at the `style` prop on the `<Link>` at :33).
- **Accessibility:** `aria-hidden="true"` on the dot (decorative — see spec §7);
  the `<h3>` continues to name the bucket, and the mastery `progressbar` at :54
  keeps its `aria-label`.
- **Fallback (FR-2):** if `vm.accentVar` is null, the `<Link>` at :33 already
  passes `` `var(${vm.accentVar})` `` to the style — with `null`, that becomes
  `var(null)`, which resolves to the fallback (transparent). The dot MUST NOT
  render at all in that case, so gate on `vm.accentVar` before emitting the
  `<span>`:
  ```tsx
  {vm.accentVar ? <span data-testid={`bucket-dot-${vm.skillId}`} aria-hidden="true" className="h-2 w-2 rounded-full bg-[var(--accent)]" /> : null}
  ```

## 3. File-level touchpoints

| File | Change | Notes |
|------|--------|-------|
| [`frontend/lib/adapters/engine/_dev_seed.ts:65,85,105`](../../frontend/lib/adapters/engine/_dev_seed.ts) | Rename `name` on 3 rows: `s-gram → Usage`, `s-rhet → Rhetoric`, `s-style → Conciseness`. `key`/`accent_var`/`description`/`share_of_test_pct`/`order` untouched. | Content edit, 3 lines. |
| [`frontend/e2e/fixtures/preact_learn_corpus.ts:47,49,51`](../../frontend/e2e/fixtures/preact_learn_corpus.ts) | Same three renames — corpus mirror. | Fixture edit, 3 lines. |
| [`frontend/e2e/learn/quiz-no-repeat-60.spec.ts:35,37,39`](../../frontend/e2e/learn/quiz-no-repeat-60.spec.ts) | Update the id→label map: `s-gram → Usage`, `s-rhet → Rhetoric`, `s-style → Conciseness`. | E2E fixture map, 3 lines. |
| [`frontend/components/dashboard/use_dashboard.test.ts:87`](../../frontend/components/dashboard/use_dashboard.test.ts) | Update the one `name: "Style"` fixture row → `name: "Conciseness"`. (No `Grammar & Usage` / `Rhetorical Skills` in this file — grep confirmed.) | Test fixture edit, 1 line. |
| [`frontend/components/dashboard/BucketCard.tsx`](../../frontend/components/dashboard/BucketCard.tsx) | Insert dot glyph as leading `<span>` in the header's title cluster. Gate on `vm.accentVar` (FR-2). | View, ~4 lines. |
| [`frontend/components/dashboard/BucketCard.test.tsx`](../../frontend/components/dashboard/BucketCard.test.tsx) *(may need to create)* | Add tests for FR-2 (no-dot fallback) + FR-5 (renders + tinted). Existing test file may exist or need creation. | New tests. |
| [`frontend/lib/adapters/engine/_dev_seed.test.ts`](../../frontend/lib/adapters/engine/_dev_seed.test.ts) *(likely new)* | Snapshot of `DEV_SKILLS` (id/name tuple + full-row shape). Covers FR-3 + FR-6. | New test file OR extends an existing seed test. |
| [`frontend/e2e/fixtures/preact_learn_corpus.test.ts`](../../frontend/e2e/fixtures/preact_learn_corpus.test.ts) *(likely new)* | Assert fixture ↔ seed agreement per row (FR-4). | New test. |
| [`frontend/e2e/learn/dashboard-bucket-taxonomy.spec.ts`](../../frontend/e2e/learn/dashboard-bucket-taxonomy.spec.ts) *(new)* | Playwright walk — 6 cards, new labels, `[data-testid^="bucket-dot-"]` present per card, non-empty computed background. | New E2E, chromium smoke. |
| [`frontend/tests/architecture/test_bucket_labels_no_old_strings.ts`](../../frontend/tests/architecture/test_bucket_labels_no_old_strings.ts) *(new)* | ts-morph walk asserting no `"Grammar & Usage"`, `"Rhetorical Skills"`, or skill-name-position `"Style"` in the runtime bundle (excluding `PreAct/`). Covers FR-1. | New arch test. |
| [`frontend/tests/architecture/test_bucket_tokens_unchanged.ts`](../../frontend/tests/architecture/test_bucket_tokens_unchanged.ts) *(new)* | Assert every seed row's `accent_var` still matches `/^--color-bucket-/`. Covers FR-7. | New arch test. |
| [`docs/adr/decisions.md`](../adr/decisions.md) | Prepend newest-first line recording the 6 canonical labels + citation `PreAct/UI-Design/design-spec.md:62-69`. | Docs, 1 line. |
| [`docs/plan/preact-parity-sprint-board-D.md`](preact-parity-sprint-board-D.md) | Flip D2 status from Draft → Implemented (post-merge). | Docs. |
| [`docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md`](preact-ui-prototype-parity-VISUAL-gap-report.md) | Mark §D-3b resolved; §X-4 marked absorbed-into-D2. | Docs. |

## 4. Execution order (TDD)

1. **Red bar first** — author the two new arch tests + the `_dev_seed.test.ts`
   snapshot + `BucketCard.test.tsx` FR-2/FR-5 cases, watch them fail on the
   pre-D2 tree (asserting the NEW state). Capture the red output for the impl
   trace.
2. **Content rename** — apply the three `name` changes to `_dev_seed.ts` +
   `preact_learn_corpus.ts` + `quiz-no-repeat-60.spec.ts` + `use_dashboard.test.ts`
   in one commit. Re-run L1 — arch tests green, snapshot green, `use_dashboard`
   green.
3. **View change** — insert the dot glyph in `BucketCard.tsx` (gated on
   `vm.accentVar`). Re-run `BucketCard.test.tsx` — green.
4. **E2E green-bar** — run `dashboard-bucket-taxonomy.spec.ts` (chromium
   smoke). Then re-run `validate_d0_baseline.spec.ts` and `quiz-no-repeat-60.spec.ts`
   to ensure the label change did not regress prior sprints.
5. **Docs** — append `decisions.md`; flip sprint-board status; update parity
   report §D-3b / §X-4.
6. **Full gate** — `make check` + `pytest tests/architecture/ -q` + `pnpm exec vitest run` +
   the D2 playwright smoke. Paste actual output into the impl trace.

## 5. Gates + risks

- **G1 (new-abstraction gate)** — DOES NOT FIRE. No new VM, no new component
  family, no new CSS token.
- **G8 (test-mass-rewrite gate)** — the D2 test edits are targeted per-file:
  4 fixture-string updates (each asserting a new exact string), plus additive
  new tests. Not a mass rewrite that weakens assertions.
- **`⚠️ Ask first`** — none of the 5 root triggers fire (no new dep, no
  trust-kernel change, no new graph node, no new horizontal service, no
  invariant deviation).
- **ADR ratchet** — no `docs/adr/*` needed; `decisions.md` is the right weight.
- **Risk: axe `definition-list` rule** — the `<dl>` at [`BucketCard.tsx:72`](../../frontend/components/dashboard/BucketCard.tsx:72)
  is unchanged; the dot goes into the `<header>`, not the `<dl>`. Verified.
- **Risk: FR-1 false positives on `"Style"`** — the arch test scopes the
  check to the exact whole strings AND uses a heuristic (adjacent `name:` or
  Skill-map value) so `styleProp` / `TextStyle` don't false-fire. Documented
  in the arch test's top-of-file comment.

## 6. Independence

D2 has no dependency on D3 or D4 and can merge to `main` alone. It does not
touch `drizzle_session_repo.ts`, `nav_model.ts`, or ADR-0023.
