# OKF convention — quick reference

The canonical convention lives at [`docs/CONVENTIONS_OKF.md`](../../../CONVENTIONS_OKF.md)
(read it for the full rules + the EXCLUDED-dirs list). This is the working summary.

## The model

- **Concept** — one markdown file with YAML frontmatter. `type` is required; `title`,
  `description`, `tags` are recommended. Body is free-form markdown.
- **Bundle** — a directory of Concepts plus `index.md` (catalog) + `log.md`
  (newest-first history). Reserved filenames: `index.md`, `log.md`, `README.md`.
- **Cross-links** — relative markdown links or `[[name]]`. Broken links are tolerated
  (not-yet-written knowledge) but linted as WARN.

## `type` vocabulary in use

Self-describing strings; consumers tolerate any value. The ones already used across
the tree (reuse these before inventing new ones):

| `type` | For |
|---|---|
| `recipe` | a numbered implementation recipe |
| `runbook` | operational step-by-step (deploy, ops) |
| `specification` / `spec` | a contract / design spec |
| `validation-walkthrough` | manual end-to-end validation procedure |
| `failure-taxonomy` | categorized failure modes (eval) |
| `rubric` | a judging rubric |
| `overview` | conceptual intro to a topic |
| `architecture` | architecture document |
| `analysis` | an analysis / comparison |
| `guide` / `handbook` | how-to / contributor guide |
| `plan` / `roadmap` | a plan or roadmap |
| `style-guide` | a code style guide |
| `reference` / `notes` / `narrative` / `process-guide` | misc authored knowledge |
| `skill` | a `SKILL.md` Concept |

## Declared bundles & the linter

- The set of bundles is the `DECLARED_BUNDLES` tuple in
  [`scripts/okf_lint.py`](../../../../scripts/okf_lint.py). To promote a new directory to
  a bundle: add `index.md` + `log.md`, add `type:` frontmatter to its Concepts, and
  append its path to `DECLARED_BUNDLES`.
- A **bundle-of-bundles** (like `docs/recipes` or top-level `docs`) is NOT declared
  itself — only its sub-bundles are — so nested files aren't double-counted. It still
  gets an `index.md` linking the sub-bundles.
- Run the gate: `python scripts/okf_lint.py` → exit 0 means structurally sound.

## Where things go

- **Recipes** → `docs/recipes/<topic>/` (one sub-bundle per topic).
- **Authored research / design prompts** → root `research/` (a declared bundle).
- **Research EVIDENCE** (coding rounds, stage reports, gold-set artifacts) →
  `docs/research/` — **EXCLUDED** from OKF (generated, not authored). Don't bundle it.
- **Architecture / style guides / guides / analyses / reviews** → their existing
  `docs/<dir>/` bundles.

## Out of scope (never bundle)

`docs/research`, `docs/reports`, `docs/reviews`-as-evidence, `docs/test-reports`,
`docs/IAA`, `docs/amp`, `docs/drift`. These are generated/ephemeral. Also out of scope
for OKF entirely: runtime long-term memory (`services/long_term_memory.py`), in-app RAG,
and per-user content — those are data-native and multi-tenant by design.
