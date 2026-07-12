---
title: 'Epic E — Skill-detail screen · Sprint Board'
type: sprint-board
epic: E
date: 2026-07-11
status: Draft — single-sprint board; Epic D released (gate cleared 2026-07-11); now gated only on content-source decision (E0)
derives_from: docs/plan/preact-parity-epics.md
report: docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md
spec_ref: 'Eng-coach-ui-design/PreACT-English-Coach-Spec.md §5.6 (Skill Detail / Tutorial)'
governs:
  - docs/plan/preact-parity-epic-E.brainstorm.md   # Stage-1 premise audit (written when E enters sdd-brainstorm)
  - docs/plan/preact-parity-E1-skill-detail.spec.md # EARS spec (written when E1 enters sdd-spec)
method: SDD lifecycle — one full pass (sdd-brainstorm → sdd-spec → implement → code-review → make check + arch-tests → sdd-converge)
adr: required (new route + engine data path) — see §Gates
---

# Epic E — Skill-detail screen · **Sprint Board**

**Epic goal** (from [epics doc §Epic E](preact-parity-epics.md#epic-e--skill-detail-screen---app-unbuilt--adr-gated)):
build the per-skill mini-lesson screen (spec §5.6) that today **404s** — the first of the two
unbuilt screens. Gives bucket cards and the Summary "See full lesson" action a real destination.

**Findings in scope:** `SD-1` (header + "Drill this skill"), `SD-2` (rule-in-one-line + worked
examples), `SD-3` ("Why you missed these" from learner misses), `SD-4` (accuracy bar chart, last 6
sessions), `SD-5` ("Due for review" FSRS count), `SD-6` (entry-point wiring), + the `D-4` caveat
(`?focus=` does not pin the scheduler). Source: [parity report §6](preact-ui-prototype-parity-VISUAL-gap-report.md).

> ⚠️ **This board revises the epics-doc E0/E1/E2/E3 split down to ONE sprint** based on a
> code-seam scout (2026-07-11). The epics doc assumed `E0 = build new engine reads` (`getTutorial`
> + miss/history aggregation). The scout **refuted** that: `getTutorial` / `listProgressPoints` and
> the `Tutorial` / `ProgressPoint` types **already exist end-to-end** (both `InMemoryEngineDb` and
> the live `DrizzleEngineDb`, real pg + sqlite tables). What the doc counted as the epic's largest,
> riskiest chunk is largely done. The genuinely-missing work (repo+wiring, a content write-path,
> SD-4 session aggregation) is a **single coherent slice** — so this board ships Epic E as **one
> releasable sprint (E1)**, preceded by a **docs-only content-source decision (E0)** that the
> constitution requires before any code (a dead/empty screen = the Q-6 trust-bug class Epic A just
> fixed).

---

## Premise correction — what the scout found (folded into scope below)

The scout mapped the epic-doc premises against the code. Verdict: the reads exist; the wiring,
content, and one aggregation do not. Full evidence:

| # | Epic-doc / report premise | Status | Evidence (verified `file:line`) |
|---|---|---|---|
| E-P1 | `E0` = build **new** `getTutorial` engine read | **REFUTED** | `getTutorial(subject, skillId)` already on the interface + **both** impls: [engine_db.ts:160](../../frontend/lib/adapters/engine/db/engine_db.ts:160), [in_memory_engine_db.ts:340](../../frontend/lib/adapters/engine/db/in_memory_engine_db.ts:340), [drizzle_engine_db.ts:612](../../frontend/lib/adapters/engine/db/drizzle_engine_db.ts:612) (queries real `pg.tutorial`) |
| E-P2 | `Tutorial` / `ProgressPoint` types must be authored | **REFUTED** | Zod types fully specified: [engine_entities.ts:272-293](../../frontend/lib/wire/engine_entities.ts:272) |
| E-P3 | SD-1 header data (bucket dot/name/share-of-test) needs new reads | **REFUTED** | `getSkillByKey`/`listSkills` exist ([engine_db.ts:64-65](../../frontend/lib/adapters/engine/db/engine_db.ts:64)); reusable VM pattern in [bucket_card_vm.ts](../../frontend/lib/translators/bucket_card_vm.ts) |
| E-P4 | SD-5 FSRS due-count needs a new per-skill read | **REFUTED** | Already wired via `LearnerReadRepo.listSkillState` (per-skill `due_at`): [learner_read_repo.ts:19-30](../../frontend/lib/ports/engine/learner_read_repo.ts:19) |
| E-P5 | SD-3 miss-history needs a new backend aggregation | **REFUTED** | Proven client-side join `missesOnSkill` (AttemptRepo.misses + QuestionRepo.get): [use_coach_surface.ts:37](../../frontend/components/coach/use_coach_surface.ts:37), [coach_surface_vm.ts:34](../../frontend/lib/translators/coach_surface_vm.ts:34) |
| E-P6 | SD-6 entry points must be built from scratch | **PARTLY REFUTED** | 2 of 3 already code-complete but **dormant** behind `comingSoon`: [BucketCard.tsx:6-26](../../frontend/components/dashboard/BucketCard.tsx:6) + [SummaryView.tsx:114-137](../../frontend/components/summary/SummaryView.tsx:114) both carry live `<Link href={skillScreen.route}>` branches + "re-points to Skill detail when S9 lands" TODOs |
| **E-P7** | `getTutorial` **returns usable content** today | **CONFIRMED-EMPTY** | `getTutorial` returns **`null` for every skill** — `seedTutorial`/`seedProgress` are **test-only** ([in_memory_engine_db.ts:10-12](../../frontend/lib/adapters/engine/db/in_memory_engine_db.ts:10) header); **no `insertTutorial` on the interface, no backend/CLI authoring path exists** (verified — the screen has no content until one is built). **This is the gating risk → E0 decision.** |
| **E-P8** | SD-4 "last 6 sessions accuracy" exists somewhere | **CONFIRMED-MISSING** | `listClosedSessionsByLearner` exists at the DB layer ([engine_db.ts:107](../../frontend/lib/adapters/engine/db/engine_db.ts:107)) but has **zero** non-DB consumers; no per-skill session-accuracy aggregation anywhere |
| E-P9 | `TutorialRepo`/`ProgressRepo` port exists | **CONFIRMED-MISSING** | Every other capability goes DB→typed repo→Ports bag; these two are **orphaned DB methods** — no port, no composition-root wiring |
| E-P10 | `D-4`: `?focus=` pins the scheduler to the skill | **REFUTED (caveat real)** | `?focus=` sets quiz **mode** only, never constrains which skill is served: [resolve_focus_mode.ts:9-40](../../frontend/components/quiz/resolve_focus_mode.ts:9) (matches the known drill-focus gap) |
| E-P11 | Route `/learn/skill` partially exists | **REFUTED** | No `frontend/app/(coach)/learn/skill/` dir — confirmed **404**; `nav_model.ts` `skill: comingSoon:true`, excluded from `NAV_MEMBERSHIP` ([nav_model.ts:75,104-106](../../frontend/components/shell/nav_model.ts:75)) |

**Net:** the big-ticket "backend seam" is done. Remaining = a **content write-path + decision**
(E0-gated), a thin **repo/wiring** layer, **SD-4 aggregation**, the **route + view**, and a
**nav/entry-point flip**. One sprint.

---

## Sprint ladder (one sprint + its mandatory decision predecessor)

| Sprint | Title | Findings | Type | Releasable alone? | Blocks |
|--------|-------|----------|------|-------------------|--------|
| **E0** | Decide the tutorial content-source | `SD-2`/`SD-3` content origin | **Decision + ADR** — no production code | ✅ yes (docs/ADR only) | E1 (unblocks its content path) |
| **E1** | Build `/learn/skill` (whole screen, one drop) | `SD-1…SD-6` + `D-4` caveat | Frontend Ring + thin engine repo/wiring + content write-path | ✅ yes | Epic C `S-5`, Epic D `D-8` (they gain a real destination) |

> **Why E0 is separate but not "a split."** E1 is the single sprint you asked for — the whole
> screen in one drop. E0 is **not production work**: it's the `decisions.md` + ADR entry the
> constitution *requires* before E1, because "where does tutorial text come from" is a product
> decision (`⚠️ Ask first`: new data path), and E1 physically can't render `SD-2`/`SD-3` until it's
> answered. Ranking it as a predecessor keeps E1 a clean, coherent single sprint instead of
> stalling mid-implementation on an unmade call. E0 is docs-only and ships independently.

---

## Sprint E0 — Decide the tutorial content-source  🟦 *(decision + ADR, no code)*

**Origin:** the scout (2026-07-11) found `getTutorial` returns `null` for every skill and there is
**no authoring path**. Before E1 can render the lesson body (`SD-2` "the rule, in one line" + worked
examples) and the miss write-up frame (`SD-3`), we must decide **where that content comes from**.
This is the ADR's central rejected-alternatives axis.

**The decision (options to adjudicate in the ADR):**

| Option | What it means | Trade-off |
|---|---|---|
| **A — Authored bank** | Tutorial rows authored per skill (like the item bank), written via a new `insertTutorial` seam + a dev-seed/CLI path | Highest fidelity to spec §5.6; most up-front work; needs a provenance story (cf. the item-bank cascade — **do not forge a provenance stamp**) |
| **B — Templated from Skill metadata** | Render `SD-1`/`SD-2` from existing `Skill` fields (name, rule summary, examples) with no new content store | Cheapest; ships now; but only as rich as `Skill` already is — may be thin for "worked examples" |
| **C — Engine-derived** | Compose the lesson from live signals (misses, examples pulled from attempted items) — no static tutorial at all | No authoring burden; always personalized; but `SD-2`'s *canonical* "the rule, in one line" isn't a per-learner artifact — risks losing the taught rule |
| **D — Hybrid** | Static rule/examples (B or A) + engine-derived "why you missed" (C for `SD-3`) | Matches the prototype's own split (left col = taught rule; "why you missed" = personalized); likely the real answer |

**E0 deliverable.** A `docs/adr/00NN-skill-tutorial-content-source.md` (copy `0000-template.md`)
recording the chosen option + rejected alternatives, and a 2–4 line [`decisions.md`](../adr/decisions.md)
pointer. **No production code.** This is the `⚠️ Ask first` ADR the epic is gated on (see §Gates).

**Releasability.** Docs/ADR only — ships independently, touches no VM/route.

---

## Sprint E1 — Build `/learn/skill` (whole screen, one drop)  🟧 *(ADR-gated — needs E0)*

**Goal.** Stand up the `/learn/skill` route end-to-end so it renders `SD-1…SD-5` from real engine
reads (per E0's content decision), wires the three `SD-6` entry points, flips the nav item on, and
returns **no 404**. Miss-history and per-skill session history are **real or honestly empty** — never
placeholder (AP-6 trust rule).

**In scope (findings → build shape, post-scout):**

| ID | Finding | Build shape |
|----|---------|-------------|
| `SD-1` | Header: bucket dot + name + "~19% of ACT English" + **"Drill this skill"** (bucket-tinted) | New `skill_detail_vm` off `getSkillByKey`/`listSkills` (reuse `bucket_card_vm` pattern); "Drill this skill" → Quiz `?focus=` |
| `SD-2` | "The rule, in one line" + ✓ worked examples | From E0's content source (A/B/D). If content-store: read via `getTutorial` behind a new `TutorialRepo` + composition wiring + write-path |
| `SD-3` | "Why you missed these" (auto-built from learner misses) | Reuse `missesOnSkill` join (AttemptRepo.misses + QuestionRepo.get) — skill-scoped; **honestly empty when no misses** |
| `SD-4` | Accuracy bar chart (last 6 sessions) | **New aggregation** over `listClosedSessionsByLearner`, per-skill — the one genuinely-new read; SVG bar chart (reuse dataviz conventions) |
| `SD-5` | "Due for review" (FSRS due-count per skill) | Already wired: `LearnerReadRepo.listSkillState` `due_at` → count |
| `SD-6` | Entry points: bucket card → here · Summary "See full lesson" → here · "Drill this skill" → Quiz | **Flip** the two dormant `<Link>` branches ([BucketCard](../../frontend/components/dashboard/BucketCard.tsx), [SummaryView](../../frontend/components/summary/SummaryView.tsx)) by landing the route + `comingSoon:false`; "Drill this skill" is the 3rd |
| `D-4` | `?focus=` does not pin the scheduler | **Scope call at spec time:** either resolve the pin (so "Drill this skill" actually drills *this* skill) or ship the interim (drill-mode opens, rotates all skills) + document it. Report marks this a caveat, not a blocker |

**Thin engine layer E1 must add (was mis-scoped as "E0 new reads"):**
- A `TutorialRepo` (+ `ProgressRepo` if the score-projection is pulled in — but that's Epic F; keep
  E1 to Tutorial) port wrapping the existing `getTutorial`, plus **composition-root wiring**
  ([composition_engine.ts](../../frontend/lib/adapters/engine/db/) + browser variant).
- **Iff E0 picks A (authored bank):** an `insertTutorial` seam on `EngineDb` + a dev-seed/authoring
  path + at least one real tutorial row so the screen isn't empty on merge.
- The **SD-4 per-skill session-accuracy aggregation** (new; no existing consumer).

**Nav flip (SD-6 completion).** [nav_model.ts:75](../../frontend/components/shell/nav_model.ts:75) —
set `skill: comingSoon:false` **and** add `skill` to `NAV_MEMBERSHIP` **only once the route renders
non-empty**. Flipping it before the screen has content = a dead nav item (the Q-6 / Epic-A bug
class). This unlocks Epic D's `D-8` "Skills" nav and Epic C's `S-5` tappable-skill destination.

**Release criteria.** `/learn/skill?skill=<id>` renders `SD-1…SD-5` from real engine reads (content
per E0); the three `SD-6` entry points route correctly; the nav item is enabled and leads here; **no
404**. Miss-history (`SD-3`) and per-skill session history (`SD-4`) are real or honestly empty. `D-4`
is either resolved or its interim documented. `make check` + `pytest tests/architecture/ -q` green.

**Independence / releasability.** Standalone route — ships without touching the core loop. Depends
**only** on E0 (content decision). Once merged, it retroactively completes two dormant links in
sibling epics (C `S-5`, D `D-8`) — but those epics don't block E1 and E1 doesn't block them.

**Tests (TDD, red first):**
- Route renders (no 404) + `SD-1` header from a seeded skill.
- `SD-3` shows real misses for a learner with a skill miss; shows the honest-empty state otherwise.
- `SD-4` bars reflect seeded closed sessions; empty state with none.
- `SD-6`: bucket card + Summary "See full lesson" navigate to `/learn/skill`; "Drill this skill" → Quiz.
- Nav: `skill` item enabled + present in membership; arch-tests still green (framework-agnostic
  boundaries, downward deps).
- E2E (`frontend/e2e/learn/skill-detail.spec.ts`, new): bucket card → skill → "Drill this skill" → Quiz.

---

## Gates

**ADR required (E0).** New route = new surface **and** the content-source is a new data path
(`⚠️ Ask first`: new abstraction / potential new write seam). Copy `docs/adr/0000-template.md` →
`docs/adr/00NN-skill-tutorial-content-source.md`; record the rejected alternatives (A/B/C/D above).
OKF: frontmatter `type:`, an `index.md` entry, a newest-first `log.md` line.

**Arch invariants (E1).** The new `TutorialRepo` + VM must respect the four-layer rules
(`components/` framework-agnostic; downward deps only; view is a thin wrapper). The SD-4 aggregation
is a **read** — no new graph node/service, so no *additional* ADR beyond E0's route/content one.

**Trust rule (AP-6).** `SD-3`/`SD-4` are trust signals: **real or honestly absent**, never a
placeholder count. Same discipline as Epic B's history line.

**Sequencing (program rule #1).** ✅ **Cleared 2026-07-11.** Epic D is **released** — D1 (#149), D3
(#150), and D4 (#151) are merged to `main`, and D-8 "Skills nav" was formally deferred to this epic
(`aca8c8d`). Epic E is now the one-in-flight epic; E1 may enter the lifecycle once E0's content-source
decision is made.

---

## Traceability

| Report finding (§6) | Sprint | Notes |
|---|---|---|
| `SD-1` header + "Drill this skill" | E1 | reads exist; new VM |
| `SD-2` rule-in-one-line + examples | E0 (source) → E1 (render) | content decision gates it |
| `SD-3` "Why you missed these" | E1 | reuse `missesOnSkill` |
| `SD-4` accuracy bar chart | E1 | **only genuinely-new read** |
| `SD-5` "Due for review" | E1 | already wired (`listSkillState`) |
| `SD-6` entry points | E1 | 2/3 dormant-wired; flip on route+nav |
| `D-4` `?focus=` scheduler pin | E1 | resolve or document interim |

**Coverage:** all six SD findings + the D-4 caveat assigned; 1 production sprint (E1) + 1 decision
predecessor (E0). No finding dropped or double-counted.

---

## What happens next

1. **You gatekeep** — Epic D must release before E1 enters the lifecycle. E0 (the content-source
   ADR) may be authored ahead since it's a decision doc, not code.
2. **E0:** run the content-source decision (default per prototype: **Option D — hybrid**), record
   the ADR + `decisions.md` pointer.
3. **E1:** `sdd-brainstorm` (premise audit — this board already did most of it) → `sdd-spec`
   (EARS `.spec.md`, resolve the `D-4` scope call) → implement (TDD, red first) → **code-review** →
   `make check` + arch-tests → `sdd-converge`.
4. On E1 release, Epic E is done; the program returns to the epics doc for the final epic (**F —
   Progress screen**), whose `listProgressPoints` read the scout also found **already built**.
