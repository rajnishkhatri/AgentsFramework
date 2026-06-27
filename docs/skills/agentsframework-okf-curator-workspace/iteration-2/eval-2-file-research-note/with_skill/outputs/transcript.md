# Transcript — eval-2 file research note (with skill)

Routine followed: **Routine 2 — File research** (agentsframework-okf-curator SKILL).

## What was filed

A new authored research Concept:

- **Path:** `research/memory_extractor_calibration_thresholds.md` (root `research/` bundle)
- **Type:** `reference`
- **Tags:** `[research, memory-extractor, calibration]`
- **Title:** "Memory extractor calibration thresholds"

Content captures the calibration acceptance thresholds verbatim from the user:
store-decision precision gate `>= 0.90`, PII-flip rate = hard zero, kappa-vs-gold
`>= 0.60` inter-rater floor; derived from the frozen test split; gates write-back via
the enable-policy certificate.

## WHERE it went and WHY — the authored-vs-evidence test

The SKILL's Routine 2 forces a single decision: *would a future agent treat this as a
fact to rely on, or as a record of what happened once?*

- **Facts to rely on → root `research/`** (a declared OKF bundle: typed, catalogued,
  linted, extractable).
- **Records of a single run / stage artifacts → `docs/research/`** — which is
  **EXCLUDED** from OKF on purpose (generated evidence; not bundled, not frontmattered,
  not catalogued).

The user explicitly framed this as "a reusable design reference we'll rely on going
forward, **not just a record of one run**." That is a fact-to-rely-on. The thresholds
are a design contract that future write-back gating and calibration runs are measured
against — they are a source of truth, not a dump of one calibration run's numbers.

Therefore it belongs in the **authored root `research/` bundle**, NOT the excluded
`docs/research/` evidence tree. (Had this been a single calibration run's report or a
gold-set dump, it would have gone to `docs/research/` with no bundling.)

## WHY this type (and not `recipe`)

- `recipe` was explicitly disallowed and would be wrong anyway — this is not a numbered
  implementation recipe and does not live under `docs/recipes/`.
- The existing `research/` Concepts are all `type: research-prompt` because they are
  literally system prompts. This note is **not a prompt** — it is a reusable design
  reference (a small table of acceptance thresholds). Routine 2 says use
  `research-prompt` "or a fitting type"; the convention `type` vocabulary lists
  `reference` for misc authored knowledge that is a source of truth.
- Chose **`type: reference`** as the research-appropriate, accurate type: a design
  reference of thresholds. Tags `[research, memory-extractor, calibration]` keep it
  discoverable under its subsystem (memory_extractor) and topic (calibration) while
  marking it as research-bundle content.

## How the bundle was updated

- Regenerated `research/index.md` with the bundled `make_bundle.py`
  (`python3 docs/skills/agentsframework-okf-curator/scripts/make_bundle.py research
  --title "Research" --note "…"`). The script auto-computes the convention link relative
  to the bundle dir, emitting the correct `../docs/CONVENTIONS_OKF.md` for the
  root-level `research/` bundle (verified — not the naive `../CONVENTIONS_OKF.md`).
  Index now lists 4 entries.
- `make_bundle.py` re-seeds `log.md` with a single dated entry (its `--append-log`
  is documented but not wired into argparse), which would have clobbered the prior
  "Declared `research/` an OKF bundle" history line. Per the SKILL ("hand-edit the
  research index/log if cleaner"), I restored the prior log entry by hand below the
  new one so the log stays newest-first and loses no history.
- `research/` is already in `DECLARED_BUNDLES` in `scripts/okf_lint.py`, so no linter
  registration edit was needed.

## Lint gate

`python3 scripts/okf_lint.py` → **exit 0**.
`okf_lint: 26 bundle(s), 130 warning(s), 0 failure(s)` — warning count unchanged from
the pre-change baseline (130), confirming the new Concept introduced **zero** new
warnings (fully typed, links resolve) and the knowledge tree is lint-clean. All 130
WARNs are pre-existing, unrelated broken-link/missing-type warnings elsewhere in the
tree. Full stdout + exit code captured in `lint_result.txt`.
