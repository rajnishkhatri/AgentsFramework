---
title: 'Epic E — Skill-detail lesson: DESIGN-side Stage-1 brainstorm'
type: brainstorm
epic: E
stage: 1
scope: 'design/UX treatment of the E1 flat lesson on /learn/skill — NOT re-deciding A1/B2'
date: 2026-07-11
status: Open — awaiting human design-direction gate
parent: docs/plan/preact-parity-epic-E-lesson-generation.brainstorm.md
board: docs/plan/preact-parity-sprint-board-E.md
design_prompt: docs/plan/preact-parity-epic-E-skill-detail.design-prompt.md
prototype: docs/plan/assets/preact-parity-2026-07-09/proto/06-skill-detail.png
method: 'sdd-brainstorm (design-side) — extract+verify+synthesize workflow, 11 agents, 11 refuted claims'
---

# Epic E — Skill-detail lesson: DESIGN-side Stage-1 brainstorm

> **Provenance.** Produced by a verify-first workflow: 5 parallel extractors pulled design
> constraints from the parity report §6, the pedagogy spec §7.1/§9.4, the design-token file, the
> sibling components, and the prototype HTML; an adversarial pass re-opened every file and **refuted
> 11 claims** (folded in below). Every premise cites a verified `file:line`. Cross-checked against the
> [prototype screenshot](assets/preact-parity-2026-07-09/proto/06-skill-detail.png) directly.

## Premise audit (design-relevant premises only)

| # | Premise | Status | Evidence |
|---|---------|--------|----------|
| P-1 | E1 lesson schema is flat: `body_md` + `examples[]`, NO `faded[]` field | **verified** | `frontend/lib/wire/engine_entities.ts:273-281` |
| P-2 | The §7.1 three-card faded ladder (●●● → ●●○ → ○○○) is a P2 aspiration needing a `skill.faded[]` field the E1 schema lacks | **verified** | pedagogy_spec §7.1 l.335-341 |
| P-3 | The Skill screen is a full mini-lesson (5 regions), NOT a stat page | **verified** | parity report §6 SD-1..SD-6; ui.spec FR-H1 |
| P-4 | Layout is a **two-column** body (left = rule+examples+why-missed; right = accuracy chart + due), NOT a 5-region vertical stack | **verified** | ui.spec l.240-242; prototype DOM left `flex:2` / right `flex:1`; verifier refuted the "five vertical regions" framing |
| **P-5** | Skill is a **non-focus, sidebar-bearing** screen on all surfaces; on iPhone the tab bar STAYS, NO ✕/back | **verified (refutes our earlier framing)** | ui.spec FR-B2 l.130-133 (✕/tab-hide is Quiz/Feedback/Coach/Summary only); FR-NAV-1 l.489. **The "stacked, no-tab-bar, back button" iPhone framing from the sibling §5.6 was WRONG — that's focus-screen chrome.** |
| P-6 | Header/tints are per-skill accent, but a *filled* CTA must use the **brand** pair (`bg-accent`/`text-on-accent`) for AA — per-bucket fill ~3.6:1 fails | **verified** | SummaryView.tsx:101-112 + AA comment. Prototype tints the CTA per-bucket; the repo's shipped rule overrides for a filled button |
| P-7 | Bucket accents resolve to concrete hex in both themes | **verified** | generated-theme.css:20-25 (light) + :64-69 (dark) |
| P-8 | No bar-chart/sparkline primitive exists; SD-4 must be built from the progressbar idiom | **verified** | grep found none; BucketCard.tsx:61-72, QuizProgress.tsx:56-66 |

**Corrected framing:** the deliverable is a **desktop two-column** Skill-detail mockup that (a) renders
the flat lesson (rule + `examples[]` ✓ list) in the left column, (b) reuses the `rounded-[13px]` card
idiom + per-skill `--accent` scoping + progressbar-derived bars, (c) keeps the sidebar on all surfaces
and the tab bar on iPhone, (d) leaves an obvious slot for the P2 faded ladder.

---

## Directions (design treatments of the same locked content)

**D1 — Prototype-faithful two-column** *(high-prob; follows SummaryView.tsx)* — reproduce prototype §06
verbatim: bucket-tinted header + two-column body (left rule-card + why-missed-card; right accuracy +
due). Highest parity, lowest risk. CTA is brand `bg-accent` (AA override of the prototype's per-bucket
gradient — the one annotated deviation). CTA is a `<button>`; bars carry `role="progressbar"` + number.

**D2 — Flat lesson as prose-first markdown block** *(high-prob; follows the `body_md` grain)* — render
`body_md` as one markdown region + `examples[]` as an inset ✓ list; a single lesson card, not a
rule-card+examples split. Cheapest bind, closest to schema; but reads flatter and gives P2 a weaker
insertion seam.

**D3 — "Examples as proto-cards" — flat now, faded later** *(exploratory; forward-compatible)* — render
each example as its own small worked-example card using the *same chrome the P2 ladder will use* (dots
slot + body slot), all in "worked ●●●" state in E1. Strongest P2 path + cleanest future diff; but risks
over-building E1 (three identical ●●● cards look redundant) → G1 new-abstraction question, flag needs-ADR
if the shell becomes a shared primitive.

**D4 — Accuracy-first right rail** *(exploratory; under-used-signal lens)* — make the 6-bar accuracy
cluster the centerpiece, lesson quiet. Serves SD-4 (the only region with no primitive) + SD-3; but
de-emphasizes the *lesson*, which is E1's headline — inverts the user's priority.

**D5 — Single-column responsive-first** *(exploratory; mobile-grain)* — design the iPhone stack first
(tab bar retained, no ✕ per P-5), widen to desktop. De-risks the responsive story + catches the refuted
iPhone premise by construction; but under-invests in the desktop two-column that is the parity target.

**D6 — "Insight callout" lesson** *(exploratory; reuses the misconception-card idiom)* — make "Why you
missed these" the hero via SummaryView's accent-callout treatment; rule/examples support it. Pedagogically
compelling + AA-safe + leakage-safe (whyMissed = `lib[tag].label + hint`, hints never reveal, DATA-7);
but subordinates the actual E1 lesson to the *most* [PROD]-deferred/placeholder-driven region.

---

## Leading direction: **D1 + D3's forward-compatible seam (scoped to one region)**

The ask wants both "consistent with the design system" (→ D1's verbatim reuse of `rounded-[13px]`,
`--accent` scoping, the brand-CTA AA split) and "a clear path to the P2 faded cards" (→ D3's reserved
shell). D1 gives the correct 2-column skeleton + max parity; D3 is scoped down to **one seam**: the
lesson region renders the flat `examples[]` ✓ list in E1 **with an annotated empty slot** ("P2: faded
ladder mounts here") rather than pre-building three redundant ●●● cards — P2 affordance without the G1
over-build.

**Hypotheses:**
- *Works because* the whole visual vocabulary already exists in siblings (card idiom, `--accent`
  inline-attr scoping, StatTile, progressbar-bar, brand-CTA/bordered-secondary AA split) — the mockup is
  a *recombination*, not a new design language. (All cited at file:line.)
- *Safe because* it keeps the sidebar on all surfaces + tab bar on iPhone (P-5), pairs every filled
  accent with its `on-*` foreground (P-6/P-7), and adds no Radix-backed shadcn primitive → strict CSP
  stays clean.
- *Forward-compatible because* the flat lesson region's card chrome + reserved P2 slot mean the faded
  ladder later changes dot-state + terminal-slot content, not the layout or region order.

**Dependency structure:** the mockup is *independent* of engine wiring — it renders placeholder data
(49%, "4 misses", "~19%") exactly as the prototype does; binding to real FSRS/history is a separate
[PROD] track. **The design artifact can be produced now with zero data dependency.** Do-regardless
hygiene: the mockup must annotate the two deliberate prototype deviations (brand CTA vs per-bucket
gradient; sidebar+tab-bar retained on iPhone vs a back button).

---

## Human gate — pick a design direction (not a spec)

- **Lesson-region form (E1):** D1-flat-✓-list (default, lowest risk) · D3-proto-cards (strongest P2
  path, G1 risk) · D2-prose-block (closest to `body_md`).
- **P2 foreshadowing intensity:** annotated empty slot (recommended) · pre-built ●●● cards · no visible
  P2 hint.
- **Do-regardless (no gate):** brand-CTA AA split · sidebar-on-all-surfaces · tab-bar-on-iPhone ·
  progressbar-derived bars with numeric labels · strict-CSP-safe primitives.

**The design-agent prompt** ([preact-parity-epic-E-skill-detail.design-prompt.md](preact-parity-epic-E-skill-detail.design-prompt.md))
encodes the leading direction (D1 flat ✓-list + reserved P2 slot). Confirm or switch the region form,
then hand the prompt to a design agent → then sdd-spec for the route + `getTutorial` read.

## Open design questions (gate these before/with the artifact)

1. **Lesson-region form** — flat ✓-list (chosen) vs proto-cards (D3) vs prose block (D2).
2. **P2 foreshadowing** — annotated empty slot (chosen) vs pre-rendered ●●● cards vs none.
3. **Accuracy-chart style** — progressbar-derived vertical bars (chosen; no primitive exists) vs a
   line/sparkline (new visual language + possible G1 primitive).
4. **CTA deviation** — confirm the AA-driven brand-accent fill (over the prototype's per-bucket gradient)
   is acceptable in the mockup (annotated).
5. **iPhone chrome** — confirm the corrected framing (tab bar stays, no ✕) — a refuted premise carried
   forward.
6. **Empty-state variant** — also show a brand-new-learner state (0 sessions / no misses), or defer to
   spec time?
7. **Secondary action** — does the Skill screen carry a secondary/bordered button, or is the single
   "Drill this skill" CTA enough for E1?
