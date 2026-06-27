---
type: runbook
title: 'Recipe 1 — Add and Lint a Knowledge Bundle'
description: 'Add a new OKF knowledge bundle (index.md / log.md / typed Concepts), declare it, and keep docs lint-clean with scripts/okf_lint.py.'
tags: [recipe, okf]
---

# Recipe 1 — Add and Lint a Knowledge Bundle

**Goal:** Add a new **OKF knowledge bundle** to the docs tree and prove it conforms —
so the next human or agent who lands on it finds the catalog (`index.md`), the history
(`log.md`), and one `type`-tagged Concept per file, all checked by a single gate. When
you finish, `python scripts/okf_lint.py` exits `0` and the new bundle is one of the
declared, machine-verified bundles.

**Status:** Complete | standalone linter [`scripts/okf_lint.py`](../../../scripts/okf_lint.py) (pure stdlib, no deps) + convention [`docs/CONVENTIONS_OKF.md`](../../CONVENTIONS_OKF.md)
**Prerequisites:** Read the convention [`CONVENTIONS_OKF.md`](../../CONVENTIONS_OKF.md) for the Concept/Bundle model and the `type` vocabulary.

---

## Quick reference

| Item | Value |
|------|-------|
| Lint gate | `python scripts/okf_lint.py` (run from repo root) |
| Convention | [`docs/CONVENTIONS_OKF.md`](../../CONVENTIONS_OKF.md) |
| Declared-bundle list | `DECLARED_BUNDLES` tuple in [`scripts/okf_lint.py`](../../../scripts/okf_lint.py) |
| Reserved filenames | `index.md`, `log.md`, `README.md` (never Concepts) |
| Exit code | `0` = structurally sound; `1` = a bundle is missing `index.md`/`log.md` |

## Before we start: a short story

The point of a bundle is **progressive disclosure**: an agent lands on a topic's
`index.md`, reads one line per Concept, and pulls only the file it needs. That promise
breaks silently the moment a bundle ships without an index, or a Concept ships without a
`type` — the catalog goes stale, the agent can't tell a recipe from a rubric, and nobody
notices until a reader trusts the wrong file.

`scripts/okf_lint.py` is the cheap insurance against that. It is a **standalone, stdlib-only**
checker (it mirrors the other one-file utilities under `scripts/`) that walks every
*declared* bundle and asserts three things:

1. the bundle directory exists and has both an `index.md` and a `log.md` — **FAIL** (exit 1) if not;
2. every authored `.md` carries non-empty `type:` frontmatter — **WARN** only;
3. every relative markdown link and `[[wiki-link]]` resolves — **WARN** only.

Only the structural check (1) is blocking. OKF treats missing `type` and broken links as
*not-yet-written knowledge* — surfaced for rot-visibility, but non-blocking so you can
backfill incrementally. That split is deliberate: CI never goes red on a forward-reference
or an un-backfilled tag, only on a bundle that is structurally broken.

## What the linter checks (read the source)

The contract is entirely in [`scripts/okf_lint.py`](../../../scripts/okf_lint.py):

- **`DECLARED_BUNDLES`** — the tuple of directories the linter governs. A directory is only
  checked if it is in this tuple. `docs/recipes` itself is *not* listed — it is a
  bundle-of-bundles (a top-level `index.md` only); its content lives in the topic
  sub-bundles (`docs/recipes/gcp`, `…/governance`, this `…/okf`, …) so files aren't
  double-counted.
- **`RESERVED = {index.md, log.md, README.md}`** — these are never treated as Concepts, so
  they are exempt from the `type` requirement.
- **Evidence skip** — any `.md` whose path contains an `outputs/` segment, a `run-N/` dir,
  or a `*-workspace` dir is skipped entirely (generated eval-evidence, not authored
  knowledge). Same idea as the excluded dirs in `CONVENTIONS_OKF.md` (`docs/research/`,
  `docs/reports/`, …): generated artifacts are never bundled.
- **Link resolution is forgiving** — a link resolves if it exists relative to the file
  *or* relative to the repo root, so a doc that links `services/x.py` (repo-root-relative)
  is not flagged. Code fences and inline spans are stripped before scanning, so
  `if [[ -n "$X" ]]` in a bash block is not mistaken for a wiki-link.

## Steps — add a new bundle

These steps add a brand-new topic bundle. (To add a Concept to an *existing* bundle, skip
to step 4: write the file, then regenerate `index.md`/`log.md`.)

1. **Create the directory and write your Concepts.** One markdown file per Concept under
   `docs/<topic>/` (or `docs/recipes/<topic>/` for recipes). Each Concept needs YAML
   frontmatter with at least a non-empty `type` (reuse the vocabulary in
   `CONVENTIONS_OKF.md` — `recipe`, `runbook`, `spec`, `rubric`, `overview`, …):

   ```markdown
   ---
   type: runbook
   title: 'My Concept'
   description: 'One line — this powers the index catalog.'
   tags: [recipe, mytopic]
   ---

   # My Concept
   ...body...
   ```

   For a batch of pre-existing files, prepend frontmatter mechanically instead of by hand:

   ```bash
   python docs/skills/agentsframework-okf-curator/scripts/add_frontmatter.py \
       docs/recipes/<topic> --type runbook --tag "recipe, <topic>"
   ```

2. **Generate `index.md` + `log.md`** from the Concepts' frontmatter — never hand-write the
   catalog, or it drifts from the files:

   ```bash
   python docs/skills/agentsframework-okf-curator/scripts/make_bundle.py \
       docs/recipes/<topic> --title "<Topic> recipes" --depth-to-root 2 \
       --note "Declared <topic> as an OKF sub-bundle."
   ```

   `--depth-to-root` is the number of `../` from the bundle dir to `docs/CONVENTIONS_OKF.md`:
   `docs/<x>/` is **1**, `docs/<x>/<y>/` (like a recipe sub-bundle) is **2**. A wrong depth
   is the #1 source of a broken convention link in the catalog.

3. **Declare the bundle.** Append the bundle's path to the `DECLARED_BUNDLES` tuple in
   [`scripts/okf_lint.py`](../../../scripts/okf_lint.py). Until you do this, the linter
   does not check the bundle at all — so a missing `index.md` would pass unnoticed.

4. **Link it from the parent index.** If the bundle is a recipe sub-bundle, add a line for
   it to [`docs/recipes/index.md`](../index.md) under *Sub-bundles* so the bundle-of-bundles
   catalog stays complete.

5. **Run the gate** (next section).

## Verification

Run the gate from the **repo root**:

```bash
python scripts/okf_lint.py
echo "exit: $?"
```

Expected:

- **exit `0`** — structurally sound; you are done. The final line reports
  `okf_lint: N bundle(s), W warning(s), 0 failure(s)`.
- **`FAIL …: missing required index.md` (exit 1)** — the only blocking condition. Re-run
  `make_bundle.py` for that bundle (step 2), or add the missing file, then re-run.
- **`FAIL …: declared bundle directory does not exist`** — you declared a path in
  `DECLARED_BUNDLES` that isn't there (typo, or you renamed the dir). Fix the tuple.
- **`WARN … missing non-empty 'type' frontmatter`** — non-blocking. Add `type:` to that
  Concept (`add_frontmatter.py` with `--insert-type-if-missing` for files that already
  carry a non-`type` frontmatter block).
- **`WARN … broken link -> …`** — non-blocking. Triage: fix genuine rot, or leave a
  deliberate forward-reference. Repo-root-relative code links (`services/x.py`) already
  resolve and won't warn.

A clean run prints only the summary line with `0 failure(s)`. That is the contract this
recipe guarantees.
