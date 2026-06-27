---
type: runbook
title: 'Recipe — Add and Lint an OKF Knowledge Bundle'
description: 'Declare a new OKF knowledge bundle and keep the docs tree lint-clean with scripts/okf_lint.py.'
tags: [recipe, okf]
---

# Recipe — Add and Lint an OKF Knowledge Bundle

**Goal:** Know exactly how to turn a directory of markdown into a *declared* OKF
knowledge bundle that the linter governs — so a new tool, subsystem, or research
topic gets an `index.md` catalog, a `log.md` history, typed Concepts, and a green
`scripts/okf_lint.py` run. When you finish you'll have a bundle a future agent can
land on, scan one line per Concept, and pull only what it needs — and a CI gate
that fails loudly the moment that structure rots.

**Status:** Complete — the linter (`scripts/okf_lint.py`) and the convention
(`docs/CONVENTIONS_OKF.md`) are shipped and govern 26 declared bundles today
(`okf_lint: 26 bundle(s), … 0 failure(s)`, exit 0).
**Prerequisites:** Read the convention at
[CONVENTIONS_OKF.md](../../CONVENTIONS_OKF.md) (the full rules + the EXCLUDED-dirs
list). The bundled generator and frontmatter scripts live under the curator skill:
[`docs/skills/agentsframework-okf-curator/scripts/`](../../skills/agentsframework-okf-curator/scripts/make_bundle.py).

---

## Quick reference

| Item | Value |
|------|-------|
| Lint gate (canonical) | [`scripts/okf_lint.py`](../../../scripts/okf_lint.py) |
| Convention (source of truth) | [`docs/CONVENTIONS_OKF.md`](../../CONVENTIONS_OKF.md) |
| Bundle registry | `DECLARED_BUNDLES` tuple in `scripts/okf_lint.py` |
| `index.md` + `log.md` generator | [`make_bundle.py`](../../skills/agentsframework-okf-curator/scripts/make_bundle.py) |
| Typed-frontmatter prepender | [`add_frontmatter.py`](../../skills/agentsframework-okf-curator/scripts/add_frontmatter.py) |
| Reserved (non-Concept) filenames | `index.md`, `log.md`, `README.md` |

## Before we start: a short story

We adopted OKF because we were already ~80% there — our skills and the agent
memory dir were already markdown-with-frontmatter Concepts. The remaining 20% was
the part that rots silently: a directory of docs that *looks* organized but has no
catalog, no history, and no machine that notices when a Concept loses its `type`
or a link goes stale. `scripts/okf_lint.py` is that machine. The trap it closes is
the **honour-system bundle** — a folder everyone treats as a knowledge bundle that
was never actually declared, so the linter never walks it, so nothing catches the
day its `index.md` drifts from the files underneath. This recipe is the checklist
that turns a folder into a *declared* bundle the linter is responsible for.

## What the linter checks (and what it does NOT)

`scripts/okf_lint.py` walks every path in its `DECLARED_BUNDLES` tuple and applies
three rules with two severities:

- **FAIL (exit 1)** — the only blocking condition. A declared bundle directory is
  missing, OR a bundle is missing its `index.md` or `log.md`. CI breaks here.
- **WARN (exit 0)** — non-blocking, surfaced for rot-visibility:
  - a Concept (`.md` that is not `index.md` / `log.md` / `README.md`) lacks a
    non-empty `type:` frontmatter key;
  - a relative markdown link or `[[wiki-link]]` does not resolve.

So **every Concept carries `type` frontmatter** is a WARN-level expectation, not a
hard gate — you backfill it incrementally, but a clean bundle has zero `type`
warnings. Two resolution niceties keep WARN noise honest: the linter strips code
fences before scanning for links (so `if [[ -n "$X" ]]` in a bash block isn't read
as a wiki-link), and it resolves links **repo-root-relative too** (so a doc linking
`services/x.py` is not "broken"). Generated eval-evidence (`*-workspace/` dirs,
`outputs/`, `run-*/`) is skipped entirely — it isn't authored Concepts.

## Steps

### 1. Decide whether you even need a new bundle

Prefer an **existing** sub-bundle if your docs belong to a topic that already has
one (`docs/recipes/gcp`, `…/governance`, `…/guardrails`, …). Only create a new
bundle when the topic is genuinely new and coherent (a new tool, a new subsystem,
a new deploy target). A flat file at `docs/recipes/` root is NOT inside a declared
topic bundle — reserve the root for truly cross-cutting one-offs. And do not bundle
**generated / evidence** dirs (`docs/research/`, `docs/reports/`,
`docs/test-reports/`, `docs/IAA/`, `docs/amp/`, `docs/drift/`) — they're EXCLUDED
on purpose (see the convention's EXCLUDED table). Bundling generated artifacts is
churn for no value.

### 2. Create the directory and write typed Concepts

```bash
mkdir -p docs/recipes/<topic>
# author one or more Concepts: docs/recipes/<topic>/NN_snake_case_title.md
```

Each Concept is one markdown file. Give it YAML frontmatter with at minimum a
**non-empty `type`** (the only key the linter checks); `title` / `description` /
`tags` are recommended because they power the generated catalog:

```markdown
---
type: runbook                 # self-describing string; reuse the vocabulary
title: 'Recipe N — <Story title>'
description: '<one line — this is what index.md shows>'
tags: [recipe, <topic>]
---

# Recipe N — <Story title>
...
```

Reuse the established `type` vocabulary before inventing a new value (`runbook`,
`recipe`, `specification`/`spec`, `validation-walkthrough`, `failure-taxonomy`,
`rubric`, `overview`, `architecture`, `analysis`, `guide`, `plan`, …). For a batch
of existing files, prepend frontmatter with the bundled script instead of by hand:

```bash
python docs/skills/agentsframework-okf-curator/scripts/add_frontmatter.py \
    docs/recipes/<topic> --type runbook --tag "recipe, <topic>"
```

### 3. Generate `index.md` + `log.md`

The two reserved files are what make the directory a *bundle* the linter accepts.
Generate them from the Concepts' frontmatter so the catalog can never drift from
the files — do **not** hand-write them:

```bash
python docs/skills/agentsframework-okf-curator/scripts/make_bundle.py \
    docs/recipes/<topic> --title "<Topic> recipes" \
    --note "Added Recipe N — <title>."
```

`make_bundle.py` auto-computes the `CONVENTIONS_OKF.md` link relative to the bundle
dir, so **do not pass `--depth-to-root`** — the depth flag was the #1 catalog bug
(a wrong depth = a broken convention link in every entry). Re-run this any time you
add or rename a Concept; it rewrites `index.md` and re-seeds `log.md`.

### 4. Register the bundle in `DECLARED_BUNDLES`

A bundle the linter never heard of is never walked. Append the new path to the
`DECLARED_BUNDLES` tuple in [`scripts/okf_lint.py`](../../../scripts/okf_lint.py):

```python
DECLARED_BUNDLES: tuple[str, ...] = (
    "docs/skills",
    "research",
    "docs/recipes/gcp",
    # …
    "docs/recipes/<topic>",   # ← add the new sub-bundle here
)
```

Note the **bundle-of-bundles** rule: `docs/recipes` itself is *not* declared (only
its topic sub-bundles are), which avoids double-counting nested recipe files. The
linter already skips a deeper declared bundle's files when walking its parent, so
declaring `docs/plan` and `docs/plan/adapter` together does not double-lint.

### 5. Link the new sub-bundle from the parent recipes index

`docs/recipes/index.md` is the bundle-of-bundles catalog. Add a line under
**Sub-bundles** pointing at the new `index.md` so a human or agent browsing the
recipes plane can discover it:

```markdown
- **[<Topic> recipes](<topic>/index.md)** — <N> Concept(s): <one-line hook>.
```

### 6. Lint

```bash
python scripts/okf_lint.py    # → exit 0
```

## Verification

Run the canonical gate from the repo root and confirm **exit 0**:

```bash
python scripts/okf_lint.py; echo "EXIT=$?"
```

A clean add looks like:

- the summary line counts your new bundle:
  `okf_lint: 27 bundle(s), … 0 failure(s)`;
- **zero `FAIL` lines** (a FAIL means the bundle dir or its `index.md` / `log.md`
  is missing — exit would be 1);
- **no new `WARN` lines for your bundle** — every new Concept should carry a
  non-empty `type`, and its links should resolve (pre-existing WARNs elsewhere in
  the tree are expected and non-blocking).

If the linter reports your bundle as missing `index.md`/`log.md`, re-run
`make_bundle.py` (Step 3). If it WARNs that a Concept is missing `type`, add the
frontmatter (Step 2) and regenerate the catalog so the new entry's title and
description appear.
