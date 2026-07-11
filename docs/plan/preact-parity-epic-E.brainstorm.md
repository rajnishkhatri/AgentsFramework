---
title: 'Epic E — Skill-detail screen · Stage-1 Brainstorm'
type: brainstorm
epic: E
stage: 1
date: 2026-07-11
status: Open — awaiting human direction gate
derives_from: docs/plan/preact-parity-sprint-board-E.md
report: docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md
spec_ref: 'Eng-coach-ui-design/PreACT-English-Coach-Spec.md §5.6 (Skill Detail / Tutorial)'
method: '.claude/skills/sdd-brainstorm — SDD Stage 1'
---

# Epic E — Skill-detail screen · **Stage-1 Brainstorm**

**Problem (as posed).** Build `/learn/skill` (spec §5.6), the per-skill mini-lesson that today
**404s** — findings `SD-1…SD-6` + the `D-4` caveat. The board flagged one open question that gates
the epic: **where does the tutorial content come from** (authored bank / templated from `Skill`
metadata / engine-derived / hybrid)? That decision drives the required ADR and blocks `SD-2`/`SD-3`.

This document does the Stage-1 job: **audit the premises against the live tree**, then generate and
validate directions **over the content-source decision** (the real fork), not over the screen layout
(which the spec already fixes). The human gate at the end picks a direction; we then advance to
`sdd-spec`.

---

## 1. Premise audit (verified against the working tree)

The board already ran a scout; this pass **re-verifies every load-bearing premise by opening the
file**, and surfaces two the board's content analysis missed (P-A1, P-A2 below). Method: grep/glob +
direct reads, never parametric memory.

| # | Premise | Status | Evidence (opened `file:line`) |
|---|---------|--------|-------------------------------|
| P1 | `getTutorial(subject, skillId)` exists on the engine port + both impls | **verified** | [engine_db.ts:160](../../frontend/lib/adapters/engine/db/engine_db.ts:160); in-memory [in_memory_engine_db.ts:340](../../frontend/lib/adapters/engine/db/in_memory_engine_db.ts:340); live pg [drizzle_engine_db.ts:612](../../frontend/lib/adapters/engine/db/drizzle_engine_db.ts:612) |
| P2 | `Tutorial` type is fully specified | **verified** | [engine_entities.ts:272-282](../../frontend/lib/wire/engine_entities.ts:272) |
| **P-A1** | **The `Tutorial` schema already encodes the content-source as *authored + reviewed + provenance-stamped*** | **verified — NEW** | `Tutorial` has `body_md`, `examples[]`, **`generated_from: string`** (provenance, exactly like the item bank), **`reviewed: boolean`**, and the doc-comment says *"same reviewed-gate as question"* ([engine_entities.ts:272-281](../../frontend/lib/wire/engine_entities.ts:272)). The schema is **not neutral** between the four options — it is shaped for Option A. |
| **P-A2** | **`getTutorial` has ZERO consumers and content cannot appear today** | **verified — NEW** | The only reference to `getTutorial`/`seedTutorial` outside `engine_db.ts` is `nav_model.ts`'s *comment* ([nav_model.ts:74](../../frontend/components/shell/nav_model.ts:74)). `seedTutorial` is called **only from within `in_memory_engine_db.ts` itself** (its own declaration) — no dev-seed, no test fixture, no VM. So `getTutorial` returns `null` for every skill and **nothing can render the lesson body until a content + write path is built.** |
| P3 | SD-1 header data (bucket dot/name/share) has existing reads + a VM pattern | **verified** | `getSkillByKey`/`listSkills` ([engine_db.ts:64-65](../../frontend/lib/adapters/engine/db/engine_db.ts:64)); reusable [bucket_card_vm.ts](../../frontend/lib/translators/bucket_card_vm.ts) |
| P4 | SD-5 FSRS due-count is already wired | **verified** | `LearnerReadRepo.listSkillState` → per-skill `due_at` |
| P5 | SD-3 miss-history reuses a proven join (no new backend read) | **verified** | `missesOnSkill` in [use_coach_surface.ts:37](../../frontend/components/coach/use_coach_surface.ts:37) + [coach_surface_vm.ts:34](../../frontend/lib/translators/coach_surface_vm.ts:34) |
| P6 | SD-6 entry points 2/3 already wired-but-dormant behind `comingSoon` | **verified** | Bucket card interim-drills to `?focus=` with "Re-points to Skill detail when S9 lands" ([BucketCard.tsx:6-26](../../frontend/components/dashboard/BucketCard.tsx:6)); Summary has **both** the disabled-button branch and a live `<Link href={skillScreen.route}>` branch ([SummaryView.tsx:114-137](../../frontend/components/summary/SummaryView.tsx:114)) |
| P7 | SD-4 "last 6 sessions accuracy" does NOT exist | **verified** | `listClosedSessionsByLearner` at [engine_db.ts:107](../../frontend/lib/adapters/engine/db/engine_db.ts:107) has **zero** non-DB consumers; no per-skill session-accuracy aggregation anywhere |
| P8 | No `TutorialRepo` port + no composition wiring | **verified** | `getTutorial` lives on `EngineDb` but there is no typed repo wrapping it and nothing wires it into a Ports bag (every *other* capability does) |
| P9 | `D-4`: `?focus=` does NOT pin the scheduler to the skill | **verified** | `?focus=` sets quiz **mode** only ([resolve_focus_mode.ts](../../frontend/components/quiz/resolve_focus_mode.ts)); matches the known drill-focus gap |
| P10 | Route `/learn/skill` 404s; nav item `comingSoon` + excluded from membership | **verified** | No `frontend/app/(coach)/learn/skill/`; [nav_model.ts:75,104-106](../../frontend/components/shell/nav_model.ts:75) |

**System-liveness check (per skill step 2).** The app is **live** and `/learn/skill` is **not
reachable** (route 404s, nav item disabled), so there is **no live open defect** on this surface —
unlike Epic A's dead Reveal button. The dormant Summary/BucketCard links are correctly gated behind
`comingSoon` and fail *safe* (disabled button / interim drill), so flipping them prematurely is the
risk to avoid, not a bug to fix now. **No D0 blocking direction is required.**

### What the audit changes about the framing

- **The content-source question is narrower than the board posed it.** P-A1 shows the `Tutorial`
  schema is already committed to *authored, reviewed, provenance-stamped* content (Option A shape).
  Options B/C/D don't get to redefine `Tutorial`; at most they decide **what fills `body_md` /
  `examples` / `generated_from`** and **whether the screen degrades when `getTutorial` is `null`**.
  So the real decision is: *author real rows now, or ship the screen degrading-gracefully over an
  empty tutorial store and defer authoring?* (re-posed as the directions below).
- **P-A2 makes "ship the whole screen in one sprint" contingent on a content decision**, confirming
  the board's E0-before-E1 ordering. Without it, E1 renders an empty left column.

---

## 2. Directions over the content-source decision

Six directions. The spec fixes the *layout*, so the design space is **how each SD region is
sourced** and **how the screen behaves before real content exists**. Three high-probability (follow a
named repo pattern) + three exploratory. The demand-side lens applies here in an unusual form: the
"expensive operation" isn't an LLM call, it's **human authoring effort + a provenance/review
obligation** — so the demand-side move is *"render the screen without requiring authored content to
exist yet."*

### High-probability (follow an existing repo pattern)

**D1 — Authored tutorial bank, mirrors the item-bank cascade.** *(pattern: the reviewed,
provenance-stamped item bank — [[coach-item-bank-live-adr0021]])*
Add an `insertTutorial` write seam + a bank-authoring/dev-seed path; author ≥1 real `Tutorial` per
in-scope skill with a truthful `generated_from` + `reviewed=true`. `SD-2` reads `body_md`/`examples`
via a new `TutorialRepo`.
- **Buys:** highest spec fidelity; the schema (`generated_from`/`reviewed`) is *designed* for this;
  consistent with how questions/hints already ship.
- **Breaks/cost:** the biggest lift — needs a write path + real authored content + a **provenance
  story**. Directly hits the known constraint: **do not forge a provenance stamp**
  ([[preact-s3-bounded-session-spec]] deferred bank-growth for exactly this reason). Calendar cost
  (authoring) not just engineering cost.
- **Stresses:** AGENTS.md `⚠️ Ask first` (new write seam on `EngineDb` ≈ new abstraction); reviewed-
  gate discipline.

**D2 — Template `SD-1`/`SD-2` from existing `Skill` metadata; no tutorial store read.** *(pattern:
[bucket_card_vm.ts](../../frontend/lib/translators/bucket_card_vm.ts) — a pure VM off `Skill`)*
Render header + a one-line rule + examples purely from fields already on `Skill` (name, any rule/
example fields). `getTutorial` is **not** called; the tutorial store stays empty.
- **Buys:** ships now, zero authoring, zero write path, no provenance obligation; smallest E0.
- **Breaks/cost:** only as rich as `Skill` already is — **gated on a data probe**: does `Skill`
  actually carry a rule string + worked examples? If not, `SD-2` is thin or empty. Leaves the
  `Tutorial` schema unused (dead code smell).
- **Stresses:** none structurally; risk is **content thinness**, not architecture.

**D3 — Degrade-gracefully over an empty tutorial store; author later.** *(pattern: the AP-6 "real or
honestly-absent" trust rule already used for the coach history line + `SD-3`/`SD-4` here)*
Build the whole route + `TutorialRepo` wiring now; `SD-2` renders an **honest empty state** ("Lesson
coming soon for this skill") whenever `getTutorial` returns `null`; `SD-1`/`SD-3`/`SD-4`/`SD-5` (which
don't need the tutorial store) render for real. Authoring real rows becomes a **follow-up**, not a
blocker. **Nav flip stays gated on the non-tutorial regions being real** (the screen is useful even
with an empty lesson).
- **Buys:** unblocks the *route + wiring + SD-1/3/4/5* immediately without an authoring/provenance
  commitment; keeps `Tutorial` schema live (the empty state reads it); real content slots in with no
  further UI work.
- **Breaks/cost:** the marquee `SD-2` region ("the rule, in one line") is empty at launch — a
  partial-parity ship. Must decide if a skill-detail screen **without its lesson** is worth shipping
  (arguably yes: SD-1/3/4/5 = header + why-you-missed + accuracy + due — already a real coaching
  surface).
- **Stresses:** none new; this is the demand-side answer (screen renders without content existing).

### Exploratory (different abstraction / integration / shift)

**D4 — Engine-derived lesson: compose `SD-2` from the learner's own attempted items.** *(shift:
personalize the *rule* the way `SD-3` personalizes misses)*
No static tutorial. "The rule, in one line" is pulled/summarized from the rationale of items the
learner attempted on this skill (the `Question.rationale`/hint rungs already exist).
- **Buys:** zero authoring; always personalized; reuses existing per-item rationale content.
- **Breaks/cost:** `SD-2`'s value is a **canonical, taught rule** — a per-learner derivation risks
  losing the one authoritative statement, and "summarize rationales" implies an LLM call (a new
  demand-side cost + a new seam). Empty for a learner with no attempts on the skill.
- **Stresses:** if summarization ⇒ LLM, that's `⚠️ Ask first` (new call site + a judge/telemetry
  obligation). Likely over-engineered for a "rule in one line."

**D5 — Hybrid: static rule/examples (D1 or D2) + engine-derived "why you missed" (`SD-3`).** *(shift:
match the prototype's own split — left col taught rule vs. personalized miss write-up)*
`SD-2` static (authored or templated); `SD-3` derived from misses (already the plan). This is what the
prototype actually shows: a fixed rule column + a personalized "why you missed these."
- **Buys:** matches the prototype's information architecture exactly; separates the *canonical* part
  (author once) from the *personalized* part (derive per learner).
- **Breaks/cost:** it's a **composition of D1/D2/D3 + D-already-planned-SD-3**, so it inherits
  whichever source you pick for `SD-2`. Not a distinct source so much as "SD-2 and SD-3 have
  *different* sources" — which is arguably just the correct default, not a separate option.
- **Stresses:** whatever the `SD-2` sub-choice stresses.

**D6 — Defer Epic E's `SD-2` entirely; ship `/learn/skill` as an analytics-only screen first.**
*(shift: re-scope the epic — split the "lesson" from the "skill dashboard")*
Ship SD-1 (header) + SD-3 (why-you-missed) + SD-4 (accuracy) + SD-5 (due) as the first `/learn/skill`
increment, with **no lesson body at all** (SD-2 explicitly out of scope for v1). SD-2 becomes a later
epic once the content-source is decided independently.
- **Buys:** removes the content-source decision from the critical path entirely; the screen still
  gives bucket cards + Summary a real destination (the entry-point unlock, SD-6, is the actual
  parity win). Smallest, fastest real route.
- **Breaks/cost:** spec §5.6's headline feature is the lesson; shipping without it is the furthest
  from parity. Risks the "See **full lesson**" button leading to a screen with no lesson (a
  labeling-trust smell — mitigate by relabeling the entry to "Skill detail" until SD-2 lands).
- **Stresses:** entry-point labeling honesty (the AP-6/Q-6 class again — the button text must match
  what the screen delivers).

---

## 3. Dependency structure + the real decision

- **Do-regardless (no ADR, independent of the source pick):** the `TutorialRepo` port + composition
  wiring (P8), the SD-4 session-accuracy aggregation (P7), the route shell + SD-1/SD-5, and flipping
  the two dormant SD-6 links (P6). None of these depend on *where SD-2 content comes from* — they can
  be specced now.
- **The one gated decision:** the **SD-2 content source**, which forks into two families:
  1. **"Author now"** (D1, or D5-with-D1): commit to the write path + provenance + real rows this
     sprint. Highest fidelity, highest cost, hits the "don't forge provenance" constraint head-on.
  2. **"Render without authored content"** (D2 / D3 / D6, or D5-with-D2): ship the screen now, source
     SD-2 from `Skill` metadata (D2), an honest empty state (D3), or omit it (D6) — defer/avoid the
     authoring+provenance obligation.
- **Capability vs. operational framing:** the *capability* (a `/learn/skill` route + entry-point
  unlock) is deliverable in one sprint under D2/D3/D6. The *content* (a real authored lesson per
  skill) is a **calendar-cost** authoring effort that D1 puts on the critical path and D3/D6 defer.
  Which one the human wants is the actual fork.
- **Data probe needed before D2 is viable:** does `Skill` carry a rule string + worked examples? If
  not, D2 collapses into D3 (empty SD-2). *(Tag: `needs-probe` — cheapest read is opening the `Skill`
  Zod type + one seeded skill row; do at spec time.)*

---

## 4. Leading direction + hypotheses (for the gate to accept or re-pose)

> **🔒 GATE OUTCOME (2026-07-11): the proposed lead was overridden — full-fidelity path chosen.**
> The human picked **D1 (author the bank now)** for Q-E1, **No / lesson-included** for Q-E2, and
> **Resolve the scheduler-pin** for Q-E3. So E1 is the **maximal** version: real reviewed tutorial
> rows + a write seam + the `?focus=` scheduler fix, all on the critical path. The D3-lead reasoning
> below is retained for the record; §7 captures the accepted decision and its consequences.

**Proposed lead (NOT chosen): D3 (degrade-gracefully) as the E1 sprint, with D1 (authored bank) as
the deferred follow-up** — i.e. build the whole route + wiring + SD-1/3/4/5 now over an honest empty
SD-2, and author real tutorials as a separate, provenance-clean effort later.

- **Works *because* X:** every SD region except SD-2 already has a real, wired data source (P3/P4/P5
  verified; SD-4 is a straightforward aggregation over an existing DB read). The screen is a genuine
  coaching surface (header + why-you-missed + accuracy + due) *without* the lesson body, so an honest
  empty SD-2 still ships real parity value + unlocks SD-6 entry points.
- **Safe *because* Y:** it never forges a provenance stamp (the `generated_from`/`reviewed` rows stay
  empty until truthfully authored — honoring [[preact-s3-bounded-session-spec]]); the nav flip is
  gated on the *real* regions, so no dead control ships (avoids the Q-6/Epic-A class); and it keeps
  the `Tutorial` schema live (the empty state path reads it), so D1 later is additive, not a rewrite.
- **What would re-pose it:** if the human wants **full §5.6 parity in one drop** (lesson included),
  the lead becomes **D1** (or D5-with-D1) and the sprint takes on the write-path + authoring +
  provenance ADR — a bigger, slower E1. If `Skill` turns out to already carry rule+examples (probe),
  **D2** could fill SD-2 for real with near-zero cost, beating D3.

---

## 5. Constitution check (per constraint)

- **`⚠️ Ask first` triggers:** D1 adds an `insertTutorial` write seam on `EngineDb` (new abstraction)
  → **ADR required**. D3/D2/D6 add a **read-only** `TutorialRepo` + a new route → still ADR-worthy as
  a **new surface + new data path** (the board already marks Epic E ADR-gated), but no *write* seam.
  Either way the ADR is the E0 deliverable.
- **Frontend Ring invariants (FD1/F-R1):** SD-4 aggregation is a **translator/VM** concern (pure);
  the view stays presentational; `getTutorial` is reached via a `TutorialRepo` port (no SDK/DB type
  escapes). No new `frontend/lib/` top-level dir (F2).
- **AP-6 trust rule:** `SD-3`/`SD-4`/`SD-2`-empty-state are all **real or honestly absent** — never a
  placeholder. This is load-bearing for D3.
- **Sequencing (program rule #1):** ✅ **cleared** — Epic D is **released** (D1 #149, D3 #150, D4
  #151 merged to `main`; D-8 "Skills nav" formally deferred to Epic E in `aca8c8d`). Epic E is now
  the one-in-flight epic and may enter the lifecycle.

---

## 6. Human gate — pick a direction (independent tracks)

Direction-level acceptance only. Three orthogonal questions the spec needs answered before it can be
written:

- **Q-E1 (the fork): SD-2 content source.** Author real tutorials now (**D1**), or ship the screen
  degrading-gracefully over an empty tutorial store and defer authoring (**D3**, lead), or template
  SD-2 from `Skill` metadata if the probe says it's rich enough (**D2**), or drop SD-2 from v1 and
  ship analytics-only (**D6**)?
- **Q-E2 (scope of the one sprint): is a `/learn/skill` that ships *without* a lesson body acceptable
  as the E1 increment** (SD-1/3/4/5 real, SD-2 empty/deferred), or must E1 include SD-2 for full §5.6
  parity (which pulls D1's write-path + authoring + provenance ADR onto the critical path)?
- **Q-E3 (the D-4 caveat): resolve or defer the scheduler-pin.** Make "Drill this skill" actually pin
  the skill (fix `?focus=` → scheduler), or ship the interim (drill-mode opens, rotates all skills)
  and document it as a known gap for a later sprint?

> Loop back if: a refuted premise wasn't re-posed (P-A1/P-A2 are the two that reshaped the framing —
> confirm you accept them), every direction violates an invariant, or the framing itself is rejected.
> On accept → **sdd-spec** with the chosen `{Q-E1, Q-E2, Q-E3}` triple + the validated hypotheses in §4.

---

## 7. Accepted decision (gate closed 2026-07-11) → hand-off to sdd-spec

| Question | Chosen | What it commits E1 to |
|---|---|---|
| **Q-E1** (SD-2 source) | **D1 — author the bank now** | Real `Tutorial` rows with a **truthful** `generated_from` + `reviewed=true`, read via a new `TutorialRepo`; a new **`insertTutorial` write seam** on `EngineDb` |
| **Q-E2** (E1 scope) | **No — lesson included** | Full §5.6: SD-2 (rule + worked examples) ships **in E1**, not deferred. Write-path + authoring + provenance are **on the critical path** |
| **Q-E3** (D-4 caveat) | **Resolve — pin the scheduler** | Fix `?focus=` so the scheduler serves **only** the drilled skill (`resolve_focus_mode.ts` + the scheduler seam), so "Drill this skill" is truthful |

**This is the maximal E1.** The brainstorm's own lead (D3) was overridden in favor of full parity.
That is a legitimate gate outcome, but it loads three obligations the **spec (sdd-spec) must now
resolve** — flagged here so they aren't discovered mid-implementation:

1. **Provenance is the central risk (Q-E1 → D1).** `reviewed=true` + `generated_from` must be
   *earned*, not stamped. The "never forge a provenance stamp" rule ([[preact-s3-bounded-session-spec]]
   deferred bank-growth for exactly this; [[coach-item-bank-live-adr0021]] is the cascade precedent)
   applies in full. **The spec must define the authoring/verification path that produces these rows**
   — where the content originates and what makes `reviewed=true` truthful — mirroring the item-bank
   cascade. Without that, D1 is just D3 wearing a forged stamp. **This is the single biggest thing to
   nail in the spec.**

2. **TWO `⚠️ Ask first` ADR triggers now fire, not one:**
   - the **`insertTutorial` write seam** on `EngineDb` (new abstraction / new write path), **and**
   - the **`?focus=` → scheduler-pin** change (Q-E3 — alters the drill/scheduler seam, a behavior
     change to how items are served).
   Both need ADR coverage. Fold them into the E0 route/content ADR (`docs/adr/00NN-skill-tutorial-
   content-source.md`) as two decisions, or split the scheduler-pin into its own ADR — the spec's
   call. The scheduler-pin also interacts with the known drill-focus gap ([[preact-drill-focus-not-pinned]]),
   so the ADR should note it *closes* that gap.

3. **The E1 sprint is now XL, single-drop.** It bundles: `TutorialRepo` + `insertTutorial` +
   composition wiring · authored content + verification · SD-4 session aggregation · the route +
   SD-1…SD-5 view · the scheduler-pin fix · the nav flip + SD-6 wiring. The board (E0 decision → E1
   build) still holds, but **sdd-spec should re-examine whether this survives program rule #4
   (independently releasable)** at this size, or whether the scheduler-pin (Q-E3) and/or the authored
   content (Q-E1) split into their own releasable slices. Raise this at spec time, don't assume.

**Next action:** advance to **sdd-spec** with the `{D1, lesson-included, resolve-pin}` triple. The
spec's first job is obligation #1 (the provenance/authoring cascade for `Tutorial` rows); its second
is the two-trigger ADR (#2); its third is the releasability re-check (#3).
