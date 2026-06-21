---
type: convention
title: OKF knowledge-bundle convention
description: How we structure the developer/agent knowledge plane as Open Knowledge Format bundles.
tags: [okf, knowledge, convention, docs]
---

# OKF knowledge-bundle convention

This repo adopts the **Open Knowledge Format (OKF)** — the Google Cloud spec
([SPEC.md](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md),
Apache 2.0) that standardizes the "LLM wiki" pattern
([Karpathy gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f))
— as the convention for our **developer/agent knowledge plane**: the markdown
that humans and agents both author, read, and traverse.

We adopted it because we were already ~80% there. Our skills (`docs/skills/*/SKILL.md`)
are already markdown-with-frontmatter Concepts, and the Claude-Code agent memory
dir is already a Bundle (an `MEMORY.md` index + one-fact-per-file frontmatter +
`[[name]]` links). OKF just gives those an explicit, lintable name. Closing the
gap was near-zero marginal cost; the benefit is one declared, machine-checkable
convention with progressive-disclosure entry points and a cross-link safety net.

## The model

### Concept

A Concept is a single markdown file with YAML frontmatter:

```markdown
---
type: skill        # REQUIRED — a self-describing string (skill, recipe,
                   #            research-prompt, convention, plan, …). Not
                   #            centrally registered; consumers tolerate
                   #            unknown values.
title: ...         # recommended
description: ...   # recommended — one line; powers index catalogs
tags: [...]        # optional
timestamp: ...     # optional — ISO-8601
resource: ...      # optional — canonical URI of the underlying asset
---

# Free-form markdown body
```

The Concept ID is the file path without `.md` (e.g. `docs/skills/gcp-live-smoke/SKILL`).
Producer-defined extension keys (like our existing `paths:` on `SKILL.md`) are
allowed and ignored by consumers that don't understand them.

### Bundle

A Bundle is a directory of Concepts plus two reserved files:

* **`index.md`** — a progressive-disclosure catalog: one line per Concept with a
  relative link and its one-line description. Reuse the `MEMORY.md` index shape
  (`- [Title](path) — hook`).
* **`log.md`** — a chronological history, **newest first**, ISO-8601 dated, one
  line per notable change to the bundle.

Other reserved names we treat as non-Concept: `README.md`.

### Links

Cross-link Concepts with relative markdown links (`[text](../other/SKILL.md)`) or
`[[name]]` wiki-links (resolved to `<name>.md` anywhere in the same bundle).
Broken links are *tolerated by consumers* — a `[[link]]` may point at
not-yet-written knowledge — but the linter flags them so rot is visible.

## Declared bundles

| Bundle | Location | Notes |
|---|---|---|
| Skills | `docs/skills/` | Each `*/SKILL.md` is a `type: skill` Concept. |
| Research prompts | `research/` | Each `*.md` is a `type: research-prompt` Concept. |
| Agent memory | `~/.claude/.../memory/` (external) | Already OKF-conformant: `MEMORY.md` index + per-fact frontmatter + `[[name]]` links. Declared here, not vendored into the repo. |

To promote another directory to a managed bundle: add `index.md` + `log.md`,
add `type:` frontmatter to its Concepts, and append the path to `DECLARED_BUNDLES`
in [`scripts/okf_lint.py`](../scripts/okf_lint.py).

## Linting

```bash
python scripts/okf_lint.py
```

* **FAIL** (exit 1): a declared bundle is missing, or is missing its
  `index.md` / `log.md`.
* **WARN** (exit 0): a Concept is missing a non-empty `type`, or a markdown/wiki
  link is broken. Both are non-blocking — OKF treats a broken link as
  not-yet-written knowledge, so it is surfaced for rot-visibility without
  breaking CI, and `type` can be backfilled incrementally.

Generated eval-evidence trees (`*-workspace/` dirs, `outputs/`, `run-*/`) are
not authored Concepts and are skipped by the linter.

## Explicit non-scope

OKF is for the shared, version-controlled, human-and-agent knowledge plane. It is
**deliberately NOT applied** to:

* **Runtime long-term memory** (`services/long_term_memory.py`, the Mem0/SQLite
  backends). That subsystem is data-native and multi-tenant on purpose: opaque
  payloads, content-free governance carriers, per-user isolation via
  `memory_subject()`. Markdown files would fragment the single source of truth and
  break the content-free audit model.
* **In-app RAG / vector ingestion.** Read-only markdown covers the knowledge-plane
  need; we are not building a retrieval pipeline.
* **Per-user multi-tenant bundles.** Git markdown is a shared plane; per-user
  content stays in the isolated memory subsystem.

A thin, read-only loader that surfaces a bundle into the agent's prompt
(`additional_instructions`) is a **documented, deferred** option — see the plan —
to be built shadow-first only when a concrete runtime-read use case exists.

### Excluded directories (generated / evidence)

These directories hold **generated, ephemeral, or evidence** artifacts — not authored
knowledge — so they are **not** declared as OKF bundles and carry no `index.md`/`log.md`
or frontmatter requirement. They are the doc-plane analogue of the recipes
`*-workspace/` eval-evidence trees the linter already skips:

| Directory | Why excluded |
|---|---|
| `docs/research/` | Qualitative-research outputs (open/axial coding, shadow rounds, stage reports). Stage artifacts, not final specs. (Distinct from the **declared** root `research/` design-prompt bundle.) |
| `docs/reports/` | Session reports / gap analyses — timestamped, event-driven. |
| `docs/test-reports/` | Playwright run reports — test outputs. |
| `docs/IAA/` | Inter-annotator-agreement results — blind-annotation eval artifacts. |
| `docs/amp/` | A single ephemeral workspace-review snapshot. |
| `docs/drift/` | A JSON event-taxonomy schema (no markdown narrative). |

To bundle one later, declare it in `DECLARED_BUNDLES` and add `index.md`/`log.md`.
