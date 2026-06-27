# Transcript — Document the OKF linter as a recipe (with skill)

**Task:** Document the newly shipped standalone OKF linter (`scripts/okf_lint.py`) and its
convention doc (`docs/CONVENTIONS_OKF.md`) as a recipe so the team knows how to add and
lint a bundle, then make sure the docs tree still lints clean.

**Skill used:** `agentsframework-okf-curator`.
**Routines used:** **Routine 1 — Document a feature as a recipe**, then **Routine 4 — Keep
it extractable** (the lint gate).

## What I did

1. **Read the skill in full** — `SKILL.md` plus its three references
   (`conventions.md`, `recipe-template.md`, `gotchas.md`) — to learn the house shape, the
   `type` vocabulary, the `--depth-to-root` rule, and the move/frontmatter gotchas.

2. **Grounded in the actual feature** — read `scripts/okf_lint.py` (the `DECLARED_BUNDLES`
   tuple, the FAIL-only-on-missing-index/log contract, the WARN-on-type/links rule, the
   evidence-skip and forgiving link resolution) and `docs/CONVENTIONS_OKF.md` (Concept /
   Bundle model, reserved filenames, excluded dirs).

3. **Ran the baseline gate** — `python scripts/okf_lint.py` → exit 0, 26 bundles,
   127 warnings, 0 failures. Warnings are all pre-existing (missing `type` on a few skill
   reference files, broken forward-reference / cache links). Recorded as the baseline.

4. **Picked the home (Routine 1, step 1).** The feature is cross-cutting docs-tooling and
   a genuinely new topic, so I created a new topic sub-bundle `docs/recipes/okf/` (per the
   skill's "new topic → create a new sub-bundle dir" guidance). This also satisfies the
   deliverable of an updated *sub-bundle* `index.md` / `log.md`.

5. **Wrote the recipe** `docs/recipes/okf/01_add_and_lint_a_knowledge_bundle.md` in the
   house shape: typed frontmatter (`type: runbook`, `tags: [recipe, okf]`), `**Goal:**`,
   `**Status:**` with real artifact links, `**Prerequisites:**`, a Quick-reference table, a
   short "why" story, a "what the linter checks (read the source)" section, numbered Steps
   for adding a bundle, and a Verification section enumerating the exact FAIL/WARN messages.
   All references are relative links to the real modules (`../../../scripts/okf_lint.py`,
   `../../CONVENTIONS_OKF.md`, `../index.md`), each verified to resolve.

6. **Declared the bundle (Routine 1, step 4).** Appended `"docs/recipes/okf"` to
   `DECLARED_BUNDLES` in `scripts/okf_lint.py`.

7. **Generated the catalog + log** with the bundled script (never hand-written):
   `make_bundle.py docs/recipes/okf --title "OKF knowledge-plane tooling" --depth-to-root 2`
   — depth 2 because a recipe sub-bundle is `docs/recipes/<topic>/`, so the convention link
   correctly emits `../../CONVENTIONS_OKF.md`.

8. **Linked the new sub-bundle** from the parent bundle-of-bundles `docs/recipes/index.md`
   (Sub-bundles list) and added a newest-first entry to `docs/recipes/log.md`.

9. **Ran the gate (Routine 4).** `python scripts/okf_lint.py` → **exit 0**, now
   **27 bundles**, **127 warnings (unchanged)**, **0 failures**. The new bundle added zero
   warnings and zero failures (`grep -c recipes/okf` over the output = 0).

## Result

- New recipe: `docs/recipes/okf/01_add_and_lint_a_knowledge_bundle.md`
- New sub-bundle catalog/history: `docs/recipes/okf/index.md`, `docs/recipes/okf/log.md`
- Declared in `scripts/okf_lint.py` (`DECLARED_BUNDLES`)
- Parent updated: `docs/recipes/index.md`, `docs/recipes/log.md`
- **Final `python scripts/okf_lint.py` exit code: 0** (0 failures; 127 pre-existing,
  unchanged warnings).
