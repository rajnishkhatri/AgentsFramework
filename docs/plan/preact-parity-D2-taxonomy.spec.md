---
title: 'D2 — Taxonomy + bucket dots (PreAct parity Epic D)'
type: spec
sprint: D2
epic: D
status: Draft — 2026-07-11
owner: Rajnish Khatri
derives_from: docs/plan/preact-parity-sprint-board-D.md
governs:
  - docs/plan/preact-parity-D2-taxonomy.plan.md  # written next
  - docs/plan/preact-parity-D2-taxonomy.tasks.md # written after plan
related:
  - docs/plan/preact-parity-sprint-board-D.md  # sprint ladder
  - PreAct/UI-Design/design-spec.md             # source-of-truth for the 6 labels
  - docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md  # findings D-3b + X-4
---

# D2 — Taxonomy + bucket dots

**Report findings:** `D-3b` (bucket names → ACT-standard + per-bucket color dot) ·
`X-4` (bucket taxonomy mismatch — merged into D2 per Stage-1 audit P15).

## 1. Goal

Rename the 3 out-of-parity skill display labels to the prototype's ACT-standard
names, and surface each bucket's existing `accent_var` as a discrete **dot glyph**
on Dashboard bucket cards. Ships as content + view; no new abstractions, no new
CSS tokens. Closes the last visible taxonomy delta on the Dashboard.

## 2. Context

The parity report (§D-3b, §X-4) flags six ACT-English bucket labels as
inconsistent with the prototype and calls for a color dot in the Dashboard header.
D-3b is a **cross-cut duplicate of X-4** (both point at the same 6-name list under
different framings) — collapsed into one sprint by the Stage-1 audit (P15).

Auditing the source-of-truth ([`PreAct/UI-Design/design-spec.md:62-69`](../../PreAct/UI-Design/design-spec.md) — the 6-row bucket table) against
[`frontend/lib/adapters/engine/_dev_seed.ts:50-111`](../../frontend/lib/adapters/engine/_dev_seed.ts:50) finds **3 of 6 labels
already match** (Punctuation, Organization, Sentence Structure) and **3 diverge**:

| id | Current `name` | Prototype canonical (design-spec.md:62-69) |
|----|----------------|-------------------------------------------|
| `s-gram`  | `Grammar & Usage`   | `Usage`       |
| `s-rhet`  | `Rhetorical Skills` | `Rhetoric`    |
| `s-style` | `Style`             | `Conciseness` |

The color mechanism already exists — every seed row carries an
`accent_var: "--color-bucket-<key>"` token; `BucketCard.tsx:33` reads it as a
local `--accent` CSS variable feeding the progress bar and border tint. What is
missing is the **discrete dot glyph** the prototype uses in the Dashboard bucket
header. All six accent tokens are already registered in `app/globals.css` — no
new tokens.

## Clarify resolutions (2026-07-11, pre-plan)

Recorded here so the plan can proceed without a second gate:

- **Rename scope: display `name` only** (human answer 2026-07-11). The `key`,
  `accent_var`, and `description` fields are untouched. Smallest diff, tightest
  grep audit, aligned with the design-spec (which dictates labels + colors, not
  description sentences).
- **CSS token names untouched.** Design-spec uses shorthand
  `--b-rhetoric`/`--b-concise`; this repo uses the fuller
  `--color-bucket-<key>`. Renaming CSS token identifiers is out-of-scope — the
  parity finding is about **display labels**, not token identifiers.
- **`s-style.accent_var` stays `--color-bucket-conciseness`.** Already correct
  ([`_dev_seed.ts:107`](../../frontend/lib/adapters/engine/_dev_seed.ts:107)).
- **E2E fixture stays in lock-step** ([`e2e/fixtures/preact_learn_corpus.ts:47-51`](../../frontend/e2e/fixtures/preact_learn_corpus.ts:47)). The
  corpus fixture is a hand-authored mirror of `_dev_seed.ts`; **update both** in
  the same PR so specs asserting the new labels pass.

## 3. Functional requirements (EARS)

Failure paths first (TAP-4).

- **FR-1 (unwanted).** IF a Dashboard consumer of bucket labels references any of
  the 3 old strings (`Grammar & Usage`, `Rhetorical Skills`, `Style`) after this
  sprint lands, THEN the sprint MUST fail its grep-audit gate (per §8). All three
  string forms must be absent from `frontend/**/*.{ts,tsx}` under the runtime
  bundle (excluding archived/legacy fixtures under `PreAct/`).
- **FR-2 (unwanted).** IF a bucket row in
  [`_dev_seed.ts`](../../frontend/lib/adapters/engine/_dev_seed.ts) is missing a
  non-null `accent_var` in the shape `--color-bucket-*`, THEN the BucketCard must
  render **without** the dot glyph (defensive; no half-rendered dot with a
  broken CSS variable). Test seen fail first with a fixture row that has
  `accent_var: null`.
- **FR-3.** THE SYSTEM SHALL rename the display `name` of exactly three skill
  rows in [`_dev_seed.ts:50-111`](../../frontend/lib/adapters/engine/_dev_seed.ts:50):
  `s-gram` → `Usage`, `s-rhet` → `Rhetoric`, `s-style` → `Conciseness`.
  The other three (`s-punc`, `s-sent`, `s-org`) are already canonical and
  MUST NOT change.
- **FR-4.** THE SYSTEM SHALL apply the same three renames verbatim to
  [`e2e/fixtures/preact_learn_corpus.ts`](../../frontend/e2e/fixtures/preact_learn_corpus.ts) so E2E fixtures stay in
  lock-step with the seed. Both files land in the same PR.
- **FR-5.** WHEN [`BucketCard.tsx`](../../frontend/components/dashboard/BucketCard.tsx)
  renders a bucket header, THE SYSTEM SHALL render a discrete dot glyph as a
  `<span data-testid="bucket-dot-{skillId}">` sibling of the existing `<h3>`
  label. The dot's fill colour MUST read the existing card-scoped `--accent`
  variable set at [`BucketCard.tsx:33`](../../frontend/components/dashboard/BucketCard.tsx:33)
  (no new CSS tokens).
- **FR-6.** THE SYSTEM SHALL NOT change `Skill.key`, `Skill.accent_var`,
  `Skill.description`, `Skill.share_of_test_pct`, or `Skill.order` for any row —
  only `Skill.name` mutates.
- **FR-7.** THE SYSTEM SHALL leave all six `--color-bucket-*` CSS token
  identifiers unchanged (renaming to the design-spec's shorthand
  `--b-<key>` is explicitly out-of-scope; see Clarify).

## 4. Data model / contracts

No wire changes. `Skill` (`frontend/lib/wire/engine_entities.ts`) is unchanged.
This is a **content** change (three `name` string values in `_dev_seed.ts` and
its e2e fixture mirror) plus a **presentational** view change (a `<span>` inside
the existing `<header>` in `BucketCard.tsx`). No new translator, no VM change,
no trust-kernel touch (no re-signing).

## 5. Invariants & security boundaries

- **AGENTS.md invariant #3 (components framework-agnostic)** — untouched. The
  view change is a `<span>` inside an existing presentational component
  (F-R1: no domain logic; the dot is style-only).
- **AGENTS.md invariant #6 (orchestration = thin wrappers)** — untouched. No
  reducer, no dispatch.
- **Frontend Ring T1 (translator purity)** — untouched. No translator changes.
- **F-R2 (no SDK imports outside `adapters/`)** — untouched.
- **F-R5 (prompts stay in `prompts/`)** — untouched.
- **F-A8 (color is never the sole signal)** — the dot glyph is **decorative**;
  the accessible label continues to be the `<h3>` text and existing
  `aria-label` on the progress bar. No visual-only state added; dot conveys
  nothing that isn't already textually named.

## 6. Edge cases

- **Empty bank / no skills.** Dashboard renders no bucket cards — no dot to
  worry about (FR-5 is per-bucket, no cross-bucket coupling).
- **Row with `accent_var: null`.** Covered by FR-2 (defensive; no half-render).
- **Duplicate labels across skills.** Not possible after this rename (six
  canonical labels are all distinct).
- **RTL / long label overflow.** Design-spec's `Rhetoric` (8 chars) is shorter
  than today's `Rhetorical Skills` (17 chars) — no overflow risk introduced;
  the card header already wraps.
- **Grep-audit false positives.** `Style` is a substring of `TextStyle`,
  `styleProp`, etc. FR-1's audit must scope the check to the **exact whole
  strings**, quoted, not substrings — see §8 test-plan gate.

## 7. Non-functional requirements

- **Latency / cost:** none — no new I/O, no new render work of consequence
  (one `<span>` per card, six cards on the Dashboard).
- **Determinism:** L1 deterministic (pure content string; pure view render).
- **Reversibility:** trivial (revert the three seed lines + the `<span>`).
- **CI-hot-path:** no live-LLM calls introduced.
- **A11y:** dot glyph is `aria-hidden="true"` (decorative — text still names the
  bucket) OR labelled with the bucket colour name is redundant and adds
  screen-reader noise. Default: `aria-hidden="true"`.

## 8. Test plan

Failure-path tests are written **first** (TAP-4), watched fail, then made green.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `frontend/tests/architecture/test_bucket_labels_no_old_strings.ts` — walks `frontend/**/*.{ts,tsx}` (excluding `PreAct/` and generated) and fails on any occurrence of `"Grammar & Usage"`, `"Rhetorical Skills"`, or the standalone token `"Style"` used as a skill name literal (heuristic: preceded by `name:` or in a `Record<..., string>` value). Seen red on pre-D2 tree. | L1 (arch) | yes |
| FR-2 | `components/dashboard/BucketCard.test.tsx::renders_no_dot_when_accent_var_missing` — RTL/jsdom fixture with `accent_var: null`; asserts `queryByTestId(/^bucket-dot-/)` is null. | L1 | yes |
| FR-3 | `lib/adapters/engine/_dev_seed.test.ts` — snapshot of `DEV_SKILLS.map(s => [s.id, s.name])`; asserts the exact 6-tuple `[[s-punc,Punctuation],[s-gram,Usage],[s-sent,Sentence Structure],[s-rhet,Rhetoric],[s-org,Organization],[s-style,Conciseness]]`. | L1 | yes |
| FR-4 | `e2e/fixtures/preact_learn_corpus.test.ts` — same 6-tuple assertion against the corpus fixture; asserts fixture and seed agree row-by-row. | L1 | yes |
| FR-5 | `components/dashboard/BucketCard.test.tsx::renders_dot_with_accent_variable` — asserts `<span data-testid="bucket-dot-{skillId}">` exists inside the `<header>`, is styled with `background: var(--accent)`, and every dot is decorative (`aria-hidden="true"`). | L1 | yes |
| FR-5 | `e2e/learn/dashboard-bucket-taxonomy.spec.ts` — Playwright walks Dashboard, asserts (a) exactly 6 bucket cards, (b) each header shows the **new** canonical label, (c) each header has a `[data-testid^="bucket-dot-"]` with a non-empty computed background colour. | L4 | yes (chromium smoke) |
| FR-6 | Same seed snapshot test as FR-3 — extended to snapshot the **full** `Skill` shape per row (keys, accent_var, description, share_of_test_pct, order); regressions on any of the untouched fields fail. | L1 | yes |
| FR-7 | `frontend/tests/architecture/test_bucket_tokens_unchanged.ts` — asserts every seed row still uses a `--color-bucket-*` accent_var (not `--b-<key>`); a rename would fail. | L1 (arch) | yes |

**Seen-fail-first evidence pasted in the plan `.impl.md`** (not a summary).
`make check` + `pytest tests/architecture/ -q` + `pnpm exec vitest run components/dashboard/ lib/adapters/engine/ e2e/fixtures/` all green.

## 9. Definition of Done

- [ ] All 7 FRs implemented; each has at least one passing test **seen to fail
      first** on the pre-D2 tree (pasted red output in the impl trace).
- [ ] The 6 canonical labels appear verbatim in [`_dev_seed.ts`](../../frontend/lib/adapters/engine/_dev_seed.ts)
      and in [`e2e/fixtures/preact_learn_corpus.ts`](../../frontend/e2e/fixtures/preact_learn_corpus.ts) — matching the
      design-spec table at `PreAct/UI-Design/design-spec.md:62-69`.
- [ ] Grep audit is green: no `"Grammar & Usage"`, `"Rhetorical Skills"`, or
      skill-name-position `"Style"` in `frontend/**/*.{ts,tsx}` outside archived
      fixtures.
- [ ] `<span data-testid="bucket-dot-{skillId}">` renders on every Dashboard
      BucketCard header, tinted by the existing `--accent` variable.
- [ ] `make check` green (lint + format-check + pyright + test + hygiene).
- [ ] Architecture tests green: `pnpm exec vitest run frontend/tests/architecture/`.
- [ ] `decisions.md` line appended recording the 6 canonical labels + source
      citation (`PreAct/UI-Design/design-spec.md:62-69`).
- [ ] Parity report updated (D-3b + X-4 marked resolved; X-4 flagged as
      merged into D2).
- [ ] No ADR (content + view; no new abstraction, no invariant change).
- [ ] Actual command output pasted (not summarized) for the verification claims.

## 10. Gates

- No `⚠️ Ask first` trigger — content + view; no new dependency, no trust-kernel
  change, no new graph node, no new abstraction.
- No ADR ratchet fires (per `tests/architecture/test_adr_ratchet.py` seam list —
  D2 touches neither the ADR trigger paths nor the `⚠️ Ask first` list).
- `decisions.md` line is the right weight (small non-obvious content choice
  with a source citation).
- G1 (new-abstraction) does not fire — no new VM, no new component family.
- G8 (test-mass-rewrite) does not fire — new tests are additive; existing
  tests that pinned the old labels are **updated to assert the new ones** (a
  targeted change, not a weakening rewrite; the tests still assert exact
  strings).
