# Transcript — file a memory-extractor calibration-thresholds research note (without_skill)

## Task
File a short, reusable research note on memory-extractor calibration thresholds
(store-decision precision >= 0.90, PII-flip hard zero, κ-vs-gold >= 0.60, frozen
test split, enable-policy certificate) into the right place in the OKF knowledge
tree, keeping the lint clean.

## What I did

1. **Read the OKF convention** (`docs/CONVENTIONS_OKF.md`) and the linter
   (`scripts/okf_lint.py`) to learn the bundle model: a Concept is a markdown file
   with `type:` frontmatter; a Bundle is a directory with reserved `index.md`
   (progressive-disclosure catalog) + `log.md` (chronological, newest-first).
   Declared bundles are listed in `DECLARED_BUNDLES`.

2. **Chose the home.** The note is *about* memory-extractor calibration and is a
   *reusable design reference*, not a one-run record. The repo already has a
   declared bundle `docs/recipes/memory_extractor/` whose existing Concepts
   (`03_enable_policy.md`, `04_calibration_runbook.md`, `02_goldset_spec.md`) are
   exactly these thresholds. So the note belongs there as a new Concept — NOT in
   the linter-excluded `docs/research/` evidence tree (that's for stage/coding
   outputs, not design references), and NOT in the runtime memory subsystem, which
   the convention explicitly puts out of OKF scope.

3. **Verified the numbers against the authoritative source.** All three thresholds
   match `03_enable_policy.md` §2 (the precision-first enable-gate table):
   store-class precision >= 0.90, content-leak / PII flip-rate == 0 (hard), κ
   (judge vs gold) >= 0.60. I disambiguated κ-vs-gold >= 0.60 (the inter-rater
   judge floor) from the unrelated α >= 0.80 gold-set-freeze gate and κ >= 0.80
   taxonomy-freeze gate (`02_goldset_spec.md`), and noted that in the Concept.

4. **Captured a clean lint baseline** before editing: 26 bundles, 127 warnings
   (all pre-existing broken links in unrelated bundles), 0 failures, exit 0.

5. **Created the Concept**
   `docs/recipes/memory_extractor/05_calibration_thresholds.md` — a distilled
   quick-reference card (threshold table + one bullet per threshold + the
   frozen-test-split / certificate gating note) cross-linked to the authoritative
   §2 gate table and the runbook/goldset siblings. Frontmatter follows the bundle
   convention (`type: research-note`, `title`, `description`, `tags`, `timestamp`).

6. **Registered it** in the bundle's `index.md` (new catalog line) and `log.md`
   (new newest-first dated entry).

7. **Re-ran the linter:** still 127 warnings / 0 failures / exit 0. Zero warnings
   reference `memory_extractor`, confirming the new Concept's frontmatter parses
   and all four of its cross-links resolve.

## Where it was filed
- New Concept: `docs/recipes/memory_extractor/05_calibration_thresholds.md`
- Updated: `docs/recipes/memory_extractor/index.md`,
  `docs/recipes/memory_extractor/log.md`

## Lint result
`python scripts/okf_lint.py` → exit code 0 (26 bundles, 127 warnings, 0 failures).
The 127 warnings are all pre-existing broken links in unrelated bundles; the
memory_extractor bundle is warning-free. Full stdout in `lint_result.txt`.
