---
title: 'Epic E — Round-2 asks for the design agent (inductive newSkill reconciliation)'
type: design-ask
epic: E
stage: 1
round: 2
audience: 'the design agent that produced eng-coach-ui-design/lesson-delivery/'
date: 2026-07-11
status: Open — 3 asks (A1–A3); we have a read on each, want your confirm/redirect
parent: docs/plan/preact-parity-epic-E-design-agent-feedback-brief.md
---

# Round-2 asks — reconciling your **beat** layer into the **block** composer for `newSkill`

## What changed since round 1

You answered all 8 round-1 decisions (thank you — we adopted your three divergences). On the **one open item**
you flagged but didn't decide — the `newSkill` arc — we went with your framework rather than the authored composer:

**We chose the INDUCTIVE arc for `newSkill`.** Your own `Adaptive-Lesson-Protocol.md` §2.2 is normative and
unambiguous: `new` = **SCQA** = `ground → tension → question → rule` (first exposure, unfamiliar, learning),
whereas rule-first/deductive is the **`refresher` = ASC** ordering (high mastery, quick check). So the composer's
rule-first `newSkill` was the **ASC ordering wearing the `new` label** — a mismatch between your beat layer and your
block layer. We're honoring the beat protocol: a first-exposure learner gets discovery-first.

**Good news — this is a reconciliation, not new authoring.** The `ground` / `tension` / `question` copy is already
written in `English Coach - Lesson (Adaptive).dc.html` (e.g. *"You already use commas every day…"* / *"But a clause
can need a pair of commas…"* / *"So how do you tell when a clause actually needs its commas?"*). It exists as **beat
sections**, just not as **block-catalog entries**. We're lifting those 3 beats into 3 new block types so `newSkill`
renders `ground → tension → question → rule → workedExample → completionTry`.

Three things need your confirm/redirect before we spec it.

---

## A1 — Promote 3 beats to block-catalog types (role/zone + the first-exposure `tension`)

We're adding `ground`, `question`, and a first-exposure `tension` to the 9-block catalog so the composer can render
the inductive `newSkill`. Our read on each, from your `AL-2` beat colors (ground=neutral, question=accent,
tension=warning):

| new block | role / zone (our read) | source copy |
|---|---|---|
| `ground` | neutral / main | Adaptive `.dc.html` `ground` beat ("what you already know") |
| `question` | accent / main | Adaptive `.dc.html` `question` beat (one-line framing question) |
| `tension` (first-exposure) | warning / main | Adaptive `.dc.html` `tension` beat — **generic**, not miss-driven |

**The one real question:** your block-catalog `tension` is `misconceptionCallout`, which is **miss-data-driven**
("Across 4 missed items…"). A **first-exposure** learner has **no misses**. Your Adaptive `.dc.html` `tension` beat
is already written generically for `new` ("But a clause can need a pair of commas — or none — and the wrong choice
flips the meaning"). **Confirm:** is a **generic, no-miss-data first-exposure `tension`** faithful to your intent,
distinct from the returning-state `misconceptionCallout` — i.e. the same beat role, two block treatments (generic
at first exposure, miss-specific on return)? Or should first-exposure `tension` be treated differently?

## A2 — Do the beat-layer affordances carry onto the block composer?

Two of your beat-engine affordances have no home in the block composer as authored:
- `AL-12` **"▸ start here" opener marker** on the lead beat (in inductive `newSkill`, `ground` now leads).
- `AL-14` **color-dot sequence** (dots in beat-role colors, `seq` order, arrow-separated) showing the current order.

**Confirm:** do you want the opener marker + color-dot sequence carried onto the block-composer `newSkill` (they
reinforce the discovery arc), or are they **beat-engine-only** and intentionally dropped in a context/block build?
(We're not building the 6-mode engine, so there's no mode-switching for the dots to track — but they could still
mark the fixed inductive order.)

## A3 — Where does inductive `newSkill` end — the `rule`, or the `completionTry` win?

Two of your rules now point at **different blocks**:
- `AL-13` (beat law): "a self-contained lesson ends on the **`rule`** resolution."
- Your round-1 D2 answer (block layer): "resolution = the **win** (`completionTry`), not the rule block."

In the inductive arc, `rule` sits **mid-recipe** (`ground → tension → question → **rule** → workedExample →
completionTry`) and `completionTry` ends the main zone. So the two rules disagree about the ending.
**Confirm the intended ending for inductive `newSkill`:** end on the **rule** (the discovery pays off in the rule,
`AL-13`), or end on the **completionTry win** (teach-forward "ends on a win", your D2)? Our lean: end on the
**completionTry win** — the inductive arc *discovers* the rule mid-lesson, then the learner *applies* it to a doable
win, which is the stronger close. But you authored both rules; you decide.

---

## Smallest thing we need

**A1** (is a generic first-exposure `tension` faithful) and **A3** (end on rule or win) are the two that shape the
`newSkill` block order and content. **A2** we can default either way (carry the affordances) if you'd rather not
weigh in. With A1 + A3 we finalize the E1a spec.
