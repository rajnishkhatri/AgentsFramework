# Recipe house shape

Recipes in `docs/recipes/<topic>/` follow a consistent shape so a human or agent can
scan one and know exactly what it does, whether it's done, and what it depends on.
Match it — consistency is what makes the bundle browsable.

## Anatomy

```markdown
---
type: recipe             # default for a numbered recipe. Use a narrower type when it
                         # fits better: runbook (ops steps), validation-walkthrough,
                         # specification, failure-taxonomy, rubric, overview, spec, …
title: 'Recipe N — <Story title>'
description: '<one line: what this recipe accomplishes>'
tags: [recipe, <topic>]  # topic = the sub-bundle dir. Use HYPHENS, not underscores,
                         # to match the rest of the tree (e.g. memory-extractor, not
                         # memory_extractor). Never tag a research note `recipe`.
---

# Recipe N — <Story title>

**Goal:** <2–4 sentences. What you'll have when this recipe is done, and why it
matters. Concrete and outcome-focused.>

**Status:** <Complete | In progress | Planned> | <test counts / artifacts, if any>
**Prerequisites:** <Recipes / plans this builds on, as relative markdown links>

---

## Quick reference

| Item | Value |
|------|-------|
| CLI driver | `scripts/<...>.py` |
| Test harness | `tests/<...>.py` |

## Before we start: a short story (optional but encouraged)

A paragraph framing the *problem* the recipe solves — the bug that hid, the gap that
bit. Recipes that teach the "why" age better than bare step lists.

## Steps

1. ...
2. ...

## Verification

How to know it worked (commands, expected output, a trace to check).
```

## Numbering & filename

- Files are `NN_snake_case_title.md`, ordered by `NN`. The cross-cutting recipes that
  don't belong to a topic live at `docs/recipes/` root (e.g. `11_…`, `12b_…`).
- The `title` H1 carries the story; the `description` is the dry one-liner the catalog
  shows.

## Worked example (abridged, from the live tree)

```markdown
---
type: validation-walkthrough
title: 'Recipe 4 — End-to-End BlackBox → Langfuse Validation Runbook'
description: 'End-to-end BlackBox → Langfuse pipeline validation on GCP.'
tags: [recipe, governance]
---

# Recipe 4 — End-to-End BlackBox → Langfuse Validation Runbook

**Goal:** Validate the full BlackBox → Langfuse pipeline on GCP: all 9 event types
land as Langfuse observations, hash-chain scores attach, compliance dataset items are
created, and PII redaction works. Then verify rollback safety and document findings.

**Status:** Ready to run
**Prerequisites:** Recipes 0–3 completed; relay-enabled backend deployed
(see [blackbox_langfuse_gcp_deploy.plan.md](../../plans/blackbox_langfuse_gcp_deploy.plan.md))
```

After writing the file, regenerate the sub-bundle catalog and append a log entry:

```bash
# make_bundle computes the CONVENTIONS_OKF.md link relative to the bundle dir
# automatically — no --depth-to-root needed (it was a foot-gun: wrong depth = a
# broken convention link in every catalog entry).
python docs/skills/agentsframework-okf-curator/scripts/make_bundle.py \
    docs/recipes/<topic> --title "<Topic> recipes"
python scripts/okf_lint.py        # must exit 0
```
