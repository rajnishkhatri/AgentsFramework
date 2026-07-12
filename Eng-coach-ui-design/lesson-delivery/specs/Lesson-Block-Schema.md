# Lesson-Block System — schema & composer

**Companion to:** `lesson-blocks-schema.json` (machine-readable) · `English Coach - Lesson Composer.dc.html` (working demo)
**Related:** `English Coach - Skill Lesson.dc.html` (baseline screen), `English Coach - Skill Lesson Options.dc.html` (directions 1a/1b/1c)

## Idea in one line
A lesson is **data** — an ordered list of typed blocks — not a hand-built layout. A runtime **composer** selects and orders blocks by learner **context**, then renders each by looking its `type` up in a component **registry**. Change the context, not the code, and the screen recomposes.

## Why
It unifies the three explored directions: color-coded signaling (1c), worked→try (1a), and the diagnostic lead (1b) become interchangeable **blocks** the composer mixes per context. It also extends the v2 philosophy (content-as-data, misconception tags) onto the lesson surface: the same learner signals that drive the outer loop pick the blocks.

## Color = meaning (semantic roles)
Every block declares a `role`; the composer resolves role → tint at render time. `--accent` on the screen root is the **skill's** bucket token, so accent blocks always read as the current skill's color.

| role | used for | tint |
|---|---|---|
| `neutral` | rule / reference | surface + border |
| `accent` | instruction, worked models, examples | bucket-accent 6% bg, 35% border |
| `accentDashed` | an active task to complete | dashed accent border, transparent |
| `accentSoft` | self-explanation / reflection | bucket-accent 5% |
| `warning` | the diagnosed error, due items | warning tint |
| `success` | confirmed answers / correct examples | success tint |

## Block catalog (v1 — 9 tags)
| tag | zone | role | key fields | when the composer uses it |
|---|---|---|---|---|
| `rule` | main | neutral | title, body, examples[] | always — the reference spine |
| `workedExample` | main | accent | sentence, steps[], answer | first exposure / rebuild (●●●) |
| `completionTry` | main | accentDashed | sentence, promptHint, choices[] | right after a worked example (●●○), ends on a win |
| `annotatedExample` | main | accent | examples[] (pre/clause/post/essential/callouts) | quick visual refresher — signaling |
| `misconceptionCallout` | main | warning | label, body, fix | returning learner with a diagnosed error |
| `dueChecklist` | rail | neutral | title, items[], cta | spaced items are due |
| `accuracyStat` | rail | accent | value, caption, bars[] | almost always (number always shown) |
| `selfExplainPrompt` | main | accentSoft | prompt | consolidation, before any explanation |
| `coachEntry` | rail | accent | label, body, cta | hand-off to the Socratic coach |

Each block also carries `zone` (`main` | `rail`) — the composer partitions blocks into the content column and the right rail.

## Context presets (demoed switcher)
The demo exposes three contexts; each is just an **ordered block list**.

| context | reasoning | block recipe |
|---|---|---|
| **New skill** | teach forward, end on a win | rule → workedExample → completionTry → selfExplainPrompt → accuracyStat |
| **Returning & struggling** | lead with the error, clear the due items | misconceptionCallout → annotatedExample → rule → dueChecklist → accuracyStat → coachEntry |
| **Quick refresher** | a pre-drill glance | annotatedExample → rule → accuracyStat |

**In production** the context is not a preset name but a decision from learner state (mastery, recent misconception tags, due schedule) — the same signals the v2 outer loop uses. Presets are the demonstrable form.

## Runtime contract
```
compose({ skill, context }):
  blocks   = CONTEXTS[context].blocks          // ordered tags
  vms      = blocks.map(tag => registry[tag].build(DATA[tag], role→color))
  main     = vms.filter(zone === 'main')
  rail     = vms.filter(zone === 'rail')
  root.style['--accent'] = SKILL_ACCENT[skill]
  render(sidebar, hero, main, rail)            // unknown tags skipped
```

## Extending
Add a block by (1) adding its entry to `blocks` in the schema, (2) adding a render branch to the composer registry, (3) referencing its tag in any context recipe. No screen is rewritten — every context that lists the tag picks it up.
