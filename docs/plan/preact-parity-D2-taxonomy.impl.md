---
title: 'D2 — Taxonomy + bucket dots · Implementation trace'
type: impl
sprint: D2
epic: D
status: In progress — 2026-07-11
owner: Rajnish Khatri
derives_from: docs/plan/preact-parity-D2-taxonomy.tasks.md
---

# D2 — Implementation trace

Paste-only evidence log (red → green). No summaries.

## T-0 — Source-of-truth labels

Confirmed from `PreAct/UI-Design/design-spec.md:62-69`:

| Bucket | Var |
|--------|-----|
| Rhetoric | `--b-rhetoric` |
| Usage | `--b-usage` |
| Punctuation | `--b-punct` |
| Organization | `--b-org` |
| Sentence Structure | `--b-struct` |
| Conciseness | `--b-concise` |

## T-DES-D2 — Dot-glyph design lock

Source: `PreAct/UI-Design/English Coach - Prototype.dc.html:71` (Dashboard mastery card header):

```html
<span style="width:11px;height:11px;border-radius:4px;background:var(--c);flex:none"></span>
```

| Choice | Locked | Rationale |
|--------|--------|-----------|
| Size | `h-[11px] w-[11px]` | Prototype exact (11×11), not plan default 8px |
| Placement | Leading (left of `<h3>`), flex-row wrapper | Prototype: dot then `<strong>` |
| Shape | `rounded` (= 4px) | Prototype `border-radius:4px` (rounded square, not disc) |
| Colour | `bg-[var(--accent)]` full strength | Prototype `background:var(--c)` |

Plan §2 defaulted to `h-2 w-2 rounded-full`; T-DES-D2 overrides to match the prototype.

## Red bar (T-1 … T-5)

```
 FAIL  tests/architecture/test_bucket_labels_no_old_strings.test.ts
 Old bucket labels still present:
 components/dashboard/use_dashboard.test.ts: skill-name-position "Style"
 e2e/fixtures/preact_learn_corpus.ts: contains "Grammar & Usage"
 e2e/fixtures/preact_learn_corpus.ts: contains "Rhetorical Skills"
 e2e/fixtures/preact_learn_corpus.ts: skill-name-position "Style"
 e2e/learn/quiz-no-repeat-60.spec.ts: contains "Grammar & Usage"
 e2e/learn/quiz-no-repeat-60.spec.ts: contains "Rhetorical Skills"
 e2e/learn/quiz-no-repeat-60.spec.ts: skill-name-position "Style"
 lib/adapters/engine/_dev_seed.ts: contains "Grammar & Usage"
 lib/adapters/engine/_dev_seed.ts: contains "Rhetorical Skills"
 lib/adapters/engine/_dev_seed.ts: skill-name-position "Style"
 Tests  1 failed (1)

 FAIL  lib/adapters/engine/_dev_seed.test.ts
 -     "Usage",
 +     "Grammar & Usage",
 -     "Rhetoric",
 +     "Rhetorical Skills",
 -     "Conciseness",
 +     "Style",

 FAIL  e2e/fixtures/preact_learn_corpus.test.ts
 (same id→name delta as seed)

 FAIL  components/dashboard/BucketCard.test.tsx
 renders_dot_with_accent_variable (FR-5)
 AssertionError: expected null not to be null

 PASS  tests/architecture/test_bucket_tokens_unchanged.test.ts (FR-7 NO-CHANGE)
 PASS  BucketCard renders_no_dot_when_accent_var_missing (FR-2 vacuous green — no dots yet)
 Test Files  4 failed | 1 passed
```


## Green bar (T-6 … T-9)

```
pnpm exec vitest run …BucketCard / _dev_seed / corpus / arch / use_dashboard
 Test Files  6 passed (6)
      Tests  22 passed (22)
```

## Arch + E2E (T-10 … T-12)

 (T-10 … T-12)

```
# T-11 + T-VAL-D2b (earlier green run)
  ✓  dashboard-bucket-taxonomy.spec.ts — six cards + labels + dots (1.9s)
  ✓  validate_d2_taxonomy — bucket labels (1.4s)
  ✓  validate_d2_taxonomy — bucket dots (1.5s)
  3 passed (5.9s)

# T-12 continuity
  ✓  validate_d0_baseline.spec.ts — D0→D1 continuity (3.1s)
  1 passed (3.9s)
```

## Validation (T-VAL-D2*)

 (T-VAL-D2*)

- T-VAL-D2a: `frontend/scripts/validate_d2_taxonomy_ui.md` authored.
- T-VAL-D2b: `validate_d2_taxonomy.spec.ts` green (see above).
- T-VAL-D2c: human walk — deferred to operator; automated mirror covers FR-1/3/5.

## Final gate (T-16)

```
make check
→ ruff check / ruff format --check / pyright / cite_lint / hygiene: passed
→ pytest: 5277 passed, 51 skipped, 72 deselected in 159.08s

pnpm exec vitest run (D2 L1 suite)
→ Test Files  7 passed (7)
→ Tests  34 passed (34)

pytest tests/architecture/ -q
→ (see below)

pnpm exec playwright test --project=learn-e2e dashboard-bucket-taxonomy + validate_d2_taxonomy
→ 3 passed (6.2s)
```
