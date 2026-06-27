# Transcript — eval-2 file-research-note (with_skill)

## Task
File a user-authored research note on memory-extractor calibration thresholds into the
OKF knowledge plane, in the right home, and keep the knowledge tree lint-clean.

## What I did

1. **Read the skill** (`agentsframework-okf-curator/SKILL.md`) and identified this as
   **Routine 2 — File research**. Read `docs/CONVENTIONS_OKF.md` (the canonical rules) to
   confirm the homes and the excluded dirs.
2. **Classified the note** (see WHY below) → authored design knowledge → root `research/`
   bundle.
3. **Created the Concept** at `research/memory_extractor_calibration_thresholds.md` with
   typed frontmatter:
   - `type: research-note` (a fitting self-describing type; the existing 3 Concepts are
     `research-prompt` system prompts, this is a design reference, not a prompt)
   - `title`, `description` (one line, powers the index), `tags`.
   - Body: a thresholds table + prose for each bar, plus a "where the numbers come from /
     what they gate" section tying the frozen test split to the enable-policy certificate
     and write-back. Faithful to the user's content; no facts changed.
4. **Updated the bundle catalog by hand** (the skill permits hand-editing for a single new
   file, and `make_bundle.py` would have damaged the existing hand-curated index/log — see
   notes below):
   - `research/index.md`: added the new entry (kept alphabetical-ish ordering, new file
     first as in the existing list style) and generalized the header from "research
     prompts / `type: research-prompt`" to cover both prompts and notes.
   - `research/log.md`: prepended a newest-first dated entry; preserved the prior entry.
5. **Ran the gate** from the worktree root: `python scripts/okf_lint.py` → **exit 0**.
   `26 bundle(s), 127 warning(s), 0 failure(s)`. Confirmed via grep that **none** of the
   127 warnings reference the new file or the `research/` bundle — they are all
   pre-existing (broken links to code/cache paths, cross-skill wiki-links, and missing
   `type` on skill reference sub-files), unrelated to this change.

## WHERE I filed it

`/tmp/okf-eval-2-with/research/memory_extractor_calibration_thresholds.md`
(repo path: `research/memory_extractor_calibration_thresholds.md`)

This is the **declared root `research/` OKF bundle** — the authored design-knowledge home.

## WHY this home (authored vs evidence)

The skill's Routine 2 test: *"would a future agent treat this as a fact to rely on, or as a
record of what happened once?"* — Facts → root `research/`; records → `docs/research/`
(EXCLUDED from OKF).

The user explicitly framed this as **"a reusable design reference we'll rely on going
forward, not just a record of one run."** Those thresholds (precision `>=0.90`,
PII-flip `==0`, kappa `>=0.60`) are a standing acceptance bar — a source of truth to gate
future runs and certificate emissions against. That is authored design knowledge, so it
belongs in root `research/`, gets typed frontmatter, and is catalogued in the bundle
index/log.

It is explicitly **NOT** `docs/research/`. Per `CONVENTIONS_OKF.md`, `docs/research/` is
the EXCLUDED dir for "qualitative-research outputs ... stage artifacts, not final specs" —
i.e. records of what happened once (coding rounds, run reports). Dropping a relied-upon
design reference there would bury it outside the linted, catalogued, agent-navigable plane.
The two are deliberately distinct: the excluded `docs/research/` (evidence) vs the declared
root `research/` (design knowledge).

## Notes / decisions
- **Did not run `make_bundle.py`.** Two reasons: (a) for a root-level bundle it emits the
  convention link as `../CONVENTIONS_OKF.md`, but the correct link from `research/` is
  `../docs/CONVENTIONS_OKF.md` (the skill/script docs both call this out — "verify the
  emitted link resolves, or fix by hand"); (b) it would clobber the existing hand-curated
  `index.md` header and the prior `log.md` entry. Hand-editing was lower-risk and the skill
  sanctions it for a single new file. The existing `../docs/CONVENTIONS_OKF.md` link is
  preserved and resolves.
- **No new `DECLARED_BUNDLES` entry needed** — `research/` is already a declared bundle in
  `scripts/okf_lint.py`; I added a Concept to it, not a new bundle.

## Result
- File created in the correct authored home.
- Bundle index + log updated and consistent with the new Concept.
- `python scripts/okf_lint.py` → **exit 0**, 0 failures; new file introduces 0 warnings.
