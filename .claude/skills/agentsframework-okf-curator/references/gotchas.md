# OKF curation gotchas

The traps that cost real time during the docs/ OKF conversion. Read before a large
change so you don't re-trip them.

## Moving files

- **A move breaks references in BOTH directions.** Links pointing *at* the file, and
  the moved file's *own* outbound relative links (depth changed), all shift. The
  `relocate.py` script fixes both — but only for the three forms it knows
  (markdown links, `@docs/` mentions, bare `docs/` / `agent/docs/` paths). Anything
  exotic (a path built by string concatenation in code, a link in a `.canvas` file)
  it will miss — grep afterwards.
- **`@docs/NAME.md` @-mentions in `AGENTS.md` are LOAD-BEARING.** They tell the agent
  which docs to pull into context. If a move leaves one stale, the agent silently
  loses that context — no error, just degraded behaviour. Always re-resolve every
  `@docs/` mention after a move (strip `@`, assert the path exists).
- **`git mv` fails on untracked files** ("not under version control"). `relocate.py`
  falls back to a plain `mv`; those show up as add+delete, not a rename, in
  `git status`. That's expected — don't chase it as a bug.
- **Always `--plan` first**, eyeball the reference counts, then `--apply`.

## Frontmatter

- **Pure prepend, never mutate the body.** `add_frontmatter.py` asserts the body below
  the inserted block is byte-identical. If you hand-edit, keep that property — a
  reviewer should be able to confirm "frontmatter added, nothing else" from the diff.
- **Native plan-mode files already have frontmatter** (`name:`/`overview:`/`todos:`)
  but no `type`. Don't wrap them in a second block — insert a single `type:` key
  with `--insert-type-if-missing`.
- **Descriptions must not contain raw markdown links.** A link truncated mid-token
  (`...(02_walkthrou`) leaks into the catalog and the linter flags it as a broken
  link. `add_frontmatter.py` strips links to their text and truncates on word
  boundaries — preserve that if you write a description by hand.
- **`type` and `tags` should fit the Concept, not the folder.** A numbered recipe is
  `type: recipe` (not `runbook` unless it's purely operational steps); a research note
  is `type: research-note`/`reference` and must NOT be tagged `recipe`. Tags use
  **hyphens** to match the tree (`memory-extractor`, not `memory_extractor`).
- **"Lint-clean" means the GATE passes (exit 0), not zero warnings.** The tree always
  carries some advisory WARNs (forward-reference links, un-typed auxiliary pages). The
  bar for a change is: **no new FAILs, and ideally no new WARNs from your files** — not
  "drive the global warning count to zero." Say "passes the OKF lint gate", and when you
  describe the linter in a doc, state it precisely: *structural failures (missing
  bundle/index/log) block with exit 1; type/link warnings are advisory and non-blocking.*

## Bundles & the linter

- **`make_bundle.py` now auto-computes the `CONVENTIONS_OKF.md` link** relative to the
  bundle dir, so you don't pass `--depth-to-root` anymore. (The old depth flag was the #1
  catalog bug: wrong depth = a broken convention link in every entry, and the root
  `research/` bundle needs `../docs/CONVENTIONS_OKF.md`, not `../CONVENTIONS_OKF.md` — a
  naive depth-1 got that wrong.) The flag still exists as a legacy override; prefer the
  default. If you hand-write a catalog, compute the link relative to *that* bundle dir.
- **Declare nested bundles, not their parent's files twice.** If both `docs/plan` and
  `docs/plan/adapter` are declared, `okf_lint.py` already skips the deeper bundle's
  files when walking the parent (don't double-count).
- **`index.md` / `log.md` / `README.md` are reserved** — the linter never requires a
  `type` on them, and they aren't Concepts.
- **Evidence dirs stay excluded.** `docs/research`, `docs/reports`, `docs/reviews`-as-
  evidence, `docs/test-reports`, `docs/IAA`, `docs/amp`, `docs/drift` are NOT bundles.
  See the EXCLUDED section of `docs/CONVENTIONS_OKF.md`. Bundling generated artifacts
  is churn for no value.

## Linter semantics (so you read its output right)

- **FAIL (exit 1)** only on a missing bundle dir or a missing `index.md`/`log.md`.
  Everything else is a non-blocking **WARN**.
- **WARN** on: a Concept missing `type`, or a broken link. Broken links are *tolerated*
  by OKF (not-yet-written knowledge) — surface them, don't block CI on them.
- The linter **strips code fences** before scanning for links, so `if [[ -n "$X" ]]`
  in a bash block isn't mistaken for a `[[wiki-link]]`. And it resolves links
  **repo-root-relative too**, so a doc linking `services/x.py` is not "broken".
  If you see a surprising WARN, check whether it's genuinely stale or a resolution
  edge case before "fixing" the doc.

## Drift report

- `drift_report.py` correlates changed code paths to docs that *mention* them — it's a
  worklist, not a verdict. Common filenames (`README.md`, `server.py`) produce noisy
  hits; judge each. Net-new behaviour with no existing doc mention is the signal to
  write a **new recipe**, not patch an old one.
