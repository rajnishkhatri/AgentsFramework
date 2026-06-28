---
type: recipe
title: 'Recipe 16 — Adding and Linting an OKF Knowledge Bundle'
description: 'Declare a directory as an OKF knowledge bundle and keep the docs tree linting clean.'
tags: [recipe, cross-cutting, okf, docs]
---

# Recipe 16 — Adding and Linting an OKF Knowledge Bundle

**Goal:** Take a plain directory of markdown and promote it to a *declared* OKF
knowledge bundle the rest of the team — and our agents — can traverse: give it an
`index.md` catalog and a `log.md` history, stamp `type` frontmatter on every
Concept, register it with the linter, and prove the docs tree still lints clean.
After this recipe you have one more directory in the knowledge plane that is
machine-checkable for structural completeness and link rot.

**Status:** Ready to run | Pure-stdlib linter, no third-party dependency | Non-blocking by design

**Prerequisites:**

* The OKF convention: [`docs/CONVENTIONS_OKF.md`](../CONVENTIONS_OKF.md) — read
  the model (Concept / Bundle / Links) and the declared-bundles table first.
* The linter: [`scripts/okf_lint.py`](../../scripts/okf_lint.py) — pure stdlib,
  run from the repo root.

---

## Before We Start: What the Linter Actually Checks

The OKF linter is deliberately small. It walks every directory listed in its
`DECLARED_BUNDLES` tuple and asserts two things, at two different severities:

| Check | Severity | Exit code | Why |
|---|---|---|---|
| Bundle directory exists, and has both `index.md` and `log.md` | **FAIL** | `1` | Structural — a declared bundle with no catalog/history is broken. |
| Every authored `.md` (non-reserved) carries non-empty `type:` frontmatter | **WARN** | `0` | OKF's permissive consumer rule — `type` can be backfilled incrementally. |
| Every relative markdown link and `[[wiki-link]]` resolves | **WARN** | `0` | OKF treats a broken link as not-yet-written knowledge — surfaced for rot-visibility, never blocks CI. |

So the gate is **green as long as every declared bundle has its two reserved
files**. Warnings are advisory: they keep `type` coverage and link rot *visible*
without turning a half-written cross-link into a red build. The reserved names
(`index.md`, `log.md`, `README.md`) are exempt from the `type` check, and
generated eval-evidence trees (`*-workspace/` dirs, `outputs/`, `run-*/`) are
skipped entirely.

The lint gate, from the repo root:

```bash
python scripts/okf_lint.py
```

---

## Step 1 — Decide whether the directory should be a bundle at all

Not every directory of markdown is a Concept bundle. OKF is for the **shared,
version-controlled, human-and-agent knowledge plane**. Before promoting a
directory, confirm it holds *authored* knowledge, not generated artifacts:

* **Promote it** if it holds skills, recipes, research prompts, plans,
  conventions, walkthroughs — anything a human or agent authors and another reads.
* **Leave it excluded** if it holds generated/ephemeral/evidence output:
  session reports, test reports, IAA results, coding-round artifacts. The
  convention's *Excluded directories* table lists the current ones; add to it
  rather than forcing an `index.md`/`log.md` onto an evidence tree. The linter
  already skips `*-workspace/`, `outputs/`, and `run-*/` for the same reason.

If in doubt, the rule of thumb is: *would a teammate ever start reading here to
learn something?* If yes, bundle it. If it's only ever an audit trail, exclude it.

---

## Step 2 — Add the two reserved files

A bundle is a directory of Concepts plus exactly two reserved files. Create them.

### `index.md` — the progressive-disclosure catalog

One line per Concept: a relative link plus its one-line description. Reuse the
`MEMORY.md` index shape — `- [Title](path) — hook`. Point the reader at the
convention so the entry point is self-describing:

```markdown
# <Bundle name> — bundle index

OKF sub-bundle. Each entry is a typed Concept. See the convention in
[CONVENTIONS_OKF.md](../../CONVENTIONS_OKF.md).

- [Concept A](a.md) — one-line description of A.
- [Concept B](b.md) — one-line description of B.
```

> Adjust the `../../CONVENTIONS_OKF.md` hops to your bundle's depth — from
> `docs/recipes/<x>/index.md` it is `../../CONVENTIONS_OKF.md`; from a top-level
> `docs/<x>/index.md` it is `../CONVENTIONS_OKF.md`.

### `log.md` — the chronological history

Newest-first, ISO-8601 dated, one line per notable change. Give it `type: log`
frontmatter so it reads as a typed Concept (it's exempt from the `type` *check*
because it's reserved, but stamping it keeps the file self-describing and matches
the existing bundle logs):

```markdown
---
type: log
title: '<Bundle name> — bundle log'
---

# <Bundle name> — bundle log

Chronological history, newest first (ISO-8601).

- 2026-06-20 — Declared `<path>/` an OKF bundle: added `index.md` + this `log.md`,
  stamped `type` frontmatter on every Concept. Convention in
  [CONVENTIONS_OKF.md](../../CONVENTIONS_OKF.md); linted by `scripts/okf_lint.py`.
```

---

## Step 3 — Stamp `type` frontmatter on every Concept

Every authored `.md` in the bundle (except the reserved files) needs YAML
frontmatter with a non-empty `type:`. The value is a self-describing string —
`recipe`, `skill`, `research-prompt`, `convention`, `plan`, `validation-walkthrough`,
`log`, … — not centrally registered; consumers tolerate unknown values. Prepend,
don't rewrite — leave the body untouched:

```markdown
---
type: recipe
title: '<Concept title>'
description: '<one line — powers the index catalog>'
tags: [recipe, <topic>]
---

# <existing body, unchanged>
```

Only `type` is required by the linter; `title`/`description`/`tags` are
recommended and keep the index catalog and search useful.

---

## Step 4 — Register the bundle with the linter

Append the bundle's repo-root-relative path to `DECLARED_BUNDLES` in
[`scripts/okf_lint.py`](../../scripts/okf_lint.py):

```python
DECLARED_BUNDLES: tuple[str, ...] = (
    "docs/skills",
    "research",
    # ...
    "docs/your-new-bundle",   # ← add here
)
```

Two layering notes:

* **Nested bundles are fine.** If you declare both `docs/plan` and
  `docs/plan/adapter`, the linter gives each `.md` to the *deepest* declared
  bundle that owns it — no double-linting. A bundle-of-bundles (like
  `docs/recipes`) carries only a top-level `index.md`/`log.md`; its content lives
  in the registered sub-bundles, which is why `docs/recipes` is *not* itself in
  the tuple.
* **Wire it into a parent index too.** Registering with the linter makes the
  bundle *checked*; it doesn't make it *discoverable*. If it's a sub-bundle of an
  existing one (e.g. under `docs/recipes/`), add a line for it to the parent
  `index.md` so a human can actually find it.

---

## Step 5 — Lint clean

Run the gate from the repo root and confirm a zero exit code:

```bash
python scripts/okf_lint.py
echo "exit: $?"
```

Read the summary line:

```
okf_lint: N bundle(s), W warning(s), 0 failure(s)
```

* **`0 failure(s)` / exit `0`** — you're done. Your new bundle has its `index.md`
  and `log.md`, and every other declared bundle still does too.
* **A `FAIL` line / exit `1`** — a declared bundle is missing, or is missing one
  of its two reserved files. This is the only thing that breaks the build. Fix
  the named file and re-run.
* **`WARN` lines** — advisory. A new `WARN` for *your* files (missing `type`, a
  broken link you just wrote) is worth fixing now while the context is fresh;
  pre-existing warnings on other bundles are tracked debt, not your blocker.

> **Tip:** to see only what *your* change introduced, diff the warning set:
> `python scripts/okf_lint.py | sort > /tmp/after.txt` before and after, then
> `diff`. The gate's pass/fail only depends on the `FAIL` lines and the exit code.

---

## What "done" looks like

* The directory has an `index.md` (catalog) and a `log.md` (history, newest-first).
* Every authored Concept carries non-empty `type` frontmatter.
* The path is in `DECLARED_BUNDLES`, and — if it's a sub-bundle — linked from its
  parent `index.md`.
* `python scripts/okf_lint.py` exits `0` with `0 failure(s)`.

That's the whole contract: two reserved files per bundle, a `type` on every
Concept, and a clean exit code. The convention in
[`docs/CONVENTIONS_OKF.md`](../CONVENTIONS_OKF.md) is the source of truth; this
recipe is the muscle-memory for applying it.
