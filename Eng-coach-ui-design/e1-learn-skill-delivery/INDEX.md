# English Coach — E1 `/learn/skill` · delivery

The adaptive lesson, bound to real learner signals and shipped as one screen. `selectLessonContext({mastery, missTag, due})` recomposes the same skill's content into three contexts — **newSkill** (inductive, discover-first), **returning** (lead with the diagnosed miss, clear the due), **refresher** (rule-first, quick check). Every binding decision (D1–D8 / I1 / A1–A3) is ratified and traceable to the spec.

## standalones/ — open in any browser, offline
Double-click. Fully self-contained (design system + runtime inlined).
- **English Coach - Learn Skill (E1).html** — **the full surface.** A prototype inspector runs the real `selectLessonContext` across five learner-state scenarios; flip a chip and watch inputs → fired rule → the recomposed screen. Shows all three contexts, the I1 tagged/untagged callout toggle, and the D7 accuracy-vs-mastery gate.
- **English Coach - E1a newSkill.html** — the focused single-context artifact: the inductive first-exposure lesson (ground → pitfall → question → self-explain → rule → worked → try), with the interactive `completionTry` and the shown-back self-explain.

## sources/ — the editable Design Components (.dc.html)
Run inside the project (they load the AgentsFramework design system + the DC runtime; fully self-contained blocks, no child components to mount).
- `English Coach - Learn Skill (E1).dc.html` — source of the full 3-context surface.
- `English Coach - E1a newSkill.dc.html` — source of the focused newSkill lesson.

## specs/ — the contracts
- **PreACT-English-Coach-v2-E1-LearnSkill-Implementation-Spec.md** — the buildable spec, derived 1:1 from the prototype: `selectLessonContext` (§4), the composer + recipes + end-on-resolution guard (§5), the 12-block catalog with interaction contracts (§6), guards, full traceability (§9), acceptance criteria (§11), phasing (§12), and a decision→requirement map (§13). Companion to the v2 implementation spec; consumes its outer-loop signals and writes none of them.
- **Adaptive-Lesson-Decisions.md** — the ratified decision record: framing verdict + D1–D8 / I1 (round 1) and A1–A3 (round 2), each with rationale and the divergences from the partner team's leans.
- **Adaptive-Lesson-Protocol.md** — the beat model + `selectLessonContext` (§5.1) + the AL-13 block-layer guard, updated to reflect the ratified decisions.
- **Lesson-Block-Schema.md** + **lesson-blocks-schema.json** — the block catalog (9 tags + the 3 E1 beat-promotions → 12) + the inductive newSkill recipe.

## the two blockers, resolved (why E1a is buildable now)
- **D1** — `selectLessonContext({firstExposure, masteryPct, dueMisses, requested})`: first-exposure/unknown → newSkill; `mastery≥80 & due==0` → refresher; any `due>0` → returning; else newSkill. The newSkill→returning flip is due-driven — no mastery threshold.
- **D3** — `completionTry` is inert to the scheduler but interactive locally: click → grade + reveal, records nothing, moves no mastery/FSRS, no answer-branching. The "doable win" closes the lesson.

## reading order
1. Open `standalones/English Coach - Learn Skill (E1).html` → flip the five learner-state chips; watch the screen recompose and the trace update.
2. Toggle **Returning · tagged** ↔ **untagged** to see the I1 callout tiers; toggle **First exposure** ↔ **Learning** to see the D7 accuracy gate.
3. `specs/PreACT-English-Coach-v2-E1-LearnSkill-Implementation-Spec.md` for the contract; `Adaptive-Lesson-Decisions.md` for why each call was made.

## what rides E1b (next)
The tier-1 aggregate callout (reviewed tag-clustering pipeline), the accuracy aggregation for history states, and the **skill-anchored coach seed contract** (`OQ-3`/D4c) — the one seam the prototype stubs (the `coachEntry` button) and the spec flags as still-unspecified.
