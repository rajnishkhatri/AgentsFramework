# Transcript — Document the OKF linter feature as a recipe

## Task
Document the newly-shipped standalone OKF linter (`scripts/okf_lint.py`) and its
convention doc (`docs/CONVENTIONS_OKF.md`) as a team-facing recipe explaining how
to add and lint a knowledge bundle. Then ensure the docs tree still lints clean.

## What I read first
1. `docs/CONVENTIONS_OKF.md` — the OKF model (Concept = `.md` + `type` frontmatter;
   Bundle = directory + reserved `index.md`/`log.md`; relative + `[[wiki]]` links),
   the declared-bundles table, the FAIL/WARN severities, and the excluded-dirs list.
2. `scripts/okf_lint.py` — confirmed the exact gate behavior: FAIL (exit 1) only on
   a missing declared bundle or a missing `index.md`/`log.md`; `type`-frontmatter and
   broken-link checks are WARN (exit 0); reserved names exempt from `type`;
   `*-workspace/`/`outputs/`/`run-*/` skipped; nested bundles owned by deepest match.
3. Existing recipe conventions: `docs/recipes/index.md`, `docs/recipes/log.md`, the
   `governance/` sub-bundle's `index.md`/`log.md`, and Concept frontmatter shape
   (e.g. `15_goaljudge_runtime_config_toggle.md`, `governance/04_*.md`).

## Baseline
Ran `python3 scripts/okf_lint.py` before any change: **exit 0**, 26 bundles,
**127 warnings, 0 failures**. The tree already lints clean; the 127 warnings are
pre-existing, non-blocking debt on other bundles.

## What I created / changed
- **New recipe** `docs/recipes/16_okf_bundle_lint.md` — a cross-cutting recipe
  ("Recipe 16 — Adding and Linting an OKF Knowledge Bundle"). Placed at the top
  level of `docs/recipes/` (not in a topic sub-bundle) because the linter is
  docs-tooling that spans every bundle. It walks the reader through: deciding
  whether a directory should be a bundle, adding the two reserved files, stamping
  `type` frontmatter on Concepts, registering the path in `DECLARED_BUNDLES`,
  wiring it into the parent index, and reading the lint output (FAIL vs WARN vs
  exit code). Carries `type: recipe` frontmatter; all links resolve.
- **Updated** `docs/recipes/index.md` — added the Recipe 16 line under
  "Cross-cutting recipes" so the new Concept is discoverable.
- **Updated** `docs/recipes/log.md` — prepended a newest-first ISO-8601 entry
  recording the addition.

No file moves, no changes to bodies of existing recipes, no change to the linter
itself (the new recipe lives inside the already-declared `docs/recipes` bundle, so
no `DECLARED_BUNDLES` edit was needed).

## Final lint
`python3 scripts/okf_lint.py` → **exit 0**, 26 bundles, **127 warnings, 0 failures**.
Warning count is unchanged from baseline: the new recipe and the edited index/log
introduced **zero** new warnings (verified by grepping the output for the changed
paths). The docs tree lints clean.

## Outputs saved here
- `16_okf_bundle_lint.md` — the new recipe (a)
- `recipes_index.md`, `recipes_log.md` — the updated bundle index/log (b)
- `lint_result.txt` — exact stdout of `python scripts/okf_lint.py` + exit code (c)
- `transcript.md` — this file (d)
