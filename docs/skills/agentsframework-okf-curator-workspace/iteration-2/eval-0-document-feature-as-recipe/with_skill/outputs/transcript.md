# Transcript — Document the OKF linter feature as a recipe (with_skill)

**Worktree (repo root):** `/tmp/okf-eval2-0-with`
**Skill followed:** `docs/skills/agentsframework-okf-curator/SKILL.md` — **Routine 1
(Document a feature as a recipe)** + **Routine 4 (Keep it extractable)**.
**Date:** 2026-06-20

## Task

> We just shipped a standalone OKF linter at `scripts/okf_lint.py` plus the
> convention doc at `docs/CONVENTIONS_OKF.md` — it declares knowledge bundles and
> checks that each has an `index.md`/`log.md` and that every Concept carries `type`
> frontmatter. Document this as a recipe so the team knows how to add and lint a
> bundle. Then make sure the docs tree still lints clean.

## What I did (and why)

1. **Read the skill and its references first** — `SKILL.md`,
   `references/recipe-template.md`, `references/conventions.md`,
   `references/gotchas.md`. Then read the actual artifacts to document:
   `scripts/okf_lint.py` (the gate), `docs/CONVENTIONS_OKF.md` (the convention),
   and the bundled `docs/skills/agentsframework-okf-curator/scripts/make_bundle.py`.

2. **Established a clean baseline** — ran `python scripts/okf_lint.py` before any
   change: **exit 0**, `26 bundle(s), 130 warning(s), 0 failure(s)`. The 130 WARNs
   are all pre-existing (missing `type` on some skill reference files + broken
   links to `cache/`, `*-workspace`, and not-yet-written docs) and are non-blocking.

3. **Picked the home — a NEW topic sub-bundle (Routine 1, step 1).** The feature is
   the OKF knowledge-plane tooling itself (the linter + the convention). It does
   not belong to any existing recipe sub-bundle (`gcp` / `governance` /
   `guardrails` / `goaljudge` / `memory_extractor`), and it is not a cross-cutting
   runtime fix like the flat root recipes 11–15. Per the skill's guidance to
   **PREFER a topic sub-bundle** for a coherent topic and to **register a new
   topic** when it's genuinely new, I created a new sub-bundle:
   **`docs/recipes/okf/`**. (A flat file at `docs/recipes/` root would NOT be
   inside a declared topic bundle, so that was rejected.)

4. **Wrote the recipe** at
   **`docs/recipes/okf/00_add_and_lint_a_bundle.md`** in the house shape from
   `references/recipe-template.md`: typed frontmatter
   (`type: runbook`, `title`, `description`, `tags: [recipe, okf]`), a `**Goal:**`,
   a real `**Status:**` (linter + convention shipped; 26 bundles, exit 0 today),
   `**Prerequisites:**` as relative links, a Quick-reference table, a short
   "why this exists" story (the honour-system-bundle trap), an explicit
   **What the linter checks (FAIL vs WARN)** section, numbered Steps
   (decide → create dir + typed Concepts → `make_bundle.py` → register in
   `DECLARED_BUNDLES` → link from parent index → lint), and a **Verification**
   section grounded in the real `okf_lint:` summary line. Every reference links the
   actual code (`scripts/okf_lint.py`, `docs/CONVENTIONS_OKF.md`, the bundled
   scripts) — all 7 links verified to resolve.

5. **Registered the new bundle in `DECLARED_BUNDLES`** (Routine 1, step 4) — added
   `"docs/recipes/okf",` to the tuple in `scripts/okf_lint.py`, grouped with the
   other `docs/recipes/*` topic sub-bundles. Also relaxed the stale comment
   "five topic sub-bundles" → "the topic sub-bundles" since there are now six.

6. **Generated `index.md` + `log.md` with the bundled `make_bundle.py`** (Routine
   1, step 4) — **no `--depth-to-root`** (the skill / gotchas call the depth flag
   the #1 catalog bug; the script auto-computes the convention link). Verified the
   emitted `../../CONVENTIONS_OKF.md` link resolves for this depth-2 bundle.

   ```bash
   python docs/skills/agentsframework-okf-curator/scripts/make_bundle.py \
       docs/recipes/okf --title "OKF knowledge-plane recipes" \
       --note "Declared docs/recipes/okf/ as an OKF sub-bundle; added Recipe — Add and Lint an OKF Knowledge Bundle."
   ```

7. **Linked the new sub-bundle from the parent recipes index** (Routine 1, step 1
   guidance — "linking from the parent recipes index") — added a bullet under
   **Sub-bundles** in `docs/recipes/index.md` pointing at `okf/index.md`.

8. **Ran the lint gate** (Routine 1 step 5 / Routine 4):
   `python scripts/okf_lint.py` → **exit 0**,
   `27 bundle(s), 130 warning(s), 0 failure(s)`.

## Result

- **Lint exit code: 0** (gate passed). FAILURES: 0.
- Bundle count went **26 → 27** (the new `docs/recipes/okf` is now walked).
- Warning count is **unchanged at 130** — the new bundle added **zero** new
  warnings: the single Concept carries `type` frontmatter, and all its links
  resolve. The docs tree still lints clean.

## Where the recipe lives

- **Recipe:** `docs/recipes/okf/00_add_and_lint_a_bundle.md`
- **Sub-bundle catalog:** `docs/recipes/okf/index.md`
- **Sub-bundle history:** `docs/recipes/okf/log.md`

## Did I register it in DECLARED_BUNDLES and link the parent index?

- **DECLARED_BUNDLES:** YES — added `"docs/recipes/okf",` to the tuple in
  `scripts/okf_lint.py` (and updated the adjacent "five sub-bundles" comment).
- **Parent recipes index:** YES — added a Sub-bundles bullet to
  `docs/recipes/index.md` linking `okf/index.md`.

## Files changed in the worktree

- `docs/recipes/okf/00_add_and_lint_a_bundle.md` (new — the recipe)
- `docs/recipes/okf/index.md` (new — generated)
- `docs/recipes/okf/log.md` (new — generated)
- `scripts/okf_lint.py` (edited — registered the bundle + comment)
- `docs/recipes/index.md` (edited — parent sub-bundle link)
