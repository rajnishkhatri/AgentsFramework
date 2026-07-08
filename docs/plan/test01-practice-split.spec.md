# Spec — D2: Test-01 corpus split (practice promotion + test exclusivity)

> EARS criteria; failure paths first. No ⚠️ Ask-first trigger (policy + data
> + one filter seam + one guard test); the split policy itself is recorded in
> `docs/adr/decisions.md` at implementation.

**Status:** Draft — 2026-07-07
**Owner:** Rajnish Khatri
**Related:** `docs/plan/act-english-full-bank.brainstorm.md` (D2 direction;
gate decision "split the 48"), `docs/plan/act-english-bank-phase-b.spec.md`
(the promotion train these rows ride — **amends its FR-8 row count**),
ADR-0015 clause 6 (re-stamping), `frontend/scripts/convert_test01_english.ts`
(generated corpus, do-not-edit).

**Clarified at the human gate (2026-07-07):** curated manifest (balanced by
skill×difficulty); accept the ~24-question timed test (backfill-to-48 is a
later option, not D2 scope; overlap/contamination rejected).

---

## 1. Goal

End the practice/test contamination risk before it exists: promote a curated
~half of the 48 rich Test-01 rows into the practice bank through the same
cascade as every other item, keep the rest exclusively in the timed test, and
add the guard that makes the exclusivity permanent.

## 2. Context

- `_test01_english_corpus.ts`: 48 `Question`-shaped rows (`stem`, full
  teaching payload — brainstorm P5 census), generated from an untracked
  local source (do-not-edit), consumed ONLY by the timed-test page and its
  e2e spec. Skill spread: gram 13, punc 13, style 8, sent 6, rhet 5, org 3.
- Practice bank rows are `TestItem`-shaped (`stem_md`); separate types/tables
  mean no leakage code-path today — **by construction, not by guard** (explore
  sweep 2026-07-07). D2 adds the guard.
- The timed test serves the whole corpus (`TEST01_ENGLISH_QUESTIONS.length`,
  35:00 in e2e literals) → the split shortens it to ~24 questions
  (gate-accepted).
- **Non-goals:** authoring new test-only items (backfill = later option),
  tagging test-only rows with `standard_id`, changing the corpus converter.

## 3. Functional requirements (EARS)

Failure paths first.

- **FR-1 (exclusivity guard).** IF any normalized stem appears in BOTH the
  practice bank (`_test_item_bank.ts`) AND the test-served corpus subset THEN
  a deterministic frontend test SHALL fail. This guard is the point of D2 —
  it outlives the split.
- **FR-2 (partition property).** IF the manifest's `promoted` ∪ `test_only`
  ≠ exactly the 48 corpus row ids, or the sets intersect, THEN the manifest
  schema test SHALL fail (every row exactly one fate).
- **FR-3 (no self-review carryover).** IF a promoted row reaches the practice
  bank without passing the FR-23 cascade THEN provenance tests SHALL fail:
  promoted rows are demoted to `reviewed=false` at fold time and re-earn
  review like every authored row; `test01-import` never appears on a served
  practice row (ADR-0015 clause 6).
- **FR-4 (curated manifest).** THE split SHALL be a committed
  `docs/plan/test01-split-manifest.json`: `promoted` (~24 ids) balanced
  ~half per skill (±1 tolerance, asserted by test), `test_only` (the rest).
  Changing a fate = a reviewable manifest diff.
- **FR-5 (fold into the canonical seed).** WHEN D2 lands THE promoted rows
  SHALL be folded into the canonical authored seed with `stem`→`stem_md`
  rename and `standard_id` tags — **amending Phase B FR-8: 192 → ~216 rows**
  — and SHALL ride the same promotion run (T7), hint train (T8), and emit
  (T9) as authored items.
- **FR-6 (test-mode filter).** THE timed-test page SHALL serve only
  `test_only` rows: a pure filter module applies the manifest at the corpus
  consumption boundary (`learn/test/page.tsx` import site); the generated
  corpus file itself is untouched (do-not-edit respected). Minutes constant
  scales to the new count; e2e literals updated.
- **FR-7 (test-mode viability).** WHEN the filter applies THE timed test
  SHALL still constitute a complete session: count > 0 asserted at module
  load (fail fast at build/test, not blank UI at runtime).

## 4. Data model / contracts

- `docs/plan/test01-split-manifest.json` — `{ "promoted": [ids],
  "test_only": [ids] }`, the audit artifact.
- New filter module (frontend, pure): corpus × manifest → served subset.
- Canonical seed rows gain ~24 entries (Question→TestItem field mapping:
  `stem`→`stem_md`; payload fields carry over 1:1 per the P5 census).
- No wire-schema change; no converter change; no new deps.

## 5. Invariants & security boundaries

- Cascade remains the sole reviewer (ADR-0015) — the split never shortcuts
  it. Frontend rules: T-family purity for the filter, existing provenance
  confinement unchanged (promoted rows land via the standard emit path).
- All new tests deterministic; no live LLM beyond the shared Phase B runs.

## 6. Edge cases

- A promoted row FAILS re-verification (solver disagrees): it stays
  `reviewed=false` — the manifest keeps it in `promoted` (intent) but it
  serves NOWHERE until fixed; the exclusivity guard is unaffected (guard
  checks served surfaces, not intent). Run report lists it (Phase B FR-3).
- Stem collision between a Test-01 row and an authored Phase B item: the
  cascade's duplicate gate quarantines the later arrival — the run report
  attributes it; curation may swap the manifest fate instead.
- Manifest id drift (corpus regenerated upstream with changed ids): FR-2's
  partition test fails loudly — the manifest must be re-curated, never
  silently re-mapped.
- e2e scripted-answer fixtures reference specific questions: updating the
  served subset requires the e2e script-map refresh in the same change.

## 7. Non-functional requirements

Deterministic throughout; LLM cost = ~24 extra solver calls + ~24 hint runs
riding Phase B's train (noise vs its budget). Reversible: manifest +
filter revert cleanly; promoted rows removable by re-emit without them.

## 8. Test plan

| FR | Test | Layer | In CI? |
|----|------|-------|--------|
| FR-1 | NEW vitest exclusivity guard (normalized-stem intersection == ∅) | L1 | yes |
| FR-2/4 | NEW manifest schema + balance test (partition, ±1 per skill) | L1 | yes |
| FR-3 | existing provenance confinement + re-stamp tests over the grown bank | L1 | yes |
| FR-5 | Phase B seed pre-flight (count amended to ~216) + matrix unchanged for the authored 150 | L1 | yes |
| FR-6/7 | filter module unit tests + count>0 load assert + updated test-mode e2e | L1 + e2e | yes / tiered |

## 9. Definition of Done

- [ ] Manifest committed, balance test green, exclusivity guard green and
      seen to fail first against a seeded overlap.
- [ ] Phase B FR-8 amendment noted in its spec (192 → ~216) with cross-ref.
- [ ] Timed-test e2e green at the new count/minutes.
- [ ] `decisions.md` entry: the split policy + rejected alternatives
      (hash-based selection; backfill-first; accepted overlap).
